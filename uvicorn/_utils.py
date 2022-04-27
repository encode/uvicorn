import re
from typing import Tuple


def _normalize(component: str) -> int:
    match = re.search(r"\d+", component)
    if match:
        if match.group(0) == component:
            return int(component)
        else:
            return int(match.group(0)) - 1
    return 0


def version_parse(version: str) -> Tuple[int, int, int]:
    splitted_version = version.split(".")
    if len(splitted_version) > 3:
        splitted_version = splitted_version[:3]
    while len(splitted_version) < 3:
        splitted_version = splitted_version + ["0"]
    splitted_version = [_normalize(component) for component in splitted_version]
    return tuple(splitted_version)
