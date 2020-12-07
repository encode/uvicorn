import asyncio

from uvicorn.config import Config
from uvicorn.loops.auto import auto_loop_setup
from uvicorn.main import ServerState
from uvicorn.protocols.http.auto import AutoHTTPProtocol
from uvicorn.protocols.websockets.auto import AutoWebSocketsProtocol

try:
    import uvloop
except ImportError:  # pragma: no cover
    uvloop = None

try:
    import httptools
except ImportError:  # pragma: no cover
    httptools = None

try:
    import websockets
except ImportError:  # pragma: no cover
    # Note that we skip the websocket tests completely in this case.
    websockets = None


async def app(scope, receive, send):
    pass  # pragma: no cover


# TODO: Add pypy to our testing matrix, and assert we get the correct classes
#       dependent on the platform we're running the tests under.


def test_loop_auto():
    auto_loop_setup()
    policy = asyncio.get_event_loop_policy()
    assert isinstance(policy, asyncio.events.BaseDefaultEventLoopPolicy)
    expected_loop = "asyncio" if uvloop is None else "uvloop"
    assert type(policy).__module__.startswith(expected_loop)


def test_http_auto():
    config = Config(app=app)
    server_state = ServerState()
    protocol = AutoHTTPProtocol(config=config, server_state=server_state)
    expected_http = "H11Protocol" if httptools is None else "HttpToolsProtocol"
    assert type(protocol).__name__ == expected_http


def test_websocket_auto():
    config = Config(app=app)
    server_state = ServerState()
    protocol = AutoWebSocketsProtocol(config=config, server_state=server_state)
    expected_websockets = "WSProtocol" if websockets is None else "WebSocketProtocol"
    assert type(protocol).__name__ == expected_websockets
