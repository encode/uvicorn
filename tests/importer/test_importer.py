import pytest

from uvicorn.importer import ImportFromStringError, import_from_string


def test_invalid_format() -> None:
    with pytest.raises(ImportFromStringError) as exc_info:
        import_from_string("example:")
    expected = 'Import string "example:" must be in format "<module>:<attribute>".'
    assert expected in str(exc_info.value)


def test_invalid_module() -> None:
    with pytest.raises(ImportFromStringError) as exc_info:
        import_from_string("tests.importer.raise_import_error_does_not_exist:myattr")
    expected = "No module named 'does_not_exist'"
    assert expected in str(exc_info.value)


def test_invalid_attr() -> None:
    with pytest.raises(ImportFromStringError) as exc_info:
        import_from_string("tempfile:attr_does_not_exist")
    expected = 'Attribute "attr_does_not_exist" not found in module "tempfile".'
    assert expected in str(exc_info.value)


def test_circular_import_error() -> None:
    with pytest.raises(ImportFromStringError) as exc_info:
        import_from_string("tests.importer.raise_import_error_circular_import_foo:foo")
    expected = (
        "cannot import name 'foo' from partially initialized module "
        "'tests.importer.raise_import_error_circular_import_foo' "
        "(most likely due to a circular import)"
    )
    assert expected in str(exc_info.value)


def test_internal_import_error() -> None:
    with pytest.raises(ImportFromStringError):
        import_from_string("tests.importer.raise_import_error_does_not_exist:myattr")


def test_valid_import() -> None:
    instance = import_from_string("tempfile:TemporaryFile")
    from tempfile import TemporaryFile

    assert instance == TemporaryFile


def test_no_import_needed() -> None:
    from tempfile import TemporaryFile

    instance = import_from_string(TemporaryFile)
    assert instance == TemporaryFile
