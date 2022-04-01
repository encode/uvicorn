import logging
from pathlib import Path
from socket import socket
from typing import Callable, List, Optional

from watchfiles import Change, watch

from uvicorn.config import Config
from uvicorn.supervisors.basereload import BaseReload

logger = logging.getLogger("uvicorn.error")


class CustomFilter:
    def __init__(self, config: Config):
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

    def __call__(self, change: Change, path: str) -> bool:
        path = Path(path)
        debug(self.includes, self.excludes, change, path)
        for include_pattern in self.includes:
            if path.match(include_pattern):
                for exclude_pattern in self.excludes:
                    if path.match(exclude_pattern):
                        return False
                return True
        return False


class WatchFilesReload(BaseReload):
    def __init__(
        self,
        config: Config,
        target: Callable[[Optional[List[socket]]], None],
        sockets: List[socket],
    ) -> None:
        super().__init__(config, target, sockets)
        self.reloader_name = "watchfiles"
        self.watchers = []
        self.reload_dirs = []
        for directory in config.reload_dirs:
            if Path.cwd() not in directory.parents:
                self.reload_dirs.append(directory)
        if Path.cwd() not in self.reload_dirs:
            self.reload_dirs.append(Path.cwd())

        watch_filter = CustomFilter(config)
        self.watcher = watch(*self.reload_dirs, watch_filter=watch_filter, stop_event=self.should_exit)

    def __next__(self) -> bool:
        changes = next(self.watcher)
        message = "WatchFilesReload detected file change in '%s'. Reloading..."
        logger.warning(message, list({c[1] for c in changes}))
        return True
