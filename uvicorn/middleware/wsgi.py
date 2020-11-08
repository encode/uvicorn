import io
import sys

from uvicorn._backends.auto import AutoBackend
from uvicorn._compat import AsyncExitStack


def build_environ(scope, message, body):
    """
    Builds a scope and request message into a WSGI environ object.
    """
    environ = {
        "REQUEST_METHOD": scope["method"],
        "SCRIPT_NAME": "",
        "PATH_INFO": scope["path"],
        "QUERY_STRING": scope["query_string"].decode("ascii"),
        "SERVER_PROTOCOL": "HTTP/%s" % scope["http_version"],
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": scope.get("scheme", "http"),
        "wsgi.input": io.BytesIO(body),
        "wsgi.errors": sys.stdout,
        "wsgi.multithread": True,
        "wsgi.multiprocess": True,
        "wsgi.run_once": False,
    }

    # Get server name and port - required in WSGI, not in ASGI
    server = scope.get("server")
    if server is None:
        server = ("localhost", 80)
    environ["SERVER_NAME"] = server[0]
    environ["SERVER_PORT"] = server[1]

    # Get client IP address
    client = scope.get("client")
    if client is not None:
        environ["REMOTE_ADDR"] = client[0]

    # Go through headers and make them into environ entries
    for name, value in scope.get("headers", []):
        name = name.decode("latin1")
        if name == "content-length":
            corrected_name = "CONTENT_LENGTH"
        elif name == "content-type":
            corrected_name = "CONTENT_TYPE"
        else:
            corrected_name = "HTTP_%s" % name.upper().replace("-", "_")
        # HTTPbis say only ASCII chars are allowed in headers, but we latin1
        # just in case
        value = value.decode("latin1")
        if corrected_name in environ:
            value = environ[corrected_name] + "," + value
        environ[corrected_name] = value
    return environ


class WSGIMiddleware:
    def __init__(self, app, workers=10):
        self.app = app

    async def __call__(self, scope, receive, send):
        assert scope["type"] == "http"
        instance = WSGIResponder(self.app, scope)
        await instance(receive, send)


class WSGIResponder:
    def __init__(self, app, scope):
        self._backend = AutoBackend()
        self.app = app
        self.scope = scope
        self.status = None
        self.response_headers = None
        self.send_event = self._backend.create_event()
        self.send_queue = []
        self.response_started = False
        self.exc_info = None

    async def __call__(self, receive, send):
        message = await receive()
        body = message.get("body", b"")
        more_body = message.get("more_body", False)
        while more_body:
            body_message = await receive()
            body += body_message.get("body", b"")
            more_body = body_message.get("more_body", False)
        environ = build_environ(self.scope, message, body)

        async def cleanup() -> None:
            self.send_queue.append(None)
            self.send_event.set()

        exit_stack = AsyncExitStack()
        async with exit_stack:
            await exit_stack.enter_async_context(
                self._backend.run_in_background(self.sender, send)
            )
            exit_stack.push_async_callback(cleanup)
            await self._backend.run_sync_in_thread(
                self.wsgi, environ, self.start_response
            )

        if self.exc_info is not None:
            raise self.exc_info[0].with_traceback(self.exc_info[1], self.exc_info[2])

    async def sender(self, send):
        while True:
            if self.send_queue:
                message = self.send_queue.pop(0)
                if message is None:
                    return
                await send(message)
            else:
                await self.send_event.wait()
                self.send_event.clear()

    def start_response(self, status, response_headers, exc_info=None):
        self.exc_info = exc_info
        if not self.response_started:
            self.response_started = True
            status_code, _ = status.split(" ", 1)
            status_code = int(status_code)
            headers = [
                (name.encode("ascii"), value.encode("ascii"))
                for name, value in response_headers
            ]
            self.send_queue.append(
                {
                    "type": "http.response.start",
                    "status": status_code,
                    "headers": headers,
                }
            )
            self._backend.call_soon(self.send_event.set)

    def wsgi(self, environ, start_response):
        for chunk in self.app(environ, start_response):
            self.send_queue.append(
                {"type": "http.response.body", "body": chunk, "more_body": True}
            )
            self._backend.call_soon(self.send_event.set)

        self.send_queue.append({"type": "http.response.body", "body": b""})
        self._backend.call_soon(self.send_event.set)
