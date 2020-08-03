import logging
import re
import socket
from os import DirEntry, path
from typing import Callable, List, Optional

from watchgod import DefaultWatcher

from uvicorn import Config
from uvicorn.supervisors.basereload import BaseReload

logger = logging.getLogger("uvicorn.error")


class CustomWatcher(DefaultWatcher):
    ignore_dotted_file_regex = r"^\/?(?:\w+\/)*(\.\w+)"
    ignored: List[str] = []

    def __init__(self, root_path: str) -> None:
        for t in self.ignored_file_regexes:
            self.ignored.append(t)
        self.ignored.append(self.ignore_dotted_file_regex)
        self._ignored = tuple(re.compile(r) for r in self.ignored)
        super().__init__(root_path)

    def should_watch_file(self, entry: DirEntry) -> bool:
        return not any(r.search(entry.name) for r in self._ignored)


class WatchGodReload(BaseReload):
    def __init__(
        self, config: Config, target: Callable, sockets: Optional[List[socket.socket]]
    ) -> None:
        super().__init__(config, target, sockets)
        self.reloader_name = "watchgod"
        self.watchers = []
        watch_dirs = {
            path.realpath(watch_dir)
            for watch_dir in self.config.reload_dirs
            if path.isdir(watch_dir)
        }
        watch_dirs_set = set(watch_dirs)

        # remove directories that already have a parent watched, so that we don't have
        # duplicated change events
        for watch_dir in watch_dirs:
            for compare_dir in watch_dirs:
                if compare_dir is watch_dir:
                    continue

                if watch_dir.startswith(compare_dir) and len(watch_dir) > len(
                    compare_dir
                ):
                    watch_dirs_set.remove(watch_dir)
        self.watch_dir_set = watch_dirs_set
        for w in watch_dirs_set:
            self.watchers.append(CustomWatcher(w))

    def should_restart(self) -> bool:
        for watcher in self.watchers:
            change = watcher.check()
            if change != set():
                message = "Detected file change in '%s'. Reloading..."
                logger.warning(message, [c[1] for c in change])
                return True

        return False
