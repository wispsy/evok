from pathlib import Path

from evok.cli import main


def test_cli_init_and_scan(tmp_path: Path) -> None:
    proj_dir = tmp_path / "cli_proj"

    # Test ev init
    rc = main(["init", str(proj_dir), "--name", "cli-proj"])
    assert rc == 0
    assert (proj_dir / "pyproject.toml").exists()
    assert (proj_dir / "src" / "cli_proj" / "__init__.py").exists()

    # Add code with unused and missing deps
    code_file = proj_dir / "src" / "cli_proj" / "app.py"
    code_file.write_text("import yaml\nimport requests\n", encoding="utf-8")

    # Add pyproject declared dependency
    pyproject = proj_dir / "pyproject.toml"
    content = pyproject.read_text(encoding="utf-8").replace(
        "dependencies = []", 'dependencies = ["pyyaml>=6.0", "unused-lib>=1.0"]'
    )
    pyproject.write_text(content, encoding="utf-8")

    # Test ev scan
    rc_scan = main(["scan", str(proj_dir)])
    assert rc_scan == 0

    # Test ev prune
    rc_prune = main(["prune", str(proj_dir)])
    assert rc_prune == 0
    updated_toml = pyproject.read_text(encoding="utf-8")
    assert "unused-lib" not in updated_toml


def test_cli_info() -> None:
    rc = main(["info"])
    assert rc == 0


def test_cli_build(tmp_path: Path) -> None:
    proj_dir = tmp_path / "built_proj"
    main(["init", str(proj_dir), "--name", "built-proj"])

    rc = main(["build", str(proj_dir), "--zipapp"])
    assert rc == 0
    dist = proj_dir / "dist"
    assert (dist / "built_proj-0.1.0-py3-none-any.whl").exists()
    assert (dist / "built_proj-0.1.0.tar.gz").exists()
    assert (dist / "built_proj.pyz").exists()


def test_cli_resolve() -> None:
    rc = main(["resolve", "requests>=2.0", "rich"])
    assert rc == 0
