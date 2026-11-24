#!/usr/bin/env python3
"""Automate publishing Homebrew Formula to wispsy/homebrew-tap."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = REPO_ROOT / "dist"
PACKAGING_DIR = REPO_ROOT / "packaging" / "homebrew"
DEFAULT_TAP_REPO = "wispsy/homebrew-tap"


def get_version() -> str:
    """Read version from src/evok/__init__.py."""
    init_file = REPO_ROOT / "src" / "evok" / "__init__.py"
    with open(init_file, encoding="utf-8") as f:
        for line in f:
            if line.startswith("__version__"):
                return line.split("=")[1].strip().strip('"').strip("'")
    return "0.1.0"


def calculate_sha256(path: Path) -> str:
    """Calculate SHA256 of a local file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def render_formula(version: str, sha256: str) -> str:
    """Render Formula/evok.rb content."""
    return f"""class Evok < Formula
  include Language::Python::Virtualenv

  desc "Pure-Python high-performance package manager and virtualization runtime"
  homepage "https://github.com/wispsy/evok"
  url "https://files.pythonhosted.org/packages/source/e/evok/evok-{version}.tar.gz"
  sha256 "{sha256}"
  license "MIT"

  depends_on "python@3.14"

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "evok {version}", shell_output("#{{bin}}/ev --version")
    assert_match "evok {version}", shell_output("#{{bin}}/evok --version")
    assert_match "evok version:", shell_output("#{{bin}}/ev info")
    system libexec/"bin/python", "-c", "import evok; assert evok.__version__ == '{version}'"
  end
end
"""


def render_tap_readme() -> str:
    """Render comprehensive README.md for wispsy/homebrew-tap."""
    return """# homebrew-tap

Homebrew formulas for wispsy applications, frameworks, tools, etc.

## Installation

Add the Wispsy tap to your Homebrew installation:

```bash
brew tap wispsy/tap
```

## Available Formulas

| Formula | Description | Installation |
|---|---|---|
| **[clownfish](Formula/clownfish.rb)** | Lightweight, zero-dependency modern terminal emulator | `brew install clownfish` |
| **[evok](Formula/evok.rb)** | Pure-Python high-performance package manager and virtualization runtime | `brew install evok` |

## Available Casks

| Cask | Description | Installation |
|---|---|---|
| **[clownfish](Casks/clownfish.rb)** | Standalone macOS application bundle for Clownfish terminal | `brew install --cask wispsy/tap/clownfish` |
"""


def publish_to_tap(
    tap_repo: str,
    formula_content: str,
    version: str,
    dry_run: bool = False,
) -> None:
    """Commit and push updated formula and README to the tap repository."""
    print(f"Target tap: {tap_repo}")
    if dry_run:
        print("\n--- [DRY RUN] Formula/evok.rb ---")
        print(formula_content)
        print("\n--- [DRY RUN] README.md ---")
        print(render_tap_readme())
        print("\nDry run completed. No remote changes made.")
        return

    with tempfile.TemporaryDirectory() as tmp_dir:
        clone_url = f"https://github.com/{tap_repo}.git"
        print(f"Cloning {clone_url}...")
        subprocess.run(["git", "clone", clone_url, tmp_dir], check=True)

        formula_dir = Path(tmp_dir) / "Formula"
        formula_dir.mkdir(parents=True, exist_ok=True)
        formula_file = formula_dir / "evok.rb"
        formula_file.write_text(formula_content, encoding="utf-8")

        # Update tap README.md
        readme_file = Path(tmp_dir) / "README.md"
        readme_file.write_text(render_tap_readme(), encoding="utf-8")

        # Also update in local packaging directory for tracking
        (PACKAGING_DIR / "Formula" / "evok.rb").write_text(formula_content, encoding="utf-8")

        status_res = subprocess.run(
            ["git", "-C", tmp_dir, "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        )
        if not status_res.stdout.strip():
            print("No changes to publish in tap repository.")
            return

        subprocess.run(["git", "-C", tmp_dir, "add", "Formula/evok.rb", "README.md"], check=True)
        commit_msg = f"feat(evok): add evok v{version} formula and update README"
        subprocess.run(
            ["git", "-C", tmp_dir, "commit", "-m", commit_msg],
            check=True,
        )
        print(f"Pushing updates to {tap_repo}...")
        subprocess.run(["git", "-C", tmp_dir, "push", "origin", "main"], check=True)
        print("Successfully published to Homebrew tap!")


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish Evok to wispsy/homebrew-tap")
    parser.add_argument("--version", default=get_version(), help="Release version")
    parser.add_argument("--tap", default=DEFAULT_TAP_REPO, help="Target Homebrew tap repository")
    parser.add_argument("--tar-sha256", help="SHA256 of evok source tarball")
    parser.add_argument("--dry-run", action="store_true", help="Print formulas without pushing")
    args = parser.parse_args()

    version = args.version
    tar_path = DIST_DIR / f"evok-{version}.tar.gz"

    tar_sha = args.tar_sha256
    if not tar_sha:
        if tar_path.exists():
            tar_sha = calculate_sha256(tar_path)
            print(f"Calculated sdist sha256: {tar_sha}")
        elif version == "0.1.0":
            # Retain the known immutable 0.1.0 digest only for that version.
            tar_sha = "77a2ab2ee59ae6403feb48dc58a3d702794e44d0cdc0713c3ac0ee2fbda304a3"
            print(f"Using known PyPI release sha256 for {version}: {tar_sha}")
        else:
            parser.error("Provide --tar-sha256 or build the exact selected source archive first")

    formula_content = render_formula(version, tar_sha)
    publish_to_tap(args.tap, formula_content, version, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
