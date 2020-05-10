import logging
import os
import signal
import threading

import click

from uvicorn.subprocess import get_subprocess

HANDLED_SIGNALS = (
    signal.SIGINT,  # Unix signal 2. Sent by Ctrl+C.
    signal.SIGTERM,  # Unix signal 15. Sent by `kill <pid>`.
)

logger = logging.getLogger("uvicorn.error")


class Multiprocess:
    def __init__(self, config, target, sockets):
        self.config = config
        self.target = target
        self.sockets = sockets
        self.processes = []
        self.should_exit = threading.Event()
        self.pid = os.getpid()

    def handle_int(self, sig, frame):
        logger.debug(sig)
        self.should_exit.set()

    def handle_term(self, sig, frame):
        logger.debug(sig)
        for process in self.processes:
            process.terminate()
        self.should_exit.set()

    def run(self):
        self.startup()
        self.should_exit.wait()
        self.shutdown()

    def startup(self):
        message = "Started parent process [{}]".format(str(self.pid))
        color_message = "Started parent process [{}]".format(
            click.style(str(self.pid), fg="cyan", bold=True)
        )
        logger.info(message, extra={"color_message": color_message})

        signal.signal(signal.SIGINT, self.handle_int)
        signal.signal(signal.SIGTERM, self.handle_term)

        for idx in range(self.config.workers):
            process = get_subprocess(
                config=self.config, target=self.target, sockets=self.sockets
            )
            process.start()
            self.processes.append(process)

    def shutdown(self):
        for process in self.processes:
            process.join()
        message = "Stopping parent process [{}]".format(str(self.pid))
        color_message = "Stopping parent process [{}]".format(
            click.style(str(self.pid), fg="cyan", bold=True)
        )
        logger.info(message, extra={"color_message": color_message})
