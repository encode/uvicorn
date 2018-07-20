import os
import sys


def _iter_py_files():
    for subdir, dirs, files in os.walk("."):
        for file in files:
            filepath = subdir + os.sep + file
            if filepath.endswith(".py"):
                yield filepath


class StatReload:
    def __init__(self, logger):
        self.logger = logger
        self.mtimes = {}

    def clear(self):
        self.mtimes = {}

    def should_restart(self):
        for filename in _iter_py_files():
            try:
                mtime = os.stat(filename).st_mtime
            except OSError:
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
