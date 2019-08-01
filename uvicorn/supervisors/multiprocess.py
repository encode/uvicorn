import multiprocessing
import os
import signal
import time

HANDLED_SIGNALS = (
    signal.SIGINT,  # Unix signal 2. Sent by Ctrl+C.
    signal.SIGTERM,  # Unix signal 15. Sent by `kill <pid>`.
)


class Multiprocess:
    def __init__(self, config):
        self.config = config
        self.workers = config.workers
        self.should_exit = False

    def handle_exit(self, sig, frame):
        self.should_exit = True

    def run(self, target, *args, **kwargs):
        pid = os.getpid()
        logger = self.config.logger_instance

        logger.info("Started parent process [{}]".format(pid))

        for sig in HANDLED_SIGNALS:
            signal.signal(sig, self.handle_exit)

        processes = []
        for idx in range(self.workers):
            process = multiprocessing.Process(target=target, args=args, kwargs=kwargs)
            process.start()
            processes.append(process)

        while (
            any([process.is_alive() for process in processes]) and not self.should_exit
        ):
            time.sleep(0.1)

        logger.info("Stopping parent process [{}]".format(pid))
