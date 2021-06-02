import httpx
import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from tests.utils import run_server
from uvicorn.config import Config


async def homepage(request):
    return JSONResponse({"hello": "world"})


app = Starlette(
    routes=[
        Route("/", homepage, methods=["GET", "POST"]),
    ],
)


@pytest.mark.asyncio
async def test_run(
    tls_ca_ssl_context, tls_ca_certificate_pem_path, tls_ca_certificate_private_key_path
):
    config = Config(
        app=app,
        http="h2",
        loop="asyncio",
        limit_max_requests=1,
        ssl_keyfile=tls_ca_certificate_private_key_path,
        ssl_certfile=tls_ca_certificate_pem_path,
        ssl_ca_certs=tls_ca_certificate_pem_path,
    )
    async with run_server(config):
        async with httpx.AsyncClient(verify=tls_ca_ssl_context, http2=True) as client:
            response = await client.post(
                "https://127.0.0.1:8000", data={"hello": "world"}
            )
    assert response.status_code == 200
    assert response.http_version == "HTTP/2"
