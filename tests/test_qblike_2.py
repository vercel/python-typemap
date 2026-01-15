import textwrap

from typing import Literal, Unpack

from typemap.type_eval import eval_call, eval_typing
from typemap.typing import (
    BaseTypedDict,
    NewProtocol,
    Iter,
    Attrs,
    Sub,
    GetType,
    Member,
    GetName,
    GetAttr,
    GetArg,
)

from . import format_helper


class Property[T]:
    pass


class Link[T]:
    pass


class SingleLink[T](Link[T]):
    pass


class MultiLink[T](Link[T]):
    pass


type DropProp[T] = GetArg[T, Property, 0]

type PropsOnly[T] = list[
    NewProtocol[
        *[
            Member[GetName[p], DropProp[GetType[p]]]
            for p in Iter[Attrs[T]]
            if Sub[GetType[p], Property]
        ]
    ]
]

type AdjustLink[Tgt, LinkTy] = list[Tgt] if Sub[LinkTy, MultiLink] else Tgt

# Conditional type alias!
type ConvertField[T] = (
    AdjustLink[PropsOnly[GetArg[T, Link, 0]], T]
    if Sub[T, Link]
    else DropProp[T]
)

# XXX: putting list here doesn't work!
def select[K: BaseTypedDict](
    rcv: type[User],
    /,
    **kwargs: Unpack[K],
) -> NewProtocol[
    *[
        Member[
            GetName[c],
            ConvertField[GetAttr[User, GetName[c]]],
        ]
        for c in Iter[Attrs[K]]
    ]
]: ...


# Basic filtering
class Comment:
    id: Property[int]
    name: Property[str]
    poster: Link[User]


class Post:
    id: Property[int]

    title: Property[str]
    content: Property[str]

    comments: MultiLink[Comment]
    author: Link[Comment]


class User:
    id: Property[int]

    name: Property[str]
    email: Property[str]
    posts: Link[Post]


def test_qblike_1():
    ret = eval_call(
        select,
        User,
        id=True,
        name=True,
    )
    fmt = format_helper.format_class(ret)

    assert fmt == textwrap.dedent("""\
        class select[...]:
            id: int
            name: str
        """)


def test_qblike_2():
    ret = eval_call(
        select,
        User,
        name=True,
        email=True,
        posts=True,
    )

    # ret = ret.__args__[0]
    fmt = format_helper.format_class(ret)

    assert fmt == textwrap.dedent("""\
        class select[...]:
            name: str
            email: str
            posts: list[tests.test_qblike_2.PropsOnly[tests.test_qblike_2.Post]]
        """)

    res = eval_typing(GetAttr[ret, Literal["posts"]])
    tgt = res.__args__[0]
    # XXX: this should probably be pre-evaluated already?
    fmt = format_helper.format_class(tgt)

    assert fmt == textwrap.dedent("""\
        class PropsOnly[tests.test_qblike_2.Post]:
            id: int
            title: str
            content: str
    """)
