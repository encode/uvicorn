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
        # TODO: Handle invalid handshake
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
        path = protocol.scope['path']
        message = {
            'type': 'websocket.receive',
            'path': path,
            'order': order
        }
        message['text'] = data if isinstance(data, str) else None
        message['bytes'] = data if isinstance(data, bytes) else None
        request.put_message(message)
        order += 1
    message = {
        'type': 'websocket.disconnect',
        'path': path,
        'code': close_code
    }
    request.put_message(message)


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
        close_code = message.get('code')
        if self.protocol.state == websockets.protocol.State.CLOSED:
            self.protocol.on_close()
        else:
            if message_type == 'websocket.accept':
                if not self.protocol.accepted:
                    self.protocol.accept()
                    self.protocol.listen()
            elif message_type == 'websocket.send':
                if text_data:
                    await self.protocol.send(text_data)
                elif bytes_data:
                    await self.protocol.send(bytes_data)
            elif message_type == 'websocket.close' or message_type == 'websocket.disconnect':
                if not self.protocol.accepted:
                    self.protocol.reject()
                else:
                    code = 1000 if not close_code else close_code
                    await self.protocol.close(code=code)



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
        request.put_message({'type': 'websocket.connect'})
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
        self.transport.write(rv)
        self.transport.close()

    def on_close(self):
        self.transport = None
        self.active_request = None
