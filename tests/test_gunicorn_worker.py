import random
import re
import signal
import subprocess
import time

import pytest
import requests


# XXX: copypaste from test_main
async def app(scope, receive, send):
    assert scope["type"] == "http"
    await send(
        {
            "type": "http.response.start",
            "status": 204,
            "headers": [(b"test-response-header", b"response-header-val")],
        }
    )
    await send({"type": "http.response.body", "body": b"", "more_body": False})


@pytest.mark.parametrize(
    "worker_class",
    [
        "uvicorn.workers.UvicornWorker",
        "uvicorn.workers.UvicornH11Worker",
    ],
)
def test_gunicorn_worker_stdout_access_log_format(worker_class):
    random_port = random.randint(1024, 49151)
    access_logformat = (
        'hellotest %(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s"'
        ' "%(a)s" %(L)s "%({test-request-header}i)s"'
        ' "%({test-response-header}o)s"'
    )
    process = subprocess.Popen(
        [
            "gunicorn",
            "tests.test_gunicorn_worker:app",
            "-k=%s" % worker_class,
            "--bind=127.0.0.1:%d" % random_port,
            "--access-logfile=-",
            "--access-logformat=%s" % access_logformat,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    attempts = 0
    while True:
        attempts += 1
        try:
            resp = requests.get(
                "http://127.0.0.1:%d" % random_port,
                headers={"Test-Request-Header": "request-header-val"},
            )
        except requests.exceptions.ConnectionError:
            if attempts > 10:
                raise
            time.sleep(0.05)
        else:
            break

    assert resp.status_code == 204
    process.send_signal(signal.SIGTERM)
    stdout, stderr = process.communicate()

    stdout_lines = stdout.decode().splitlines()
    if not len(stdout_lines) == 1:
        pytest.fail("Access log line not found, stderr:\n" + stderr.decode())

    assert re.match(
        r'hellotest 127\.0\.0\.1 - - \[[^]]+\] "GET / HTTP/1\.1" 204 - "-"'
        r' "python-requests/2.25.1" [0-9.]+ "request-header-val" '
        '"response-header-val"',
        stdout_lines[0],
    )
