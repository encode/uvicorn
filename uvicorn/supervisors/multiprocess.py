import logging
import os
import signal
import threading
from multiprocessing import Pipe
from socket import socket
from typing import Any, Callable, List, Optional, Union

import click

from uvicorn._subprocess import get_subprocess
from uvicorn.config import Config

UNIX_SIGNALS = {
    getattr(signal, f"SIG{x}"): x
    for x in "HUP QUIT TTIN TTOU USR1 USR2 WINCH".split()
    if hasattr(signal, f"SIG{x}")
}

logger = logging.getLogger("uvicorn.error")


class Process:
    def __init__(
        self,
        config: Config,
        target: Callable[[Optional[List[socket]]], None],
        sockets: List[socket],
    ) -> None:
        self.real_target = target

        self.parent_conn, self.child_conn = Pipe()
        self.process = get_subprocess(config, self.target, sockets)

    def ping(self, timeout: float = 5) -> bool:
        self.parent_conn.send(b"ping")
        if self.parent_conn.poll(timeout):
            self.parent_conn.recv()
            return True
        return False

    def pong(self) -> None:
        self.child_conn.recv()
        self.child_conn.send(b"pong")

    def always_pong(self) -> None:
        while True:
            self.pong()

    def target(self, sockets: Optional[List[socket]] = None) -> Any:
        if os.name == "nt":
            # Windows doesn't support SIGTERM, so we use SIGBREAK instead.
            # And then we raise SIGTERM when SIGBREAK is received.
            # https://learn.microsoft.com/zh-cn/cpp/c-runtime-library/reference/signal?view=msvc-170
            signal.signal(
                signal.SIGBREAK,  # type: ignore[attr-defined]
                lambda sig, frame: signal.raise_signal(signal.SIGTERM),
            )

        threading.Thread(target=self.always_pong, daemon=True).start()
        return self.real_target(sockets)

    def is_alive(self, timeout: float = 5) -> bool:
        if not self.process.is_alive():
            return False

        return self.ping(timeout)

    def start(self) -> None:
        self.process.start()
        logger.info("Started child process [{}]".format(self.process.pid))

    def terminate(self) -> None:
        if self.process.exitcode is not None:
            return
        assert self.process.pid is not None
        if os.name == "nt":
            # Windows doesn't support SIGTERM.
            # So send SIGBREAK, and then in process raise SIGTERM.
            os.kill(self.process.pid, signal.CTRL_BREAK_EVENT)  # type: ignore[attr-defined]
        else:
            os.kill(self.process.pid, signal.SIGTERM)
        logger.info("Terminated child process [{}]".format(self.process.pid))

        self.parent_conn.close()
        self.child_conn.close()

    def kill(self) -> None:
        # In Windows, the method will call `TerminateProcess` to kill the process.
        # In Unix, the method will send SIGKILL to the process.
        self.process.kill()

    def join(self) -> None:
        logger.info("Waiting for child process [{}]".format(self.process.pid))
        self.process.join()

    @property
    def pid(self) -> Union[int, None]:
        return self.process.pid


class Multiprocess:
    def __init__(
        self,
        config: Config,
        target: Callable[[Optional[List[socket]]], None],
        sockets: List[socket],
    ) -> None:
        self.config = config
        self.target = target
        self.sockets = sockets

        self.processes_num = config.workers
        self.processes: List[Process] = []

        self.should_exit = threading.Event()

        self.signal_queue: List[int] = []
        for sig in UNIX_SIGNALS:
            signal.signal(sig, lambda sig, frame: self.signal_queue.append(sig))

        # Sent by Ctrl+C.
        signal.signal(signal.SIGINT, lambda sig, frame: self.handle_int())
        # Sent by `kill <pid>`. Not sent on Windows.
        signal.signal(signal.SIGTERM, lambda sig, frame: self.handle_term())
        if os.name == "nt":
            # Sent by `Ctrl+Break` on Windows.
            signal.signal(signal.SIGBREAK, lambda sig, frame: self.handle_break())  # type: ignore[attr-defined]

    def init_processes(self) -> None:
        for _ in range(self.processes_num):
            process = Process(self.config, self.target, self.sockets)
            process.start()
            self.processes.append(process)

    def terminate_all(self) -> None:
        for process in self.processes:
            process.terminate()

    def join_all(self) -> None:
        for process in self.processes:
            process.join()

    def restart_all(self) -> None:
        for idx, process in enumerate(tuple(self.processes)):
            process.terminate()
            process.join()
            del self.processes[idx]
            process = Process(self.config, self.target, self.sockets)
            process.start()
            self.processes.append(process)

    def run(self) -> None:
        message = "Started parent process [{}]".format(os.getpid())
        color_message = "Started parent process [{}]".format(
            click.style(str(os.getpid()), fg="cyan", bold=True)
        )
        logger.info(message, extra={"color_message": color_message})

        self.init_processes()

        while not self.should_exit.wait(0.5):
            self.handle_signals()
            self.keep_subprocess_alive()

        self.terminate_all()
        self.join_all()

        message = "Stopping parent process [{}]".format(os.getpid())
        color_message = "Stopping parent process [{}]".format(
            click.style(str(os.getpid()), fg="cyan", bold=True)
        )
        logger.info(message, extra={"color_message": color_message})

    def keep_subprocess_alive(self) -> None:
        for idx, process in enumerate(tuple(self.processes)):
            if process.is_alive():
                continue

            process.kill()  # process is hung, kill it
            process.join()
            logger.info("Child process [{}] died".format(process.pid))
            del self.processes[idx]
            process = Process(self.config, self.target, self.sockets)
            process.start()
            self.processes.append(process)

    def handle_signals(self) -> None:
        for sig in tuple(self.signal_queue):
            self.signal_queue.remove(sig)
            sig_name = UNIX_SIGNALS[sig]
            sig_handler = getattr(self, f"handle_{sig_name.lower()}", None)
            if sig_handler is not None:
                sig_handler()
            else:
                logger.info(f"Received signal [{sig_name}], but nothing to do")

    def handle_int(self) -> None:
        if not self.should_exit.is_set():
            self.should_exit.set()
        else:
            self.terminate_all()

    def handle_term(self) -> None:
        logger.info("Received SIGTERM, exiting")
        if not self.should_exit.is_set():
            self.should_exit.set()
        else:
            self.terminate_all()

    def handle_break(self) -> None:
        logger.info("Received SIGBREAK, exiting")
        if not self.should_exit.is_set():
            self.should_exit.set()
        else:
            self.terminate_all()

    def handle_hup(self) -> None:
        logger.info("Received SIGHUP, restarting processes")
        self.restart_all()

    def handle_ttin(self) -> None:
        logger.info("Received SIGTTIN, increasing processes")
        self.processes_num += 1
        process = Process(self.config, self.target, self.sockets)
        process.start()
        self.processes.append(process)

    def handle_ttou(self) -> None:
        logger.info("Received SIGTTOU, decreasing processes")
        if self.processes_num <= 1:
            logger.info("Cannot decrease processes any more")
            return
        self.processes_num -= 1
        process = self.processes.pop()
        process.terminate()
        process.join()
