import logging
from typing import AsyncIterator, Awaitable, Callable

from .backends.auto import AutoBackend
from .base import BaseHTTPConnection
from .utils import STATUS_PHRASES, get_path_with_query_string


class ASGIRequestResponseCycle:
    def __init__(
        self,
        conn: BaseHTTPConnection,
        scope: dict,
        request_body: AsyncIterator[bytes],
        send_response_body: Callable[[bytes], Awaitable[None]],
        access_log: bool,
    ) -> None:
        self._conn = conn
        self._scope = scope
        self._request_body = request_body
        self._do_send_response_body = send_response_body
        self._access_log = access_log

        self._backend = AutoBackend()
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
            msg = "ASGI callable should return None, but returned '%s'."
            raise RuntimeError(msg % result)

        if not self._response_started:
            msg = "ASGI callable returned without starting response."
            raise RuntimeError(msg)

        if not self._response_complete:
            msg = "ASGI callable returned without completing response."
            raise RuntimeError(msg)

    async def _send_response(self, message: dict) -> None:
        if message["type"] != "http.response.start":
            msg = "Expected ASGI message 'http.response.start', but got '%s'."
            raise RuntimeError(msg % message["type"])

        self._response_started = True
        self._waiting_for_100_continue = False

        status_code = message["status"]
        headers = self._conn.basic_headers() + message.get("headers", [])
        reason = STATUS_PHRASES[status_code]

        if self._access_log:
            self._access_logger.info(
                '%s - "%s %s HTTP/%s" %d',
                self._conn.client,
                self._scope["method"],
                get_path_with_query_string(self._scope),
                self._scope["http_version"],
                status_code,
                extra={"status_code": status_code, "scope": self._scope},
            )

        await self._conn.send_response(
            status_code=status_code, headers=headers, reason=reason
        )

    async def _send_response_body(self, message: dict) -> None:
        if message["type"] != "http.response.body":
            msg = "Expected ASGI message 'http.response.body', but got '%s'."
            raise RuntimeError(msg % message["type"])

        body = message.get("body", b"")
        more_body = message.get("more_body", False)

        if self._scope["method"] == "HEAD":
            body = b""

        await self._do_send_response_body(body)

        if not more_body:
            if body != b"":
                await self._do_send_response_body(b"")
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
            chunk = await self._request_body.__anext__()
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
