from urllib.parse import unquote
from uvicorn.protocols.utils import get_local_addr, get_remote_addr, is_ssl
import asyncio
import h11
import logging
import traceback
import wsproto.connection
import wsproto.events
import wsproto.extensions


class WSProtocol(asyncio.Protocol):
    def __init__(self, app, connections=None, tasks=None, loop=None, logger=None):
        self.app = app
        self.root_path = ''
        self.connections = set() if connections is None else connections
        self.tasks = set() if tasks is None else tasks
        self.loop = loop or asyncio.get_event_loop()
        self.logger = logger or logging.getLogger("uvicorn")

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

        self.read_paused = False
        self.writable = asyncio.Event()
        self.writable.set()

        # Buffers
        self.bytes = b''
        self.text = ''

    # Protocol interface

    def connection_made(self, transport):
        self.connections.add(self)
        self.transport = transport
        self.server = get_local_addr(transport)
        self.client = get_remote_addr(transport)
        self.scheme = "wss" if is_ssl(transport) else "ws"

    def connection_lost(self, exc):
        self.connections.remove(self)

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
            elif isinstance(event, wsproto.events.ConnectionFailed):
                self.handle_no_connect(event)
            elif isinstance(event, wsproto.events.ConnectionClosed):
                self.handle_close(event)
            elif isinstance(event, wsproto.events.PingReceived):
                self.handle_ping(event)

    def pause_writing(self):
        """
        Called by the transport when the write buffer exceeds the high water mark.
        """
        self.writable.clear()

    def resume_writing(self):
        """
        Called by the transport when the write buffer drops below the low water mark.
        """
        self.writable.set()

    def shutdown(self):
        self.queue.put_nowait({
            'type': 'websocket.disconnect',
            'code': 1012
        })
        self.conn.close(1012)
        output = self.conn.bytes_to_send()
        self.transport.write(output)
        self.transport.close()

    def on_task_complete(self, task):
        self.tasks.discard(task)

    # Event handlers

    def handle_connect(self, event):
        self.connect_event = event
        request = event.h11request
        headers = [(key.lower(), value) for key, value in request.headers]
        path, _, query_string = request.target.partition(b'?')
        self.scope = {
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
        task = self.loop.create_task(self.run_asgi())
        task.add_done_callback(self.on_task_complete)
        self.tasks.add(task)

    def handle_no_connect(self, event):
        headers = [
            (b"content-type", b"text/plain; charset=utf-8"),
            (b"connection", b"close"),
        ]
        msg = h11.Response(status_code=400, headers=headers, reason='Bad Request')
        output = self.conn._upgrade_connection.send(msg)
        msg = h11.Data(data=event.reason.encode('utf-8'))
        output += self.conn._upgrade_connection.send(msg)
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
            if not self.read_paused:
                self.read_paused = True
                self.transport.pause_reading()

    def handle_bytes(self, event):
        self.bytes += event.data
        if event.message_finished:
            self.queue.put_nowait({
                'type': 'websocket.receive',
                'bytes': self.bytes
            })
            self.bytes = b''
            if not self.read_paused:
                self.read_paused = True
                self.transport.pause_reading()

    def handle_close(self, event):
        self.queue.put_nowait({
            'type': 'websocket.disconnect',
            'code': event.code
        })
        self.transport.close()

    def handle_ping(self, event):
        output = self.conn.bytes_to_send()
        self.transport.write(output)

    def send_500_response(self):
        headers = [
            (b"content-type", b"text/plain; charset=utf-8"),
            (b"connection", b"close"),
        ]
        msg = h11.Response(status_code=500, headers=headers, reason='Internal Server Error')
        output = self.conn._upgrade_connection.send(msg)
        msg = h11.Data(data=b'Internal Server Error')
        output += self.conn._upgrade_connection.send(msg)
        msg = h11.EndOfMessage()
        output += self.conn._upgrade_connection.send(msg)
        self.transport.write(output)

    async def run_asgi(self):
        try:
            asgi = self.app(self.scope)
            result = await asgi(self.receive, self.send)
        except:
            msg = "Exception in ASGI application\n%s"
            traceback_text = "".join(traceback.format_exc())
            self.logger.error(msg, traceback_text)
            if not self.handshake_complete:
                self.send_500_response()
            self.transport.close()
        else:
            if not self.handshake_complete:
                msg = "ASGI callable returned without completing handshake."
                self.logger.error(msg)
                self.send_500_response()
                self.transport.close()
            elif result is not None:
                msg = "ASGI callable should return None, but returned '%s'."
                self.logger.error(msg, result)
                self.transport.close()

    async def send(self, message):
        await self.writable.wait()

        message_type = message["type"]

        if not self.handshake_complete:
            if message_type == "websocket.accept":
                self.logger.info(
                    '%s - "WebSocket %s" [accepted]',
                    self.scope["server"][0],
                    self.scope["path"],
                )
                self.handshake_complete = True
                subprotocol = message.get("subprotocol")
                self.conn.accept(self.connect_event, subprotocol)
                output = self.conn.bytes_to_send()
                self.transport.write(output)

            elif message_type == "websocket.close":
                self.queue.put_nowait({
                    'type': 'websocket.disconnect',
                    'code': None
                })
                self.logger.info(
                    '%s - "WebSocket %s" 403',
                    self.scope["server"][0],
                    self.scope["path"],
                )
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
                if not self.transport.is_closing():
                    self.transport.write(output)

            elif message_type == 'websocket.close':
                self.close_sent = True
                code = message.get('code', 1000)
                self.queue.put_nowait({
                    'type': 'websocket.disconnect',
                    'code': code
                })
                self.conn.close(code)
                output = self.conn.bytes_to_send()
                if not self.transport.is_closing():
                    self.transport.write(output)
                    self.transport.close()

            else:
                msg = "Expected ASGI message 'websocket.send' or 'websocket.close', but got '%s'."
                raise RuntimeError(msg % message_type)

        else:
            msg = "Unexpected ASGI message '%s', after sending 'websocket.close'."
            raise RuntimeError(msg % message_type)

    async def receive(self):
        message = await self.queue.get()
        if self.read_paused and self.queue.empty():
            self.read_paused = False
            self.transport.resume_reading()
        return message
