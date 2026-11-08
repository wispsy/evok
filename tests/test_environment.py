import sys
from pathlib import Path

from evok.environment import Environment
from evok.importer import EvokMetaPathFinder, install_importer, uninstall_importer


def test_meta_path_finder_loading(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "virtual_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("MAGIC = 42\ndef hello(): return 'world'\n", encoding="utf-8")

    finder = EvokMetaPathFinder([tmp_path])
    sys.meta_path.insert(0, finder)
    try:
        import virtual_pkg

        assert virtual_pkg.MAGIC == 42
        assert virtual_pkg.hello() == "world"
    finally:
        if finder in sys.meta_path:
            sys.meta_path.remove(finder)
        sys.modules.pop("virtual_pkg", None)


def test_environment_ephemeral_context(tmp_path: Path) -> None:
    mod_dir = tmp_path / "ephem_dir"
    mod_dir.mkdir()
    (mod_dir / "ephem_mod.py").write_text("ANSWER = 'ephemeral_success'\n", encoding="utf-8")

    with Environment.ephemeral(search_paths=[mod_dir]) as env:
        mod = env.import_module("ephem_mod")
        assert mod.ANSWER == "ephemeral_success"
        assert "ephem_mod" in sys.modules

    # After context exit, the module is cleanly unregistered
    assert "ephem_mod" not in sys.modules


def test_install_uninstall_importer(tmp_path: Path) -> None:
    finder = install_importer([tmp_path])
    assert finder in sys.meta_path
    uninstall_importer()
    assert finder not in sys.meta_path
