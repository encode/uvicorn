from typing import Any, Optional

import h11

from ...exceptions import ProtocolError
from .base import HTTP11Parser, Event


H11_STATES_MAP = {
    h11.IDLE: "IDLE",
    h11.SEND_RESPONSE: "SEND_RESPONSE",
    h11.SEND_BODY: "SEND_BODY",
    h11.DONE: "DONE",
    h11.MUST_CLOSE: "MUST_CLOSE",
    h11.CLOSED: "CLOSED",
    h11.ERROR: "ERROR",
}


class H11Parser(HTTP11Parser):
    """
    An HTTP/1.1 parser backed by the `h11` library.
    """

    def __init__(self) -> None:
        self._h11_state = h11.Connection(h11.SERVER)

    def states(self) -> dict:
        return {
            "client": H11_STATES_MAP[self._h11_state.their_state],
            "server": H11_STATES_MAP[self._h11_state.our_state],
        }

    @property
    def they_are_waiting_for_100_continue(self) -> bool:
        return self._h11_state.they_are_waiting_for_100_continue

    def receive_data(self, data: bytes) -> None:
        self._h11_state.receive_data(data)

    def next_event(self) -> Event:
        event = self._h11_state.next_event()
        return from_h11_event(event)

    def send(self, event: Event) -> Optional[bytes]:
        h11_event = to_h11_event(event)
        return self._h11_state.send(h11_event)

    def start_next_cycle(self) -> None:
        try:
            self._h11_state.start_next_cycle()
        except h11.ProtocolError as exc:
            raise ProtocolError(exc)


def from_h11_event(event: Any) -> Event:
    if event is h11.NEED_DATA:
        return {"type": "NEED_DATA"}

    if isinstance(event, h11.Request):
        return {
            "type": "Request",
            "http_version": event.http_version,
            "method": event.method,
            "target": event.target,
            "headers": event.headers,
        }

    if isinstance(event, h11.ConnectionClosed):
        return {"type": "ConnectionClosed"}

    if isinstance(event, h11.Data):
        return {"type": "Data", "data": event.data}

    if isinstance(event, h11.EndOfMessage):
        return {"type": "EndOfMessage"}

    raise RuntimeError(f"Unknown event type: {type(event)}")


def to_h11_event(event: Event) -> Any:
    if event["type"] == "InformationalResponse":
        return h11.InformationalResponse(status_code=100)

    if event["type"] == "Response":
        return h11.Response(
            status_code=event["status_code"],
            headers=event["headers"],
            reason=event["reason"]
        )

    if event["type"] == "Data":
        return h11.Data(data=event["data"])

    if event["type"] == "EndOfMessage":
        return h11.EndOfMessage()

    assert event["type"] == "ConnectionClosed"
    return h11.ConnectionClosed()
