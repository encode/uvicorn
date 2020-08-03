import logging
import os
import socket
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Optional

from uvicorn import Config
from uvicorn.supervisors.basereload import BaseReload

logger = logging.getLogger("uvicorn.error")


class StatReload(BaseReload):
    def __init__(
        self, config: Config, target: Callable, sockets: Optional[List[socket.socket]]
    ) -> None:
        super().__init__(config, target, sockets)
        self.reloader_name = "statreload"
        self.mtimes: Dict[str, float] = {}

    def should_restart(self) -> bool:
        for filename in self.iter_py_files():
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

    def iter_py_files(self) -> Iterator:
        for reload_dir in self.config.reload_dirs:
            for subdir, dirs, files in os.walk(reload_dir):
                for file in files:
                    if file.endswith(".py"):
                        yield subdir + os.sep + file
