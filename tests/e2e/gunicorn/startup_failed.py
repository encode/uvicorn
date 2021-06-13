from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route


def homepage(request):
    return PlainTextResponse("Hello, world!")


def startup():
    print("Ready to go")
    raise RuntimeError


routes = [
    Route("/", homepage),
]

app = Starlette(routes=routes, on_startup=[startup])
