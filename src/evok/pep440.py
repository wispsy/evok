"""High-performance PEP 440 version arithmetic using 64-bit integer packing.

Encodes epoch, major, minor, patch, and release lifecycle tags into a single scalar integer
for microsecond comparisons and specifier matching without Python object allocation overhead.
"""

from __future__ import annotations

import re
from typing import Any

# Bit-allocation layout for 64-bit packed integer:
# [63..56]: Epoch (8 bits: 0..255)
# [55..42]: Major (14 bits: 0..16,383)
# [41..28]: Minor (14 bits: 0..16,383)
# [27..14]: Patch (14 bits: 0..16,383)
# [13..11]: Stage (3 bits: 0=dev, 1=alpha, 2=beta, 3=rc, 4=final, 5=post)
# [10..0] : Stage Number (11 bits: 0..2,047)

STAGE_DEV = 0
STAGE_ALPHA = 1
STAGE_BETA = 2
STAGE_RC = 3
STAGE_FINAL = 4
STAGE_POST = 5

_VERSION_PATTERN = re.compile(
    r"""
    ^
    v?
    (?:(?P<epoch>[0-9]+)!)?                           # epoch
    (?P<release>[0-9]+(?:\.[0-9]+)*)                  # release segment
    (?P<pre>[-._]?(?P<pre_kind>a|b|rc|alpha|beta|c|pre|preview)[-._]?(?P<pre_num>[0-9]+)?)?  # pre-release
    (?P<post>[-._]?(?P<post_kind>post|rev|r)[-._]?(?P<post_num>[0-9]+)?)?                    # post-release
    (?P<dev>[-._]?(?P<dev_kind>dev)[-._]?(?P<dev_num>[0-9]+)?)?                              # dev-release
    (?:\+(?P<local>[a-z0-9]+(?:[-._][a-z0-9]+)*))?   # local version
    $
    """,
    re.VERBOSE | re.IGNORECASE,
)


def _normalize_stage(
    pre_kind: str | None,
    pre_num: str | None,
    post_kind: str | None,
    post_num: str | None,
    dev_kind: str | None,
    dev_num: str | None,
) -> tuple[int, int]:
    """Map release suffixes to (stage, stage_num) preserving PEP 440 order."""
    if dev_kind is not None:
        num = int(dev_num) if dev_num else 0
        return (STAGE_DEV, min(num, 2047))

    if pre_kind is not None:
        kind = pre_kind.lower()
        num = int(pre_num) if pre_num else 0
        if kind in ("a", "alpha"):
            return (STAGE_ALPHA, min(num, 2047))
        elif kind in ("b", "beta"):
            return (STAGE_BETA, min(num, 2047))
        elif kind in ("rc", "c", "pre", "preview"):
            return (STAGE_RC, min(num, 2047))

    if post_kind is not None:
        num = int(post_num) if post_num else 0
        return (STAGE_POST, min(num, 2047))

    return (STAGE_FINAL, 0)


class BitPackedVersion:
    """PEP 440 Version packed into a 64-bit integer for fast sorting and comparison."""

    __slots__ = ("_packed", "_raw", "epoch", "local", "release", "stage", "stage_num")

    def __init__(self, raw_version: str) -> None:
        self._raw = raw_version.strip()
        match = _VERSION_PATTERN.match(self._raw)
        if not match:
            raise ValueError(f"Invalid PEP 440 version string: {raw_version!r}")

        groups = match.groupdict()
        self.epoch = int(groups["epoch"]) if groups["epoch"] else 0
        self.release = tuple(int(seg) for seg in groups["release"].split("."))
        self.local = groups["local"]

        self.stage, self.stage_num = _normalize_stage(
            groups["pre_kind"],
            groups["pre_num"],
            groups["post_kind"],
            groups["post_num"],
            groups["dev_kind"],
            groups["dev_num"],
        )

        major = self.release[0] if len(self.release) > 0 else 0
        minor = self.release[1] if len(self.release) > 1 else 0
        patch = self.release[2] if len(self.release) > 2 else 0

        # Pack into 64-bit integer if within limits, otherwise fallback
        if (
            self.epoch < 256
            and major < 16384
            and minor < 16384
            and patch < 16384
            and len(self.release) <= 3
        ):
            self._packed = (
                (self.epoch << 56)
                | (major << 42)
                | (minor << 28)
                | (patch << 14)
                | (self.stage << 11)
                | self.stage_num
            )
        else:
            self._packed = None

    @property
    def is_prerelease(self) -> bool:
        return self.stage in (STAGE_DEV, STAGE_ALPHA, STAGE_BETA, STAGE_RC)

    @property
    def is_postrelease(self) -> bool:
        return self.stage == STAGE_POST

    @property
    def is_devrelease(self) -> bool:
        return self.stage == STAGE_DEV

    @property
    def packed(self) -> int | None:
        return self._packed

    def _full_key(self) -> tuple[Any, ...]:
        return (self.epoch, self.release, self.stage, self.stage_num, self.local or "")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BitPackedVersion):
            if isinstance(other, str):
                try:
                    other = BitPackedVersion(other)
                except ValueError:
                    return False
            else:
                return False
        if self._packed is not None and other._packed is not None:
            return self._packed == other._packed and self.local == other.local
        return self._full_key() == other._full_key()

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, BitPackedVersion):
            if isinstance(other, str):
                other = BitPackedVersion(other)
            else:
                return NotImplemented
        if self._packed is not None and other._packed is not None:
            if self._packed != other._packed:
                return self._packed < other._packed
            return (self.local or "") < (other.local or "")
        return self._full_key() < other._full_key()

    def __le__(self, other: object) -> bool:
        return self == other or self < other

    def __gt__(self, other: object) -> bool:
        return not (self <= other)

    def __ge__(self, other: object) -> bool:
        return not (self < other)

    def __hash__(self) -> int:
        return hash(self._full_key())

    def __repr__(self) -> str:
        return f"BitPackedVersion('{self._raw}', packed={hex(self._packed) if self._packed else 'fallback'})"

    def __str__(self) -> str:
        return self._raw


class VersionSpecifier:
    """Single PEP 440 version specifier clause (e.g. '>=1.2.0', '<2.0', '==1.2.*', '~=1.4.2')."""

    def __init__(self, clause: str) -> None:
        clause = clause.strip()
        match = re.match(r"^([=><~^!]{1,2})\s*(.*)$", clause)
        if match:
            self.op = match.group(1)
            self.target_str = match.group(2).strip()
        else:
            self.op = "=="
            self.target_str = clause

        self.is_wildcard = self.target_str.endswith(".*")
        if self.is_wildcard:
            prefix = self.target_str[:-2]
            self.prefix_parts = [int(p) for p in prefix.split(".") if p.isdigit()]
        else:
            self.target = BitPackedVersion(self.target_str)

    def contains(self, v: BitPackedVersion | str) -> bool:
        ver = v if isinstance(v, BitPackedVersion) else BitPackedVersion(v)

        if self.is_wildcard:
            prefix_match = ver.release[: len(self.prefix_parts)] == tuple(self.prefix_parts)
            if self.op in ("==", "==="):
                return prefix_match
            elif self.op == "!=":
                return not prefix_match
            return False

        if self.op == "==":
            return ver == self.target
        elif self.op == "!=":
            return ver != self.target
        elif self.op == "<":
            return ver < self.target
        elif self.op == "<=":
            return ver <= self.target
        elif self.op == ">":
            return ver > self.target
        elif self.op == ">=":
            return ver >= self.target
        elif self.op == "~=":
            # PEP 440 compatible release: ~=X.Y.Z is >= X.Y.Z, == X.Y.*
            if ver < self.target:
                return False
            base_len = max(len(self.target.release) - 1, 1)
            return ver.release[:base_len] == self.target.release[:base_len]
        return False

    def __contains__(self, v: BitPackedVersion | str) -> bool:
        return self.contains(v)

    def __repr__(self) -> str:
        return f"VersionSpecifier('{self.op}{self.target_str}')"


class SpecifierSet:
    """Set of PEP 440 version constraints, comma-separated."""

    def __init__(self, specifiers: str = "") -> None:
        self.raw = specifiers.strip()
        self.clauses: list[VersionSpecifier] = []
        if self.raw:
            for part in self.raw.split(","):
                part = part.strip()
                if part:
                    self.clauses.append(VersionSpecifier(part))

    def contains(self, v: BitPackedVersion | str, prereleases: bool = False) -> bool:
        ver = v if isinstance(v, BitPackedVersion) else BitPackedVersion(v)
        if not prereleases and ver.is_prerelease:
            # Only match prerelease if explicitly requested in a clause
            has_prerelease_spec = any(
                c.target.is_prerelease for c in self.clauses if hasattr(c, "target")
            )
            if not has_prerelease_spec:
                return False
        return all(c.contains(ver) for c in self.clauses)

    def filter(
        self, versions: list[BitPackedVersion | str], prereleases: bool = False
    ) -> list[BitPackedVersion]:
        parsed = [v if isinstance(v, BitPackedVersion) else BitPackedVersion(v) for v in versions]
        return [v for v in parsed if self.contains(v, prereleases=prereleases)]

    def __contains__(self, v: BitPackedVersion | str) -> bool:
        return self.contains(v)

    def __repr__(self) -> str:
        return f"SpecifierSet('{self.raw}')"
