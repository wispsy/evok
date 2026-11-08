# Evok (`ev`)

[![CI](https://github.com/wispsy/evok/actions/workflows/ci.yml/badge.svg)](https://github.com/wispsy/evok/actions/workflows/ci.yml)
[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> **Pure-Python high-performance package manager and zero-venv virtualization runtime.**

Evok demonstrates that a clean-slate Python implementation leveraging modern OS primitives and stdlib capabilities can reach ~80% of `uv`'s speed while delivering native capabilities that compiled binaries cannot provide: first-class in-process APIs, zero-venv `sys.meta_path` virtualization, dynamic AST dependency inference, and single-file zero-binary `.pyz` bootstrapping.

---

## Key Highlights

- **Zero-Copy Reflink Cache**: Unpacks wheels once into a global cache and installs in milliseconds using macOS APFS `clonefile`, Linux `FICLONE`, and hardlink (`os.link`) fallbacks.
- **Bit-Packed PEP 440 Arithmetic**: Encodes release segments and lifecycle stages into single 64-bit scalar integers for microsecond comparisons.
- **Async Metadata & Range Tail-Reads**: Fetches package metadata from remote ZIP central directories using HTTP Range requests without downloading full wheels.
- **Zero-Venv Virtualization**: Run code with in-process `sys.meta_path` hooks that load dependencies directly from the cache without creating a `.venv` directory on disk.
- **AST Dependency Scanner**: Scans project source code to automatically detect third-party imports, flag missing packages, and prune unused/dead dependencies.
- **Pure-Python Wheel & Sdist Builder**: Standards-compliant PEP 427 wheel generator, PEP 625 sdist packager, and single-file `.pyz` executable bundler.

---

## Quickstart

### Installation

Evok runs on Python 3.12+ with zero external runtime dependencies:

```bash
# Using uv
uv pip install evok

# Or via pip
pip install evok
```

### Command-Line Usage (`ev`)

```bash
# Initialize a new project
ev init my-app

# Inspect AST imports and compare with pyproject.toml
ev scan

# Automatically prune unused dependencies
ev prune

# Build standard wheel, sdist, and standalone zipapp
ev build --zipapp

# Run a script with in-process zero-venv dependency virtualization
ev run script.py

# Check platform reflink support and runtime info
ev info
```

---

## Programmatic Python API

Evok is built as a first-class Python library:

```python
from evok import Environment, InMemoryProvider, Resolver

# 1. Dependency Resolution
provider = InMemoryProvider(
    {
        "httpx": {"0.27.0": ["httpcore>=1.0.0"]},
        "httpcore": {"1.0.5": []},
    }
)
resolver = Resolver(provider=provider)
graph = resolver.resolve(["httpx>=0.24.0"])
print(graph.get("httpx").version)  # 0.27.0

# 2. Ephemeral Zero-Venv Execution
with Environment.ephemeral(graph) as env:
    mod = env.import_module("httpx")
```

---

## Documentation

- [System Architecture](docs/architecture.md)
- [CLI Reference](docs/cli.md)
- [Python API Reference](docs/api.md)
- [Performance & Bottleneck Analysis](docs/benchmarks.md)
- [Implementation Plan](IMPLEMENTATION_PLAN.md)

---

## License

MIT License.
