from pathlib import Path

from evok.ast_scanner import scan_file_imports, scan_project


def test_scan_file_imports(tmp_path: Path) -> None:
    code = """
import os
import sys
import yaml
from PIL import Image
from .local_mod import helper

def run():
    import requests
    pass
"""
    f = tmp_path / "sample.py"
    f.write_text(code, encoding="utf-8")

    imports = scan_file_imports(f)
    assert "os" in imports
    assert "sys" in imports
    assert "yaml" in imports
    assert "PIL" in imports
    assert "requests" in imports
    assert "local_mod" not in imports  # relative import ignored


def test_scan_project_dependencies(tmp_path: Path) -> None:
    src_dir = tmp_path / "src" / "my_app"
    src_dir.mkdir(parents=True)
    (src_dir / "__init__.py").write_text("", encoding="utf-8")
    (src_dir / "main.py").write_text("import yaml\nimport requests\n", encoding="utf-8")

    # pyproject.toml declaring only pyyaml and unused rich
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
name = "my_app"
dependencies = [
    "pyyaml>=6.0",
    "rich>=13.0.0",
]
""",
        encoding="utf-8",
    )

    result = scan_project(tmp_path)
    # yaml is mapped to pyyaml
    assert "pyyaml" in result.inferred_packages
    assert "requests" in result.inferred_packages
    assert "rich" in result.unused_dependencies
    assert "requests" in result.missing_dependencies
    assert "pyyaml" not in result.missing_dependencies
    assert "pyyaml" not in result.unused_dependencies
