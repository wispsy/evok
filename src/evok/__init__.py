"""Evok: Pure-Python high-performance package manager and virtualization runtime."""

from evok.environment import Environment
from evok.pep440 import BitPackedVersion, SpecifierSet, VersionSpecifier
from evok.resolver import InMemoryProvider, Requirement, ResolutionGraph, Resolver

__version__ = "0.1.0"

__all__ = [
    "BitPackedVersion",
    "Environment",
    "InMemoryProvider",
    "Requirement",
    "ResolutionGraph",
    "Resolver",
    "SpecifierSet",
    "VersionSpecifier",
    "__version__",
]
