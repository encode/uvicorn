from typing import TYPE_CHECKING, Type, Union

from uvicorn.supervisors.multiprocess import Multiprocess

if TYPE_CHECKING:
    from uvicorn.supervisors.statreload import StatReload
    from uvicorn.supervisors.watchgodreload import WatchGodReload

ChangeReload: Union[Type["WatchGodReload"], Type["StatReload"]]

try:
    from uvicorn.supervisors.watchgodreload import WatchGodReload as ChangeReload
except ImportError:
    from uvicorn.supervisors.statreload import StatReload as ChangeReload

__all__ = ["Multiprocess", "ChangeReload"]
