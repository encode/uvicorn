from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route


async def homepage(request):
    return JSONResponse({'hello': 'world'})

routes = [
    Route("/", endpoint=homepage)
]


async def some_startup_task():
    print('start')


async def some_shutdown_task():
    print('end')


app = Starlette(
    routes=routes,
    on_startup=[some_startup_task],
    on_shutdown=[some_shutdown_task]
)
