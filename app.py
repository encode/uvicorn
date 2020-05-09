from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

import uvicorn


async def homepage(request):
    return JSONResponse({'hello': 'world'})


app = Starlette(debug=True, routes=[
    Route('/', homepage),
])


if __name__ == '__main__':
    uvicorn.run("app:app", workers=2)