import asyncio
import http
import logging
import traceback
from urllib.parse import unquote

import httptools


logger = logging.getLogger()


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
    def __init__(self, app, loop):
        self.app = app
        self.loop = loop
        self.parser = httptools.HttpRequestParser(self)

        # Per-connection state
        self.transport = None
        self.server = None
        self.client = None
        self.scheme = None

        # Per-request state
        self.scope = None
        self.headers = None
        self.queue = asyncio.Queue()

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
        logger.debug("%s - Connected", self.server[0])

    def connection_lost(self, exc):
        logger.debug("%s - Disconnected", self.server[0])
        message = {"type": "http.disconnect"}
        self.queue.put_nowait(message)

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
        asgi = self.app(self.scope)
        self.loop.create_task(self.run_asgi(asgi))

    def on_body(self, body: bytes):
        self.pause_reading()
        message = {
            "type": "http.request",
            "body": body,
            "more_body": True,
        }
        self.queue.put_nowait(message)

    def on_message_complete(self):
        message = {"type": "http.request", "body": b"", "more_body": False}
        self.queue.put_nowait(message)

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

    # ASGI exception wrapper
    async def run_asgi(self, asgi):
        try:
            result = await asgi(self.receive, self.send)
        except:
            msg = "Exception in ASGI application\n%s"
            traceback_text = "".join(traceback.format_exc())
            logger.error(msg, traceback_text)
            if self.conn.our_state == h11.SEND_RESPONSE:
                await self.send({
                    "type": "http.response.start",
                    "status": 500,
                    "headers": [
                        (b"content-type", b"text/plain; charset=utf-8")
                        (b"connection", b"close")
                    ]
                })
                await self.send({
                    "type": "http.response.body",
                    "body": b"Internal Server Error"
                })
            # elif self.conn.our_state == h11.SEND_BODY:
            #     event = h11.ConnectionClosed()
            #     self.conn.send(event)
            #     self.transport.close()
            return

        if result is not None:
            msg = "ASGI callable should return None, but returned '%s'."
            logger.error(msg, result)

    # ASGI interface
    async def send(self, message):
        if not self.writable:
            await self.writable_event.wait()

        message_type = message["type"]

        if message_type == "http.response.start":
            status_code = message["status"]
            headers = message.get("headers", [])
            logger.info(
                '%s - "%s %s HTTP/%s" %d',
                self.server[0],
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
                # if header_name == b'content-length':
                #     self.content_length = int(header_value.decode())
                if header_name == b'connection' and header_value.lower() == b'close':
                    self.keep_alive = False
                content.extend([header_name, b': ', header_value, b'\r\n'])
            content.append(b'\r\n')
            self.transport.write(b''.join(content))

        elif message_type == "http.response.body":
            body = message.get("body", b"")
            more_body = message.get("more_body", False)
            self.transport.write(body)

            if not more_body:
                if not self.keep_alive:
                    self.transport.close()

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
        # if self.conn.our_state == h11.CLOSED and self.queue.empty():
        #     raise RuntimeError("Connection is closed")
        self.resume_reading()
        return await self.queue.get()
