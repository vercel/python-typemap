import dataclasses
import enum
import textwrap

from typing import (
    Callable,
    ForwardRef,
    Literal,
    Never,
    ReadOnly,
    Self,
    TypedDict,
)

from typemap.type_eval import eval_typing
from typemap.typing import (
    Attrs,
    GetArg,
    GetAttr,
    GetName,
    GetQuals,
    GetType,
    GetInit,
    InitField,
    Iter,
    Member,
    NewProtocol,
    Param,
    IsSub,
)

from . import format_helper


type ReplaceNever[T, D] = T if not IsSub[T, Never] else D
type GetFieldItem[T: InitField, K, Default] = ReplaceNever[
    GetAttr[GetArg[T, InitField, Literal[0]], K], Default
]


@dataclasses.dataclass(frozen=True)
class DbBoolean:
    pass


@dataclasses.dataclass(frozen=True)
class DbInteger:
    pass


@dataclasses.dataclass(frozen=True)
class DbString:
    length: int


type DbType = DbInteger | DbString


class Table[name: str]:
    pass


class FieldArgs(TypedDict, total=False):
    primary_key: ReadOnly[bool]
    db_type: ReadOnly[DbType]
    nullable: ReadOnly[bool]
    unique: ReadOnly[bool]
    autoincrement: ReadOnly[bool] = False
    default: ReadOnly[object]


class Field[Args: FieldArgs](InitField[Args]):
    pass


type FieldIsNullable[Init] = GetFieldItem[
    Init, Literal["nullable"], Literal[True]
]
type FieldIsAutoincrement[Init] = GetFieldItem[
    Init, Literal["autoincrement"], Literal[False]
]
type FieldHasDefault[Init] = (
    Literal[True]
    if not IsSub[GetFieldItem[Init, Literal["default"], Never], Never]
    else Literal[False]
)


type FieldIsRequiredForCreate[Init] = (
    Literal[True]
    if not IsSub[Literal[True], FieldIsNullable[Init]]
    and not IsSub[Literal[True], FieldIsAutoincrement[Init]]
    and not IsSub[Literal[True], FieldHasDefault[Init]]
    else Literal[False]
)
type FieldIsDefaultNone[Init] = (
    Literal[True]
    if IsSub[Literal[True], FieldIsNullable[Init]]
    and not IsSub[Literal[True], FieldIsAutoincrement[Init]]
    and IsSub[GetFieldItem[Init, Literal["default"], None], None]
    else Literal[False]
)


class Cardinality(enum.Enum):
    ONE = "ONE"
    MANY = "MANY"


class DbLinkTargetArgs(TypedDict, total=False):
    target: ReadOnly[type[Table] | ForwardRef]
    cardinality: ReadOnly[Cardinality] = Cardinality.ONE


class DbLinkTarget[Args: DbLinkTargetArgs](InitField[Args]):
    pass


class DbLinkSourceArgs(TypedDict, total=False):
    source: ReadOnly[type[Table] | ForwardRef]
    cardinality: ReadOnly[Cardinality] = Cardinality.ONE


class DbLinkSource[Args: DbLinkSourceArgs](InitField[Args]):
    pass


class Default:
    pass


type InitFnType[T] = Member[
    Literal["__init__"],
    Callable[
        [
            Param[Literal["self"], Self],
            *[
                Param[
                    GetName[p],
                    (
                        GetType[p]
                        if IsSub[
                            Literal[True], FieldIsRequiredForCreate[GetInit[p]]
                        ]
                        else GetType[p] | None
                        if IsSub[Literal[True], FieldIsDefaultNone[GetInit[p]]]
                        else GetType[p] | Default
                    ),
                    (
                        Literal["keyword"]
                        if IsSub[
                            Literal[True], FieldIsRequiredForCreate[GetInit[p]]
                        ]
                        else Literal["keyword", "default"]
                    ),
                ]
                for p in Iter[Attrs[T]]
                if not IsSub[
                    GetFieldItem[GetInit[p], Literal["db_type"], Never],
                    DbLinkSource,
                ]
            ],
        ],
        None,
    ],
    Literal["ClassVar"],
]
type AddInit[T] = NewProtocol[
    InitFnType[T],
    *[Member[GetName[p], GetType[p], GetQuals[p]] for p in Iter[Attrs[T]]],
]


class NoChange:
    pass


type Create[T] = NewProtocol[
    *[
        Member[
            GetName[p],
            (
                GetType[p]
                if IsSub[
                    Literal[True],
                    FieldIsRequiredForCreate[GetInit[p]],
                ]
                else GetType[p] | None
                if IsSub[
                    Literal[True],
                    FieldIsDefaultNone[GetInit[p]],
                ]
                else GetType[p] | Default
            ),
            GetQuals[p],
        ]
        for p in Iter[Attrs[T]]
        if not IsSub[
            Literal[True],
            GetFieldItem[GetInit[p], Literal["primary_key"], Never],
        ]
        and not IsSub[
            GetFieldItem[GetInit[p], Literal["db_type"], Never], DbLinkSource
        ]
    ],
]
type Update[T] = NewProtocol[
    *[
        Member[GetName[p], GetType[p] | NoChange, GetQuals[p]]
        for p in Iter[Attrs[T]]
        if not IsSub[
            Literal[True],
            GetFieldItem[GetInit[p], Literal["primary_key"], Never],
        ]
        and not IsSub[
            GetFieldItem[GetInit[p], Literal["db_type"], Never], DbLinkSource
        ]
    ],
]


class User(Table[Literal["users"]]):
    id: int = Field(db_type=DbInteger(), primary_key=True, autoincrement=True)
    name: str = Field(db_type=DbString(length=50), nullable=False)
    email: str = Field(
        db_type=DbString(length=100), unique=True, nullable=False
    )
    age: int | None = Field(db_type=DbInteger())
    active: bool = Field(db_type=DbBoolean(), default=True)
    posts: list[Post] = Field(
        db_type=DbLinkSource(
            source=ForwardRef("Post"), cardinality=Cardinality.MANY
        )
    )


class Post(Table[Literal["posts"]]):
    id: int = Field(db_type=DbInteger(), primary_key=True, autoincrement=True)
    content: str = Field(db_type=DbString(length=1000), nullable=False)
    author: User = Field(
        db_type=DbLinkTarget(target=ForwardRef("User")), nullable=False
    )


def test_qblike_3_add_init_01():
    tgt = eval_typing(AddInit[User])
    fmt = format_helper.format_class(tgt)

    assert fmt == textwrap.dedent("""\
        class AddInit[tests.test_qblike_3.User]:
            id: int
            name: str
            email: str
            age: int | None
            active: bool
            posts: list[tests.test_qblike_3.Post]
            def __init__(self: Self, *, id: int | tests.test_qblike_3.Default = ..., name: str, email: str, age: int | None = ..., active: bool | tests.test_qblike_3.Default = ...) -> None: ...
    """)


def test_qblike_3_add_init_02():
    tgt = eval_typing(AddInit[Post])
    fmt = format_helper.format_class(tgt)

    assert fmt == textwrap.dedent("""\
        class AddInit[tests.test_qblike_3.Post]:
            id: int
            content: str
            author: tests.test_qblike_3.User
            def __init__(self: Self, *, id: int | tests.test_qblike_3.Default = ..., content: str, author: tests.test_qblike_3.User) -> None: ...
    """)


def test_qblike_3_create_01():
    tgt = eval_typing(Create[User])
    fmt = format_helper.format_class(tgt)

    assert fmt == textwrap.dedent("""\
        class Create[tests.test_qblike_3.User]:
            name: str
            email: str
            age: int | None
            active: bool | tests.test_qblike_3.Default
    """)


def test_qblike_3_create_02():
    tgt = eval_typing(Create[Post])
    fmt = format_helper.format_class(tgt)

    assert fmt == textwrap.dedent("""\
        class Create[tests.test_qblike_3.Post]:
            content: str
            author: tests.test_qblike_3.User
    """)


def test_qblike_3_update_01():
    tgt = eval_typing(Update[User])
    fmt = format_helper.format_class(tgt)

    assert fmt == textwrap.dedent("""\
        class Update[tests.test_qblike_3.User]:
            name: str | tests.test_qblike_3.NoChange
            email: str | tests.test_qblike_3.NoChange
            age: int | None | tests.test_qblike_3.NoChange
            active: bool | tests.test_qblike_3.NoChange
    """)


def test_qblike_3_update_02():
    tgt = eval_typing(Update[Post])
    fmt = format_helper.format_class(tgt)

    assert fmt == textwrap.dedent("""\
        class Update[tests.test_qblike_3.Post]:
            content: str | tests.test_qblike_3.NoChange
            author: tests.test_qblike_3.User | tests.test_qblike_3.NoChange
    """)
