import asyncio
import threading

from h2.config import H2Configuration
from h2.connection import H2Connection
from h2.events import (
    RequestReceived, WindowUpdated
)  # StreamEnded


END_DATA_SENTINEL = object()


class RequestStream:
    def __init__(self, scope, stream_id, protocol):
        self.scope = scope
        self.stream_id = stream_id
        self.protocol = protocol
        self.receive_queue = asyncio.Queue()
        self.response_status = b''
        self.response_headers = []
        self.headers_emitted = False

    def put_message(self, message):
        self.receive_queue.put_nowait(message)

    async def receive(self):
        message = await self.receive_queue.get()
        return message

    async def send(self, message):
        message_type = message['type']

        if message_type == 'http.response.start':
            status = message['status']
            headers = message.get('headers', [])

            response_headers = [
                ('status', str(status)),
                ('server', 'uvicorn'),
            ]
            for header_name, header_value in headers:
                header = header_name.lower()
                if header == b'content-length':
                    self.content_length = int(header_value.decode())
                response_headers.append((header_name.decode(), header_value.decode()))

            self.response_status = status
            self.response_headers = response_headers

        elif message_type == 'http.response.body':
            body = message.get('body', b'')
            more_body = message.get('more_body', False)
            body_size = len(body)
            self.protocol.open_flow_control_window(self.stream_id, body_size)
            self.write(body)
            if not more_body:
                self.write(END_DATA_SENTINEL)

    def write(self, data):
        if not self.headers_emitted:
            self.emit_headers()
        self.protocol.data_for_stream(self.stream_id, data)

    def emit_headers(self):
        self.headers_emitted = True
        status = str(self.response_status)
        headers = [(":status", status)]
        headers.extend(self.response_headers)
        self.protocol.send_response(self.stream_id, headers)


class H2Protocol(asyncio.Protocol):

    def __init__(self, consumer, loop=None, state=None):
        self.consumer = consumer
        self.loop = loop or asyncio.get_event_loop()
        self.state = state or {'total_requests': 0}

        config = H2Configuration(client_side=False, header_encoding='utf-8')
        self.conn = H2Connection(config=config)

        self.transport = None
        self.server = None
        self.client = None

        self.stream_data = {}

        self.active_request = None
        self.scope = {}

        self.streams = {}
        self.stream_data = asyncio.Queue()
        self.flow_controlled_data = {}
        self.reset_streams = set()
        self.send_loop_task = None

    def connection_made(self, transport):
        self.transport = transport
        self.server = transport.get_extra_info('sockname')
        self.client = transport.get_extra_info('peername')
        self.conn.initiate_connection()
        self.transport.write(self.conn.data_to_send())
        self.send_loop_task = self.loop.create_task(self.sending_loop())

    def connection_lost(self, exc):
        self.send_loop_task.cancel()

    def data_received(self, data):
        events = self.conn.receive_data(data)

        for event in events:
            if isinstance(event, RequestReceived):
                self.request_received(event)
            elif isinstance(event, WindowUpdated):
                self.window_opened(event)
            # elif isinstance(event, StreamEnded):
            #     self.end_stream(event)

        self.transport.write(self.conn.data_to_send())

    def request_received(self, event):
        headers = dict(event.headers)

        _headers = []
        for name, value in headers.items():
            _headers.append([name.lower().encode(), value.encode()])

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
            'headers': _headers,
        }

        request = RequestStream(self.scope, event.stream_id, self)
        self.streams[event.stream_id] = request
        asgi_instance = self.consumer(request.scope)
        self.loop.create_task(asgi_instance(request.receive, request.send))

    def window_opened(self, event):
        if event.stream_id:
            if event.stream_id in self.flow_controlled_data:
                self.stream_data.put_nowait(
                    self.flow_controlled_data.pop(event.stream_id)
                )
        else:
            for data in self.flow_controlled_data.values():
                self.stream_data.put_nowait(data)

            self.flow_controlled_data = {}

    # def end_stream(self, event):
    #     stream = self.streams[event.stream_id]
    #     stream.request_complete()

    def reset_stream(self, event):
        if event.stream_id in self.flow_controlled_data:
            del self.flow_controlled_data

        self.reset_streams.add(event.stream_id)
        # self.end_stream(event)

    def send_response(self, stream_id, headers):
        self.conn.send_headers(stream_id, headers, end_stream=False)
        self.transport.write(self.conn.data_to_send())

    def data_for_stream(self, stream_id, data):
        event = threading.Event()
        self.loop.call_soon_threadsafe(
            self.stream_data.put_nowait,
            (stream_id, data, event)
        )
        return event

    @asyncio.coroutine
    def sending_loop(self):
        while True:
            stream_id, data, event = yield from self.stream_data.get()

            if stream_id in self.reset_streams:
                event.set()

            if data is END_DATA_SENTINEL:
                self.conn.end_stream(stream_id)
                self.transport.write(self.conn.data_to_send())
                event.set()
                continue

            window_size = self.conn.local_flow_control_window(stream_id)
            chunk_size = min(window_size, len(data))
            data_to_send = data[:chunk_size]
            data_to_buffer = data[chunk_size:]

            if data_to_send:
                max_size = self.conn.max_outbound_frame_size
                chunks = (
                    data_to_send[x: x + max_size]
                    for x in range(0, len(data_to_send), max_size)
                )
                for chunk in chunks:
                    self.conn.send_data(stream_id, chunk)
                self.transport.write(self.conn.data_to_send())

            if data_to_buffer:
                self.flow_controlled_data[stream_id] = (
                    stream_id, data_to_buffer, event
                )
            else:
                event.set()

    def open_flow_control_window(self, stream_id, increment):

        def _inner_open(stream_id, increment):
            self.conn.increment_flow_control_window(increment, stream_id)
            self.conn.increment_flow_control_window(increment, None)
            self.transport.write(self.conn.data_to_send())

        self.loop.call_soon_threadsafe(
            _inner_open,
            stream_id,
            increment,
        )
