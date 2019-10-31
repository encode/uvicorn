import logging
import multiprocessing
import os
import signal
import time

import click

HANDLED_SIGNALS = (
    signal.SIGINT,  # Unix signal 2. Sent by Ctrl+C.
    signal.SIGTERM,  # Unix signal 15. Sent by `kill <pid>`.
)


class Multiprocess:
    def __init__(self, config):
        self.config = config
        self.workers = config.workers
        self.should_exit = False

    def handle_exit(self, sig, frame):
        self.should_exit = True

    def run(self, target, *args, **kwargs):
        pid = str(os.getpid())
        logger = logging.getLogger("uvicorn.error")

        message = "Started parent process [{}]".format(pid)
        color_message = "Started parent process [{}]".format(
            click.style(pid, fg="cyan", bold=True)
        )
        logger.info(message, extra={"color_message": color_message})

        for sig in HANDLED_SIGNALS:
            signal.signal(sig, self.handle_exit)

        processes = []
        for idx in range(self.workers):
            process = multiprocessing.Process(target=target, args=args, kwargs=kwargs)
            process.start()
            processes.append(process)

        while (
            any([process.is_alive() for process in processes]) and not self.should_exit
        ):
            time.sleep(0.1)

        message = "Stopping parent process [{}]".format(pid)
        color_message = "Stopping parent process [{}]".format(
            click.style(pid, fg="cyan", bold=True)
        )
        logger.info(message, extra={"color_message": color_message})
