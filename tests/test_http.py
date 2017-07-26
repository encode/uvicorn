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


def mock_consumer(message, channels):
    pass


def get_protocol():
    loop = MockLoop()
    transport = MockTransport()
    protocol = HttpProtocol(mock_consumer, loop)
    protocol.connection_made(transport)
    return protocol


def run_coroutine(coroutine):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coroutine)


def read_body(message, channels):
    body = message.get('body', b'')
    if 'body' in channels:
        while True:
            message_chunk = run_coroutine(channels['body'].receive())
            body += message_chunk['content']
            if not message_chunk.get('more_content', False):
                break
    return body


# Test cases...

def test_get_request():
    protocol = get_protocol()
    protocol.data_received(b'GET / HTTP/1.1\r\nHost: example.org\r\n\r\n')

    assert protocol.active_request is not None
    message, channels = protocol.active_request
    assert message['method'] == 'GET'
    assert message['path'] == '/'
    assert message['headers'] == [[b'host', b'example.org']]

    run_coroutine(channels['reply'].send({'status': 200, 'headers': [[b'content-length', b'3']], 'content': b'abc'}))

    output = protocol.transport.content
    assert b'content-length: 3' in output
    assert output.endswith(b'abc')


def test_post_request():
    protocol = get_protocol()
    protocol.data_received(b'POST / HTTP/1.1\r\nContent-Length: 12\r\n\r\nHello, world')

    assert protocol.active_request is not None
    message, channels = protocol.active_request
    assert message['method'] == 'POST'
    assert message['path'] == '/'

    body = read_body(message, channels)
    assert body == b'Hello, world'


def test_pipelined_request():
    protocol = get_protocol()
    protocol.data_received(
        b'GET /1 HTTP/1.1\r\nHost: example.org\r\n\r\n'
        b'GET /2 HTTP/1.1\r\nHost: example.org\r\n\r\n'
        b'GET /3 HTTP/1.1\r\nHost: example.org\r\n\r\n'
    )

    assert protocol.active_request is not None
    assert len(protocol.pipeline_queue) == 2
    message, channels = protocol.active_request
    assert message['method'] == 'GET'
    assert message['path'] == '/1'
    assert message['headers'] == [[b'host', b'example.org']]

    run_coroutine(channels['reply'].send({'status': 204}))

    assert protocol.active_request is not None
    assert len(protocol.pipeline_queue) == 1
    message, channels = protocol.active_request
    assert message['method'] == 'GET'
    assert message['path'] == '/2'
    assert message['headers'] == [[b'host', b'example.org']]

    run_coroutine(channels['reply'].send({'status': 204}))

    assert protocol.active_request is not None
    assert len(protocol.pipeline_queue) == 0
    message, channels = protocol.active_request
    assert message['method'] == 'GET'
    assert message['path'] == '/3'
    assert message['headers'] == [[b'host', b'example.org']]

    run_coroutine(channels['reply'].send({'status': 204}))

    assert protocol.active_request is None
    assert len(protocol.pipeline_queue) == 0


def test_release_request_body():
    protocol = get_protocol()
    protocol.data_received(b'POST / HTTP/1.1\r\nContent-Length: 100\r\n\r\n')

    # Send half of the request body.
    for idx in range(5):
        protocol.data_received(b'0123456789')
    assert protocol.buffer_size == 50

    # Sending the response should release the buffer.
    message, channels = protocol.active_request
    run_coroutine(channels['reply'].send({'status': 204}))
    assert protocol.buffer_size == 0

    # Sending the remaining request body shouldn't buffer any more data.
    for idx in range(5):
        protocol.data_received(b'0123456789')
    assert protocol.buffer_size == 0


def test_chunked_response():
    protocol = get_protocol()
    protocol.data_received(b'GET /1 HTTP/1.1\r\nHost: example.org\r\n\r\n')

    assert protocol.active_request is not None
    message, channels = protocol.active_request

    run_coroutine(channels['reply'].send({'status': 200, 'content': b'123', 'more_content': True}))
    run_coroutine(channels['reply'].send({'content': b'456', 'more_content': True}))
    run_coroutine(channels['reply'].send({'content': b'789', 'more_content': False}))

    output = protocol.transport.content
    assert b'transfer-encoding: chunked\r\n' in output
    assert output.endswith(b'3\r\n123\r\n3\r\n456\r\n3\r\n789\r\n0\r\n\r\n')


def test_server_connection_close():
    protocol = get_protocol()
    protocol.data_received(b'GET /1 HTTP/1.1\r\nHost: example.org\r\n\r\n')
    transport = protocol.transport

    assert protocol.active_request is not None
    message, channels = protocol.active_request

    run_coroutine(channels['reply'].send({'status': 204,'headers': [[b'connection', b'close']]}))

    assert transport.closed
    assert protocol.transport is None


def test_client_connection_close():
    protocol = get_protocol()
    protocol.data_received(b'GET /1 HTTP/1.1\r\nConnection: close\r\n\r\n')
    transport = protocol.transport

    assert protocol.active_request is not None
    message, channels = protocol.active_request

    run_coroutine(channels['reply'].send({'status': 204}))

    assert transport.closed
    assert protocol.transport is None
