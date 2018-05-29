import asyncio
import enum
import collections
import email
import http
import httptools
import time

from h2.config import H2Configuration
from h2.connection import H2Connection
from h2.events import (
    ConnectionTerminated, RequestReceived, StreamEnded
)
from h2.exceptions import ProtocolError

from uvicorn.protocols.websocket import websocket_upgrade


def set_time_and_date():
    global CURRENT_TIME
    global CURRENT_DATE

    CURRENT_TIME = time.time()
    CURRENT_DATE = email.utils.formatdate(CURRENT_TIME, usegmt=True)


def get_status_line(status_code):
    try:
        phrase = http.HTTPStatus(status_code).phrase.encode()
    except ValueError:
        phrase = b''
    return b''.join([
        b'HTTP/1.1 ', str(status_code).encode(), b' ', phrase, b'\r\n'
    ])


CURRENT_TIME = 0.0
CURRENT_DATE = ''
SERVER_NAME = 'uvicorn'
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
    def __init__(self, transport, scope, protocol, **kwargs):
        self.state = RequestResponseState.STARTED
        self.transport = transport
        self.scope = scope
        self.protocol = protocol
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

            await self.on_response_start(status, headers)

        elif message_type == 'http.response.body':
            body = message.get('body', b'')
            more_body = message.get('more_body', False)

            await self.on_response_body(body, more_body)

        else:
            raise Exception('Unexpected message type "%s"' % message_type)

        if self.protocol.is_writing:
            await self.protocol.drain()

        if self.state == RequestResponseState.CLOSED:
            self.on_response_complete()


class HttpRequestResponseCycle(RequestResponseCycle):
    def __init__(self, transport, scope, protocol, keep_alive=True):
        super().__init__(transport, scope, protocol)
        self.keep_alive = keep_alive
        self.chunked_encoding = False

    async def on_response_start(self, status, headers):
        content = [
            STATUS_LINE[status],
            b''.join([
                b'server: ',
                SERVER_NAME.encode(),
                b'\r\n'
            ]),
            b''.join([
                b'date: ',
                CURRENT_DATE.encode(),
                b'\r\n'
            ])
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

    async def on_response_body(self, body, more_body):

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

    def on_response_complete(self):
        self.protocol.on_response_complete(keep_alive=self.keep_alive)


class H2RequestResponseCycle(RequestResponseCycle):
    def __init__(self, transport, scope, stream, h2_connection, protocol):
        super().__init__(transport, scope, protocol)
        self.stream = stream
        self.h2_connection = h2_connection

    async def on_response_start(self, status, headers):
        content = [
            (':status', str(status)),
            ('server', SERVER_NAME),
            ('date', CURRENT_DATE),
        ]
        for header_name, header_value in headers:
            header = header_name.lower()
            if header == b'content-length':
                self.content_length = int(header_value.decode())
            content.append((header_name, header_value))

        await self.protocol.send_headers(self.stream.stream_id, content)

        self.state = RequestResponseState.SENDING_BODY

    async def on_response_body(self, body, more_body):

        if self.state == RequestResponseState.SENDING_BODY:
            # Receive the body from the application to be handled by the stream
            await self.stream.send_data(body)
        else:
            raise Exception("Unexpected 'http.response.body' message.")

        if not more_body:
            self.state = RequestResponseState.CLOSED

    def on_response_complete(self):
        self.h2_connection.end_stream(self.stream.stream_id)
        self.transport.write(self.h2_connection.data_to_send())


class H2Stream:
    def __init__(self, transport, h2_connection, stream_id, protocol):
        self.transport = transport
        self.h2_connection = h2_connection
        self.stream_id = stream_id
        self.protocol = protocol

    def get_chunk_size(self, data):
        window_size = self.h2_connection.local_flow_control_window(self.stream_id)
        return min(min(window_size, len(data)), self.h2_connection.max_outbound_frame_size)

    # TODO: Handle priority / related events / additional http2 features
    async def send_data(self, data):
        # Chunk the incoming request body if it exceeds the maximum frame size
        if len(data) > self.h2_connection.max_outbound_frame_size:
            # Block and send until there is no longer buffer data
            # At this point we only know that at least one additional send is required
            data = self.chunked_write(data)
            while True:
                data = self.chunked_write(data)
                if data is None:
                    break
        else:
            self.write(data)

    def write(self, data):
        self.h2_connection.send_data(self.stream_id, data)
        self.transport.write(self.h2_connection.data_to_send())

    def chunked_write(self, data):
        if not data:
            return None

        # Chunk the buffer data using the window size and maximum frame size
        chunk_size = self.get_chunk_size(data)
        data_to_send = data[:chunk_size]
        self.write(data_to_send)

        data_to_buffer = data[chunk_size:]

        if not len(data_to_buffer) > self.h2_connection.max_outbound_frame_size:
            # No need to buffer the data further, send the response immediately
            self.write(data_to_buffer)
            return None

        # Continue the loop until the entire request body has been sent
        return data_to_buffer


class HttpProtocolFactory:
    def __init__(self, consumer, loop=None, state=None):
        self.consumer = consumer
        self.loop = loop or asyncio.get_event_loop()
        self.state = state or {'total_requests': 0}

    def connection_made(self, transport):
        self.transport = transport
        self.server = transport.get_extra_info('sockname')
        self.client = transport.get_extra_info('peername')
        ssl_object = transport.get_extra_info('ssl_object')
        if ssl_object:
            protocol_type = ssl_object.selected_alpn_protocol()
            if protocol_type == 'h2':
                protocol_class = H2Protocol
        else:
            protocol_class = HttpProtocol

        protocol = protocol_class(self.consumer, loop=self.loop, state=self.state)
        protocol.connection_made(transport)
        self.transport.set_protocol(protocol)


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
        self.is_writing = asyncio.Event(loop=loop)
        self.is_writing.set()

    # The asyncio.Protocol hooks...
    def connection_made(self, transport):
        self.transport = transport
        self.server = transport.get_extra_info('sockname')
        self.client = transport.get_extra_info('peername')
        self.scheme = 'https' if transport.get_extra_info('sslcontext') else 'http'

    def connection_lost(self, exc):
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
        self.is_writing.clear()

    def resume_writing(self):
        self.is_writing.set()

    async def drain(self):
        await self.is_writing.wait()

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

        request = HttpRequestResponseCycle(
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


class H2Protocol(asyncio.Protocol):
    def __init__(self, consumer, loop=None, state=None):
        self.consumer = consumer
        self.loop = loop or asyncio.get_event_loop()
        self.state = state or {'total_requests': 0}

        config = H2Configuration(client_side=False, header_encoding='utf-8')
        self.h2_connection = H2Connection(config=config)

        self.transport = None
        self.server = None
        self.client = None

        self.is_writing = asyncio.Event(loop=loop)
        self.is_writing.set()

        self.scope = None
        self.stream_data = {}

    def connection_made(self, transport):
        self.transport = transport
        self.server = transport.get_extra_info('sockname')
        self.client = transport.get_extra_info('peername')
        self.h2_connection.initiate_connection()
        self.transport.write(self.h2_connection.data_to_send())

    def connection_lost(self, exc):
        self.transport = None

    # Flow control
    def pause_writing(self):
        self.is_writing.clear()

    def resume_writing(self):
        self.is_writing.set()

    async def drain(self):
        await self.is_writing.wait()

    def data_received(self, data):
        try:
            events = self.h2_connection.receive_data(data)
        except ProtocolError as e:
            self.transport.write(self.h2_connection.data_to_send())
            self.transport.close()
        else:
            self.transport.write(self.h2_connection.data_to_send())
            for event in events:
                if isinstance(event, RequestReceived):
                    self.request_received(event.headers, event.stream_id)
                elif isinstance(event, StreamEnded):
                    self.stream_complete(event.stream_id)
                elif isinstance(event, ConnectionTerminated):
                    self.transport.close()
                self.transport.write(self.h2_connection.data_to_send())

    def request_received(self, headers, stream_id):
        # Create the stream object that will handle the response
        stream = H2Stream(self.transport, self.h2_connection, stream_id, self)
        self.stream_data[stream_id] = stream

        headers = dict(headers)
        scope_headers = []
        for name, value in headers.items():
            # Ignore the HTTP2 pseudo-headers
            if ':' not in name:
                scope_headers.append([name.lower().encode(), value.encode()])

        path = headers[':path']
        try:
            path, query_string = path.split('?')
        except ValueError:
            query_string = b''

        self.scope = {
            'type': 'http',
            'http_version': '2',
            'server': self.server,
            'client': self.client,
            'scheme': headers[':scheme'],
            'method': headers[':method'],
            'path': path,
            'query_string': query_string,
            'headers': scope_headers,
        }

        request = H2RequestResponseCycle(
            self.transport,
            self.scope,
            stream,
            self.h2_connection,
            self
        )
        asgi_instance = self.consumer(request.scope)
        self.loop.create_task(asgi_instance(request.receive, request.send))

    def stream_complete(self, stream_id):
        self.state['total_requests'] += 1

    async def send_headers(self, stream_id, response_headers):
        self.h2_connection.send_headers(stream_id, response_headers)
