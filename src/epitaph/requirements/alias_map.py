"""Mapa import → paquete de distribución."""

from __future__ import annotations

ALIASES = {
    "pil": "Pillow",
    "yaml": "PyYAML",
    "cv2": "opencv-python",
    "bs4": "beautifulsoup4",
    "sklearn": "scikit-learn",
    "dotenv": "python-dotenv",
    "jwt": "PyJWT",
    "dateutil": "python-dateutil",
    "serial": "pyserial",
    "magic": "python-magic",
    "attr": "attrs",
    "google": "google-api-python-client",
    "OpenSSL": "pyOpenSSL",
    "MySQLdb": "mysqlclient",
    "psycopg2": "psycopg2-binary",
    "Crypto": "pycryptodome",
    "win32api": "pywin32",
    "gi": "PyGObject",
    "wx": "wxPython",
    "pkg_resources": "setuptools",
}

AMBIGUOUS = {
    "magic": "python-magic o python-magic-bin",
    "google": "google-api-python-client o google-cloud-*",
    "crypto": "pycryptodome o pycrypto",
}


def package_for(import_name: str) -> str:
    return ALIASES.get(import_name, import_name)


def normalize(name: str) -> str:
    base = name.split("[")[0].split(";")[0].strip()
    for separator in ("==", ">=", "<=", "~=", "!=", ">", "<", "@"):
        base = base.split(separator)[0]
    return base.strip().lower().replace("_", "-")
