"""Pure-Python standard wheel/sdist builder and standalone zipapp bundler.

Implements:
- PEP 427 standard wheel packaging
- PEP 625 / PEP 517 standard source distribution (sdist .tar.gz)
- Single-file zero-binary zipapp (.pyz) executable creation
"""

from __future__ import annotations

import base64
import hashlib
import os
import tarfile
import tomllib
import zipapp
import zipfile
from pathlib import Path


def _sha256_b64(data: bytes) -> str:
    """Return URL-safe base64 SHA256 digest without trailing '=' for RECORD."""
    digest = hashlib.sha256(data).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def load_project_metadata(project_dir: Path | str) -> dict[str, str | list[str]]:
    """Parse pyproject.toml and return normalized project metadata."""
    p_dir = Path(project_dir).resolve()
    pyproject_file = p_dir / "pyproject.toml"
    if not pyproject_file.exists():
        raise FileNotFoundError(f"pyproject.toml not found in {project_dir}")

    with open(pyproject_file, "rb") as f:
        data = tomllib.load(f)

    project = data.get("project", {})
    name = project.get("name")
    if not name:
        raise ValueError("Missing 'project.name' in pyproject.toml")
    version = project.get("version", "0.1.0")
    description = project.get("description", "")
    requires_python = project.get("requires-python", ">=3.12")
    dependencies = project.get("dependencies", [])

    return {
        "name": name,
        "version": str(version),
        "description": description,
        "requires_python": requires_python,
        "dependencies": dependencies,
    }


def build_wheel(project_dir: Path | str, dist_dir: Path | str | None = None) -> Path:
    """Build a PEP 427 pure-Python wheel (.whl) from project_dir."""
    p_dir = Path(project_dir).resolve()
    meta = load_project_metadata(p_dir)

    name = str(meta["name"])
    norm_name = name.lower().replace("-", "_")
    version = str(meta["version"])
    dist_path = Path(dist_dir).resolve() if dist_dir else p_dir / "dist"
    dist_path.mkdir(parents=True, exist_ok=True)

    wheel_filename = f"{norm_name}-{version}-py3-none-any.whl"
    wheel_path = dist_path / wheel_filename

    # Locate package files (src layout or flat)
    source_root = p_dir / "src" if (p_dir / "src").is_dir() else p_dir
    dist_info = f"{norm_name}-{version}.dist-info"

    # Build METADATA content
    metadata_lines = [
        "Metadata-Version: 2.1",
        f"Name: {name}",
        f"Version: {version}",
        f"Summary: {meta['description']}",
        f"Requires-Python: {meta['requires_python']}",
    ]
    for dep in meta["dependencies"]:  # type: ignore[union-attr]
        metadata_lines.append(f"Requires-Dist: {dep}")
    metadata_bytes = ("\n".join(metadata_lines) + "\n").encode("utf-8")

    wheel_bytes = (
        b"Wheel-Version: 1.0\nGenerator: evok (0.1.0)\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
    )

    record_rows: list[str] = []

    with zipfile.ZipFile(wheel_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 1. Package source files
        for root, _, files in os.walk(source_root):
            for file in files:
                if file.endswith(".py"):
                    full_file = Path(root) / file
                    rel_arc = full_file.relative_to(source_root)
                    data = full_file.read_bytes()
                    zf.writestr(str(rel_arc), data)
                    record_rows.append(f"{rel_arc},sha256={_sha256_b64(data)},{len(data)}")

        # 2. Add dist-info/METADATA
        meta_arc = f"{dist_info}/METADATA"
        zf.writestr(meta_arc, metadata_bytes)
        record_rows.append(f"{meta_arc},sha256={_sha256_b64(metadata_bytes)},{len(metadata_bytes)}")

        # 3. Add dist-info/WHEEL
        wheel_arc = f"{dist_info}/WHEEL"
        zf.writestr(wheel_arc, wheel_bytes)
        record_rows.append(f"{wheel_arc},sha256={_sha256_b64(wheel_bytes)},{len(wheel_bytes)}")

        # 4. Add dist-info/RECORD
        record_arc = f"{dist_info}/RECORD"
        record_rows.append(f"{record_arc},,")
        record_bytes = ("\n".join(record_rows) + "\n").encode("utf-8")
        zf.writestr(record_arc, record_bytes)

    return wheel_path


def build_sdist(project_dir: Path | str, dist_dir: Path | str | None = None) -> Path:
    """Build a PEP 625 / PEP 517 standard source distribution (.tar.gz)."""
    p_dir = Path(project_dir).resolve()
    meta = load_project_metadata(p_dir)

    name = str(meta["name"])
    norm_name = name.lower().replace("-", "_")
    version = str(meta["version"])
    dist_path = Path(dist_dir).resolve() if dist_dir else p_dir / "dist"
    dist_path.mkdir(parents=True, exist_ok=True)

    sdist_filename = f"{norm_name}-{version}.tar.gz"
    sdist_path = dist_path / sdist_filename

    prefix = f"{norm_name}-{version}"

    with tarfile.open(sdist_path, "w:gz") as tar:
        # Add pyproject.toml
        pyproject_file = p_dir / "pyproject.toml"
        tar.add(pyproject_file, arcname=f"{prefix}/pyproject.toml")

        # Add README.md if present
        readme = p_dir / "README.md"
        if readme.exists():
            tar.add(readme, arcname=f"{prefix}/README.md")

        # Add src/ or python files
        src_dir = p_dir / "src"
        if src_dir.is_dir():
            tar.add(src_dir, arcname=f"{prefix}/src")

    return sdist_path


def build_zipapp(
    source_dir: Path | str,
    output_path: Path | str,
    main_entrypoint: str = "evok.cli:main",
) -> Path:
    """Package a Python package source tree into an executable standalone .pyz zipapp."""
    src = Path(source_dir).resolve()
    out = Path(output_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    has_main = (src / "__main__.py").is_file()
    entry = None if has_main else main_entrypoint

    zipapp.create_archive(
        src,
        target=out,
        interpreter="/usr/bin/env python3",
        main=entry,
        compressed=True,
    )
    # Ensure executable permission
    out.chmod(0o755)
    return out
