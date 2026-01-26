import dataclasses
import enum
import textwrap

from typing import (
    Any,
    ForwardRef,
    Literal,
    Never,
    ReadOnly,
    TypedDict,
    Unpack,
)

from typemap.type_eval import eval_call_with_types, eval_typing
from typemap.typing import (
    Attrs,
    Length,
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
    IsSub,
)

from . import format_helper


"""
An example of a SQL-Alchemy like ORM.

The User and Post classes model a SQLite schema:
```
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    age INTEGER,
    active BOOLEAN DEFAULT TRUE
);

CREATE TABLE posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    author_id INTEGER NOT NULL,
    FOREIGN KEY (author_id) REFERENCES users (id)
);

CREATE TABLE comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    author_id INTEGER NOT NULL,
    post_id INTEGER NOT NULL,
    FOREIGN KEY (author_id) REFERENCES users (id),
    FOREIGN KEY (post_id) REFERENCES posts (id)
);
```

Protocols are generated using AddInit[T], Create[T], and Update[T].
"""


# Type Helpers


type ReplaceNever[T, D] = T if not IsSub[T, Never] else D
type GetInitFieldItem[T: InitField, K, Default] = ReplaceNever[
    GetAttr[GetArg[T, InitField, Literal[0]], K], Default
]


# Database Types


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


class Field[Table, PyType]:
    def __lt__(self, other: Any) -> Filter[Table]: ...


type FieldTable[T] = GetArg[GetType[T], Field, Literal[0]]
type FieldPyType[T] = GetArg[GetType[T], Field, Literal[1]]


class ColumnArgs(TypedDict, total=False):
    primary_key: ReadOnly[bool]
    db_type: ReadOnly[DbType]
    nullable: ReadOnly[bool]
    unique: ReadOnly[bool]
    autoincrement: ReadOnly[bool] = False
    default: ReadOnly[object]


class column[Args: ColumnArgs](InitField[Args]):
    pass


type ColumnInitIsNullable[Init] = GetInitFieldItem[
    Init, Literal["nullable"], Literal[True]
]
type ColumnInitIsAutoincrement[Init] = GetInitFieldItem[
    Init, Literal["autoincrement"], Literal[False]
]
type ColumnInitHasDefault[Init] = (
    Literal[True]
    if not IsSub[GetInitFieldItem[Init, Literal["default"], Never], Never]
    else Literal[False]
)

type FieldValueNeverNull[F, C] = (
    Literal[True]
    if not IsSub[Literal[True], ColumnInitIsNullable[C]]
    or IsSub[Literal[True], ColumnInitIsAutoincrement[C]]
    or (
        IsSub[FieldPyType[F], list]
        and IsSub[GetArg[FieldPyType[F], list, Literal[0]], Table]
    )
    else Literal[False]
)


class Filter[T: Table]:
    pass


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


# Query Types


type Select[T] = NewProtocol[
    *[
        Member[
            GetName[p],
            (
                FieldPyType[p]
                if IsSub[
                    Literal[True],
                    FieldValueNeverNull[GetType[p], GetInit[p]],
                ]
                else FieldPyType[p] | None
            ),
            GetQuals[p],
        ]
        for p in Iter[Attrs[T]]
    ],
]


type AddTable[Tables, New] = (
    Tables
    if any(IsSub[t, New] and IsSub[New, t] for t in Iter[Tables])
    else tuple[*[t for t in Iter[Tables]], New]
)
type AddTables[Tables, News] = (
    Tables
    if IsSub[Length[News], Literal[0]]
    else AddTables[
        AddTable[Tables, GetArg[News, tuple, Literal[0]]],
        tuple[*([n for n in Iter[News]][1:])],
    ]
)
type UniqueTables[Tables] = AddTables[tuple[()], Tables]


def select[*E](
    *entity: Unpack[E],
) -> Query[UniqueTables[tuple[*[e for e in Iter[E]]]]]: ...


class Query[E: tuple[type[Table], ...]]:
    pass


type QueryRow[E: tuple[type[Table], ...]] = (
    Select[GetArg[E, tuple, Literal[0]]]
    if IsSub[Literal[1], Length[E]]
    else NewProtocol[
        *[
            Member[
                Literal[e.__name__],
                Select[e],
            ]
            for e in Iter[E]
        ]
    ]
)


class Session:
    def execute[E: tuple[type[Table], ...]](
        self, query: Query[E]
    ) -> list[QueryRow[E]]: ...


# Application Types


class User(Table[Literal["users"]]):
    id: Field[User, int] = column(
        db_type=DbInteger(), primary_key=True, autoincrement=True
    )
    name: Field[User, str] = column(
        db_type=DbString(length=150), nullable=False
    )
    email: Field[User, str] = column(
        db_type=DbString(length=100), unique=True, nullable=False
    )
    age: Field[User, int | None] = column(db_type=DbInteger())
    active: Field[User, bool] = column(
        db_type=DbBoolean(), default=True, nullable=False
    )
    posts: Field[User, list[Post]] = column(
        db_type=DbLinkSource(source="Post", cardinality=Cardinality.MANY)
    )


class Post(Table[Literal["posts"]]):
    id: Field[Post, int] = column(
        db_type=DbInteger(), primary_key=True, autoincrement=True
    )
    content: Field[Post, str] = column(
        db_type=DbString(length=1000), nullable=False
    )
    author: Field[Post, User] = column(
        db_type=DbLinkTarget(target=User), nullable=False
    )
    comments: Field[Post, list[Comment]] = column(
        db_type=DbLinkSource(source="Comment", cardinality=Cardinality.MANY)
    )


class Comment(Table[Literal["comments"]]):
    id: Field[Comment, int] = column(
        db_type=DbInteger(), primary_key=True, autoincrement=True
    )
    content: Field[Comment, str] = column(
        db_type=DbString(length=1000), nullable=False
    )
    author: Field[Comment, User] = column(
        db_type=DbLinkTarget(target=User), nullable=False
    )
    post: Field[Comment, Post] = column(
        db_type=DbLinkTarget(target=Post), nullable=False
    )


# Tests


def test_qblike_3_select_01():
    # select(User)
    query = eval_call_with_types(select, User)
    fmt = format_helper.format_class(query)

    assert fmt == textwrap.dedent("""\
        class Query[tuple[tests.test_qblike_3.User]]:
    """)

    results = eval_call_with_types(Session.execute, Session, query)
    result = eval_typing(GetArg[results, list, Literal[0]])
    fmt = format_helper.format_class(result)
    assert fmt == textwrap.dedent("""\
        class Select[tests.test_qblike_3.User]:
            id: int
            name: str
            email: str
            age: int | None
            active: bool
            posts: list[tests.test_qblike_3.Post]
    """)


def test_qblike_3_select_02():
    # select(User, User)
    query = eval_call_with_types(select, User, User)
    fmt = format_helper.format_class(query)

    assert fmt == textwrap.dedent("""\
        class Query[tuple[tests.test_qblike_3.User]]:
    """)

    results = eval_call_with_types(Session.execute, Session, query)
    result = eval_typing(GetArg[results, list, Literal[0]])
    fmt = format_helper.format_class(result)
    assert fmt == textwrap.dedent("""\
        class Select[tests.test_qblike_3.User]:
            id: int
            name: str
            email: str
            age: int | None
            active: bool
            posts: list[tests.test_qblike_3.Post]
    """)


def test_qblike_3_select_03():
    # select(User, Post)
    query = eval_call_with_types(select, User, Post)
    fmt = format_helper.format_class(query)

    assert fmt == textwrap.dedent("""\
        class Query[tuple[tests.test_qblike_3.User, tests.test_qblike_3.Post]]:
    """)

    results = eval_call_with_types(Session.execute, Session, query)
    result = eval_typing(GetArg[results, list, Literal[0]])
    fmt = format_helper.format_class(result)
    assert fmt == textwrap.dedent("""\
        class QueryRow[tuple[tests.test_qblike_3.User, tests.test_qblike_3.Post]]:
            User: tests.test_qblike_3.Select[tests.test_qblike_3.User]
            Post: tests.test_qblike_3.Select[tests.test_qblike_3.Post]
    """)

    result_user = eval_typing(GetAttr[result, Literal["User"]])
    fmt = format_helper.format_class(result_user)
    assert fmt == textwrap.dedent("""\
        class Select[tests.test_qblike_3.User]:
            id: int
            name: str
            email: str
            age: int | None
            active: bool
            posts: list[tests.test_qblike_3.Post]
    """)

    result_post = eval_typing(GetAttr[result, Literal["Post"]])
    fmt = format_helper.format_class(result_post)
    assert fmt == textwrap.dedent("""\
        class Select[tests.test_qblike_3.Post]:
            id: int
            content: str
            author: tests.test_qblike_3.User
            comments: list[tests.test_qblike_3.Comment]
    """)
