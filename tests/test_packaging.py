"""Behavioral tests for CLI packaging, distribution artifacts, and Homebrew integration."""

from __future__ import annotations

import io
import sys
import tomllib
from pathlib import Path
from unittest.mock import patch

import pytest

import evok
from evok.cli import main

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_package_version_consistency() -> None:
    """Verify version is consistent across package and pyproject.toml."""
    pyproject_path = REPO_ROOT / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)
    assert evok.__version__ == pyproject["project"]["version"]
    assert evok.__version__ == "0.1.2"


def test_cli_version_argument() -> None:
    """Verify ev --version and -v print version and exit cleanly."""
    stdout_buf = io.StringIO()
    with patch("sys.stdout", stdout_buf):
        rc = main(["--version"])
    assert rc == 0
    assert stdout_buf.getvalue().strip() == f"evok {evok.__version__}"

    stdout_buf = io.StringIO()
    with patch("sys.stdout", stdout_buf):
        rc = main(["-v"])
    assert rc == 0
    assert stdout_buf.getvalue().strip() == f"evok {evok.__version__}"


def test_homebrew_tap_packaging_artifacts() -> None:
    """Verify Formula template for wispsy/homebrew-tap exists."""
    formula_path = REPO_ROOT / "packaging" / "homebrew" / "Formula" / "evok.rb"
    assert formula_path.exists()
    formula_content = formula_path.read_text(encoding="utf-8")
    assert "class Evok < Formula" in formula_content
    assert (
        "https://files.pythonhosted.org/packages/source/e/evok/evok-0.1.0.tar.gz" in formula_content
    )

    publish_script = REPO_ROOT / "scripts" / "publish_homebrew.py"
    assert publish_script.exists()


def test_homebrew_formula_rendering() -> None:
    """Verify render_formula includes python@3.14 dependency and virtualenv target."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from scripts.publish_homebrew import render_formula, render_tap_readme

    formula_str = render_formula("0.1.0", "dummy_sha256")
    assert 'depends_on "python@3.14"' in formula_str
    assert "virtualenv_install_with_resources" in formula_str
    assert "bin}/ev --version" in formula_str
    assert "bin}/evok --version" in formula_str

    readme_str = render_tap_readme()
    assert "brew tap wispsy/tap" in readme_str
    assert "brew install evok" in readme_str
    assert "brew install clownfish" in readme_str


def test_new_homebrew_version_requires_its_own_archive_digest(tmp_path, monkeypatch):
    from scripts import publish_homebrew

    monkeypatch.setattr(publish_homebrew, "DIST_DIR", tmp_path)
    monkeypatch.setattr(publish_homebrew, "get_version", lambda: "0.1.1")
    monkeypatch.setattr(sys, "argv", ["publish_homebrew", "--version", "0.1.1", "--dry-run"])
    with pytest.raises(SystemExit) as error:
        publish_homebrew.main()
    assert error.value.code == 2
