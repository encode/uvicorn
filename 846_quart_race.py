from quart import Quart, request as qrequest

from starlette.applications import Starlette
from starlette.responses import Response
import uvicorn

qapp = Quart(__name__)
sapp = Starlette()


@sapp.route('/', methods=['POST'])
async def starlette(request):
    data = await request.body()
    return Response(data)


@qapp.route('/', methods=['POST'])
async def quart():
    data = await qrequest.get_data()
    return data
    # return data, 200, {'Connection': 'close'}

if __name__ == '__main__':
    # uvicorn.run("846_quart_race:qapp", log_level="trace")
    uvicorn.run("846_quart_race:sapp", log_level="trace")


