from typing import Optional


class ProtocolError(Exception):
    pass


class HTTPConnection:
    @property
    def state(self) -> str:
        raise NotImplementedError  # pragma: no cover

    @property
    def is_client_waiting_for_100_continue(self) -> bool:
        raise NotImplementedError  # pragma: no cover

    def receive_data(self, data: bytes) -> None:
        raise NotImplementedError  # pragma: no cover

    def next_event(self) -> dict:
        raise NotImplementedError  # pragma: no cover

    def send(self, event: dict) -> Optional[bytes]:
        raise NotImplementedError  # pragma: no cover

    def start_next_cycle(self) -> None:
        raise NotImplementedError  # pragma: no cover
