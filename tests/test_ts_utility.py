# mypy: ignore-errors
"""
TypeScript-style utility type operators: Pick, Omit, Partial.

See https://www.typescriptlang.org/docs/handbook/utility-types.html
"""

import textwrap
from typing import Literal, NotRequired, TypedDict

import typemap_extensions as typing
from typemap.type_eval import eval_typing

from . import format_helper


# The "Todo" type from the TypeScript utility-types examples
class Todo:
    title: str
    description: str
    completed: bool


class TodoTD(TypedDict):
    title: str
    description: str
    completed: bool


# Begin PEP section: Utility types
"""
TypeScript defines a number of `utility types
<https://www.typescriptlang.org/docs/handbook/utility-types.html>`__
for performing common type operations.

We present implementations of a selection of them::

"""


# Pick<T, Keys>
# Constructs a type by picking the set of properties Keys from T.
type Pick[T, Keys] = typing.NewProtocol[
    *[
        p
        for p in typing.Iter[typing.Members[T]]
        if typing.IsAssignable[p.name, Keys]
    ]
]

# Omit<T, Keys>
# Constructs a type by picking all properties from T and then removing Keys.
type Omit[T, Keys] = typing.NewProtocol[
    *[
        p
        for p in typing.Iter[typing.Members[T]]
        if not typing.IsAssignable[p.name, Keys]
    ]
]

# Partial<T>
# Constructs a type with all properties of T set to optional (T | None).
type Partial[T] = typing.NewProtocol[
    *[
        typing.Member[p.name, p.type | None, p.quals]
        for p in typing.Iter[typing.Attrs[T]]
    ]
]

# PartialTD<T>
# Like Partial, but for TypedDicts: wraps all fields in NotRequired
# rather than making them T | None.
type PartialTD[T] = typing.NewProtocol[
    *[
        typing.Member[p.name, NotRequired[p.type], p.quals]
        for p in typing.Iter[typing.Attrs[T]]
    ]
]
# End PEP section: Utility types


def test_pick():
    tgt = eval_typing(Pick[Todo, Literal["title"] | Literal["completed"]])
    fmt = format_helper.format_class(tgt)
    assert fmt == textwrap.dedent("""\
        class Pick[tests.test_ts_utility.Todo, typing.Literal['title'] | typing.Literal['completed']]:
            title: str
            completed: bool
    """)


def test_omit():
    tgt = eval_typing(Omit[Todo, Literal["description"]])
    fmt = format_helper.format_class(tgt)
    assert fmt == textwrap.dedent("""\
        class Omit[tests.test_ts_utility.Todo, typing.Literal['description']]:
            title: str
            completed: bool
    """)


def test_partial():
    tgt = eval_typing(Partial[Todo])
    fmt = format_helper.format_class(tgt)
    assert fmt == textwrap.dedent("""\
        class Partial[tests.test_ts_utility.Todo]:
            title: str | None
            description: str | None
            completed: bool | None
    """)


def test_partial_td():
    tgt = eval_typing(PartialTD[TodoTD])
    fmt = format_helper.format_class(tgt)
    assert fmt == textwrap.dedent("""\
        class PartialTD[tests.test_ts_utility.TodoTD]:
            title: typing.NotRequired[str]
            description: typing.NotRequired[str]
            completed: typing.NotRequired[bool]
    """)
