import logging
from os import path

from watchgod import watch, run_process

from uvicorn.supervisors.basereload import BaseReload


logger = logging.getLogger("uvicorn.error")


class WatchGodReload():
    def __init__(self, config, target, sockets):
        self.config = config
        self.target = target
        self.sockets = sockets

        self.should_restart = False
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
        self.watch_dir_set = watch_dirs_set

    def run(self):
        for w in self.watch_dir_set:
            run_process(w, target=self.target, callback=self.callback)

    def callback(self, change):
        logger.info("callback")
        logger.info(change)

