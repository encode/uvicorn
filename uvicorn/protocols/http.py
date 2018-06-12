import asyncio
import enum
import collections
import email
import http
import httptools
import time
from uvicorn.protocols.websocket import websocket_upgrade


def set_time_and_date():
    global CURRENT_TIME
    global DATE_HEADER

    CURRENT_TIME = time.time()
    DATE_HEADER = b''.join([
        b'date: ',
        email.utils.formatdate(CURRENT_TIME, usegmt=True).encode(),
        b'\r\n'
    ])


def get_status_line(status_code):
    try:
        phrase = http.HTTPStatus(status_code).phrase.encode()
    except ValueError:
        phrase = b''
    return b''.join([
        b'HTTP/1.1 ', str(status_code).encode(), b' ', phrase, b'\r\n'
    ])


CURRENT_TIME = 0.0
DATE_HEADER = b''
SERVER_HEADER = b'server: uvicorn\r\n'
STATUS_LINE = {
    status_code: get_status_line(status_code) for status_code in range(100, 600)
}

LOW_WATER_LIMIT = 16384
HIGH_WATER_LIMIT = 65536
MAX_PIPELINED_REQUESTS = 20

set_time_and_date()


class RequestResponseState(enum.Enum):
    STARTED = 0
    FINALIZING_HEADERS = 1
    SENDING_BODY = 2
    CLOSED = 3


class RequestResponseCycle:
    def __init__(self, transport, scope, protocol, keep_alive=True):
        self.state = RequestResponseState.STARTED
        self.transport = transport
        self.scope = scope
        self.protocol = protocol
        self.keep_alive = keep_alive
        self.chunked_encoding = False
        self.content_length = None
        self.receive_queue = asyncio.Queue()

    def put_message(self, message):
        if self.state == RequestResponseState.CLOSED:
            return
        self.protocol.buffer_size += len(message.get('body', b''))
        self.receive_queue.put_nowait(message)

    async def receive(self):
        message = await self.receive_queue.get()
        self.protocol.buffer_size -= len(message.get('body', b''))
        return message

    async def send(self, message):
        message_type = message['type']

        if message_type == 'http.response.start':
            if self.state != RequestResponseState.STARTED:
                raise Exception("Unexpected 'http.response.start' message.")

            status = message['status']
            headers = message.get('headers', [])

            content = [
                STATUS_LINE[status],
                SERVER_HEADER,
                DATE_HEADER,
            ]
            for header_name, header_value in headers:
                header = header_name.lower()
                if header == b'content-length':
                    self.content_length = int(header_value.decode())
                elif header == b'connection':
                    if header_value.lower() == b'close':
                        self.keep_alive = False
                content.extend([header_name, b': ', header_value, b'\r\n'])

            if self.content_length is None:
                self.state = RequestResponseState.FINALIZING_HEADERS
            else:
                content.append(b'\r\n')
                self.state = RequestResponseState.SENDING_BODY

            self.transport.write(b''.join(content))

        elif message_type == 'http.response.body':
            body = message.get('body', b'')
            more_body = message.get('more_body', False)

            if self.state == RequestResponseState.FINALIZING_HEADERS:
                if more_body:
                    content = [
                        b'transfer-encoding: chunked\r\n\r\n',
                        b'%x\r\n' % len(body),
                        body,
                        b'\r\n'
                    ]
                    self.chunked_encoding = True
                    self.transport.write(b''.join(content))
                else:
                    content = [
                        b'content-length: ',
                        str(len(body)).encode(),
                        b'\r\n\r\n',
                        body
                    ]
                    self.transport.write(b''.join(content))

            elif self.state == RequestResponseState.SENDING_BODY:
                if self.chunked_encoding:
                    content = [
                        b'%x\r\n' % len(body),
                        body,
                        b'\r\n'
                    ]
                    if not more_body:
                        content.append(b'0\r\n\r\n')
                    self.transport.write(b''.join(content))
                else:
                    self.transport.write(body)

            else:
                raise Exception("Unexpected 'http.response.body' message.")

            if more_body:
                self.state = RequestResponseState.SENDING_BODY
            else:
                self.state = RequestResponseState.CLOSED

        else:
            raise Exception('Unexpected message type "%s"' % message_type)

        await self.protocol.drain()

        if self.state == RequestResponseState.CLOSED:
            self.protocol.on_response_complete(keep_alive=self.keep_alive)


class HttpProtocol(asyncio.Protocol):
    def __init__(self, consumer, loop=None, state=None):
        self.consumer = consumer
        self.loop = loop or asyncio.get_event_loop()
        self.request_parser = httptools.HttpRequestParser(self)
        self.state = state or {'total_requests': 0}

        # Per-connection state...
        self.transport = None
        self.server = None
        self.client = None
        self.scheme = None

        # Per-request state....
        self.scope = None
        self.headers = []
        self.body = b''

        # We run client request/response cycles strictly in turn, but allow
        # the server to continue pipelining and parsing incoming requests...
        self.pipelined_requests = collections.deque()
        self.active_request = None
        self.parsing_request = None

        # Flow control
        self.buffer_size = 0
        self.read_paused = False
        self.write_paused = False
        self.high_water_limit = HIGH_WATER_LIMIT
        self.low_water_limit = LOW_WATER_LIMIT
        self.max_pipelined_requests = MAX_PIPELINED_REQUESTS
        self.drain_waiter = asyncio.Event()
        self.drain_waiter.set()

    # The asyncio.Protocol hooks...
    def connection_made(self, transport):
        self.transport = transport
        self.server = transport.get_extra_info('sockname')
        self.client = transport.get_extra_info('peername')
        self.scheme = 'https' if transport.get_extra_info('sslcontext') else 'http'

    def connection_lost(self, exc):
        if self.active_request is not None:
            self.active_request.put_message({'type': 'http.disconnect'})
        self.transport = None

    def eof_received(self):
        pass

    def data_received(self, data):
        try:
            self.request_parser.feed_data(data)
        except httptools.HttpParserUpgrade:
            websocket_upgrade(self)

    # Flow control

    def pause_writing(self):
        self.write_paused = True
        self.drain_waiter.clear()

    def resume_writing(self):
        self.write_paused = False
        self.drain_waiter.set()

    async def drain(self):
        if not self.write_paused:
            return
        await self.drain_waiter.wait()

    def check_pause_reading(self):
        if self.read_paused:
            return

        if (self.buffer_size > self.high_water_limit or
                len(self.pipelined_requests) > self.max_pipelined_requests):
            self.transport.pause_reading()
            self.read_paused = True

    def check_resume_reading(self):
        if not self.read_paused:
            return
        if (self.buffer_size <= self.low_water_limit or
                len(self.pipelined_requests) <= self.max_pipelined_requests):
            self.transport.resume_reading()
            self.read_paused = False

    # Event hooks called back into by HttpRequestParser...
    def on_message_begin(self):
        self.scope = None
        self.headers = []
        self.body = b''
        self.parsing_request = None

    def on_url(self, url):
        parsed = httptools.parse_url(url)
        method = self.request_parser.get_method()
        http_version = self.request_parser.get_http_version()
        self.scope = {
            'type': 'http',
            'http_version': http_version,
            'server': self.server,
            'client': self.client,
            'scheme': self.scheme,
            'method': method.decode('ascii'),
            'path': parsed.path.decode('ascii'),
            'query_string': parsed.query if parsed.query else b'',
            'headers': self.headers
        }

    def on_header(self, name: bytes, value: bytes):
        self.headers.append([name.lower(), value])

    def on_headers_complete(self):
        if self.request_parser.should_upgrade():
            return

        request = RequestResponseCycle(
            self.transport,
            self.scope,
            protocol=self,
            keep_alive=self.request_parser.should_keep_alive(),
        )
        if self.active_request is None:
            self.active_request = request
            asgi_instance = self.consumer(request.scope)
            self.loop.create_task(asgi_instance(request.receive, request.send))
        else:
            self.pipelined_requests.append(request)
            self.check_pause_reading()
        self.parsing_request = request

    def on_body(self, body: bytes):
        if self.body:
            self.parsing_request.put_message({
                'type': 'http.request',
                'body': self.body,
                'more_body': True
            })
            self.check_pause_reading()
        self.body = body

    def on_message_complete(self):
        if self.request_parser.should_upgrade():
            return
        self.parsing_request.put_message({
            'type': 'http.request',
            'body': self.body
        })
        self.check_pause_reading()

    # Called back into by RequestHandler
    def on_response_complete(self, keep_alive=True):
        self.state['total_requests'] += 1

        if not keep_alive:
            self.transport.close()
            return

        if not self.pipelined_requests:
            self.active_request = None
            return

        request = self.pipelined_requests.popleft()
        self.active_request = request
        asgi_instance = self.consumer(request.scope)
        self.loop.create_task(asgi_instance(request.receive, request.send))
        self.check_resume_reading()
