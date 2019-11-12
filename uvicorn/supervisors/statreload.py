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
        self.mtimes = {}

    def handle_exit(self, sig, frame):
        """
        A signal handler that is registered with the parent process.
        """
        self.should_exit.set()

    def run(self):
        pid = str(os.getpid())

        message = "Started reloader process [{}]".format(pid)
        color_message = "Started reloader process [{}]".format(
            click.style(pid, fg="cyan", bold=True)
        )
        logger.info(message, extra={"color_message": color_message})

        for sig in HANDLED_SIGNALS:
            signal.signal(sig, self.handle_exit)

        process = get_subprocess(
            config=self.config, target=self.target, sockets=self.sockets
        )
        process.start()

        while not self.should_exit.wait(0.25):
            if self.should_restart():
                process = self.restart(process)

        process.join()
        message = "Stopping reloader process [{}]".format(pid)
        color_message = "Stopping reloader process [{}]".format(
            click.style(pid, fg="cyan", bold=True)
        )
        logger.info(message, extra={"color_message": color_message})

    def restart(self, process):
        self.mtimes = {}
        os.kill(process.pid, signal.SIGTERM)
        process.join()

        process = get_subprocess(self.config, target, kwargs=kwargs)
        process.start()
        return process

    def should_restart(self):
        for filename in self.iter_py_files():
            try:
                mtime = os.stat(filename).st_mtime
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
