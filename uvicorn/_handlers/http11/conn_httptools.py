import logging
import re
from typing import Any, List, Optional, Tuple

import httptools

from .conn_base import HTTPConnection, ProtocolError

HEADER_RE = re.compile(b'[\x00-\x1F\x7F()<>@,;:[]={} \t\\"]')
HEADER_VALUE_RE = re.compile(b"[\x00-\x1F\x7F]")


class HttpToolsConnection(HTTPConnection):
    def __init__(self) -> None:
        self._parser = httptools.HttpRequestParser(self)
        self._logger = logging.getLogger("uvicorn.error")

        self._parsed_url: Optional[Any] = None
        self._headers: List[Tuple[bytes, bytes]] = []
        self._expected_content_length: Optional[int] = None
        self._is_chunked_encoding: Optional[bool] = None
        self._is_client_waiting_for_100_continue = False
        self._is_keep_alive_enabled = True
        # Happy path: IDLE, RECV_BODY, SEND_RESPONSE, SEND_BODY, DONE
        # Other cases: MUST_CLOSE, CLOSED, ERROR
        self._state = "IDLE"
        self._client_events: List[dict] = []

    # Parser API.

    @property
    def state(self) -> str:
        return self._state

    @property
    def is_client_waiting_for_100_continue(self) -> bool:
        return self._is_client_waiting_for_100_continue

    def receive_data(self, data: bytes) -> None:
        try:
            self._parser.feed_data(data)
        except httptools.HttpParserError as exc:
            self._state = "ERROR"
            raise ProtocolError(exc)

        if not data:
            self._state = "CLOSED"

    def next_event(self) -> dict:
        if self._state == "ERROR":
            raise ProtocolError("Can't receive data when peer state is ERROR")

        if self._state == "CLOSED":
            return {"type": "ConnectionClosed"}

        try:
            return self._client_events.pop(0)
        except IndexError:
            return {"type": "NEED_DATA"}

    def send(self, event: dict) -> Optional[bytes]:
        if event["type"] == "InformationalResponse":
            assert self._state == "SEND_RESPONSE"
            content = self._render_informational_response()
            self._is_client_waiting_for_100_continue = False
            return content

        if event["type"] == "Response":
            assert self._state == "SEND_RESPONSE"
            if self._parser.get_method() == b"HEAD":
                self._expected_content_length = 0
            status_code = event["status_code"]
            headers = event["headers"]
            reason = event["reason"]
            self._state = "SEND_BODY"
            return self._render_response(status_code, headers, reason)

        if event["type"] == "Data":
            assert self._state == "SEND_BODY"
            body = event["data"]
            return self._render_response_body(body)

        if event["type"] == "EndOfMessage":
            assert self._state in {"SEND_RESPONSE", "SEND_BODY"}
            if self._is_keep_alive_enabled:
                self._state = "DONE"
            else:
                self._state = "MUST_CLOSE"
            num_bytes_remaining = self._expected_content_length or 0
            if num_bytes_remaining != 0:
                raise ProtocolError(
                    "Too little data for declared Content-Length: "
                    f"{num_bytes_remaining} remaining"
                )
            return b""

        if event["type"] == "ConnectionClosed":
            self._state = "CLOSED"
            return None

        raise NotImplementedError(event["type"])  # pragma: no cover

    def start_next_cycle(self) -> None:
        if self._state != "DONE":
            raise ProtocolError()

        assert self._is_keep_alive_enabled
        assert not self._is_client_waiting_for_100_continue

        # Reset.
        self._state = "IDLE"
        self._headers.clear()
        self._parsed_url = None
        self._expected_content_length = None
        self._is_chunked_encoding = None
        self._is_client_waiting_for_100_continue = False
        self._is_keep_alive_enabled = True
        self._client_events.clear()

    # Response rendering helpers.

    def _render_informational_response(self) -> bytes:
        return b"HTTP/1.1 100 Continue\r\n\r\n"

    def _render_response(
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
            if name == b"content-length" and self._is_chunked_encoding is None:
                self._expected_content_length = int(value.decode("ascii"))
                self._is_chunked_encoding = False
            elif name == b"transfer-encoding" and value.lower() == b"chunked":
                self._expected_content_length = 0
                self._is_chunked_encoding = True
            elif name == b"connection" and value.lower() == b"close":
                self._is_keep_alive_enabled = False
            content.extend([name, b": ", value, b"\r\n"])

        if (
            self._is_chunked_encoding is None
            and self._parser.get_method() != b"HEAD"
            and status_code not in (204, 304)
        ):
            # Neither content-length nor transfer-encoding specified
            self._is_chunked_encoding = True
            content.append(b"transfer-encoding: chunked\r\n")

        content.append(b"\r\n")

        if self._is_chunked_encoding:
            content.append(b"0\r\n\r\n")

        return b"".join(content)

    def _render_response_body(self, body: bytes) -> bytes:
        if self._is_chunked_encoding:
            content = [b"%x\r\n" % len(body), body, b"\r\n"] if body else []
            content.append(b"0\r\n\r\n")
            return b"".join(content)

        assert self._expected_content_length is not None
        if len(body) > self._expected_content_length:
            raise RuntimeError("Response content longer than Content-Length")
        self._expected_content_length -= len(body)

        return body

    # HttpTools callbacks.

    def on_message_begin(self) -> None:
        if self._parser.get_http_version() == "1.0":
            self._is_keep_alive_enabled = False

    def on_url(self, url: str) -> None:
        assert self._parsed_url is None
        self._parsed_url = httptools.parse_url(url)

    def on_header(self, name: bytes, value: bytes) -> None:
        name = name.lower()
        if name == b"expect" and value.lower() == b"100-continue":
            self._is_client_waiting_for_100_continue = True
        if name == b"connection" and value.lower() == b"close":
            self._is_keep_alive_enabled = False
        self._headers.append((name, value))

    def on_headers_complete(self) -> None:
        assert self._parsed_url is not None

        target = self._parsed_url.path
        if self._parsed_url.query:
            target += b"?%s" % self._parsed_url.query

        event = {
            "type": "Request",
            "http_version": self._parser.get_http_version().encode("ascii"),
            "method": self._parser.get_method(),
            "target": target,
            "headers": self._headers,
        }

        self._client_events.append(event)
        self._state = "RECV_BODY"

    def on_body(self, body: bytes) -> None:
        assert self._state == "RECV_BODY"
        event = {"type": "Data", "data": body}
        self._client_events.append(event)

    def on_message_complete(self) -> None:
        assert self._state == "RECV_BODY"
        self._client_events.append({"type": "EndOfMessage"})
        self._state = "SEND_RESPONSE"
