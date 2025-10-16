import textwrap
import typing
import unittest

from typemap import typing as next
from typemap.type_eval import eval_typing

from . import format_helper


type A[T] = T | None | typing.Literal[False]
type B = A[int]

type OrGotcha[K] = K | typing.Literal["gotcha!"]


class F[T]:
    fff: T


class F_int(F[int]):
    pass


type MapRecursive[A] = next.NewProtocol[
    *[
        (
            next.Member[next.GetName[p], OrGotcha[next.GetType[p]]]
            if not next.Is[next.GetType[p], A]
            else next.Member[next.GetName[p], OrGotcha[MapRecursive[A]]]
        )
        # XXX: type language - concatenating DirProperties is sketchy
        for p in (next.Attrs[A] + next.Attrs[F_int])
    ],
    next.Member[typing.Literal["control"], float],
]


class Recursive:
    n: int
    m: str
    t: typing.Literal[False]
    a: Recursive


def test_eval_types_1():
    assert str(eval_typing(B)) == "int | None | typing.Literal[False]"


def test_eval_types_2():
    evaled = eval_typing(MapRecursive[Recursive])

    # Validate that recursion worked properly and "Recursive" was only walked once
    assert evaled.__annotations__["a"].__args__[0] is evaled

    assert format_helper.format_class(evaled) == textwrap.dedent("""\
        class MapRecursive[tests.test_type_eval.Recursive]:
            n: int | typing.Literal['gotcha!']
            m: str | typing.Literal['gotcha!']
            t: typing.Literal[False] | typing.Literal['gotcha!']
            a: tests.test_type_eval.MapRecursive[tests.test_type_eval.Recursive] | typing.Literal['gotcha!']
            fff: int | typing.Literal['gotcha!']
            control: float
        """)


# XXX: should this work???
# probably not?
@unittest.skip
def test_eval_types_3():
    evaled = eval_typing(F[bool])

    assert format_helper.format_class(evaled) == textwrap.dedent("""\
        class F[bool]:
            fff: bool
        """)
