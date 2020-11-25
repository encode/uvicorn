import asyncio
import logging
from typing import Any, AsyncIterator, Callable, List, Optional, Tuple
from urllib.parse import unquote

from uvicorn.config import Config
from uvicorn.server import ServerState

from ..concurrency import AsyncioSocket
from ..utils import STATUS_PHRASES, get_path_with_query_string
from .conn_base import HTTPConnection, ProtocolError
from .conn_h11 import H11Connection

try:
    import httptools

    from .conn_httptools import HttpToolsConnection
except ImportError:  # pragma: no cover
    httptools = None  # type: ignore
    HttpToolsConnection = None  # type: ignore

TRACE_LOG_LEVEL = 5
MAX_RECV = 65536


def create_http_connection(config: Config) -> HTTPConnection:
    use_httptools = (
        config.http == "auto" and httptools is not None or config.http == "httptools"
    )
    return HttpToolsConnection() if use_httptools else H11Connection()


async def handle_http11(
    sock: AsyncioSocket,
    server_state: ServerState,
    config: Config,
) -> None:
    if not config.loaded:
        config.load()

    logger = logging.getLogger("uvicorn.error")

    app = config.loaded_app
    conn = create_http_connection(config)
    wrapper = ConnectionWrapper(
        sock,
        conn,
        default_headers=server_state.default_headers,
    )
    server = sock.get_local_addr()
    client = sock.get_remote_addr()
    scheme = "https" if sock.is_ssl else "http"

    server_state.connections.add(wrapper)
    prefix = "%s:%d - " % (client[0], client[1]) if client else ""
    logger.log(TRACE_LOG_LEVEL, "%sConnection made", prefix)

    keepalive = KeepAlive(wrapper, timeout=config.timeout_keep_alive)

    while True:
        try:
            request = await receive_request(wrapper)
            if request is None:
                break  # Client has disconnected.
            http_version, method, path, headers = request
            stream = await receive_request_body(wrapper)
            await asgi_send_response(
                app,
                wrapper,
                scheme=scheme,
                method=method,
                path=path,
                headers=headers,
                stream=stream,
                server=server,
                client=client,
                root_path=config.root_path,
                access_log=config.access_log,
            )
        except ProtocolError:
            logger.warning("Invalid HTTP request received.")
        except Exception as exc:
            logger.exception("Error while responding to request: %s", exc)
            await maybe_send_error_response(wrapper, conn)
        else:
            server_state.total_requests += 1

        # Deal with Keep-Alive.

        if conn.state == "MUST_CLOSE":
            # Not reusable -- shut down.
            break

        try:
            conn.start_next_cycle()
        except ProtocolError:
            # We thought keep-alive was possible, but it's not -- abandon ship!
            await maybe_send_error_response(wrapper, conn)
            break
        else:
            keepalive.reset()
            keepalive.schedule()

    # Clean up.
    keepalive.reset()
    await wrapper.shutdown_and_clean_up()
    server_state.connections.discard(wrapper)
    logger.log(TRACE_LOG_LEVEL, "%sConnection lost", prefix)


class ConnectionWrapper:
    def __init__(
        self,
        sock: AsyncioSocket,
        conn: HTTPConnection,
        default_headers: List[Tuple[bytes, bytes]],
    ) -> None:
        self._sock = sock
        self._conn = conn
        self._logger = logging.getLogger("uvicorn.error")
        self._default_headers = default_headers

    def prepare_headers(
        self, headers: List[Tuple[bytes, bytes]]
    ) -> List[Tuple[bytes, bytes]]:
        return self._default_headers + headers

    async def _read_from_peer(self) -> None:
        if self._conn.is_client_waiting_for_100_continue:
            await self.send_event({"type": "InformationalResponse"})

        data = await self._sock.read(MAX_RECV)
        self._conn.receive_data(data)

    async def receive_event(self) -> Any:
        while True:
            try:
                event = self._conn.next_event()
            except ProtocolError:
                raise

            if event["type"] == "NEED_DATA":
                await self._read_from_peer()
                continue

            return event

    async def send_event(self, event: Any) -> None:
        data = self._conn.send(event)
        if data is None:
            assert event["type"] == "ConnectionClosed"
            await self._sock.write(b"")
            await self.shutdown_and_clean_up()
        else:
            await self._sock.write(data)

    async def trigger_shutdown(self) -> None:
        if self._conn.state in {"IDLE", "DONE"}:
            await self.send_event({"type": "ConnectionClosed"})

    async def shutdown_and_clean_up(self) -> None:
        self._sock.send_eof()

        # Wait and read for a bit to give them a chance to see that we closed
        # things, but eventually give up and just close the socket.
        async def attempt_read_until_eof() -> None:
            try:
                while True:
                    got = await self._sock.read(MAX_RECV)
                    if not got:
                        break
            except Exception:
                pass

        try:
            await asyncio.wait_for(attempt_read_until_eof(), 5)
        except asyncio.TimeoutError:
            pass
        finally:
            await self._sock.aclose()


# Request/response helpers.


async def receive_request(
    wrapper: ConnectionWrapper,
) -> Optional[Tuple[bytes, bytes, bytes, List[Tuple[bytes, bytes]]]]:
    event = await wrapper.receive_event()

    if event["type"] == "ConnectionClosed":
        return None

    assert event["type"] == "Request"

    http_version: bytes = event["http_version"]
    method: bytes = event["method"]
    path: bytes = event["target"]
    headers = [(key.lower(), value) for key, value in event["headers"]]

    return (http_version, method, path, headers)


async def receive_request_body(wrapper: ConnectionWrapper) -> AsyncIterator[bytes]:
    async def receive_data() -> bytes:
        event = await wrapper.receive_event()
        if event["type"] == "EndOfMessage":
            return b""
        assert event["type"] == "Data"
        return event["data"]

    async def request_body(data: bytes) -> AsyncIterator[bytes]:
        while data:
            yield data
            data = await receive_data()

    # Read at least one event so that we get a chance of seeing `EndOfMessage`
    # right away in case the client does not send a body (eg HEAD or GET requests).
    initial = await receive_data()

    return request_body(initial)


async def send_response(
    wrapper: ConnectionWrapper,
    status_code: int,
    headers: List[Tuple[bytes, bytes]],
    reason: bytes = b"",
) -> None:
    if not reason:
        reason = STATUS_PHRASES[status_code]
    headers = wrapper.prepare_headers(headers)
    event = {
        "type": "Response",
        "status_code": status_code,
        "headers": headers,
        "reason": reason,
    }
    await wrapper.send_event(event)


async def send_response_body(wrapper: ConnectionWrapper, body: bytes) -> None:
    if body:
        event = {"type": "Data", "data": body}
    else:
        event = {"type": "EndOfMessage"}
    await wrapper.send_event(event)


async def send_simple_response(
    wrapper: ConnectionWrapper, status_code: int, content_type: str, body: bytes
) -> None:
    headers = [
        (b"Content-Type", content_type.encode("utf-8")),
        (b"Content-Length", str(len(body)).encode("utf-8")),
    ]
    await send_response(wrapper, status_code=status_code, headers=headers)
    await wrapper.send_event({"type": "Data", "data": body})
    await wrapper.send_event({"type": "EndOfMessage"})


async def maybe_send_error_response(
    wrapper: ConnectionWrapper, conn: HTTPConnection
) -> None:
    if conn.state not in {"IDLE", "SEND_BODY"}:
        return  # Not much we can do.

    status_code = 500
    content_type = "text/plain; charset=utf-8"
    body = b"Internal Server Error"
    try:
        await send_simple_response(wrapper, status_code, content_type, body)
    except Exception:
        pass


# ASGI response helpers.


async def asgi_send_response(
    app: Callable,
    wrapper: ConnectionWrapper,
    *,
    scheme: str,
    method: bytes,
    path: bytes,
    headers: List[Tuple[bytes, bytes]],
    stream: AsyncIterator[bytes],
    server: Tuple[str, int] = None,
    client: Tuple[str, int] = None,
    root_path: str = "",
    access_log: bool = True,
) -> None:
    raw_path, _, query_string = path.partition(b"?")

    scope = {
        "type": "http",
        "asgi": {
            "version": "3.0",
            "spec_version": "2.1",
        },
        "http_version": "1.1",
        "server": server,
        "client": client,
        "scheme": scheme,
        "method": method.decode("ascii"),
        "root_path": root_path,
        "path": unquote(raw_path.decode("ascii")),
        "raw_path": raw_path,
        "query_string": query_string,
        "headers": headers,
    }

    responder = ASGIResponder(
        wrapper,
        scope=scope,
        stream=stream,
        access_log=access_log,
    )

    await responder.run_asgi(app)


class ASGIResponder:
    def __init__(
        self,
        wrapper: ConnectionWrapper,
        scope: dict,
        stream: AsyncIterator[bytes],
        access_log: bool,
    ) -> None:
        self._wrapper = wrapper
        self._scope = scope
        self._stream = stream
        self._access_log = access_log

        self._logger = logging.getLogger("uvicorn.error")
        self._access_logger = logging.getLogger("uvicorn.access")

        self._response_started = False
        self._response_complete = False

    # ASGI exception wrapper
    async def run_asgi(self, app: Callable) -> None:
        try:
            result = await app(self._scope, self._receive, self._send)
        except Exception:
            raise

        if result is not None:
            raise RuntimeError(
                f"ASGI callable should return None, but returned {result!r}."
            )

        if not self._response_started:
            raise RuntimeError("ASGI callable returned without starting response.")

        if not self._response_complete:
            raise RuntimeError("ASGI callable returned without completing response.")

    async def _send_response(self, message: dict) -> None:
        if message["type"] != "http.response.start":
            raise RuntimeError(
                "Expected ASGI message 'http.response.start', "
                f"but got {message['type']!r}."
            )

        self._response_started = True

        status_code = message["status"]
        headers = message.get("headers", [])
        reason = STATUS_PHRASES[status_code]

        if self._access_log:
            self._access_logger.info(
                '%s - "%s %s HTTP/%s" %d',
                self._scope["client"],
                self._scope["method"],
                get_path_with_query_string(self._scope),
                self._scope["http_version"],
                status_code,
                extra={"status_code": status_code, "scope": self._scope},
            )

        await send_response(
            self._wrapper, status_code=status_code, headers=headers, reason=reason
        )

    async def _send_response_body(self, message: dict) -> None:
        if message["type"] != "http.response.body":
            msg = "Expected ASGI message 'http.response.body', but got '%s'."
            raise RuntimeError(msg % message["type"])

        body = message.get("body", b"")
        more_body = message.get("more_body", False)

        if self._scope["method"] == "HEAD":
            body = b""

        await send_response_body(self._wrapper, body)

        if not more_body:
            if body != b"":
                await send_response_body(self._wrapper, b"")
            self._response_complete = True

    # ASGI interface

    async def _send(self, message: dict) -> None:
        if not self._response_started:
            await self._send_response(message)

        elif not self._response_complete:
            await self._send_response_body(message)

        else:
            # Response already sent
            msg = "Unexpected ASGI message '%s' sent, after response already completed."
            raise RuntimeError(msg % message["type"])

    async def _receive(self) -> dict:
        if self._response_complete:
            return {"type": "http.disconnect"}

        try:
            chunk = await self._stream.__anext__()
        except StopAsyncIteration:
            chunk = b""
            more_body = False
        else:
            more_body = True

        return {
            "type": "http.request",
            "body": chunk,
            "more_body": more_body,
        }


# Keep-alive.


class KeepAlive:
    def __init__(self, wrapper: ConnectionWrapper, timeout: float) -> None:
        self._wrapper = wrapper
        self._timeout = timeout
        self._loop = asyncio.get_event_loop()
        self._keepalive_task: Optional[asyncio.Task] = None

    def reset(self) -> None:
        if self._keepalive_task is not None:
            self._keepalive_task.cancel()
            self._keepalive_task = None

    def schedule(self) -> None:
        assert self._keepalive_task is None
        self._keepalive_task = self._loop.create_task(self._run())

    async def _run(self) -> None:
        await asyncio.sleep(self._timeout)
        await self._wrapper.trigger_shutdown()
