from typing import Any, List, Set, Tuple


class ServerState:
    def __init__(self) -> None:
        self.default_headers: List[Tuple[bytes, bytes]] = []  # Set by the server.
        self.total_requests = 0  # Updated by server handlers.
        self.connections: Set[Any] = set()
        self.tasks: Set[Any] = set()  # May be used by async backends (not all do).
