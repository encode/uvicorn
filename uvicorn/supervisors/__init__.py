import typing
import warnings

from uvicorn.supervisors.basereload import BaseReload
from uvicorn.supervisors.multiprocess import Multiprocess

if typing.TYPE_CHECKING:
    ChangeReload: typing.Type[BaseReload]  # pragma: no cover
else:
    try:
        from uvicorn.supervisors.watchfilesreload import (
            WatchFilesReload as ChangeReload,
        )
    except ImportError:  # pragma: no cover
        try:
            from uvicorn.supervisors.watchgodreload import (
                WatchGodReload as ChangeReload,
            )
        except ImportError:
            from uvicorn.supervisors.statreload import StatReload as ChangeReload
        else:
            warnings.warn(
                '"watchgod" is depreciated, you should switch '
                "to watchfiles (`pip install watchfiles`).",
                DeprecationWarning,
            )

__all__ = ["Multiprocess", "ChangeReload"]
