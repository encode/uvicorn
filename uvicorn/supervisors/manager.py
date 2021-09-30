import logging
import multiprocessing
import os
import signal
from multiprocessing.context import SpawnProcess
from socket import socket
from types import FrameType
from typing import Callable, List, Optional, Protocol

from uvicorn.config import Config
from uvicorn.subprocess import get_subprocess

HANDLED_SIGNALS = (
    signal.SIGINT,  # Unix signal 2. Sent by Ctrl+C.
    signal.SIGTERM,  # Unix signal 15. Sent by `kill <pid>`.
)

logger = logging.getLogger("uvicorn.error")


class Target(Protocol):
    def __call__(self, sockets: Optional[List[socket.socket]] = None) -> None:
        ...


class ProcessManager:
    def __init__(self, config: Config, target: Target, sockets: List[socket]) -> None:
        self.config = config
        self.target = target
        self.sockets = sockets
        self.processes: List[SpawnProcess] = []
        self.should_exit = multiprocessing.Event()

    def run(self) -> None:
        self.start()

    def start(self) -> None:
        self.pid = os.getpid()
