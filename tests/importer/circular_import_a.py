# Used by test_importer.py
from .circular_import_b import foo  # noqa

bar = 123  # pragma: no cover
