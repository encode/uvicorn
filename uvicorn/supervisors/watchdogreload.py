import logging
import os
from datetime import datetime, timedelta
from os import path

from watchdog.events import PatternMatchingEventHandler
from watchdog.observers import Observer

from uvicorn.supervisors.basereload import BaseReload

logger = logging.getLogger("uvicorn.error")


class WatchdogReload(BaseReload):
    def __init__(self, config, target, sockets):
        super().__init__(config, target, sockets)

        self.reload_count = 0
        self.has_changed = False

        # watchdog only accept directories
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

        def callback(event):
            # logger.info(event)
            display_path = getattr(event, "dest_path", event.src_path)
            message = "Detected file change in '%s'. Reloading..."
            logger.warning(message, display_path)
            self.has_changed = True

        observer = Observer()
        event_handler = ChangeEventHandler(patterns=["*.py"], callback=callback)

        for watch_dir in watch_dirs_set:
            observer.schedule(event_handler, watch_dir, recursive=True)

        observer.start()

    def should_restart(self):
        if self.has_changed:
            self.has_changed = False
            return True

        return False


class ChangeEventHandler(PatternMatchingEventHandler):
    def __init__(
        self,
        patterns=None,
        ignore_patterns=None,
        ignore_directories=False,
        case_sensitive=False,
        callback=None,
    ):
        super().__init__(
            patterns=patterns,
            ignore_patterns=ignore_patterns,
            ignore_directories=ignore_directories,
            case_sensitive=case_sensitive,
        )
        self.last_modified = datetime.now()

        self.callback = callback

    def on_any_event(self, event):
        super().on_any_event(event)
        if self.callback is not None:
            if event.event_type == "modified":
                if datetime.now() - self.last_modified < timedelta(milliseconds=100):
                    return
                else:
                    self.last_modified = datetime.now()
                    self.callback(event)
            else:
                self.callback(event)
