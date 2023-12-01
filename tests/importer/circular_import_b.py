# Used by test_importer.py
from .circular_import_a import bar  # noqa

foo = 123  # pragma: no cover
