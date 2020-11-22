import re
from typing import Any, Dict, List, Optional, Tuple, Union

import httptools

from ...exceptions import ProtocolError
from .base import Event, HTTP11Parser

HEADER_RE = re.compile(b'[\x00-\x1F\x7F()<>@,;:[]={} \t\\"]')
HEADER_VALUE_RE = re.compile(b"[\x00-\x1F\x7F]")


class HttpToolsParser(HTTP11Parser):
    """
    An HTTP/1.1 parser backed by the `httptools` library.
    """

    def __init__(self) -> None:
        self._parser = httptools.HttpRequestParser(self)
        self._state = State()
        # Parser-specific state.
        self._parsed_url: Optional[Any] = None
        self._headers: List[Tuple[bytes, bytes]] = []
        self._chunked_encoding: Optional[bool] = None
        self._expected_content_length: Optional[int] = None

    # Parser API.

    def states(self) -> dict:
        return self._state.states()

    @property
    def they_are_waiting_for_100_continue(self) -> bool:
        return self._state.client_waiting_for_100_continue

    def receive_data(self, data: bytes) -> None:
        try:
            self._parser.feed_data(data)
        except (
            httptools.HttpParserInvalidMethodError,
            httptools.HttpParserInvalidURLError,
            httptools.HttpParserError,
        ) as exc:
            self._state.process_error("client")
            raise ProtocolError(exc)
        except (
            httptools.HttpParserInvalidStatusError,
            httptools.HttpParserCallbackError,
        ) as exc:
            self._state.process_error("server")
            raise ProtocolError(exc)

        if not data:
            self._state.process_client_event({"type": "ConnectionClosed"})

    def next_event(self) -> Event:
        return self._state.next_event()

    def send(self, event: Event) -> Optional[bytes]:
        self._state.process_server_event(event)

        if event["type"] == "InformationalResponse":
            return self._render_informational_response()

        if event["type"] == "Response":
            if self._parser.get_method() == b"HEAD":
                self._expected_content_length = 0
            status_code = event["status_code"]
            headers = event["headers"]
            reason = event["reason"]
            return self._render_response(status_code, headers, reason)

        if event["type"] == "Data":
            body = event["data"]
            return self._render_response_body(body)

        if event["type"] == "EndOfMessage":
            num_bytes_remaining = self._expected_content_length or 0
            if num_bytes_remaining != 0:
                raise ProtocolError(
                    "Too little data for declared Content-Length: "
                    f"{num_bytes_remaining} remaining"
                )
            return b""

        assert event["type"] == "ConnectionClosed"
        return None

    def start_next_cycle(self) -> None:
        try:
            self._state.start_next_cycle()
        except ProtocolError:
            raise

        # Reset.
        self._parsed_url = None
        self._headers.clear()
        self._chunked_encoding = None
        self._expected_content_length = None

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
            if name == b"content-length" and self._chunked_encoding is None:
                self._expected_content_length = int(value.decode("ascii"))
                self._chunked_encoding = False
            elif name == b"transfer-encoding" and value.lower() == b"chunked":
                self._expected_content_length = 0
                self._chunked_encoding = True
            elif name == b"connection" and value.lower() == b"close":
                self._state.process_keep_alive_disabled()
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

    def _render_response_body(self, body: bytes) -> bytes:
        if self._chunked_encoding:
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
            self._state.process_keep_alive_disabled()

    def on_url(self, url: str) -> None:
        assert self._parsed_url is None
        self._parsed_url = httptools.parse_url(url)

    def on_header(self, name: bytes, value: bytes) -> None:
        name = name.lower()
        if name == b"expect" and value.lower() == b"100-continue":
            self._state.process_expect_100_continue()
        if name == b"connection" and value.lower() == b"close":
            self._state.process_keep_alive_disabled()
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

        self._state.process_client_event(event)

    def on_body(self, body: bytes) -> None:
        event = {"type": "Data", "data": body}
        self._state.process_client_event(event)

    def on_message_complete(self) -> None:
        event = {"type": "EndOfMessage"}
        self._state.process_client_event(event)


# Code below is adapted from h11's state machine code.

EVENT_TRIGGERED_TRANSITIONS: Dict[
    str, Dict[str, Dict[Union[str, Tuple[str, str]], str]]
] = {
    # Role -> State -> Event -> New state
    "client": {
        "IDLE": {"Request": "SEND_BODY", "ConnectionClosed": "CLOSED"},
        "SEND_BODY": {"Data": "SEND_BODY", "EndOfMessage": "DONE"},
        "DONE": {"ConnectionClosed": "CLOSED"},
        "MUST_CLOSE": {"ConnectionClosed": "CLOSED"},
        "CLOSED": {"ConnectionClosed": "CLOSED"},
        "ERROR": {},
    },
    "server": {
        "IDLE": {
            "ConnectionClosed": "CLOSED",
            "Response": "SEND_BODY",
            # Special case: server sees client Request events.
            ("Request", "client"): "SEND_RESPONSE",
        },
        "SEND_RESPONSE": {
            "InformationalResponse": "SEND_RESPONSE",
            "Response": "SEND_BODY",
        },
        "SEND_BODY": {"Data": "SEND_BODY", "EndOfMessage": "DONE"},
        "DONE": {"ConnectionClosed": "CLOSED"},
        "MUST_CLOSE": {"ConnectionClosed": "CLOSED"},
        "CLOSED": {"ConnectionClosed": "CLOSED"},
        "ERROR": {},
    },
}

STATE_TRIGGERED_TRANSITIONS: Dict[Tuple[str, str], Dict[str, str]] = {
    # (Client state, Server state) -> New states
    # Socket shutdown
    ("CLOSED", "DONE"): {"server": "MUST_CLOSE"},
    ("CLOSED", "IDLE"): {"server": "MUST_CLOSE"},
    ("ERROR", "DONE"): {"server": "MUST_CLOSE"},
    ("DONE", "CLOSED"): {"client": "MUST_CLOSE"},
    ("IDLE", "CLOSED"): {"client": "MUST_CLOSE"},
    ("DONE", "ERROR"): {"clientt": "MUST_CLOSE"},
}


class State:
    def __init__(self) -> None:
        self._states = {"client": "IDLE", "server": "IDLE"}
        self._client_events: List[Event] = []
        self._keep_alive_enabled = True
        self._expect_100_continue = False

    @property
    def client_waiting_for_100_continue(self) -> bool:
        return self._expect_100_continue

    def states(self) -> dict:
        return dict(self._states)

    def _process_event(self, role: str, event: Event) -> None:
        self._fire_event_triggered_transitions(role, event["type"])
        if event["type"] == "Request":
            # Special case: the server state does get to see Request events.
            self._fire_event_triggered_transitions("server", ("Request", "client"))
        self._fire_state_triggered_transitions()

    def process_client_event(self, event: Event) -> None:
        self._process_event("client", event)
        self._client_events.append(event)

    def process_server_event(self, event: Event) -> None:
        self._process_event("server", event)

    def process_keep_alive_disabled(self) -> None:
        self._keep_alive_enabled = False

    def process_expect_100_continue(self) -> None:
        assert not self._expect_100_continue
        self._expect_100_continue = True

    def process_error(self, role: str) -> None:
        self._states[role] = "ERROR"
        self._fire_state_triggered_transitions()  # Peer may have to close.

    def _fire_event_triggered_transitions(
        self, role: str, event_type: Union[str, Tuple[str, str]]
    ) -> None:
        state = self._states[role]

        try:
            new_state = EVENT_TRIGGERED_TRANSITIONS[role][state][event_type]
        except KeyError:
            raise ProtocolError(
                f"can't handle event type {event_type} when "
                f"role={role.upper()} and state={state}"
            )

        self._states[role] = new_state

        if role == "server" and event_type in {"Response", "InformationalResponse"}:
            self._expect_100_continue = False

    def _fire_state_triggered_transitions(self) -> None:
        # Apply transitions until we converge to a fixed point.
        while True:
            states = dict(self._states)

            if not self._keep_alive_enabled:
                for role in ("client", "server"):
                    if self._states[role] == "DONE":
                        self._states[role] = "MUST_CLOSE"

            joint_state = (self._states["client"], self._states["server"])
            changes = STATE_TRIGGERED_TRANSITIONS.get(joint_state, {})
            self._states.update(changes)

            if self._states == states:
                break

    def next_event(self) -> Event:
        if self._states["client"] == "ERROR":
            raise ProtocolError("Can't receive data when peer state is ERROR")

        if self._states["client"] == "CLOSED":
            return {"type": "ConnectionClosed"}

        try:
            return self._client_events.pop(0)
        except IndexError:
            return {"type": "NEED_DATA"}

    def start_next_cycle(self) -> None:
        if self._states != {"client": "DONE", "server": "DONE"}:
            raise ProtocolError(f"Not in a reusable state: {self._states}")

        assert self._keep_alive_enabled
        assert not self._expect_100_continue
        # Reset.
        self._states = {"client": "IDLE", "server": "IDLE"}
        self._keep_alive_enabled = True
        self._client_events.clear()
