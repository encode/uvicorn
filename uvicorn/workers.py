import asyncio

from gunicorn.workers.base import Worker

from uvicorn.config import Config
from uvicorn.main import Server


class UvicornWorker(Worker):
    """
    A worker class for Gunicorn that interfaces with an ASGI consumer callable,
    rather than a WSGI callable.
    """

    CONFIG_KWARGS = {"loop": "uvloop", "http": "httptools"}

    def __init__(self, *args, **kwargs):
        super(UvicornWorker, self).__init__(*args, **kwargs)

        self.log.level = self.log.loglevel

        config_kwargs = {
            "app": None,
            "logger": self.log,
            "timeout_keep_alive": self.cfg.keepalive,
            "timeout_notify": self.timeout,
            "callback_notify": self.callback_notify,
        }

        if self.cfg.is_ssl:
            ssl_kwargs = {
                "ssl_keyfile": self.cfg.ssl_options.get("keyfile"),
                "ssl_certfile": self.cfg.ssl_options.get("certfile"),
                "ssl_version": self.cfg.ssl_options.get("ssl_version"),
                "ssl_cert_reqs": self.cfg.ssl_options.get("cert_reqs"),
                "ssl_ca_certs": self.cfg.ssl_options.get("ca_certs"),
                "ssl_ciphers": self.cfg.ssl_options.get("ciphers"),
            }
            config_kwargs.update(ssl_kwargs)

        config_kwargs.update(self.CONFIG_KWARGS)

        self.config = Config(**config_kwargs)

    def init_process(self):
        self.config.setup_event_loop()
        super(UvicornWorker, self).init_process()

    def init_signals(self):
        pass

    def run(self):
        self.config.app = self.wsgi
        server = Server(config=self.config)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(
            server.serve(sockets=self.sockets, shutdown_servers=False)
        )

    async def callback_notify(self):
        self.notify()


class UvicornH11Worker(UvicornWorker):
    CONFIG_KWARGS = {"loop": "asyncio", "http": "h11"}
