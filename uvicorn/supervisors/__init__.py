from __future__ import annotations

from typing import TYPE_CHECKING

from uvicorn.supervisors.multiprocess import Multiprocess

if TYPE_CHECKING:
    from typing import Type

    from uvicorn.supervisors.basereload import BaseReload

    ChangeReload: Type[BaseReload]  # pragma: no cover
else:
    try:
        from uvicorn.supervisors.watchgodreload import WatchGodReload as ChangeReload
    except ImportError:  # pragma: no cover
        from uvicorn.supervisors.statreload import StatReload as ChangeReload

__all__ = ["Multiprocess", "ChangeReload"]
