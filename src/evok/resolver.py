"""In-memory dependency resolver with constraint satisfaction and backtracking.

Supports in-memory mock providers, local wheel cache, and remote PyPI Simple index.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol

from evok.pep440 import BitPackedVersion, SpecifierSet


@dataclass(frozen=True)
class Requirement:
    """Dependency requirement (e.g. 'requests>=2.28.0,<3.0.0; python_version>=\"3.10\"')."""

    name: str
    specifier: SpecifierSet = field(default_factory=SpecifierSet)
    marker: str | None = None
    raw: str = ""

    @classmethod
    def parse(cls, req_str: str) -> Requirement:
        req_clean = req_str.strip()
        marker = None
        if ";" in req_clean:
            parts = req_clean.split(";", 1)
            req_clean = parts[0].strip()
            marker = parts[1].strip()

        # Extract name and version specifiers
        # e.g., requests>=2.28.0 or package==1.0
        match = re.match(r"^([a-zA-Z0-9_\-\.]+)\s*(.*)$", req_clean)
        if not match:
            raise ValueError(f"Invalid requirement string: {req_str!r}")

        name = match.group(1).lower().replace("_", "-")
        spec_str = match.group(2).strip()
        specifier = SpecifierSet(spec_str) if spec_str else SpecifierSet()

        return cls(name=name, specifier=specifier, marker=marker, raw=req_str)

    def __str__(self) -> str:
        return self.raw or f"{self.name}{self.specifier.raw}"


@dataclass
class Candidate:
    """A specific version candidate for a package."""

    name: str
    version: BitPackedVersion
    dependencies: list[Requirement] = field(default_factory=list)

    def __str__(self) -> str:
        return f"{self.name}=={self.version}"


class PackageProvider(Protocol):
    """Protocol for candidate search."""

    def get_candidates(self, package_name: str) -> list[Candidate]:
        """Return available candidates for package_name sorted descending by version."""
        ...


class InMemoryProvider:
    """In-memory package repository provider for tests and custom graphs."""

    def __init__(self, data: dict[str, dict[str, list[str]]] | None = None) -> None:
        # data: {pkg_name: {version_str: [dep_str1, dep_str2]}}
        self._packages: dict[str, list[Candidate]] = {}
        if data:
            for pkg, versions in data.items():
                safe_name = pkg.lower().replace("_", "-")
                cands: list[Candidate] = []
                for v_str, deps in versions.items():
                    reqs = [Requirement.parse(d) for d in deps]
                    cands.append(
                        Candidate(
                            name=safe_name,
                            version=BitPackedVersion(v_str),
                            dependencies=reqs,
                        )
                    )
                # Sort descending by version
                cands.sort(key=lambda c: c.version, reverse=True)
                self._packages[safe_name] = cands

    def add_package(self, name: str, version: str, dependencies: list[str] | None = None) -> None:
        safe_name = name.lower().replace("_", "-")
        deps = [Requirement.parse(d) for d in dependencies or []]
        cand = Candidate(name=safe_name, version=BitPackedVersion(version), dependencies=deps)
        if safe_name not in self._packages:
            self._packages[safe_name] = []
        self._packages[safe_name].append(cand)
        self._packages[safe_name].sort(key=lambda c: c.version, reverse=True)

    def get_candidates(self, package_name: str) -> list[Candidate]:
        safe_name = package_name.lower().replace("_", "-")
        return self._packages.get(safe_name, [])


@dataclass
class ResolutionGraph:
    """Resolved dependency graph."""

    packages: dict[str, Candidate] = field(default_factory=dict)

    def __contains__(self, name: str) -> bool:
        return name.lower().replace("_", "-") in self.packages

    def get(self, name: str) -> Candidate | None:
        return self.packages.get(name.lower().replace("_", "-"))

    def to_lock_dict(self) -> dict[str, dict[str, str]]:
        return {
            name: {
                "version": str(cand.version),
                "dependencies": [str(d) for d in cand.dependencies],
            }
            for name, cand in sorted(self.packages.items())
        }


class ResolutionError(Exception):
    """Raised when dependency resolution fails due to unsatisfiable constraints."""


class Resolver:
    """PubGrub-inspired backtracking dependency resolver."""

    def __init__(self, provider: PackageProvider | None = None) -> None:
        self.provider = provider or InMemoryProvider()

    def resolve(self, root_requirements: list[str | Requirement]) -> ResolutionGraph:
        """Resolve a list of root requirements into a consistent ResolutionGraph."""
        parsed_roots = [
            r if isinstance(r, Requirement) else Requirement.parse(r) for r in root_requirements
        ]

        # Initial constraints: {pkg_name: list of (SpecifierSet, source_desc)}
        constraints: dict[str, list[Requirement]] = {}
        for req in parsed_roots:
            constraints.setdefault(req.name, []).append(req)

        resolved: dict[str, Candidate] = {}
        success = self._backtrack(list(constraints.keys()), constraints, resolved)
        if not success:
            raise ResolutionError(f"Could not resolve dependencies for: {root_requirements}")

        return ResolutionGraph(packages=resolved)

    def _backtrack(
        self,
        queue: list[str],
        constraints: dict[str, list[Requirement]],
        resolved: dict[str, Candidate],
    ) -> bool:
        if not queue:
            return True

        current_pkg = queue[0]
        remaining_queue = queue[1:]

        # Filter candidates matching all constraints for current_pkg
        active_constraints = constraints.get(current_pkg, [])
        all_candidates = self.provider.get_candidates(current_pkg)
        matching_candidates = [
            c
            for c in all_candidates
            if all(req.specifier.contains(c.version) for req in active_constraints)
        ]

        if not matching_candidates:
            return False

        for candidate in matching_candidates:
            # Speculatively assign candidate
            resolved[current_pkg] = candidate

            # Add candidate's dependencies to constraints
            new_constraints: dict[str, list[Requirement]] = {
                k: list(v) for k, v in constraints.items()
            }
            new_queue = list(remaining_queue)
            conflict = False

            for dep in candidate.dependencies:
                dep_name = dep.name
                new_constraints.setdefault(dep_name, []).append(dep)

                # Check if already resolved package satisfies this new constraint
                if dep_name in resolved:
                    if not dep.specifier.contains(resolved[dep_name].version):
                        conflict = True
                        break
                elif dep_name not in new_queue:
                    new_queue.append(dep_name)

            if not conflict and self._backtrack(new_queue, new_constraints, resolved):
                return True

            # Backtrack
            del resolved[current_pkg]

        return False
