from tests.client import TestClient
from uvicorn.wsgi import WSGIMiddleware


def hello_world(environ, start_response):
    status = '200 OK'
    output = b'Hello World!\n'
    headers = [
        ('Content-Type', 'text/plain; charset=utf-8'),
        ('Content-Length', str(len(output)))
    ]
    start_response(status, headers)
    return [output]


def test_wsgi_get():
    app = WSGIMiddleware(hello_world)
    client = TestClient(app)
    response = client.get('/')
    assert response.status_code == 200
    assert response.text == 'Hello World!\n'


def test_wsgi_post():
    app = WSGIMiddleware(hello_world)
    client = TestClient(app)
    response = client.post('/', json={"example": 123})
    assert response.status_code == 200
    assert response.text == 'Hello World!\n'
