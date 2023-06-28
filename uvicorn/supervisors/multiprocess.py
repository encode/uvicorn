import logging
import os
import signal
import time
import threading
from multiprocessing.context import SpawnProcess
from socket import socket
from types import FrameType
from typing import Callable, List, Optional

import click

from uvicorn._subprocess import get_subprocess
from uvicorn.config import Config

HANDLED_SIGNALS = (
    signal.SIGINT,  # Unix signal 2. Sent by Ctrl+C.
    signal.SIGTERM,  # Unix signal 15. Sent by `kill <pid>`.
)

logger = logging.getLogger("uvicorn.error")


class Multiprocess:
    def __init__(
        self,
        config: Config,
        target: Callable[[Optional[List[socket]]], None],
        sockets: List[socket],
    ) -> None:
        self.config = config
        self.target = target
        self.sockets = sockets
        self.processes: List[SpawnProcess] = []
        self.should_exit = threading.Event()
        self.pid = os.getpid()

    def signal_handler(self, sig: int, frame: Optional[FrameType]) -> None:
        """
        A signal handler that is registered with the parent process.
        """
        self.should_exit.set()

    def start_worker_process(self) -> None:
        process = get_subprocess(
            config=self.config, target=self.target, sockets=self.sockets
        )
        process.start()
        self.processes.append(process)

    def guard_check(self) -> None:
        while not self.should_exit.isSet():
            for item in self.processes:
                if item.is_alive():
                    continue
                else:
                    self.processes.remove(item)
                    logger.error(
                        f"Worker process is die [{item.pid}]. "
                        f"Will restart in {self.config.guard_check_time} second"
                    )

                    self.start_worker_process()
                    break

            time.sleep(self.config.guard_check_time)

    def run(self) -> None:
        self.startup()
        if self.config.guard:
            self.guard_check()
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

        for _idx in range(self.config.workers):
            self.start_worker_process()

    def shutdown(self) -> None:
        for process in self.processes:
            process.terminate()
            process.join()

        message = "Stopping parent process [{}]".format(str(self.pid))
        color_message = "Stopping parent process [{}]".format(
            click.style(str(self.pid), fg="cyan", bold=True)
        )
        logger.info(message, extra={"color_message": color_message})
