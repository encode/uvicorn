import contextlib
import typing

import httpx
import wsproto
from httpx._types import (
    AuthTypes,
    CertTypes,
    CookieTypes,
    HeaderTypes,
    ProxiesTypes,
    QueryParamTypes,
    TimeoutTypes,
    URLTypes,
    VerifyTypes,
    RequestExtensions,
)
from httpx._config import (
    DEFAULT_LIMITS,
    DEFAULT_MAX_REDIRECTS,
    DEFAULT_TIMEOUT_CONFIG,
    Limits,
)
from httpx import AsyncBaseTransport


class ConnectionClosed(Exception):
    pass


class WebsocketConnection:
    def __init__(self, network_steam):
        self._ws_connection_state = wsproto.Connection(wsproto.ConnectionType.CLIENT)
        self._network_stream = network_steam
        self._events = []

    async def send(self, text):
        """
        Send a text frame over the websocket connection.
        """
        event = wsproto.events.TextMessage(text)
        data = self._ws_connection_state.send(event)
        await self._network_stream.write(data)

    async def recv(self):
        """
        Receive the next text frame from the websocket connection.
        """
        while not self._events:
            data = await self._network_stream.read(max_bytes=4096)
            self._ws_connection_state.receive_data(data)
            self._events = list(self._ws_connection_state.events())

        event = self._events.pop(0)
        if isinstance(event, wsproto.events.TextMessage):
            return event.data
        elif isinstance(event, wsproto.events.CloseConnection):
            raise ConnectionClosed()

    @property
    def open(self) -> bool:
        return self._ws_connection_state.state == wsproto.ConnectionState.OPEN


@contextlib.asynccontextmanager
async def ws_connect(
    url,
    auth: typing.Optional[AuthTypes] = None,
    params: typing.Optional[QueryParamTypes] = None,
    headers: typing.Optional[HeaderTypes] = None,
    cookies: typing.Optional[CookieTypes] = None,
    verify: VerifyTypes = True,
    cert: typing.Optional[CertTypes] = None,
    http1: bool = True,
    http2: bool = False,
    proxies: typing.Optional[ProxiesTypes] = None,
    mounts: typing.Optional[typing.Mapping[str, AsyncBaseTransport]] = None,
    timeout: TimeoutTypes = DEFAULT_TIMEOUT_CONFIG,
    follow_redirects: bool = False,
    limits: Limits = DEFAULT_LIMITS,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
    event_hooks: typing.Optional[
        typing.Mapping[str, typing.List[typing.Callable[..., typing.Any]]]
    ] = None,
    base_url: URLTypes = "",
    transport: typing.Optional[AsyncBaseTransport] = None,
    app: typing.Optional[typing.Callable[..., typing.Any]] = None,
    trust_env: bool = True,
    default_encoding: typing.Union[str, typing.Callable[[bytes], str]] = "utf-8",
    extensions: typing.Optional[RequestExtensions] = None,
):
    async with httpx.AsyncClient(
        auth=auth,
        params=params,
        headers=headers,
        cookies=cookies,
        verify=verify,
        cert=cert,
        http1=http1,
        http2=http2,
        proxies=proxies,
        mounts=mounts,
        timeout=timeout,
        follow_redirects=follow_redirects,
        limits=limits,
        max_redirects=max_redirects,
        event_hooks=event_hooks,
        base_url=base_url,
        transport=transport,
        app=app,
        trust_env=trust_env,
        default_encoding=default_encoding,
    ) as client:
        async with client.stream(
            "GET", url, headers=headers, extensions=extensions
        ) as response:
            network_steam = response.extensions["network_stream"]
            yield WebsocketConnection(network_steam)
