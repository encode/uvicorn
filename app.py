from uvicorn.utils import ASGIAdapter, WSGIAdapter


# Run: `uvicorn app:asgi`
async def asgi(message, channels):
    """
    ASGI-style 'Hello, world' application.
    """
    await channels['reply'].send({
        'status': 200,
        'headers': [
            [b'content-type', b'text/plain'],
        ],
        'content': b'Hello, world\n'
    })


# Run: `gunicorn app:wsgi`
def wsgi(environ, start_response):
    """
    WSGI 'Hello, world' application.
    """
    status = '200 OK'
    response_headers = [('Content-type','text/plain')]
    start_response(status, response_headers)
    return [b'Hello, world\n']


# Run: `uvicorn app:asgi_from_wsgi`
asgi_from_wsgi = ASGIAdapter(wsgi)


# Run: `gunicorn app:wsgi_from_asgi`
wsgi_from_asgi = WSGIAdapter(asgi)
