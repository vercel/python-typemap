import textwrap

from typing import (
    Callable,
    Literal,
    Union,
    ReadOnly,
    TypedDict,
    Never,
    Self,
)

from typemap.type_eval import eval_typing
from typemap.typing import (
    NewProtocol,
    Iter,
    Attrs,
    Sub,
    FromUnion,
    GetArg,
    GetAttr,
    GetType,
    GetName,
    GetQuals,
    GetInit,
    InitField,
    Member,
    Members,
    Param,
)

from . import format_helper


class FieldArgs(TypedDict, total=False):
    hidden: ReadOnly[bool]
    primary_key: ReadOnly[bool]
    index: ReadOnly[bool]
    default: ReadOnly[object]


class Field[T: FieldArgs](InitField[T]):
    pass


####

# TODO: Should this go into the stdlib?
type GetFieldItem[T: InitField, K] = GetAttr[GetArg[T, InitField, 0], K]


##

# Strip `| None` from a type by iterating over its union components
# and filtering
type NotOptional[T] = Union[
    *[x for x in Iter[FromUnion[T]] if not Sub[x, None]]
]

# Adjust an attribute type for use in Public below by dropping | None for
# primary keys and stripping all annotations.
type FixPublicType[T, Init] = (
    NotOptional[T]
    if Sub[Literal[True], GetFieldItem[Init, Literal["primary_key"]]]
    else T
)

# Extract the default type from an Init field.
# If it is a Field, then we try pulling out the "default" field,
# otherwise we return the type itself.
type GetDefault[Init] = (
    GetFieldItem[Init, Literal["default"]] if Sub[Init, Field] else Init
)

# Strip out everything that is Hidden and also make the primary key required
# Drop all the annotations, since this is for data getting returned to users
# from the DB, so we don't need default values.
type Public[T] = NewProtocol[
    *[
        Member[GetName[p], FixPublicType[GetType[p], GetInit[p]], GetQuals[p]]
        for p in Iter[Attrs[T]]
        if not Sub[Literal[True], GetFieldItem[GetInit[p], Literal["hidden"]]]
    ]
]

# Create takes everything but the primary key and preserves defaults
type Create[T] = NewProtocol[
    *[
        Member[GetName[p], GetType[p], GetQuals[p], GetDefault[GetInit[p]]]
        for p in Iter[Attrs[T]]
        if not Sub[
            Literal[True], GetFieldItem[GetInit[p], Literal["primary_key"]]
        ]
    ]
]

# Update takes everything but the primary key, but makes them all have
# None defaults
type Update[T] = NewProtocol[
    *[
        Member[
            GetName[p],
            GetType[p] | None,
            GetQuals[p],
            Literal[None],
        ]
        for p in Iter[Attrs[T]]
        if not Sub[
            Literal[True], GetFieldItem[GetInit[p], Literal["primary_key"]]
        ]
    ]
]

##

# Generate the Member field for __init__ for a class
type InitFnType[T] = Member[
    Literal["__init__"],
    Callable[
        [
            Param[Literal["self"], Self],
            *[
                Param[
                    GetName[p],
                    GetType[p],
                    # All arguments are keyword-only
                    # It takes a default if a default is specified in the class
                    Literal["keyword"]
                    if Sub[
                        GetDefault[GetInit[p]],
                        Never,
                    ]
                    else Literal["keyword", "default"],
                ]
                for p in Iter[Attrs[T]]
            ],
        ],
        None,
    ],
    Literal["ClassVar"],
]
type AddInit[T] = NewProtocol[
    InitFnType[T],
    *[x for x in Iter[Members[T]]],
]


####

# This is the FastAPI example code that we are trying to repair!
# Adapted from https://fastapi.tiangolo.com/tutorial/sql-databases/#heroupdate-the-data-model-to-update-a-hero
"""
class HeroBase(SQLModel):
    name: str = Field(index=True)
    age: int | None = Field(default=None, index=True)


class Hero(HeroBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    secret_name: str


class HeroPublic(HeroBase):
    id: int


class HeroCreate(HeroBase):
    secret_name: str


class HeroUpdate(HeroBase):
    name: str | None = None
    age: int | None = None
    secret_name: str | None = None
"""


class Hero:
    id: int | None = Field(default=None, primary_key=True)

    name: str = Field(index=True)
    age: int | None = Field(default=None, index=True)

    secret_name: str = Field(hidden=True)


#######


def test_fastapi_like_0():
    tgt = eval_typing(AddInit[Hero])
    fmt = format_helper.format_class(tgt)

    assert fmt == textwrap.dedent("""\
        class AddInit[tests.test_fastapilike_2.Hero]:
            id: int | None = Field(default=None, primary_key=True)
            name: str = Field(index=True)
            age: int | None = Field(default=None, index=True)
            secret_name: str = Field(hidden=True)
            def __init__(self: Self, *, id: int | None = ..., name: str, age: int | None = ..., secret_name: str) -> None: ...
    """)


def test_fastapi_like_1():
    tgt = eval_typing(AddInit[Public[Hero]])
    fmt = format_helper.format_class(tgt)

    assert fmt == textwrap.dedent("""\
        class AddInit[tests.test_fastapilike_2.Public[tests.test_fastapilike_2.Hero]]:
            id: int
            name: str
            age: int | None
            def __init__(self: Self, *, id: int, name: str, age: int | None) -> None: ...
    """)


def test_fastapi_like_2():
    tgt = eval_typing(AddInit[Create[Hero]])
    fmt = format_helper.format_class(tgt)

    assert fmt == textwrap.dedent("""\
        class AddInit[tests.test_fastapilike_2.Create[tests.test_fastapilike_2.Hero]]:
            name: str
            age: int | None = None
            secret_name: str
            def __init__(self: Self, *, name: str, age: int | None = ..., secret_name: str) -> None: ...
    """)


def test_fastapi_like_3():
    tgt = eval_typing(AddInit[Update[Hero]])
    fmt = format_helper.format_class(tgt)

    assert fmt == textwrap.dedent("""\
        class AddInit[tests.test_fastapilike_2.Update[tests.test_fastapilike_2.Hero]]:
            name: str | None = None
            age: int | None = None
            secret_name: str | None = None
            def __init__(self: Self, *, name: str | None = ..., age: int | None = ..., secret_name: str | None = ...) -> None: ...
    """)
