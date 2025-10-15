import textwrap
import typing

from typemap.type_eval import eval_call, eval_typing
from typemap import typing as next

from . import format_helper


class Property[T]:
    pass


class Link[T]:
    pass


# XXX: We need to be able to check against _GenericAlias for our qb
# stuff, but this can't be how we do it.
def _is_alias_of(typ, cls):
    return isinstance(typ, typing._GenericAlias) and issubclass(
        typ.__origin__, cls
    )


type PropsOnly[T] = next.NewProtocol[
    [
        next.Property[p.name, p.type]
        for p in next.DirProperties[T]
        # XXX: type language -- _is_alias_of
        if _is_alias_of(p.type, Property)
    ]
]

# XXX: How do we feel about a pure conditional type alias???
# We could inline it if needed
type FilterLinks[T] = (
    # XXX: type language -- _is_alias_of and __args__
    Link[PropsOnly[T.__args__[0]]] if _is_alias_of(T, Link) else T
)


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


def select[C: next.CallSpec](
    __rcv: A, *args: C.args, **kwargs: C.kwargs
) -> next.NewProtocol[
    [
        next.Property[
            c.name,
            FilterLinks[next.GetAttr[A, c.name]],
        ]
        for c in next.CallSpecKwargs[C]
    ]
]: ...


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
            z: tests.test_qblike.Link[PropsOnly[tests.test_qblike.Tgt]]
        """)

    tgt = eval_typing(next.GetAttr[ret, "z"].__args__[0])
    fmt = format_helper.format_class(tgt)

    assert fmt == textwrap.dedent("""\
        class PropsOnly[tests.test_qblike.Tgt]:
            name: tests.test_qblike.Property[str]
    """)
