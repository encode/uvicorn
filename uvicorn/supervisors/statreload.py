import multiprocessing
import os
import signal
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

    def handle_exit(self, sig, frame):
        self.should_exit = True

    def run(self, target, *args, **kwargs):
        pid = os.getpid()
        logger = self.config.logger_instance

        logger.info("Started reloader process [{}]".format(pid))

        for sig in HANDLED_SIGNALS:
            signal.signal(sig, self.handle_exit)

        spawn = multiprocessing.get_context("spawn")
        process = spawn.Process(target=target, args=args, kwargs=kwargs)
        process.start()

        while process.is_alive() and not self.should_exit:
            time.sleep(0.3)
            if self.should_restart():
                self.clear()
                os.kill(process.pid, signal.SIGTERM)
                process.join()
                process = spawn.Process(target=target, args=args, kwargs=kwargs)
                process.start()
                self.reload_count += 1

        logger.info("Stopping reloader process [{}]".format(pid))

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
                self.config.logger_instance.warning(message, display_path)
                return True
        return False

    def iter_py_files(self):
        for reload_dir in self.config.reload_dirs:
            for subdir, dirs, files in os.walk(reload_dir):
                for file in files:
                    filepath = subdir + os.sep + file
                    if filepath.endswith(".py"):
                        yield filepath
