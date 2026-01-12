import dataclasses
import enum
import textwrap

from typing import Annotated, Literal, Union

from typemap.type_eval import eval_typing
from typemap.typing import (
    NewProtocol,
    Iter,
    Attrs,
    Is,
    GetAnnotations,
    DropAnnotations,
    FromUnion,
    GetType,
    GetName,
    GetQuals,
    Member,
)

from . import format_helper


class PropQuals(enum.StrEnum):
    HIDDEN = "HIDDEN"
    PRIMARY = "PRIMARY"
    HAS_DEFAULT = "HAS_DEFAULT"


@dataclasses.dataclass(frozen=True)
class _Default:
    val: object


type Hidden[T] = Annotated[T, Literal[PropQuals.HIDDEN]]
type Primary[T] = Annotated[T, Literal[PropQuals.PRIMARY]]
type HasDefault[T, default] = Annotated[
    T, _Default(default), Literal[PropQuals.HAS_DEFAULT]
]


####
type AllOptional[T] = NewProtocol[
    *[
        Member[GetName[p], GetType[p] | None, GetQuals[p]]
        for p in Iter[Attrs[T]]
    ]
]

type NotOptional[T] = Union[
    *[x for x in Iter[FromUnion[T]] if not Is[x, type(None)]]
]
type FixPublicType[T] = DropAnnotations[
    # Drop the | None for the primary keys
    NotOptional[T] if Is[Literal[PropQuals.PRIMARY], GetAnnotations[T]] else T
]

# Strip out everything that is Hidden and also make the primary key required
# Drop all the annotations, since this is for returns.
type Public[T] = NewProtocol[
    *[
        Member[GetName[p], FixPublicType[GetType[p]], GetQuals[p]]
        for p in Iter[Attrs[T]]
        if not Is[Literal[PropQuals.HIDDEN], GetAnnotations[GetType[p]]]
    ]
]

# Create takes everything but the primary key and preserves defaults
type Create[T] = NewProtocol[
    *[
        Member[GetName[p], GetType[p], GetQuals[p]]
        for p in Iter[Attrs[T]]
        if not Is[Literal[PropQuals.PRIMARY], GetAnnotations[GetType[p]]]
    ]
]


# Update takes everything but the primary key, but makes them all have
# None defaults
type Update[T] = NewProtocol[
    *[
        Member[
            GetName[p],
            HasDefault[DropAnnotations[GetType[p]] | None, None],
            GetQuals[p],
        ]
        for p in Iter[Attrs[T]]
        if not Is[Literal[PropQuals.PRIMARY], GetAnnotations[GetType[p]]]
    ]
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
    id: Primary[
        HasDefault[int | None, None]
    ]  # = Field(default=None, primary_key=True)

    name: str
    age: HasDefault[int | None, None]  # = Field(default=None, index=True)

    secret_name: Hidden[str]


#######


def test_eval_drop_optional_1():
    tgt = eval_typing(NotOptional[int | None])
    assert tgt is int


def test_fastapi_like_1():
    tgt = eval_typing(Public[Hero])
    fmt = format_helper.format_class(tgt)

    assert fmt == textwrap.dedent("""\
        class Public[tests.test_fastapilike_1.Hero]:
            id: int
            name: str
            age: int | None
    """)


def test_fastapi_like_2():
    tgt = eval_typing(Create[Hero])
    fmt = format_helper.format_class(tgt)

    assert fmt == textwrap.dedent("""\
        class Create[tests.test_fastapilike_1.Hero]:
            name: str
            age: typing.Annotated[int | None, _Default(val=None), typing.Literal[<PropQuals.HAS_DEFAULT: 'HAS_DEFAULT'>]]
            secret_name: typing.Annotated[str, typing.Literal[<PropQuals.HIDDEN: 'HIDDEN'>]]
    """)


def test_fastapi_like_3():
    tgt = eval_typing(Update[Hero])
    fmt = format_helper.format_class(tgt)

    assert fmt == textwrap.dedent("""\
        class Update[tests.test_fastapilike_1.Hero]:
            name: typing.Annotated[str | None, _Default(val=None), typing.Literal[<PropQuals.HAS_DEFAULT: 'HAS_DEFAULT'>]]
            age: typing.Annotated[int | None, _Default(val=None), typing.Literal[<PropQuals.HAS_DEFAULT: 'HAS_DEFAULT'>]]
            secret_name: typing.Annotated[str | None, _Default(val=None), typing.Literal[<PropQuals.HAS_DEFAULT: 'HAS_DEFAULT'>]]
    """)
