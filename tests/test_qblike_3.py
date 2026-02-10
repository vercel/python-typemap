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
from typemap_extensions import (
    Attrs,
    Bool,
    Length,
    GetArg,
    GetMemberType,
    GetName,
    GetSpecialAttr,
    GetType,
    GetInit,
    InitField,
    IsAssignable,
    Iter,
    IsEquivalent,
    Member,
    NewProtocol,
    Slice,
)

from . import format_helper


"""
An example of a SQL-Alchemy like ORM.

The User, Post, and Comment classes model a SQLite schema:
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

Users can query using the `select` function, which generates a `Query` object
with the specified tables and fields.

Users can then execute the query using `Session.execute`, which returns a
list of `QueryRow` objects.

If a single table is selected, the `QueryRow` object will contain the selected
fields.

For example, `select(User)` will return a list of:

    class Select[User, tuple[...]]:
        id: int
        name: str
        email: str
        age: int | None
        active: bool
        posts: list[Post]

If multiple tables are selected, the `QueryRow` object will contain a field for
each table, which in turn contains the selected fields.

For example, `select(User.name, Post.content)` will return a list of:

    class QueryRow[...]:
        User: Select[User, tuple[...]]]:
        Post: Select[Post, tuple[...]]]:

    where,

    class Select[User, tuple[...]]:
        name: str

    class Select[Post, tuple[...]]:
        content: str
"""


# Type Helpers


type ReplaceNever[T, D] = T if not IsAssignable[T, Never] else D
type GetInitFieldItem[T: InitField, K, Default] = ReplaceNever[
    GetMemberType[GetArg[T, InitField, Literal[0]], K], Default
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


type DbType = DbBoolean | DbInteger | DbString | DbLinkTarget | DbLinkSource


class Table[name: str]:
    pass


class Field[PyType, Table, Name]:
    def __lt__(self, other: Any) -> Filter[Table]: ...


type FieldPyType[T] = GetArg[T, Field, Literal[0]]
type FieldTable[T] = GetArg[T, Field, Literal[1]]
type FieldName[T] = GetArg[T, Field, Literal[2]]


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
type ColumnInitHasDefault[Init] = not IsAssignable[
    GetInitFieldItem[Init, Literal["default"], Never], Never
]

type ReadValueNeverNull[M] = (
    not Bool[ColumnInitIsNullable[GetInit[M]]]
    or Bool[ColumnInitIsAutoincrement[GetInit[M]]]
    or (
        IsAssignable[FieldPyType[GetType[M]], list]
        and IsAssignable[
            GetArg[FieldPyType[GetType[M]], list, Literal[0]], Table
        ]
    )
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


type QueryEntry[T: Table, FieldNames: tuple[Literal[str], ...]] = tuple[
    T, FieldNames
]
type EntryTable[E: QueryEntry] = GetArg[E, tuple, Literal[0]]
type EntryFields[E: QueryEntry] = GetArg[E, tuple, Literal[1]]

type EntryFieldMembers[T: Table, FieldNames: tuple[Literal[str], ...]] = tuple[
    *[
        m
        for m in Iter[Attrs[T]]
        if any(IsAssignable[GetName[m], f] for f in Iter[FieldNames])
    ]
]

type EntryIsTable[E: QueryEntry, T: Table] = IsEquivalent[EntryTable[E], T]
type EntriesHasTable[Es: tuple[QueryEntry, ...], T: Table] = any(
    Bool[EntryIsTable[e, T]] for e in Iter[Es]
)

type MakeQueryEntryAllFields[T: Table] = QueryEntry[
    T,
    tuple[
        *[
            GetName[m]
            for m in Iter[Attrs[T]]
            if IsAssignable[GetType[m], Field]
        ],
    ],
]
type MakeQueryEntryNamedFields[
    T: Table,
    FieldNames: tuple[Literal[str], ...],
] = QueryEntry[
    T,
    tuple[
        *[
            GetName[m]
            for m in Iter[Attrs[T]]
            if IsAssignable[GetType[m], Field]
            and any(
                IsAssignable[FieldName[GetType[m]], f] for f in Iter[FieldNames]
            )
        ],
    ],
]

type AddTable[Entries, New: Table] = tuple[
    *[  # Existing entries
        (e if not Bool[EntryIsTable[e, New]] else MakeQueryEntryAllFields[New])
        for e in Iter[Entries]
    ],
    *(  # Add entries if not present
        []
        if Bool[EntriesHasTable[Entries, New]]
        else [MakeQueryEntryAllFields[New]]
    ),
]
type AddField[Entries, New: Field] = tuple[
    *[  # Existing entries
        (
            e  # Non-matching entry
            if not Bool[EntryIsTable[e, FieldTable[New]]]
            else MakeQueryEntryNamedFields[
                EntryTable[e],
                tuple[*[f for f in Iter[EntryFields[e]]], FieldName[New]],
            ]
        )
        for e in Iter[Entries]
    ],
    *(  # Add entries if not present
        e
        for e in Iter[tuple[QueryEntry[FieldTable[New], tuple[FieldName[New]]]]]
        if not Bool[EntriesHasTable[Entries, FieldTable[New]]]
    ),
]
type AddEntries[Entries, News: tuple[Table | Field, ...]] = (
    Entries
    if IsAssignable[Length[News], Literal[0]]
    else AddEntries[
        (
            AddTable[Entries, GetArg[News, tuple, Literal[0]]]
            if IsAssignable[GetArg[News, tuple, Literal[0]], Table]
            else AddField[Entries, GetArg[News, tuple, Literal[0]]]
        ),
        Slice[News, Literal[1], Literal[None]],
    ]
)
type UniqueEntries[Entries] = AddEntries[tuple[()], Entries]


def select[*Es](*entity: Unpack[Es]) -> Query[UniqueEntries[Es]]: ...


class Query[Es: tuple[QueryEntry[Table, tuple[Member]], ...]]:
    pass


type Select[T: Table, FieldNames: tuple[Literal[str], ...]] = NewProtocol[
    *[
        Member[
            GetName[m],
            (
                FieldPyType[GetType[m]]
                if Bool[ReadValueNeverNull[m]]
                else FieldPyType[GetType[m]] | None
            ),
        ]
        for m in Iter[EntryFieldMembers[T, FieldNames]]
    ],
]


type QueryRow[Es: tuple[QueryEntry[Table, tuple[Member]], ...]] = (
    Select[
        EntryTable[GetArg[Es, tuple, Literal[0]]],
        EntryFields[GetArg[Es, tuple, Literal[0]]],
    ]
    if IsAssignable[Literal[1], Length[Es]]
    else NewProtocol[
        *[
            Member[
                GetSpecialAttr[EntryTable[e], Literal["__name__"]],
                Select[EntryTable[e], EntryFields[e]],
            ]
            for e in Iter[Es]
        ]
    ]
)


class Session:
    def execute[Es: tuple[type[Table], ...]](
        self, query: Query[Es]
    ) -> list[QueryRow[Es]]: ...


# Application Types


class User(Table[Literal["users"]]):
    id: Field[int, User, Literal["id"]] = column(
        db_type=DbInteger(), primary_key=True, autoincrement=True
    )
    name: Field[str, User, Literal["name"]] = column(
        db_type=DbString(length=150), nullable=False
    )
    email: Field[str, User, Literal["email"]] = column(
        db_type=DbString(length=100), unique=True, nullable=False
    )
    age: Field[int | None, User, Literal["age"]] = column(db_type=DbInteger())
    active: Field[bool, User, Literal["active"]] = column(
        db_type=DbBoolean(), default=True, nullable=False
    )
    posts: Field[list[Post], User, Literal["posts"]] = column(
        db_type=DbLinkSource(source="Post", cardinality=Cardinality.MANY)
    )


class Post(Table[Literal["posts"]]):
    id: Field[int, Post, Literal["id"]] = column(
        db_type=DbInteger(), primary_key=True, autoincrement=True
    )
    content: Field[str, Post, Literal["content"]] = column(
        db_type=DbString(length=1000), nullable=False
    )
    author: Field[User, Post, Literal["author"]] = column(
        db_type=DbLinkTarget(target=User), nullable=False
    )
    comments: Field[list[Comment], Post, Literal["comments"]] = column(
        db_type=DbLinkSource(source="Comment", cardinality=Cardinality.MANY)
    )


class Comment(Table[Literal["comments"]]):
    id: Field[int, Comment, Literal["id"]] = column(
        db_type=DbInteger(), primary_key=True, autoincrement=True
    )
    content: Field[str, Comment, Literal["content"]] = column(
        db_type=DbString(length=1000), nullable=False
    )
    author: Field[User, Comment, Literal["author"]] = column(
        db_type=DbLinkTarget(target=User), nullable=False
    )
    post: Field[Post, Comment, Literal["post"]] = column(
        db_type=DbLinkTarget(target=Post), nullable=False
    )


# Tests


type AttrNames[T] = tuple[*[GetName[f] for f in Iter[Attrs[T]]]]


def test_qblike_3_select_01():
    # select(User)
    query = eval_call_with_types(select, User)

    fmt = format_helper.format_class(query)
    assert fmt == textwrap.dedent("""\
        class Query[tuple[tuple[tests.test_qblike_3.User, tuple[typing.Literal['id'], typing.Literal['name'], typing.Literal['email'], typing.Literal['age'], typing.Literal['active'], typing.Literal['posts']]]]]:
    """)

    results = eval_call_with_types(Session.execute, Session, query)
    result = eval_typing(GetArg[results, list, Literal[0]])

    fmt = format_helper.format_class(result)
    assert fmt == textwrap.dedent("""\
        class Select[tests.test_qblike_3.User, tuple[typing.Literal['id'], typing.Literal['name'], typing.Literal['email'], typing.Literal['age'], typing.Literal['active'], typing.Literal['posts']]]:
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
        class Query[tuple[tuple[tests.test_qblike_3.User, tuple[typing.Literal['id'], typing.Literal['name'], typing.Literal['email'], typing.Literal['age'], typing.Literal['active'], typing.Literal['posts']]]]]:
    """)

    results = eval_call_with_types(Session.execute, Session, query)
    result = eval_typing(GetArg[results, list, Literal[0]])

    fmt = format_helper.format_class(result)
    assert fmt == textwrap.dedent("""\
        class Select[tests.test_qblike_3.User, tuple[typing.Literal['id'], typing.Literal['name'], typing.Literal['email'], typing.Literal['age'], typing.Literal['active'], typing.Literal['posts']]]:
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
        class Query[tuple[tuple[tests.test_qblike_3.User, tuple[typing.Literal['id'], typing.Literal['name'], typing.Literal['email'], typing.Literal['age'], typing.Literal['active'], typing.Literal['posts']]], tuple[tests.test_qblike_3.Post, tuple[typing.Literal['id'], typing.Literal['content'], typing.Literal['author'], typing.Literal['comments']]]]]:
    """)

    results = eval_call_with_types(Session.execute, Session, query)
    result = eval_typing(GetArg[results, list, Literal[0]])

    result_names = eval_typing(AttrNames[result])
    assert result_names == tuple[Literal["User"], Literal["Post"]]

    result_user = eval_typing(GetMemberType[result, Literal["User"]])
    fmt = format_helper.format_class(result_user)
    assert fmt == textwrap.dedent("""\
        class Select[tests.test_qblike_3.User, tuple[typing.Literal['id'], typing.Literal['name'], typing.Literal['email'], typing.Literal['age'], typing.Literal['active'], typing.Literal['posts']]]:
            id: int
            name: str
            email: str
            age: int | None
            active: bool
            posts: list[tests.test_qblike_3.Post]
    """)

    result_post = eval_typing(GetMemberType[result, Literal["Post"]])
    fmt = format_helper.format_class(result_post)
    assert fmt == textwrap.dedent("""\
        class Select[tests.test_qblike_3.Post, tuple[typing.Literal['id'], typing.Literal['content'], typing.Literal['author'], typing.Literal['comments']]]:
            id: int
            content: str
            author: tests.test_qblike_3.User
            comments: list[tests.test_qblike_3.Comment]
    """)


def test_qblike_3_select_04():
    # select(User.name)
    user_name = eval_typing(GetMemberType[User, Literal["name"]])
    query = eval_call_with_types(select, user_name)

    fmt = format_helper.format_class(query)
    assert fmt == textwrap.dedent("""\
        class Query[tuple[tuple[tests.test_qblike_3.User, tuple[typing.Literal['name']]]]]:
    """)

    results = eval_call_with_types(Session.execute, Session, query)
    result = eval_typing(GetArg[results, list, Literal[0]])

    fmt = format_helper.format_class(result)
    assert fmt == textwrap.dedent("""\
        class Select[tests.test_qblike_3.User, tuple[typing.Literal['name']]]:
            name: str
    """)


def test_qblike_3_select_05():
    # select(User.name, User.name)
    user_name = eval_typing(GetMemberType[User, Literal["name"]])
    query = eval_call_with_types(select, user_name, user_name)

    fmt = format_helper.format_class(query)
    assert fmt == textwrap.dedent("""\
        class Query[tuple[tuple[tests.test_qblike_3.User, tuple[typing.Literal['name']]]]]:
    """)

    results = eval_call_with_types(Session.execute, Session, query)
    result = eval_typing(GetArg[results, list, Literal[0]])

    fmt = format_helper.format_class(result)
    assert fmt == textwrap.dedent("""\
        class Select[tests.test_qblike_3.User, tuple[typing.Literal['name']]]:
            name: str
    """)


def test_qblike_3_select_06():
    # select(User.name, User.email)
    user_name = eval_typing(GetMemberType[User, Literal["name"]])
    user_email = eval_typing(GetMemberType[User, Literal["email"]])
    query = eval_call_with_types(select, user_name, user_email)

    fmt = format_helper.format_class(query)
    assert fmt == textwrap.dedent("""\
        class Query[tuple[tuple[tests.test_qblike_3.User, tuple[typing.Literal['name'], typing.Literal['email']]]]]:
    """)

    results = eval_call_with_types(Session.execute, Session, query)
    result = eval_typing(GetArg[results, list, Literal[0]])

    fmt = format_helper.format_class(result)
    assert fmt == textwrap.dedent("""\
        class Select[tests.test_qblike_3.User, tuple[typing.Literal['name'], typing.Literal['email']]]:
            name: str
            email: str
    """)


def test_qblike_3_select_07():
    # select(User.name, Post.content)
    user_name = eval_typing(GetMemberType[User, Literal["name"]])
    post_content = eval_typing(GetMemberType[Post, Literal["content"]])
    query = eval_call_with_types(select, user_name, post_content)

    fmt = format_helper.format_class(query)
    assert fmt == textwrap.dedent("""\
        class Query[tuple[tuple[tests.test_qblike_3.User, tuple[typing.Literal['name']]], tuple[tests.test_qblike_3.Post, tuple[typing.Literal['content']]]]]:
    """)

    results = eval_call_with_types(Session.execute, Session, query)
    result = eval_typing(GetArg[results, list, Literal[0]])

    result_names = eval_typing(AttrNames[result])
    assert result_names == tuple[Literal["User"], Literal["Post"]]

    result_user = eval_typing(GetMemberType[result, Literal["User"]])
    fmt = format_helper.format_class(result_user)
    assert fmt == textwrap.dedent("""\
        class Select[tests.test_qblike_3.User, tuple[typing.Literal['name']]]:
            name: str
    """)

    result_post = eval_typing(GetMemberType[result, Literal["Post"]])
    fmt = format_helper.format_class(result_post)
    assert fmt == textwrap.dedent("""\
        class Select[tests.test_qblike_3.Post, tuple[typing.Literal['content']]]:
            content: str
    """)
