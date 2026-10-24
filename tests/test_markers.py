from __future__ import annotations

from epitaph.readme.markers import fingerprint, format_block, parse


def test_parse_roundtrip() -> None:
    block = format_block("overview", "## Descripción\n\nHola.")
    parsed = parse(f"# T\n\n{block}\n")
    assert parsed.errors == []
    assert parsed.ids == ["overview"]
    assert parsed.segments[1].kind == "auto"
    assert parsed.segments[1].content.strip() == "## Descripción\n\nHola."
    assert parsed.segments[1].fp == fingerprint("## Descripción\n\nHola.")


def test_parse_preserves_text() -> None:
    text = "antes\n<!-- epitaph:begin id=a fp=1 -->\ncontenido\n<!-- epitaph:end id=a -->\ndespués"
    parsed = parse(text)
    assert parsed.segments[0].raw == "antes"
    assert parsed.segments[2].raw == "después"


def test_parse_detects_missing_end() -> None:
    parsed = parse("<!-- epitaph:begin id=a -->\ncontenido")
    assert parsed.errors
    assert parsed.ids == []


def test_parse_detects_duplicate_ids() -> None:
    block = format_block("a", "x")
    parsed = parse(f"{block}\n\n{block}")
    assert any("duplicado" in error for error in parsed.errors)


def test_fingerprint_is_stable() -> None:
    assert fingerprint("  hola  ") == fingerprint("hola")
    assert fingerprint("hola") != fingerprint("hola2")
