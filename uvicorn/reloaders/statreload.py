import os
import signal
import sys
import time
import multiprocessing


HANDLED_SIGNALS = (
    signal.SIGINT,  # Unix signal 2. Sent by Ctrl+C.
    signal.SIGTERM,  # Unix signal 15. Sent by `kill <pid>`.
)


class StatReload:
    def __init__(self, logger):
        self.logger = logger
        self.should_exit = False
        self.mtimes = {}

    def handle_exit(self, sig, frame):
        self.should_exit = True

    def run(self, target, kwargs):
        pid = os.getpid()

        self.logger.info("Started reloader process [{}]".format(pid))

        for sig in HANDLED_SIGNALS:
            signal.signal(sig, self.handle_exit)

        process = multiprocessing.Process(target=target, kwargs=kwargs)
        process.start()

        while process.is_alive() and not self.should_exit:
            time.sleep(0.2)
            if self.should_restart():
                self.clear()
                os.kill(process.pid, signal.SIGTERM)
                process.join()
                process = multiprocessing.Process(target=target, kwargs=kwargs)
                process.start()

        self.logger.info("Stopping reloader process [{}]".format(pid))

        sys.exit(process.exitcode)

    def clear(self):
        self.mtimes = {}

    def should_restart(self):
        for filename in self.iter_py_files():
            try:
                mtime = os.stat(filename).st_mtime
            except OSError as exc:
                continue

            old_time = self.mtimes.get(filename)
            if old_time is None:
                self.mtimes[filename] = mtime
                continue
            elif mtime > old_time:
                message = "Detected file change in '%s'. Reloading..."
                self.logger.warning(message, filename)
                return True
        return False

    def iter_py_files(self):
        for subdir, dirs, files in os.walk("."):
            for file in files:
                filepath = subdir + os.sep + file
                if filepath.endswith(".py"):
                    yield filepath
