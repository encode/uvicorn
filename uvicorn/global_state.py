import threading


class GlobalState:
    """
    State that is global to each worker process.
    """

    def __init__(self):
        self.total_requests = 0
        self.connections = set()
        self.tasks = set()
        self.started = threading.Event()
