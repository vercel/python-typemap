import textwrap

from typing import Literal, Unpack

from typemap.type_eval import eval_call, eval_typing
from typemap.typing import (
    BaseTypedDict,
    NewProtocol,
    Iter,
    Attrs,
    IsSub,
    GetType,
    Member,
    GetName,
    GetAttr,
    GetArg,
)

from . import format_helper


# Begin PEP section: Prisma-style ORMs

"""First, to support the annotations we saw above, we have a collection
of dummy classes with generic types.
"""


class Pointer[T]:
    pass


class Property[T](Pointer[T]):
    pass


class Link[T](Pointer[T]):
    pass


class SingleLink[T](Link[T]):
    pass


class MultiLink[T](Link[T]):
    pass


"""
The ``select`` method is where we start seeing new things.

The ``**kwargs: Unpack[K]`` is part of this proposal, and allows
*inferring* a TypedDict from keyword args.

``Attrs[K]`` extracts ``Member`` types corresponding to every
type-annotated attribute of ``K``, while calling ``NewProtocol`` with
``Member`` arguments constructs a new structural type.

``GetName`` is a getter operator that fetches the name of a ``Member``
as a literal type--all of these mechanisms lean very heavily on literal types.
``GetAttr`` gets the type of an attribute from a class.

"""


def select[ModelT, K: BaseTypedDict](
    typ: type[ModelT],
    /,
    **kwargs: Unpack[K],
) -> list[
    NewProtocol[
        *[
            Member[
                GetName[c],
                ConvertField[GetAttr[ModelT, GetName[c]]],
            ]
            for c in Iter[Attrs[K]]
        ]
    ]
]: ...


"""ConvertField is our first type helper, and it is a conditional type
alias, which decides between two types based on a (limited)
subtype-ish check.

In ``ConvertField``, we wish to drop the ``Property`` or ``Link``
annotation and produce the underlying type, as well as, for links,
producing a new target type containing only properties and wrapping
``MultiLink`` in a list.
"""

type ConvertField[T] = (
    AdjustLink[PropsOnly[PointerArg[T]], T] if IsSub[T, Link] else PointerArg[T]
)

"""``PointerArg`` gets the type argument to ``Pointer`` or a subclass.

``GetArg[T, Base, I]`` is one of the core primitives; it fetches the
index ``I`` type argument to ``Base`` from a type ``T``, if ``T``
inherits from ``Base``.

(The subtleties of this will be discussed later; in this case, it just
grabs the argument to a ``Pointer``).

"""
type PointerArg[T: Pointer] = GetArg[T, Pointer, Literal[0]]

"""
``AdjustLink`` sticks a ``list`` around ``MultiLink``, using features
we've discussed already.

"""
type AdjustLink[Tgt, LinkTy] = list[Tgt] if IsSub[LinkTy, MultiLink] else Tgt

"""And the final helper, ``PropsOnly[T]``, generates a new type that
contains all the ``Property`` attributes of ``T``.

"""
type PropsOnly[T] = list[
    NewProtocol[
        *[
            Member[GetName[p], PointerArg[GetType[p]]]
            for p in Iter[Attrs[T]]
            if IsSub[GetType[p], Property]
        ]
    ]
]

"""
The full test is `in our test suite <#qb-test_>`_.
"""


# End PEP section


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


def test_qblike2_1():
    ret = eval_call(
        select,
        User,
        id=True,
        name=True,
    )
    assert ret.__origin__ is list
    ret = ret.__args__[0]
    fmt = format_helper.format_class(ret)

    assert fmt == textwrap.dedent("""\
        class select[...]:
            id: int
            name: str
        """)


def test_qblike2_2():
    ret = eval_call(
        select,
        User,
        name=True,
        email=True,
        posts=True,
    )

    assert ret.__origin__ is list
    ret = ret.__args__[0]
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
