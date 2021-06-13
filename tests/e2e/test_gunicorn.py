import pathlib

import httpx
import pytest
from docker import DockerClient


E2E_BASE = pathlib.Path(__file__).parent
TEST_BASE = E2E_BASE.parent
UVICORN_BASE = TEST_BASE.parent


docker_client = DockerClient.from_env()


@pytest.fixture
def uvicorn_e2e_gunicorn():
    guncicorn_dockerfile_path = E2E_BASE / "gunicorn" / "Dockerfile"
    image, build_stream = docker_client.images.build(
        path=UVICORN_BASE.as_posix(),
        dockerfile=guncicorn_dockerfile_path.as_posix(),
        tag="uvicorn_e2e_gunicorn",
    )
    for chunk in build_stream:
        if "stream" in chunk:
            for line in chunk["stream"].splitlines():
                print(line)
    yield image


@pytest.mark.asyncio
@pytest.mark.filterwarnings("ignore:unclosed")
async def test_gunicorn_default(uvicorn_e2e_gunicorn):
    asgi_app_path = E2E_BASE / "gunicorn" / "app.py"
    container = docker_client.containers.run(
        uvicorn_e2e_gunicorn,
        volumes={asgi_app_path: {"bind": "/opt/app.py", "mode": "ro"}},
        ports={"8000": "8000"},
        command="gunicorn app:app -b 0.0.0.0 -k uvicorn.workers.UvicornWorker",
        detach=True,
        remove=True,
    )
    exit_code, output = container.exec_run(cmd=["wait-for-it", "localhost:8000"])
    if exit_code == 0:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://127.0.0.1:8000")
        assert response.status_code == 204
    container.stop()
