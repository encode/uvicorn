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

    protocol = WebSocketProtocol(http, response_headers)
    protocol.connection_made(http.transport, http.message)
    http.transport.set_protocol(protocol)


class ReplyChannel():
    def __init__(self, websocket):
        self._websocket = websocket
        self.name = 'reply:%d' % id(self)

    async def send(self, message):
        accept = message.get('accept')
        text_data = message.get('text')
        bytes_data = message.get('bytes')
        close = message.get('close')

        if not self._websocket.accepted:
            if (accept is True) or (accept is None and (text_data or bytes_data)):
                self._websocket.accept()
                if not close:
                    self._websocket.listen()
            elif accept is False:
                text_data = None
                bytes_data = None
                close = True

        if text_data:
            await self._websocket.send(text_data)
        elif bytes_data:
            await self._websocket.send(bytes_data)

        if close:
            if not self._websocket.accepted:
                self._websocket.reject()
            else:
                code = 1000 if (close is True) else close
                await self._websocket.close(code=code)


async def reader(protocol):
    path = protocol.message['path']

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
    def __init__(self, http, handshake_headers):
        super().__init__(max_size=10000000, max_queue=10000000)
        self.handshake_headers = handshake_headers
        self.accepted = False
        self.loop = http.loop
        self.consumer = http.consumer
        self.channels = {
            'reply': ReplyChannel(self)
        }

    def connection_made(self, transport, message):
        super().connection_made(transport)
        self.transport = transport
        self.message = message
        message.update({
            'channel': 'websocket.connect',
            'order': 0
        })
        self.loop.create_task(self.consumer(message, self.channels))

    def accept(self):
        self.accepted = True
        rv = b'HTTP/1.1 101 Switching Protocols\r\n'
        for k, v in self.handshake_headers:
           rv += k + b': ' + v + b'\r\n'
        rv += b'\r\n'
        self.transport.write(rv)

    def listen(self):
        self.loop.create_task(reader(self))

    def reject(self):
        rv = b'HTTP/1.1 403 Forbidden\r\n\r\n'
        self.transport.write(rv)
        self.transport.close()
