"""Run mypy on each test file that doesn't have # SKIP MYPY."""

import os
import pathlib
import subprocess
import sys

import pytest

PROJECT_ROOT = pathlib.Path(__file__).parent.parent

# Set MYPY_SOURCE_DIR to use a local mypy source checkout.
_mypy_source = os.environ.get("MYPY_SOURCE_DIR")
MYPY_SOURCE_DIR = pathlib.Path(_mypy_source).resolve() if _mypy_source else None


def _collect_mypy_test_files():
    """Collect test files that don't have # SKIP MYPY."""
    tests_dir = pathlib.Path(__file__).parent
    for path in sorted(tests_dir.glob("test_*.py")):
        if path.name in ("test_cqa.py", "test_mypy_proto.py"):
            continue
        text = path.read_text()
        if "# SKIP MYPY" not in text:
            yield pytest.param(path, id=path.stem)


@pytest.mark.parametrize("test_file", _collect_mypy_test_files())
def test_mypy(test_file):
    """Test that individual test files pass mypy."""
    env = None
    if MYPY_SOURCE_DIR:
        env = {**os.environ, "PYTHONPATH": str(MYPY_SOURCE_DIR)}
    cmd = [
        sys.executable,
        "-m",
        "mypy",
        "--config-file",
        str(PROJECT_ROOT / "pyproject.toml"),
        str(test_file),
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        env=env,
    )

    if result.returncode != 0:
        output = result.stdout
        if result.stderr:
            output += "\n\n" + result.stderr
        pytest.fail(
            f"mypy failed on {test_file.name}:\n{output}", pytrace=False
        )
