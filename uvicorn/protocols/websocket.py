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
        http.loop.create_task(http.channels['reply'].send({
            'status': 400,
            'headers': [[b'content-type', b'text/plain']],
            'content': b'Invalid WebSocket handshake'
        }))
        return

    http.loop.create_task(http.channels['reply'].send({
        'status': 101,
        'headers': response_headers
    }))
    protocol = WebSocketProtocol(http)
    protocol.connection_made(http.transport, http.message)
    http.transport.set_protocol(protocol)


class ReplyChannel():
    def __init__(self, websocket):
        self._websocket = websocket
        self.name = 'reply:%d' % id(self)

    async def send(self, message):
        if message.get('text'):
            await self._websocket.send(message['text'])
        elif message.get('bytes'):
            await self._websocket.send(message['bytes'])


async def reader(protocol, path):
    close_code = None
    order = 1
    while True:
        try:
            data = await protocol.recv()
        except websockets.exceptions.ConnectionClosed as exc:
            close_code = exc.code
            break

        message = {
            'channel': 'websocket.receive',
            'path': path,
            'order': order,
            'text': None,
            'bytes': None
        }
        if isinstance(data, str):
            message['text'] = data
        elif isinstance(data, bytes):
            message['bytes'] = data
        protocol.loop.create_task(protocol.consumer(message, protocol.channels))
        order += 1

    message = {
        'channel': 'websocket.disconnect',
        'code': close_code,
        'path': path,
        'order': order
    }
    protocol.loop.create_task(protocol.consumer(message, protocol.channels))


class WebSocketProtocol(websockets.WebSocketCommonProtocol):
    def __init__(self, http):
        super().__init__(max_size=10000000, max_queue=10000000)
        self.loop = http.loop
        self.consumer = http.consumer
        self.channels = {
            'reply': ReplyChannel(self)
        }

    def connection_made(self, transport, message):
        super().connection_made(transport)
        message.update({
            'channel': 'websocket.connect',
            'order': 0
        })
        self.loop.create_task(self.consumer(message, self.channels))
        self.loop.create_task(reader(self, message['path']))
