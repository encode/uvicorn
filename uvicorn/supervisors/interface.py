import logging
import os
import signal
import threading

logger = logging.getLogger("uvicorn.error")


class ProcessTracker:
    def __init__(self):
        self.child_pids = []
        self.should_exit = threading.Event()

    def signal_handler(self, sig, frame):
        """
        A signal handler that is registered with the parent process.
        """
        for child_pid in self.child_pids:
            try:
                os.kill(child_pid, signal.SIGINT)
                finished = os.waitpid(child_pid, 0)
            except Exception as e:
                logger.error(f"Could not kill child PID {child_pid}: {e}")
        self.should_exit.set()

    def signal_handler2(self, sig, frame):
        """
        A signal handler that is registered with the parent process.
        """
        logger.info(f"Handling signal: {sig}")
        for child_pid in self.child_pids:
            logger.debug(f"Attempt at killing child PID {child_pid}")
            try:
                os.kill(child_pid, signal.SIGINT)
                (pid, status) = os.waitpid(child_pid, 0)
                if pid == child_pid:
                    logger.debug(f"{pid}: {status}")
                    if os.WIFEXITED(status):
                        logger.debug(
                            "process returning status exited via the exit() system call"
                        )
                    elif os.WIFSIGNALED(status):
                        logger.debug(
                            "process returning status was terminated by a signal"
                        )
                    elif os.WIFSTOPPED(status):
                        logger.debug("process returning status was stopped")
            except Exception as e:
                logger.error(f"Cant kill child PID {child_pid}: {e}")
        self.should_exit.set()
