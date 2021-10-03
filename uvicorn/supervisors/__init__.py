import sys
import typing

from uvicorn.supervisors.basereload import BaseReload

if typing.TYPE_CHECKING:
    ChangeReload: typing.Type[BaseReload]  # pragma: no cover
else:
    try:
        from uvicorn.supervisors.watchgodreload import WatchGodReload as ChangeReload
    except ImportError:  # pragma: no cover
        from uvicorn.supervisors.statreload import StatReload as ChangeReload

if sys.platform == "win32":
    from uvicorn.supervisors.multiprocess import Multiprocess
else:
    from uvicorn.supervisors.manager import ProcessManager as Multiprocess

__all__ = ["Multiprocess", "ChangeReload"]
