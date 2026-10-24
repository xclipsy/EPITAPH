from __future__ import annotations

from collections import OrderedDict

from epitaph.readme.merge import merge


def test_new_document_contains_sections() -> None:
    sections = OrderedDict([("overview", "## Descripción\n\nHola")])
    result = merge(None, sections, title="Demo")
    assert result.changed
    assert result.text.startswith("# Demo")
    assert "<!-- epitaph:begin id=overview" in result.text


def test_human_text_is_preserved() -> None:
    existing = "# Demo\n\nTexto humano.\n\n## Notas\n\nNo tocar.\n"
    sections = OrderedDict([("overview", "## Descripción\n\nGenerado")])
    result = merge(existing, sections, title="Demo")
    assert "Texto humano." in result.text
    assert "No tocar." in result.text
    assert "Generado" in result.text


def test_idempotent() -> None:
    sections = OrderedDict(
        [
            ("overview", "## Descripción\n\nHola"),
            ("install", "## Instalación\n\n```bash\nuv sync\n```"),
        ]
    )
    first = merge(None, sections, title="Demo")
    second = merge(first.text, sections, title="Demo")
    assert second.changed is False
    assert second.text == first.text


def test_trailing_whitespace_does_not_trigger_rewrite() -> None:
    sections = OrderedDict([("overview", "## Descripción\n\nHola")])
    first = merge(None, sections, title="Demo")
    mutated = first.text.replace("Hola", "Hola   ")
    second = merge(mutated, sections, title="Demo")
    assert second.changed is False
    assert second.text == mutated


def test_only_changed_section_is_rewritten() -> None:
    sections = OrderedDict(
        [
            ("overview", "## Descripción\n\nHola"),
            ("license", "## Licencia\n\nMIT"),
        ]
    )
    first = merge(None, sections, title="Demo")
    license_before = first.text.split("<!-- epitaph:begin id=license")[1]

    updated = OrderedDict(
        [
            ("overview", "## Descripción\n\nAdiós"),
            ("license", "## Licencia\n\nMIT"),
        ]
    )
    second = merge(first.text, updated, title="Demo")

    assert second.changed is True
    assert second.changes == ["actualizada: overview"]
    assert second.text.split("<!-- epitaph:begin id=license")[1] == license_before


def test_missing_sections_are_appended() -> None:
    existing = merge(
        None, OrderedDict([("overview", "## Descripción\n\nHola")]), title="Demo"
    ).text
    sections = OrderedDict(
        [("overview", "## Descripción\n\nHola"), ("license", "## Licencia\n\nMIT")]
    )
    result = merge(existing, sections, title="Demo")
    assert "id=license" in result.text
    assert result.text.index("id=overview") < result.text.index("id=license")


def test_invalid_markers_do_not_overwrite() -> None:
    existing = "# Demo\n\n<!-- epitaph:begin id=x -->\nroto\n"
    sections = OrderedDict([("overview", "## Descripción\n\nHola")])
    result = merge(existing, sections, title="Demo")
    assert result.changed is False
    assert result.errors
    assert result.text == existing
    assert result.suggested is not None
