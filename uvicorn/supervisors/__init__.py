import typing

from uvicorn.supervisors.basereload import BaseReload
from uvicorn.supervisors.multiprocess import Multiprocess

if typing.TYPE_CHECKING:
    ChangeReload: typing.Type[BaseReload]  # pragma: no cover
else:
    try:
        from uvicorn.supervisors.watchfilesreload import WatchFilesReload

        ChangeReload = WatchFilesReload
    except ImportError:  # pragma: no cover
        try:
            from uvicorn.supervisors.watchgodreload import WatchGodReload

            ChangeReload = WatchGodReload
        except ImportError:  # pragma: no cover
            from uvicorn.supervisors.statreload import StatReload as ChangeReload

__all__ = ["Multiprocess", "ChangeReload"]
