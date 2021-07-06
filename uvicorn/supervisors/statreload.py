import logging
import os
from pathlib import Path
from socket import socket
from typing import Callable, Iterator, List, Optional

from uvicorn.config import Config
from uvicorn.supervisors.basereload import BaseReload

logger = logging.getLogger("uvicorn.error")


class StatReload(BaseReload):
    def __init__(
        self,
        config: Config,
        target: Callable[[Optional[List[socket]]], None],
        sockets: List[socket],
    ) -> None:
        super().__init__(config, target, sockets)
        self.reloader_name = "statreload"
        self.mtimes = {}

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
                message = "StatReload detected file change in '%s'. Reloading..."
                logger.warning(message, display_path)
                return True
        return False

    def iter_py_files(self) -> Iterator[str]:
        for reload_dir in self.config.reload_dirs:
            for subdir, dirs, files in os.walk(reload_dir):
                for file in files:
                    if file.endswith(".py"):
                        yield subdir + os.sep + file
