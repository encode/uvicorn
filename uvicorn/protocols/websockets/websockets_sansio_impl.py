from __future__ import annotations

import asyncio
import logging
from asyncio.transports import BaseTransport, Transport
from http import HTTPStatus
from typing import Any, Literal, cast
from urllib.parse import unquote

from websockets import InvalidState
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
    WebSocketResponseBodyEvent,
    WebSocketResponseStartEvent,
    WebSocketScope,
    WebSocketSendEvent,
)
from uvicorn.config import Config
from uvicorn.logging import TRACE_LOG_LEVEL
from uvicorn.protocols.utils import (
    ClientDisconnected,
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
        app_state: dict[str, Any],
        _loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        if not config.loaded:
            config.load()  # pragma: no cover

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
        self.server: tuple[str, int] | None = None
        self.client: tuple[str, int] | None = None
        self.scheme: Literal["wss", "ws"] = None  # type: ignore[assignment]

        # WebSocket state
        self.queue: asyncio.Queue[ASGIReceiveEvent] = asyncio.Queue()
        self.handshake_initiated = False
        self.handshake_complete = False
        self.close_sent = False
        self.initial_response: tuple[int, list[tuple[str, str]], bytes] | None = None

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
        transport = cast(Transport, transport)
        self.connections.add(self)
        self.transport = transport
        self.server = get_local_addr(transport)
        self.client = get_remote_addr(transport)
        self.scheme = "wss" if is_ssl(transport) else "ws"

        if self.logger.level <= TRACE_LOG_LEVEL:
            prefix = "%s:%d - " % self.client if self.client else ""
            self.logger.log(TRACE_LOG_LEVEL, "%sWebSocket connection made", prefix)

    def connection_lost(self, exc: Exception | None) -> None:
        code = 1005 if self.handshake_complete else 1006
        self.queue.put_nowait({"type": "websocket.disconnect", "code": code})
        self.connections.remove(self)

        if self.logger.level <= TRACE_LOG_LEVEL:
            prefix = "%s:%d - " % self.client if self.client else ""
            self.logger.log(TRACE_LOG_LEVEL, "%sWebSocket connection lost", prefix)

        self.handshake_complete = True
        if exc is None:
            self.transport.close()

    def eof_received(self) -> None:
        pass

    def shutdown(self) -> None:
        if not self.transport.is_closing():
            if self.handshake_complete:
                self.queue.put_nowait({"type": "websocket.disconnect", "code": 1012})
                self.close_sent = True
                self.conn.send_close(1012)
                output = self.conn.data_to_send()
                self.transport.write(b"".join(output))
            elif not self.handshake_initiated:
                self.send_500_response()
                self.queue.put_nowait({"type": "websocket.disconnect", "code": 1006})
            self.transport.close()

    def data_received(self, data: bytes) -> None:
        self.conn.receive_data(data)
        parser_exc = self.conn.parser_exc
        if parser_exc is not None:
            self.handle_parser_exception()
            return
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
            self.transport.write(b"".join(output))
            self.transport.close()
            return

        headers = [
            (key.encode("ascii"), value.encode("ascii", errors="surrogateescape"))
            for key, value in event.headers.raw_items()
        ]
        raw_path, _, query_string = event.path.partition("?")
        self.scope: WebSocketScope = {
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
            "extensions": {"websocket.http.response": {}},
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
        self.transport.write(b"".join(output))

    def handle_close(self, event: Frame) -> None:
        if not self.close_sent and not self.transport.is_closing():
            disconnect_event: WebSocketDisconnectEvent = {
                "type": "websocket.disconnect",
                "code": self.conn.close_rcvd.code,  # type: ignore[union-attr]
                "reason": self.conn.close_rcvd.reason,  # type: ignore[union-attr]
            }
            self.queue.put_nowait(disconnect_event)
            output = self.conn.data_to_send()
            self.transport.write(b"".join(output))
            self.transport.close()

    def handle_parser_exception(self) -> None:
        disconnect_event: WebSocketDisconnectEvent = {
            "type": "websocket.disconnect",
            "code": self.conn.close_sent.code,  # type: ignore[union-attr]
            "reason": self.conn.close_sent.reason,  # type: ignore[union-attr]
        }
        self.queue.put_nowait(disconnect_event)
        output = self.conn.data_to_send()
        self.transport.write(b"".join(output))
        self.close_sent = True
        self.transport.close()

    def on_task_complete(self, task: asyncio.Task[None]) -> None:
        self.tasks.discard(task)

    async def run_asgi(self) -> None:
        try:
            result = await self.app(self.scope, self.receive, self.send)
        except ClientDisconnected:
            self.transport.close()
        except BaseException:
            self.logger.exception("Exception in ASGI application\n")
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
        if self.initial_response or self.handshake_complete:
            return
        response = self.conn.reject(500, "Internal Server Error")
        self.conn.send_response(response)
        output = self.conn.data_to_send()
        self.transport.write(b"".join(output))

    async def send(self, message: ASGISendEvent) -> None:
        await self.writable.wait()

        message_type = message["type"]

        if not self.handshake_complete and self.initial_response is None:
            if message_type == "websocket.accept":
                message = cast(WebSocketAcceptEvent, message)
                self.logger.info(
                    '%s - "WebSocket %s" [accepted]',
                    self.scope["client"],
                    get_path_with_query_string(self.scope),
                )
                headers = [
                    (name.decode("latin-1").lower(), value.decode("latin-1").lower())
                    for name, value in (self.default_headers + list(message.get("headers", [])))
                ]
                accepted_subprotocol = message.get("subprotocol")
                if accepted_subprotocol:
                    headers.append(("Sec-WebSocket-Protocol", accepted_subprotocol))
                self.response.headers.update(headers)

                if not self.transport.is_closing():
                    self.handshake_complete = True
                    self.conn.send_response(self.response)
                    output = self.conn.data_to_send()
                    self.transport.write(b"".join(output))

            elif message_type == "websocket.close":
                message = cast(WebSocketCloseEvent, message)
                self.queue.put_nowait({"type": "websocket.disconnect", "code": 1006})
                self.logger.info(
                    '%s - "WebSocket %s" 403',
                    self.scope["client"],
                    get_path_with_query_string(self.scope),
                )
                response = self.conn.reject(HTTPStatus.FORBIDDEN, "")
                self.conn.send_response(response)
                output = self.conn.data_to_send()
                self.close_sent = True
                self.handshake_complete = True
                self.transport.write(b"".join(output))
                self.transport.close()
            elif message_type == "websocket.http.response.start" and self.initial_response is None:
                message = cast(WebSocketResponseStartEvent, message)
                if not (100 <= message["status"] < 600):
                    raise RuntimeError("Invalid HTTP status code '%d' in response." % message["status"])
                self.logger.info(
                    '%s - "WebSocket %s" %d',
                    self.scope["client"],
                    get_path_with_query_string(self.scope),
                    message["status"],
                )
                headers = [
                    (name.decode("latin-1"), value.decode("latin-1"))
                    for name, value in list(message.get("headers", []))
                ]
                self.initial_response = (message["status"], headers, b"")
            else:
                msg = (
                    "Expected ASGI message 'websocket.accept', 'websocket.close' "
                    "or 'websocket.http.response.start' "
                    "but got '%s'."
                )
                raise RuntimeError(msg % message_type)

        elif not self.close_sent and self.initial_response is None:
            try:
                if message_type == "websocket.send":
                    message = cast(WebSocketSendEvent, message)
                    bytes_data = message.get("bytes")
                    text_data = message.get("text")
                    if text_data:
                        self.conn.send_text(text_data.encode())
                    elif bytes_data:
                        self.conn.send_binary(bytes_data)
                    output = self.conn.data_to_send()
                    self.transport.write(b"".join(output))

                elif message_type == "websocket.close" and not self.transport.is_closing():
                    message = cast(WebSocketCloseEvent, message)
                    code = message.get("code", 1000)
                    reason = message.get("reason", "") or ""
                    self.queue.put_nowait({"type": "websocket.disconnect", "code": code})
                    self.conn.send_close(code, reason)
                    output = self.conn.data_to_send()
                    self.transport.write(b"".join(output))
                    self.close_sent = True
                    self.transport.close()
                else:
                    msg = "Expected ASGI message 'websocket.send' or 'websocket.close'," " but got '%s'."
                    raise RuntimeError(msg % message_type)
            except InvalidState:
                raise ClientDisconnected()
        elif self.initial_response is not None:
            if message_type == "websocket.http.response.body":
                message = cast(WebSocketResponseBodyEvent, message)
                body = self.initial_response[2] + message["body"]
                self.initial_response = self.initial_response[:2] + (body,)
                if not message.get("more_body", False):
                    response = self.conn.reject(self.initial_response[0], body.decode())
                    response.headers.update(self.initial_response[1])
                    self.queue.put_nowait({"type": "websocket.disconnect", "code": 1006})
                    self.conn.send_response(response)
                    output = self.conn.data_to_send()
                    self.close_sent = True
                    self.transport.write(b"".join(output))
                    self.transport.close()
            else:
                msg = "Expected ASGI message 'websocket.http.response.body' " "but got '%s'."
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
