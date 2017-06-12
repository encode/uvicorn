import asyncio
import io
import http

# TODO:
# Encodings
# Path / Path Info
# Handling multiple headers
# exc_info
# wsgi.errors
# wsgi.sendfile
# max request body


# Request conversions...

def message_to_environ(message):
    """
    ASGI message -> WSGI environ
    """
    environ = {
        'REQUEST_METHOD': message['method'],
        'SCRIPT_NAME': message['root_path'],
        'PATH_INFO': message['path'],
        'QUERY_STRING': message['query_string'],
        'SERVER_PROTOCOL': 'http/%s' % message['http_version'],
        'wsgi.url_scheme': message['scheme'],
    }

    if message.get('client'):
        environ['REMOTE_ADDR'] = message['client'][0]
        environ['REMOTE_PORT'] = str(message['client'][1])
    if message.get('server'):
        environ['SERVER_NAME'] = message['server'][0]
        environ['SERVER_PORT'] = str(message['server'][1])

    headers = dict(message['headers'])
    if b'content-type' in headers:
        environ['CONTENT_TYPE'] = headers.pop(b'content-type')
    if b'content-length' in headers:
        environ['CONTENT_LENGTH'] = headers.pop(b'content-length')
    for key, val in headers.items():
        key_str = 'HTTP_%s' % key.decode('latin-1').replace('-', '_').upper()
        val_str = val.decode('latin-1')
        environ[key_str] = val_str

    return environ


def environ_to_message(environ):
    """
    WSGI environ -> ASGI message
    """
    message = {
        'method': environ['REQUEST_METHOD'].upper(),
        'root_path': environ.get('SCRIPT_NAME', ''),
        'path': environ.get('PATH_INFO', ''),
        'query_string': environ.get('QUERY_STRING', ''),
        'http_version': environ.get('SERVER_PROTOCOL', 'http/1.0').split('/', 1)[-1],
        'scheme': environ.get('wsgi.url_scheme', 'http'),
    }

    if 'REMOTE_ADDR' in environ and 'REMOTE_PORT' in environ:
        message['client'] = [environ['REMOTE_ADDR'], int(environ['REMOTE_PORT'])]
    if 'SERVER_NAME' in environ and 'SERVER_PORT' in environ:
        message['server'] = [environ['SERVER_NAME'], int(environ['SERVER_PORT'])]

    headers = []
    if environ.get('CONTENT_TYPE'):
        headers.append([b'content-type', environ['CONTENT_TYPE'].encode('latin-1')])
    if environ.get('CONTENT_LENGTH'):
        headers.append([b'content-length', environ['CONTENT_LENGTH'].encode('latin-1')])
    for key, val in environ.items():
        if key.startswith('HTTP_'):
            key_bytes = key[5:].replace('_', '-').upper().encode('latin-1')
            val_bytes = val.encode()
            headers.append([key_bytes, val_bytes])

    return message


# Response conversions...

def status_line_to_status_code(status):
    """
    WSGI status to ASGI status
    """
    return int(status.split()[0])


def status_code_to_status_line(status):
    """
    ASGI status to WSGI status
    """
    try:
        phrase = http.HTTPStatus(status).phrase
    except ValueError:
        phrase = ''
    return '%d %s' % (status, phrase)


def str_headers_to_byte_headers(headers):
    """
    WSGI response_headers to ASGI headers
    """
    return [
        [key.lower().encode('latin-1'), val.encode('latin-1')]
        for key, val in headers
    ]


def byte_headers_to_str_headers(headers):
    """
    ASGI headers to WSGI response_headers
    """
    return [
        (key.decode('latin-1'), val.decode('latin-1'))
        for key, val in headers
    ]


async def read_body(message, channels):
    """
    Read and return the entire body from an incoming ASGI message.
    """
    body = message.get('body', b'')
    if 'body' in channels:
        while True:
            message_chunk = await channels['body'].receive()
            body += message_chunk['content']
            if not message_chunk.get('more_content', False):
                break
    return body


# Adapters...

def enumerate_with_markers(iterator):
    # Transform an WSGI response iterator into (is_first, item, is_last).
    previous_is_first = True
    previous = None
    for item in iterator:
        if previous is not None:
            # Yield each non-final item in the iterator.
            yield (previous_is_first, previous, False)
            previous_is_first = False
        previous = item

    if previous is None:
        # Handle the empty case.
        yield (True, b'', True)
    else:
        # Yield the final item in the iterator.
        yield (previous_is_first, previous, True)


class ASGIAdapter(object):
    """
    Expose an ASGI interface, given a WSGI application.
    """
    def __init__(self, wsgi):
        self.wsgi = wsgi

    async def __call__(self, message, channels):
        response = {}
        def start_response(status, response_headers, exc_info=None):
            response.update({
                'status': status_line_to_status_code(status),
                'headers': str_headers_to_byte_headers(response_headers)
            })

        body = await read_body(message, channels)
        environ = message_to_environ(message)
        environ['wsgi.input'] = io.BytesIO(body)

        iterator = self.wsgi(environ, start_response)
        for is_first, content, is_last in enumerate_with_markers(iterator):
            if is_first:
                response.update({
                    'content': content,
                    'more_content': not(is_last)
                })
            else:
                response = {
                    'content': content,
                    'more_content': not(is_last)
                }
            await channels['reply'].send(response)


class WSGIAdapter(object):
    """
    Expose an WSGI interface, given an ASGI application.
    """
    def __init__(self, asgi):
        self.asgi = asgi
        self.loop = asyncio.get_event_loop()

    def __call__(self, environ, start_response):
        class ReplyChannel():
            def __init__(self, queue):
                self._queue = queue

            async def send(self, message):
                self._queue.append(message)

        class BodyChannel():
            def __init__(self, environ):
                self._stream = environ['wsgi.input']

            async def receive(self):
                return self._stream.read()

        reply = []
        message = environ_to_message(environ)
        channels = {
            'reply': ReplyChannel(reply),
            'body': BodyChannel(environ)
        }

        coroutine = self.asgi(message, channels)
        self.loop.run_until_complete(coroutine)

        assert(reply)
        status = status_code_to_status_line(reply[0]['status'])
        headers = byte_headers_to_str_headers(reply[0]['headers'])
        exc_info = None
        start_response(status, headers, exc_info)
        return [message['content'] for message in reply]
