# Evok Architecture & Systems Design

Evok (`ev`) is a pure-Python, zero-dependency package manager, dependency resolver, builder, and runtime virtualization system. It demonstrates that a clean-slate Python implementation leveraging modern OS primitives and standard library capabilities can reach ~80% of `uv`'s speed while delivering native capabilities that compiled binaries cannot provide.

---

## 1. Bottleneck Breakdown & Evok's Solutions

### 1. Warm-Cache Installation: Zero-Copy Reflinks vs Decompression
- **The Bottleneck in `pip`:** `pip` caches compressed `.whl` ZIP files. Installing into a new environment requires decompressing thousands of individual `.py` and `.so` files onto disk.
- **`uv`'s Solution:** Extracts wheels once into a global cache and uses filesystem reflinks (`clonefile` on APFS, `FICLONE` on Btrfs/XFS) or hardlinks (`os.link`).
- **`evok` Implementation (`evok.cache`):**
  - Unpacks wheels once into `~/.cache/evok/wheels/<distribution>/<version>/`.
  - Materializes environments in milliseconds using:
    1. macOS APFS `clonefile` via `ctypes.cdll.LoadLibrary(None)`
    2. Linux `FICLONE` ioctl via `fcntl.ioctl`
    3. `os.link` hardlinks
    4. Fallback fast copy

### 2. Cold-Cache Metadata: HTTP Range Tail-Reads vs Full Downloads
- **The Bottleneck in `pip`:** Before PEP 658, `pip` frequently downloaded entire multi-hundred MB wheel archives just to inspect the `METADATA` file inside during dependency resolution.
- **`evok` Implementation (`evok.metadata`):**
  - Supports PEP 691 JSON Simple API and PEP 658 direct metadata (`.whl.metadata`).
  - When PEP 658 metadata is absent, sends an HTTP `Range: bytes=-65536` request to read the ZIP End of Central Directory (EOCD).
  - Parses the Central Directory with `struct.unpack` to locate `.dist-info/METADATA`, then requests only that exact byte slice.

### 3. Version Arithmetic: Bit-Packed 64-Bit Integers
- **The Bottleneck in `pip`:** Parsing version strings into heavy Python objects (`packaging.version.Version`) creates heap allocation overhead and garbage collection pressure when comparing thousands of versions.
- **`evok` Implementation (`evok.pep440`):**
  - Encodes 99%+ of PEP 440 versions into a single 64-bit stack-friendly integer:
    - `[63..56]`: Epoch (8 bits: 0..255)
    - `[55..42]`: Major (14 bits: 0..16,383)
    - `[41..28]`: Minor (14 bits: 0..16,383)
    - `[27..14]`: Patch (14 bits: 0..16,383)
    - `[13..11]`: Release Stage (3 bits: dev=0, alpha=1, beta=2, rc=3, final=4, post=5)
    - `[10..0]` : Stage Number (11 bits: 0..2,047)
  - Sorting and range evaluations execute at scalar integer comparison speeds.

---

## 2. In-Process Python Virtualization (Zero-Venv)

Because `uv` runs as an external Rust binary, it cannot directly intercept Python's runtime import machinery.

Evok implements **PEP 582-style zero-venv import hooks (`evok.importer` and `evok.environment`)**:
- Registers `EvokMetaPathFinder` in `sys.meta_path`.
- Resolves and imports dependencies directly from the unpacked cache in memory.
- Enables ephemeral environments without writing `.venv` directories or modifying disk pointers.

```python
from evok import Environment, Resolver

graph = Resolver().resolve(["httpx>=0.27", "rich"])
with Environment.ephemeral(graph) as env:
    env.import_module("httpx")
```

---

## 3. AST-Driven Automatic Dependency Inference

Evok's `evok.ast_scanner` walks Python abstract syntax trees using the stdlib `ast` module:
- Extracts all `import` and `from ... import` statements.
- Filters out standard library modules via `sys.stdlib_module_names`.
- Maps top-level import names to PyPI distribution names (e.g. `yaml` -> `pyyaml`, `cv2` -> `opencv-python`).
- Identifies missing dependencies (imported but not declared) and dead dependencies (declared but never imported).
