import asyncio
import websockets


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
        http.transport.write(rv)
        http.transport.close()
        return

    protocol = WebSocketProtocol(http, response_headers)
    protocol.connection_open()
    protocol.connection_made(http.transport, http.scope)
    http.transport.set_protocol(protocol)


async def websocket_session(protocol):
    close_code = None
    order = 1
    path = protocol.scope['path']
    loop = protocol.loop
    request = protocol.active_request

    while True:
        try:
            data = await protocol.recv()
        except websockets.exceptions.ConnectionClosed as exc:
            close_code = exc.code
            break

        message = {
            'type': 'websocket.receive',
            'path': path,
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


class WebSocketRequest:

    def __init__(self, protocol, scope):
        self.protocol = protocol
        self.scope = scope
        self.loop = protocol.loop
        self.receive_queue = asyncio.Queue()
        
    def put_message(self, message):
        self.receive_queue.put_nowait(message)

    async def receive(self):
        return await self.receive_queue.get()

    async def send(self, message):
        message_type = message['type']
        text_data = message.get('text')
        bytes_data = message.get('bytes')
        if self.protocol.state == websockets.protocol.State.OPEN:
            if not self.protocol.accepted:
                accept = (message_type == 'websocket.accept')
                close = (message_type == 'websocket.close')
                if accept or close:
                    self.protocol.accept()
                    if not close:
                        self.protocol.listen()
                else:
                    self.protocol.reject()

            if text_data:
                await self.protocol.send(text_data)
            elif bytes_data:
                await self.protocol.send(bytes_data)

            if message_type == 'websocket.close' or message_type == 'websocket.disconnect':
                code = message.get('code', 1000)
                await self.protocol.close(code=code)
        else:
            raise Exception('Unexpected message, WebSocket request is disconnected.')


class WebSocketProtocol(websockets.WebSocketCommonProtocol):

    def __init__(self, http, handshake_headers):
        super().__init__(max_size=10000000, max_queue=10000000)
        self.handshake_headers = handshake_headers
        self.accepted = False
        self.loop = http.loop
        self.consumer = http.consumer
        self.active_request = None

    def connection_made(self, transport, scope):
        super().connection_made(transport)
        self.transport = transport
        self.scope = scope
        self.scope.update({
            'type': 'websocket'
        })
        asgi_instance = self.consumer(self.scope)
        request = WebSocketRequest(
            self,
            self.scope
        )
        self.loop.create_task(asgi_instance(request.receive, request.send))
        request.put_message({
            'type': 'websocket.connect', 
            'order': 0
        })
        self.active_request = request

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
