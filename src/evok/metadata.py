"""PyPI metadata fetcher and HTTP Range tail-reader for remote wheel ZIP central directories.

Implements PEP 658 direct metadata download, PEP 691 JSON Simple API queries,
and zero-download HTTP Range requests reading the ZIP Central Directory.
"""

from __future__ import annotations

import email.parser
import json
import re
import struct
import urllib.error
import urllib.request
import zlib
from dataclasses import dataclass, field
from typing import Any

EOCD_SIGNATURE = b"PK\x05\x06"
CENTRAL_DIR_SIGNATURE = b"PK\x01\x02"
LOCAL_HEADER_SIGNATURE = b"PK\x03\x04"


@dataclass
class ZipEntry:
    """Entry in a ZIP archive central directory."""

    filename: str
    compression_method: int
    compressed_size: int
    uncompressed_size: int
    local_header_offset: int


@dataclass
class PackageMetadata:
    """Parsed package METADATA fields."""

    name: str
    version: str
    requires_python: str | None = None
    requires_dist: list[str] = field(default_factory=list)
    summary: str = ""
    raw_headers: dict[str, Any] = field(default_factory=dict)


def parse_metadata_bytes(content: bytes | str) -> PackageMetadata:
    """Parse RFC 822 format METADATA from a wheel."""
    text = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else content
    parser = email.parser.Parser()
    msg = parser.parsestr(text)

    name = msg.get("Name", "")
    version = msg.get("Version", "")
    requires_python = msg.get("Requires-Python")
    summary = msg.get("Summary", "")

    # Requires-Dist can occur multiple times
    requires_dist = msg.get_all("Requires-Dist", [])

    return PackageMetadata(
        name=name,
        version=version,
        requires_python=requires_python,
        requires_dist=requires_dist,
        summary=summary,
        raw_headers=dict(msg.items()),
    )


def parse_zip_central_directory(tail_bytes: bytes, file_total_size: int) -> list[ZipEntry]:
    """Parse ZIP central directory from tail bytes of a remote or local archive."""
    eocd_pos = tail_bytes.rfind(EOCD_SIGNATURE)
    if eocd_pos == -1:
        raise ValueError("End of Central Directory (EOCD) signature not found in byte buffer")

    # Unpack EOCD: signature(4), disk(2), start_disk(2), records_disk(2), total_records(2),
    # size_cd(4), offset_cd(4), comment_len(2)
    eocd_data = tail_bytes[eocd_pos : eocd_pos + 22]
    if len(eocd_data) < 22:
        raise ValueError("Malformed EOCD record")

    _, _, _, _, total_records, _size_cd, offset_cd, _ = struct.unpack("<4sHHHHIIH", eocd_data)

    # Offset in tail_bytes where Central Directory starts
    # tail_bytes corresponds to [file_total_size - len(tail_bytes) : file_total_size]
    buffer_start_offset = file_total_size - len(tail_bytes)
    cd_start_in_buf = offset_cd - buffer_start_offset

    if cd_start_in_buf < 0 or cd_start_in_buf >= len(tail_bytes):
        raise ValueError("Central directory starts outside provided tail buffer (buffer too small)")

    entries: list[ZipEntry] = []
    idx = cd_start_in_buf

    for _ in range(total_records):
        if idx + 46 > len(tail_bytes):
            break
        header = tail_bytes[idx : idx + 46]
        if not header.startswith(CENTRAL_DIR_SIGNATURE):
            break

        (
            _,
            _,
            _,
            _,
            compression_method,
            _,
            _,
            _,
            compressed_size,
            uncompressed_size,
            filename_len,
            extra_len,
            comment_len,
            _,
            _,
            _,
            local_header_offset,
        ) = struct.unpack("<4sHHHHHHIIIHHHHHII", header)

        name_start = idx + 46
        name_end = name_start + filename_len
        filename = tail_bytes[name_start:name_end].decode("utf-8", errors="replace")

        entries.append(
            ZipEntry(
                filename=filename,
                compression_method=compression_method,
                compressed_size=compressed_size,
                uncompressed_size=uncompressed_size,
                local_header_offset=local_header_offset,
            )
        )

        idx = name_end + extra_len + comment_len

    return entries


def extract_metadata_from_payload(payload: bytes, compression_method: int) -> bytes:
    """Decompress or extract file content from local ZIP chunk."""
    # If starting at local header signature PK\x03\x04
    if payload.startswith(LOCAL_HEADER_SIGNATURE):
        # 30 bytes fixed header: 4s H H H H H I I I H H (11 fields)
        (
            _sig,
            _ver,
            _flags,
            _comp,
            _mod_t,
            _mod_d,
            _crc,
            _csize,
            _usize,
            fn_len,
            ex_len,
        ) = struct.unpack("<4sHHHHHIIIHH", payload[:30])
        data_offset = 30 + fn_len + ex_len
        payload = payload[data_offset:]

    if compression_method == 0:  # Stored
        return payload
    elif compression_method == 8:  # Deflate
        return zlib.decompress(payload, -zlib.MAX_WBITS)
    raise ValueError(f"Unsupported compression method: {compression_method}")


class PyPISimpleClient:
    """Client for PyPI Simple API (PEP 691 JSON & PEP 658 Metadata)."""

    def __init__(self, index_url: str = "https://pypi.org/simple/") -> None:
        self.index_url = index_url.rstrip("/") + "/"

    def fetch_project_info(self, project_name: str) -> dict[str, Any]:
        """Fetch project release metadata via PEP 691 JSON Simple API."""
        safe_name = re.sub(r"[-_.]+", "-", project_name).lower()
        url = f"{self.index_url}{safe_name}/"
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.pypi.simple.v1+json",
                "User-Agent": "evok/0.1.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read()
                return json.loads(data.decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise FileNotFoundError(f"Package '{project_name}' not found on PyPI") from e
            raise

    def fetch_pep658_metadata(self, wheel_url: str) -> PackageMetadata:
        """Fetch PEP 658 metadata directly via {wheel_url}.metadata."""
        metadata_url = f"{wheel_url}.metadata"
        req = urllib.request.Request(
            metadata_url,
            headers={"User-Agent": "evok/0.1.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read()
            return parse_metadata_bytes(content)

    def fetch_wheel_tail_metadata(self, wheel_url: str, tail_size: int = 65536) -> PackageMetadata:
        """Fetch METADATA from a remote wheel using HTTP Range requests."""
        # Step 1: Head or Range request to get total length and Central Directory
        req_tail = urllib.request.Request(
            wheel_url,
            headers={
                "Range": f"bytes=-{tail_size}",
                "User-Agent": "evok/0.1.0",
            },
        )
        with urllib.request.urlopen(req_tail, timeout=10) as resp:
            tail_bytes = resp.read()
            content_range = resp.headers.get("Content-Range", "")
            # e.g., 'bytes 1000-1099/1100'
            total_size = int(content_range.split("/")[-1]) if "/" in content_range else len(tail_bytes)

        entries = parse_zip_central_directory(tail_bytes, total_size)
        metadata_entry = None
        for entry in entries:
            if entry.filename.endswith(".dist-info/METADATA"):
                metadata_entry = entry
                break

        if not metadata_entry:
            raise ValueError(f"No .dist-info/METADATA found in wheel: {wheel_url}")

        # Step 2: Request byte range containing the METADATA entry
        start_byte = metadata_entry.local_header_offset
        # Max local header size (30 bytes + 256 path + extra) + compressed size
        end_byte = start_byte + 30 + 512 + metadata_entry.compressed_size
        req_entry = urllib.request.Request(
            wheel_url,
            headers={
                "Range": f"bytes={start_byte}-{end_byte}",
                "User-Agent": "evok/0.1.0",
            },
        )
        with urllib.request.urlopen(req_entry, timeout=10) as resp:
            payload = resp.read()
            uncompressed = extract_metadata_from_payload(payload, metadata_entry.compression_method)
            return parse_metadata_bytes(uncompressed)
