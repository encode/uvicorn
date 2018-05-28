import asyncio

from h2.config import H2Configuration
from h2.connection import H2Connection
from h2.events import RequestReceived, StreamEnded
from h2.exceptions import ProtocolError


class RequestStream:
    def __init__(self, scope, stream_id, protocol):
        self.scope = scope
        self.stream_id = stream_id
        self.protocol = protocol
        self.receive_queue = asyncio.Queue()
        self.headers_sent = False
        self.response_headers = []

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
                (':status', str(status)),
                ('server', 'uvicorn'),
            ]
            for header_name, header_value in headers:
                header = header_name.lower()
                if header == b'content-length':
                    self.content_length = int(header_value.decode())
                response_headers.append((header_name.decode(), header_value.decode()))

            await self.set_headers(response_headers)

        elif message_type == 'http.response.body':
            body = message.get('body', b'')
            more_body = message.get('more_body', False)
            if not self.headers_sent:
                self.protocol.conn.send_headers(self.stream_id, self.response_headers)
                self.headers_sent = True
            self.protocol.stream_data.put_nowait((self.stream_id, body, more_body))

    async def set_headers(self, response_headers):
        self.response_headers = response_headers


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
        self.scope = {}

        self.streams = {}
        self.stream_data = asyncio.Queue()
        self.stream_task = None

    def connection_made(self, transport):
        self.transport = transport
        self.server = transport.get_extra_info('sockname')
        self.client = transport.get_extra_info('peername')

        self.conn.initiate_connection()
        self.transport.write(self.conn.data_to_send())

        self.stream_task = self.loop.create_task(self.stream_response())

    def data_received(self, data):
        try:
            events = self.conn.receive_data(data)
        except ProtocolError as e:
            self.transport.write(self.conn.data_to_send())
            self.transport.close()
        else:
            for event in events:
                if isinstance(event, RequestReceived):
                    self.request_received(event)
                # elif isinstance(event, StreamEnded):
                #     self.stream_ended(event)
        self.transport.write(self.conn.data_to_send())

    def request_received(self, event):
        headers = dict(event.headers)
        stream_id = event.stream_id

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

        request = RequestStream(self.scope, stream_id, self)
        self.streams[stream_id] = request
        asgi_instance = self.consumer(request.scope)
        self.loop.create_task(asgi_instance(request.receive, request.send))

    # def stream_ended(self, event):
    #     print(event)

    async def stream_response(self):
        while True:

            stream_id, data, more_body = await self.stream_data.get()
            data = self.handle_send(stream_id, data, more_body)

            if data is not None:
                while True:
                    data = self.handle_send(stream_id, data, more_body)
                    if data is None:
                        break

            if not more_body:
                break

    def handle_send(self, stream_id, data, more_body):
        window_size = self.conn.local_flow_control_window(stream_id)
        max_size = self.conn.max_outbound_frame_size
        chunk_size = min(min(window_size, len(data)), max_size)
        data_to_send = data[:chunk_size]
        data_to_buffer = data[chunk_size:]

        self.conn.send_data(stream_id, data_to_send)
        self.transport.write(self.conn.data_to_send())
        if len(data) == 0:
            return None
        return data_to_buffer
