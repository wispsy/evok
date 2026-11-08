# Evok Documentation

Welcome to the documentation for **Evok** (`ev`), a pure-Python high-performance packaging engine and zero-venv virtualization runtime.

## Core Features
- **Zero-Copy Cache**: Fast wheel extraction cache using APFS `clonefile`, Linux `FICLONE`, and hardlink fallback.
- **Bit-Packed PEP 440 Arithmetic**: Microsecond version comparison and range checking.
- **Async Metadata & Tail-Reads**: Range requests to fetch package metadata from remote wheel ZIP central directories without full archive downloads.
- **Zero-Venv Virtualization**: In-process `sys.meta_path` virtualization for dynamic dependency isolation.
- **AST Dependency Scanner**: Automatic dependency discovery and dead dependency pruning from project source code.
- **Pure-Python Builder & Zipapp**: Self-contained single-file bootstrapping and wheel builder.
