import asyncio
import websockets
import enum


def websocket_upgrade(http):
    request_headers = dict(http.headers)
    response_headers = []

    def get_header(key):
        key = key.lower().encode('utf-8')
        return request_headers.get(key, b'').decode('utf-8')

    def set_header(key, val):
        response_headers.append((key.encode('utf-8'), val.encode('utf-8')))

    try:
        key = websockets.handshake.check_request(get_header)
        websockets.handshake.build_response(set_header, key)
    except websockets.InvalidHandshake:
        rv = b'HTTP/1.1 403 Forbidden\r\n\r\n'
        http.writer.write(rv)
        http.writer.close()
        return

    # Retrieve any subprotocols to be negotiated with the consumer later
    subprotocols = request_headers.get(b'sec-websocket-protocol', None)
    if subprotocols:
        subprotocols = subprotocols.split(b',')
    http.scope.update({
        'type': 'websocket',
        'subprotocols': subprotocols
    })
    asgi_instance = http.consumer(http.scope)
    request = WebSocketRequest(
        http,
        response_headers
    )
    http.loop.create_task(asgi_instance(request.receive, request.send))
    request.put_message({
        'type': 'websocket.connect', 
        'order': 0
    })


async def websocket_session(protocol):
    close_code = None
    order = 1
    request = protocol.active_request
    path = request.scope['path']

    while True:
        try:
            data = await protocol.recv()
        except websockets.exceptions.ConnectionClosed as exc:
            close_code = exc.code
            break

        message = {
            'type': 'websocket.receive',
            'path': path,
            'text': None,
            'bytes': None,
            'order': order
        }
        if isinstance(data, str):
            message['text'] = data
        elif isinstance(data, bytes):
            message['bytes'] = data
        request.put_message(message)
        order += 1

    message = {
        'type': 'websocket.disconnect',
        'code': close_code,
        'path': path,
        'order': order
    }
    request.put_message(message)
    protocol.active_request = None


class WebSocketRequestState(enum.Enum):
    CONNECTING = 0
    CONNECTED = 1
    CLOSED = 2


class WebSocketRequest:

    def __init__(self, http, response_headers):
        self.state = WebSocketRequestState.CONNECTING
        self.http = http
        self.scope = http.scope
        self.response_headers = response_headers
        self.loop = asyncio.get_event_loop()
        self.receive_queue = asyncio.Queue()
        self.protocol = None
        
    def put_message(self, message):
        self.receive_queue.put_nowait(message)

    async def receive(self):
        return await self.receive_queue.get()

    async def send(self, message):
        message_type = message['type']
        text_data = message.get('text')
        bytes_data = message.get('bytes')

        if self.state == WebSocketRequestState.CLOSED:
            raise Exception('Unexpected message, WebSocketRequest is CLOSED.')

        if self.state == WebSocketRequestState.CONNECTING:
            # Complete the handshake after negotiating a subprotocol with the consumer
            subprotocol = message.get('subprotocol', None)
            if subprotocol:
                self.response_headers.append((b'Sec-WebSocket-Protocol', subprotocol.encode('utf-8')))
            protocol = WebSocketProtocol(self.http, self.response_headers)
            protocol.connection_open()
            protocol.connection_made(self.http.transport, subprotocol)
            self.http.transport.set_protocol(protocol)
            self.protocol = protocol
            self.protocol.active_request = self

            if not self.protocol.accepted:
                accept = (message_type == 'websocket.accept')
                close = (message_type == 'websocket.close')

                if accept or close:
                    self.protocol.accept()
                    self.state = WebSocketRequestState.CONNECTED
                    if accept:
                        self.protocol.listen()
                else:
                    self.protocol.reject()
                    self.state = WebSocketRequestState.CLOSED

        if self.state == WebSocketRequestState.CONNECTED:
            if text_data:
                await self.protocol.send(text_data)
            elif bytes_data:
                await self.protocol.send(bytes_data)

            if message_type == 'websocket.close':
                code = message.get('code', 1000)
                await self.protocol.close(code=code)
                self.state = WebSocketRequestState.CLOSED
        else:
            raise Exception('Unexpected message, WebSocketRequest is %s' % self.state)


class WebSocketProtocol(websockets.WebSocketCommonProtocol):

    def __init__(self, http, handshake_headers):
        super().__init__(max_size=10000000, max_queue=10000000)
        self.handshake_headers = handshake_headers
        self.accepted = False
        self.loop = http.loop
        self.consumer = http.consumer
        self.active_request = None

    def connection_made(self, transport, subprotocol):
        super().connection_made(transport)
        self.subprotocol = subprotocol
        self.transport = transport

    def accept(self):
        self.accepted = True
        rv = b'HTTP/1.1 101 Switching Protocols\r\n'
        for k, v in self.handshake_headers:
            rv += k + b': ' + v + b'\r\n'
        rv += b'\r\n'
        self.transport.write(rv)

    def listen(self):
        self.loop.create_task(websocket_session(self))

    def reject(self):
        rv = b'HTTP/1.1 403 Forbidden\r\n\r\n'
        self.active_request = None
        self.transport.write(rv)
        self.transport.close()
