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
        self.logger = logging.getLogger("uvicorn")

    async def __call__(self, scope, receive, send):
        self.task_counter += 1

        task_counter = self.task_counter
        client_addr = scope.get("client")

        async def inner_receive():
            nonlocal client_addr, receive, task_counter
            message = await receive()
            logged_message = message_with_placeholders(message)
            log_text = "%s - ASGI [%d] Sent %s"
            self.logger.debug(log_text, client_addr, task_counter, logged_message)
            return message

        async def inner_send(message):
            logged_message = message_with_placeholders(message)
            log_text = "%s - ASGI [%d] Received %s"
            self.logger.debug(log_text, client_addr, task_counter, logged_message)
            await send(message)

        log_text = "%s - ASGI [%d] Started"
        self.logger.debug(log_text, client_addr, task_counter)
        try:
            await self.app(scope, inner_receive, inner_send)
        except BaseException as exc:
            log_text = "%s - ASGI [%d] Raised exception"
            self.logger.debug(log_text, client_addr, task_counter)
            raise exc from None
        else:
            log_text = "%s - ASGI [%d] Completed"
            self.logger.debug(log_text, client_addr, task_counter)
