import logging
from typing import AsyncIterator, List, Tuple
from urllib.parse import unquote

from uvicorn.config import Config

from ..asgi import ASGIRequestResponseCycle
from ..backends.base import AsyncSocket
from ..exceptions import BrokenSocket, ProtocolError
from ..state import ServerState
from .connection import HTTP11Connection
from .keepalive import KeepAlive
from .parsers.h11 import H11Parser

try:
    import httptools

    from .parsers.httptools import HttpToolsParser
except ImportError:  # pragma: no cover
    httptools = None  # type: ignore
    HttpToolsParser = None  # type: ignore


def create_http11_connection(
    sock: AsyncSocket, state: ServerState, config: Config
) -> HTTP11Connection:
    use_httptools = config.http == "httptools" or (
        config.http == "auto" and httptools is not None
    )
    parser = HttpToolsParser() if use_httptools else H11Parser()
    return HTTP11Connection(sock, default_headers=state.default_headers, parser=parser)


async def handle_http11(sock: AsyncSocket, state: ServerState, config: Config) -> None:
    if not config.loaded:
        config.load()

    logger = logging.getLogger("uvicorn.error")

    conn = create_http11_connection(sock, state, config)
    keepalive = KeepAlive(conn, config)
    state.connections.add(conn)
    conn.debug("Connection made")

    while True:
        assert conn.states() == {"client": "IDLE", "server": "IDLE"}
        try:
            (
                http_version,
                method,
                path,
                headers,
                upgrade,
            ) = await conn.read_request()
            assert http_version == b"1.1", http_version
            assert upgrade is None, "WebSocket not supported yet"
            request_body = await conn.aiter_request_body()
            await send_h11_response(
                conn,
                config=config,
                method=method,
                path=path,
                headers=headers,
                request_body=request_body,
            )
        except BrokenSocket:
            break
        except Exception as exc:
            logger.error("Error while responding to request: %s", exc, exc_info=exc)
            await maybe_send_error_response(conn)
        else:
            state.total_requests += 1

        states = conn.states()
        if states["server"] == "MUST_CLOSE":
            conn.trace("Connection is not reusable, shutting down")
            break

        conn.trace("Trying to reuse connection")
        try:
            conn.set_keepalive()
        except ProtocolError as exc:
            conn.trace("Connection is not reusable, bailing out: %s ", exc)
            await maybe_send_error_response(conn)
            break
        else:
            await keepalive.reset()
            await keepalive.schedule()
            conn.debug("Connection kept alive")

    await keepalive.aclose()
    await conn.shutdown_and_clean_up()
    state.connections.discard(conn)
    conn.debug("Connection closed")


async def send_h11_response(
    conn: HTTP11Connection,
    *,
    config: Config,
    method: bytes,
    path: bytes,
    headers: List[Tuple[bytes, bytes]],
    request_body: AsyncIterator[bytes],
) -> None:
    conn.trace("Sending response")

    raw_path, _, query_string = path.partition(b"?")

    scope = {
        "type": "http",
        "asgi": {
            "version": "3.0",
            "spec_version": "2.1",
        },
        "http_version": "1.1",
        "server": conn.server,
        "client": conn.client,
        "scheme": conn.scheme,
        "method": method.decode("ascii"),
        "root_path": config.root_path,
        "path": unquote(raw_path.decode("ascii")),
        "raw_path": raw_path,
        "query_string": query_string,
        "headers": headers,
    }

    send_response_body = conn.send_response_body

    cycle = ASGIRequestResponseCycle(
        conn,
        scope=scope,
        request_body=request_body,
        send_response_body=send_response_body,
        access_log=config.access_log,
    )

    app = config.loaded_app

    await cycle.run_asgi(app)


async def maybe_send_error_response(conn: HTTP11Connection) -> None:
    states = conn.states()
    if states["server"] not in {"IDLE", "ACTIVE"}:
        return

    conn.trace("send error response")
    status_code = 500
    content_type = "text/plain; charset=utf-8"
    body = b"Internal Server Error"
    try:
        await conn.send_simple_response(status_code, content_type, body)
    except Exception as exc:
        conn.trace("error while sending error response: %s", exc)
