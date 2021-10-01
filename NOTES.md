Q.: What happens if the startup event fails on a single worker?
A.: The manager is notified and then terminate gracefully the workers i.e. it
will give time to the other workers to perform the shutdown event.

Q.: Should we have an "age" attribute on the manager?
A.: ?

Q.: Why is there a random delay on gunicorn spawn_workers function?
A.: ?
