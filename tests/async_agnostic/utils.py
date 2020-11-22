HTTP11_IMPLEMENTATIONS = ["h11"]

try:
    import httptools  # noqa
except ImportError:  # pragma: no cover
    pass
else:
    HTTP11_IMPLEMENTATIONS.append("httptools")
