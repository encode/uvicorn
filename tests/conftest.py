import pytest
import trustme


@pytest.fixture
def tls_certificate_authority() -> trustme.CA:
    return trustme.CA()


@pytest.fixture
def tls_certificate(tls_certificate_authority):
    return tls_certificate_authority.issue_server_cert(
        "localhost",
        "127.0.0.1",
        "::1",
    )


@pytest.fixture
def tls_ca_certificate_pem_path(tls_certificate_authority):
    with tls_certificate_authority.cert_pem.tempfile() as ca_cert_pem:
        yield ca_cert_pem


@pytest.fixture
def tls_ca_certificate_private_key_path(tls_certificate_authority):
    with tls_certificate_authority.private_key_pem.tempfile() as private_key:
        yield private_key


@pytest.fixture
def tls_certificate_pem_path(tls_certificate):
    with tls_certificate.private_key_and_cert_chain_pem.tempfile() as cert_pem:
        yield cert_pem
