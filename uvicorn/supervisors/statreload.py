import logging
import os
import re
from pathlib import Path

from uvicorn.supervisors.basereload import BaseReload

logger = logging.getLogger("uvicorn.error")


class StatReload(BaseReload):
    ignored_file_regexes = r'\.py[cod]$', r'\.___jb_...___$', r'\.sw.$', '~$'
    def __init__(self, config, target, sockets):
        super().__init__(config, target, sockets)
        self.reloader_name = "statreload"
        self.mtimes = {}
        self._ignored_file_regexes = tuple(re.compile(r) for r in self.ignored_file_regexes)

    def should_restart(self):
        for filename in self.iter_files():
            try:
                mtime = os.path.getmtime(filename)
            except OSError:  # pragma: nocover
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

    def iter_files(self):
        for reload_dir in self.config.reload_dirs:
            for subdir, dirs, files in os.walk(reload_dir):
                for file in files:
                    if not file.startswith(".") and not any(r.search(file) for r in self._ignored_file_regexes):
                        yield subdir + os.sep + file
