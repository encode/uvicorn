import enum
import logging
import multiprocessing as mp
import os
import queue
import signal
import sys
import time
from multiprocessing.context import SpawnProcess
from socket import socket
from types import FrameType
from typing import Callable, List, Optional, Protocol

from uvicorn.config import Config
from uvicorn.subprocess import get_subprocess

logger = logging.getLogger("uvicorn.error")


class Target(Protocol):
    def __call__(self, sockets: Optional[List[socket]] = None) -> None:
        ...


class ExitCode(enum.IntEnum):
    OK = 0
    STARTUP_FAILED = 3


class ProcessManager:
    # Complete list of signals can be found on:
    # http://manpages.ubuntu.com/manpages/bionic/man7/signal.7.html
    SIGNALS = {
        getattr(signal, f"SIG{sig.upper()}"): sig
        for sig in (
            "abrt",  # Abort signal from abort(3)
            "hup",  # Hangup signal generated by terminal close.
            "quit",  # Quit signal generated by terminal close.
            "int",  # Interrupt signal generated by Ctrl+C
            "term",  # Termination signal
            "winch",  # Window size change signal
            "chld",  # Child process terminated, stopped, or continued
        )
    }

    # TODO(Marcelo): This should be converted into a CLI option.
    GRACEFUL_TIMEOUT = 30

    def __init__(self, config: Config, target: Target, sockets: List[socket]) -> None:
        self.config = config
        self.target = target
        self.sockets = sockets
        self.processes: List[SpawnProcess] = []
        self.sig_queue = mp.Queue()

    def run(self) -> None:
        self.start()

        try:
            self.spawn_processes()

            while True:
                try:
                    sig = self.sig_queue.get(timeout=0.25)
                except queue.Empty:
                    self.reap_processes()
                    self.spawn_processes()
                    continue

                if sig not in self.SIGNALS.keys():
                    logger.info("Ignoring unknown signal: %d", sig)
                    continue

                handler = self.signal_handler(sig)
                if handler is None:
                    logger.info("Unhandled signal: %s", self.SIGNALS.get(sig))
                    continue

                handler()
        except StopIteration:
            self.halt()
        except Exception as exc:
            print(repr(exc))
            print(exc)

    def start(self) -> None:
        self.pid = os.getpid()
        logger.info("Started manager process [%d]", self.pid)
        self.init_signals()

    def spawn_processes(self) -> None:
        for _ in range(self.config.workers - len(self.processes)):
            self.spawn_process()

    def spawn_process(self) -> None:
        process = get_subprocess(self.config, target=self.target, sockets=self.sockets)
        process.start()
        self.processes.append(process)

    def init_signals(self) -> None:
        for s in self.SIGNALS.keys():
            signal.signal(s, self._signal)
        signal.signal(signal.SIGCHLD, self.handle_chld)

    def _signal(self, sig: signal.Signals, frame: FrameType) -> None:
        print("Master got signal: ", self.SIGNALS.get(sig))
        self.sig_queue.put(sig)

    def handle_int(self) -> None:
        self.stop(signal.SIGINT)

    def handle_term(self) -> None:
        self.stop(signal.SIGTERM)

    def handle_quit(self) -> None:
        self.stop(signal.SIGQUIT)

    def handle_chld(self, sig: signal.Signals, frame: FrameType) -> None:
        print("Master got signal: ", self.SIGNALS.get(sig))
        self.reap_processes()

    def signal_handler(self, sig: signal.Signals) -> Optional[Callable[..., None]]:
        sig_name = self.SIGNALS.get(sig)
        return getattr(self, f"handle_{sig_name}", None)

    def reap_processes(self) -> None:
        # NOTE: This is probably not reliable.
        for process in self.processes:
            if not process.is_alive():
                print(f"Process {process.pid} is not alive!")
                self.processes.remove(process)

    def halt(self, exit_code: int = ExitCode.OK) -> None:
        logger.info("Stopping parent process [%d]", self.pid)
        sys.exit(exit_code)

    def kill_processes(self, sig: signal.Signals) -> None:
        for process in self.processes:
            self.kill_process(process, sig)

    def kill_process(self, process: SpawnProcess, sig: signal.Signals) -> None:
        os.kill(process.pid, sig)
        self.processes.remove(process)

    def wait_timeout(self) -> None:
        limit = time.time() + self.GRACEFUL_TIMEOUT
        while self.processes and time.time() < limit:
            time.sleep(0.1)

    def stop(self, sig: signal.Signals) -> None:
        self.kill_processes(sig)
        self.wait_timeout()
        self.kill_processes(signal.SIGKILL)

        for sock in self.sockets:
            sock.close()

        raise StopIteration
