import logging
import os
import signal

import click

from uvicorn.subprocess import get_subprocess
from uvicorn.supervisors.interface import ProcessTracker

HANDLED_SIGNALS = (
    signal.SIGINT,  # Unix signal 2. Sent by Ctrl+C.
    signal.SIGTERM,  # Unix signal 15. Sent by `kill <pid>`.
)

logger = logging.getLogger("uvicorn.error")


class Multiprocess(ProcessTracker):
    def __init__(self, config, target, sockets):
        super().__init__()
        self.config = config
        self.target = target
        self.sockets = sockets
        self.processes = []
        self.pid = os.getpid()

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

        for sig in HANDLED_SIGNALS:
            signal.signal(sig, self.signal_handler)

        for idx in range(self.config.workers):
            process = get_subprocess(
                config=self.config, target=self.target, sockets=self.sockets
            )
            process.start()
            self.processes.append(process)
        for process in self.processes:
            self.child_pids.append(process.pid)

    def shutdown(self):
        for process in self.processes:
            process.join()

        message = "Stopping parent process [{}]".format(str(self.pid))
        color_message = "Stopping parent process [{}]".format(
            click.style(str(self.pid), fg="cyan", bold=True)
        )
        logger.info(message, extra={"color_message": color_message})
