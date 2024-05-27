import pprint
import xml.etree.ElementTree as ET
import subprocess

import httpx

GENERATED_FILENAME = "uvicorn/protocols/http/tls_const.py"

TLS_PARAMETERS_URL = "https://www.iana.org/assignments/tls-parameters/tls-parameters.xml"
NAMESPACES = {"iana": "http://www.iana.org/assignments"}
TLS_CIPHER_SUITES_XPATH = './/iana:registry[@id="tls-parameters-4"]/iana:record'

content = httpx.get(TLS_PARAMETERS_URL).content
root = ET.fromstring(content)

tls_cipher_suites = {}

for record in root.findall(TLS_CIPHER_SUITES_XPATH, NAMESPACES):
    cipher = record.find("iana:description", NAMESPACES).text
    if cipher == "Unassigned":
        continue
    if cipher == "Reserved":
        continue

    value = record.find("iana:value", NAMESPACES).text
    if "-" in value:
        continue

    vs = [int(v, 16) for v in value.split(",")]
    code = (vs[0] << 8) + vs[1]
    tls_cipher_suites[cipher] = code


GENERATED_SOURCE = f"""
# generated by tools/generate_tls_const.py

from __future__ import annotations

from typing import Final

TLS_CIPHER_SUITES: Final[dict[str, int]] = {pprint.pformat(tls_cipher_suites)}
"""


with open(GENERATED_FILENAME, "wt") as fp:
    fp.write(GENERATED_SOURCE)

subprocess.run(["ruff", "format", GENERATED_FILENAME])
subprocess.run(["ruff", "check", "--fix", GENERATED_FILENAME])