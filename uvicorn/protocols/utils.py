import asyncio


def create_application_instance(application, scope, application_queue, application_handler=None, loop=None):
    """
    Create an instance for the request and associate it with a handler
    """
    loop = loop or asyncio.get_event_loop()
    application_instance = application(scope=scope)
    asyncio.ensure_future(
        application_instance(
            application_queue.get,
            lambda message: application_handler(message)
        ), loop=loop
    )
    # Run the initial request against the instance to begin processing
    application_queue.put_nowait(scope)
