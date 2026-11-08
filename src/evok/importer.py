"""Zero-venv sys.meta_path virtualization engine.

Enables loading Python modules and packages directly from the unpacked wheel cache
or custom locations without creating a .venv directory on disk.
"""

from __future__ import annotations

import importlib.abc
import importlib.machinery
import importlib.util
import sys
from collections.abc import Sequence
from pathlib import Path


class EvokPackageLoader(importlib.abc.Loader):
    """Loader that executes Python modules from an arbitrary cache location."""

    def __init__(self, fullname: str, filepath: Path, is_package: bool) -> None:
        self.fullname = fullname
        self.filepath = filepath
        self.is_package = is_package

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> None:
        # Default module creation semantics
        return None

    def exec_module(self, module: object) -> None:
        code = self.filepath.read_bytes()
        compiled = compile(code, str(self.filepath), "exec")
        if self.is_package:
            module.__path__ = [str(self.filepath.parent)]
        module.__file__ = str(self.filepath)
        module.__loader__ = self
        # Execute in module namespace
        exec(compiled, module.__dict__)  # noqa: S102


class EvokMetaPathFinder(importlib.abc.MetaPathFinder):
    """Custom MetaPathFinder mapping import statements directly to cached packages."""

    def __init__(self, search_paths: Sequence[Path | str] | None = None) -> None:
        self.search_paths: list[Path] = [Path(p).resolve() for p in (search_paths or [])]

    def add_path(self, path: Path | str) -> None:
        p = Path(path).resolve()
        if p not in self.search_paths:
            self.search_paths.insert(0, p)

    def remove_path(self, path: Path | str) -> None:
        p = Path(path).resolve()
        if p in self.search_paths:
            self.search_paths.remove(p)

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None = None,
        target: object | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        parts = fullname.split(".")
        rel_mod_path = "/".join(parts) + ".py"
        rel_pkg_path = "/".join(parts) + "/__init__.py"

        # Search across registered paths
        roots = [Path(p) for p in path] if path else self.search_paths

        for root in roots:
            # Check package directory: root / pkg / __init__.py
            candidate_pkg = root / rel_pkg_path
            if candidate_pkg.is_file():
                loader = EvokPackageLoader(fullname, candidate_pkg, is_package=True)
                spec = importlib.machinery.ModuleSpec(
                    fullname,
                    loader,
                    origin=str(candidate_pkg),
                    is_package=True,
                )
                spec.submodule_search_locations = [str(candidate_pkg.parent)]
                return spec

            # Check single-file module: root / mod.py
            candidate_mod = root / rel_mod_path
            if candidate_mod.is_file():
                loader = EvokPackageLoader(fullname, candidate_mod, is_package=False)
                return importlib.machinery.ModuleSpec(
                    fullname,
                    loader,
                    origin=str(candidate_mod),
                    is_package=False,
                )

        return None


# Global active finder reference
_ACTIVE_FINDER: EvokMetaPathFinder | None = None


def install_importer(search_paths: Sequence[Path | str] | None = None) -> EvokMetaPathFinder:
    """Install EvokMetaPathFinder at the head of sys.meta_path."""
    global _ACTIVE_FINDER
    if _ACTIVE_FINDER is None:
        _ACTIVE_FINDER = EvokMetaPathFinder(search_paths)
        sys.meta_path.insert(0, _ACTIVE_FINDER)
    else:
        for p in search_paths or []:
            _ACTIVE_FINDER.add_path(p)
    return _ACTIVE_FINDER


def uninstall_importer() -> None:
    """Remove EvokMetaPathFinder from sys.meta_path."""
    global _ACTIVE_FINDER
    if _ACTIVE_FINDER in sys.meta_path:
        sys.meta_path.remove(_ACTIVE_FINDER)
    _ACTIVE_FINDER = None
