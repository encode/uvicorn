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

            # Connection headers need to be sent before processing the stream body
            await self.protocol.send_headers(self.stream_id, response_headers)

        elif message_type == 'http.response.body':
            body = message.get('body', b'')
            more_body = message.get('more_body', False)
            self.protocol.stream_data.put_nowait(
                (self.stream_id, body, more_body)
            )


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
        self.stream_requests = {}
        self.stream_data = asyncio.Queue()
        self.stream_task = None

    def connection_made(self, transport):
        self.transport = transport
        self.server = transport.get_extra_info('sockname')
        self.client = transport.get_extra_info('peername')
        self.conn.initiate_connection()
        self.transport.write(self.conn.data_to_send())

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
                elif isinstance(event, StreamEnded):
                    self.stream_ended(event)

        self.transport.write(self.conn.data_to_send())

    def request_received(self, event):
        headers = dict(event.headers)
        stream_id = event.stream_id

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

        request = RequestStream(self.scope, stream_id, self)
        self.stream_task = self.loop.create_task(self.stream_response())
        self.stream_requests[stream_id] = request
        asgi_instance = self.consumer(request.scope)
        self.loop.create_task(asgi_instance(request.receive, request.send))

    def stream_ended(self, event):
        # Cleanup the current stream...
        self.stream_requests[event.stream_id] = None
        self.state['total_requests'] += 1

    # TODO: Handle priority / related events?
    async def stream_response(self):

        while True:

            # Retrieve incoming stream data from the application and apply flow control
            stream_id, body, more_body = await self.stream_data.get()
            _body_buffer = self.send_response(
                stream_id,
                body,
                more_body
            )

            if _body_buffer is not None:

                # Ensure buffered data is sent before sending any new data for a stream
                while True:
                    _body_buffer = self.send_response(
                        stream_id,
                        _body_buffer,
                        more_body
                    )
                    if _body_buffer is None:
                        break

            # The application is no longer sending, we can end the stream
            if not more_body:
                break

        self.conn.end_stream(stream_id)
        self.transport.write(self.conn.data_to_send())

    async def send_headers(self, stream_id, response_headers):
        self.conn.send_headers(stream_id, response_headers)

    def send_response(self, stream_id, data, more_body):

        # Maximum amount of data that can be sent on stream
        window_size = self.conn.local_flow_control_window(stream_id)

        # Chunk the data using the window size and maximium outbound frame size
        chunk_size = min(min(window_size, len(data)), self.conn.max_outbound_frame_size)

        data_to_send = data[:chunk_size]
        self.conn.send_data(stream_id, data_to_send)
        self.transport.write(self.conn.data_to_send())

        # Return any remaining buffer data and loop until empty
        data_to_buffer = data[chunk_size:]
        if data_to_buffer == b'':
            return None
        return data_to_buffer
