import logging
from pathlib import Path
from socket import socket
from typing import TYPE_CHECKING

from watchfiles import PythonFilter, watch

from uvicorn.supervisors.basereload import BaseReload

if TYPE_CHECKING:
    from typing import Callable, List, Optional, Sequence, Union

    from uvicorn.config import Config

logger = logging.getLogger("uvicorn.error")


class CustomFilter(PythonFilter):
    def __init__(
        self,
        *,
        ignore_paths: Optional[Sequence[Union[str, Path]]] = None,
        extra_extensions: Sequence[str] = ()
    ) -> None:
        super().__init__(ignore_paths=ignore_paths, extra_extensions=extra_extensions)


class WatchFilesReload(BaseReload):
    def __init__(
        self,
        config: Config,
        target: Callable[[Optional[List[socket]]], None],
        sockets: List[socket],
    ) -> None:
        super().__init__(config, target, sockets)
        self.reloader_name = "watchfiles"
        self.reload_dirs = []

        for directory in config.reload_dirs:
            if Path.cwd() not in directory.parents:
                self.reload_dirs.append(directory)
        if Path.cwd() not in self.reload_dirs:
            self.reload_dirs.append(Path.cwd())

        self.watch_filter = CustomFilter()

    def should_restart(self) -> bool:
        for changes in watch(*self.reload_dirs, watch_filter=self.watch_filter):
            message = "WatchFilesReload detected file change in '%s'. Reloading..."
            logger.warning(message, [c[1] for c in changes])
            return True

        return False
