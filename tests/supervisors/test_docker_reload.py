# import logging
# import shutil
# import signal
# import time
# from pathlib import Path
#
# import docker
# import pytest
# from docker import DockerClient
#
# DOCKERFILE = """
# FROM python:3.7-buster
# RUN apt update && apt-get install -y git --no-install-recommends && rm -rf /var/lib/apt/lists/* && apt-get clean
# COPY uvicorn .
# RUN pip install -e .
# WORKDIR /app
# CMD ["uvicorn", "app:app", "--host=0.0.0.0", "--port=5000", "--log-level=debug"]
# """
#
# DOCKERFILE_RELOAD = """
# FROM python:3.7-buster
# RUN apt update && apt-get install -y git --no-install-recommends && rm -rf /var/lib/apt/lists/* && apt-get clean
# COPY uvicorn .
# RUN pip install -e .
# WORKDIR /app
# CMD ["uvicorn", "app:app", "--host=0.0.0.0", "--port=5000", "--reload", "--log-level=debug"]
# """
#
# DOCKERFILE_WORKER = """
# FROM python:3.7-buster
# RUN apt update && apt-get install -y git --no-install-recommends && rm -rf /var/lib/apt/lists/* && apt-get clean
# COPY uvicorn .
# RUN pip install -e .
# WORKDIR /app
# CMD ["uvicorn", "app:app", "--host=0.0.0.0", "--port=5000", "--workers", "2", "--log-level=debug"]
# """
#
# APPFILE = """
# async def app(scope, receive, send):
#     message = await receive()
#     await send({"type": "http.response.start", "status": 200, "headers": []})
#     await send({"type": "http.response.body", "body": b"", "more_body": False})
# """
#
#
# data = [(DOCKERFILE, "uv"), (DOCKERFILE_RELOAD, "uvr"), (DOCKERFILE_WORKER, "uvw")]
#
#
# @pytest.mark.parametrize("dockerfile, tag", data)
# def test_docker(tmpdir_factory, dockerfile, tag):
#     logger = logging.getLogger(__name__)
#     logger.setLevel(logging.INFO)
#     appdir = tmpdir_factory.mktemp("app")
#     with open(appdir / "Dockerfile", "w") as f:
#         f.write(dockerfile)
#     with open(appdir / "app.py", "w") as f:
#         f.write(APPFILE)
#     shutil.copytree(Path(__file__).parent.parent.parent, appdir / "uvicorn")
#     client: DockerClient = docker.from_env()
#     image, _ = client.images.build(
#         path=appdir.strpath, dockerfile=appdir / "Dockerfile", tag=tag
#     )
#     container = client.containers.run(
#         image,
#         name="uvicorn_docker",
#         detach=True,
#         volumes={appdir: {"bind": "/app", "mode": "rw"}},
#     )
#     try:
#         time.sleep(1)
#         assert container.status == "created"
#         time.sleep(1)
#         assert "Application startup complete" in container.logs().decode()
#         logger.info(
#             f"number of process in container top: {len(container.top()['Processes'])}"
#         )
#         logger.info(container.top()["Processes"])
#         container.kill(signal=signal.SIGINT)
#         time.sleep(1)
#         clogs = container.logs().decode()
#         logger.info(container.logs().decode())
#         assert "Finished server process" in clogs
#         time.sleep(1)
#     except Exception as e:
#         logger.error(e)
#         raise Exception
#     finally:
#         container.stop()
#         container.remove()
