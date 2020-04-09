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


class BaseReload:
    def __init__(self, config, target, sockets):
        self.config = config
        self.target = target
        self.sockets = sockets
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
        while not self.should_exit.wait(0.25):
            if self.should_restart():
                self.restart()
        self.shutdown()

        self.child_pids.append(self.process.pid)
        while not self.should_exit.wait(0.25):
            if self.should_restart():
                self.restart()
        self.shutdown()

    def startup(self):
        message = "Started reloader process [{}]".format(str(self.pid))
        color_message = "Started reloader process [{}]".format(
            click.style(str(self.pid), fg="cyan", bold=True)
        )
        logger.info(message, extra={"color_message": color_message})

        for sig in HANDLED_SIGNALS:
            signal.signal(sig, self.signal_handler)

        self.process = get_subprocess(
            config=self.config, target=self.target, sockets=self.sockets
        )
        self.process.start()

    def restart(self):
        self.mtimes = {}
        os.kill(self.process.pid, signal.SIGTERM)
        self.process.join()

        self.process = get_subprocess(
            config=self.config, target=self.target, sockets=self.sockets
        )
        self.process.start()

    def shutdown(self):
        self.process.join()
        message = "Stopping reloader process [{}]".format(str(self.pid))
        color_message = "Stopping reloader process [{}]".format(
            click.style(str(self.pid), fg="cyan", bold=True)
        )
        logger.info(message, extra={"color_message": color_message})

    def should_restart(self):
        raise NotImplementedError("Reload strategies should override should_restart()")
