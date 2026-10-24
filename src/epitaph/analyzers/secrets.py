"""Enmascarado de secretos antes de cualquier inferencia."""

from __future__ import annotations

import re

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("AWSKey", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("GitHubToken", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("GitLabToken", re.compile(r"glpat-[A-Za-z0-9_-]{20,}")),
    ("SlackToken", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("JWT", re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")),
    ("PrivateKey", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    (
        "GenericSecret",
        re.compile(
            r"""(?i)\b(?:password|passwd|secret|api[_-]?key|access[_-]?token)\b\s*[:=]\s*['"][^'"]{6,}['"]"""
        ),
    ),
]


def mask(text: str) -> tuple[str, list[dict]]:
    """Devuelve el texto enmascarado y los hallazgos (sin el valor original)."""
    findings: list[dict] = []
    masked = text
    for kind, pattern in PATTERNS:
        for match in pattern.finditer(masked):
            sample = match.group(0)[:4] + "****"
            findings.append({"type": kind, "sample": sample})
        masked = pattern.sub(f"[REDACTED:{kind}]", masked)
    return masked, findings


def scan_text(text: str) -> list[dict]:
    findings: list[dict] = []
    for kind, pattern in PATTERNS:
        for match in pattern.finditer(text):
            findings.append({"type": kind, "sample": match.group(0)[:4] + "****"})
    return findings
