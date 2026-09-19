"""Assemble the Lambda deployment package: Linux wheels for the runtime dependencies plus the
``app`` package. Invoked by ``services/api/Makefile`` during ``sam build``; needs only the stdlib
and pip, so it works from any local Python. It lives inside the function's source directory
because SAM builds from a copy of that directory and nothing outside it.

Dependencies come from ``services/api/pyproject.toml`` so there is one source of truth. Two are
left out on purpose: ``uvicorn`` is only for running locally, and ``boto3`` is provided by the
Lambda runtime.
"""

import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

# Must match the runtime in infrastructure/aws/template.yaml (a test enforces this).
LAMBDA_PYTHON = "3.14"
LAMBDA_PLATFORMS = ("manylinux2014_x86_64", "manylinux_2_17_x86_64", "manylinux_2_28_x86_64")
EXCLUDED_DEPENDENCIES = frozenset({"uvicorn", "boto3"})

API_DIR = Path(__file__).resolve().parents[1]


def _distribution_name(requirement: str) -> str:
    match = re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", requirement)
    if match is None:
        raise ValueError(f"cannot read requirement {requirement!r}")
    return match.group(0).lower().replace("_", "-")


def lambda_requirements(pyproject: Path = API_DIR / "pyproject.toml") -> list[str]:
    declared: list[str] = tomllib.loads(pyproject.read_text())["project"]["dependencies"]
    return [r for r in declared if _distribution_name(r) not in EXCLUDED_DEPENDENCIES]


def build(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as scratch:
        requirements_file = Path(scratch) / "requirements.txt"
        requirements_file.write_text("\n".join(lambda_requirements()) + "\n")
        command = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--requirement",
            str(requirements_file),
            "--target",
            str(target),
            "--only-binary=:all:",
            "--implementation",
            "cp",
            "--python-version",
            LAMBDA_PYTHON,
            "--no-cache-dir",
            "--quiet",
        ]
        for platform in LAMBDA_PLATFORMS:
            command += ["--platform", platform]
        subprocess.run(command, check=True)
    shutil.copytree(
        API_DIR / "app",
        target / "app",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        dirs_exist_ok=True,
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: build_lambda.py <artifacts-dir>")
    build(Path(sys.argv[1]))
