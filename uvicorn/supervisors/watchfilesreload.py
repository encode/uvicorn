import logging
from pathlib import Path
from socket import socket
from typing import Callable, List, Optional

from watchfiles import Change, watch

from uvicorn.config import Config
from uvicorn.supervisors.basereload import BaseReload

logger = logging.getLogger("uvicorn.error")


class FileFilter:
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

    def __call__(self, path: Path) -> bool:
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
        self.reloader_name = "WatchFilesReload"
        self.watchers = []
        self.reload_dirs = []
        for directory in config.reload_dirs:
            if Path.cwd() not in directory.parents:
                self.reload_dirs.append(directory)
        if Path.cwd() not in self.reload_dirs:
            self.reload_dirs.append(Path.cwd())

        self.watch_filter = FileFilter(config)
        self.watcher = watch(
            *self.reload_dirs,
            watch_filter=None,
            stop_event=self.should_exit,
        )

    def should_restart(self) -> Optional[List[Path]]:
        changes = next(self.watcher)
        unique_paths = {Path(c[1]) for c in changes}
        return [p for p in unique_paths if self.watch_filter(p)]
