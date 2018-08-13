from urllib.parse import unquote
import asyncio
import h11
import traceback
import wsproto.connection
import wsproto.events
import wsproto.extensions


class WSProtocol(asyncio.Protocol):
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

        # WebSocket state
        self.connect_event = None
        self.queue = asyncio.Queue()
        self.handshake_complete = False
        self.close_sent = False

        self.conn = wsproto.connection.WSConnection(
            conn_type=wsproto.connection.SERVER,
            extensions=[wsproto.extensions.PerMessageDeflate()],
        )

        # Buffers
        self.bytes = b''
        self.text = ''

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
        print('data_received', data)
        self.conn.receive_bytes(data)
        for event in self.conn.events():
            print(event)
            if isinstance(event, wsproto.events.ConnectionRequested):
                self.handle_connect(event)
            elif isinstance(event, wsproto.events.TextReceived):
                self.handle_text(event)
            elif isinstance(event, wsproto.events.BytesReceived):
                self.handle_bytes(event)
            elif isinstance(event, wsproto.events.ConnectionFailed):
                self.handle_no_connect(event)
            elif isinstance(event, wsproto.events.ConnectionClosed):
                self.handle_close(event)
            elif isinstance(event, wsproto.events.PingReceived):
                self.handle_ping(event)

    # Event handlers

    def handle_connect(self, event):
        self.connect_event = event
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
        self.queue.put_nowait({
            "type": "websocket.connect"
        })
        self.loop.create_task(self.run_asgi(scope))

    def handle_no_connect(self, event):
        msg = h11.Response(status_code=400, headers=[])
        output = self.conn._upgrade_connection.send(msg)
        msg = h11.EndOfMessage()
        output += self.conn._upgrade_connection.send(msg)
        self.transport.write(output)
        self.transport.close()

    def handle_text(self, event):
        self.text += event.data
        if event.message_finished:
            self.queue.put_nowait({
                'type': 'websocket.receive',
                'text': self.text
            })
            self.text = ''

    def handle_bytes(self, event):
        self.bytes += event.data
        if event.message_finished:
            self.queue.put_nowait({
                'type': 'websocket.receive',
                'bytes': self.bytes
            })
            self.bytes = b''

    def handle_close(self, event):
        self.queue.put_nowait({
            'type': 'websocket.disconnect',
            'code': event.code
        })
        self.transport.close()

    def handle_ping(self, event):
        output = self.conn.bytes_to_send()
        self.transport.write(output)

    async def run_asgi(self, scope):
        print('run_asgi')
        try:
            asgi = self.app(scope)
            result = await asgi(self.receive, self.send)
        except:
            msg = "Exception in ASGI application\n%s"
            traceback_text = "".join(traceback.format_exc())
            self.logger.error(msg, traceback_text)
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

    async def send(self, message):
        message_type = message["type"]
        print('send', message)

        if not self.handshake_complete:
            if message_type == "websocket.accept":
                self.handshake_complete = True
                subprotocol = message.get("subprotocol")
                self.conn.accept(self.connect_event, subprotocol)
                output = self.conn.bytes_to_send()
                self.transport.write(output)

            elif message_type == "websocket.close":
                self.handshake_complete = True
                self.close_sent = True
                msg = h11.Response(status_code=403, headers=[])
                output = self.conn._upgrade_connection.send(msg)
                msg = h11.EndOfMessage()
                output += self.conn._upgrade_connection.send(msg)
                self.transport.write(output)
                self.transport.close()

            else:
                msg = "Expected ASGI message 'websocket.accept' or 'websocket.close', but got '%s'."
                raise RuntimeError(msg % message_type)

        elif not self.close_sent:
            if message_type == 'websocket.send':
                bytes_data = message.get('bytes')
                text_data = message.get('text')
                data = text_data if bytes_data is None else bytes_data
                self.conn.send_data(data)
                output = self.conn.bytes_to_send()
                self.transport.write(output)

            elif message_type == 'websocket.close':
                self.close_sent = True
                message.get('code', 1000)
                self.conn.close(code)
                output = self.conn.bytes_to_send()
                self.transport.write(output)
                self.transport.close()

            else:
                msg = "Expected ASGI message 'websocket.send' or 'websocket.close', but got '%s'."
                raise RuntimeError(msg % message_type)

        else:
            msg = "Unexpected ASGI message '%s', after sending 'websocket.close'."
            raise RuntimeError(msg % message_type)

    async def receive(self):
        print('receive')
        return await self.queue.get()
