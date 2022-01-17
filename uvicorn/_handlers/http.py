import asyncio
from typing import TYPE_CHECKING

from uvicorn.config import Config

if TYPE_CHECKING:  # pragma: no cover
    from uvicorn.server import ServerState


MAX_RECV = 2 ** 16


async def handle_http(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    server_state: "ServerState",
    config: Config,
) -> None:
    # Run transport/protocol session from streams.
    #
    # This is a bit fiddly, so let me explain why we do this in the first place.
    #
    # This was introduced to switch to the asyncio streams API while retaining our
    # existing protocols-based code.
    #
    # The aim was to:
    # * Make it easier to support alternative async libaries (all of which expose
    #   a streams API, rather than anything similar to asyncio's transports and
    #   protocols) while keeping the change footprint (and risk) at a minimum.
    # * Keep a "fast track" for asyncio that's as efficient as possible, by reusing
    #   our asyncio-optimized protocols-based implementation.
    #
    # See: https://github.com/encode/uvicorn/issues/169
    # See: https://github.com/encode/uvicorn/pull/869

    # Use a future to coordinate between the protocol and this handler task.
    # https://docs.python.org/3/library/asyncio-protocol.html#connecting-existing-sockets
    loop = asyncio.get_event_loop()
    reader_read = asyncio.create_task(reader.read(MAX_RECV))

    # Switch the protocol from the stream reader to our own HTTP protocol class.
    protocol = config.http_protocol_class(  # type: ignore[call-arg, operator]
        config=config,
        server_state=server_state,
        on_connection_lost=reader_read.cancel,
    )
    transport = writer.transport
    transport.set_protocol(protocol)

    # Asyncio stream servers don't `await` handler tasks (like the one we're currently
    # running), so we must make sure exceptions that occur in protocols but outside the
    # ASGI cycle (e.g. bugs) are properly retrieved and logged.
    # Vanilla asyncio handles exceptions properly out-of-the-box, but uvloop doesn't.
    # So we need to attach a callback to handle exceptions ourselves for that case.
    # (It's not easy to know which loop we're effectively running on, so we attach the
    # callback in all cases. In practice it won't be called on vanilla asyncio.)
    task = asyncio.current_task()
    assert task is not None

    @task.add_done_callback
    def retrieve_exception(task: asyncio.Task) -> None:
        exc = task.exception() if not task.cancelled() else None

        if exc is None:
            return

        loop.call_exception_handler(
            {
                "message": "Fatal error in server handler",
                "exception": exc,
                "transport": transport,
                "protocol": protocol,
            }
        )
        # Hang up the connection so the client doesn't wait forever.
        transport.close()

    # Kick off the HTTP protocol.
    protocol.connection_made(transport)
    data = await reader_read
    protocol.data_received(data)
