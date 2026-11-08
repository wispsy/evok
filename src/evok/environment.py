"""Environment management: ephemeral in-process environments and virtual environment materialization."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from evok.cache import WheelCache, default_cache_dir, materialize_tree
from evok.importer import EvokMetaPathFinder
from evok.resolver import ResolutionGraph


class Environment:
    """Runtime execution environment."""

    def __init__(
        self,
        graph: ResolutionGraph | None = None,
        paths: list[Path] | None = None,
        cache: WheelCache | None = None,
    ) -> None:
        self.graph = graph or ResolutionGraph()
        self.paths = paths or []
        self.cache = cache or WheelCache()

    def import_module(self, name: str) -> Any:
        """Import a module directly in the current environment."""
        return importlib.import_module(name)

    @classmethod
    @contextmanager
    def ephemeral(
        cls,
        graph: ResolutionGraph | None = None,
        search_paths: list[Path | str] | None = None,
        cache_dir: Path | str | None = None,
    ) -> Generator[Environment, None, None]:
        """Context manager providing an isolated in-process ephemeral environment.

        Hooks into sys.meta_path so that resolved packages from the global cache
        or search_paths are importable with zero disk-copying or venv creation.
        """
        cache = WheelCache(cache_dir or default_cache_dir())
        resolved_paths: list[Path] = [Path(p).resolve() for p in (search_paths or [])]

        if graph:
            for name, candidate in graph.packages.items():
                wheel_dir = cache.get_wheel_dir(name, str(candidate.version))
                if wheel_dir.is_dir():
                    resolved_paths.append(wheel_dir)

        finder = EvokMetaPathFinder(resolved_paths)
        sys.meta_path.insert(0, finder)
        env = cls(graph=graph, paths=resolved_paths, cache=cache)

        modules_before = set(sys.modules.keys())
        try:
            yield env
        finally:
            if finder in sys.meta_path:
                sys.meta_path.remove(finder)
            # Prune newly loaded ephemeral modules to keep interpreter clean
            newly_loaded = set(sys.modules.keys()) - modules_before
            for mod in newly_loaded:
                # Only prune modules loaded from our finder
                mod_obj = sys.modules.get(mod)
                if mod_obj and getattr(mod_obj, "__loader__", None).__class__.__name__ == "EvokPackageLoader":
                    sys.modules.pop(mod, None)

    def materialize(self, target_dir: Path | str, strategy: str = "auto") -> dict[str, int]:
        """Materialize the environment to a target directory (e.g., site-packages) using zero-copy links."""
        target = Path(target_dir).resolve()
        target.mkdir(parents=True, exist_ok=True)
        total_counts: dict[str, int] = {}

        for name, candidate in self.graph.packages.items():
            wheel_dir = self.cache.get_wheel_dir(name, str(candidate.version))
            if wheel_dir.is_dir():
                counts = materialize_tree(wheel_dir, target, strategy=strategy)
                for k, v in counts.items():
                    total_counts[k] = total_counts.get(k, 0) + v

        return total_counts
