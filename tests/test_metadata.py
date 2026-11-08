import io
import zipfile
from pathlib import Path

from evok.metadata import (
    extract_metadata_from_payload,
    parse_metadata_bytes,
    parse_zip_central_directory,
)


def test_parse_metadata_bytes() -> None:
    raw = """Metadata-Version: 2.1
Name: example-pkg
Version: 2.4.1
Summary: An example package
Requires-Python: >=3.10
Requires-Dist: requests>=2.28
Requires-Dist: pydantic<3.0
"""
    meta = parse_metadata_bytes(raw)
    assert meta.name == "example-pkg"
    assert meta.version == "2.4.1"
    assert meta.requires_python == ">=3.10"
    assert "requests>=2.28" in meta.requires_dist
    assert "pydantic<3.0" in meta.requires_dist
    assert meta.summary == "An example package"


def test_zip_central_directory_parsing_and_extraction(tmp_path: Path) -> None:
    # Build in-memory zip archive
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("pkg/__init__.py", "print('hello')\n")
        zf.writestr("pkg-1.0.0.dist-info/METADATA", "Name: pkg\nVersion: 1.0.0\n")

    full_bytes = buf.getvalue()
    total_size = len(full_bytes)

    # Simulate tail request buffer
    tail_size = min(total_size, 4096)
    tail_bytes = full_bytes[-tail_size:]

    entries = parse_zip_central_directory(tail_bytes, total_size)
    assert len(entries) == 2
    filenames = [e.filename for e in entries]
    assert "pkg/__init__.py" in filenames
    assert "pkg-1.0.0.dist-info/METADATA" in filenames

    # Find metadata entry and extract payload directly
    meta_entry = next(e for e in entries if e.filename.endswith("METADATA"))
    payload = full_bytes[
        meta_entry.local_header_offset : meta_entry.local_header_offset
        + 30
        + 100
        + meta_entry.compressed_size
    ]

    extracted = extract_metadata_from_payload(payload, meta_entry.compression_method)
    meta = parse_metadata_bytes(extracted)
    assert meta.name == "pkg"
    assert meta.version == "1.0.0"
