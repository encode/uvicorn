from gunicorn.app.wsgiapp import WSGIApplication
from gunicorn.config import Config, WorkerClass, KNOWN_SETTINGS
from gunicorn.workers import SUPPORTED_WORKERS
from importlib import import_module
import traceback


SUPPORTED_WORKERS = {
    'uvicorn': 'uvicorn.worker.UvicornWorker'
}

WorkerClass.default = 'uvicorn'


def load_class(uri):
    components = uri.split('.')
    if len(components) == 1 and uri in SUPPORTED_WORKERS:
        components = SUPPORTED_WORKERS[uri].split(".")

    klass = components.pop(-1)
    try:
        mod = import_module('.'.join(components))
    except:
        exc = traceback.format_exc()
        msg = "class uri %r invalid or not found: \n\n[%s]"
        raise RuntimeError(msg % (uri, exc))
    return getattr(mod, klass)


class UvicornConfig(Config):
    @property
    def worker_class(self):
        # Modified so that `load_class` is not hardwired to gunicorn defaults.
        uri = self.settings['worker_class'].get()
        worker_class = load_class(uri)
        if hasattr(worker_class, "setup"):
            worker_class.setup()
        return worker_class

    @property
    def worker_class_str(self):
        # Modified so that we include the uvicorn version string in logging.
        from uvicorn import __version__
        uri = self.settings['worker_class'].get()
        if uri == 'uvicorn':
            return 'uvicorn %s' % __version__
        return uri


class ASGIApplication(WSGIApplication):
    def load_default_config(self):
        self.cfg = UvicornConfig(self.usage, prog=self.prog)
        self.cfg.settings['worker_class'].default = 'uvicorn'


def run():
    ASGIApplication("%(prog)s [OPTIONS] [APP_MODULE]").run()


if __name__ == '__main__':
    run()
