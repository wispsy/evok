import zipfile
from pathlib import Path

from evok.cache import WheelCache, materialize_tree, reflink_file


def test_reflink_file(tmp_path: Path) -> None:
    src = tmp_path / "src.txt"
    dst = tmp_path / "dst.txt"
    src.write_text("hello reflink world", encoding="utf-8")

    strategy = reflink_file(src, dst)
    assert strategy in ("clonefile", "ficlone", "hardlink", "copy")
    assert dst.exists()
    assert dst.read_text(encoding="utf-8") == "hello reflink world"


def test_materialize_tree(tmp_path: Path) -> None:
    src_dir = tmp_path / "source"
    dst_dir = tmp_path / "target"

    (src_dir / "pkg").mkdir(parents=True)
    (src_dir / "pkg" / "__init__.py").write_text("# init", encoding="utf-8")
    (src_dir / "pkg" / "module.py").write_text("x = 42", encoding="utf-8")

    counts = materialize_tree(src_dir, dst_dir)
    assert sum(counts.values()) == 2
    assert (dst_dir / "pkg" / "__init__.py").read_text(encoding="utf-8") == "# init"
    assert (dst_dir / "pkg" / "module.py").read_text(encoding="utf-8") == "x = 42"


def test_wheel_cache_unpack_and_install(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    cache = WheelCache(cache_root)

    # Create dummy wheel zip
    wheel_file = tmp_path / "demo_pkg-1.0.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel_file, "w") as zf:
        zf.writestr("demo_pkg/__init__.py", "VAL = 100\n")
        zf.writestr("demo_pkg-1.0.0.dist-info/METADATA", "Name: demo-pkg\nVersion: 1.0.0\n")

    unpacked = cache.unpack_wheel(wheel_file)
    assert unpacked.is_dir()
    assert cache.is_cached("demo-pkg", "1.0.0")

    # Install into virtual environment site-packages
    site_packages = tmp_path / "site-packages"
    counts = cache.install_to("demo-pkg", "1.0.0", site_packages)
    assert sum(counts.values()) >= 2
    assert (site_packages / "demo_pkg" / "__init__.py").exists()
    assert (site_packages / "demo_pkg-1.0.0.dist-info" / "METADATA").exists()
