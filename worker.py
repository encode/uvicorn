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
import os
import uvloop

from gunicorn.http.wsgi import base_environ
from gunicorn.workers.base import Worker


class HttpProtocol(asyncio.Protocol):
    def __init__(self, wsgi, loop, sock, cfg):
        self.request_parser = httptools.HttpRequestParser(self)
        self.wsgi = wsgi
        self.loop = loop
        self.transport = None

        sockname = sock.getsockname()

        self.base_environ = base_environ(cfg)
        self.base_environ.update({
            'SCRIPT_NAME': os.environ.get('SCRIPT_NAME', ''),
            'SERVER_NAME': sockname[0],
            'SERVER_PORT': str(sockname[1]),
            'wsgi.url_scheme': 'https' if cfg.is_ssl else 'http',
        })

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
        self.environ = self.base_environ.copy()
        self.environ['wsgi.input'] = self.input = io.BytesIO()

    def on_url(self, url):
        parsed = httptools.parse_url(url)
        method = self.request_parser.get_method()
        http_version = self.request_parser.get_http_version()
        self.environ.update({
            'SERVER_PROTOCOL': http_version,
            'PATH_INFO': parsed.path.decode('ascii'),
            'QUERY_STRING': parsed.query.decode('ascii') if parsed.query else '',
            'REQUEST_METHOD': method.decode('ascii'),
        })

    def on_header(self, name: bytes, value: bytes):
        key = name.decode('ascii').upper().replace('-', '_')
        content = value.decode('ascii')

        if key in ('HOST', 'CONTENT_LENGTH', 'CONTENT_TYPE', 'SCRIPT_NAME'):
            self.environ[key] = content
        elif key == 'EXPECT':
            # Respond to 'Expect: 100-Continue' headers.
            if content.lower() == '100-continue':
                self.transport.write('HTTP/1.1 100 Continue\r\n\r\n')
        else:
            key = 'HTTP_' + key
            if key in self.environ:
                # Handle repeated headers.
                content = self.environ[key] + ',' + content
            self.environ[key] = content

    def on_body(self, body: bytes):
        self.input.write(body)

    def on_message_complete(self):
        self.input.seek(0)

        body_iterator = self.wsgi(self.environ, self.start_response)
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
        response = [
            b'HTTP/1.1 ',
            status.encode('ascii'),
            b'\r\n'
        ]
        for header_name, header_value in response_headers:
            response.extend([
                header_name.encode('ascii'), b': ',
                header_value.encode('ascii'), b'\r\n'
            ])
        response.append(b'\r\n')
        self.response_bytes = b''.join(response)


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
            protocol = functools.partial(
                HttpProtocol,
                wsgi=wsgi, loop=loop, sock=sock, cfg=cfg
            )
            await loop.create_server(protocol, sock=sock)
