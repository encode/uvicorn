from typing import Any, Dict, Optional

# We use the same state machine approach than `h11` because it's very convenient
# to program against.
#
# NOTE: Everything below is in the `h11` state machine docs:
# https://h11.readthedocs.io/en/latest/api.html#the-state-machine
# We describe the expected state machine to explicitly state the expected contract.
#
# Possible states
# ---------------
# IDLE
# SEND_RESPONSE
# SEND_BODY
# DONE
# MUST_CLOSE
# CLOSED
# ERROR
#
# Happy path
# ----------
# Client:
#     IDLE --(Request)-> SEND_BODY [--(Data)-> SEND_BODY] --(EndOfMessage)-> DONE
# Server:
#     IDLE --(Request)-> SEND_RESPONSE [--(InformationalResponse)-> SEND_RESPONSE] \
#         --(Response)-> SEND_BODY [--(Data)-> SEND_BODY] --(EndOfMessage)-> DONE
#
# Keep-Alive
# ----------
# ENABLED --(HTTP/1.0 | Connection: close)-> DISABLED
# Client + Server: DONE --(KeepAlive ENABLED)-> IDLE
#
# Closing paths
# -------------
# IDLE --(ConnectionClosed)-> CLOSED
# IDLE --(Peer CLOSED)-> MUST_CLOSE
# DONE --(KeepAlive DISABLED | Peer CLOSED | Peer ERROR)-> MUST_CLOSE
# MUST_CLOSE --(ConnectionClosed)-> CLOSED
# DONE --(ConnectionClosed)-> CLOSED
# CLOSED --(ConnectionClosed)-> CLOSED
#
# Error paths
# -----------
# * --> ERROR
# NOTE: this path is managed by `h11` internally. For other libraries, the ERROR state
# should be entered anytime the parser raises a parsing exception.

Event = Dict[str, Any]


class HTTP11Parser:
    """
    An event-based HTTP/1.1 parser interface, inspired by `h11`.
    """

    def states(self) -> dict:
        raise NotImplementedError  # pragma: no cover

    @property
    def they_are_waiting_for_100_continue(self) -> bool:
        raise NotImplementedError  # pragma: no cover

    def receive_data(self, data: bytes) -> None:
        raise NotImplementedError  # pragma: no cover

    def next_event(self) -> Event:
        raise NotImplementedError  # pragma: no cover

    def send(self, event: Event) -> Optional[bytes]:
        raise NotImplementedError  # pragma: no cover

    def start_next_cycle(self) -> None:
        raise NotImplementedError  # pragma: no cover
