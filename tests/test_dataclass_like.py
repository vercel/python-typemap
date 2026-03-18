from typing import (
    Callable,
    Literal,
    ReadOnly,
    TypedDict,
    Never,
    Self,
)

import typemap_extensions as typing

import pytest


class FieldArgs(TypedDict, total=False):
    default: ReadOnly[object]


class Field[T: FieldArgs](typing.InitField[T]):
    pass


####

# TODO: Should this go into the stdlib?
type GetFieldItem[T, K] = typing.GetMemberType[
    typing.GetArg[T, typing.InitField, Literal[0]], K
]


# Extract the default type from an Init field.
# If it is a Field, then we try pulling out the "default" field,
# otherwise we return the type itself.
type GetDefault[Init] = (
    GetFieldItem[Init, Literal["default"]]
    if typing.IsAssignable[Init, Field]
    else Init
)


# Begin PEP section: dataclass like __init__

"""

``InitFnType`` generates a ``Member`` for a new ``__init__`` function
based on iterating over all attributes.

``GetDefault`` here is borrowed from our FastAPI-like example above.

"""

# Generate the Member field for __init__ for a class
type InitFnType[T] = typing.Member[
    Literal["__init__"],
    Callable[
        typing.Params[
            typing.Param[Literal["self"], Self],
            *[
                typing.Param[
                    p.name,
                    p.type,
                    # All arguments are keyword-only
                    # It takes a default if a default is specified in the class
                    Literal["keyword"]
                    if typing.IsAssignable[
                        GetDefault[p.init],
                        Never,
                    ]
                    else Literal["keyword", "default"],
                ]
                for p in typing.Iter[typing.Attrs[T]]
            ],
        ],
        None,
    ],
    Literal["ClassVar"],
]
type AddInit[T] = typing.NewProtocol[
    InitFnType[T],
    *[x for x in typing.Iter[typing.Members[T]]],
]


"""

``UpdateClass`` can then be used to create a class decorator (a la
``@dataclass``) adds a new ``__init__`` method to a class.

"""


def dataclass_ish[T](
    cls: type[T],
) -> typing.UpdateClass[
    # Add the computed __init__ function
    InitFnType[T],
]:
    pass


"""

Or to create a base class (a la Pydantic) that does.

"""


class Model:
    def __init_subclass__[T](
        cls: type[T],
    ) -> typing.UpdateClass[
        # Add the computed __init__ function
        InitFnType[T],
    ]:
        super().__init_subclass__()


# End PEP section


class Hero(Model):
    id: int | None = None

    name: str
    age: int | None = Field(default=None)

    secret_name: str


#######

import textwrap

from typemap.type_eval import eval_typing
from typemap.type_eval import format_helper


@pytest.mark.xfail(reason="UpateClass currently drops things")
def test_dataclass_like_1():
    tgt = eval_typing(Hero)
    fmt = format_helper.format_class(tgt)

    assert fmt == textwrap.dedent("""\
        class Hero:
            @classmethod
            def __init_subclass__[T](cls: type[T]) -> typemap.typing.UpdateClass[InitFnType[T]]: ...
            id: int | None = None
            name: str
            age: int | None = Field(default=None)
            secret_name: str
            def __init__(self: Self, *, id: int | None = ..., name: str, age: int | None = ..., secret_name: str) -> None: ...
    """)


# XXX: Delete this test once above passes
def test_dataclass_like_1_temp():
    tgt = eval_typing(Hero)
    fmt = format_helper.format_class(tgt)

    assert fmt == textwrap.dedent("""\
        class Hero:
            @classmethod
            def __init_subclass__[T](cls: type[T]) -> typemap.typing.UpdateClass[InitFnType[T]]: ...
            def __init__(self: Self, *, id: int | None = ..., name: str, age: int | None = ..., secret_name: str) -> None: ...
    """)
