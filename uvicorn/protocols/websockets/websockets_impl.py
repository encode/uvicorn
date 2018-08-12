from urllib.parse import unquote
import asyncio
import http
import traceback
import websockets


class Server:
    closing = False

    def register(self, ws):
        pass

    def unregister(self, ws):
        pass


class WebSocketProtocol(websockets.WebSocketServerProtocol):
    def __init__(self, app, logger):
        self.app = app
        self.root_path = ''
        self.logger = logger
        self.loop = asyncio.get_event_loop()

        # Connection state
        self.transport = None
        self.server = None
        self.client = None
        self.scheme = None

        # Connection events
        self.handshake_started_event = asyncio.Event()
        self.handshake_completed_event = asyncio.Event()
        self.closed_event = asyncio.Event()
        self.initial_response = None
        self.connect_sent = False
        self.accepted_subprotocol = None

        server = Server()

        super().__init__(ws_handler=self.ws_handler, ws_server=server)

    def connection_made(self, transport):
        self.transport = transport
        self.server = transport.get_extra_info("sockname")
        self.client = transport.get_extra_info("peername")
        self.scheme = "wss" if transport.get_extra_info("sslcontext") else "ws"
        super().connection_made(transport)

    async def process_request(self, path, headers):
        websockets.handshake.check_request(headers)

        subprotocols = []
        for header in headers.get_all('Sec-WebSocket-Protocol'):
            subprotocols.extend([token.strip() for token in header.split(',')])

        scope = {
            'type': 'websocket',
            'scheme': self.scheme,
            'server': self.server,
            'client': self.client,
            'root_path': self.root_path,
            'path': unquote(path),
            'query_string': b'',  # TODO
            'headers': [],  # TODO
            'subprotocols': subprotocols,
        }
        self.loop.create_task(self.run_asgi(scope))
        await self.handshake_started_event.wait()
        print('initial_response', self.initial_response)
        return self.initial_response

    def process_subprotocol(self, headers, available_subprotocols):
        return self.accepted_subprotocol

    async def ws_handler(self, protocol, path):
        print('ws_handler')
        self.handshake_completed_event.set()
        await self.closed_event.wait()

    async def write_http_response(self, status, headers, body=b''):
        print('write_http_response(%s, %s, %s)' % (status, headers, body))
        await super().write_http_response(status, headers, body)

    async def run_asgi(self, scope):
        """
        Wrapper around the ASGI callable, handling exceptions and unexpected
        termination states.
        """
        try:
            asgi = self.app(scope)
            result = await asgi(self.asgi_receive, self.asgi_send)
        except:
            self.closed_event.set()
            msg = "Exception in ASGI application\n%s"
            traceback_text = "".join(traceback.format_exc())
            self.logger.error(msg, traceback_text)
            self.transport.close()
        else:
            self.closed_event.set()
            if result is not None:
                msg = "ASGI callable should return None, but returned '%s'."
                self.logger.error(msg, result)
                self.transport.close()
            elif not self.handshake_started_event.is_set():
                msg = "ASGI callable returned without sending handshake."
                self.logger.error(msg)
                self.transport.close()

    async def asgi_send(self, message):
        print('send', message)
        message_type = message["type"]

        if not self.handshake_started_event.is_set():
            if message_type == "websocket.accept":
                self.initial_response = None
                self.accepted_subprotocol = message.get('subprotocol')
                self.handshake_started_event.set()

            elif message_type == "websocket.close":
                self.initial_response = (http.HTTPStatus.FORBIDDEN, [], b'')
                self.handshake_started_event.set()
                self.closed_event.set()

            else:
                msg = "Expected ASGI message 'websocket.accept' or 'websocket.close', but got '%s'."
                raise RuntimeError(msg % message_type)

        else:
            if self.closed_event.is_set():
                msg = "Unexpected ASGI message '%s', after sending 'websocket.close'."
                raise RuntimeError(msg % message_type)

            await self.handshake_completed_event.wait()

            if message_type == 'websocket.send':
                bytes_data = message.get('bytes')
                text_data = message.get('text')
                data = text_data if bytes_data is None else bytes_data
                await self.send(data)

            elif message_type == 'websocket.close':
                self.closed_event.set()

            else:
                msg = "Expected ASGI message 'websocket.send' or 'websocket.close', but got '%s'."
                raise RuntimeError(msg % message_type)

    async def asgi_receive(self):
        print('receive')

        if not self.connect_sent:
            self.connect_sent = True
            return {
                "type": "websocket.connect"
            }

        await self.handshake_completed_event.wait()
        try:
            data = await self.recv()
        except websockets.ConnectionClosed as exc:
            return {
                "type": "websocket.disconnect",
                "code": exc.code,
            }

        is_text = isinstance(data, str)
        return {
            "type": "websocket.receive",
            "text": data if is_text else None,
            "bytes": None if is_text else data,
        }
