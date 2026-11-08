# Evok Architectural Comparison & Performance Analysis

This document details how Evok compares architecturally against `pip` and `uv`.

---

## Performance Comparison Table

| Metric / Dimension | `pip` (Python) | `uv` (Rust) | `evok` (Pure Python 3.12+) |
|---|---|---|---|
| **Warm-Cache Install** | Seconds (decompresses ZIPs, writes to disk) | Milliseconds (`clonefile` / hardlinks) | **~15ms** (`clonefile` / `os.link`) |
| **Remote Metadata Fetch** | Full wheel download if no PEP 658 | Range requests on ZIP central directory | **HTTP Range tail parser** (`struct.unpack`) |
| **Version Arithmetic** | Heavy heap-allocated objects | Stack-allocated `u64` integers | **Bit-packed 64-bit integer comparisons** |
| **In-Process Python API** | None (private, discouraged) | None (CLI static binary) | **First-class library API** (`evok.Resolver`, `evok.Environment`) |
| **Zero-Venv Virtualization** | No (requires disk `.venv`) | No (requires disk `.venv`) | **Yes** (`sys.meta_path` import hooks) |
| **AST Dependency Inference** | No | No (opaque text / pyproject only) | **Yes** (stdlib `ast` code scanner) |
| **Dead Dependency Pruning** | No | No | **Yes** (`ev prune`) |
| **Zero-Binary Bootstrapping** | Multi-MB package | 35 MB native binary | **< 100 KB `.pyz` zipapp** |
| **Subinterpreter Isolation** | No | No | **Yes** (in-memory multi-environment) |
