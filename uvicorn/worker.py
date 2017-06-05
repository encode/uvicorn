# wrk -d20s -t10 -c200 http://127.0.0.1:8080/
# gunicorn app:hello_world --bind localhost:8080 --worker-class worker.ASGIWorker
# https://github.com/MagicStack/httptools - Fast HTTP parsing.
# https://github.com/aio-libs/aiohttp - An asyncio framework, including gunicorn worker.
# https://github.com/channelcat/sanic - An asyncio framework, including gunicorn worker.
# https://python-hyper.org/projects/h2/en/stable/asyncio-example.html - HTTP2 parser
# https://github.com/jeamland/guvnor - Gunicorn worker implementation
import asyncio
import functools
import io
import os

import httptools
import uvloop

from gunicorn.workers.base import Worker


class HttpProtocol(asyncio.Protocol):
    def __init__(self, consumer, loop, sock, cfg):
        self.request_parser = httptools.HttpRequestParser(self)
        self.consumer = consumer
        self.loop = loop
        self.transport = None

        self.base_message = {
            'reply_channel': self,
            'scheme': 'https' if cfg.is_ssl else 'http',
            'root_path': os.environ.get('SCRIPT_NAME', ''),
            'server': sock.getsockname()
        }

    # The asyncio.Protocol hooks...
    def connection_made(self, transport):
        self.transport = transport

    def connection_lost(self, exc):
        self.transport = None

    def eof_received(self):
        pass

    def data_received(self, data):
        self.request_parser.feed_data(data)

    # Event hooks called back into by HttpRequestParser...
    def on_message_begin(self):
        self.message = self.base_message.copy()
        self.headers = []
        self.body = []

    def on_url(self, url):
        parsed = httptools.parse_url(url)
        method = self.request_parser.get_method()
        http_version = self.request_parser.get_http_version()

        self.message.update({
            'http_version': http_version,
            'method': method.decode('ascii'),
            'path': parsed.path.decode('ascii'),
            'query_string': parsed.query if parsed.query else b'',
        })

    def on_header(self, name: bytes, value: bytes):
        self.headers.append([name.lower(), value])

    def on_headers_complete(self):
        self.message['headers'] = self.headers

    def on_body(self, body: bytes):
        self.body.append(body)

    def on_message_complete(self):
        self.message['body'] = b''.join(self.body)
        self.consumer({
            'reply_channel': self,
            'channel_layer': self,
            'message': self.message
        })

    def on_chunk_header(self):
        pass

    def on_chunk_complete(self):
        pass

    # Called back into by the ASGI consumer...
    def send(self, message):
        if self.transport is None:
            return

        status = message.get('status')
        if 'status' is not None:
            status_line = [b'HTTP/1.1 ', str(status).encode(), b'\r\n']
            self.transport.write(b''.join(status_line))

        headers = message.get('headers')
        if 'headers' is not None:
            headers_lines = []
            for header_name, header_value in headers:
                headers_lines.extend([header_name, b': ', header_value, b'\r\n'])
            headers_lines.append(b'\r\n')
            self.transport.write(b''.join(headers_lines))

        content = message.get('content')
        if content is not None:
            self.transport.write(content)

        more_content = message.get('more_content', False)
        if not more_content and not self.request_parser.should_keep_alive():
            self.transport.close()


class UvicornWorker(Worker):
    """
    A worker class for Gunicorn that interfaces with an ASGI consumer callable,
    rather than a WSGI callable.

    We use a couple of packages from MagicStack in order to achieve an
    extremely high-throughput and low-latency implementation:

    * `uvloop` as the event loop policy.
    * `httptools` as the HTTP request parser.
    """

    def init_process(self):
        # Close any existing event loop before setting a
        # new policy.
        asyncio.get_event_loop().close()

        # Setup uvloop policy, so that every
        # asyncio.get_event_loop() will create an instance
        # of uvloop event loop.
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

        super().init_process()

    def run(self):
        loop = asyncio.get_event_loop()
        loop.create_task(self.create_servers(loop))
        loop.run_forever()

    async def create_servers(self, loop):
        cfg = self.cfg
        consumer = self.wsgi

        for sock in self.sockets:
            protocol = functools.partial(
                HttpProtocol,
                consumer=consumer, loop=loop, sock=sock, cfg=cfg
            )
            await loop.create_server(protocol, sock=sock)
