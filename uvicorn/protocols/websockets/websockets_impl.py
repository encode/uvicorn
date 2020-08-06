import asyncio
import http
import logging
from asyncio import AbstractEventLoop, Task
from typing import TYPE_CHECKING, Optional, Sequence, Union
from urllib.parse import unquote

import websockets
from websockets import Subprotocol, WebSocketServer, WebSocketServerProtocol
from websockets.http import Headers

from uvicorn._types import Message, Scope, TransportType
from uvicorn.protocols.utils import get_local_addr, get_remote_addr, is_ssl

if TYPE_CHECKING:
    from uvicorn import Config
    from uvicorn.main import ServerState


class Server(WebSocketServer):
    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self.closing: bool = False
        super().__init__(loop)

    def register(self, ws: websockets.WebSocketServerProtocol) -> None:
        pass

    def unregister(self, ws: websockets.WebSocketServerProtocol) -> None:
        pass

    def is_serving(self) -> bool:
        return not self.closing


class WebSocketProtocol(websockets.WebSocketServerProtocol):
    def __init__(
        self,
        config: "Config",
        server_state: "ServerState",
        _loop: Optional[AbstractEventLoop] = None,
    ):
        if not config.loaded:
            config.load()

        self.config = config
        self.app = config.loaded_app
        self.loop = _loop or asyncio.get_event_loop()
        self.logger = logging.getLogger("uvicorn.error")
        self.root_path = config.root_path

        # Shared server state
        self.connections = server_state.connections
        self.tasks = server_state.tasks

        # Connection events
        self.handshake_started_event = asyncio.Event()
        self.handshake_completed_event = asyncio.Event()
        self.closed_event = asyncio.Event()
        self.connect_sent = False
        self.accepted_subprotocol = None

        self.ws_server = Server(loop=self.loop)

        super().__init__(ws_handler=self.ws_handler, ws_server=self.ws_server)

    def connection_made(self, transport: TransportType) -> None:
        self.connections.add(self)
        self.transport = transport
        self.server = get_local_addr(transport)
        self.client = get_remote_addr(transport)
        self.scheme = "wss" if is_ssl(transport) else "ws"
        super().connection_made(transport)

    def connection_lost(self, exc: Optional[Exception]) -> None:
        self.connections.remove(self)
        self.handshake_completed_event.set()
        super().connection_lost(exc)

    def shutdown(self) -> None:
        # self.ws_server.closing = True
        self.transport.close()

    def on_task_complete(self, task: Task) -> None:
        self.tasks.discard(task)

    async def process_request(self, path: str, headers: Headers) -> None:
        """
        This hook is called to determine if the websocket should return
        an HTTP response and close.

        Our behavior here is to start the ASGI application, and then wait
        for either `accept` or `close` in order to determine if we should
        close the connection.
        """
        path_portion, _, query_string = path.partition("?")

        websockets.handshake.check_request(headers)

        subprotocols = []
        for header in headers.get_all("Sec-WebSocket-Protocol"):
            subprotocols.extend([token.strip() for token in header.split(",")])

        asgi_headers = [
            (name.encode("ascii"), value.encode("ascii"))
            for name, value in headers.raw_items()
        ]

        self.scope: Scope = {
            "type": "websocket",
            "asgi": {"version": self.config.asgi_version, "spec_version": "2.1"},
            "scheme": self.scheme,
            "server": self.server,
            "client": self.client,
            "root_path": self.root_path,
            "path": unquote(path_portion),
            "raw_path": path_portion,
            "query_string": query_string.encode("ascii"),
            "headers": asgi_headers,
            "subprotocols": subprotocols,
        }
        task = self.loop.create_task(self.run_asgi())
        task.add_done_callback(self.on_task_complete)
        self.tasks.add(task)
        await self.handshake_started_event.wait()
        return self.initial_response

    def process_subprotocol(
        self, headers: Headers, available_subprotocols: Optional[Sequence[Subprotocol]]
    ) -> Optional[Subprotocol]:
        """
        We override the standard 'process_subprotocol' behavior here so that
        we return whatever subprotocol is sent in the 'accept' message.
        """
        return self.accepted_subprotocol

    def send_500_response(self) -> None:
        msg = b"Internal Server Error"
        content = [
            b"HTTP/1.1 500 Internal Server Error\r\n"
            b"content-type: text/plain; charset=utf-8\r\n",
            b"content-length: " + str(len(msg)).encode("ascii") + b"\r\n",
            b"connection: close\r\n",
            b"\r\n",
            msg,
        ]
        self.transport.write(b"".join(content))

    async def ws_handler(self, protocol: WebSocketServerProtocol, path: str) -> None:
        """
        This is the main handler function for the 'websockets' implementation
        to call into. We just wait for close then return, and instead allow
        'send' and 'receive' events to drive the flow.
        """
        self.handshake_completed_event.set()
        await self.closed_event.wait()

    async def run_asgi(self) -> None:
        """
        Wrapper around the ASGI callable, handling exceptions and unexpected
        termination states.
        """
        try:
            result = await self.app(self.scope, self.asgi_receive, self.asgi_send)
        except BaseException as exc:
            self.closed_event.set()
            msg = "Exception in ASGI application\n"
            self.logger.error(msg, exc_info=exc)
            if not self.handshake_started_event.is_set():
                self.send_500_response()
            else:
                await self.handshake_completed_event.wait()
            self.transport.close()
        else:
            self.closed_event.set()
            if not self.handshake_started_event.is_set():
                msg = "ASGI callable returned without sending handshake."
                self.logger.error(msg)
                self.send_500_response()
                self.transport.close()
            elif result is not None:
                msg = "ASGI callable should return None, but returned '%s'."
                self.logger.error(msg, result)
                await self.handshake_completed_event.wait()
                self.transport.close()

    async def asgi_send(self, message: Message) -> None:
        message_type = message["type"]

        if not self.handshake_started_event.is_set():
            if message_type == "websocket.accept":
                self.logger.info(
                    '%s - "WebSocket %s" [accepted]',
                    self.scope["client"],
                    self.scope["root_path"] + self.scope["path"],
                )
                self.initial_response = None
                self.accepted_subprotocol = message.get("subprotocol")
                self.handshake_started_event.set()

            elif message_type == "websocket.close":
                self.logger.info(
                    '%s - "WebSocket %s" 403',
                    self.scope["client"],
                    self.scope["root_path"] + self.scope["path"],
                )
                self.initial_response = (http.HTTPStatus.FORBIDDEN, [], b"")
                self.handshake_started_event.set()
                self.closed_event.set()

            else:
                msg = (
                    "Expected ASGI message 'websocket.accept' or 'websocket.close', "
                    "but got '%s'."
                )
                raise RuntimeError(msg % message_type)

        elif not self.closed_event.is_set():
            await self.handshake_completed_event.wait()

            if message_type == "websocket.send":
                bytes_data: bytes = message.get("bytes")
                text_data: str = message.get("text")
                data: Union[
                    str, bytes
                ] = text_data if bytes_data is None else bytes_data
                await self.send(data)

            elif message_type == "websocket.close":
                code = message.get("code", 1000)
                await self.close(code)
                self.closed_event.set()

            else:
                msg = (
                    "Expected ASGI message 'websocket.send' or 'websocket.close',"
                    " but got '%s'."
                )
                raise RuntimeError(msg % message_type)

        else:
            msg = "Unexpected ASGI message '%s', after sending 'websocket.close'."
            raise RuntimeError(msg % message_type)

    async def asgi_receive(self) -> Message:
        if not self.connect_sent:
            self.connect_sent = True
            return {"type": "websocket.connect"}

        await self.handshake_completed_event.wait()
        try:
            data = await self.recv()
        except websockets.ConnectionClosed as exc:
            return {"type": "websocket.disconnect", "code": exc.code}

        msg: Message
        msg = {"type": "websocket.receive"}

        if isinstance(data, str):
            msg["text"] = data
        else:
            msg["bytes"] = data

        return msg
