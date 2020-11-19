from uvicorn import Server


class _CustomServer(Server):
    def install_signal_handlers(self):
        pass
