import logging
from pathlib import Path
from socket import socket
from typing import TYPE_CHECKING, Callable, List, Optional

from watchgod import DefaultWatcher

from uvicorn.config import Config
from uvicorn.supervisors.basereload import BaseReload

logger = logging.getLogger("uvicorn.error")

if TYPE_CHECKING:
    import os

    DirEntry = os.DirEntry[str]


class CustomWatcher(DefaultWatcher):
    def __init__(self, root_path: Path, config: Config):
        default_includes = ["*.py"]
        self.includes = [
            default
            for default in default_includes
            if default not in config.reload_excludes
        ]
        self.includes.extend(config.reload_includes)
        self.includes = list(set(self.includes))

        default_excludes = [".*", ".py[cod]", ".sw.*", "~*"]
        self.excludes = [
            default
            for default in default_excludes
            if default not in config.reload_includes
        ]
        self.excludes.extend(config.reload_excludes)
        self.excludes = list(set(self.excludes))

        self.dirs = config.reload_dirs
        self.dirs_excludes = config.reload_dirs_excludes
        super().__init__(str(root_path))

    def should_watch_file(self, entry: "DirEntry") -> bool:
        entry_path = Path(entry)
        for include_pattern in self.includes:
            if entry_path.match(include_pattern):
                for exclude_pattern in self.excludes:
                    if entry_path.match(exclude_pattern):
                        return False
                return True

        return False

    def should_watch_dir(self, entry: "DirEntry") -> bool:
        entry_path = Path(entry)
        for directory in self.dirs:
            if entry_path == directory or directory in entry_path.parents:
                for excl_directory in self.dirs_excludes:
                    if (
                        entry_path == excl_directory
                        or excl_directory in entry_path.parents
                    ):
                        return False
                return True
        return False


class WatchGodReload(BaseReload):
    def __init__(
        self,
        config: Config,
        target: Callable[[Optional[List[socket]]], None],
        sockets: List[socket],
    ) -> None:
        super().__init__(config, target, sockets)
        self.reloader_name = "watchgod"
        self.watchers = []
        for w in config.reload_dirs:
            self.watchers.append(CustomWatcher(w.resolve(), self.config))

    def should_restart(self) -> bool:
        for watcher in self.watchers:
            change = watcher.check()
            if change != set():
                message = "WatchGodReload detected file change in '%s'. Reloading..."
                logger.warning(message, [c[1] for c in change])
                return True

        return False
