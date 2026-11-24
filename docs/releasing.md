# Releasing Evok

Version 0.1.1 publishes `ev --version`, `ev -v` and equivalent `evok` commands
already implemented on main. The runtime version and package metadata agree.
This patch does not make new performance or package-index compatibility claims.

Build one wheel and sdist, then run `python scripts/check_release.py dist --tag
v0.1.1` and `python scripts/qualify.py dist`. The latter installs each artifact
outside the checkout, runs the existing behavioral suite and both installed CLI
entry points, and checks dependency consistency. Platform/Python CI must pass
before merging the release preparation.

Publish through `release.yaml`, environment `pypi`. The workflow uploads the same
qualified files and retains SHA256/byte-size receipts. Verify actual PyPI bytes
and install the index version before recording publication as complete.

The tracked Homebrew formula preserves the previous archive identity. Update the
actual tap through a separate PR using the verified new PyPI sdist digest. Supply
that digest explicitly to the rendering helper, or build the exact archive;
a future version cannot reuse the historical 0.1.0 digest. Do not use the helper's
direct push path against protected main.
