from uvicorn.protocols.utils import get_local_addr, get_remote_addr


class MockTransport:
    def __init__(self, info):
        self.info = info

    def get_extra_info(self, info_type):
        return self.info[info_type]


def test_get_local_addr():
    transport = MockTransport({"sockname": "path/to/unix-domain-socket"})
    assert get_local_addr(transport) is None

    transport = MockTransport({"sockname": ['123.45.6.7', 123]})
    assert get_local_addr(transport) == ('123.45.6.7', 123)


def test_get_remote_addr():
    transport = MockTransport({"peername": None})
    assert get_remote_addr(transport) is None

    transport = MockTransport({"peername": ['123.45.6.7', 123]})
    assert get_remote_addr(transport) == ('123.45.6.7', 123)
