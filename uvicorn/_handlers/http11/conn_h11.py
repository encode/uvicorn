from typing import Any, Optional

import h11

from .conn_base import HTTPConnection, ProtocolError

# Simple mapping from h11 client/server states to states we're interested in.
H11_STATES_MAP = {
    h11.CLIENT: {
        h11.IDLE: "IDLE",
        h11.SEND_BODY: "RECV_BODY",
        h11.ERROR: "ERROR",
    },
    h11.SERVER: {
        h11.SEND_RESPONSE: "SEND_RESPONSE",
        h11.SEND_BODY: "SEND_BODY",
        h11.DONE: "DONE",
        h11.MUST_CLOSE: "MUST_CLOSE",
        h11.CLOSED: "CLOSED",
        h11.ERROR: "ERROR",
    },
}


class H11Connection(HTTPConnection):
    def __init__(self) -> None:
        self._conn = h11.Connection(h11.SERVER)

    @property
    def state(self) -> str:
        try:
            return H11_STATES_MAP[h11.CLIENT][self._conn.states[h11.CLIENT]]
        except KeyError:
            pass

        try:
            return H11_STATES_MAP[h11.SERVER][self._conn.states[h11.SERVER]]
        except KeyError:
            pass

        raise NotImplementedError(self._conn.states)

    @property
    def is_client_waiting_for_100_continue(self) -> bool:
        return self._conn.they_are_waiting_for_100_continue

    def receive_data(self, data: bytes) -> None:
        self._conn.receive_data(data)

    def next_event(self) -> dict:
        try:
            event = self._conn.next_event()
        except h11.RemoteProtocolError as exc:
            raise ProtocolError(exc)
        else:
            return from_h11_event(event)

    def send(self, event: dict) -> Optional[bytes]:
        h11_event = to_h11_event(event)
        return self._conn.send(h11_event)

    def start_next_cycle(self) -> None:
        try:
            self._conn.start_next_cycle()
        except h11.RemoteProtocolError as exc:
            raise ProtocolError(exc)


def to_h11_event(event: dict) -> Any:
    kwargs = {k: v for k, v in event.items() if k != "type"}
    return getattr(h11, event["type"])(**kwargs)


def from_h11_event(event: Any) -> dict:
    try:
        # Eg: h11.NEED_DATA
        event_type = event.__name__
    except AttributeError:
        # Eg: h11.Request
        event_type = event.__class__.__name__

    return {"type": event_type, **vars(event)}
