import json
import re
from importlib.metadata import requires
from typing import List, Tuple, cast
from urllib import request

import pytest
from packaging import version
from pkg_resources import parse_version

from uvicorn._utils import version_parse


def extra_packages():
    requirements = cast(List[str], requires("uvicorn"))
    for requirement in requirements:
        if 'extra == "standard"' in requirement:
            package = requirement.split(";")[0]
            splitted_package = re.split("<|>|=|!", package)
            name, min_version = splitted_package[0], splitted_package[-1]
            yield name, min_version


def versions(pkg_name: str):
    """Extracted from https://stackoverflow.com/a/40745656/13087720."""
    url = f"https://pypi.python.org/pypi/{pkg_name}/json"
    releases = json.loads(request.urlopen(url).read())["releases"]
    return sorted(releases, key=parse_version, reverse=True)


@pytest.mark.parametrize("package", extra_packages())
def test_version_parse(package: Tuple[str, str]) -> None:
    name, min_version = package
    for current_version in versions(name):
        packaging_min = version.parse(min_version)
        packaging_current = version.parse(current_version)

        uvicorn_min = version_parse(min_version)
        uvicorn_current = version_parse(current_version)

        packaging_eval = packaging_current >= packaging_min
        uvicorn_eval = uvicorn_current >= uvicorn_min
        assert packaging_eval == uvicorn_eval, {
            "uvicorn": {"min": uvicorn_min, "current": uvicorn_current},
            "packaging": {"min": packaging_min, "current": packaging_current},
        }
