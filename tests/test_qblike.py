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


type PropsOnly[T] = NewProtocol[
    *[p for p in Iter[Attrs[T]] if Sub[GetType[p], Property]]
]

# Conditional type alias!
type FilterLinks[T] = Link[PropsOnly[GetArg[T, Link, 0]]] if Sub[T, Link] else T


def select[K: BaseTypedDict](
    rcv: A,
    /,
    **kwargs: Unpack[K],
) -> NewProtocol[
    *[
        Member[
            GetName[c],
            FilterLinks[GetAttr[A, GetName[c]]],
        ]
        for c in Iter[Attrs[K]]
    ]
]: ...


# Basic filtering
class Tgt2:
    pass


class Tgt:
    name: Property[str]
    tgt2: Link[Tgt2]


class A:
    x: Property[int]
    y: Property[bool | None]
    z: Link[Tgt]
    w: Property[list[str]]


def test_qblike_1():
    ret = eval_call(
        select,
        A(),
        x=True,
        w=True,
    )
    fmt = format_helper.format_class(ret)

    assert fmt == textwrap.dedent("""\
        class select[...]:
            x: tests.test_qblike.Property[int]
            w: tests.test_qblike.Property[list[str]]
        """)


def test_qblike_2():
    ret = eval_typing(PropsOnly[A])
    fmt = format_helper.format_class(ret)

    assert fmt == textwrap.dedent("""\
        class PropsOnly[tests.test_qblike.A]:
            x: tests.test_qblike.Property[int]
            y: tests.test_qblike.Property[bool | None]
            w: tests.test_qblike.Property[list[str]]
        """)


def test_qblike_3():
    ret = eval_call(
        select,
        A(),
        x=True,
        w=True,
        z=True,
    )
    fmt = format_helper.format_class(ret)

    assert fmt == textwrap.dedent("""\
        class select[...]:
            x: tests.test_qblike.Property[int]
            w: tests.test_qblike.Property[list[str]]
            z: tests.test_qblike.Link[tests.test_qblike.PropsOnly[tests.test_qblike.Tgt]]
        """)

    res = eval_typing(GetAttr[ret, Literal["z"]])
    tgt = res.__args__[0]
    # XXX: this should probably be pre-evaluated already?
    tgt = eval_typing(tgt)
    fmt = format_helper.format_class(tgt)

    assert fmt == textwrap.dedent("""\
        class PropsOnly[tests.test_qblike.Tgt]:
            name: tests.test_qblike.Property[str]
    """)
