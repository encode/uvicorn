from typing import Any, AsyncIterator, List, Optional, Tuple

import h11

from ..backends.auto import AutoBackend
from ..backends.base import AsyncSocket
from ..exceptions import BrokenSocket, ProtocolError
from ..utils import STATUS_PHRASES, find_upgrade_header
from .base import BaseHTTP11Connection


class H11Connection(BaseHTTP11Connection):
    """
    An HTTP/1.1 connection class backed by the `h11` library.
    """

    def __init__(
        self, sock: AsyncSocket, default_headers: List[Tuple[bytes, bytes]]
    ) -> None:
        super().__init__()
        self._sock = sock
        self._default_headers = default_headers
        self._h11_state = h11.Connection(h11.SERVER)
        self._backend = AutoBackend()

    @property
    def scheme(self) -> str:
        return "https" if self._sock.is_ssl else "http"

    @property
    def server(self) -> Optional[Tuple[str, int]]:
        return self._sock.get_local_addr()

    @property
    def client(self) -> Optional[Tuple[str, int]]:
        return self._sock.get_remote_addr()

    def basic_headers(self) -> List[Tuple[bytes, bytes]]:
        return super().basic_headers() + self._default_headers

    def states(self) -> dict:
        # IDLE -> ACTIVE -> (DONE | (MUST_CLOSE -> CLOSED) | ERROR) (-> IDLE)
        states_map = {
            h11.IDLE: "IDLE",
            h11.SEND_RESPONSE: "ACTIVE",
            h11.SEND_BODY: "ACTIVE",
            h11.DONE: "DONE",
            h11.MUST_CLOSE: "MUST_CLOSE",
            h11.CLOSED: "CLOSED",
            h11.ERROR: "ERROR",
        }
        return {
            "client": states_map[self._h11_state.their_state],
            "server": states_map[self._h11_state.our_state],
        }

    # h11 helpers.

    async def _send_event(self, event: Any) -> None:
        if isinstance(event, h11.Data):
            self.trace("send_event event=Data(<%d bytes>)", len(event.data))
        elif isinstance(event, h11.Response):
            self.trace(
                "send_event event=Response("
                "status_code=%d, headers=<Headers(...)>, http_version=%s, reason=%s)",
                event.status_code,
                event.http_version,
                event.reason,
            )
        elif isinstance(event, h11.EndOfMessage):
            self.trace("send_event event=EndOfMessage(headers=<Headers(...)>")
        else:
            self.trace("send_event event=%r", event)

        data = self._h11_state.send(event)
        if data is None:
            assert type(event) is h11.ConnectionClosed
            await self._sock.write(b"")
            await self.shutdown_and_clean_up()
        else:
            await self._sock.write(data)

    async def _read_from_peer(self) -> None:
        if self._h11_state.they_are_waiting_for_100_continue:
            self.trace("Sending 100 Continue")
            go_ahead = h11.InformationalResponse(
                status_code=100, headers=self.basic_headers()
            )
            await self._send_event(go_ahead)

        data = await self._sock.read(self.MAX_RECV)
        self.trace("read_data Data(<%d bytes>)", len(data))
        self._h11_state.receive_data(data)

    async def _receive_event(self) -> Any:
        while True:
            try:
                event = self._h11_state.next_event()
            except h11.RemoteProtocolError:
                raise ProtocolError("Invalid HTTP request received")

            if event is h11.NEED_DATA:
                await self._read_from_peer()
                continue

            if isinstance(event, h11.ConnectionClosed):
                self.trace("receive_event event=ConnectionClosed()")
            elif isinstance(event, h11.Request):
                self.trace(
                    "receive_event event=Request("
                    "http_version=%s, method=%s, target=%s, headers=...)",
                    event.http_version,
                    event.method,
                    event.target,
                )
            elif isinstance(event, h11.Data):
                self.trace("receive_event event=Data(<%d bytes>)", len(event.data))
            elif isinstance(event, h11.EndOfMessage):
                self.trace("receive_event event=EndOfMessage(headers=<Headers(...)>")
            else:
                self.trace("receive_event event=%r", event)

            return event

    async def read_request(
        self,
    ) -> Tuple[bytes, bytes, bytes, List[Tuple[bytes, bytes]], Optional[bytes]]:
        event = await self._receive_event()

        if isinstance(event, h11.ConnectionClosed):
            raise BrokenSocket("Client has disconnected")

        assert isinstance(event, h11.Request), type(event)

        http_version: bytes = event.http_version
        method: bytes = event.method
        path: bytes = event.target
        headers = [(key.lower(), value) for key, value in event.headers]
        upgrade = find_upgrade_header(headers)

        return (http_version, method, path, headers, upgrade)

    async def aiter_request_body(self) -> AsyncIterator[bytes]:
        async def receive_data() -> bytes:
            event = await self._receive_event()
            if isinstance(event, h11.EndOfMessage):
                return b""
            assert isinstance(event, h11.Data), type(event)
            return event.data

        async def request_body(data: bytes) -> AsyncIterator[bytes]:
            while data:
                yield data
                data = await receive_data()

        # Read at least one event so that we get a chance of seeing `EndOfMessage`
        # right away in case the client does not send a body (eg HEAD or GET requests).
        initial = await receive_data()

        return request_body(initial)

    async def send_response(
        self, status_code: int, headers: List[Tuple[bytes, bytes]], reason: bytes = b""
    ) -> None:
        if not reason:
            reason = STATUS_PHRASES[status_code]
        event = h11.Response(status_code=status_code, headers=headers, reason=reason)
        await self._send_event(event)

    async def send_simple_response(
        self, status_code: int, content_type: str, body: bytes
    ) -> None:
        self.trace("send_simple_response %d (%d bytes)", status_code, len(body))
        headers = self.basic_headers() + [
            (b"Content-Type", content_type.encode("utf-8")),
            (b"Content-Length", str(len(body)).encode("utf-8")),
        ]
        await self.send_response(status_code=status_code, headers=headers)
        await self._send_event(h11.Data(data=body))
        await self._send_event(h11.EndOfMessage())

    async def send_response_body(self, chunk: bytes) -> None:
        event = h11.Data(data=chunk) if chunk else h11.EndOfMessage()
        await self._send_event(event)

    def set_keepalive(self) -> None:
        try:
            self._h11_state.start_next_cycle()
        except h11.ProtocolError:
            raise ProtocolError(f"unexpected states: {self.states()}")

    async def trigger_shutdown(self) -> None:
        self.trace("triggering shutdown")
        if self._h11_state.our_state in {h11.IDLE, h11.DONE}:
            event = h11.ConnectionClosed()
            await self._send_event(event)

    async def shutdown_and_clean_up(self) -> None:
        self.trace("shutting down")

        try:
            await self._sock.send_eof()
        except BrokenSocket:
            self.trace("failed to send EOF: client is already gone")
            return

        self.trace("EOF sent")

        # Wait and read for a bit to give them a chance to see that we closed
        # things, but eventually give up and just close the socket.
        async def attempt_read_until_eof() -> None:
            try:
                while True:
                    data = await self._sock.read(self.MAX_RECV)
                    if not data:
                        self.trace("EOF acknowledged by peer")
                        break
            except Exception:
                pass  # It broke.

        try:
            await self._backend.move_on_after(5, attempt_read_until_eof)
        finally:
            await self._sock.aclose()
