import contextlib
import logging
import os
import signal
import socket
import threading
import time
from typing import Iterator, List, Optional

import click

from ..config import Config
from .backends.auto import select_async_backend
from .backends.base import AsyncListener, Event, TaskStatus
from .http11.handler import handle_http11
from .lifespan import Lifespan
from .state import ServerState
from .utils import to_internet_date

HANDLED_SIGNALS = (
    signal.SIGINT,  # Unix signal 2. Sent by Ctrl+C.
    signal.SIGTERM,  # Unix signal 15. Sent by `kill <pid>`.
)


class Server:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._state = ServerState()
        self._backend = select_async_backend(config.async_library)
        self._logger = logging.getLogger("uvicorn.error")
        self._last_notified = time.time()
        self._force_exit = False
        self._sync_started_event = threading.Event()

    @property
    def _shutdown_event(self) -> Event:
        if not hasattr(self, "_shutdown_event_obj"):
            # Can't be created on init due to a limitation of multiprocessing.
            self._shutdown_event_obj = self._backend.create_event()
        return self._shutdown_event_obj

    @property
    def _closed_event(self) -> Event:
        if not hasattr(self, "_closed_event_obj"):
            # Can't be created on init due to a limitation of multiprocessing.
            self._closed_event_obj = self._backend.create_event()
        return self._closed_event_obj

    def run(self, sockets: List[socket.SocketType] = None) -> None:
        if self._config.async_library == "asyncio":
            self._config.setup_event_loop()
        self._backend.run(self._main, sockets)

    @contextlib.contextmanager
    def run_in_thread(self, sockets: List[socket.SocketType] = None) -> Iterator[None]:
        thread_exc: Optional[Exception] = None

        def target() -> None:
            nonlocal thread_exc
            try:
                self.run(sockets=sockets)
            except Exception as exc:
                self._logger.exception(exc)
                self._sync_started_event.set()
                thread_exc = exc

        thread = threading.Thread(target=target)
        thread.start()
        try:
            self._sync_started_event.wait()
            if thread_exc is not None:
                raise thread_exc
            yield
        finally:
            thread.join()

    async def _main(self, sockets: List[socket.SocketType] = None) -> None:
        process_id = os.getpid()
        message = "Started server process [%d]"
        color_message = "Started server process [" + click.style("%d", fg="cyan") + "]"
        self._logger.info(message, process_id, extra={"color_message": color_message})

        config = self._config

        if not config.loaded:
            config.load()

        lifespan = Lifespan(config)
        shutdown_trigger = (
            self._shutdown_event.wait
            if config.shutdown_trigger is None
            else config.shutdown_trigger
        )

        async with self._backend.start_soon(lifespan.main, cancel_on_exit=True):
            await lifespan.startup()

            try:
                async with self._backend.start(self._serve, sockets) as listeners:
                    async with (
                        self._backend.start_soon(self._main_loop),
                        self._backend.start_soon(self._listen_signals),
                    ):
                        # Server has started.
                        self._sync_started_event.set()
                        self._log_started_message(listeners, sockets=sockets)
                        # Let the server run until exit is requested.
                        await shutdown_trigger()
                        await self._shutdown_event.set()
            finally:
                if not self._force_exit:
                    await lifespan.shutdown()

        message = "Finished server process [%d]"
        color_message = "Finished server process [" + click.style("%d", fg="cyan") + "]"
        self._logger.info(
            "Finished server process [%d]",
            process_id,
            extra={"color_message": color_message},
        )

    async def _serve(
        self,
        sockets: List[socket.SocketType] = None,
        *,
        task_status: TaskStatus = TaskStatus.IGNORED,
    ) -> None:
        await self._backend.serve_tcp(
            handle_http11,
            self._state,
            self._config,
            sockets=sockets,
            wait_close=self._shutdown_event.wait,
            on_close=self._on_close,
            task_status=task_status,
        )

    async def _main_loop(self) -> None:
        counter = 0
        should_exit = await self._tick(counter)
        while not should_exit:
            counter += 1
            counter = counter % 864000
            await self._backend.sleep(0.1)
            should_exit = await self._tick(counter)
        await self._shutdown_event.set()

    async def _tick(self, counter: int) -> bool:
        state = self._state
        config = self._config

        # Update the default headers, once per second.
        if counter % 10 == 0:
            current_time = time.time()
            current_date = to_internet_date(current_time).encode()
            state.default_headers = [(b"date", current_date)] + config.encoded_headers

            # Callback to `callback_notify` once every `timeout_notify` seconds.
            if config.callback_notify is not None:
                if current_time - self._last_notified > config.timeout_notify:
                    self._last_notified = current_time
                    await config.callback_notify()

        # Determine if we should exit.
        if self._shutdown_event.is_set():
            return True
        if config.limit_max_requests is not None:
            return state.total_requests >= config.limit_max_requests
        return False

    async def _listen_signals(self) -> None:
        if threading.current_thread() is not threading.main_thread():
            await self._closed_event.wait()
            return

        async def handle_signal_exit() -> None:
            if self._shutdown_event.is_set():
                self._logger.info("Shutting down forcibly")
                self._force_exit = True
            else:
                await self._shutdown_event.set()

        async def listen_signals() -> None:
            await self._backend.listen_signals(
                *HANDLED_SIGNALS, handler=handle_signal_exit
            )

        async with self._backend.start_soon(listen_signals, cancel_on_exit=True):
            await self._closed_event.wait()

    async def _on_close(self) -> None:
        assert self._shutdown_event.is_set()

        self._logger.info("Shutting down")
        state = self._state

        # Request shutdown on all existing connections.
        for conn in list(state.connections):
            await conn.trigger_shutdown()

        # Wait for existing connections to finish sending responses.
        if state.connections and not self._force_exit:
            self._logger.info(
                "Waiting for connections to close. (CTRL+C to force quit)"
            )
            while state.connections and not self._force_exit:
                await self._backend.sleep(0.1)

        # Wait for existing tasks to complete.
        if state.tasks and not self._force_exit:
            self._logger.info(
                "Waiting for background tasks to complete. (CTRL+C to force quit)"
            )
            while state.tasks and not self._force_exit:
                await self._backend.sleep(0.1)

        await self._closed_event.set()

    def _log_started_message(
        self, listeners: List[AsyncListener], sockets: List[socket.SocketType] = None
    ) -> None:
        if sockets is not None:
            # We're running multiple workers, and a message has already been
            # logged by `config.bind_socket()``.
            return

        config = self._config

        if config.fd is not None:
            sock = listeners[0].socket
            self._logger.info(
                "Uvicorn running on socket %s (Press CTRL+C to quit)",
                sock.getsockname(),
            )
            return

        if config.uds is not None:
            self._logger.info(
                "Uvicorn running on unix socket %s (Press CTRL+C to quit)", config.uds
            )
            return

        addr_format = "%s://%s:%d"
        host = "0.0.0.0" if config.host is None else config.host
        if ":" in host:
            # It's an IPv6 address.
            addr_format = "%s://[%s]:%d"

        port = config.port
        if port == 0:
            sock = listeners[0].socket
            _, port = sock.getpeername()

        protocol_name = "https" if config.ssl else "http"
        message = f"Uvicorn running on {addr_format} (Press CTRL+C to quit)"
        color_message = (
            "Uvicorn running on "
            + click.style(addr_format, bold=True)
            + " (Press CTRL+C to quit)"
        )
        self._logger.info(
            message,
            protocol_name,
            host,
            port,
            extra={"color_message": color_message},
        )
