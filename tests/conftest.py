import socket

import pytest

CERTIFICATE = b"""-----BEGIN CERTIFICATE-----
MIIEaDCCAtCgAwIBAgIRAPeU748qfVOTZJ7rj5DupbowDQYJKoZIhvcNAQELBQAw
fTEeMBwGA1UEChMVbWtjZXJ0IGRldmVsb3BtZW50IENBMSkwJwYDVQQLDCBmcmFp
cjUwMEBmcmFpcjUwMC1QcmVjaXNpb24tNTUyMDEwMC4GA1UEAwwnbWtjZXJ0IGZy
YWlyNTAwQGZyYWlyNTAwLVByZWNpc2lvbi01NTIwMB4XDTE5MDEwOTIwMzQ1N1oX
DTI5MDEwOTIwMzQ1N1owVDEnMCUGA1UEChMebWtjZXJ0IGRldmVsb3BtZW50IGNl
cnRpZmljYXRlMSkwJwYDVQQLDCBmcmFpcjUwMEBmcmFpcjUwMC1QcmVjaXNpb24t
NTUyMDCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBALahGo80UFExe7Iv
jPDulPP9Vu3mPVW/4XhrvmbwjHPSXk6nvK34kdDmGsS/UVgtSMH+sdMNFavkhyK/
b6PW5dPy+febfxlnaOkrZ5ptYx5IG1l/CNY/QDpQKGljW9YGQDV2t9apgKgT1/Ob
JIKf/rfd2o94iyxlrRnbXXidyMa1E6loo1AzzaN/g17dnblIL7ZCZtflgbsgnytw
UtwS92kTsvMHvuzM7Paz2M0xx+RNtQ2rq51fwph55gn7HLlBFEbkrMsfFj7hEquC
vJYvyrIEvaQLMyIOf+6/OgmrG9Z5ioMV4WAW9FLSuzXuuJruQc7FwQl4XIuE8d0M
jPjRfIcCAwEAAaOBizCBiDAOBgNVHQ8BAf8EBAMCBaAwEwYDVR0lBAwwCgYIKwYB
BQUHAwEwDAYDVR0TAQH/BAIwADAfBgNVHSMEGDAWgBTfMtd0Al3Ly09elEje6jyl
b3EQmjAyBgNVHREEKzApgglsb2NhbGhvc3SHBAAAAACHBH8AAAGHEAAAAAAAAAAA
AAAAAAAAAAEwDQYJKoZIhvcNAQELBQADggGBADLu7RSMVnUiRNyTqIM3aMmkUXmL
xSPB/SZRifqVwmp9R6ygAZWzC7Lw5BpX2WCde1jqWJZw1AjYbe4w5i8e9jaiUyYZ
eaLuQN7/+dyWeMIfFKx7thDxmati+OkSJSoojROA1v4NY7QAIM6ycfFkwTBRokPz
42srfR+XXrvdNmBRqjpvpr48SAn44uvqAkVr3kNgqs1xycPgjsFvMO7qZlU6w/ev
/7QFUgtyZS/Saa4s3yRXHZ++g3SpPinrzf8VqmovL/MoaqB/tYVjOA/1B3QAkli6
DIl+99eKANlqARXzMeXvgLpcg+1oAw0hYjFpCtqKhovhQzqN6KlAbmJ9JWTk35x8
81nOERZH5dh6JZoHzaaB/ZMEjWkmHnyi4bf5dXiPLzfXJslbQKHhnSt4nfZiSodS
brUVv/sux119zyUPe9iA6NNPFS/No1XOKcHrG19jiXTq/HIdJRoIrN6eRJDTRVK1
HyJ6uTvTJDu4ceBp2J1gz7R5opWbGyytDGg3Tw==
-----END CERTIFICATE-----
"""

PRIVATE_KEY = b"""-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC2oRqPNFBRMXuy
L4zw7pTz/Vbt5j1Vv+F4a75m8Ixz0l5Op7yt+JHQ5hrEv1FYLUjB/rHTDRWr5Ici
v2+j1uXT8vn3m38ZZ2jpK2eabWMeSBtZfwjWP0A6UChpY1vWBkA1drfWqYCoE9fz
mySCn/633dqPeIssZa0Z2114ncjGtROpaKNQM82jf4Ne3Z25SC+2QmbX5YG7IJ8r
cFLcEvdpE7LzB77szOz2s9jNMcfkTbUNq6udX8KYeeYJ+xy5QRRG5KzLHxY+4RKr
gryWL8qyBL2kCzMiDn/uvzoJqxvWeYqDFeFgFvRS0rs17ria7kHOxcEJeFyLhPHd
DIz40XyHAgMBAAECggEAZ1q7Liob/icz6r5wU/WhhIduB8qSEZI65qyLH7Sot+9p
Abh51jbjRsbChXAEeBOAppEeT+OKzTHSrH6MjrtSa+WJQ3DTuCvGupae1k1rl7qV
B8wV0zIOhjHQ/PuHAJOfCOK73ZclwXkhcLLvMaGcRLAgPaupj6GnGggEWPtqodDo
qBOcixT3/lMW5M1GklkqJqbD8g8qcx7SFBwORJjpwVX84Ynnursu0ZvTfK/CzZTk
D5t/UXyRV5Y5QBkzKIKzC0qUHv4eMIqkzlPBYx2PnAgrHokOm9/RS28yKT2DVPhw
t311ZM6+Z5AxfKamARWZbZdC8RG5Qo0ujLmgogNn2QKBgQDsqpwO+/yJlvF81nf9
0Ye5o0OdOdD5q1ra46PyhQ56hIC5cRZx3s3E9hUFDcot81qj9nMTpSGJL5J6GqAY
W7p3PbpYxT27MDjthgHHcZy7hu1M9no65ZAK1ElxVhKMgl89RQu/HQoa6Uh3qjbF
X0edTBTBJoGOYQ1lVaoL8s307QKBgQDFjGtEKubolZ0OqFb361fDcYs0RDKNlNxy
RIMM6Dhl0tgGHxNFuFNlLdjKyPEltfNaK0L0W3i3Ndf5sUlr2MuXYgO6RRqWo/D2
Tr2/jd6gsVKLK871WD7IS5SbCirCwuEsZQsZ2J2TWECoPqc8L3iZwyW6VGRkIW+K
o2Sl7P4cwwKBgQCnhAt6P7p82S6NInFEY28iYwGU5DuavUNN9BszqiKZbfh/SiCM
8RvM8jHmpeAZrkrWC7dgjF20cMvJSddP5n2RsUuZUeNj/7oLxfK0bSJ3SgXlmADk
d2EBiUmCw13VvuISyDCMUc25Rq5YpU6nXc2e9R8rqEnDscZ9l6kJVA+b8QKBgBAZ
coB6spjP4J3aMERCJMPj1AFtcWVCdXjGhpudrUL3HO3ayHpNHFbJlrpoB+cX3f5C
OlGpxru/optRzHcCkw0CSuV6TkFqmO+p2SLsT/Fuohh/eH1cNLmkFzdPa861jR5O
GcqAcc8ZSSOs/3oTMFPvqHp3+DqE0w9MY552Ivt7AoGATtJkMAg9M4U/5qIsCbRz
LplSCRvcarrg+czXW1re6y117rVjRHPCHgT//azsBDER0WpWSGv7XEnZwnz8U6Cn
FCXoiqqEJuD2wLwQlhb7QVXYTMdCwfPj5WV7ARJO1N4ty3g8x+jnTQCVoMpdhgxC
Sflxx+6bI4XMh0AsZhgtdW4=
-----END PRIVATE KEY-----
"""


@pytest.fixture(scope="function")
def certfile_and_keyfile(tmp_path):
    certfile = str(tmp_path / "cert.pem")
    with open(certfile, "bw") as fout:
        fout.write(CERTIFICATE)

    keyfile = str(tmp_path / "key.pem")
    with open(keyfile, "bw") as fout:
        fout.write(PRIVATE_KEY)

    return certfile, keyfile


ENV_FILE = """KEY_TRUE="1"
KEY_FALSE=""
WEB_CONCURRENCY=2048
"""


@pytest.fixture(scope="function")
def env_file(tmp_path):
    envfile = str(tmp_path / ".env")
    with open(envfile, "w") as fout:
        fout.write(ENV_FILE)
    return envfile


INI_LOG_CONFIG = """[loggers]
keys=root
[handlers]
keys=h
[formatters]
keys=f
[logger_root]
level=INFO
handlers=h
[handler_h]
class=StreamHandler
level=INFO
formatter=f
args=(sys.stderr,)
[formatter_f]
format=%(asctime)s %(name)s %(levelname)-4s %(message)s
"""


@pytest.fixture(scope="function")
def ini_log_config(tmp_path):
    inifile = str(tmp_path / "log_config.ini")
    with open(inifile, "w") as fout:
        fout.write(INI_LOG_CONFIG)
    return inifile


@pytest.fixture(scope="function")
def socket_file(tmp_path):
    sockfile = str(tmp_path / "socket")
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    fd = sock.fileno()
    try:
        sock.bind(sockfile)
        yield sockfile, sock, fd
    finally:
        sock.close()
