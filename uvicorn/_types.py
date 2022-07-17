import types
from typing import Any, Callable, Iterable, MutableMapping, Optional, Tuple, Type, Union

# WSGI
Environ = MutableMapping[str, Any]
ExcInfo = Tuple[Type[BaseException], BaseException, Optional[types.TracebackType]]
StartResponse = Callable[[str, Iterable[Tuple[str, str]], Optional[ExcInfo]], None]
WSGIApp = Callable[[Environ, StartResponse], Union[Iterable[bytes], BaseException]]
