import pytest
import trustme


@pytest.fixture(scope="function")
def certfile_and_keyfile(tmp_path):
    ca = trustme.CA()
    certfile = str(tmp_path / "cert.pem")
    ca.cert_pem.write_to_path(certfile)
    keyfile = str(tmp_path / "key.pem")
    ca.private_key_pem.write_to_path(keyfile)
    return certfile, keyfile
