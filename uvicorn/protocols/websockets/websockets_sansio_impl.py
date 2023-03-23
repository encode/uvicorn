import asyncio
import logging
import sys
import typing
from asyncio.transports import BaseTransport, Transport
from urllib.parse import unquote

from websockets.extensions.permessage_deflate import ServerPerMessageDeflateFactory
from websockets.http11 import Request
from websockets.server import ServerConnection

from uvicorn.config import Config
from uvicorn.logging import TRACE_LOG_LEVEL
from uvicorn.protocols.utils import (
    get_local_addr,
    get_path_with_query_string,
    get_remote_addr,
    is_ssl,
)
from uvicorn.server import ServerState

if sys.version_info < (3, 8):
    from typing_extensions import Literal
else:
    from typing import Literal

if typing.TYPE_CHECKING:
    from asgiref.typing import (
        ASGISendEvent,
        WebSocketAcceptEvent,
        WebSocketCloseEvent,
        WebSocketConnectEvent,
        WebSocketDisconnectEvent,
        WebSocketReceiveEvent,
        WebSocketScope,
        WebSocketSendEvent,
    )

    WebSocketEvent = typing.Union[
        "WebSocketReceiveEvent",
        "WebSocketDisconnectEvent",
        "WebSocketConnectEvent",
    ]


class WebSocketsSansIOProtocol(asyncio.Protocol):
    def __init__(
        self,
        config: Config,
        server_state: ServerState,
        app_state: typing.Dict[str, typing.Any],
        _loop: typing.Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        if not config.loaded:
            config.load()

        self.config = config
        self.app = config.loaded_app
        self.loop = _loop or asyncio.get_event_loop()
        self.logger = logging.getLogger("uvicorn.error")
        self.root_path = config.root_path
        self.app_state = app_state

        # Shared server state
        self.connections = server_state.connections
        self.tasks = server_state.tasks
        self.default_headers = server_state.default_headers

        # Connection state
        self.transport: asyncio.Transport = None  # type: ignore[assignment]
        self.server: typing.Optional[typing.Tuple[str, int]] = None
        self.client: typing.Optional[typing.Tuple[str, int]] = None
        self.scheme: Literal["wss", "ws"] = None  # type: ignore[assignment]

        # WebSocket state
        self.queue: asyncio.Queue["WebSocketEvent"] = asyncio.Queue()
        self.handshake_complete = False
        self.close_sent = False

        extensions = []
        if self.config.ws_per_message_deflate:
            extensions.append(ServerPerMessageDeflateFactory())
        self.conn = ServerConnection(extensions=extensions)

        self.read_paused = False
        self.writable = asyncio.Event()
        self.writable.set()

        # Buffers
        self.bytes = b""
        self.text = ""

    def connection_made(self, transport: BaseTransport) -> None:
        """Called when a connection is made."""
        transport = typing.cast(Transport, transport)
        self.connections.add(self)
        self.transport = transport
        self.server = get_local_addr(transport)
        self.client = get_remote_addr(transport)
        self.scheme = "wss" if is_ssl(transport) else "ws"

        if self.logger.level <= TRACE_LOG_LEVEL:
            prefix = "%s:%d - " % self.client if self.client else ""
            self.logger.log(TRACE_LOG_LEVEL, "%sWebSocket connection made", prefix)

    def eof_received(self) -> None:
        self.conn.receive_eof()

    def data_received(self, data: bytes) -> None:
        # NOTE: Does receive_data raises any other exception?
        self.conn.receive_data(data)
        self.handle_events()

    def handle_events(self) -> None:
        for event in self.conn.events_received():
            print(event)
            if isinstance(event, Request):
                self.handle_connect(event)

    # Event handlers

    def handle_connect(self, event: Request) -> None:
        self.request = event
        headers = [
            (key.lower().encode(), value.encode())
            for key, value in event.headers.raw_items()
        ]
        raw_path, _, query_string = event.path.partition("?")
        self.scope: "WebSocketScope" = {  # type: ignore[typeddict-item]
            "type": "websocket",
            "asgi": {"version": self.config.asgi_version, "spec_version": "2.3"},
            "http_version": "1.1",
            "scheme": self.scheme,
            "server": self.server,
            "client": self.client,
            "root_path": self.root_path,
            "path": unquote(raw_path),
            "raw_path": raw_path.encode("ascii"),
            "query_string": query_string.encode("ascii"),
            "headers": headers,
            "subprotocols": event.headers.get_all("Sec-WebSocket-Protocol"),
            "extensions": None,
            "state": self.app_state.copy(),
        }
        self.queue.put_nowait({"type": "websocket.connect"})
        task = self.loop.create_task(self.run_asgi())
        # task.add_done_callback(self.on_task_complete)
        # self.tasks.add(task)

    async def run_asgi(self) -> None:
        try:
            result = await self.app(self.scope, self.receive, self.send)
        except BaseException:
            self.logger.exception("Exception in ASGI application\n")
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

    def send_500_response(self) -> None:
        ...

    async def send(self, message: "ASGISendEvent") -> None:
        await self.writable.wait()

        message_type = message["type"]

        if not self.handshake_complete:
            if message_type == "websocket.accept":
                message = typing.cast("WebSocketAcceptEvent", message)
                self.logger.info(
                    '%s - "WebSocket %s" [accepted]',
                    self.scope["client"],
                    get_path_with_query_string(self.scope),
                )
                extra_headers = [
                    (key.decode(), value.decode())
                    for key, value in self.default_headers
                    + list(message.get("headers", []))
                ]
                if not self.transport.is_closing():
                    self.handshake_complete = True
                    response = self.conn.accept(self.request)
                    response.headers.update(extra_headers)
                    self.conn.send_response(response)
                    output = self.conn.data_to_send()
                    self.transport.writelines(output)

            elif message_type == "websocket.close":
                self.queue.put_nowait({"type": "websocket.disconnect", "code": 1006})
                self.logger.info(
                    '%s - "WebSocket %s" 403',
                    self.scope["client"],
                    get_path_with_query_string(self.scope),
                )
                self.handshake_complete = True
                self.close_sent = True
                event = events.RejectConnection(status_code=403, headers=[])
                output = self.conn.send(event)
                self.transport.write(output)
                self.transport.close()

            else:
                msg = (
                    "Expected ASGI message 'websocket.accept' or 'websocket.close', "
                    "but got '%s'."
                )
                raise RuntimeError(msg % message_type)

        elif not self.close_sent:
            if message_type == "websocket.send":
                message = typing.cast("WebSocketSendEvent", message)
                bytes_data = message.get("bytes")
                text_data = message.get("text")
                data = text_data if bytes_data is None else bytes_data
                output = self.conn.send(
                    wsproto.events.Message(data=data)  # type: ignore[type-var]
                )
                if not self.transport.is_closing():
                    self.transport.write(output)

            elif message_type == "websocket.close":
                message = typing.cast("WebSocketCloseEvent", message)
                self.close_sent = True
                code = message.get("code", 1000)
                reason = message.get("reason", "") or ""
                self.queue.put_nowait({"type": "websocket.disconnect", "code": code})
                output = self.conn.send(
                    wsproto.events.CloseConnection(code=code, reason=reason)
                )
                if not self.transport.is_closing():
                    self.transport.write(output)
                    self.transport.close()

            else:
                msg = (
                    "Expected ASGI message 'websocket.send' or 'websocket.close',"
                    " but got '%s'."
                )
                raise RuntimeError(msg % message_type)

        else:
            msg = "Unexpected ASGI message '%s', after sending 'websocket.close'."
            raise RuntimeError(msg % message_type)

    async def receive(self) -> "WebSocketEvent":
        message = await self.queue.get()
        if self.read_paused and self.queue.empty():
            self.read_paused = False
            self.transport.resume_reading()
        return message
