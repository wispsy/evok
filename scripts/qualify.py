"""Qualify the exact installed wheel and sdist outside the checkout."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(command, cwd):
    return subprocess.run(command, cwd=cwd, check=True, timeout=180)


def main():
    directory = Path(sys.argv[1]).resolve()
    artifacts = sorted([*directory.glob("*.whl"), *directory.glob("*.tar.gz")])
    if len(artifacts) != 2:
        raise ValueError("Select one wheel and one sdist")
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    for artifact in artifacts:
        with tempfile.TemporaryDirectory(prefix="evok-installed-") as temporary:
            outside = Path(temporary)
            for folder in ("tests", "scripts", "packaging"):
                shutil.copytree(
                    ROOT / folder,
                    outside / folder,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
                )
            shutil.copy2(ROOT / "pyproject.toml", outside / "pyproject.toml")
            environment = outside / "env"
            run(["uv", "venv", str(environment), "--python", sys.executable], outside)
            scripts = environment / ("Scripts" if os.name == "nt" else "bin")
            python = scripts / ("python.exe" if os.name == "nt" else "python")
            run(
                [
                    "uv",
                    "pip",
                    "install",
                    "--python",
                    str(python),
                    str(artifact),
                    *project["dependency-groups"]["dev"],
                ],
                outside,
            )
            run(
                [
                    str(python),
                    "-I",
                    "-c",
                    "import evok; from pathlib import Path; import sys; assert Path(evok.__file__).is_relative_to(sys.prefix)",
                ],
                outside,
            )
            run(
                [str(python), "-I", "-m", "pytest", "tests", "--import-mode=importlib", "-q"],
                outside,
            )
            for name in ("ev", "evok"):
                command = scripts / (name + ".exe" if os.name == "nt" else name)
                for flag in ("--version", "-v"):
                    result = subprocess.run(
                        [str(command), flag],
                        cwd=outside,
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    assert result.stdout.strip() == "evok " + project["project"]["version"]
                result = subprocess.run(
                    [str(command), "info"], cwd=outside, capture_output=True, text=True, check=True
                )
                assert (
                    result.stdout.splitlines()[0]
                    == "evok version:     " + project["project"]["version"]
                )
            run(["uv", "pip", "check", "--python", str(python)], outside)
        print(
            json.dumps(
                {
                    "artifact": artifact.name,
                    "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                    "python": sys.version.split()[0],
                    "platform": sys.platform,
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
