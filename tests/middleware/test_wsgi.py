import pytest
import sys
from tests.client import TestClient
from uvicorn.middleware.wsgi import WSGIMiddleware


def hello_world(environ, start_response):
    status = '200 OK'
    output = b'Hello World!\n'
    headers = [
        ('Content-Type', 'text/plain; charset=utf-8'),
        ('Content-Length', str(len(output)))
    ]
    start_response(status, headers)
    return [output]


def echo_body(environ, start_response):
    status = '200 OK'
    output = environ['wsgi.input'].read()
    headers = [
        ('Content-Type', 'text/plain; charset=utf-8'),
        ('Content-Length', str(len(output)))
    ]
    start_response(status, headers)
    return [output]


def raise_exception(environ, start_response):
    raise RuntimeError('Something went wrong')


def return_exc_info(environ, start_response):
    try:
        raise RuntimeError('Something went wrong')
    except:
        status = '500 Internal Server Error'
        output = b'Internal Server Error'
        headers = [
            ('Content-Type', 'text/plain; charset=utf-8'),
            ('Content-Length', str(len(output)))
        ]
        start_response(status, headers, exc_info=sys.exc_info())
        return [output]


def test_wsgi_get():
    app = WSGIMiddleware(hello_world)
    client = TestClient(app)
    response = client.get('/')
    assert response.status_code == 200
    assert response.text == 'Hello World!\n'


def test_wsgi_post():
    app = WSGIMiddleware(echo_body)
    client = TestClient(app)
    response = client.post('/', json={"example": 123})
    assert response.status_code == 200
    assert response.text == '{"example": 123}'


def test_wsgi_exception():
    # Note that we're testing the WSGI app directly here.
    # The HTTP protocol implementations would catch this error and return 500.
    app = WSGIMiddleware(raise_exception)
    client = TestClient(app)
    with pytest.raises(RuntimeError):
        response = client.get('/')


def test_wsgi_exc_info():
    # Note that we're testing the WSGI app directly here.
    # The HTTP protocol implementations would catch this error and return 500.
    app = WSGIMiddleware(return_exc_info)
    client = TestClient(app)
    with pytest.raises(RuntimeError):
        response = client.get('/')

    app = WSGIMiddleware(return_exc_info)
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get('/')
    assert response.status_code == 500
    assert response.text == 'Internal Server Error'
