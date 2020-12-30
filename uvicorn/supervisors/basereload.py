import logging
import signal

from uvicorn.supervisors import Multiprocess

HANDLED_SIGNALS = (
    signal.SIGINT,  # Unix signal 2. Sent by Ctrl+C.
    signal.SIGTERM,  # Unix signal 15. Sent by `kill <pid>`.
)

logger = logging.getLogger("uvicorn.error")


class BaseReload(Multiprocess):
    def __init__(self, config, target, sockets, shutdown_event, reload_event):
        super().__init__(config, target, sockets, shutdown_event, reload_event)
        self.reloader_name = None

    def should_restart(self):
        raise NotImplementedError("Reload strategies should override should_restart()")
