"""
Some light wrappers around Python's multiprocessing, to deal with cleanly
starting child processes.
"""
import multiprocessing
import os
import sys

multiprocessing.allow_connection_pickling()
spawn = multiprocessing.get_context("spawn")


def get_subprocess(config, target, sockets):
    """
    Called in the parent process, to instantiate a new child process instance.
    The child is not yet started at this point.

    * config - The Uvicorn configuration instance.
    * target - A callable that accepts a list of sockets. In practice this will
               be the `Server.run()` method.
    * sockets - A list of sockets to pass to the server. Sockets are bound once
                by the parent process, and then passed to the child processes.
    """

    kwargs = {
        "config": config,
        "target": target,
        "sockets": sockets,
    }

    return spawn.Process(target=subprocess_started, kwargs=kwargs)


def subprocess_started(config, target, sockets):
    """
    Called when the child process starts.

    * config - The Uvicorn configuration instance.
    * target - A callable that accepts a list of sockets. In practice this will
               be the `Server.run()` method.
    * sockets - A list of sockets to pass to the server. Sockets are bound once
                by the parent process, and then passed to the child processes.
    """
    # Re-open stdin.
    # This is required for some debugging environments.
    try:
        sys.stdin = open("/dev/stdin")
    except:
        print("WARNING: Failed to open '/dev/stdin', debugging might not work.")

    # Logging needs to be setup again for each child.
    config.configure_logging()

    # Now we can call into `Server.run(sockets=sockets)`
    target(sockets=sockets)
