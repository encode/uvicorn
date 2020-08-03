import logging
from typing import Any

from uvicorn._types import ASGIApp, Message, Receive, Scope, Send

PLACEHOLDER_FORMAT = {
    "body": "<{length} bytes>",
    "bytes": "<{length} bytes>",
    "text": "<{length} chars>",
    "headers": "<...>",
}
TRACE_LOG_LEVEL = 5


def message_with_placeholders(message: Message) -> Message:
    """
    Return an ASGI message, with any body-type content omitted and replaced
    with a placeholder.
    """
    assert isinstance(message, dict)
    new_message = message.copy()
    for attr in PLACEHOLDER_FORMAT.keys():
        if message.get(attr) is not None:
            content = message[attr]
            placeholder = PLACEHOLDER_FORMAT[attr].format(length=len(content))
            new_message[attr] = placeholder
    return new_message


class MessageLoggerMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.task_counter = 0
        self.app = app
        self.logger = logging.getLogger("uvicorn.asgi")

        def trace(message: str, *args: Any, **kwargs: Any) -> None:
            self.logger.log(TRACE_LOG_LEVEL, message, *args, **kwargs)

        self.logger.trace = trace  # type: ignore

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        self.task_counter += 1

        task_counter = self.task_counter
        client = scope.get("client")
        prefix = "%s:%d - ASGI" % (client[0], client[1]) if client else "ASGI"

        async def inner_receive() -> Message:
            message = await receive()
            logged_message = message_with_placeholders(message)
            log_text = "%s [%d] Receive %s"
            self.logger.trace(  # type: ignore
                log_text, prefix, task_counter, logged_message
            )
            return message

        async def inner_send(message: Message) -> None:
            logged_message = message_with_placeholders(message)
            log_text = "%s [%d] Send %s"
            self.logger.trace(  # type: ignore
                log_text, prefix, task_counter, logged_message
            )
            await send(message)

        logged_scope = message_with_placeholders(scope)
        log_text = "%s [%d] Started scope=%s"
        self.logger.trace(log_text, prefix, task_counter, logged_scope)  # type: ignore
        try:
            await self.app(scope, inner_receive, inner_send)
        except BaseException as exc:
            log_text = "%s [%d] Raised exception"
            self.logger.trace(log_text, prefix, task_counter)  # type: ignore
            raise exc from None
        else:
            log_text = "%s [%d] Completed"
            self.logger.trace(log_text, prefix, task_counter)  # type: ignore
