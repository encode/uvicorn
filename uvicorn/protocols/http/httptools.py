import asyncio
from email.utils import formatdate
import http
import logging
import time
import traceback
from urllib.parse import unquote
from uvicorn.protocols.websockets.websockets import websocket_upgrade

import httptools


def _get_default_headers():
    current_time = time.time()
    current_date = formatdate(current_time, usegmt=True).encode()
    return b"".join([b"server: uvicorn\r\ndate: ", current_date, b"\r\n"])


def _get_status_line(status_code):
    try:
        phrase = http.HTTPStatus(status_code).phrase.encode()
    except ValueError:
        phrase = b""
    return b"".join([b"HTTP/1.1 ", str(status_code).encode(), b" ", phrase, b"\r\n"])


STATUS_LINE = {
    status_code: _get_status_line(status_code) for status_code in range(100, 600)
}

DEFAULT_HEADERS = _get_default_headers()

HIGH_WATER_LIMIT = 65536


class HttpToolsProtocol(asyncio.Protocol):
    __slots__ = (
        'app', 'loop', 'state', 'logger', 'access_logs', 'parser',
        'transport', 'server', 'client', 'scheme',
        'scope', 'headers', 'cycle', 'client_event',
        'readable', 'writable', 'writable_event',
        'pipeline'
    )

    def __init__(self, app, loop=None, state=None, logger=None):
        self.app = app
        self.loop = loop or asyncio.get_event_loop()
        self.state = {"total_requests": 0} if state is None else state
        self.logger = logger or logging.getLogger()
        self.access_logs = self.logger.level >= logging.INFO
        self.parser = httptools.HttpRequestParser(self)

        # Per-connection state
        self.transport = None
        self.server = None
        self.client = None
        self.scheme = None

        # Per-request state
        self.scope = None
        self.headers = None
        self.cycle = None
        self.client_event = asyncio.Event()

        # Flow control
        self.readable = True
        self.writable = True
        self.writable_event = asyncio.Event()
        self.writable_event.set()

        self.pipeline = []

    @classmethod
    def tick(cls):
        global DEFAULT_HEADERS
        DEFAULT_HEADERS = _get_default_headers()

    # Protocol interface
    def connection_made(self, transport):
        self.transport = transport
        self.server = transport.get_extra_info("sockname")
        self.client = transport.get_extra_info("peername")
        self.scheme = "https" if transport.get_extra_info("sslcontext") else "http"
        if self.access_logs:
            self.logger.debug("%s - Connected", self.server[0])

    def connection_lost(self, exc):
        if self.access_logs:
            self.logger.debug("%s - Disconnected", self.server[0])

        if self.cycle and not self.cycle.response_complete:
            self.cycle.disconnected = True
        self.client_event.set()

    def eof_received(self):
        pass

    def data_received(self, data):
        try:
            self.parser.feed_data(data)
        except httptools.parser.errors.HttpParserError:
            msg = "Invalid HTTP request received."
            self.logger.warn(msg)
            self.transport.close()
        except httptools.HttpParserUpgrade:
            websocket_upgrade(self)

    # Parser callbacks
    def on_url(self, url):
        method = self.parser.get_method()
        parsed_url = httptools.parse_url(url)
        self.headers = []
        self.scope = {
            "type": "http",
            "http_version": "1.1",
            "server": self.server,
            "client": self.client,
            "scheme": self.scheme,
            "method": method.decode("ascii"),
            "path": parsed_url.path.decode("ascii"),
            "query_string": parsed_url.query if parsed_url.query else b"",
            "headers": self.headers,
        }

    def on_header(self, name: bytes, value: bytes):
        self.headers.append((name.lower(), value))

    def on_headers_complete(self):
        http_version = self.parser.get_http_version()
        if http_version != "1.1":
            self.scope["http_version"] = http_version
        if self.parser.should_upgrade():
            return

        existing_cycle = self.cycle
        self.cycle = RequestResponseCycle(self.scope, self)
        if existing_cycle is None or existing_cycle.response_complete:
            # Standard case - start processing the request.
            self.loop.create_task(self.cycle.run_asgi(self.app))
        else:
            # Pipelined HTTP requests need to be queued up.
            self.pause_reading()
            existing_cycle.done_callback = self.on_response_complete
            self.pipeline.insert(0, self.cycle)

    def on_body(self, body: bytes):
        if self.parser.should_upgrade() or self.cycle.response_complete:
            return
        self.cycle.body += body
        if len(self.cycle.body) > HIGH_WATER_LIMIT:
            self.pause_reading()
        self.client_event.set()

    def on_message_complete(self):
        if self.parser.should_upgrade() or self.cycle.response_complete:
            return
        self.cycle.more_body = False
        self.client_event.set()

    def on_response_complete(self):
        # Callback for pipelined HTTP requests to be started.
        if self.pipeline and not self.transport.is_closing():
            cycle = self.pipeline.pop()
            self.loop.create_task(cycle.run_asgi(self.app))
            if not self.pipeline:
                self.resume_reading()

    # Flow control
    def pause_reading(self):
        if self.readable:
            self.readable = False
            self.transport.pause_reading()

    def resume_reading(self):
        if not self.readable:
            self.readable = True
            self.transport.resume_reading()

    def pause_writing(self):
        if self.writable:
            self.writable = False
            self.writable_event.clear()

    def resume_writing(self):
        if not self.writable:
            self.writable = True
            self.writable_event.set()


class RequestResponseCycle:
    __slots__ = (
        'scope', 'protocol', 'disconnected', 'done_callback',
        'body', 'more_body',
        'response_started', 'response_complete', 'keep_alive', 'chunked_encoding', 'expected_content_length'
    )

    def __init__(self, scope, protocol):
        self.scope = scope
        self.protocol = protocol
        self.disconnected = False
        self.done_callback = None

        # Request state
        self.body = b""
        self.more_body = True

        # Response state
        self.response_started = False
        self.response_complete = False
        self.keep_alive = True
        self.chunked_encoding = None
        self.expected_content_length = 0

    # ASGI exception wrapper
    async def run_asgi(self, app):
        try:
            asgi = app(self.scope)
            result = await asgi(self.receive, self.send)
        except:
            msg = "Exception in ASGI application\n%s"
            traceback_text = "".join(traceback.format_exc())
            self.protocol.logger.error(msg, traceback_text)
            if not self.response_started:
                await self.send_500_response()
            else:
                self.protocol.transport.close()
        else:
            if not self.response_started:
                msg = "ASGI callable returned without starting response."
                self.protocol.logger.error(msg)
                await self.send_500_response()
            elif not self.response_complete:
                msg = "ASGI callable returned without completing response."
                self.protocol.logger.error(msg)
                self.protocol.transport.close()
            elif result is not None:
                msg = "ASGI callable should return None, but returned '%s'."
                self.protocol.logger.error(msg, result)
                self.protocol.transport.close()
        finally:
            self.protocol.state["total_requests"] += 1
            if self.done_callback is not None:
                self.done_callback()

    async def send_500_response(self):
        await self.send(
            {
                "type": "http.response.start",
                "status": 500,
                "headers": [
                    (b"content-type", b"text/plain; charset=utf-8"),
                    (b"connection", b"close"),
                ],
            }
        )
        await self.send(
            {"type": "http.response.body", "body": b"Internal Server Error"}
        )

    # ASGI interface
    async def send(self, message):
        protocol = self.protocol
        message_type = message["type"]

        if self.disconnected:
            return

        if not protocol.writable:
            await protocol.writable_event.wait()

        if not self.response_started:
            # Sending response status line and headers
            if message_type != "http.response.start":
                msg = "Expected ASGI message 'http.response.start', but got '%s'."
                raise RuntimeError(msg % message_type)

            self.response_started = True

            status_code = message["status"]
            headers = message.get("headers", [])

            if protocol.access_logs:
                protocol.logger.info(
                    '%s - "%s %s HTTP/%s" %d',
                    self.scope["server"][0],
                    self.scope["method"],
                    self.scope["path"],
                    self.scope["http_version"],
                    status_code,
                )

            # Write response status line and headers
            content = [STATUS_LINE[status_code], DEFAULT_HEADERS]

            for name, value in headers:
                name = name.lower()
                if name == b"content-length" and self.chunked_encoding is None:
                    self.expected_content_length = int(value.decode())
                    self.chunked_encoding = False
                elif name == b"transfer-encoding" and value.lower() == b"chunked":
                    self.expected_content_length = 0
                    self.chunked_encoding = True
                elif name == b"connection" and value.lower() == b"close":
                    self.keep_alive = False
                content.extend([name, b": ", value, b"\r\n"])

            if self.chunked_encoding is None:
                # Neither content-length nor transfer-encoding specified
                self.chunked_encoding = True
                content.append(b"transfer-encoding: chunked\r\n")

            content.append(b"\r\n")
            protocol.transport.write(b"".join(content))

        elif not self.response_complete:
            # Sending response body
            if message_type != "http.response.body":
                msg = "Expected ASGI message 'http.response.body', but got '%s'."
                raise RuntimeError(msg % message_type)

            body = message.get("body", b"")
            more_body = message.get("more_body", False)

            # Write response body
            if self.chunked_encoding:
                content = [b"%x\r\n" % len(body), body, b"\r\n"]
                if not more_body:
                    content.append(b"0\r\n\r\n")
                protocol.transport.write(b"".join(content))
            else:
                num_bytes = len(body)
                if num_bytes > self.expected_content_length:
                    raise RuntimeError("Response content longer than Content-Length")
                else:
                    self.expected_content_length -= num_bytes
                protocol.transport.write(body)

            # Handle response completion
            if not more_body:
                if self.expected_content_length != 0:
                    raise RuntimeError("Response content shorter than Content-Length")
                self.response_complete = True
                if not self.keep_alive:
                    protocol.transport.close()
                else:
                    protocol.resume_reading()
        else:
            # Response already sent
            msg = "Unexpected ASGI message '%s' sent, after response already completed."
            raise RuntimeError(msg % message_type)

    async def receive(self):
        # If a client calls recieve once they've already sent the response
        # then raise an error. Allows us to stop buffering any more request
        # body to memory once the response has been sent.
        if self.response_complete:
            msg = "Response already sent. Receive channel no longer available."
            raise RuntimeError(msg)

        protocol = self.protocol
        protocol.resume_reading()

        if self.more_body and not self.body and not self.disconnected:
            await protocol.client_event.wait()
            protocol.client_event.clear()

        if self.disconnected:
            message = {"type": "http.disconnect"}
        else:
            message = {
                "type": "http.request",
                "body": self.body,
                "more_body": self.more_body,
            }
            self.body = b""

        return message
