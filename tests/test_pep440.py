import pytest

from evok.pep440 import BitPackedVersion, SpecifierSet, VersionSpecifier


def test_bit_packed_version_ordering() -> None:
    v_dev = BitPackedVersion("1.0.0.dev1")
    v_a = BitPackedVersion("1.0.0a1")
    v_b = BitPackedVersion("1.0.0b1")
    v_rc = BitPackedVersion("1.0.0rc1")
    v_final = BitPackedVersion("1.0.0")
    v_post = BitPackedVersion("1.0.0.post1")
    v_next = BitPackedVersion("1.0.1")

    # Strict ascending order
    assert v_dev < v_a
    assert v_a < v_b
    assert v_b < v_rc
    assert v_rc < v_final
    assert v_final < v_post
    assert v_post < v_next

    # Check packed integer exists and preserves order
    assert v_dev.packed is not None
    assert v_final.packed is not None
    assert v_dev.packed < v_final.packed


def test_version_equality() -> None:
    v1 = BitPackedVersion("1.2.3")
    v2 = BitPackedVersion("1.2.3")
    v3 = BitPackedVersion("1.2.4")

    assert v1 == v2
    assert v1 == "1.2.3"
    assert v1 != v3
    assert hash(v1) == hash(v2)


def test_version_specifiers() -> None:
    s_gte = VersionSpecifier(">=1.2.0")
    assert "1.2.0" in s_gte
    assert "1.2.1" in s_gte
    assert "1.1.9" not in s_gte

    s_lt = VersionSpecifier("<2.0.0")
    assert "1.99.99" in s_lt
    assert "2.0.0" not in s_lt

    s_compat = VersionSpecifier("~=1.4.2")
    assert "1.4.2" in s_compat
    assert "1.4.9" in s_compat
    assert "1.5.0" not in s_compat
    assert "1.4.1" not in s_compat

    s_wildcard = VersionSpecifier("==1.2.*")
    assert "1.2.0" in s_wildcard
    assert "1.2.15" in s_wildcard
    assert "1.3.0" not in s_wildcard


def test_specifier_set() -> None:
    spec = SpecifierSet(">=1.0.0, <2.0.0, !=1.5.0")
    assert spec.contains("1.0.0")
    assert spec.contains("1.4.9")
    assert not spec.contains("1.5.0")
    assert not spec.contains("2.0.0")
    assert not spec.contains("0.9.9")

    # Prereleases exclusion by default
    assert not spec.contains("1.6.0a1")
    assert spec.contains("1.6.0a1", prereleases=True)

    filtered = spec.filter(["0.9.0", "1.2.0", "1.5.0", "1.8.0", "2.1.0"])
    assert [str(v) for v in filtered] == ["1.2.0", "1.8.0"]


def test_invalid_version() -> None:
    with pytest.raises(ValueError, match="Invalid PEP 440"):
        BitPackedVersion("not-a-valid-version-!!!")
