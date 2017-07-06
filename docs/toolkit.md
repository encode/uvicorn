# Tool Kit

Unicorn provides a set of basic tooling for building services with. You don’t need to use these components, but they’ll give you an extra set of useful functionality if you do want to.

## Installation

The uvicorn tools are provided as a separate package…

```shell
$ pip install uvitools
```

# Routing

You’ll almost always want to break you application into several different endpoints, referenced at different URLs.

## Path routing

The `Router` class allows you to route messages based on the path component of their URL.

This example demonstrates routing to two separate handlers:

```python
from uvitools.routing import Route, Router

async def hello_world(message, channels):
    data = {'hello': 'world'}
    await channels['reply'].send({
        'status': 200,
        'headers': [
            [b'content-type', b'application/json']
        ],
        'content': json.dumps(data).encode()
    })

async def hello_user(message, channels):
    data = {'hello': message['args']['username']}
    await channels['reply'].send({
        'status': 200,
        'headers': [
            [b'content-type', b'application/json']
        ],
        'content': json.dumps(data).encode()
    })

app = Router([
    Route('/hello/', hello_world),
    Route('/hello/<username>/', hello_user)
])
```

Path components use the `<square_bracket>` syntax, and are added into the incoming message, using the `args` dictionary value.

You can include type converters in a route...

```python
Route('/hello/<int:user_id>/', hello_user)
```

Or limit which methods a route will accept...

```python
Route('/hello/<username>/', hello_user, methods=['GET'])
```

Routing will automatically handle 404 Not Found, 405 Method Not Allowed, and 301 Redirect cases.

For more information on the routing syntax, see [the Werkzeug URL Routing documentation](http://werkzeug.pocoo.org/docs/routing/).

## Channel routing

In order to route messages on various different channels, you'll want to use `ChannelSwitch`. This allows you to match either literal or wildcard channel names, and route each to different handlers...

```python
from uvitools.routing import ChannelSwitch

app = ChannelSwitch({
    'http.request': ...
    'websocket.*': ...
})
```

Wildcard matches may only be included as the last character of the channel string. You can match all channels by using the `"*"` string literal.

Channel switching will only use the single most specific match found for each incoming message.

## Composing routers

You'll probably want to combine both channel and path routing in your application.

Here's an example that demonstrates composing several layers of channel and path routing together...

```python
from uvitools.routing import ChannelSwitch, Route, Router

app = ChannelSwitch({
    'http.request': Router([
        Route('/', homepage, methods=['GET', 'POST']),
        Route('/<room>/', chatpage, methods=['GET']),
    ]),
    'websocket.*': Router([
        Route('/<room>/', ChannelSwitch({
            'websocket.connect': chat_connect,
            'websocket.disconnect': chat_disconnect,
            'websocket.receive': chat_receive,
        })),
    ])
})
```

# Debug

The uvitools package includes the werkzeug interactive debugger, which allows you to inspect exceptions that occur during development.

## Showing tracebacks

If you just want nicely formatted tracebacks, you can instantiated the `DebugMiddleware` class without any configuration options.

```python
from uvitools.debug import DebugMiddleware
from uvitools.routing import Route, Router


router = Router([
    ...
])

app = DebugMiddleware(router)
```

## The interactive debugger

To turn on the interactive debugger, use `evalx=True`:

```python
from uvitools.debug import DebugMiddleware
from uvitools.routing import Route, Router


router = Router([
    ...
])

app = DebugMiddleware(router, evalx=True)
```

The interactive debugger will only work properly when running on a single process, on a single instance. It should *never be used in production environments*, as doing so represents a significant security risk.

For more information on available configuration options, see [the Werkzeug Debugging documentation](http://werkzeug.pocoo.org/docs/debug/).
