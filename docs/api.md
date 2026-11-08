# Evok Python API Reference

Evok exposes a first-class, importable Python library API for programmatic dependency resolution, cache management, and in-process ephemeral environment orchestration.

---

## 1. `Resolver` & `ResolutionGraph`

```python
from evok import InMemoryProvider, Requirement, Resolver

# Create a resolver with an in-memory or custom provider
provider = InMemoryProvider(
    {
        "httpx": {"0.27.0": ["httpcore>=1.0.0"]},
        "httpcore": {"1.0.5": []},
    }
)

resolver = Resolver(provider=provider)
graph = resolver.resolve(["httpx>=0.24.0"])

print(graph.get("httpx").version)  # 0.27.0
print(graph.to_lock_dict())
```

---

## 2. `Environment.ephemeral()` (Zero-Venv Virtualization)

Load packages directly into `sys.meta_path` from cached directories without touching the disk:

```python
from evok import Environment

# Run within an ephemeral environment
with Environment.ephemeral(search_paths=["/path/to/custom_pkg"]) as env:
    mod = env.import_module("my_package")
    mod.do_work()

# On exit, sys.meta_path and newly imported modules are cleanly restored
```

---

## 3. `BitPackedVersion` & `SpecifierSet`

Microsecond-speed PEP 440 version arithmetic:

```python
from evok.pep440 import BitPackedVersion, SpecifierSet

v1 = BitPackedVersion("1.0.0a1")
v2 = BitPackedVersion("1.0.0")

print(v1 < v2)  # True
print(hex(v1.packed))  # 64-bit integer representation

spec = SpecifierSet(">=1.0.0,<2.0.0,!=1.5.0")
print(spec.contains("1.4.2"))  # True
print(spec.contains("1.5.0"))  # False
```

---

## 4. `WheelCache` & `materialize_tree`

Zero-copy cache management and file reflink materialization:

```python
from evok.cache import WheelCache, reflink_file

cache = WheelCache()
# Unpack wheel into global cache
wheel_dir = cache.unpack_wheel("pkg-1.0.0-py3-none-any.whl")

# Materialize wheel to target directory via macOS clonefile or Linux FICLONE
stats = cache.install_to("pkg", "1.0.0", target_dir="./site-packages")
print(stats)  # {'clonefile': 12}
```

---

## 5. `ast_scanner.scan_project()`

Inspect codebases for import statements and audit dependencies:

```python
from evok.ast_scanner import scan_project

result = scan_project(".")
print("Inferred Packages:", result.inferred_packages)
print("Missing Dependencies:", result.missing_dependencies)
print("Unused Dependencies:", result.unused_dependencies)
```
