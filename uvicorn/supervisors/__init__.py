from typing import TYPE_CHECKING, Type

from uvicorn.supervisors.basereload import BaseReload
from uvicorn.supervisors.multiprocess import Multiprocess

if TYPE_CHECKING:
    ChangeReload: Type[BaseReload]
else:
    try:
        from uvicorn.supervisors.watchgodreload import WatchGodReload as ChangeReload
    except ImportError:  # pragma: no cover
        from uvicorn.supervisors.statreload import StatReload as ChangeReload

__all__ = ["Multiprocess", "ChangeReload"]
