# Computed Types in Python

See [pep.rst](pep.rst) for the PEP draft and [design-qs.rst](design-qs.rst) for some design discussion not yet merged into the PEP.

## Development

1. Clone the repo
2. `$ cd typemap`
3. `$ uv sync`
4. `$ uv run pytest`

## Running the typechecker

If you have https://github.com/msullivan/mypy/tree/typemap active in a
venv, you can run it against at least some of the tests with
invocations like:
  `mypy --python-version=3.14 tests/test_qblike_2.py`

Not all of them run cleanly yet though.
