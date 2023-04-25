import asyncio
import signal
from asyncio import Event, Task
from functools import partial

import httpx
import pytest

from tests.utils import run_server
from uvicorn import Server
from uvicorn.config import Config


def set_event(event: Event, task: Task):
    event.set()


@pytest.mark.anyio
async def test_sigint_finish_req(unused_tcp_port: int):
    """
    Test that a request that is sent, sigint is sent, but request is finished and not cancelled
    """

    server_event = Event()

    async def wait_app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"start", "more_body": True})
        await server_event.wait()
        await send({"type": "http.response.body", "body": b"end", "more_body": False})

    config = Config(
        app=wait_app, reload=False, port=unused_tcp_port, timeout_graceful_shutdown=1
    )
    server: Server
    async with run_server(config) as server:
        async with httpx.AsyncClient() as client:
            task_complete_event = Event()
            req = asyncio.create_task(client.get(f"http://127.0.0.1:{unused_tcp_port}"))
            req.add_done_callback(partial(set_event, task_complete_event))
            await asyncio.sleep(0.1)  # ensure next tick
            server.handle_exit(sig=signal.SIGINT, frame=None)  # exit
            server_event.set()  # continue request
            # ensure httpx has processed the response and result is complete
            await task_complete_event.wait()
            assert req.result().status_code == 200


@pytest.mark.anyio
async def test_sigint_abort_req_3_11_up(unused_tcp_port: int, caplog):
    """
    Test that a request that is sent, sigint is sent, but request is cancelled since it lasts too long
    """

    async def forever_app(scope, receive, send):
        server_event = Event()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"start", "more_body": True})
        await server_event.wait()  # we never continue this one, so this request will time out
        await send({"type": "http.response.body", "body": b"end", "more_body": False})

    config = Config(
        app=forever_app, reload=False, port=unused_tcp_port, timeout_graceful_shutdown=1
    )
    server: Server
    async with run_server(config) as server:
        async with httpx.AsyncClient() as client:
            task_complete_event = Event()
            req = asyncio.create_task(client.get(f"http://127.0.0.1:{unused_tcp_port}"))
            req.add_done_callback(partial(set_event, task_complete_event))
            await asyncio.sleep(0.1)  # next tick
            # trigger exit, this request should time out in ~1 sec
            server.handle_exit(sig=signal.SIGINT, frame=None)
            await task_complete_event.wait()
    with pytest.raises(httpx.RemoteProtocolError):
        req.result()
    assert (
        "Cancel 1 running task(s), timeout_graceful_shutdown exceeded"
        in caplog.messages
    )


@pytest.mark.anyio
async def test_sigint_deny_request_after_triggered(unused_tcp_port: int):
    """
    Test that sigint is sent, and that the server denies further requests
    """

    async def app(scope, receive, send):
        pass

    config = Config(
        app=app, reload=False, port=unused_tcp_port, timeout_graceful_shutdown=1
    )
    server: Server
    async with run_server(config) as server:
        server.handle_exit(
            sig=signal.SIGINT, frame=None
        )  # exit and ensure we do not accept more requests
        async with httpx.AsyncClient() as client:
            with pytest.raises(httpx.ConnectError):
                await client.get(f"http://127.0.0.1:{unused_tcp_port}")
