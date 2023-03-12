import os
import ssl
from pathlib import Path
from typing import List, Optional, Tuple, Union


def create_ssl_context(
    certfile: Union[str, os.PathLike],
    keyfile: Optional[Union[str, os.PathLike]],
    password: Optional[str],
    ssl_version: int,
    cert_reqs: int,
    ca_certs: Optional[Union[str, os.PathLike]],
    ciphers: Optional[str],
) -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl_version)
    get_password = (lambda: password) if password else None
    ctx.load_cert_chain(certfile, keyfile, get_password)
    ctx.verify_mode = ssl.VerifyMode(cert_reqs)
    if ca_certs:
        ctx.load_verify_locations(ca_certs)
    if ciphers:
        ctx.set_ciphers(ciphers)
    return ctx


def is_dir(path: Path) -> bool:
    try:
        if not path.is_absolute():
            path = path.resolve()
        return path.is_dir()
    except OSError:
        return False


def resolve_reload_patterns(
    patterns_list: List[str], directories_list: List[str]
) -> Tuple[List[str], List[Path]]:
    directories: List[Path] = list(set(map(Path, directories_list.copy())))
    patterns: List[str] = patterns_list.copy()

    current_working_directory = Path.cwd()
    for pattern in patterns_list:
        # Special case for the .* pattern, otherwise this would only match
        # hidden directories which is probably undesired
        if pattern == ".*":
            continue
        patterns.append(pattern)
        if is_dir(Path(pattern)):
            directories.append(Path(pattern))
        else:
            for match in current_working_directory.glob(pattern):
                if is_dir(match):
                    directories.append(match)

    directories = list(set(directories))
    directories = list(map(Path, directories))
    directories = list(map(lambda x: x.resolve(), directories))
    directories = list(
        {reload_path for reload_path in directories if is_dir(reload_path)}
    )

    children = []
    for j in range(len(directories)):
        for k in range(j + 1, len(directories)):
            if directories[j] in directories[k].parents:
                children.append(directories[k])  # pragma: py-darwin
            elif directories[k] in directories[j].parents:
                children.append(directories[j])

    directories = list(set(directories).difference(set(children)))

    return list(set(patterns)), directories


def _normalize_dirs(dirs: Union[List[str], str, None]) -> List[str]:
    if dirs is None:
        return []
    if isinstance(dirs, str):
        return [dirs]
    return list(set(dirs))
