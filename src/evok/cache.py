"""Unpacked wheel cache with zero-copy filesystem reflinks and hardlinks.

Supports:
- macOS APFS clonefile via ctypes
- Linux FICLONE ioctl
- os.link hardlinks
- Fast fallback to symlink/shutil.copy
"""

from __future__ import annotations

import ctypes
import fcntl
import os
import shutil
import sys
import zipfile
from pathlib import Path

# macOS APFS clonefile setup
_clonefile = None
if sys.platform == "darwin":
    try:
        _libc = ctypes.cdll.LoadLibrary(None)
        if hasattr(_libc, "clonefile"):
            _clonefile = _libc.clonefile
            _clonefile.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
            _clonefile.restype = ctypes.c_int
    except (OSError, AttributeError):
        _clonefile = None

# Linux FICLONE ioctl constant
FICLONE = 0x40049409


def default_cache_dir() -> Path:
    """Return default evok cache directory."""
    custom = os.environ.get("EVOK_CACHE_DIR")
    if custom:
        return Path(custom).expanduser().resolve()
    return Path.home() / ".cache" / "evok"


def reflink_file(src: Path | str, dst: Path | str) -> str:
    """Perform zero-copy file clone (reflink) or hardlink from src to dst.

    Returns the strategy used: 'clonefile', 'ficlone', 'hardlink', or 'copy'.
    """
    src_p = Path(src).resolve()
    dst_p = Path(dst).resolve()
    dst_p.parent.mkdir(parents=True, exist_ok=True)

    if dst_p.exists():
        dst_p.unlink()

    src_bytes = str(src_p).encode("utf-8")
    dst_bytes = str(dst_p).encode("utf-8")

    # 1. macOS APFS clonefile
    if _clonefile is not None:
        ret = _clonefile(src_bytes, dst_bytes, 0)
        if ret == 0:
            return "clonefile"

    # 2. Linux FICLONE ioctl
    if sys.platform.startswith("linux"):
        try:
            with open(src_p, "rb") as f_in, open(dst_p, "wb") as f_out:
                fcntl.ioctl(f_out.fileno(), FICLONE, f_in.fileno())
            return "ficlone"
        except OSError:
            if dst_p.exists():
                dst_p.unlink()

    # 3. os.link (Hardlink)
    try:
        os.link(src_p, dst_p)
        return "hardlink"
    except OSError:
        pass

    # 4. Fallback copy
    shutil.copy2(src_p, dst_p)
    return "copy"


def materialize_tree(
    src_dir: Path | str, dst_dir: Path | str, strategy: str = "auto"
) -> dict[str, int]:
    """Materialize files from src_dir into dst_dir using zero-copy links.

    Returns a count of files linked by strategy.
    """
    src_root = Path(src_dir).resolve()
    dst_root = Path(dst_dir).resolve()
    counts: dict[str, int] = {}

    for dirpath, _, filenames in os.walk(src_root):
        rel_path = Path(dirpath).relative_to(src_root)
        target_dir = dst_root / rel_path
        target_dir.mkdir(parents=True, exist_ok=True)

        for filename in filenames:
            src_file = Path(dirpath) / filename
            dst_file = target_dir / filename
            if strategy == "hardlink":
                try:
                    if dst_file.exists():
                        dst_file.unlink()
                    os.link(src_file, dst_file)
                    st = "hardlink"
                except OSError:
                    shutil.copy2(src_file, dst_file)
                    st = "copy"
            elif strategy == "copy":
                shutil.copy2(src_file, dst_file)
                st = "copy"
            else:
                st = reflink_file(src_file, dst_file)
            counts[st] = counts.get(st, 0) + 1

    return counts


class WheelCache:
    """Global unpacked wheel cache."""

    def __init__(self, cache_dir: Path | str | None = None) -> None:
        self.root = Path(cache_dir).expanduser().resolve() if cache_dir else default_cache_dir()
        self.wheels_dir = self.root / "wheels"
        self.wheels_dir.mkdir(parents=True, exist_ok=True)

    def get_wheel_dir(self, name: str, version: str) -> Path:
        """Return the directory path for an unpacked wheel."""
        safe_name = name.lower().replace("-", "_")
        return self.wheels_dir / safe_name / version

    def is_cached(self, name: str, version: str) -> bool:
        """Check if an unpacked wheel already exists."""
        w_dir = self.get_wheel_dir(name, version)
        return w_dir.is_dir() and (w_dir / ".evok_complete").exists()

    def unpack_wheel(self, wheel_path: Path | str) -> Path:
        """Unpack a .whl file into the global cache."""
        wheel_p = Path(wheel_path).resolve()
        filename = wheel_p.name
        # Wheel filename format: {distribution}-{version}(-{build_tag})?-{python_tag}-{abi_tag}-{platform_tag}.whl
        parts = filename[:-4].split("-")
        if len(parts) < 2:
            raise ValueError(f"Invalid wheel filename format: {filename}")

        name, version = parts[0], parts[1]
        target_dir = self.get_wheel_dir(name, version)
        if self.is_cached(name, version):
            return target_dir

        target_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(wheel_p, "r") as zf:
            zf.extractall(target_dir)

        # Mark complete
        (target_dir / ".evok_complete").write_text("ok\n", encoding="utf-8")
        return target_dir

    def install_to(
        self, name: str, version: str, target_dir: Path | str, strategy: str = "auto"
    ) -> dict[str, int]:
        """Materialize an unpacked wheel into target_dir (e.g. site-packages)."""
        src = self.get_wheel_dir(name, version)
        if not src.is_dir():
            raise FileNotFoundError(f"Wheel {name}=={version} not found in cache")
        return materialize_tree(src, target_dir, strategy=strategy)
