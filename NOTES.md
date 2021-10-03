Q.: What happens if the startup event fails on a single worker?
A.: The manager is notified and then terminate gracefully the workers i.e. it
will give time to the other workers to perform the shutdown event.

Q.: Should we have an "age" attribute on the manager?
A.: Age is used to choose which worker to kill.

Q.: Why is there a random delay on gunicorn `spawn_workers` function?
A.: ?

Q.: Should we implement the `maybe_promote_worker` logic? With USR2 signal?
A.: Yes! References:
    - https://docs.gunicorn.org/en/stable/signals.html#upgrading-to-a-new-binary-on-the-fly
    - https://github.com/benoitc/gunicorn/issues/1267

Q.: On the `signal()` method on the `Arbiter`, why is there a limit of 5 signals on the queue?
A.: ?

Q.: Should we accept `--pidfile`?
A.: Not for now, on the future maybe.

Q.: I'm assuming that we don't need an analogous `PIPE` and `sleep`, as we are using `mp.Queue()` and blocking until an item is available in the queue. Is that correct?
A.: ?

Q.: Do I need to have a health check? I see that on gunicorn, a temporary file is written from time to time by the workers, so the manager is able to detect if the workers are alive or not.
A.: Yes, we need to have a health check. Not sure if we can use a PIPE instead of a temporary file here.

Q.: Do we need a timeout on the process `join()` method?
A.: Yes. For now let's add a default behavior and then let's add a `--timeout` or `--worker-timeout` in the future. Similar to `timeout` and `graceful_timeout` on [gunicorn](https://docs.gunicorn.org/en/stable/settings.html#timeout).

Q.: Do we need `KeyboardInterruption` exception catch on the main loop?
A.: ?
