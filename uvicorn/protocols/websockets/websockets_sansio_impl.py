import asyncio
import logging
import typing
from asyncio.transports import BaseTransport, Transport
from http import HTTPStatus
from typing import Literal
from urllib.parse import unquote

from websockets.extensions.permessage_deflate import ServerPerMessageDeflateFactory
from websockets.frames import Frame, Opcode
from websockets.http11 import Request
from websockets.server import ServerProtocol

from uvicorn._types import (
    ASGIReceiveEvent,
    ASGISendEvent,
    WebSocketAcceptEvent,
    WebSocketCloseEvent,
    WebSocketDisconnectEvent,
    WebSocketReceiveEvent,
    WebSocketScope,
    WebSocketSendEvent,
)
from uvicorn.config import Config
from uvicorn.logging import TRACE_LOG_LEVEL
from uvicorn.protocols.utils import (
    get_local_addr,
    get_path_with_query_string,
    get_remote_addr,
    is_ssl,
)
from uvicorn.server import ServerState


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
        self.queue: asyncio.Queue[ASGIReceiveEvent] = asyncio.Queue()
        self.handshake_initiated = False
        self.handshake_complete = False
        self.close_sent = False

        extensions = []
        if self.config.ws_per_message_deflate:
            extensions = [ServerPerMessageDeflateFactory()]
        self.conn = ServerProtocol(
            extensions=extensions,
            max_size=self.config.ws_max_size,
            logger=logging.getLogger("uvicorn.error"),
        )

        self.read_paused = False
        self.writable = asyncio.Event()
        self.writable.set()

        # Buffers
        self.bytes = b""

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

    def connection_lost(self, exc: typing.Optional[Exception]) -> None:
        self.connections.remove(self)
        if self.logger.level <= TRACE_LOG_LEVEL:
            prefix = "%s:%d - " % self.client if self.client else ""
            self.logger.log(TRACE_LOG_LEVEL, "%sWebSocket connection lost", prefix)
        if self.handshake_initiated and not self.close_sent:
            self.queue.put_nowait({"type": "websocket.disconnect", "code": 1006})

    def shutdown(self) -> None:
        if not self.transport.is_closing():
            if self.handshake_complete:
                self.queue.put_nowait({"type": "websocket.disconnect", "code": 1012})
                self.close_sent = True
                self.conn.send_close(1012)
                output = self.conn.data_to_send()
                self.transport.writelines(output)
            elif self.handshake_initiated:
                self.send_500_response()
                self.queue.put_nowait({"type": "websocket.disconnect", "code": 1006})
            self.transport.close()

    def data_received(self, data: bytes) -> None:
        try:
            self.conn.receive_data(data)
        except Exception:
            self.logger.exception("Exception in ASGI server")
            self.transport.close()
        self.handle_events()

    def handle_events(self) -> None:
        for event in self.conn.events_received():
            if isinstance(event, Request):
                self.handle_connect(event)
            if isinstance(event, Frame):
                if event.opcode == Opcode.CONT:
                    self.handle_cont(event)
                elif event.opcode == Opcode.TEXT:
                    self.handle_text(event)
                elif event.opcode == Opcode.BINARY:
                    self.handle_bytes(event)
                elif event.opcode == Opcode.PING:
                    self.handle_ping(event)
                elif event.opcode == Opcode.PONG:
                    self.handle_pong(event)
                elif event.opcode == Opcode.CLOSE:
                    self.handle_close(event)

    # Event handlers

    def handle_connect(self, event: Request) -> None:
        self.request = event
        self.response = self.conn.accept(event)
        self.handshake_initiated = True
        # if status_code is not 101 return response
        if self.response.status_code != 101:
            self.handshake_complete = True
            self.close_sent = True
            self.conn.send_response(self.response)
            output = self.conn.data_to_send()
            self.transport.writelines(output)
            self.transport.close()
            return

        headers = [
            (key.encode("ascii"), value.encode("ascii", errors="surrogateescape"))
            for key, value in event.headers.raw_items()
        ]
        raw_path, _, query_string = event.path.partition("?")
        self.scope: "WebSocketScope" = {
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
            "state": self.app_state.copy(),
        }
        self.queue.put_nowait({"type": "websocket.connect"})
        task = self.loop.create_task(self.run_asgi())
        task.add_done_callback(self.on_task_complete)
        self.tasks.add(task)

    def handle_cont(self, event: Frame) -> None:
        self.bytes += event.data
        if event.fin:
            self.send_receive_event_to_app()

    def handle_text(self, event: Frame) -> None:
        self.bytes = event.data
        self.curr_msg_data_type: Literal["text", "bytes"] = "text"
        if event.fin:
            self.send_receive_event_to_app()

    def handle_bytes(self, event: Frame) -> None:
        self.bytes = event.data
        self.curr_msg_data_type = "bytes"
        if event.fin:
            self.send_receive_event_to_app()

    def send_receive_event_to_app(self) -> None:
        data_type = self.curr_msg_data_type
        msg: WebSocketReceiveEvent
        if data_type == "text":
            msg = {"type": "websocket.receive", data_type: self.bytes.decode()}
        else:
            msg = {"type": "websocket.receive", data_type: self.bytes}
        self.queue.put_nowait(msg)
        if not self.read_paused:
            self.read_paused = True
            self.transport.pause_reading()

    def handle_ping(self, event: Frame) -> None:
        output = self.conn.data_to_send()
        self.transport.writelines(output)

    def handle_pong(self, event: Frame) -> None:
        pass

    def handle_close(self, event: Frame) -> None:
        if not self.close_sent and not self.transport.is_closing():
            disconnect_event: WebSocketDisconnectEvent = {
                "type": "websocket.disconnect",
                "code": self.conn.close_rcvd.code,  # type: ignore[union-attr]
            }
            self.queue.put_nowait(disconnect_event)
            output = self.conn.data_to_send()
            self.transport.writelines(output)
            self.close_sent = True
            self.transport.close()

    def on_task_complete(self, task: asyncio.Task[None]) -> None:
        self.tasks.discard(task)

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

    async def send(self, message: ASGISendEvent) -> None:
        await self.writable.wait()

        message_type = message["type"]

        if not self.handshake_complete:
            if message_type == "websocket.accept" and not self.transport.is_closing():
                message = typing.cast("WebSocketAcceptEvent", message)
                self.logger.info(
                    '%s - "WebSocket %s" [accepted]',
                    self.scope["client"],
                    get_path_with_query_string(self.scope),
                )
                headers = [
                    (
                        key.decode("ascii"),
                        value.decode("ascii", errors="surrogateescape"),
                    )
                    for key, value in self.default_headers
                    + list(message.get("headers", []))
                ]

                accepted_subprotocol = message.get("subprotocol")
                if accepted_subprotocol:
                    headers.append(("Sec-WebSocket-Protocol", accepted_subprotocol))

                self.handshake_complete = True
                self.response.headers.update(headers)
                self.conn.send_response(self.response)
                output = self.conn.data_to_send()
                self.transport.writelines(output)

            elif message_type == "websocket.close" and not self.transport.is_closing():
                message = typing.cast("WebSocketCloseEvent", message)
                self.queue.put_nowait(
                    {
                        "type": "websocket.disconnect",
                        "code": message.get("code", 1000) or 1000,
                    }
                )
                self.logger.info(
                    '%s - "WebSocket %s" 403',
                    self.scope["client"],
                    get_path_with_query_string(self.scope),
                )
                extra_headers = [
                    (
                        key.decode("ascii"),
                        value.decode("ascii", errors="surrogateescape"),
                    )
                    for key, value in self.default_headers
                ]

                response = self.conn.reject(
                    HTTPStatus.FORBIDDEN, message.get("reason", "") or ""
                )
                response.headers.update(extra_headers)
                self.conn.send_response(response)
                output = self.conn.data_to_send()
                self.close_sent = True
                self.handshake_complete = True
                self.transport.writelines(output)
                self.transport.close()

            else:
                msg = (
                    "Expected ASGI message 'websocket.accept' or 'websocket.close', "
                    "but got '%s'."
                )
                raise RuntimeError(msg % message_type)

        elif not self.close_sent:
            if message_type == "websocket.send" and not self.transport.is_closing():
                message = typing.cast(WebSocketSendEvent, message)
                bytes_data = message.get("bytes")
                text_data = message.get("text")
                if text_data:
                    self.conn.send_text(text_data.encode())
                elif bytes_data:
                    self.conn.send_binary(bytes_data)
                output = self.conn.data_to_send()
                self.transport.writelines(output)

            elif message_type == "websocket.close" and not self.transport.is_closing():
                message = typing.cast(WebSocketCloseEvent, message)
                code = message.get("code", 1000)
                reason = message.get("reason", "") or ""
                self.queue.put_nowait({"type": "websocket.disconnect", "code": code})
                self.conn.send_close(code, reason)
                output = self.conn.data_to_send()
                self.transport.writelines(output)
                self.close_sent = True
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

    async def receive(self) -> ASGIReceiveEvent:
        message = await self.queue.get()
        if self.read_paused and self.queue.empty():
            self.read_paused = False
            self.transport.resume_reading()
        return message
