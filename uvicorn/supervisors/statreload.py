import logging
import multiprocessing
import os
import signal
import sys
import time
from pathlib import Path

HANDLED_SIGNALS = (
    signal.SIGINT,  # Unix signal 2. Sent by Ctrl+C.
    signal.SIGTERM,  # Unix signal 15. Sent by `kill <pid>`.
)


class StatReload:
    def __init__(self, config):
        self.config = config
        self.should_exit = False
        self.reload_count = 0
        self.mtimes = {}
        self.logger = logging.getLogger("uvicorn.error")

    def handle_exit(self, sig, frame):
        self.should_exit = True

    @staticmethod
    def handle_fds(target, fd_stdin, **kwargs):
        """Handle stdin in subprocess for pdb."""
        if fd_stdin is not None:
            sys.stdin = os.fdopen(fd_stdin)
        target(**kwargs)

    def run(self, target, *args, **kwargs):
        pid = os.getpid()

        self.logger.info("Started reloader process [{}]".format(pid))

        for sig in HANDLED_SIGNALS:
            signal.signal(sig, self.handle_exit)

        def get_subprocess():
            spawn = multiprocessing.get_context("spawn")
            try:
                fileno = sys.stdin.fileno()
            except OSError:
                fileno = None

            return spawn.Process(
                target=self.handle_fds, args=(target, fileno), kwargs=kwargs
            )

        process = get_subprocess()
        process.start()

        while process.is_alive() and not self.should_exit:
            time.sleep(0.3)
            if self.should_restart():
                self.clear()
                os.kill(process.pid, signal.SIGTERM)
                process.join()

                process = get_subprocess()
                process.start()
                self.reload_count += 1

        self.logger.info("Stopping reloader process [{}]".format(pid))

    def clear(self):
        self.mtimes = {}

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
                self.logger.warning(message, display_path)
                return True
        return False

    def iter_py_files(self):
        for reload_dir in self.config.reload_dirs:
            for subdir, dirs, files in os.walk(reload_dir):
                for file in files:
                    filepath = subdir + os.sep + file
                    if filepath.endswith(".py"):
                        yield filepath
