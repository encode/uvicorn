import logging
import multiprocessing
import os
import signal
import sys
from multiprocessing.context import Process

import click

HANDLED_SIGNALS = (
    signal.SIGINT,  # Unix signal 2. Sent by Ctrl+C.
    signal.SIGTERM,  # Unix signal 15. Sent by `kill <pid>`.
)

logger = logging.getLogger("uvicorn.error")

multiprocessing.allow_connection_pickling()


class Multiprocess:
    def __init__(self, config, target, sockets, shutdown_event, reload_event):
        self.config = config
        self.target = target
        self.sockets = sockets
        self.processes = []
        self.pid = os.getpid()
        self.shutdown_event = shutdown_event
        self.reload_event = reload_event

    def multiprocess_signal_handler(self, sig, frame):
        logger.debug(f"MultiServer received: {sig}")
        self.shutdown_event.set()

    def run(self):
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        if self.config.reload:
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            self.startup()
            while not self.reload_event.wait(self.config.reload_delay):
                if self.should_restart():
                    self.restart()
                if self.shutdown_event.is_set():
                    break
            self.shutdown()
        else:
            self.startup()
            self.shutdown()

    def startup(self):
        message = "Started parent process [{}]".format(str(self.pid))
        color_message = "Started parent process [{}]".format(
            click.style(str(self.pid), fg="cyan", bold=True)
        )
        logger.info(message, extra={"color_message": color_message})

        for idx in range(self.config.workers):
            process = Process(
                target=self.target,
                kwargs={
                    "config": self.config,
                    "sockets": self.sockets,
                    "shutdown_event": self.shutdown_event,
                },
            )
            process.start()
            self.processes.append(process)

        for sig in HANDLED_SIGNALS:
            signal.signal(sig, self.multiprocess_signal_handler)

    def shutdown(self):
        message = "Stopping parent process [{}]".format(str(self.pid))
        color_message = "Stopping parent process [{}]".format(
            click.style(str(self.pid), fg="cyan", bold=True)
        )
        logger.info(message, extra={"color_message": color_message})
        for process in self.processes:
            process.join()

    def restart(self):
        message = "Restarting parent process [{}]".format(str(self.pid))
        color_message = "Restarting parent process [{}]".format(
            click.style(str(self.pid), fg="cyan", bold=True)
        )
        logger.debug(message, extra={"color_message": color_message})
        for process in self.processes:
            message = "Killing children process [{}]".format(str(process.pid))
            color_message = "Killing children process [{}]".format(
                click.style(str(process.pid), fg="cyan")
            )
            logger.debug(message, extra={"color_message": color_message})
            if sys.version_info < (3, 7):
                os.kill(process.pid, signal.SIGKILL)
            else:
                process.kill()
            process.join()
            self.processes.remove(process)
            self.mtimes = {}
        self.reload_event.clear()
        self.startup()
