from urllib.parse import unquote
import asyncio
import wsproto


class WSProtocol(asyncio.Protocol):
    def __init__(self):
        self.conn = wsproto.connection.WSConnection(
            conn_type=wsproto.connection.SERVER,
            extensions=[wsproto.extensions.PerMessageDeflate()],
        )
        self.app = None
        self.root_path = ''

        self.transport = None
        self.server = None
        self.client = None
        self.scheme = None

    # Protocol interface

    def connection_made(self, transport):
        self.transport = transport
        self.server = transport.get_extra_info("sockname")
        self.client = transport.get_extra_info("peername")
        self.scheme = "wss" if transport.get_extra_info("sslcontext") else "ws"

    def connection_lost(self, exc):
        pass

    def eof_received(self):
        pass

    def data_received(self, data):
        self.conn.receive_bytes(data)
        for event in self.conn.events():
            if isinstance(event, wsproto.events.ConnectionRequested):
                self.handle_connect(event)
            elif isinstance(event, wsproto.events.TextReceived):
                self.handle_text(event)
            elif isinstance(event, wsproto.events.BytesReceived):
                self.handle_bytes(event)
            elif isinstance(event, wsproto.events.ConnectionClosed):
                self.handle_close(event)
            elif isinstance(event, wsproto.events.PingReceived):
                self.handle_ping(event)

    # Event handlers

    def handle_connect(self, event):
        request = event.h11request
        headers = [(key.lower(), value) for key, value in request.headers]
        path, _, query_string = request.target.partition(b'?')
        scope = {
            'type': 'websocket',
            'scheme': self.scheme,
            'server': self.server,
            'client': self.client,
            'root_path': self.root_path,
            'path': unquote(path.decode('ascii')),
            'query_string': query_string,
            'headers': headers,
            'subprotocols': [],
        }
        self.session = WebSocketSession(
            scope=scope,
            request=event,
            conn=self.conn,
            transport=self.transport,
            logger=self.logger
        )
        self.loop.create_task(self.session.run_asgi(self.app))

    def handle_text(self, event):
        self.text += event.data
        if event.message_finished:
            self.session.queue.put_nowait({
                'type': 'websocket.receive',
                'text': self.text
            })
            self.text = ''
            self.bytes = b''
            # TODO: Flow control

    def handle_bytes(self, event):
        self.bytes += event.data
        if event.message_finished:
            self.session.queue.put_nowait({
                'type': 'websocket.receive',
                'bytes': self.bytes
            })
            self.text = ''
            self.bytes = b''
            # TODO: Flow control

    def handle_close(self, event):
        self.session.queue.put_nowait({
            'type': 'websocket.disconnect',
            'code': event.code
        })

    def handle_ping(self, event):
        output = self.conn.bytes_to_send()
        self.transport.write(output)


class WebSocketSession:
    def __init__(self, scope, request, conn, transport, logger):
        self.scope = scope
        self.request = request
        self.conn = conn
        self.transport = transport
        self.logger = logger
        self.queue = asyncio.Queue()
        self.queue.put_nowait({'type': 'websocket.connect'})
        self.handshake_complete = False
        self.close_sent = False

    async def run_asgi(self, app):
        try:
            asgi = app(self.scope)
            result = await asgi(self.receive, self.send)
        except:
            msg = "Exception in ASGI application\n%s"
            traceback_text = "".join(traceback.format_exc())
            self.logger.error(msg, traceback_text)
            if not self.response_started:
                await self.send_500_response()
            else:
                self.transport.close()
        else:
            if result is not None:
                msg = "ASGI callable should return None, but returned '%s'."
                self.logger.error(msg, result)
                self.transport.close()
            elif not self.handshake_complete:
                msg = "ASGI callable returned without completing handshake."
                self.logger.error(msg)
                self.transport.close()
            # elif not self.response_complete:
            #     msg = "ASGI callable returned without completing response."
            #     self.logger.error(msg)
            #     self.transport.close()

    async def send(self, message):
        message_type = message["type"]

        # TODO: flow control

        if not self.handshake_complete:
            if message_type == "websocket.accept":
                self.handshake_complete = True
                self.conn.accept(self.request)
                output = self.connection.bytes_to_send()
                self.transport.write(output)

            elif message_type == "websocket.close":
                self.handshake_complete = True
                self.close_sent = True
                message.get('code', 1000)
                self.conn.close(code)
                output = self.connection.bytes_to_send()
                self.transport.write(output)

            else:
                msg = "Expected ASGI message 'websocket.accept' or 'websocket.close', but got '%s'."
                raise RuntimeError(msg % message_type)

        elif not self.closed:
            if message_type == 'websocket.send':
                bytes_data = message.get('bytes')
                    data = message.get('')
                self.conn.send_data(data)
                output = self.conn.bytes_to_send()
                self.transport.write(output)

            elif message_type == 'websocket.close':
                self.close_sent = True
                message.get('code', 1000)
                self.conn.close(code)
                output = self.connection.bytes_to_send()
                self.transport.write(output)

            else:
                msg = "Expected ASGI message 'websocket.send' or 'websocket.close', but got '%s'."
                raise RuntimeError(msg % message_type)

    async def receive(self):
        message = await self.queue.get()
        # TODO: flow control
        return message
