import logging

import uvicorn
import yaml

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def app(scope, receive, send):
    logger.debug("DEBUG APP")
    assert scope['type'] == 'http'
    await send({
        'type': 'http.response.start',
        'status': 200,
        'headers': [
            [b'content-type', b'text/plain'],
        ]
    })
    await send({
        'type': 'http.response.body',
        'body': b'Hello, world!',
    })


if __name__ == '__main__':
    with open('logging.yaml', 'r') as stream:
        config = yaml.load(stream, yaml.FullLoader)
    # DEBUG DEV
    # uvicorn.run("main:app", reload=True, log_config=config)
    # TRACE
    uvicorn.run("main:app", reload=True, log_config=config, log_level="trace")