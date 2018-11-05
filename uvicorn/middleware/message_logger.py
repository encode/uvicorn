import logging

PLACEHOLDER_FORMAT = {
    'body': '<{length} bytes>',
    'bytes': '<{length} bytes>',
    'text': '<{length} chars>',
    'headers': '<...>',
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

    def __call__(self, scope):
        self.task_counter += 1
        return MessageLoggerResponder(scope, self.app, self.logger, self.task_counter)


class MessageLoggerResponder:
    def __init__(self, scope, app, logger, task_counter):
        self.scope = scope
        self.logger = logger
        self.task_counter = task_counter
        self.client_addr = scope.get('client')

        logged_scope = message_with_placeholders(scope)
        log_text = '%s - ASGI [%d] Initialized %s'
        self.logger.debug(log_text, self.client_addr, self.task_counter, logged_scope)
        try:
            self.inner = app(scope)
        except BaseException as exc:
            log_text = '%s - ASGI [%d] Raised exception'
            self.logger.debug(log_text, self.client_addr, self.task_counter)
            raise exc from None

    async def __call__(self, receive, send):
        self._receive = receive
        self._send = send
        log_text = '%s - ASGI [%d] Started task'
        self.logger.debug(log_text, self.client_addr, self.task_counter)
        try:
            await self.inner(self.receive, self.send)
        except BaseException as exc:
            log_text = '%s - ASGI [%d] Raised exception'
            self.logger.debug(log_text, self.client_addr, self.task_counter)
            raise exc from None
        else:
            log_text = '%s - ASGI [%d] Completed'
            self.logger.debug(log_text, self.client_addr, self.task_counter)

    async def receive(self):
        message = await self._receive()
        logged_message = message_with_placeholders(message)
        log_text = '%s - ASGI [%d] Sent %s'
        self.logger.debug(log_text, self.client_addr, self.task_counter, logged_message)
        return message

    async def send(self, message):
        logged_message = message_with_placeholders(message)
        log_text = '%s - ASGI [%d] Received %s'
        self.logger.debug(log_text, self.client_addr, self.task_counter, logged_message)
        await self._send(message)
