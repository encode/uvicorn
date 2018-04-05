import asyncio

import websockets

from uvicorn.protocols.request import AsgiWebsocketRequestHandler
from uvicorn.protocols.utils import create_application_instance


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
    protocol.connection_open()
    protocol.connection_made(http.transport, http.message)
    http.transport.set_protocol(protocol)


class WebSocketProtocol(websockets.WebSocketCommonProtocol):

    def __init__(self, http, handshake_headers):
        super().__init__(max_size=10000000, max_queue=10000000)
        self.handshake_headers = handshake_headers
        self.accepted = False
        self.application_queue = asyncio.Queue()
        self.loop = http.loop
        self.application = http.application

    def connection_made(self, transport, message):
        super().connection_made(transport)
        self.transport = transport
        self.message = message
        self.message.update({'type': 'websocket.connect'})
        application_handler = AsgiWebsocketRequestHandler(
            self,
            self.application_queue
        )
        create_application_instance(
            self.application,
            self.message,
            self.application_queue,
            application_handler=application_handler
        )

    def accept(self):
        self.accepted = True
        rv = b'HTTP/1.1 101 Switching Protocols\r\n'
        for k, v in self.handshake_headers:
            rv += k + b': ' + v + b'\r\n'
        rv += b'\r\n'
        self.transport.write(rv)

    def reject(self):
        rv = b'HTTP/1.1 403 Forbidden\r\n\r\n'
        self.transport.write(rv)
        self.transport.close()
