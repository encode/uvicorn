import os
import functools
import signal
import trio
import trio_protocol


HANDLED_SIGNALS = (
    signal.SIGINT,  # Unix signal 2. Sent by Ctrl+C.
    signal.SIGTERM,  # Unix signal 15. Sent by `kill <pid>`.
)


def trio_setup():
    pass


class TrioServer:
    def __init__(
        self,
        app,
        host,
        port,
        uds,
        sock,
        logger,
        loop,
        connections,
        tasks,
        state,
        limit_max_requests,
        create_protocol,
        on_tick,
        install_signal_handlers,
        ready_event,
    ):
        self.app = app
        self.host = host
        self.port = port
        self.uds = uds
        self.sock = sock
        self.logger = logger
        self.connections = connections
        self.tasks = tasks
        self.state = state
        self.limit_max_requests = limit_max_requests
        self.create_protocol = create_protocol
        self.on_tick = on_tick
        self.install_signal_handlers = install_signal_handlers
        self.ready_event = ready_event
        self.should_exit = False
        self.pid = os.getpid()

    async def handle_signals(self):
        if not self.install_signal_handlers:
            return

        signals = {
            signal: self.handle_exit
            for signal in HANDLED_SIGNALS
        }

        with trio.catch_signals(signals) as batched_signal_aiter:
            async for batch in batched_signal_aiter:
                for signum in batch:
                    signals[signum](signum)   

    def handle_exit(self, sig):
        self.should_exit = True

    def run(self):
        async def main():
            self.logger.info("Started server process [{}]".format(self.pid))

            async with trio.open_nursery() as nursery:
                loop = trio_protocol.Loop(nursery)
                nursery.start_soon(self.tick, loop)
                nursery.start_soon(self.handle_signals)
                await self.create_server(nursery, loop)
                if self.ready_event is not None:
                    self.ready_event.set()

        trio.run(main)

    async def create_server(self, nursery, loop):
        loop = trio_protocol.Loop(nursery)
        create_protocol = functools.partial(self.create_protocol, loop=loop)

        if self.sock is not None:
            # Use an existing socket.
            self.server = await trio_protocol.create_server(
                nursery, create_protocol, sock=self.sock
            )
            message = "Uvicorn running on socket %s (Press CTRL+C to quit)"
            self.logger.info(message % str(self.sock.getsockname()))

        elif self.uds is not None:
            # https://github.com/python-trio/trio/issues/279
            raise NotImplementedError()
        else:
            # Standard case. Create a socket from a host/port pair.
            self.server = await trio_protocol.create_server(
                nursery, create_protocol, host=self.host, port=self.port
            )
            
            message = "Uvicorn running on http://%s:%d (Press CTRL+C to quit)"
            self.logger.info(message % (self.host, self.port))

    async def tick(self, loop):
        should_limit_requests = self.limit_max_requests is not None

        while not self.should_exit:
            if (
                should_limit_requests
                and self.state["total_requests"] >= self.limit_max_requests
            ):
                break
            self.on_tick()
            await trio.sleep(1)

        self.logger.info("Stopping server process [{}]".format(self.pid))
        self.server.close()
        await self.server.wait_closed()
        for connection in list(self.connections):
            connection.shutdown()

        await trio.sleep(0.1)
        if self.connections:
            self.logger.info("Waiting for connections to close.")
            while self.connections:
                await trio.sleep(0.1)
        if self.tasks:
            self.logger.info("Waiting for background tasks to complete.")
            while self.tasks:
                await trio.sleep(0.1)

        loop.stop()