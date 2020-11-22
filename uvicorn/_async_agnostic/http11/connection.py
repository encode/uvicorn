import itertools
import logging
import time
from typing import Any, AsyncIterator, List, Optional, Tuple

from ..backends.auto import AutoBackend
from ..backends.base import AsyncSocket
from ..exceptions import BrokenSocket, ProtocolError
from ..utils import STATUS_PHRASES, find_upgrade_header, to_internet_date
from .parsers.base import Event, HTTP11Parser

TRACE_LOG_LEVEL = 5
NEXT_ID = itertools.count()


class HTTP11Connection:
    MAX_RECV = 2 ** 16

    def __init__(
        self,
        sock: AsyncSocket,
        default_headers: List[Tuple[bytes, bytes]],
        parser: HTTP11Parser,
    ) -> None:
        self._sock = sock
        self._default_headers = default_headers
        self._parser = parser

        self._obj_id = next(NEXT_ID)
        self._logger = logging.getLogger("uvicorn.error")
        self._backend = AutoBackend()

    def trace(self, msg: str, *args: Any) -> None:
        self._logger.log(TRACE_LOG_LEVEL, f"conn(%s): {msg}", self._obj_id, *args)

    def debug(self, msg: str, *args: Any) -> None:
        self._logger.debug(f"conn(%s): {msg}", self._obj_id, *args)

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
        return [
            (b"date", to_internet_date(time.time()).encode("utf-8")),
        ] + self._default_headers

    # State machine helpers

    def states(self) -> dict:
        return self._parser.states()

    async def _send_event(self, event: Event) -> None:
        if event["type"] == "Response":
            self.trace(
                "send_event event=Response("
                "status_code=%d, headers=<Headers(...)>, reason=%s)",
                event["status_code"],
                event["reason"],
            )
        elif event["type"] == "Data":
            self.trace("send_event event=Data(<%d bytes>)", len(event["data"]))
        elif event["type"] == "EndOfMessage":
            self.trace("send_event event=EndOfMessage(headers=<Headers(...)>")
        else:
            assert event["type"] == "ConnectionClosed"
            self.trace("send_event event=ConnectionClosed()")

        data = self._parser.send(event)
        if data is None:
            assert event["type"] == "ConnectionClosed", event
            await self._sock.write(b"")
            await self.shutdown_and_clean_up()
        else:
            await self._sock.write(data)

    async def _read_from_peer(self) -> None:
        if self._parser.they_are_waiting_for_100_continue:
            self.trace("Sending 100 Continue")
            await self._send_event({"type": "InformationalResponse"})

        data = await self._sock.read(self.MAX_RECV)
        self.trace("read_data Data(<%d bytes>)", len(data))
        self._parser.receive_data(data)

    async def _receive_event(self) -> Any:
        while True:
            try:
                event = self._parser.next_event()
            except ProtocolError as exc:
                raise ProtocolError(f"Invalid HTTP request received: {exc}")

            if event["type"] == "NEED_DATA":
                await self._read_from_peer()
                continue

            if event["type"] == "Request":
                self.trace(
                    "receive_event event=Request("
                    "http_version=%s, method=%s, target=%s, headers=...)",
                    event["http_version"],
                    event["method"],
                    event["target"],
                )
            elif event["type"] == "Data":
                self.trace("receive_event event=Data(<%d bytes>)", len(event["data"]))
            elif event["type"] == "EndOfMessage":
                self.trace("receive_event event=EndOfMessage(headers=<Headers(...)>")
            else:
                assert event["type"] == "ConnectionClosed"
                self.trace("receive_event event=ConnectionClosed()")

            return event

    async def read_request(
        self,
    ) -> Tuple[bytes, bytes, bytes, List[Tuple[bytes, bytes]], Optional[bytes]]:
        event = await self._receive_event()

        if event["type"] == "ConnectionClosed":
            raise BrokenSocket("Client has disconnected")

        assert event["type"] == "Request"

        http_version: bytes = event["http_version"]
        method: bytes = event["method"]
        path: bytes = event["target"]
        headers = [(key.lower(), value) for key, value in event["headers"]]
        upgrade = find_upgrade_header(headers)

        return (http_version, method, path, headers, upgrade)

    async def aiter_request_body(self) -> AsyncIterator[bytes]:
        async def receive_data() -> bytes:
            event = await self._receive_event()
            if event["type"] == "EndOfMessage":
                return b""
            assert event["type"] == "Data"
            return event["data"]

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
        event = {
            "type": "Response",
            "status_code": status_code,
            "headers": headers,
            "reason": reason,
        }
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
        await self._send_event({"type": "Data", "data": body})
        await self._send_event({"type": "EndOfMessage"})

    async def send_response_body(self, chunk: bytes) -> None:
        if chunk:
            event = {"type": "Data", "data": chunk}
        else:
            event = {"type": "EndOfMessage"}
        await self._send_event(event)

    def set_keepalive(self) -> None:
        try:
            self._parser.start_next_cycle()
        except ProtocolError:
            raise

    async def trigger_shutdown(self) -> None:
        self.trace("triggering shutdown")
        states = self._parser.states()
        if states["server"] in {"IDLE", "DONE"}:
            await self._send_event({"type": "ConnectionClosed"})

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
