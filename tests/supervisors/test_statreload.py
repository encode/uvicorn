import logging
import os
import signal
import sys
import time
from pathlib import Path

import docker
import pytest
from docker import DockerClient

from uvicorn.config import Config
from uvicorn.supervisors import StatReload


def run(sockets):
    pass


def test_statreload():
    """
    A basic sanity check.

    Simply run the reloader against a no-op server, and signal for it to
    quit immediately.
    """
    config = Config(app=None, reload=True)
    reloader = StatReload(config, target=run, sockets=[])
    reloader.signal_handler(sig=signal.SIGINT, frame=None)
    reloader.run()


@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="Skipping reload test on Windows, due to low mtime resolution.",
)
def test_should_reload(tmpdir):
    update_file = Path(os.path.join(str(tmpdir), "example.py"))
    update_file.touch()

    working_dir = os.getcwd()
    os.chdir(str(tmpdir))
    try:
        config = Config(app=None, reload=True)
        reloader = StatReload(config, target=run, sockets=[])
        reloader.signal_handler(sig=signal.SIGINT, frame=None)
        reloader.startup()

        assert not reloader.should_restart()
        update_file.touch()
        assert reloader.should_restart()

        reloader.restart()
        reloader.shutdown()
    finally:
        os.chdir(working_dir)


DOCKERFILE = """
FROM python:3.7-buster
RUN apt update && apt-get install -y git --no-install-recommends && rm -rf /var/lib/apt/lists/* && apt-get clean
RUN pip install git+https://github.com/euri10/uvicorn.git@docker_signal#egg=uvicorn
WORKDIR /app
CMD ["uvicorn", "app:app", "--host=0.0.0.0", "--port=5000"]
"""

DOCKERFILE_RELOAD = """
FROM python:3.7-buster
RUN apt update && apt-get install -y git --no-install-recommends && rm -rf /var/lib/apt/lists/* && apt-get clean
RUN pip install git+https://github.com/euri10/uvicorn.git@docker_signal#egg=uvicorn
WORKDIR /app
CMD ["uvicorn", "app:app", "--host=0.0.0.0", "--port=5000", "--reload"]
"""

DOCKERFILE_WORKER = """
FROM python:3.7-buster
RUN apt update && apt-get install -y git --no-install-recommends && rm -rf /var/lib/apt/lists/* && apt-get clean
RUN pip install git+https://github.com/euri10/uvicorn.git@852cef442bc19d5ccb982a149b8529f4d358f223#egg=uvicorn
WORKDIR /app
CMD ["uvicorn", "app:app", "--host=0.0.0.0", "--port=5000", "--workers", "2"]
"""

APPFILE = """
async def app(scope, receive, send):
    message = await receive()
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"", "more_body": False})

"""


data = [(DOCKERFILE, "uv"), (DOCKERFILE_RELOAD, "uvr"), (DOCKERFILE_WORKER, "uvw")]


@pytest.mark.parametrize("dockerfile, tag", data)
def test_docker(tmpdir_factory, dockerfile, tag):
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    appdir = tmpdir_factory.mktemp("app")
    with open(appdir / "Dockerfile", "w") as f:
        f.write(dockerfile)
    with open(appdir / "app.py", "w") as f:
        f.write(APPFILE)
    client: DockerClient = docker.from_env()
    image, _ = client.images.build(path=".", dockerfile=appdir / "Dockerfile", tag=tag)
    container = client.containers.run(
        image,
        name="uvicorn_docker",
        detach=True,
        volumes={appdir: {"bind": "/app", "mode": "rw"}},
    )
    try:
        time.sleep(1)
        assert container.status == "created"
        time.sleep(1)
        assert "Application startup complete" in container.logs().decode()
        logger.info(
            f"number of process in container top: {len(container.top()['Processes'])}"
        )
        logger.info(container.top()["Processes"])
        container.kill(signal=signal.SIGINT)
        time.sleep(1)
        logger.info(container.logs().decode())
        time.sleep(1)
    except Exception as e:
        logger.info(e)
    finally:

        container.stop()
        container.remove()
