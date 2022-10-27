# Logging

Logging in Python is pretty complex, and there are many different ways to do it.
This document is intended to provide an overview about the logger objects available in **Uvicorn**.

### Loggers

**Uvicorn** has many loggers available, each one with a different purpose.

It contains an ancestor logger called `uvicorn`, and then multiple children loggers.

#### Server Logger (`uvicorn.server`)

This logger is used to log information about the core server functionality, such as startup and shutdown.

#### WebSocket Logger (`uvicorn.websocket`)

This logger is used to log server-side information about WebSocket protocol messages.

#### HTTP Logger (`uvicorn.http`)

This logger is used to log server-side information about HTTP protocol messages.

#### Access Logger (`uvicorn.access`)

This logger is used to log client-side information about each request/response cycle.

#### ASGI Logger (`uvicorn.asgi`)

This logger is used to log low-level server-side ASGI messages. Only available when `--log-level` is set to `trace`.

### Configuration

**Uvicorn** uses the standard Python `logging` module to handle logging.

This section will be used to teach people how to configure uvicorn loggers.

### Tutorials

This section will be used to link tutorials.
