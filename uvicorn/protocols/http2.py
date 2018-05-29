import asyncio
import enum
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

set_time_and_date()


class RequestStreamState(enum.Enum):
    STARTED = 0
    SENDING_BODY = 1
    CLOSED = 2


class RequestStream:
    def __init__(self, transport, scope, stream, protocol):
        self.state = RequestStreamState.STARTED
        self.transport = transport
        self.scope = scope
        self.protocol = protocol
        self.stream = stream
        self.content_length = None
        self.receive_queue = asyncio.Queue()

    def put_message(self, message):
        if self.state == RequestStreamState.CLOSED:
            return
        self.receive_queue.put_nowait(message)

    async def receive(self):
        message = await self.receive_queue.get()
        return message

    async def send(self, message):
        message_type = message['type']
        if message_type == 'http.response.start':
            if self.state != RequestStreamState.STARTED:
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
                content.extend([header_name, b': ', header_value, b'\r\n'])

                self.state = RequestStreamState.SENDING_BODY

            response_headers = [
                (':status', str(status)),
                ('server', 'uvicorn'),
            ]

            await self.protocol.send_headers(self.stream.stream_id, response_headers)

        elif message_type == 'http.response.body':
            body = message.get('body', b'')
            more_body = message.get('more_body', False)

            if self.state == RequestStreamState.SENDING_BODY:
                await self.stream.send_data(body)
            else:
                raise Exception("Unexpected 'http.response.body' message.")

            if not more_body:
                self.state = RequestStreamState.CLOSED

        else:
            raise Exception('Unexpected message type "%s"' % message_type)

        if self.state == RequestStreamState.CLOSED:
            self.protocol.conn.end_stream(self.stream.stream_id)
            self.transport.write(self.protocol.conn.data_to_send())


class H2Stream:
    def __init__(self, stream_id, conn, protocol):
        self.stream_id = stream_id
        self.conn = conn
        self.protocol = protocol
        self.loop = asyncio.get_event_loop()
        self.transport = protocol.transport
        self.is_complete = False

    @property
    def window_size(self):
        return self.conn.local_flow_control_window(self.stream_id)

    @property
    def max_frame_size(self):
        return self.conn.max_outbound_frame_size

    def get_chunk_size(self, data):
        return min(min(self.window_size, len(data)), self.max_frame_size)

    async def send_data(self, data):
        if len(data) > self.max_frame_size:
            data = self.chunked_write(data)
            while True:
                data = self.chunked_write(data)
                if data is None:
                    break
        else:
            self.write(data)

    def write(self, data):
        self.conn.send_data(self.stream_id, data)
        self.transport.write(self.conn.data_to_send())

    def chunked_write(self, data):
        if not data:
            return None

        chunk_size = self.get_chunk_size(data)
        data_to_send = data[:chunk_size]
        self.write(data_to_send)

        data_to_buffer = data[chunk_size:]

        if not len(data_to_buffer) > self.max_frame_size:
            self.write(data_to_buffer)
            return None

        return data_to_buffer


class H2Protocol(asyncio.Protocol):
    def __init__(self, consumer, loop=None, state=None):
        self.consumer = consumer
        self.loop = loop or asyncio.get_event_loop()
        self.request_parser = httptools.HttpRequestParser(self)
        self.state = state or {'total_requests': 0}

        config = H2Configuration(client_side=False, header_encoding='utf-8')
        self.conn = H2Connection(config=config)

        self.transport = None
        self.server = None
        self.client = None

        self.scope = None
        self.stream_data = {}

    def connection_made(self, transport):
        self.transport = transport
        self.server = transport.get_extra_info('sockname')
        self.client = transport.get_extra_info('peername')
        self.conn.initiate_connection()
        self.transport.write(self.conn.data_to_send())

    def connection_lost(self, exc):
        self.transport = None

    def data_received(self, data):
        try:
            events = self.conn.receive_data(data)
        except ProtocolError as e:
            self.transport.write(self.conn.data_to_send())
            self.transport.close()
        else:
            self.transport.write(self.conn.data_to_send())
            for event in events:
                if isinstance(event, RequestReceived):
                    self.request_received(event.headers, event.stream_id)
                elif isinstance(event, StreamEnded):
                    self.stream_complete(event.stream_id)
                elif isinstance(event, ConnectionTerminated):
                    self.transport.close()
                self.transport.write(self.conn.data_to_send())

    def request_received(self, headers, stream_id):
        stream = H2Stream(stream_id, self.conn, self)
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

        request = RequestStream(
            self.transport,
            self.scope,
            stream,
            protocol=self
        )
        asgi_instance = self.consumer(request.scope)
        self.loop.create_task(asgi_instance(request.receive, request.send))

    def stream_complete(self, stream_id):
        self.state['total_requests'] += 1

    async def send_headers(self, stream_id, response_headers):
        self.conn.send_headers(stream_id, response_headers)
