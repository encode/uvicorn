import asyncio
import email
import time
from h2.config import H2Configuration
from h2.connection import H2Connection
from h2.events import (
    ConnectionTerminated, RequestReceived, StreamEnded
)
from h2.exceptions import ProtocolError
from uvicorn.protocols.http import RequestResponseState


def set_time_and_date():
    global CURRENT_TIME
    global DATE_HEADER

    CURRENT_TIME = time.time()
    DATE_HEADER = ('date', email.utils.formatdate(CURRENT_TIME, usegmt=True))

CURRENT_TIME = 0.0
DATE_HEADER = ''

set_time_and_date()


class RequestResponseCycle:
    def __init__(self, transport, scope, stream, h2_connection, protocol):
        self.state = RequestResponseState.STARTED
        self.transport = transport
        self.scope = scope
        self.stream = stream
        self.h2_connection = h2_connection
        self.protocol = protocol
        self.content_length = None
        self.receive_queue = asyncio.Queue()

    def put_message(self, message):
        if self.state == RequestResponseState.CLOSED:
            return
        self.receive_queue.put_nowait(message)

    async def receive(self):
        message = await self.receive_queue.get()
        return message

    async def send(self, message):
        message_type = message['type']
        if message_type == 'http.response.start':
            if self.state != RequestResponseState.STARTED:
                raise Exception("Unexpected 'http.response.start' message.")

            status = message['status']
            headers = message.get('headers', [])

            content = [
                (':status', str(status)),
                ('server', 'uvicorn'),
                DATE_HEADER,
            ]
            for header_name, header_value in headers:
                header = header_name.lower()
                if header == b'content-length':
                    self.content_length = int(header_value.decode())
                content.append((header_name, header_value))

            await self.protocol.send_headers(self.stream.stream_id, content)

            self.state = RequestResponseState.SENDING_BODY

        elif message_type == 'http.response.body':
            body = message.get('body', b'')
            more_body = message.get('more_body', False)

            if self.state == RequestResponseState.SENDING_BODY:
                # Receive the body from the application to be handled by the stream
                await self.stream.send_data(body)
            else:
                raise Exception("Unexpected 'http.response.body' message.")

            if not more_body:
                self.state = RequestResponseState.CLOSED

        else:
            raise Exception('Unexpected message type "%s"' % message_type)

        if self.state == RequestResponseState.CLOSED:
            self.h2_connection.end_stream(self.stream.stream_id)
            self.transport.write(self.h2_connection.data_to_send())


class Http2Stream:
    def __init__(self, transport, h2_connection, stream_id, protocol):
        self.transport = transport
        self.h2_connection = h2_connection
        self.stream_id = stream_id
        self.protocol = protocol
        self.loop = asyncio.get_event_loop()

    @property
    def window_size(self):
        return self.h2_connection.local_flow_control_window(self.stream_id)

    @property
    def max_frame_size(self):
        return self.h2_connection.max_outbound_frame_size

    def get_chunk_size(self, data):
        return min(min(self.window_size, len(data)), self.max_frame_size)

    # TODO: Handle priority / related events / additional http2 features
    async def send_data(self, data):
        # Chunk the incoming request body if it exceeds the maximum frame size
        if len(data) > self.max_frame_size:
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

        # There is no need to buffer the data further, send the response immediately
        if not len(data_to_buffer) > self.max_frame_size:
            self.write(data_to_buffer)
            return None

        # Continue the loop until the entire request body has been sent
        return data_to_buffer


class Http2Protocol(asyncio.Protocol):
    def __init__(self, consumer, loop=None, state=None):
        self.consumer = consumer
        self.loop = loop or asyncio.get_event_loop()
        self.state = state or {'total_requests': 0}

        config = H2Configuration(client_side=False, header_encoding='utf-8')
        self.h2_connection = H2Connection(config=config)

        self.transport = None
        self.server = None
        self.client = None

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
        stream = Http2Stream(self.transport, self.h2_connection, stream_id, self)
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

        request = RequestResponseCycle(
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
