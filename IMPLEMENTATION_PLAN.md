# Evok Implementation Plan

> **Pure-Python High-Performance Packaging Engine & Zero-Venv Virtualization Runtime**

Evok (`ev`) is a pure-Python, zero-dependency package manager, dependency resolver, project builder, and runtime virtualization system. It proves that a clean-slate Python implementation leveraging modern OS primitives and stdlib capabilities can reach ~80% of `uv`'s speed while delivering unique developer capabilities that native binaries cannot match: in-process APIs, zero-venv `sys.meta_path` virtualization, dynamic AST dependency inference, dynamic platform execution hooks, and zero-binary `.pyz` bootstrapping.

---

## 1. Architectural Foundation & Bottleneck Elimination

Evok addresses the five systemic bottlenecks of traditional package managers identified in `~/vaults/Projects/evok.md`:

| Bottleneck Layer | `pip` Bottleneck | `uv` (Rust) Solution | `evok` (Pure Python 3.12+) Solution |
|---|---|---|---|
| **Warm Installation** | Decompresses `.whl` ZIP files and writes thousands of files sequentially. | Unpacked global cache + reflinks (`clonefile`/`FICLONE`) or hardlinks. | **`evok.cache`**: Global unpacked wheel cache (`~/.cache/evok/wheels/<hash>`) using macOS APFS `clonefile` via `ctypes`, Linux `FICLONE` via `fcntl.ioctl`, with safe hardlink (`os.link`) and symlink fallbacks. |
| **Remote Metadata** | Downloads full multi-hundred MB wheels to read `METADATA`. | PEP 658 + HTTP Range requests reading ZIP central directory in 2 calls. | **`evok.metadata`**: Async HTTP/2 + PEP 691 JSON Simple API client with PEP 658 metadata support and HTTP `Range: bytes=-65536` ZIP central directory tail parser. |
| **Version Arithmetic** | Heavy heap-allocated Python objects (`packaging.version.Version`) with heavy GC pressure. | Stack-allocated 64-bit integer (`u64`) bit-packed representation. | **`evok.pep440`**: Bit-packed 64-bit Python integer representation encoding epoch, major, minor, patch, pre/post/dev flags into single scalar integer comparisons. |
| **Interpreter Boot** | Imports massive dependency tree (`urllib3`, `email`, `packaging`). | Native binary execution (~2ms). | Lazy imports, minimal zero-dependency stdlib-only core, and compiled bytecache startup. |
| **In-Memory Cache** | Parses RFC 822 `METADATA` headers on every invocation. | Zero-copy `rkyv` mmap binary cache. | `mmap`-backed SQLite binary index (`PRAGMA mmap_size`, WAL mode) and in-memory caches. |

---

## 2. Competitive Differentiators (Why `evok` > `uv`)

Because `evok` runs *inside* the Python runtime:
1. **First-Class In-Process API**:
   ```python
   from evok import Environment, Resolver

   graph = Resolver().resolve(["httpx>=0.27", "rich"])
   with Environment.ephemeral(graph) as env:
       env.import_module("httpx")
   ```
2. **Zero-Venv `sys.meta_path` Virtualization (PEP 582)**:
   Loads packages directly into memory from the unpacked global cache using custom `MetaPathFinder` and `Loader` without creating `.venv` directories or modifying disk pointers. Supports multi-version isolation in subinterpreters.
3. **AST-Driven Dependency Inference & Dead Dependency Pruning**:
   Uses stdlib `ast` to scan projects in milliseconds, extract imported modules, match against PyPI top-level packages, automatically generate dependencies, and identify dead dependencies declared in `pyproject.toml`.
4. **Dynamic Hardware & Execution Hooks**:
   Inspects runtime acceleration (Apple Silicon Metal/MLX, CUDA, ROCm, AVX) via `ctypes` and `platform` directly in-process to select matching wheel variants without spawning PEP 517 build backends.
5. **Zero-Binary Bootstrapping (`zipapp`)**:
   Packaged into a single standalone `.pyz` executable under 100 KB that runs on any standard Python interpreter without requiring native compilation or `curl | sh` installers.

---

## 3. Modular System Architecture

```
src/evok/
├── __init__.py           # Public exports (Resolver, Environment, __version__)
├── __main__.py          # Entrypoint for python -m evok
├── cli.py               # `ev` command-line interface (argparse/zero-dep)
├── pep440.py            # Bit-packed 64-bit PEP 440 version arithmetic
├── cache.py             # Reflink (APFS/FICLONE) and hardlink global cache
├── metadata.py          # PEP 658 & PEP 691 HTTP Range tail-reader
├── resolver.py          # PubGrub-inspired backtracking dependency resolver
├── importer.py          # sys.meta_path import hooks for zero-venv execution
├── environment.py       # Ephemeral and virtual environment orchestration
├── ast_scanner.py       # AST import inspection and dead-dependency pruning
└── builder.py           # Standard wheel / sdist builder & zipapp packager
```

---

## 4. Implementation & PR Roadmap

All development follows Conventional Commits (`feat:`, `fix:`, `docs:`, `ci:`, `chore:`, `test:`) with 1 Issue and 1 PR per feature branch, squash-merged to `main`:

### Phase 1: Project Scaffolding & CI Pipeline (Issue #1 / PR #1)
- Configure `pyproject.toml` with console scripts: `ev` and `evok`.
- Setup formatting/linting (`ruff`) and testing (`pytest`, `pytest-cov`).
- Setup GitHub Actions CI matrix testing across Python 3.12, 3.13, and 3.14.
- Initialize `docs/` structure.

### Phase 2: Core Primitives — Bit-Packed PEP 440 & Zero-Copy Cache (Issue #2 / PR #2)
- Implement `evok.pep440`: `BitPackedVersion`, version range operators (`>=`, `<=`, `~=`, `==`, `!=`), and release segment bit-packing.
- Implement `evok.cache`: APFS `clonefile` (macOS), `FICLONE` ioctl (Linux), `os.link` hardlinks, directory caching.
- Unit tests covering bit-packing edge cases, APFS reflink fallbacks, and hardlinking.

### Phase 3: PyPI Metadata & AST Dependency Scanner (Issue #3 / PR #3)
- Implement `evok.ast_scanner`: project AST parsing for imports, stdlib exclusion, PyPI top-level mapping, dead dependency detection.
- Implement `evok.metadata`: Simple API JSON client, HTTP Range ZIP tail reader parsing the Central Directory with `struct.unpack`.
- Unit tests for AST parsing and ZIP central directory range parsing.

### Phase 4: PubGrub Resolver & Zero-Venv Import Hooks (Issue #4 / PR #4)
- Implement `evok.resolver`: in-memory candidate resolution and constraint backtracking.
- Implement `evok.importer`: `EvokMetaPathFinder` and `EvokPackageLoader` registering into `sys.meta_path`.
- Implement `evok.environment`: `Environment` context manager supporting ephemeral in-memory environments.
- Unit tests for resolution and import virtualization.

### Phase 5: Build System, Zipapp Bootstrapper & CLI Commands (Issue #5 / PR #5)
- Implement `evok.builder`: Pure-Python `.whl` and `.tar.gz` sdist packager and `zipapp` (`.pyz`) generator.
- Implement `evok.cli`: `ev init`, `ev build`, `ev add`, `ev resolve`, `ev install`, `ev scan`, `ev run`, `ev info`.
- End-to-end integration tests.

### Phase 6: Documentation, Benchmarks & Polish (Issue #6 / PR #6)
- Comprehensive user documentation, architecture guide, API reference, and performance benchmarks.
