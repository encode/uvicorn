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
    ]
)
def anyio_backend(request: Any) -> str:
    return request.param
