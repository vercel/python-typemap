# Type Manipulation in Python

This is the development repository for
[PEP 827 – Type Manipulation](https://peps.python.org/pep-0827/),
which proposes TypeScript-inspired type-level introspection and construction
facilities for the Python type system.

This repository contains an implementation of the proposed additions
to ``typing`` ([typemap/typing.py](typemap/typing.py)), exported as
the module ``typemap_extensions``.

It also contains a **prototype** runtime evaluator
([typemap/type_eval](typemap/type_eval)).

Discussion of the PEP is at the
[PEP 827 discussion thread](https://discuss.python.org/t/pep-827-type-manipulation/106353).

A prototype typechecker implementation lives at
https://github.com/msullivan/mypy-typemap and is a test dependency of
this repo.

## Development

1. Clone the repo
2. `$ cd typemap`
3. `$ uv sync`
4. `$ uv run pytest`

## Running the typechecker

The prototype mypy can be run from this repo with `uv run mypy`.
Stubs are set up so that importing ``typemap_extensions`` will do the
right thing.

`uv run pytest tests/test_mypy_proto.py` will run the mypy prototype
against a supported subset of test files.

You can also run the prototype mypy directly on a file with `uv run mypy <file>`
