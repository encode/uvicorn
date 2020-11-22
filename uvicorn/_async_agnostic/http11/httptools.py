import re
from typing import Any, AsyncIterator, List, Optional, Tuple

import httptools

from ..backends.auto import AutoBackend
from ..backends.base import AsyncSocket
from ..exceptions import BrokenSocket, ProtocolError
from ..utils import STATUS_PHRASES, find_upgrade_header
from .base import BaseHttp11Connection

HEADER_RE = re.compile(b'[\x00-\x1F\x7F()<>@,;:[]={} \t\\"]')
HEADER_VALUE_RE = re.compile(b"[\x00-\x1F\x7F]")


class HttpToolsProtocol:
    def __init__(self) -> None:
        self._parser = httptools.HttpRequestParser(self)
        self._parsed_url: Optional[Any] = None
        self._headers: List[Tuple[bytes, bytes]] = []
        self._states = {"server": "IDLE", "client": "IDLE"}
        self._expect_100_continue = False
        self._chunked_encoding: Optional[bool] = None
        self._expected_content_length: Optional[int] = None
        self._allow_keep_alive = True
        self._events: List[dict] = []

    # Custom API.

    def states(self) -> dict:
        return dict(self._states)

    @property
    def they_are_waiting_for_100_continue(self) -> bool:
        return self._expect_100_continue

    def receive_data(self, data: bytes) -> None:
        try:
            self._parser.feed_data(data)
        except (
            httptools.HttpParserInvalidMethodError,
            httptools.HttpParserInvalidURLError,
            httptools.HttpParserError,
        ) as exc:
            self._states["client"] = "ERROR"
            self._states["server"] = "MUST_CLOSE"
            raise ProtocolError(exc)
        except (
            httptools.HttpParserInvalidStatusError,
            httptools.HttpParserCallbackError,
        ) as exc:
            self._states["client"] = "MUST_CLOSE"
            self._states["server"] = "ERROR"
            raise ProtocolError(exc)

        if not data:
            assert self._states["client"] in {"IDLE", "DONE", "MUST_CLOSE", "CLOSED"}
            self._states["client"] = "CLOSED"
            self._states["server"] = "MUST_CLOSE"

    def next_event(self) -> dict:
        if self._states["client"] == "ERROR":
            raise ProtocolError("Can't receive data when peer state is ERROR")

        if self._events:
            return self._events.pop(0)

        if self._states["client"] == "CLOSED":
            return {"type": "CONNECTION_CLOSED"}

        return {"type": "NEED_DATA"}

    def _get_informational_response_content(self) -> bytes:
        return b"HTTP/1.1 100 Continue\r\n\r\n"

    def _get_response_content(
        self, status_code: int, headers: List[Tuple[bytes, bytes]], reason: bytes
    ) -> bytes:
        status_line = b"".join(
            [b"HTTP/1.1", b" ", str(status_code).encode("utf-8"), b" ", reason, b"\r\n"]
        )

        content = [status_line]

        for name, value in headers:
            if HEADER_RE.search(name):
                raise RuntimeError("Invalid HTTP header name")
            if HEADER_VALUE_RE.search(value):
                raise RuntimeError("Invalid HTTP header value")

            name = name.lower()
            if name == b"content-length" and self._chunked_encoding is None:
                self._expected_content_length = int(value.decode("ascii"))
                self._chunked_encoding = False
            elif name == b"transfer-encoding" and value.lower() == b"chunked":
                self._expected_content_length = 0
                self._chunked_encoding = True
            elif name == b"connection" and value.lower() == b"close":
                self._allow_keep_alive = False
            content.extend([name, b": ", value, b"\r\n"])

        if (
            self._chunked_encoding is None
            and self._parser.get_method() != b"HEAD"
            and status_code not in (204, 304)
        ):
            # Neither content-length nor transfer-encoding specified
            self._chunked_encoding = True
            content.append(b"transfer-encoding: chunked\r\n")

        content.append(b"\r\n")

        if self._chunked_encoding:
            content.append(b"0\r\n\r\n")

        return b"".join(content)

    def _get_response_body_content(self, body: bytes) -> bytes:
        if self._chunked_encoding:
            content = [b"%x\r\n" % len(body), body, b"\r\n"] if body else []
            content.append(b"0\r\n\r\n")
            return b"".join(content)

        assert self._expected_content_length is not None
        if len(body) > self._expected_content_length:
            raise RuntimeError("Response content longer than Content-Length")
        self._expected_content_length -= len(body)

        return body

    def send(self, event: dict) -> Optional[bytes]:
        if event["type"] == "INFORMATIONAL_RESPONSE":
            assert self._states["server"] == "SEND_RESPONSE"
            content = self._get_informational_response_content()
            self._expect_100_continue = False
            return content

        if event["type"] == "RESPONSE":
            assert self._states["server"] == "SEND_RESPONSE"
            self._expect_100_continue = False
            if self._parser.get_method() == b"HEAD":
                self._expected_content_length = 0
            status_code = event["status_code"]
            headers = event["headers"]
            reason = event["reason"]
            content = self._get_response_content(status_code, headers, reason)
            self._states["server"] = "SEND_BODY"
            return content

        if event["type"] == "DATA":
            assert self._states["server"] == "SEND_BODY"
            body = event["data"]
            return self._get_response_body_content(body)

        if event["type"] == "END_OF_MESSAGE":
            assert self._states["server"] == "SEND_BODY"
            if (
                self._expected_content_length is not None
                and self._expected_content_length != 0
            ):
                raise ProtocolError(
                    "Too little data for declared Content-Length: "
                    f"{self._expected_content_length} remaining"
                )
            self._states["server"] = "DONE"
            if not self._allow_keep_alive:
                self._states["server"] = "MUST_CLOSE"
            return b""

        if event["type"] == "CONNECTION_CLOSED":
            assert self._states["server"] in {"IDLE", "MUST_CLOSE", "DONE", "CLOSED"}
            self._states["server"] = "CLOSED"
            self._states["client"] = "MUST_CLOSE"
            return None

        raise RuntimeError(f"Unknown event type: {event['type']}")

    def start_next_cycle(self) -> None:
        if self._states["client"] == "DONE" and self._states["server"] == "DONE":
            assert self._allow_keep_alive
            assert not self._expect_100_continue
            self._parsed_url = None
            self._headers = []
            self._states["client"] = "IDLE"
            self._states["server"] = "IDLE"
            self._expect_100_continue = False
            self._chunked_encoding = None
            self._expected_content_length = None
            self._allow_keep_alive = True
            self._events = []
        else:
            raise ProtocolError("Not allowed to start new cycle")

    # HttpTools callbacks.

    def on_message_begin(self) -> None:
        assert self._states["client"] == "IDLE"
        assert self._states["server"] == "IDLE"
        if self._parser.get_http_version() == "1.0":
            self._allow_keep_alive = False

    def on_url(self, url: str) -> None:
        assert self._parsed_url is None
        assert self._states["client"] == "IDLE", self._states
        assert self._states["server"] == "IDLE"
        self._parsed_url = httptools.parse_url(url)

    def on_header(self, name: bytes, value: bytes) -> None:
        assert self._states["client"] == "IDLE"
        assert self._states["server"] == "IDLE"
        name = name.lower()
        if name == b"expect" and value.lower() == b"100-continue":
            self._expect_100_continue = True
        if name == b"connection" and value.lower() == b"close":
            self._allow_keep_alive = False
        self._headers.append((name, value))

    def on_headers_complete(self) -> None:
        assert self._states["client"] == "IDLE"
        assert self._states["server"] == "IDLE"
        assert self._parsed_url is not None

        target = self._parsed_url.path
        if self._parsed_url.query:
            target += b"?%s" % self._parsed_url.query

        request = {
            "type": "REQUEST",
            "http_version": self._parser.get_http_version(),
            "method": self._parser.get_method(),
            "target": target,
            "headers": self._headers,
        }
        self._events.append(request)

        self._states["client"] = "SEND_BODY"

    def on_body(self, body: bytes) -> None:
        assert self._states["client"] == "SEND_BODY"
        assert self._states["server"] == "IDLE"
        self._events.append({"type": "DATA", "data": body})

    def on_message_complete(self) -> None:
        assert self._states["client"] == "SEND_BODY"
        assert self._states["server"] == "IDLE"

        self._events.append({"type": "END_OF_MESSAGE"})

        self._states["client"] = "DONE"
        if not self._allow_keep_alive:
            self._states["client"] = "MUST_CLOSE"
        self._states["server"] = "SEND_RESPONSE"


class HttpToolsHttp11Connection(BaseHttp11Connection):
    """
    An HTTP/1.1 connection class backed by the `httptools` library.
    """

    def __init__(
        self, sock: AsyncSocket, default_headers: List[Tuple[bytes, bytes]]
    ) -> None:
        super().__init__()
        self._sock = sock
        self._default_headers = default_headers
        self._protocol = HttpToolsProtocol()
        self._backend = AutoBackend()

    # END parser callbacks

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
        return self._protocol.states()

    # h11 helpers.

    async def _send_event(self, event: dict) -> None:
        if event["type"] == "DATA":
            self.trace("send_event event=Data(<%d bytes>)", len(event["data"]))
        elif event["type"] == "RESPONSE":
            self.trace(
                "send_event event=Response("
                "status_code=%d, headers=<Headers(...)>, http_version=%s, reason=%s)",
                event["status_code"],
                event["http_version"],
                event["reason"],
            )
        elif event["type"] == "END_OF_MESSAGE":
            self.trace("send_event event=EndOfMessage(headers=<Headers(...)>")
        elif event["type"] == "CONNECTION_CLOSED":
            self.trace("send_event event=ConnectionClosed()")
        else:
            self.trace("send_event event=%r", {"type": event["type"]})

        data = self._protocol.send(event)
        if data is None:
            assert event["type"] == "CONNECTION_CLOSED"
            await self._sock.write(b"")
            await self.shutdown_and_clean_up()
        else:
            await self._sock.write(data)

    async def _read_from_peer(self) -> None:
        if self._protocol.they_are_waiting_for_100_continue:
            self.trace("Sending 100 Continue")
            await self._send_event({"type": "INFORMATIONAL_RESPONSE"})

        data = await self._sock.read(self.MAX_RECV)
        self.trace("read_data Data(<%d bytes>)", len(data))
        self._protocol.receive_data(data)

    async def _receive_event(self) -> Any:
        while True:
            try:
                event = self._protocol.next_event()
            except httptools.HttpParserError:
                raise ProtocolError("Invalid HTTP request received")

            if event["type"] == "NEED_DATA":
                await self._read_from_peer()
                continue

            if event["type"] == "CONNECTION_CLOSED":
                self.trace("receive_event event=ConnectionClosed()")
            elif event["type"] == "REQUEST":
                self.trace(
                    "receive_event event=Request("
                    "http_version=%s, method=%s, target=%s, headers=...)",
                    event["http_version"],
                    event["method"],
                    event["target"],
                )
            elif event["type"] == "DATA":
                self.trace("receive_event event=Data(<%d bytes>)", len(event["data"]))
            elif event["type"] == "END_OF_MESSAGE":
                self.trace("receive_event event=EndOfMessage(headers=<Headers(...)>")
            else:
                self.trace("receive_event event=%r", {"type": event["type"]})

            return event

    async def read_request(
        self,
    ) -> Tuple[bytes, bytes, bytes, List[Tuple[bytes, bytes]], Optional[bytes]]:
        event = await self._receive_event()

        if event["type"] == "CONNECTION_CLOSED":
            raise BrokenSocket("Client has disconnected")

        assert event["type"] == "REQUEST", event["type"]

        http_version: bytes = event["http_version"].encode("ascii")
        method: bytes = event["method"]
        path: bytes = event["target"]
        headers = [(key.lower(), value) for key, value in event["headers"]]
        upgrade = find_upgrade_header(headers)

        return (http_version, method, path, headers, upgrade)

    async def aiter_request_body(self) -> AsyncIterator[bytes]:
        async def receive_data() -> bytes:
            event = await self._receive_event()
            if event["type"] == "END_OF_MESSAGE":
                return b""
            assert event["type"] == "DATA", event["type"]
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
            "type": "RESPONSE",
            "http_version": "HTTP/1.1",
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
        await self._send_event({"type": "DATA", "data": body})
        await self._send_event({"type": "END_OF_MESSAGE"})

    async def send_response_body(self, chunk: bytes) -> None:
        event = {"type": "DATA", "data": chunk} if chunk else {"type": "END_OF_MESSAGE"}
        await self._send_event(event)

    def set_keepalive(self) -> None:
        try:
            self._protocol.start_next_cycle()
        except ProtocolError:
            raise ProtocolError(f"unexpected states: {self.states()}")

    async def trigger_shutdown(self) -> None:
        self.trace("triggering shutdown")
        states = self.states()
        if states["server"] in {"IDLE", "DONE"}:
            await self._send_event({"type": "CONNECTION_CLOSED"})

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
