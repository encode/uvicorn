import asyncio
from email.utils import formatdate
import http
import logging
import time
import traceback
from urllib.parse import unquote
from uvicorn.protocols.websockets.websockets_impl import websocket_upgrade

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


def _get_remote_from_proxy(scope):
    headers = dict(scope["headers"])
    scheme = scope["scheme"]
    client = scope["client"]

    if b"x-forwarded-proto" in headers:
        scheme = headers[b"x-forwarded-proto"].decode("ascii").strip()

    if b"x-forwarded-for" in headers:
        host = headers[b"x-forwarded-for"].decode("ascii").split(",")[-1].strip()
        try:
            port = int(headers[b"x-forwarded-port"].decode("ascii"))
        except (KeyError, ValueError):
            port = 0
        client = (host, port)

    return (scheme, client)


STATUS_LINE = {
    status_code: _get_status_line(status_code) for status_code in range(100, 600)
}

DEFAULT_HEADERS = _get_default_headers()

HIGH_WATER_LIMIT = 65536


class FlowControl:
    def __init__(self, transport):
        self._transport = transport
        self.read_paused = False
        self.write_paused = False
        self._is_writable_event = asyncio.Event()
        self._is_writable_event.set()

    async def drain(self):
        await self._is_writable_event.wait()

    def pause_reading(self):
        if not self.read_paused:
            self.read_paused = True
            self._transport.pause_reading()

    def resume_reading(self):
        if self.read_paused:
            self.read_paused = False
            self._transport.resume_reading()

    def pause_writing(self):
        if not self.write_paused:
            self.write_paused = True
            self._is_writable_event.clear()

    def resume_writing(self):
        if self.write_paused:
            self.write_paused = False
            self._is_writable_event.set()


class ServiceUnavailable:
    def __init__(self, scope):
        pass

    async def __call__(self, receive, send):
        await send(
            {
                "type": "http.response.start",
                "status": 503,
                "headers": [
                    (b"content-type", b"text/plain; charset=utf-8"),
                    (b"connection", b"close"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": b"Service Unavailable"})


class HttpToolsProtocol(asyncio.Protocol):
    def __init__(
        self,
        app,
        loop=None,
        connections=None,
        tasks=None,
        state=None,
        logger=None,
        proxy_headers=False,
        root_path="",
        limit_concurrency=None,
        timeout_keep_alive=5,
        timeout_response=60,
    ):
        self.app = app
        self.loop = loop or asyncio.get_event_loop()
        self.connections = set() if connections is None else connections
        self.tasks = set() if tasks is None else tasks
        self.state = {"total_requests": 0} if state is None else state
        self.logger = logger or logging.getLogger()
        self.parser = httptools.HttpRequestParser(self)
        self.proxy_headers = proxy_headers
        self.root_path = root_path
        self.limit_concurrency = limit_concurrency

        # Timeouts
        self.timeout_keep_alive_task = None
        self.timeout_keep_alive = timeout_keep_alive
        self.timeout_response = timeout_response

        # Per-connection state
        self.transport = None
        self.flow = None
        self.server = None
        self.client = None
        self.scheme = None
        self.pipeline = []

        # Per-request state
        self.scope = None
        self.headers = None
        self.expect_100_continue = False
        self.cycle = None
        self.message_event = asyncio.Event()

    @classmethod
    def tick(cls):
        global DEFAULT_HEADERS
        DEFAULT_HEADERS = _get_default_headers()

    # Protocol interface
    def connection_made(self, transport):
        self.connections.add(self)

        self.transport = transport
        self.flow = FlowControl(transport)
        self.server = transport.get_extra_info("sockname")
        self.client = transport.get_extra_info("peername")
        self.scheme = "https" if transport.get_extra_info("sslcontext") else "http"

        if self.logger.level <= logging.DEBUG:
            self.logger.debug("%s - Connected", self.server[0])

    def connection_lost(self, exc):
        self.connections.discard(self)

        if self.logger.level <= logging.DEBUG:
            self.logger.debug("%s - Disconnected", self.server[0])

        if self.cycle and not self.cycle.response_complete:
            self.cycle.disconnected = True
        self.message_event.set()

    def eof_received(self):
        pass

    def data_received(self, data):
        if self.timeout_keep_alive_task is not None:
            self.timeout_keep_alive_task.cancel()
            self.timeout_keep_alive_task = None

        try:
            self.parser.feed_data(data)
        except httptools.parser.errors.HttpParserError:
            msg = "Invalid HTTP request received."
            self.logger.warning(msg)
            self.transport.close()
        except httptools.HttpParserUpgrade:
            websocket_upgrade(self)

    # Parser callbacks
    def on_url(self, url):
        method = self.parser.get_method()
        parsed_url = httptools.parse_url(url)
        self.expect_100_continue = False
        self.headers = []
        self.scope = {
            "type": "http",
            "http_version": "1.1",
            "server": self.server,
            "client": self.client,
            "scheme": self.scheme,
            "method": method.decode("ascii"),
            "root_path": self.root_path,
            "path": parsed_url.path.decode("ascii"),
            "query_string": parsed_url.query if parsed_url.query else b"",
            "headers": self.headers,
        }

    def on_header(self, name: bytes, value: bytes):
        name = name.lower()
        if name == b"expect" and value.lower() == b"100-continue":
            self.expect_100_continue = True
        self.headers.append((name, value))

    def on_headers_complete(self):
        http_version = self.parser.get_http_version()
        if http_version != "1.1":
            self.scope["http_version"] = http_version
        if self.proxy_headers:
            scheme, client = _get_remote_from_proxy(self.scope)
            self.scope["scheme"] = scheme
            self.scope["client"] = client
        if self.parser.should_upgrade():
            return

        # Handle 503 responses when 'limit_concurrency' is exceeded.
        if self.limit_concurrency is not None and (
            len(self.connections) >= self.limit_concurrency
            or len(self.tasks) >= self.limit_concurrency
        ):
            app = ServiceUnavailable
            message = "Exceeded concurrency limit."
            self.logger.warning(message)
        else:
            app = self.app

        existing_cycle = self.cycle
        self.cycle = RequestResponseCycle(
            scope=self.scope,
            transport=self.transport,
            flow=self.flow,
            logger=self.logger,
            message_event=self.message_event,
            expect_100_continue=self.expect_100_continue,
            on_response=self.on_response_complete,
        )
        if existing_cycle is None or existing_cycle.response_complete:
            # Standard case - start processing the request.
            task = self.loop.create_task(self.cycle.run_asgi(app))
            task.add_done_callback(self.on_task_complete)
            self.tasks.add(task)
            self.loop.call_later(
                self.timeout_response, self.timeout_response_handler, task
            )
        else:
            # Pipelined HTTP requests need to be queued up.
            self.flow.pause_reading()
            self.pipeline.insert(0, (self.cycle, app))

    def on_body(self, body: bytes):
        if self.parser.should_upgrade() or self.cycle.response_complete:
            return
        self.cycle.body += body
        if len(self.cycle.body) > HIGH_WATER_LIMIT:
            self.flow.pause_reading()
        self.message_event.set()

    def on_message_complete(self):
        if self.parser.should_upgrade() or self.cycle.response_complete:
            return
        self.cycle.more_body = False
        self.message_event.set()

    def on_response_complete(self):
        # Callback for pipelined HTTP requests to be started.
        self.state["total_requests"] += 1

        if self.transport.is_closing():
            return

        # Set a short Keep-Alive timeout.
        self.timeout_keep_alive_task = self.loop.call_later(
            self.timeout_keep_alive, self.timeout_keep_alive_handler
        )

        # Unpause data reads if needed.
        self.flow.resume_reading()

        # Unblock any pipelined events.
        if self.pipeline:
            cycle, app = self.pipeline.pop()
            task = self.loop.create_task(cycle.run_asgi(app))
            task.add_done_callback(self.on_task_complete)
            self.tasks.add(task)
            self.loop.call_later(
                self.timeout_response, self.timeout_response_handler, task
            )

    def on_task_complete(self, task):
        self.tasks.discard(task)

    def shutdown(self):
        """
        Called by the server to commence a graceful shutdown.
        """
        if self.cycle is None or self.cycle.response_complete:
            self.transport.close()
        else:
            self.cycle.keep_alive = False

    def pause_writing(self):
        """
        Called by the transport when the write buffer exceeds the high water mark.
        """
        self.flow.pause_writing()

    def resume_writing(self):
        """
        Called by the transport when the write buffer drops below the low water mark.
        """
        self.flow.resume_writing()

    def timeout_keep_alive_handler(self):
        """
        Called on a keep-alive connection if no new data is received after a short delay.
        """
        if not self.transport.is_closing():
            self.transport.close()

    def timeout_response_handler(self, task):
        """
        Called once per task, when the reponse timeout is reached.
        """
        if not task.done():
            self.logger.error("Task exceeded response timeout.")
            task.cancel()


class RequestResponseCycle:
    def __init__(
        self,
        scope,
        transport,
        flow,
        logger,
        message_event,
        expect_100_continue,
        on_response,
    ):
        self.scope = scope
        self.transport = transport
        self.flow = flow
        self.logger = logger
        self.message_event = message_event
        self.on_response = on_response

        # Connection state
        self.disconnected = False
        self.keep_alive = True
        self.waiting_for_100_continue = expect_100_continue

        # Request state
        self.body = b""
        self.more_body = True

        # Response state
        self.response_started = False
        self.response_complete = False
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
            self.logger.error(msg, traceback_text)
            if not self.response_started:
                await self.send_500_response()
            else:
                self.transport.close()
        else:
            if result is not None:
                msg = "ASGI callable should return None, but returned '%s'."
                self.logger.error(msg, result)
                self.transport.close()
            elif not self.response_started:
                msg = "ASGI callable returned without starting response."
                self.logger.error(msg)
                if not self.disconnected:
                    await self.send_500_response()
            elif not self.response_complete:
                msg = "ASGI callable returned without completing response."
                self.logger.error(msg)
                if not self.disconnected:
                    self.transport.close()

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
        message_type = message["type"]

        if self.disconnected:
            return

        if self.flow.write_paused:
            await self.flow.drain()

        if not self.response_started:
            # Sending response status line and headers
            if message_type != "http.response.start":
                msg = "Expected ASGI message 'http.response.start', but got '%s'."
                raise RuntimeError(msg % message_type)

            self.response_started = True
            self.waiting_for_100_continue = False

            status_code = message["status"]
            headers = message.get("headers", [])

            if self.logger.level <= logging.INFO:
                self.logger.info(
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
            self.transport.write(b"".join(content))

        elif not self.response_complete:
            # Sending response body
            if message_type != "http.response.body":
                msg = "Expected ASGI message 'http.response.body', but got '%s'."
                raise RuntimeError(msg % message_type)

            body = message.get("body", b"")
            more_body = message.get("more_body", False)

            # Write response body
            if self.scope["method"] == "HEAD":
                self.expected_content_length = 0
            elif self.chunked_encoding:
                content = [b"%x\r\n" % len(body), body, b"\r\n"]
                if not more_body:
                    content.append(b"0\r\n\r\n")
                self.transport.write(b"".join(content))
            else:
                num_bytes = len(body)
                if num_bytes > self.expected_content_length:
                    raise RuntimeError("Response content longer than Content-Length")
                else:
                    self.expected_content_length -= num_bytes
                self.transport.write(body)

            # Handle response completion
            if not more_body:
                if self.expected_content_length != 0:
                    raise RuntimeError("Response content shorter than Content-Length")
                self.response_complete = True
                if not self.keep_alive:
                    self.transport.close()
                self.on_response()

        else:
            # Response already sent
            msg = "Unexpected ASGI message '%s' sent, after response already completed."
            raise RuntimeError(msg % message_type)

    async def receive(self):
        if self.waiting_for_100_continue and not self.transport.is_closing():
            self.transport.write(b"HTTP/1.1 100 Continue\r\n")
            self.waiting_for_100_continue = False

        self.flow.resume_reading()
        await self.message_event.wait()
        self.message_event.clear()

        if self.disconnected or self.response_complete:
            message = {"type": "http.disconnect"}
        else:
            message = {
                "type": "http.request",
                "body": self.body,
                "more_body": self.more_body,
            }
            self.body = b""

        return message
