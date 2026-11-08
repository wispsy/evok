"""AST-driven dependency inference and dead-dependency pruning.

Inspects Python AST to discover third-party imports, maps module names to PyPI distributions,
and compares against pyproject.toml to flag missing or unused dependencies.
"""

from __future__ import annotations

import ast
import os
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

# Known mapping of top-level import name to canonical PyPI package name
KNOWN_IMPORT_MAP: dict[str, str] = {
    "yaml": "pyyaml",
    "cv2": "opencv-python",
    "PIL": "pillow",
    "bs4": "beautifulsoup4",
    "sklearn": "scikit-learn",
    "dateutil": "python-dateutil",
    "dotenv": "python-dotenv",
    "fitz": "pymupdf",
    "magic": "python-magic",
    "jwt": "pyjwt",
    "serial": "pyserial",
    "usb": "pyusb",
    "gi": "pygobject",
    "git": "gitpython",
    "jose": "python-jose",
    "multipart": "python-multipart",
}

_IGNORED_DIRS = {
    ".venv",
    "venv",
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "build",
    "dist",
    "site-packages",
}


def get_stdlib_modules() -> set[str]:
    """Return set of standard library module names."""
    if hasattr(sys, "stdlib_module_names"):
        return set(sys.stdlib_module_names)
    # Fallback list for older or custom runtimes
    return {
        "os",
        "sys",
        "io",
        "math",
        "json",
        "re",
        "time",
        "datetime",
        "pathlib",
        "typing",
        "ast",
        "unittest",
        "logging",
        "collections",
        "urllib",
        "http",
        "subprocess",
        "threading",
        "multiprocessing",
        "asyncio",
        "contextlib",
        "functools",
        "itertools",
        "shutil",
        "tempfile",
        "glob",
        "hashlib",
        "random",
        "socket",
        "ssl",
        "inspect",
        "importlib",
        "ctypes",
        "struct",
        "copy",
        "enum",
    }


def normalize_package_name(name: str) -> str:
    """Normalize package name according to PEP 503."""
    return name.lower().replace("_", "-").replace(".", "-")


class ImportVisitor(ast.NodeVisitor):
    """AST visitor collecting imported module names."""

    def __init__(self) -> None:
        self.imports: set[str] = set()

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            root = alias.name.split(".")[0]
            if root:
                self.imports.add(root)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level == 0 and node.module:
            root = node.module.split(".")[0]
            if root:
                self.imports.add(root)
        self.generic_visit(node)


def scan_file_imports(file_path: Path | str) -> set[str]:
    """Parse a single Python file and return all root imported module names."""
    p = Path(file_path)
    try:
        content = p.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(content, filename=str(p))
    except (SyntaxError, UnicodeDecodeError):
        return set()

    visitor = ImportVisitor()
    visitor.visit(tree)
    return visitor.imports


@dataclass
class ScanResult:
    """Results of AST dependency scanning across a codebase."""

    all_imports: set[str] = field(default_factory=set)
    inferred_packages: set[str] = field(default_factory=set)
    declared_dependencies: set[str] = field(default_factory=set)
    missing_dependencies: set[str] = field(default_factory=set)
    unused_dependencies: set[str] = field(default_factory=set)


def map_module_to_package(module_name: str) -> str:
    """Map an imported module name to its likely PyPI distribution name."""
    if module_name in KNOWN_IMPORT_MAP:
        return KNOWN_IMPORT_MAP[module_name]
    return normalize_package_name(module_name)


def scan_project(root_dir: Path | str) -> ScanResult:
    """Recursively scan Python files under root_dir and audit against pyproject.toml."""
    root = Path(root_dir).resolve()
    stdlib = get_stdlib_modules()

    # Discover local project packages/modules to avoid false positives
    local_modules: set[str] = set()
    for item in root.iterdir():
        if item.name.startswith("."):
            continue
        if item.is_file() and item.suffix == ".py":
            local_modules.add(item.stem)
        elif item.is_dir() and (item / "__init__.py").exists():
            local_modules.add(item.name)

    # Check for src-layout
    src_dir = root / "src"
    if src_dir.is_dir():
        for item in src_dir.iterdir():
            if item.is_file() and item.suffix == ".py":
                local_modules.add(item.stem)
            elif item.is_dir() and (item / "__init__.py").exists():
                local_modules.add(item.name)

    all_imports: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _IGNORED_DIRS and not d.startswith(".")]
        for f in filenames:
            if f.endswith(".py"):
                file_p = Path(dirpath) / f
                all_imports.update(scan_file_imports(file_p))

    # Filter out stdlib and local modules
    third_party_modules = {
        m for m in all_imports if m not in stdlib and m not in local_modules and not m.startswith("_")
    }

    inferred_packages = {map_module_to_package(m) for m in third_party_modules}

    # Read declared dependencies from pyproject.toml if present
    declared: set[str] = set()
    pyproject_file = root / "pyproject.toml"
    if pyproject_file.exists():
        try:
            with open(pyproject_file, "rb") as f:
                data = tomllib.load(f)
            deps = data.get("project", {}).get("dependencies", [])
            for dep in deps:
                # Strip version specifiers like '>=1.0.0', '==2.0'
                name = dep.split(";")[0].split(">")[0].split("<")[0].split("=")[0].split("~")[0]
                name = name.strip()
                if name:
                    declared.add(normalize_package_name(name))
        except (OSError, tomllib.TOMLDecodeError):
            pass

    missing = inferred_packages - declared
    unused = declared - inferred_packages

    return ScanResult(
        all_imports=all_imports,
        inferred_packages=inferred_packages,
        declared_dependencies=declared,
        missing_dependencies=missing,
        unused_dependencies=unused,
    )
