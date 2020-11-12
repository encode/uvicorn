import asyncio
from typing import Generator, Any, Set

from quart import Quart, request as qrequest

from starlette.applications import Starlette
from starlette.responses import Response
import uvicorn

qapp = Quart(__name__)
sapp = Starlette()


@sapp.route('/', methods=['POST'])
async def starlette(request):
    data = await request.body()
    return Response(data)


@qapp.route('/', methods=['POST'])
async def quart():
    data = await qrequest.get_data()
    return data
    # return data, 200, {'Connection': 'close'}


async def aapp(scope, receive, send):
    if scope["type"] == "http":
        asgi_handler = ASGIHTTPConnection()
        await asgi_handler(receive, send)


class ASGIHTTPConnection:

    def __init__(self):
        self.body = Body()

    async def __call__(self, receive, send):
        receiver_task = asyncio.ensure_future(self.handle_messages(self.body, receive))
        handler_task = asyncio.ensure_future(self.handle_request(self.body, send))
        done, pending = await asyncio.wait(
            [handler_task, receiver_task], return_when=asyncio.FIRST_COMPLETED
        )
        await self._cancel_tasks(pending)

    async def _cancel_tasks(self, tasks: Set[asyncio.Future]) -> None:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def handle_messages(self, body, receive) -> None:
        while True:
            message = await receive()
            if message["type"] == "http.request":
                body.append(message.get("body", b""))
                if not message.get("more_body", False):
                    body.set_complete()
            elif message["type"] == "http.disconnect":
                return

    async def handle_request(self, body, send) -> None:
        data = await body
        await send({
            'type': 'http.response.start',
            'status': 200,
            'headers': [(b'content-length', b"%d" % len(data))],
        })
        await send({
            'type': 'http.response.body',
            'body': data,
            'more_body': False,
        })


class Body:

    def __init__(self) -> None:
        self._data = bytearray()
        self._complete: asyncio.Event = asyncio.Event()

    def __await__(self) -> Generator[Any, None, Any]:
        yield from self._complete.wait().__await__()
        return bytes(self._data)

    def append(self, data: bytes) -> None:
        self._data.extend(data)

    def set_complete(self) -> None:
        self._complete.set()


async def wait_for_disconnect(receive):
    while True:
        p = await receive()
        if p['type'] == 'http.disconnect':
            print('Disconnected!')
            break


async def app748(scope, receive, send):
    await asyncio.sleep(0.2)
    m = await receive()

    if m['type'] == 'lifespan.startup':
        await send({'type': 'lifespan.startup.complete'})
    elif m['type'] == 'http.request':
        if scope['path'] == '/foo':
            asyncio.create_task(wait_for_disconnect(receive))
            await asyncio.sleep(0.2)

        await send({'type': 'http.response.start', 'status': 404})
        await send({'type': 'http.response.body', 'body': b'Not found!\n'})

if __name__ == '__main__':
    # uvicorn.run("846_quart_race:app748", log_level="trace")
    # uvicorn.run("846_quart_race:aapp", log_level="trace")
    uvicorn.run("846_quart_race:qapp", log_level="trace")
    # uvicorn.run("846_quart_race:sapp", log_level="trace")


