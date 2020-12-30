import logging
import re
from pathlib import Path

from watchgod import DefaultWatcher

from uvicorn.supervisors.basereload import BaseReload

logger = logging.getLogger("uvicorn.error")


class CustomWatcher(DefaultWatcher):
    ignore_dotted_file_regex = r"^\/?(?:\w+\/)*(\.\w+)"
    ignored = []

    def __init__(self, root_path):
        for t in self.ignored_file_regexes:
            self.ignored.append(t)
        self.ignored.append(self.ignore_dotted_file_regex)
        self._ignored = tuple(re.compile(r) for r in self.ignored)
        super().__init__(root_path)

    def should_watch_file(self, entry):
        return not any(r.search(entry.name) for r in self._ignored)


class WatchGodReload(BaseReload):
    def __init__(self, config, target, sockets, shutdown_event, reload_event):
        super().__init__(config, target, sockets, shutdown_event, reload_event)
        self.reloader_name = "watchgod"
        self.watchers = []
        watch_dirs = {
            Path(watch_dir).resolve()
            for watch_dir in self.config.reload_dirs
            if Path(watch_dir).is_dir()
        }
        watch_dirs_set = set(watch_dirs)

        # remove directories that already have a parent watched, so that we don't have
        # duplicated change events
        for watch_dir in watch_dirs:
            for compare_dir in watch_dirs:
                if compare_dir is watch_dir:
                    continue

                if compare_dir in watch_dir.parents:
                    watch_dirs_set.remove(watch_dir)
        self.watch_dir_set = watch_dirs_set

    def should_restart(self):
        if not self.watchers:
            for w in self.watch_dir_set:
                self.watchers.append(CustomWatcher(w))
        for watcher in self.watchers:
            change = watcher.check()
            if change != set():
                message = "WatchGodReload detected file change in '%s'. Reloading..."
                logger.warning(message, [c[1] for c in change])
                self.watchers = []
                return True
        return False
