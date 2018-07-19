from uvicorn.importer import import_from_string, ImportFromStringError
import pytest
import os
import sys


def test_invalid_format():
    with pytest.raises(ImportFromStringError) as exc:
        import_from_string("example:")
    expected = 'Import string "example:" must be in format "<module>:<attribute>".'
    assert expected in str(exc)


def test_invalid_module():
    with pytest.raises(ImportFromStringError) as exc:
        import_from_string("module_does_not_exist:myattr")
    expected = 'Could not import module "module_does_not_exist".'
    assert expected in str(exc)


def test_invalid_attr():
    with pytest.raises(ImportFromStringError) as exc:
        import_from_string("tempfile:attr_does_not_exist")
    expected = 'Attribute "attr_does_not_exist" not found in module "tempfile".'
    assert expected in str(exc)


def test_internal_import_error():
    with pytest.raises(ModuleNotFoundError) as exc:
        import_from_string("tests.raise_import_error:myattr")


def test_valid_import():
    instance = import_from_string("tempfile:TemporaryFile")
    from tempfile import TemporaryFile

    assert instance == TemporaryFile


def test_no_import_needed():
    from tempfile import TemporaryFile

    instance = import_from_string(TemporaryFile)
    assert instance == TemporaryFile
