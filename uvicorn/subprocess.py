"""
Some light wrappers around Python's multiprocessing, to deal with cleanly
starting child processes.
"""
import multiprocessing
import os
import sys
from multiprocessing.context import SpawnProcess
from socket import socket
from typing import Any, Callable, List, Optional

from uvicorn.config import Config

multiprocessing.allow_connection_pickling()
spawn = multiprocessing.get_context("spawn")


def get_subprocess(
    config: Config,
    target: Callable[..., None],
    sockets: List[socket],
) -> SpawnProcess:
    """
    Called in the parent process, to instantiate a new child process instance.
    The child is not yet started at this point.

    * config - The Uvicorn configuration instance.
    * target - A callable that accepts a list of sockets. In practice this will
               be the `Server.run()` method.
    * sockets - A list of sockets to pass to the server. Sockets are bound once
                by the parent process, and then passed to the child processes.
    """
    # We pass across the stdin fileno, and reopen it in the child process.
    # This is required for some debugging environments.
    stdin_fileno: Optional[int]
    try:
        stdin_fileno = sys.stdin.fileno()
    except OSError:
        stdin_fileno = None

    kwargs = {
        "config": config,
        "target": target,
        "sockets": sockets,
        "stdin_fileno": stdin_fileno,
    }

    return spawn.Process(target=subprocess_started, kwargs=kwargs)


def subprocess_started(
    config: Config,
    target: Callable[..., None],
    sockets: List[socket],
    stdin_fileno: Optional[int],
) -> None:
    """
    Called when the child process starts.

    * config - The Uvicorn configuration instance.
    * target - A callable that accepts a list of sockets. In practice this will
               be the `Server.run()` method.
    * sockets - A list of sockets to pass to the server. Sockets are bound once
                by the parent process, and then passed to the child processes.
    * stdin_fileno - The file number of sys.stdin, so that it can be reattached
                     to the child process.
    """
    # Re-open stdin.
    if stdin_fileno is not None:
        sys.stdin = os.fdopen(stdin_fileno)

    # Logging needs to be setup again for each child.
    config.configure_logging()

    # Now we can call into `Server.run(sockets=sockets)`
    target(sockets=sockets)


# class Subprocess(spawn.Process):
#     """
#     A subclass of `multiprocessing.Process` that overrides the `run()` method
#     to allow us to pass in `config`, `target` and `sockets` to the child process.
#     """

#     def __init__(
#         self,
#         config: Config,
#         target: Callable[..., None],
#         sockets: List[socket],
#         *args: Any,
#         **kwargs: Any,
#     ) -> None:
#         super().__init__(*args, **kwargs)
#         self.config = config
#         self.target = target
#         self.sockets = sockets

#         # We pass across the stdin fileno, and reopen it in the child process.
#         # This is required for some debugging environments.
#         try:
#             self.stdin_fileno = sys.stdin.fileno()
#         except OSError:
#             self.stdin_fileno = None

#     def run(self) -> None:
#         """
#         Overrides the `run()` method to call the `target` with the `sockets`.
#         """
#         if self.stdin_fileno is not None:
#             sys.stdin = os.fdopen(self.stdin_fileno)

#         self.config.configure_logging()
#         self.target(sockets=self.sockets)
