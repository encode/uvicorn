from uvicorn.supervisors.multiprocess import Multiprocess

try:
    from uvicorn.supervisors.watchdogreload import WatchdogReload as ChangeReload
except ImportError:
    from uvicorn.supervisors.statreload import StatReload as ChangeReload

__all__ = ["Multiprocess", "ChangeReload"]
