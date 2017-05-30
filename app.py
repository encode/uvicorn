def app(environ, start_response):
    """Simplest possible application object"""
    data = b'Hello, World!\n'
    data += environ['REQUEST_METHOD'].encode('latin-1')
    data += b' '
    data += environ['PATH_INFO'].encode('latin-1')

    status = '200 OK'
    response_headers = [
        ('Content-type','text/plain'),
        ('Content-Length', str(len(data)))
    ]
    start_response(status, response_headers)
    return [data]
