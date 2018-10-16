import asyncio

from uvicorn.config import Config
from uvicorn.loops.auto import auto_loop_setup
from uvicorn.main import ServerState
from uvicorn.protocols.http.auto import AutoHTTPProtocol
from uvicorn.protocols.websockets.auto import AutoWebSocketsProtocol

try:
    import uvloop
except ImportError:
    uvloop = None

try:
    import httptools
except ImportError:
    httptools = None

try:
    import websockets
except ImportError:  # Note that when this happens, the websocket tests are skipped
    websockets = None


# TODO: Add pypy to our testing matrix, and assert we get the correct classes
#       dependent on the platform we're running the tests under.


def test_loop_auto():
    loop = auto_loop_setup()
    policy = asyncio.get_event_loop_policy()
    assert isinstance(policy, asyncio.events.BaseDefaultEventLoopPolicy)
    if uvloop is None:
        assert type(policy).__module__.startswith("asyncio")
    else:
        assert isinstance(policy, uvloop.EventLoopPolicy)
        assert type(policy).__module__.startswith("uvloop")


def test_http_auto():
    config = Config(app=None)
    server_state = ServerState()
    protocol = AutoHTTPProtocol(config=config, server_state=server_state)
    if httptools is None:
        assert type(protocol).__name__ == "H11Protocol"
    else:
        assert type(protocol).__name__ == "HttpToolsProtocol"


def test_websocket_auto():
    config = Config(app=None)
    server_state = ServerState()
    protocol = AutoWebSocketsProtocol(config=config, server_state=server_state)
    if websockets is None:
        assert type(protocol).__name__ == "WSProtocol"
    else:
        assert type(protocol).__name__ == "WebSocketProtocol"
