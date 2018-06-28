import asyncio
from uvicorn.protocols.http import H11Protocol, HttpToolsProtocol
import h11
import pytest
import starlette


SIMPLE_GET_REQUEST = b'\r\n'.join([
    b'GET / HTTP/1.1',
    b'Host: example.org',
    b'',
    b''
])

SIMPLE_POST_REQUEST = b'\r\n'.join([
    b'POST / HTTP/1.1',
    b'Host: example.org',
    b'Content-Type: application/json',
    b'Content-Length: 18',
    b'',
    b'{"hello": "world"}'
])


class MockTransport:
    def __init__(self, sockname=None, peername=None, sslcontext=False):
        self.sockname = ('127.0.0.1', 8000) if sockname is None else sockname
        self.peername = ('127.0.0.1', 8001) if peername is None else peername
        self.sslcontext = sslcontext
        self.closed = False
        self.buffer = b''
        self.read_paused = False

    def get_extra_info(self, key):
        return {
            'sockname': self.sockname,
            'peername': self.peername,
            'sslcontext': self.sslcontext
        }[key]

    def write(self, data):
        assert not self.closed
        self.buffer += data

    def close(self):
        assert not self.closed
        self.closed = True

    def pause_reading(self):
        self.read_paused = True

    def resume_reading(self):
        self.read_paused = False

    def is_closing(self):
        return self.closed


class MockLoop:
    def __init__(self):
        self.tasks = []

    def create_task(self, coroutine):
        self.tasks.insert(0, coroutine)

    def run_one(self):
        coroutine = self.tasks.pop()
        asyncio.get_event_loop().run_until_complete(coroutine)


def get_connected_protocol(app, protocol_cls):
    loop = MockLoop()
    transport = MockTransport()
    protocol = protocol_cls(app, loop)
    protocol.connection_made(transport)
    return protocol


@pytest.mark.parametrize("protocol_cls", [HttpToolsProtocol, H11Protocol])
def test_get_request(protocol_cls):
    def app(scope):
        return starlette.Response('Hello, world', media_type='text/plain')

    protocol = get_connected_protocol(app, protocol_cls)
    protocol.data_received(SIMPLE_GET_REQUEST)
    protocol.loop.run_one()
    assert b'HTTP/1.1 200 OK' in protocol.transport.buffer
    assert b'Hello, world' in protocol.transport.buffer


@pytest.mark.parametrize("protocol_cls", [HttpToolsProtocol, H11Protocol])
def test_post_request(protocol_cls):
    @starlette.asgi_application
    async def app(request):
        body = await request.body()
        return starlette.Response(b'Body: ' + body, media_type='text/plain')

    protocol = get_connected_protocol(app, protocol_cls)
    protocol.data_received(SIMPLE_POST_REQUEST)
    protocol.loop.run_one()
    assert b'HTTP/1.1 200 OK' in protocol.transport.buffer
    assert b'Body: {"hello": "world"}' in protocol.transport.buffer


@pytest.mark.parametrize("protocol_cls", [HttpToolsProtocol, H11Protocol])
def test_keepalive(protocol_cls):
    def app(scope):
        return starlette.Response(b'', status_code=204)

    protocol = get_connected_protocol(app, protocol_cls)
    protocol.data_received(SIMPLE_GET_REQUEST)
    protocol.loop.run_one()
    assert b'HTTP/1.1 204 No Content' in protocol.transport.buffer
    assert not protocol.transport.is_closing()


@pytest.mark.parametrize("protocol_cls", [HttpToolsProtocol, H11Protocol])
def test_close(protocol_cls):
    def app(scope):
        return starlette.Response(b'', status_code=204, headers={'connection': 'close'})

    protocol = get_connected_protocol(app, protocol_cls)
    protocol.data_received(SIMPLE_GET_REQUEST)
    protocol.loop.run_one()
    assert b'HTTP/1.1 204 No Content' in protocol.transport.buffer
    assert protocol.transport.is_closing()


@pytest.mark.parametrize("protocol_cls", [HttpToolsProtocol, H11Protocol])
def test_undersized_request(protocol_cls):
    def app(scope):
        return starlette.Response(b'xxx', headers={'content-length': 10})

    protocol = get_connected_protocol(app, protocol_cls)
    protocol.data_received(SIMPLE_GET_REQUEST)
    protocol.loop.run_one()
    assert protocol.transport.is_closing()


@pytest.mark.parametrize("protocol_cls", [HttpToolsProtocol, H11Protocol])
def test_oversized_request(protocol_cls):
    def app(scope):
        return starlette.Response(b'xxx' * 20, headers={'content-length': 10})

    protocol = get_connected_protocol(app, protocol_cls)
    protocol.data_received(SIMPLE_GET_REQUEST)
    protocol.loop.run_one()
    assert protocol.transport.is_closing()


@pytest.mark.parametrize("protocol_cls", [HttpToolsProtocol, H11Protocol])
def test_app_exception(protocol_cls):
    @starlette.asgi_application
    async def app(request):
        raise Exception()

    protocol = get_connected_protocol(app, protocol_cls)
    protocol.data_received(SIMPLE_GET_REQUEST)
    protocol.loop.run_one()
    assert b'HTTP/1.1 500 Internal Server Error' in protocol.transport.buffer
    assert protocol.transport.is_closing()


@pytest.mark.parametrize("protocol_cls", [HttpToolsProtocol, H11Protocol])
def test_app_init_exception(protocol_cls):
    def app(scope):
        raise Exception()

    protocol = get_connected_protocol(app, protocol_cls)
    protocol.data_received(SIMPLE_GET_REQUEST)
    protocol.loop.run_one()
    assert b'HTTP/1.1 500 Internal Server Error' in protocol.transport.buffer
    assert protocol.transport.is_closing()


@pytest.mark.parametrize("protocol_cls", [HttpToolsProtocol, H11Protocol])
def test_exception_during_response(protocol_cls):
    async def streamer():
        for chunk in [b'1', b'2', b'3']:
            yield chunk
        raise Exception()

    @starlette.asgi_application
    def app(request):
        return starlette.StreamingResponse(streamer())

    protocol = get_connected_protocol(app, protocol_cls)
    protocol.data_received(SIMPLE_GET_REQUEST)
    protocol.loop.run_one()
    assert b'HTTP/1.1 500 Internal Server Error' not in protocol.transport.buffer
    assert protocol.transport.is_closing()


@pytest.mark.parametrize("protocol_cls", [HttpToolsProtocol, H11Protocol])
def test_no_response_returned(protocol_cls):
    class App:
        def __init__(self, scope):
            pass
        async def __call__(self, receive, send):
            pass

    protocol = get_connected_protocol(App, protocol_cls)
    protocol.data_received(SIMPLE_GET_REQUEST)
    protocol.loop.run_one()
    assert b'HTTP/1.1 500 Internal Server Error' in protocol.transport.buffer
    assert protocol.transport.is_closing()


@pytest.mark.parametrize("protocol_cls", [HttpToolsProtocol, H11Protocol])
def test_partial_response_returned(protocol_cls):
    class App:
        def __init__(self, scope):
            pass
        async def __call__(self, receive, send):
            await send({"type": "http.response.start", "status": 200})

    protocol = get_connected_protocol(App, protocol_cls)
    protocol.data_received(SIMPLE_GET_REQUEST)
    protocol.loop.run_one()
    assert b'HTTP/1.1 500 Internal Server Error' not in protocol.transport.buffer
    assert protocol.transport.is_closing()


@pytest.mark.parametrize("protocol_cls", [HttpToolsProtocol, H11Protocol])
def test_duplicate_start_message(protocol_cls):
    class App:
        def __init__(self, scope):
            pass
        async def __call__(self, receive, send):
            await send({"type": "http.response.start", "status": 200})
            await send({"type": "http.response.start", "status": 200})

    protocol = get_connected_protocol(App, protocol_cls)
    protocol.data_received(SIMPLE_GET_REQUEST)
    protocol.loop.run_one()
    assert b'HTTP/1.1 500 Internal Server Error' not in protocol.transport.buffer
    assert protocol.transport.is_closing()


@pytest.mark.parametrize("protocol_cls", [HttpToolsProtocol, H11Protocol])
def test_missing_start_message(protocol_cls):
    class App:
        def __init__(self, scope):
            pass
        async def __call__(self, receive, send):
            await send({"type": "http.response.body", "body": b""})

    protocol = get_connected_protocol(App, protocol_cls)
    protocol.data_received(SIMPLE_GET_REQUEST)
    protocol.loop.run_one()
    assert b'HTTP/1.1 500 Internal Server Error' in protocol.transport.buffer
    assert protocol.transport.is_closing()


@pytest.mark.parametrize("protocol_cls", [HttpToolsProtocol, H11Protocol])
def test_message_after_body_complete(protocol_cls):
    class App:
        def __init__(self, scope):
            pass
        async def __call__(self, receive, send):
            await send({"type": "http.response.start", "status": 200})
            await send({"type": "http.response.body", "body": b""})
            await send({"type": "http.response.body", "body": b""})

    protocol = get_connected_protocol(App, protocol_cls)
    protocol.data_received(SIMPLE_GET_REQUEST)
    protocol.loop.run_one()
    assert b'HTTP/1.1 200 OK' in protocol.transport.buffer
    assert protocol.transport.is_closing()


@pytest.mark.parametrize("protocol_cls", [HttpToolsProtocol, H11Protocol])
def test_value_returned(protocol_cls):
    class App:
        def __init__(self, scope):
            pass
        async def __call__(self, receive, send):
            await send({"type": "http.response.start", "status": 200})
            await send({"type": "http.response.body", "body": b""})
            return 123

    protocol = get_connected_protocol(App, protocol_cls)
    protocol.data_received(SIMPLE_GET_REQUEST)
    protocol.loop.run_one()
    assert b'HTTP/1.1 200 OK' in protocol.transport.buffer
    assert protocol.transport.is_closing()
