import httpx
import pytest

from tests.utils import run_server
from uvicorn.config import Config


async def app(scope, receive, send):
    assert scope["type"] == "http"
    await send({"type": "http.response.start", "status": 204, "headers": []})
    await send({"type": "http.response.body", "body": b"", "more_body": False})


@pytest.mark.asyncio
async def test_run(
    tls_ca_ssl_context, tls_ca_certificate_pem_path, tls_ca_certificate_private_key_path
):
    config = Config(
        app=app,
        loop="asyncio",
        limit_max_requests=1,
        ssl_keyfile=tls_ca_certificate_private_key_path,
        ssl_certfile=tls_ca_certificate_pem_path,
        log_level="trace",
    )
    async with run_server(config):
        async with httpx.AsyncClient(verify=tls_ca_ssl_context) as client:
            response = await client.get("https://127.0.0.1:8000")
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_run_chain(tls_ca_ssl_context, tls_certificate_pem_path):
    config = Config(
        app=app,
        loop="asyncio",
        limit_max_requests=1,
        ssl_certfile=tls_certificate_pem_path,
        log_level="trace",
    )
    async with run_server(config):
        async with httpx.AsyncClient(verify=tls_ca_ssl_context) as client:
            response = await client.get("https://127.0.0.1:8000")
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_run_password(
    tls_ca_ssl_context,
    tls_ca_certificate_pem_path,
    tls_ca_certificate_private_key_encrypted_path,
):
    config = Config(
        app=app,
        loop="asyncio",
        limit_max_requests=1,
        ssl_keyfile=tls_ca_certificate_private_key_encrypted_path,
        ssl_certfile=tls_ca_certificate_pem_path,
        ssl_keyfile_password="uvicorn password for the win",
        log_level="trace",
    )
    async with run_server(config):
        async with httpx.AsyncClient(verify=tls_ca_ssl_context) as client:
            response = await client.get("https://127.0.0.1:8000")
    assert response.status_code == 204
