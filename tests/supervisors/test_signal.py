import asyncio
import signal

import httpx
import pytest

from tests.utils import run_server
from uvicorn import Server
from uvicorn.config import Config

async def app(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"start", "more_body": True})
    await asyncio.sleep(2)
    await send({"type": "http.response.body", "body": b"end", "more_body": False})


@pytest.mark.anyio
async def test_x(unused_tcp_port: int):
    """
    * Start server
    * Send request 1
    * Sleep 1 sec
    * Send request 2
    * Send SIGINT (grace configured to 1 second)
    * Sleep 1 sec, ensure one tick
    * Request 1 should be finished 200 OK
    * Request 2 should be cancelled, since it did not complete in the 1 second
    * Request 3 should fail, since app never accepted requests at that point
    """
    config = Config(app=app, reload=False, port=unused_tcp_port, timeout_graceful_shutdown=1)
    server: Server
    async with run_server(config) as server:
        async with httpx.AsyncClient() as client:
            r1 = asyncio.create_task(client.get(f"http://127.0.0.1:{unused_tcp_port}"))  # success
            await asyncio.sleep(1)  # ensure next request should time out
            r2 = asyncio.create_task(client.get(f"http://127.0.0.1:{unused_tcp_port}"))  # cancelled
            server.handle_exit(sig=signal.SIGINT, frame=None)
            await asyncio.sleep(1)  # ensure one tick pass, and that server does not accept requests
            r3 = asyncio.create_task(client.get(f"http://127.0.0.1:{unused_tcp_port}"))  # connect error
            await asyncio.sleep(1)  # ensure one more tick pass, and everything has been handled
            assert r1.result().status_code == 200
            with pytest.raises(httpx.ConnectTimeout):  # fix this.. task is not cancelled, test fails
                r2.result()
            with pytest.raises(httpx.ConnectError):
                r3.result()