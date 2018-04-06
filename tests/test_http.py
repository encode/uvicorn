from collections import namedtuple
from uvicorn.protocols.http import HttpProtocol
import asyncio


# Utils...

class MockLoop(object):
    def create_task(self, *args):
        pass


class MockTransport(object):
    content = b''
    closed = False

    def close(self):
        self.closed = True

    def write(self, content):
        self.content += content

    def get_extra_info(self, name):
        if name == 'sockname':
            return ('127.0.0.1', 8000)
        elif name == 'peername':
            return ('123.456.789.0', 1234)
        return None


def mock_consumer(scope):
    def mock_asgi(receive, send):
        pass
    return mock_asgi


def get_protocol():
    loop = MockLoop()
    transport = MockTransport()
    protocol = HttpProtocol(mock_consumer, loop)
    protocol.connection_made(transport)
    return protocol


def run_coroutine(coroutine):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coroutine)


def read_body(request):
    body = b''
    while True:
        message = run_coroutine(request.receive())
        body += message.get('body', b'')
        if not message.get('more_body', False):
            break
    return body


# Test cases...

def test_get_request():
    protocol = get_protocol()
    protocol.data_received(b'GET / HTTP/1.1\r\nHost: example.org\r\n\r\n')

    assert protocol.active_request is not None
    request = protocol.active_request
    assert request.scope['method'] == 'GET'
    assert request.scope['path'] == '/'
    assert request.scope['headers'] == [[b'host', b'example.org']]

    run_coroutine(request.send({
        'type': 'http.response.start',
        'status': 200,
        'headers': [
            [b'content-length', b'3']
        ]
    }))
    run_coroutine(request.send({
        'type': 'http.response.body',
        'body': b'abc'
    }))

    output = protocol.transport.content
    assert b'content-length: 3' in output
    assert output.endswith(b'abc')


def test_post_request():
    protocol = get_protocol()
    protocol.data_received(b'POST / HTTP/1.1\r\nContent-Length: 12\r\n\r\nHello, ')
    protocol.data_received(b'world')

    assert protocol.active_request is not None
    request = protocol.active_request
    assert request.scope['method'] == 'POST'
    assert request.scope['path'] == '/'

    body = read_body(request)
    assert body == b'Hello, world'


def test_pipelined_request():
    protocol = get_protocol()
    protocol.data_received(
        b'GET /1 HTTP/1.1\r\nHost: example.org\r\n\r\n'
        b'GET /2 HTTP/1.1\r\nHost: example.org\r\n\r\n'
        b'GET /3 HTTP/1.1\r\nHost: example.org\r\n\r\n'
    )

    assert protocol.active_request is not None
    assert len(protocol.pending_requests) == 2
    request = protocol.active_request
    assert request.scope['method'] == 'GET'
    assert request.scope['path'] == '/1'
    assert request.scope['headers'] == [[b'host', b'example.org']]

    run_coroutine(request.send({
        'type': 'http.response.start',
        'status': 204,
    }))
    run_coroutine(request.send({
        'type': 'http.response.body',
    }))

    assert protocol.active_request is not None
    assert len(protocol.pending_requests) == 1
    request = protocol.active_request
    assert request.scope['method'] == 'GET'
    assert request.scope['path'] == '/2'
    assert request.scope['headers'] == [[b'host', b'example.org']]

    run_coroutine(request.send({
        'type': 'http.response.start',
        'status': 204,
    }))
    run_coroutine(request.send({
        'type': 'http.response.body',
    }))

    assert protocol.active_request is not None
    assert len(protocol.pending_requests) == 0
    request = protocol.active_request
    assert request.scope['method'] == 'GET'
    assert request.scope['path'] == '/3'
    assert request.scope['headers'] == [[b'host', b'example.org']]

    run_coroutine(request.send({
        'type': 'http.response.start',
        'status': 204,
    }))
    run_coroutine(request.send({
        'type': 'http.response.body',
    }))

    assert protocol.active_request is None
    assert len(protocol.pending_requests) == 0


# def test_release_request_body():
#     protocol = get_protocol()
#     protocol.data_received(b'POST / HTTP/1.1\r\nContent-Length: 100\r\n\r\n')
#
#     # Send half of the request body.
#     for idx in range(5):
#         protocol.data_received(b'0123456789')
#     assert protocol.buffer_size == 50
#
#     # Sending the response should release the buffer.
#     message, channels = protocol.active_request
#     run_coroutine(channels['reply'].send({'status': 204}))
#     assert protocol.buffer_size == 0
#
#     # Sending the remaining request body shouldn't buffer any more data.
#     for idx in range(5):
#         protocol.data_received(b'0123456789')
#     assert protocol.buffer_size == 0


def test_chunked_response():
    protocol = get_protocol()
    protocol.data_received(b'GET /1 HTTP/1.1\r\nHost: example.org\r\n\r\n')

    assert protocol.active_request is not None
    request = protocol.active_request

    run_coroutine(request.send({
        'type': 'http.response.start',
        'status': 200,
    }))
    run_coroutine(request.send({
        'type': 'http.response.body',
        'body': b'123',
        'more_body': True
    }))
    run_coroutine(request.send({
        'type': 'http.response.body',
        'body': b'456',
        'more_body': True
    }))
    run_coroutine(request.send({
        'type': 'http.response.body',
        'body': b'789',
    }))

    output = protocol.transport.content
    assert b'transfer-encoding: chunked\r\n' in output
    assert output.endswith(b'3\r\n123\r\n3\r\n456\r\n3\r\n789\r\n0\r\n\r\n')


def test_client_connection_close():
    protocol = get_protocol()
    protocol.data_received(b'GET /1 HTTP/1.1\r\nHost: example.org\r\n\r\n')
    transport = protocol.transport

    assert protocol.active_request is not None
    request = protocol.active_request

    run_coroutine(request.send({
        'type': 'http.response.start',
        'status': 204,
        'headers': [
            [b'connection', b'close']
        ]
    }))
    run_coroutine(request.send({
        'type': 'http.response.body',
    }))

    assert transport.closed
    #assert protocol.transport is None


def test_server_connection_close():
    protocol = get_protocol()
    protocol.data_received(b'GET /1 HTTP/1.1\r\nConnection: close\r\n\r\n')
    transport = protocol.transport

    assert protocol.active_request is not None
    request = protocol.active_request

    run_coroutine(request.send({
        'type': 'http.response.start',
        'status': 204,
    }))
    run_coroutine(request.send({
        'type': 'http.response.body',
    }))

    assert transport.closed
    #assert protocol.transport is None
