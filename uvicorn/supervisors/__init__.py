import typing

from uvicorn.supervisors.basereload import BaseReload
from uvicorn.supervisors.multiprocess import Multiprocess

if typing.TYPE_CHECKING:
    ChangeReload: typing.Type[BaseReload]
else:
    try:
        from uvicorn.supervisors.watchgodreload import WatchGodReload as ChangeReload
    except ImportError:
        from uvicorn.supervisors.statreload import StatReload as ChangeReload


__all__ = ["Multiprocess", "ChangeReload"]
