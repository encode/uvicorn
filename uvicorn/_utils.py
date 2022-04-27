import re
from typing import Tuple, cast


def _normalize(component: str) -> int:
    """Normalize a version component.

    In case:
    - the component is a number, it's casted to int.
    - the component has both digits and letters, it's casted to int, and subtracted
        by one. This is just to make sure that `1.0dev`, 1.0rc`, and analogous are lower
        than `1.0`.
    """
    match = cast(re.Match, re.search(r"\d+", component))
    if match.group(0) == component:
        return int(component)
    else:
        return int(match.group(0)) - 1


def version_parse(version: str) -> Tuple[int, int, int]:
    """Parse version string into tuple of ints."""
    splitted_version = version.split(".")
    if len(splitted_version) > 3:
        splitted_version = splitted_version[:3]
    while len(splitted_version) < 3:
        splitted_version = splitted_version + ["0"]
    splitted_version = [_normalize(component) for component in splitted_version]
    return tuple(splitted_version)
