import zipfile
from pathlib import Path

from evok.builder import build_sdist, build_wheel, build_zipapp


def test_build_wheel_and_sdist(tmp_path: Path) -> None:
    # Setup sample project
    proj_dir = tmp_path / "sample_project"
    proj_dir.mkdir()
    (proj_dir / "pyproject.toml").write_text(
        """[project]
name = "sample-proj"
version = "1.2.3"
description = "A sample package"
requires-python = ">=3.12"
dependencies = ["requests>=2.28"]
""",
        encoding="utf-8",
    )
    (proj_dir / "README.md").write_text("# Sample Proj\n", encoding="utf-8")
    src_dir = proj_dir / "src" / "sample_proj"
    src_dir.mkdir(parents=True)
    (src_dir / "__init__.py").write_text("GREETING = 'hello world'\n", encoding="utf-8")

    dist_dir = tmp_path / "dist"
    wheel = build_wheel(proj_dir, dist_dir)
    assert wheel.exists()
    assert wheel.name == "sample_proj-1.2.3-py3-none-any.whl"

    # Inspect wheel contents
    with zipfile.ZipFile(wheel, "r") as zf:
        namelist = zf.namelist()
        assert "sample_proj/__init__.py" in namelist
        assert "sample_proj-1.2.3.dist-info/METADATA" in namelist
        assert "sample_proj-1.2.3.dist-info/WHEEL" in namelist
        assert "sample_proj-1.2.3.dist-info/RECORD" in namelist

    sdist = build_sdist(proj_dir, dist_dir)
    assert sdist.exists()
    assert sdist.name == "sample_proj-1.2.3.tar.gz"


def test_build_zipapp(tmp_path: Path) -> None:
    src_dir = tmp_path / "app_src"
    src_dir.mkdir()
    (src_dir / "__main__.py").write_text("print('zipapp works')\n", encoding="utf-8")

    out_pyz = tmp_path / "app.pyz"
    build_zipapp(src_dir, out_pyz, main_entrypoint="__main__:None")
    assert out_pyz.exists()
    assert out_pyz.stat().st_size > 0
