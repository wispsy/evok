"""Command-line interface for evok (ev / evok).

Designed for low startup latency (~15ms) using lazy imports and stdlib argparse.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize a new clean Python project."""
    target_dir = Path(args.path or ".").resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    name = args.name or target_dir.name

    pyproject = target_dir / "pyproject.toml"
    if pyproject.exists() and not args.force:
        print(f"Error: {pyproject} already exists. Use --force to overwrite.", file=sys.stderr)
        return 1

    pyproject.write_text(
        f"""[project]
name = "{name}"
version = "0.1.0"
description = "A new Python project created with evok"
readme = "README.md"
requires-python = ">=3.12"
dependencies = []

[build-system]
requires = ["evok>=0.1.0"]
build-backend = "evok.builder"
""",
        encoding="utf-8",
    )

    readme = target_dir / "README.md"
    if not readme.exists():
        readme.write_text(f"# {name}\n\nCreated with evok.\n", encoding="utf-8")

    pkg_dir = target_dir / "src" / name.replace("-", "_")
    pkg_dir.mkdir(parents=True, exist_ok=True)
    init_file = pkg_dir / "__init__.py"
    if not init_file.exists():
        init_file.write_text(
            f'"""{name} package."""\n\n__version__ = "0.1.0"\n',
            encoding="utf-8",
        )

    tests_dir = target_dir / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    test_file = tests_dir / "test_basic.py"
    if not test_file.exists():
        test_file.write_text(
            f"import {name.replace('-', '_')}\n\ndef test_version():\n    assert {name.replace('-', '_')}.__version__ == '0.1.0'\n",
            encoding="utf-8",
        )

    print(f"Initialized clean evok project '{name}' at {target_dir}")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    """Build wheel, sdist, and optional zipapp."""
    from evok.builder import build_sdist, build_wheel, build_zipapp

    project_dir = Path(args.path or ".").resolve()
    dist_dir = Path(args.dist or (project_dir / "dist")).resolve()

    wheel_path = build_wheel(project_dir, dist_dir)
    print(f"Built wheel: {wheel_path.name} -> {wheel_path}")

    sdist_path = build_sdist(project_dir, dist_dir)
    print(f"Built sdist: {sdist_path.name} -> {sdist_path}")

    if args.zipapp:
        src_dir = project_dir / "src" if (project_dir / "src").is_dir() else project_dir
        zipapp_path = dist_dir / f"{project_dir.name}.pyz"
        build_zipapp(src_dir, zipapp_path)
        print(f"Built standalone zipapp: {zipapp_path.name} -> {zipapp_path}")

    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    """Run AST dependency audit."""
    from evok.ast_scanner import scan_project

    project_dir = Path(args.path or ".").resolve()
    res = scan_project(project_dir)

    print(f"AST Scan Results for: {project_dir}")
    print(f"  Total Imported Modules: {len(res.all_imports)}")
    print(f"  Inferred PyPI Packages: {sorted(res.inferred_packages) or 'None'}")
    print(f"  Declared Dependencies:  {sorted(res.declared_dependencies) or 'None'}")

    if res.missing_dependencies:
        print("\n  [!] Missing Dependencies (imported but not declared):")
        for pkg in sorted(res.missing_dependencies):
            print(f"      + {pkg}")

    if res.unused_dependencies:
        print("\n  [-] Unused / Dead Dependencies (declared but not imported):")
        for pkg in sorted(res.unused_dependencies):
            print(f"      - {pkg}")

    if not res.missing_dependencies and not res.unused_dependencies:
        print("\n  Dependencies are in sync with codebase imports.")

    return 0


def cmd_prune(args: argparse.Namespace) -> int:
    """Prune dead/unused dependencies from pyproject.toml."""
    from evok.ast_scanner import scan_project

    project_dir = Path(args.path or ".").resolve()
    res = scan_project(project_dir)

    if not res.unused_dependencies:
        print("No dead dependencies found.")
        return 0

    pyproject_file = project_dir / "pyproject.toml"
    lines = pyproject_file.read_text(encoding="utf-8").splitlines()
    new_lines: list[str] = []

    for line in lines:
        is_unused = False
        for unused in res.unused_dependencies:
            if f'"{unused}' in line or f"'{unused}" in line:
                is_unused = True
                break
        if not is_unused:
            new_lines.append(line)

    pyproject_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    print(f"Pruned dead dependencies: {sorted(res.unused_dependencies)}")
    return 0


def cmd_resolve(args: argparse.Namespace) -> int:
    """Resolve dependency constraints in-memory."""
    from evok.resolver import InMemoryProvider, Requirement, Resolver

    provider = InMemoryProvider()
    for req_str in args.requirements:
        req = Requirement.parse(req_str)
        # Choose a sensible default candidate version matching target or latest
        target_v = "1.0.0"
        if req.specifier.clauses:
            for clause in req.specifier.clauses:
                if hasattr(clause, "target"):
                    target_v = str(clause.target)
        provider.add_package(req.name, target_v)

    resolver = Resolver(provider=provider)
    graph = resolver.resolve(args.requirements)

    print("Resolved Graph:")
    for name, cand in sorted(graph.packages.items()):
        print(f"  {name} == {cand.version}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Execute a script with zero-venv in-process virtualization."""
    import runpy

    from evok.environment import Environment

    script_path = Path(args.script).resolve()
    if not script_path.is_file():
        print(f"Error: Script not found: {script_path}", file=sys.stderr)
        return 1

    with Environment.ephemeral():
        sys.argv = [str(script_path), *args.args]
        runpy.run_path(str(script_path), run_name="__main__")
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    """Display runtime environment and filesystem capabilities."""
    import platform

    from evok.cache import default_cache_dir, reflink_file

    print("evok version:     0.1.0")
    print(f"Python runtime:   {platform.python_implementation()} {sys.version.split()[0]}")
    print(f"Platform:         {sys.platform} ({platform.machine()})")
    cache_dir = default_cache_dir()
    print(f"Cache Directory:  {cache_dir}")

    # Test reflink support
    test_src = cache_dir / ".reflink_test_src"
    test_dst = cache_dir / ".reflink_test_dst"
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        test_src.write_text("test", encoding="utf-8")
        st = reflink_file(test_src, test_dst)
        print(f"Reflink Strategy: {st}")
    except (OSError, RuntimeError) as e:
        print(f"Reflink Strategy: copy ({e})")
    finally:
        if test_src.exists():
            test_src.unlink()
        if test_dst.exists():
            test_dst.unlink()

    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point for ev and evok CLI."""
    parser = argparse.ArgumentParser(
        prog="ev",
        description="evok: Pure-Python high-performance package manager and virtualization runtime",
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to execute")

    # init
    p_init = subparsers.add_parser("init", help="Initialize a new project")
    p_init.add_argument("path", nargs="?", default=".", help="Project directory")
    p_init.add_argument("--name", help="Project name")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing project files")

    # build
    p_build = subparsers.add_parser("build", help="Build wheel and sdist")
    p_build.add_argument("path", nargs="?", default=".", help="Project directory")
    p_build.add_argument("--dist", help="Output directory")
    p_build.add_argument("--zipapp", action="store_true", help="Also generate executable .pyz zipapp")

    # scan
    p_scan = subparsers.add_parser("scan", help="Audit AST imports vs declared dependencies")
    p_scan.add_argument("path", nargs="?", default=".", help="Project directory")

    # prune
    p_prune = subparsers.add_parser("prune", help="Prune unused dependencies from pyproject.toml")
    p_prune.add_argument("path", nargs="?", default=".", help="Project directory")

    # resolve
    p_resolve = subparsers.add_parser("resolve", help="Resolve dependency requirements in memory")
    p_resolve.add_argument("requirements", nargs="+", help="Package requirements")

    # run
    p_run = subparsers.add_parser("run", help="Run a script with zero-venv virtualization")
    p_run.add_argument("script", help="Python script to run")
    p_run.add_argument("args", nargs="*", help="Arguments passed to script")

    # info
    subparsers.add_parser("info", help="Display runtime environment and filesystem capabilities")

    parsed = parser.parse_args(argv)
    if not parsed.command:
        parser.print_help()
        return 0

    commands = {
        "init": cmd_init,
        "build": cmd_build,
        "scan": cmd_scan,
        "prune": cmd_prune,
        "resolve": cmd_resolve,
        "run": cmd_run,
        "info": cmd_info,
    }

    cmd_fn = commands.get(parsed.command)
    if cmd_fn:
        return cmd_fn(parsed)
    return 1


if __name__ == "__main__":
    sys.exit(main())
