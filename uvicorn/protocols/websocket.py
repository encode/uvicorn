# In progress...
from websockets import handshake, InvalidHandshake


def websocket_upgrade(http):
    request_headers = dict(http.headers)
    response_headers = []

    def get_header(key):
        key = key.lower().encode('utf-8')
        return request_headers.get(key, b'').decode('utf-8')

    def set_header(key, val):
        response_headers.append((key.encode('utf-8'), val.encode('utf-8')))

    try:
        key = handshake.check_request(get_header)
        handshake.build_response(set_header, key)
    except InvalidHandshake:
        http.loop.create_task(http.channels['reply'].send({
            'status': 404,
            'headers': [[b'content-type', 'text/plain']],
            'content': b'Invalid WebSocket handshake'
        }))
    else:
        http.loop.create_task(http.channels['reply'].send({
            'status': 101,
            'headers': response_headers
        }))


# class WebSocketChannel():
#     def __init__(self, websocket):
#         self._websocket = websocket
#
#     async def send(message):
#         await self._websocket.put(message['text'])
#
#     async def receive(message):
#         return await self._websocket.recv()
#
#
# class WebSocketProtocol(WebSocketCommonProtocol):
#     def __init__(self, message, loop, consumer):
#         self.message = message
#         self.loop = loop
#
#     def on_message_complete(self):
#
#
#         protocol = WebSocketCommonProtocol(max_size=10000000, max_queue=10000000)
#         protocol.connection_made(transport)
#         self.transport.set_protocol(protocol)
#         channels = {
#             'websocket': WebSocketChannel(websocket)
#         }
#         self.loop.create_task(self.consumer(self.message, channels))
