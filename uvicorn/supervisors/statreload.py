import logging
import os
import signal
import threading
from pathlib import Path

import click

from uvicorn.subprocess import get_subprocess

HANDLED_SIGNALS = (
    signal.SIGINT,  # Unix signal 2. Sent by Ctrl+C.
    signal.SIGTERM,  # Unix signal 15. Sent by `kill <pid>`.
)

logger = logging.getLogger("uvicorn.error")


class StatReload:
    def __init__(self, config, target, sockets):
        self.config = config
        self.target = target
        self.sockets = sockets
        self.should_exit = threading.Event()
        self.pid = os.getpid()
        self.mtimes = {}

    def signal_handler(self, sig, frame):
        """
        A signal handler that is registered with the parent process.
        """
        self.should_exit.set()

    def run(self):
        self.startup()
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
        for filename in self.iter_py_files():
            try:
                mtime = os.path.getmtime(filename)
            except OSError as exc:  # pragma: nocover
                continue

            old_time = self.mtimes.get(filename)
            if old_time is None:
                self.mtimes[filename] = mtime
                continue
            elif mtime > old_time:
                display_path = os.path.normpath(filename)
                if Path.cwd() in Path(filename).parents:
                    display_path = os.path.normpath(os.path.relpath(filename))
                message = "Detected file change in '%s'. Reloading..."
                logger.warning(message, display_path)
                return True
        return False

    def iter_py_files(self):
        for reload_dir in self.config.reload_dirs:
            for subdir, dirs, files in os.walk(reload_dir):
                for file in files:
                    if file.endswith(".py"):
                        yield subdir + os.sep + file
