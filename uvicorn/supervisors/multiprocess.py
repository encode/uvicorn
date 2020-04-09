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
        self.child_pids = []

    def signal_handler(self, sig, frame):
        """
        A signal handler that is registered with the parent process.
        """
        logger.info(f"Handling signal: {sig}")
        for child_pid in self.child_pids:
            logger.debug(f"Attempt at killing child PID {child_pid}")
            try:
                os.kill(child_pid, signal.SIGINT)
                (pid, status) = os.waitpid(child_pid, 0)
                if pid == child_pid:
                    logger.debug(f"{pid}: {status}")
                    if os.WIFEXITED(status):
                        logger.debug(
                            "process returning status exited via the exit() system call"
                        )
                    elif os.WIFSIGNALED(status):
                        logger.debug(
                            "process returning status was terminated by a signal"
                        )
                    elif os.WIFSTOPPED(status):
                        logger.debug("process returning status was stopped")
            except Exception as e:
                logger.error(f"Cant kill child PID {child_pid}: {e}")
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
