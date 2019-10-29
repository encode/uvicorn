import logging

PLACEHOLDER_FORMAT = {
    "body": "<{length} bytes>",
    "bytes": "<{length} bytes>",
    "text": "<{length} chars>",
    "headers": "<...>",
}


def message_with_placeholders(message):
    """
    Return an ASGI message, with any body-type content omitted and replaced
    with a placeholder.
    """
    new_message = message.copy()
    for attr in PLACEHOLDER_FORMAT.keys():
        if message.get(attr) is not None:
            content = message[attr]
            placeholder = PLACEHOLDER_FORMAT[attr].format(length=len(content))
            new_message[attr] = placeholder
    return new_message


class MessageLoggerMiddleware:
    def __init__(self, app):
        self.task_counter = 0
        self.app = app
        self.logger = logging.getLogger("uvicorn.error")

    async def __call__(self, scope, receive, send):
        self.task_counter += 1

        task_counter = self.task_counter
        client = scope.get("client")
        prefix = "%s:%d - ASGI" % (client[0], client[1]) if client else "ASGI"

        async def inner_receive():
            message = await receive()
            logged_message = message_with_placeholders(message)
            log_text = "%s [%d] Sent %s"
            self.logger.debug(log_text, prefix, task_counter, logged_message)
            return message

        async def inner_send(message):
            logged_message = message_with_placeholders(message)
            log_text = "%s [%d] Received %s"
            self.logger.debug(log_text, prefix, task_counter, logged_message)
            await send(message)

        log_text = "%s [%d] Started"
        self.logger.debug(log_text, prefix, task_counter)
        try:
            await self.app(scope, inner_receive, inner_send)
        except BaseException as exc:
            log_text = "%s [%d] Raised exception"
            self.logger.debug(log_text, prefix, task_counter)
            raise exc from None
        else:
            log_text = "%s [%d] Completed"
            self.logger.debug(log_text, prefix, task_counter)
