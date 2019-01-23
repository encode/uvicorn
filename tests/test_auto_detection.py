import asyncio

import uvloop

from uvicorn.config import Config
from uvicorn.loops.auto import auto_loop_setup
from uvicorn.main import ServerState
from uvicorn.protocols.http.auto import AutoHTTPProtocol
from uvicorn.protocols.http.httptools_impl import HttpToolsProtocol

# TODO: Add pypy to our testing matrix, and assert we get the correct classes
#       dependent on the platform we're running the tests under.


def test_http_auto():
    config = Config(app=None)
    server_state = ServerState()
    protocol = AutoHTTPProtocol(config=config, server_state=server_state)
    assert isinstance(protocol, HttpToolsProtocol)


def test_loop_auto():
    loop = auto_loop_setup()
    assert isinstance(asyncio.get_event_loop_policy(), uvloop.EventLoopPolicy)
