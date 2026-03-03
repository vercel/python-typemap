# Type Manipulation in Python

This is the development repository for
[PEP 827 – Type Manipulation](https://peps.python.org/pep-0827/),
which proposes TypeScript-inspired type-level introspection and construction
facilities for the Python type system.

Discussion of the PEP is at the
[PEP 827 discussion thread](https://discuss.python.org/t/pep-827-type-manipulation/106353).

This repository also contains an implementation of the proposed
additions to ``typing`` ([typemap/typing.py](typemap/typing.py)), as well as a
**prototype** runtime evaluator ([typemap/type_eval](typemap/type_eval)).

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
