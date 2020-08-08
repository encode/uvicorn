import asyncio
import concurrent.futures
import io
import sys
from asyncio import AbstractEventLoop
from types import TracebackType
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Type, Union

from uvicorn._types import HeaderTypes, HTTPConnectionScope, Message, Receive, Send


def build_environ(
    scope: HTTPConnectionScope, message: Message, body: bytes
) -> Dict[str, Any]:
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
        namestr = name.decode("latin1")
        if namestr == "content-length":
            corrected_name = "CONTENT_LENGTH"
        elif namestr == "content-type":
            corrected_name = "CONTENT_TYPE"
        else:
            corrected_name = "HTTP_%s" % namestr.upper().replace("-", "_")
        # HTTPbis say only ASCII chars are allowed in headers, but we latin1
        # just in case
        valuestr = value.decode("latin1")
        if corrected_name in environ:
            valuestr = str(environ[corrected_name]) + "," + valuestr
        environ[corrected_name] = valuestr
    return environ


class WSGIMiddleware:
    def __init__(self, app: Callable, workers: int = 10) -> None:
        self.app = app
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=workers)

    async def __call__(
        self, scope: HTTPConnectionScope, receive: Receive, send: Send
    ) -> None:
        assert scope["type"] == "http"
        instance = WSGIResponder(self.app, self.executor, scope)
        await instance(receive, send)


class WSGIResponder:
    def __init__(
        self,
        app: Callable,
        executor: concurrent.futures.ThreadPoolExecutor,
        scope: HTTPConnectionScope,
    ):
        self.app = app
        self.executor = executor
        self.scope = scope
        self.status = None
        self.response_headers = None
        self.send_event = asyncio.Event()
        self.send_queue: List[
            Optional[Dict[str, Union[str, bytes, int, HeaderTypes]]]
        ] = []
        self.loop: Optional[AbstractEventLoop] = None
        self.response_started = False
        self.exc_info: Optional[Tuple[Type[Exception], Exception, TracebackType]] = None

    async def __call__(self, receive: Receive, send: Send) -> None:
        message = await receive()
        body = message.get("body", b"")
        more_body = message.get("more_body", False)
        while more_body:
            body_message = await receive()
            body += body_message.get("body", b"")
            more_body = body_message.get("more_body", False)
        environ = build_environ(self.scope, message, body)
        self.loop = asyncio.get_event_loop()
        wsgi = self.loop.run_in_executor(
            self.executor, self.wsgi, environ, self.start_response
        )
        sender = self.loop.create_task(self.sender(send))
        try:
            await asyncio.wait_for(wsgi, None)
        finally:
            self.send_queue.append(None)
            self.send_event.set()
            await asyncio.wait_for(sender, None)
        if self.exc_info is not None:
            raise self.exc_info[0].with_traceback(self.exc_info[1], self.exc_info[2])

    async def sender(self, send: Send) -> None:
        while True:
            if self.send_queue:
                message = self.send_queue.pop(0)
                if message is None:
                    return
                await send(message)
            else:
                await self.send_event.wait()
                self.send_event.clear()

    def start_response(
        self,
        status: str,
        response_headers: Sequence[Tuple[str, str]],
        exc_info: Optional[Tuple[Type[Exception], Exception, TracebackType]] = None,
    ) -> None:
        self.exc_info = exc_info
        if not self.response_started:
            self.response_started = True
            status_code_split, _ = status.split(" ", 1)
            status_code = int(status_code_split)
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
            if self.loop:
                self.loop.call_soon_threadsafe(self.send_event.set)

    def wsgi(self, environ: dict, start_response: Callable) -> None:
        for chunk in self.app(environ, start_response):
            self.send_queue.append(
                {"type": "http.response.body", "body": chunk, "more_body": True}
            )
            assert self.loop
            self.loop.call_soon_threadsafe(self.send_event.set)

        self.send_queue.append({"type": "http.response.body", "body": b""})
        assert self.loop
        self.loop.call_soon_threadsafe(self.send_event.set)
