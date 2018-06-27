import asyncio
from uvicorn.protocols.http import H11Protocol, HttpToolsProtocol
import h11


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


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

    @property
    def has_pending_tasks(self):
        return bool(self.tasks)


def get_connected_protocol(app):
    loop = MockLoop()
    transport = MockTransport()
    protocol = H11Protocol(app, loop)
    protocol.connection_made(transport)
    return protocol


class Echo:
    def __init__(self, scope):
        self.scope = scope

    async def __call__(self, receive, send):
        content = '%s %s' % (self.scope['method'], self.scope['path'])
        content = content.encode()
        if self.scope['method'] == 'POST':
            content += b' '
            while True:
                message = await receive()
                content += message.get('body', b'')
                if not message.get('more_body', False):
                    break

        await send({
            'type': 'http.response.start',
            'status': 200,
            'headers': [
                [b'content-type', b'text/plain'],
                [b'content-length', str(len(content)).encode()],
            ]
        })
        await send({
            'type': 'http.response.body',
            'body': content,
        })



class CloseConnection:
    def __init__(self, scope):
        self.scope = scope

    async def __call__(self, receive, send):
        content = '%s %s' % (self.scope['method'], self.scope['path'])
        content = content.encode()

        await send({
            'type': 'http.response.start',
            'status': 200,
            'headers': [
                [b'content-type', b'text/plain'],
                [b'connection', b'close'],
                [b'content-length', str(len(content)).encode()],
            ]
        })
        await send({
            'type': 'http.response.body',
            'body': content,
        })


def test_get_request():
    protocol = get_connected_protocol(Echo)
    protocol.data_received(b'\r\n'.join([
        b'GET / HTTP/1.1',
        b'Host: example.org',
        b'',
        b''
    ]))
    protocol.loop.run_one()
    assert protocol.transport.buffer == b'\r\n'.join([
        b'HTTP/1.1 200 OK',
        b'content-type: text/plain',
        b'content-length: 5',
        b'',
        b'GET /'
    ])


def test_post_request():
    protocol = get_connected_protocol(Echo)
    protocol.data_received(b'\r\n'.join([
        b'POST / HTTP/1.1',
        b'Host: example.org',
        b'Content-Type: application/json',
        b'Content-Length: 18',
        b'',
        b'{"hello": "world"}'
    ]))
    protocol.loop.run_one()
    assert protocol.transport.buffer == b'\r\n'.join([
        b'HTTP/1.1 200 OK',
        b'content-type: text/plain',
        b'content-length: 25',
        b'',
        b'POST / {"hello": "world"}'
    ])


def test_read_flow_control():
    protocol = get_connected_protocol(Echo)
    protocol.data_received(b'\r\n'.join([
        b'POST / HTTP/1.1',
        b'Host: example.org',
        b'Content-Type: application/json',
        b'Content-Length: 18',
        b'',
        b'{"h'
    ]))
    assert protocol.scope == {
        'type': 'http',
        'http_version': '1.1',
        'server': ('127.0.0.1', 8000),
        'client': ('127.0.0.1', 8001),
        'scheme': 'http',
        'method': 'POST',
        'path': '/',
        'query_string': b'',
        'headers': [
            (b'host', b'example.org'),
            (b'content-type', b'application/json'),
            (b'content-length', b'18'),
        ]
    }
    assert protocol.transport.read_paused
    assert run(protocol.receive()) == {
        'type': 'http.request',
        'body': b'{"h',
        'more_body': True
    }
    assert not protocol.transport.read_paused

    protocol.data_received(b'ello": ')
    assert protocol.transport.read_paused
    assert run(protocol.receive()) == {
        'type': 'http.request',
        'body': b'ello": ',
        'more_body': True
    }
    assert not protocol.transport.read_paused

    protocol.data_received(b'"world"}')
    assert protocol.transport.read_paused
    assert run(protocol.receive()) == {
        'type': 'http.request',
        'body': b'"world"}',
        'more_body': True
    }
    assert not protocol.transport.read_paused

    assert run(protocol.receive()) == {
        'type': 'http.request',
        'body': b'',
        'more_body': False
    }


def test_keepalive():
    # An initial request
    protocol = get_connected_protocol(Echo)
    protocol.data_received(b'\r\n'.join([
        b'GET / HTTP/1.1',
        b'Host: example.org',
        b'',
        b''
    ]))
    protocol.loop.run_one()
    assert protocol.transport.buffer == b'\r\n'.join([
        b'HTTP/1.1 200 OK',
        b'content-type: text/plain',
        b'content-length: 5',
        b'',
        b'GET /'
    ])
    assert not protocol.transport.is_closing()

    # A second request on the same connection
    protocol.transport.buffer = b''
    protocol.data_received(b'\r\n'.join([
        b'GET / HTTP/1.1',
        b'Host: example.org',
        b'',
        b''
    ]))
    protocol.loop.run_one()
    assert not protocol.transport.is_closing()
    assert protocol.transport.buffer == b'\r\n'.join([
        b'HTTP/1.1 200 OK',
        b'content-type: text/plain',
        b'content-length: 5',
        b'',
        b'GET /'
    ])


def test_close():
    protocol = get_connected_protocol(CloseConnection)
    protocol.data_received(b'\r\n'.join([
        b'GET / HTTP/1.1',
        b'Host: example.org',
        b'',
        b''
    ]))
    protocol.loop.run_one()
    assert protocol.transport.buffer == b'\r\n'.join([
        b'HTTP/1.1 200 OK',
        b'content-type: text/plain',
        b'connection: close',
        b'content-length: 5',
        b'',
        b'GET /'
    ])
    assert protocol.transport.is_closing()


def test_pipeline_split_first_request():
    protocol = get_connected_protocol(Echo)
    protocol.data_received(b'\r\n'.join([
        b'POST /1 HTTP/1.1',
        b'Host: example.org',
        b'Content-Type: application/json',
        b'Content-Length: 18',
        b'',
        b'{"hello": "wo'
    ]))
    assert protocol.scope == {
        'type': 'http',
        'http_version': '1.1',
        'server': ('127.0.0.1', 8000),
        'client': ('127.0.0.1', 8001),
        'scheme': 'http',
        'method': 'POST',
        'path': '/1',
        'query_string': b'',
        'headers': [
            (b'host', b'example.org'),
            (b'content-type', b'application/json'),
            (b'content-length', b'18'),
        ]
    }
    # We send back the response immediately, midway through the request data.
    # This tests that the recieve buffer for the first request does not
    # end up being passed to the second instance ASGI app.
    run(protocol.send({
        'type': 'http.response.start',
        'status': 204
    }))
    run(protocol.send({
        'type': 'http.response.body',
        'body': b'',
    }))
    protocol.data_received(b'\r\n'.join([
        b'rld"}'
        b'POST /2 HTTP/1.1',
        b'Host: example.org',
        b'Content-Type: application/json',
        b'Content-Length: 19',
        b'',
        b'{"next": "request"}'
    ]))
    protocol.data_received(b'est"}')
    assert run(protocol.receive()) == {
        'type': 'http.request',
        'body': b'{"next": "request"}',
        'more_body': True
    }
    assert run(protocol.receive()) == {
        'type': 'http.request',
        'body': b'',
        'more_body': False
    }


def test_pipeline_split_second_request():
    protocol = get_connected_protocol(Echo)
    protocol.data_received(b'\r\n'.join([
        b'POST /1 HTTP/1.1',
        b'Host: example.org',
        b'Content-Type: application/json',
        b'Content-Length: 18',
        b'',
        b'{"hello": "world"}'
        b'POST /2 HTTP/1.1',
        b'Host: example.org',
        b'Content-Type: application/json',
        b'Content-Length: 19',
        b'',
        b'{"next": "requ'
    ]))
    assert protocol.scope == {
        'type': 'http',
        'http_version': '1.1',
        'server': ('127.0.0.1', 8000),
        'client': ('127.0.0.1', 8001),
        'scheme': 'http',
        'method': 'POST',
        'path': '/1',
        'query_string': b'',
        'headers': [
            (b'host', b'example.org'),
            (b'content-type', b'application/json'),
            (b'content-length', b'18'),
        ]
    }
    run(protocol.send({
        'type': 'http.response.start',
        'status': 204
    }))
    run(protocol.send({
        'type': 'http.response.body',
        'body': b'',
    }))
    protocol.data_received(b'est"}')
    assert run(protocol.receive()) == {
        'type': 'http.request',
        'body': b'{"next": "request"}',
        'more_body': True
    }
    assert run(protocol.receive()) == {
        'type': 'http.request',
        'body': b'',
        'more_body': False
    }
