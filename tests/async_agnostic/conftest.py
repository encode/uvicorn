import asyncio
from typing import Any

import pytest


@pytest.fixture(
    params=[
        pytest.param(("asyncio", {"use_uvloop": True}), id="asyncio+uvloop"),
        pytest.param(("asyncio", {"use_uvloop": False}), id="asyncio"),
        pytest.param(
            ("trio", {"restrict_keyboard_interrupt_to_checkpoints": True}), id="trio"
        ),
        pytest.param(("curio", {}), id="curio"),
    ],
)
def anyio_backend(request: Any) -> str:
    return request.param


@pytest.fixture(autouse=True)
def ensure_event_loop():
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        # We use anyio; its pytest plugin shuts down and unsets the asyncio event loop
        # after each test cases. For some reason on Windows when the loop is unset
        # asyncio won't create one again by itself. So we give it a hand.
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    yield
