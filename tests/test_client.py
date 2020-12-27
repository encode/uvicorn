import httpx
import pytest


async def hello_world(scope, receive, send):
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"text/plain")],
        }
    )
    await send(
        {"type": "http.response.body", "body": b"hello, world", "more_body": False}
    )


@pytest.mark.asyncio
async def test_explicit_base_url():
    async with httpx.AsyncClient(
        app=hello_world, base_url="http://testserver"
    ) as client:
        response = await client.get("/")
    assert response.status_code == 200
    assert response.text == "hello, world"


@pytest.mark.asyncio
async def test_explicit_host():
    async with httpx.AsyncClient(
        app=hello_world, base_url="http://testserver"
    ) as client:
        response = await client.get("/", headers={"host": "example.org"})
    assert response.status_code == 200
    assert response.text == "hello, world"
