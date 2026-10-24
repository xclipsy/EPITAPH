from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def sample_repo(tmp_path: Path) -> Path:
    root = tmp_path / "sample"
    (root / "src" / "app").mkdir(parents=True)
    (root / "tests").mkdir()

    (root / "pyproject.toml").write_text(
        "[project]\nname = \"sample\"\nversion = \"0.1.0\"\n\n"
        "[tool.ruff]\nline-length = 100\n",
        encoding="utf-8",
    )
    (root / "requirements.txt").write_text("httpx>=0.27\nrich>=13.0\n", encoding="utf-8")
    (root / "LICENSE").write_text("MIT License\n\nCopyright (c) 2026\n", encoding="utf-8")

    (root / "src" / "app" / "__init__.py").write_text("", encoding="utf-8")
    (root / "src" / "app" / "__main__.py").write_text(
        "from .core import run\n\n\nif __name__ == \"__main__\":\n    run()\n",
        encoding="utf-8",
    )
    (root / "src" / "app" / "core.py").write_text(
        "import httpx\nfrom .util import helper\n\n\ndef run():\n    return helper()\n",
        encoding="utf-8",
    )
    (root / "src" / "app" / "util.py").write_text(
        "from .core import run\n\n\ndef helper():\n    return 1\n",
        encoding="utf-8",
    )
    (root / "src" / "app" / "orphan.py").write_text(
        "import yaml\n\n\ndef unused():\n    return yaml.safe_load('a: 1')\n",
        encoding="utf-8",
    )
    (root / "tests" / "test_core.py").write_text(
        "from src.app.core import run\n\n\ndef test_run():\n    assert run() == 1\n",
        encoding="utf-8",
    )

    (root / "README.md").write_text(
        "# Sample\n\nTexto humano que debe sobrevivir.\n\n"
        "## Notas\n\nEsto no lo escribe EPITAPH.\n",
        encoding="utf-8",
    )
    return root
