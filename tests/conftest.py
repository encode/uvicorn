import pytest
import trustme


@pytest.fixture
def tls_certificate_authority():
    return trustme.CA()


@pytest.fixture
def tls_certificate(tls_certificate_authority):
    return tls_certificate_authority.issue_server_cert(
        'localhost',
        '127.0.0.1',
        '::1',
    )


@pytest.fixture(scope="function")
def certfile_and_keyfile(tls_certificate_authority, tmp_path):
    certfile = str(tmp_path / "cert.pem")
    tls_certificate_authority.cert_pem.write_to_path(certfile)
    keyfile = str(tmp_path / "key.pem")
    tls_certificate_authority.private_key_pem.write_to_path(keyfile)
    return certfile, keyfile
