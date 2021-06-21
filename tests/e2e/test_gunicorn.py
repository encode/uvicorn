import pathlib
import sys

import httpx
import pytest
from docker import DockerClient
from docker.errors import ImageNotFound

E2E_BASE = pathlib.Path(__file__).parent
TEST_BASE = E2E_BASE.parent
UVICORN_BASE = TEST_BASE.parent


docker_client = DockerClient.from_env()


@pytest.fixture
def uvicorn_e2e_gunicorn():
    guncicorn_dockerfile_path = E2E_BASE / "gunicorn" / "Dockerfile"
    try:
        image = docker_client.images.get("uvicorn_e2e_gunicorn")
    except ImageNotFound as e:
        image, build_stream = docker_client.images.build(
            path=UVICORN_BASE.as_posix(),
            dockerfile=guncicorn_dockerfile_path.as_posix(),
            tag="uvicorn_e2e_gunicorn",
            cache_from=["uvicorn_e2e_gunicorn"],
        )
        for chunk in build_stream:
            if "stream" in chunk:
                for line in chunk["stream"].splitlines():
                    print(line)
    yield image


@pytest.mark.asyncio
@pytest.mark.skipif(
    sys.platform == "win32", reason="Github actions can't run this on windows"
)
@pytest.mark.parametrize(
    "app, expected_exit_code",
    [
        ("default.py", 0),
        ("startup_failed.py", 137),
    ],
)
async def test_gunicorn_default(uvicorn_e2e_gunicorn, app, expected_exit_code):
    asgi_app_path = E2E_BASE / "gunicorn" / app
    app_name = asgi_app_path.stem
    container = docker_client.containers.run(
        uvicorn_e2e_gunicorn,
        name=f"uvicorn_e2e_gunicorn_{app_name}",
        volumes={asgi_app_path: {"bind": f"/opt/{app}", "mode": "ro"}},
        ports={"8000": "8000"},
        command=f"gunicorn {app_name}:app -b 0.0.0.0 -k uvicorn.workers.UvicornWorker",  # noqa: E501
        detach=True,
        remove=True,
    )
    try:
        exit_code, output = container.exec_run(cmd=["wait-for-it", "localhost:8000"])
        assert exit_code == expected_exit_code
        if expected_exit_code == 0:
            async with httpx.AsyncClient() as client:
                response = await client.get("http://127.0.0.1:8000")
            assert response.status_code == 204
    finally:
        print(container.logs())
        container.stop()
