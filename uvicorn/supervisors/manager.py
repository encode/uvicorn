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
    def __call__(self, sockets: Optional[List[socket]] = None) -> None:
        ...


class ProcessManager:
    STARTUP_FAILED = 3

    def __init__(self, config: Config, target: Target, sockets: List[socket]) -> None:
        self.config = config
        self.target = target
        self.sockets = sockets
        self.processes: List[SpawnProcess] = []
        self.should_exit = multiprocessing.Event()

    def run(self) -> None:
        self.start()

        try:
            self.spawn_processes()

            while True:
                ...
        except Exception:
            ...

        self.shutdown()

    def start(self) -> None:
        self.pid = os.getpid()
        print(self.pid)

    def shutdown(self) -> None:
        for process in self.processes:
            process.terminate()
            process.join()

        for sock in self.sockets:
            sock.close()

    def spawn_processes(self):
        for _ in range(self.config.workers - len(self.processes)):
            self.spawn_process()
            # NOTE: Random delay is necessary?

    def spawn_process(self):
        process = get_subprocess(self.config, target=self.target, sockets=self.sockets)
        process.start()
        self.processes.append(process)
