"""Code quality assurance tests using pytest."""

import pathlib
import subprocess
import sys

import pytest


@pytest.fixture(scope="module")
def project_root() -> pathlib.Path:
    """Get the project root directory."""
    return pathlib.Path(__file__).parent.parent


def test_cqa_ruff_check(project_root):
    """Test that code passes ruff linting checks."""
    # Ruff respects pyproject.toml configuration and exclusions
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "."],
        capture_output=True,
        text=True,
        cwd=project_root,
    )

    if result.returncode != 0:
        pytest.fail(
            f"ruff check failed:\n{result.stdout}\n{result.stderr}",
            pytrace=False,
        )


def test_cqa_ruff_format_check(project_root):
    """Test that code is properly formatted according to ruff."""
    # Ruff format respects pyproject.toml exclusions
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "format", "--check", "."],
        capture_output=True,
        text=True,
        cwd=project_root,
    )

    if result.returncode != 0:
        pytest.fail(
            f"ruff format check failed:\n{result.stdout}\n{result.stderr}",
            pytrace=False,
        )


def test_cqa_mypy(project_root):
    """Test that code passes mypy type checking."""
    # Mypy uses configuration from pyproject.toml
    # Run on typemap -- tests not ready yet
    for subdir in ["typemap"]:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "mypy",
                "--config-file",
                project_root / "pyproject.toml",
                subdir,
            ],
            capture_output=True,
            text=True,
            cwd=project_root,
        )

        if result.returncode != 0:
            output = result.stdout
            if result.stderr:
                output += "\n\n" + result.stderr
            pytest.fail(f"mypy validation failed:\n{output}", pytrace=False)
