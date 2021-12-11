import ssl

import pytest
import trustme
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

from uvicorn.config import LOGGING_CONFIG

# Workaround: pytest caplog not able to capture no-propagate loggers
# See also: https://github.com/pytest-dev/pytest/issues/3697
LOGGING_CONFIG["loggers"]["uvicorn"]["propagate"] = True


@pytest.fixture
def tls_certificate_authority() -> trustme.CA:
    return trustme.CA()


@pytest.fixture
def tls_certificate(tls_certificate_authority: trustme.CA) -> trustme.LeafCert:
    return tls_certificate_authority.issue_cert(
        "localhost",
        "127.0.0.1",
        "::1",
    )


@pytest.fixture
def tls_ca_certificate_pem_path(tls_certificate_authority: trustme.CA):
    with tls_certificate_authority.cert_pem.tempfile() as ca_cert_pem:
        yield ca_cert_pem


@pytest.fixture
def tls_ca_certificate_private_key_path(tls_certificate_authority: trustme.CA):
    with tls_certificate_authority.private_key_pem.tempfile() as private_key:
        yield private_key


@pytest.fixture
def tls_certificate_private_key_encrypted_path(tls_certificate):
    private_key = serialization.load_pem_private_key(
        tls_certificate.private_key_pem.bytes(),
        password=None,
        backend=default_backend(),
    )
    encrypted_key = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.BestAvailableEncryption(b"uvicorn password for the win"),
    )
    with trustme.Blob(encrypted_key).tempfile() as private_encrypted_key:
        yield private_encrypted_key


@pytest.fixture
def tls_certificate_private_key_path(tls_certificate: trustme.CA):
    with tls_certificate.private_key_pem.tempfile() as private_key:
        yield private_key


@pytest.fixture
def tls_certificate_key_and_chain_path(tls_certificate: trustme.LeafCert):
    with tls_certificate.private_key_and_cert_chain_pem.tempfile() as cert_pem:
        yield cert_pem


@pytest.fixture
def tls_certificate_server_cert_path(tls_certificate: trustme.LeafCert):
    with tls_certificate.cert_chain_pems[0].tempfile() as cert_pem:
        yield cert_pem


@pytest.fixture
def tls_ca_ssl_context(tls_certificate_authority: trustme.CA) -> ssl.SSLContext:
    ssl_ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    tls_certificate_authority.configure_trust(ssl_ctx)
    return ssl_ctx


@pytest.fixture(scope="package")
def reload_directory_structure(tmp_path_factory: pytest.TempPathFactory):
    """
    This fixture creates a directory structure to enable reload parameter tests

    The fixture has the following structure:
    root
    ├── [app, app_first, app_second, app_third]
    │   ├── css
    │   │   └── main.css
    │   ├── js
    │   │   └── main.js
    │   ├── src
    │   │   └── main.py
    │   └── sub
    │       └── sub.py
    ├── ext
    │   └── ext.jpg
    └── main.py
    """
    root = tmp_path_factory.mktemp("reload_directory")
    apps = ["app", "app_first", "app_second", "app_third"]

    root_file = root / "main.py"
    root_file.touch()

    dotted_file = root / ".dotted"
    dotted_file.touch()

    dotted_dir = root / ".dotted_dir"
    dotted_dir.mkdir()
    dotted_dir_file = dotted_dir / "file.txt"
    dotted_dir_file.touch()

    for app in apps:
        app_path = root / app
        app_path.mkdir()
        dir_files = [
            ("src", ["main.py"]),
            ("js", ["main.js"]),
            ("css", ["main.css"]),
            ("sub", ["sub.py"]),
        ]
        for directory, files in dir_files:
            directory_path = app_path / directory
            directory_path.mkdir()
            for file in files:
                file_path = directory_path / file
                file_path.touch()
    ext_dir = root / "ext"
    ext_dir.mkdir()
    ext_file = ext_dir / "ext.jpg"
    ext_file.touch()

    yield root
