import asyncio

import pytest

from uvicorn.config import Config
from uvicorn.loops.auto import auto_loop_setup
from uvicorn.main import ServerState
from uvicorn.protocols.http.auto import AutoHTTPProtocol
from uvicorn.protocols.websockets.auto import AutoWebSocketsProtocol

pytest.importorskip("uvloop")
pytest.importorskip("httptools")
pytest.importorskip("websockets")


async def app(scope, receive, send):
    pass  # pragma: no cover


# TODO: Add pypy to our testing matrix, and assert we get the correct classes
#       dependent on the platform we're running the tests under.


def test_loop_auto():
    auto_loop_setup()
    policy = asyncio.get_event_loop_policy()
    assert isinstance(policy, asyncio.events.BaseDefaultEventLoopPolicy)
    assert type(policy).__module__.startswith("uvloop")


@pytest.mark.anyio
async def test_http_auto():
    config = Config(app=app)
    server_state = ServerState()
    protocol = AutoHTTPProtocol(config=config, server_state=server_state, app_state={})  # type: ignore[call-arg]
    assert type(protocol).__name__ == "HttpToolsProtocol"


@pytest.mark.anyio
async def test_websocket_auto():
    config = Config(app=app)
    server_state = ServerState()

    assert AutoWebSocketsProtocol is not None
    protocol = AutoWebSocketsProtocol(
        config=config, server_state=server_state, app_state={}
    )
    assert type(protocol).__name__ == "WebSocketProtocol"
