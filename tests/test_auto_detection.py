from uvicorn.protocols.http.httptools import HttpToolsProtocol
from uvicorn.protocols.http.auto import AutoHTTPProtocol
from uvicorn.loops.auto import auto_loop_setup
import asyncio
import uvloop

# TODO: Add pypy to our testing matrix, and assert we get the correct classes
#       dependent on the platform we're running the tests under.


def test_http_auto():
    protocol = AutoHTTPProtocol(app=None)
    assert isinstance(protocol, HttpToolsProtocol)


def test_loop_auto():
    loop = auto_loop_setup()
    assert isinstance(asyncio.get_event_loop_policy(), uvloop.EventLoopPolicy)
