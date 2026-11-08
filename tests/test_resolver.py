import pytest

from evok.pep440 import BitPackedVersion
from evok.resolver import InMemoryProvider, Requirement, ResolutionError, Resolver


def test_requirement_parsing() -> None:
    req = Requirement.parse("httpx>=0.24.0,<1.0.0")
    assert req.name == "httpx"
    assert req.specifier.contains("0.24.0")
    assert req.specifier.contains("0.27.0")
    assert not req.specifier.contains("1.0.0")


def test_resolver_simple_resolution() -> None:
    provider = InMemoryProvider(
        {
            "pkg-a": {"1.0.0": ["pkg-b>=2.0"], "0.9.0": []},
            "pkg-b": {"2.1.0": [], "2.0.0": [], "1.5.0": []},
        }
    )

    resolver = Resolver(provider=provider)
    graph = resolver.resolve(["pkg-a>=0.9.0"])

    assert "pkg-a" in graph
    assert graph.get("pkg-a").version == BitPackedVersion("1.0.0")
    assert "pkg-b" in graph
    assert graph.get("pkg-b").version == BitPackedVersion("2.1.0")


def test_resolver_backtracking_conflict() -> None:
    # pkg-a 2.0 requires pkg-c==1.0
    # pkg-a 1.0 requires pkg-c==2.0
    # root requires pkg-b which requires pkg-c>=2.0
    # Resolver should backtrack from pkg-a 2.0 to 1.0 to satisfy pkg-c>=2.0!
    provider = InMemoryProvider(
        {
            "pkg-a": {
                "2.0.0": ["pkg-c==1.0.0"],
                "1.0.0": ["pkg-c==2.0.0"],
            },
            "pkg-b": {
                "1.0.0": ["pkg-c>=2.0.0"],
            },
            "pkg-c": {
                "2.0.0": [],
                "1.0.0": [],
            },
        }
    )

    resolver = Resolver(provider=provider)
    graph = resolver.resolve(["pkg-a", "pkg-b"])

    assert graph.get("pkg-a").version == BitPackedVersion("1.0.0")
    assert graph.get("pkg-b").version == BitPackedVersion("1.0.0")
    assert graph.get("pkg-c").version == BitPackedVersion("2.0.0")


def test_resolver_unsatisfiable() -> None:
    provider = InMemoryProvider(
        {
            "pkg-a": {"1.0.0": ["pkg-b<1.0"]},
            "pkg-b": {"2.0.0": []},
        }
    )
    resolver = Resolver(provider=provider)
    with pytest.raises(ResolutionError):
        resolver.resolve(["pkg-a"])
