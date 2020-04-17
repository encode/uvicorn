import asyncio
import concurrent.futures
import sys
import time


class Body:
    def __init__(self, recv_event):
        self.buffer = bytearray()
        self.recv_event = recv_event
        self._has_more = True

    def feed_eof(self):
        self._has_more = False

    @property
    def has_more(self):
        if self._has_more or self.buffer:
            return True
        return False

    def write(self, data):
        self.buffer.extend(data)

    def _read(self, size=0):
        """
        read data

        * Call _read to pre-read data into the buffer
        * Call _read(size) to read data of specified length in buffer
        * Call _read(negative) to read all data in buffer
        """
        while self._has_more and not self.buffer:
            if not self.recv_event.is_set():
                self.recv_event.set()
            time.sleep(0.25)

        if size < 0:
            data = self.buffer[:]
            del self.buffer[:]
        else:
            data = self.buffer[:size]
            del self.buffer[:size]
        return bytes(data)

    def read(self, size=-1):
        data = self._read(size)
        while (len(data) < size or size == -1) and self.has_more:
            data += self._read(size - len(data))
        return data

    def _readline(self, limit):
        index = self.buffer.find(b"\n")
        if -1 < index:  # found b"\n"
            if limit > -1:
                return self._read(min(index + 1, limit))
            return self._read(index + 1)

        if -1 < limit < len(self.buffer):
            return self._read(limit)

        if self._has_more:  # Not found b"\n", request more data
            self.recv_event.set()
        return None

    def readline(self, limit=-1):
        data = self._readline(limit)
        while (not data) and self.has_more:
            data = self._readline(limit)
        return data if data else bytes()

    def readlines(self, hint=-1):
        if hint == -1:
            raw_data = self.read(-1)
            if raw_data[-1] == 10:  # 10 -> b"\n"
                raw_data = raw_data[:-1]
            bytelist = raw_data.split(b"\n")
            return [line + b"\n" for line in bytelist]
        return [self.readline() for _ in range(hint)]

    def __iter__(self):
        while self.has_more:
            yield self.readline()


def build_environ(scope, body):
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
        "wsgi.input": body,
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
        # HTTPbis say only ASCII chars are allowed in headers, but we latin1 just in case
        value = value.decode("latin1")
        if corrected_name in environ:
            value = environ[corrected_name] + "," + value
        environ[corrected_name] = value
    return environ


class WSGIMiddleware:
    def __init__(self, app, workers=10):
        self.app = app
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=workers)

    async def __call__(self, scope, receive, send):
        assert scope["type"] == "http"
        instance = WSGIResponder(self.app, self.executor, scope)
        await instance(receive, send)


class WSGIResponder:
    def __init__(self, app, executor, scope):
        self.app = app
        self.executor = executor
        self.scope = scope
        self.status = None
        self.response_headers = None
        self.recv_event = asyncio.Event()
        self.send_event = asyncio.Event()
        self.send_queue = []
        self.loop = None
        self.response_started = False
        self.exc_info = None

    async def __call__(self, receive, send):
        body = Body(self.recv_event)
        environ = build_environ(self.scope, body)
        self.loop = asyncio.get_event_loop()
        wsgi = self.loop.run_in_executor(
            self.executor, self.wsgi, environ, self.start_response
        )
        sender = self.loop.create_task(self.sender(send))
        receiver = self.loop.create_task(self.recevier(receive, body))
        try:
            await asyncio.wait_for(wsgi, None)
        finally:
            self.send_queue.append(None)
            self.send_event.set()
            await asyncio.wait_for(sender, None)
            receiver.cancel()
        if self.exc_info is not None:
            raise self.exc_info[0].with_traceback(self.exc_info[1], self.exc_info[2])

    async def recevier(self, receive, body):
        more_body = True
        while more_body:
            await self.recv_event.wait()
            message = await receive()
            self.recv_event.clear()
            body.write(message.get("body", b""))
            more_body = message.get("more_body", False)
        body.feed_eof()

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
            self.loop.call_soon_threadsafe(self.send_event.set)

    def wsgi(self, environ, start_response):
        for chunk in self.app(environ, start_response):
            self.send_queue.append(
                {"type": "http.response.body", "body": chunk, "more_body": True}
            )
            self.loop.call_soon_threadsafe(self.send_event.set)

        self.send_queue.append({"type": "http.response.body", "body": b""})
        self.loop.call_soon_threadsafe(self.send_event.set)
