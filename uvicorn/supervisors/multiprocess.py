import logging
import os
import signal
import socket
import threading
from multiprocessing.context import SpawnProcess
from types import FrameType
from typing import Callable, List, Optional

import click

from uvicorn import Config
from uvicorn.subprocess import get_subprocess, shutdown_subprocess

HANDLED_SIGNALS = (
    signal.SIGINT,  # Unix signal 2. Sent by Ctrl+C.
    signal.SIGTERM,  # Unix signal 15. Sent by `kill <pid>`.
)

logger = logging.getLogger("uvicorn.error")


class Multiprocess:
    def __init__(
        self, config: Config, target: Callable, sockets: Optional[List[socket.socket]]
    ):
        self.config = config
        self.target = target
        self.sockets = sockets
        self.processes: List[SpawnProcess] = []
        self.should_exit = threading.Event()
        self.pid = os.getpid()

    def signal_handler(self, sig: int, frame: FrameType) -> None:
        """
        A signal handler that is registered with the parent process.
        """

        for process in self.processes:
            try:
                assert process.pid
                shutdown_subprocess(process.pid)
            except Exception as exc:
                logger.error(f"Could not stop child process {process.pid}: {exc}")

        self.should_exit.set()

    def run(self) -> None:
        self.startup()
        self.should_exit.wait()
        self.shutdown()

    def startup(self) -> None:
        message = "Started parent process [{}]".format(str(self.pid))
        color_message = "Started parent process [{}]".format(
            click.style(str(self.pid), fg="cyan", bold=True)
        )
        logger.info(message, extra={"color_message": color_message})

        for sig in HANDLED_SIGNALS:
            signal.signal(sig, self.signal_handler)

        for idx in range(self.config.workers):
            process = get_subprocess(
                config=self.config, target=self.target, sockets=self.sockets
            )
            process.start()
            self.processes.append(process)

    def shutdown(self) -> None:
        for process in self.processes:
            process.join()

        message = "Stopping parent process [{}]".format(str(self.pid))
        color_message = "Stopping parent process [{}]".format(
            click.style(str(self.pid), fg="cyan", bold=True)
        )
        logger.info(message, extra={"color_message": color_message})
