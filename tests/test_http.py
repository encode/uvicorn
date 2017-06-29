from collections import namedtuple
from uvicorn.protocols.http import HttpProtocol
import asyncio


# Utils...

class MockLoop(object):
    def create_task(self, *args):
        pass


class MockTransport(object):
    content = b''

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


def test_post_request():
    protocol = get_protocol()
    protocol.data_received(b'POST / HTTP/1.1\r\nContent-Length: 12\r\n\r\nHello, world')

    assert protocol.active_request is not None
    message, channels = protocol.active_request
    assert message['method'] == 'POST'
    assert message['path'] == '/'

    body = read_body(message, channels)
    assert body == b'Hello, world'
