# wrk -d20s -t10 -c200 http://127.0.0.1:8080/
# gunicorn app:app --bind localhost:8080 --worker-class worker.AsyncioWorker
# https://github.com/MagicStack/httptools - Fast HTTP parsing.
# https://github.com/aio-libs/aiohttp - An asyncio framework, including gunicorn worker.
# https://github.com/channelcat/sanic - An asyncio framework, including gunicorn worker.
# https://python-hyper.org/projects/h2/en/stable/asyncio-example.html - HTTP2 parser
# https://github.com/jeamland/guvnor - Gunicorn worker implementation
import asyncio
import functools
import httptools
import io
import uvloop

from gunicorn.http.wsgi import base_environ
from gunicorn.workers.base import Worker


class HttpProtocol(asyncio.Protocol):
    def __init__(self, wsgi, loop, sockname, cfg):
        self.request_parser = httptools.HttpRequestParser(self)
        self.wsgi = wsgi
        self.loop = loop
        self.sockname = sockname
        self.cfg = cfg
        self.transport = None

    # The asyncio.Protocol hooks...
    def connection_made(self, transport):
        self.transport = transport

    def connection_lost(self, exc):
        pass

    def eof_received(self):
        pass

    def data_received(self, data):
        self.request_parser.feed_data(data)

    # Event hooks called by request_parser...
    def on_message_begin(self):
        self.headers = {}
        self.body = b''
        self.url = None

    def on_url(self, url):
        self.url = httptools.parse_url(url)

    def on_header(self, name: bytes, value: bytes):
        self.headers[name] = value

    def on_headers_complete(self):
        pass

    def on_body(self, body: bytes):
        self.body += body

    def on_message_complete(self):
        url = self.url
        method = self.request_parser.get_method()

        environ = base_environ(self.cfg)
        environ.update({
            'PATH_INFO': url.path.decode('latin-1'),
            'QUERY_STRING': url.query.decode('latin-1') if url.query else '',
            'REQUEST_METHOD': method.decode('latin-1'),
            'wsgi.input': io.BytesIO(self.body),
        })

        body_iterator = self.wsgi(environ, self.start_response)
        self.transport.write(self.response_bytes)
        for body_chunk in body_iterator:
            self.transport.write(body_chunk)
        if not self.request_parser.should_keep_alive():
            self.transport.close()

    def on_chunk_header(self):
        pass

    def on_chunk_complete(self):
        pass

    # Called by the WSGI app...
    def start_response(self, status, response_headers):
        response_bytes = b'HTTP/1.1 '
        response_bytes += status.encode('latin-1')
        response_bytes += b'\r\n'
        for header_name, header_value in response_headers:
            response_bytes += header_name.encode('latin-1')
            response_bytes += b': '
            response_bytes += header_value.encode('latin-1')
            response_bytes += b'\r\n'
        response_bytes += b'\r\n'
        self.response_bytes = response_bytes


class AsyncioWorker(Worker):
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
        wsgi = self.wsgi

        for sock in self.sockets:
            sockname = sock.getsockname()
            protocol = functools.partial(
                HttpProtocol,
                wsgi=wsgi, loop=loop, sockname=sockname, cfg=cfg
            )
            await loop.create_server(protocol, sock=sock)
