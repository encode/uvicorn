import asyncio
import http
import logging
import traceback
from urllib.parse import unquote

import httptools


def _get_status_line(status_code):
    try:
        phrase = http.HTTPStatus(status_code).phrase.encode()
    except ValueError:
        phrase = b''
    return b''.join([
        b'HTTP/1.1 ', str(status_code).encode(), b' ', phrase, b'\r\n'
    ])


STATUS_LINE = {
    status_code: _get_status_line(status_code) for status_code in range(100, 600)
}


class HttpToolsProtocol(asyncio.Protocol):
    def __init__(self, app, loop=None, logger=None):
        self.app = app
        self.loop = loop or asyncio.get_event_loop()
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
        self.keep_alive = True

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

        if self.cycle and self.cycle.more_body:
            self.cycle.disconnected = True
        self.client_event.set()

    def eof_received(self):
        pass

    def data_received(self, data):
        self.parser.feed_data(data)

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
            "method": method.decode('ascii'),
            "path": parsed_url.path.decode('ascii'),
            "query_string": parsed_url.query if parsed_url.query else b'',
            "headers": self.headers,
        }

    def on_header(self, name: bytes, value: bytes):
        self.headers.append((name.lower(), value))

    def on_headers_complete(self):
        self.cycle = RequestResponseCycle(self.scope, self)
        asgi = self.app(self.scope)
        self.loop.create_task(self.cycle.run_asgi(asgi))

    def on_body(self, body: bytes):
        self.cycle.body += body
        self.pause_reading()
        self.client_event.set()

    def on_message_complete(self):
        self.cycle.more_body = False
        self.pause_reading()
        self.client_event.set()

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
    def __init__(self, scope, protocol):
        self.scope = scope
        self.protocol = protocol
        self.body = b''
        self.more_body = True
        self.disconnected = False
        self.keep_alive = True
        self.chunked_encoding = None

    # ASGI exception wrapper
    async def run_asgi(self, asgi):
        protcol = self.protocol

        try:
            result = await asgi(self.receive, self.send)
        except:
            msg = "Exception in ASGI application\n%s"
            traceback_text = "".join(traceback.format_exc())
            protocol.logger.error(msg, traceback_text)
            # if protcol.conn.our_state == h11.SEND_RESPONSE:
            #     await self.send({
            #         "type": "http.response.start",
            #         "status": 500,
            #         "headers": [
            #             (b"content-type", b"text/plain; charset=utf-8")
            #             (b"connection", b"close")
            #         ]
            #     })
            #     await self.send({
            #         "type": "http.response.body",
            #         "body": b"Internal Server Error"
            #     })
            # elif self.conn.our_state == h11.SEND_BODY:
            #     event = h11.ConnectionClosed()
            #     self.conn.send(event)
            #     self.transport.close()
            return

        if result is not None:
            msg = "ASGI callable should return None, but returned '%s'."
            protocol.logger.error(msg, result)

    # ASGI interface
    async def send(self, message):
        protocol = self.protocol
        message_type = message["type"]

        if not protocol.writable:
            await protocol.writable_event.wait()

        if message_type == "http.response.start":
            status_code = message["status"]
            headers = message.get("headers", [])
            if protocol.access_logs:
                protocol.logger.info(
                    '%s - "%s %s HTTP/%s" %d',
                    protocol.server[0],
                    self.scope["method"],
                    self.scope["path"],
                    self.scope["http_version"],
                    status_code,
                )
            content = [
                STATUS_LINE[status_code],
            ]
            for header_name, header_value in headers:
                header_name = header_name.lower()
                if header_name == b'content-length' and self.chunked_encoding is None:
                    self.chunked_encoding = False
                elif header_name == b'transfer-encoding' and header_value.lower() == b'chunked':
                    self.chunked_encoding = True
                elif header_name == b'connection' and header_value.lower() == b'close':
                    self.keep_alive = False
                content.extend([header_name, b': ', header_value, b'\r\n'])

            if self.chunked_encoding is None:
                self.chunked_encoding = True
                content.append(b'transfer-encoding: chunked\r\n')

            content.append(b'\r\n')
            protocol.transport.write(b''.join(content))

        elif message_type == "http.response.body":
            body = message.get("body", b"")
            more_body = message.get("more_body", False)

            if self.chunked_encoding:
                content = [
                    b'%x\r\n' % len(body),
                    body,
                    b'\r\n'
                ]
                if not more_body:
                    content.append(b'0\r\n\r\n')
                protocol.transport.write(b''.join(content))
            else:
                protocol.transport.write(body)

            if not more_body:
                if not self.keep_alive:
                    protocol.transport.close()
                else:
                    protocol.resume_reading()

        # if self.conn.our_state is h11.MUST_CLOSE:
        #     event = h11.ConnectionClosed()
        #     self.conn.send(event)
        #     self.transport.close()
        # elif self.conn.our_state is h11.DONE:
        #     self.scope = None
        #     while not self.queue.empty():
        #         self.queue.get_nowait()
        #     self.transport.resume_reading()
        #     if self.conn.their_state is h11.DONE:
        #         self.conn.start_next_cycle()

    async def receive(self):
        protocol = self.protocol

        if self.more_body and not self.body and not self.disconnected:
            protocol.resume_reading()
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
            self.body = b''
            protocol.resume_reading()

        return message
