import asyncio
import collections

import httptools

from uvicorn.protocols.websocket import websocket_upgrade
from uvicorn.protocols.request import AsgiHttpRequestHandler
from uvicorn.protocols.utils import create_application_instance


LOW_WATER_LIMIT = 16384
HIGH_WATER_LIMIT = 65536
MAX_PIPELINED_REQUESTS = 20


class HttpProtocol(asyncio.Protocol):

    __slots__ = [
        'application',
        'application_queue',
        'loop',
        'state',
        'base_message',
        'message',
        'request_handler',
        'request_parser',
        'transport',
        'headers',
        'upgrade',
        'read_paused',
        'write_paused',
        'buffer_size',
        'high_water_limit',
        'low_water_limit',
        'max_pipelined_requests',
        'pipeline_queue',
    ]

    def __init__(self, application, loop=None, state=None):
        self.application = application
        self.application_queue = asyncio.Queue()
        self.loop = loop or asyncio.get_event_loop()
        self.state = {'total_requests': 0} if state is None else state
        self.request_handler = None
        self.request_parser = httptools.HttpRequestParser(self)
        self.base_message = {'type': 'http'}
        self.message = None
        self.transport = None
        self.headers = None
        self.upgrade = None
        self.read_paused = False
        self.write_paused = False
        self.buffer_size = 0
        self.high_water_limit = HIGH_WATER_LIMIT
        self.low_water_limit = LOW_WATER_LIMIT
        self.max_pipelined_requests = MAX_PIPELINED_REQUESTS
        self.pipeline_queue = collections.deque()

    def connection_made(self, transport):
        self.transport = transport
        self.base_message.update({
            'server': transport.get_extra_info('sockname'),
            'client': transport.get_extra_info('peername'),
            'scheme': 'https' if transport.get_extra_info('sslcontext') else 'http',
        })

    def connection_lost(self, exc):
        self.transport = None

    def data_received(self, data):
        try:
            self.request_parser.feed_data(data)
        except httptools.HttpParserUpgrade:
            websocket_upgrade(self)

    def on_url(self, url):
        parsed_url = httptools.parse_url(url)
        self.message.update({
            'http_version': self.request_parser.get_http_version(),
            'method': self.request_parser.get_method().decode('ascii'),
            'path': parsed_url.path.decode('ascii'),
            'query_string': parsed_url.query if parsed_url.query else b'',
            'headers': self.headers
        })

    def on_message_begin(self):
        self.message = self.base_message.copy()
        self.headers = []

    def on_header(self, name: bytes, value: bytes):
        name = name.lower()
        if name == b'upgrade':
            self.upgrade = value
        elif name == b'expect' and value.lower() == b'100-continue':
            self.transport.write(b'HTTP/1.1 100 Continue\r\n\r\n')
        self.headers.append([name, value])

    def on_message_complete(self):
        """
        Prepare the ASGI application instance for the request
        """
        if self.upgrade is not None:
            return
        if self.request_handler is None:
            self.request_handler = AsgiHttpRequestHandler(
                self,
                self.transport,
                self.application_queue
            )
            create_application_instance(
                self.application,
                self.message,
                self.application_queue,
                application_handler=self.request_handler
            )
        # else:
        #     self.pipeline_queue.append(self.message)
        #     self.check_pause_reading()

    # def pause_writing(self):
    #     self.write_paused = True

    # def resume_writing(self):
    #     self.write_paused = False

    # def check_pause_reading(self):
    #     if self.transport is None or self.read_paused:
    #         return
    #     if (self.buffer_size > self.high_water_limit or
    #         len(self.pipeline_queue) >= self.max_pipelined_requests):
    #         self.transport.pause_reading()
    #         self.read_paused = True

    # def check_resume_reading(self):
    #     if self.transport is None or not self.read_paused:
    #         return
    #     if (self.buffer_size < self.low_water_limit and
    #         len(self.pipeline_queue) < self.max_pipelined_requests):
    #         self.transport.resume_reading()
    #         self.read_paused = False
