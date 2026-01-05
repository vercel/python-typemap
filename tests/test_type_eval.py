import textwrap
import unittest
from typing import Literal, Never, Tuple

from typemap.type_eval import eval_typing
from typemap.typing import (
    Attrs,
    FromUnion,
    GetArg,
    GetAttr,
    GetName,
    GetType,
    Is,
    Iter,
    Length,
    Member,
    NewProtocol,
    StrConcat,
    StrSlice,
    Uppercase,
)

from . import format_helper

type A[T] = T | None | Literal[False]
type B = A[int]

type OrGotcha[K] = K | Literal["gotcha!"]


class F[T]:
    fff: T


class F_int(F[int]):
    pass


type ConcatTuples[A, B] = tuple[
    *[x for x in Iter[A]],
    *[x for x in Iter[B]],
]

type MapRecursive[A] = NewProtocol[
    *[
        (
            Member[GetName[p], OrGotcha[GetType[p]]]
            if not Is[GetType[p], A]
            else Member[GetName[p], OrGotcha[MapRecursive[A]]]
        )
        # XXX: This next line *ought* to work, but we haven't
        # implemented it yet.
        # for p in Iter[*Attrs[A], *Attrs[F_int]]
        for p in Iter[ConcatTuples[Attrs[A], Attrs[F_int]]]
    ],
    Member[Literal["control"], float],
]


class Recursive:
    n: int
    m: str
    t: Literal[False]
    a: Recursive


def test_eval_types_1():
    assert str(eval_typing(B)) == "int | None | typing.Literal[False]"


def test_eval_types_2():
    evaled = eval_typing(MapRecursive[Recursive])

    # FIXME, or think about: this doesn't work, we currently evaluate it to an
    # *unexpanded* type alias.
    # # Validate that recursion worked properly and "Recursive" was only walked once
    # assert evaled.__annotations__["a"].__args__[0] is evaled

    assert format_helper.format_class(evaled) == textwrap.dedent("""\
        class MapRecursive[tests.test_type_eval.Recursive]:
            n: int | typing.Literal['gotcha!']
            m: str | typing.Literal['gotcha!']
            t: typing.Literal[False] | typing.Literal['gotcha!']
            a: MapRecursive[tests.test_type_eval.Recursive] | typing.Literal['gotcha!']
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


class TA:
    x: int
    y: list[float]
    z: TB


class TB:
    x: str
    y: list[object]


def test_type_getattr_union_1():
    d = eval_typing(GetAttr[TA | TB, Literal["x"]])
    assert d == int | str


def test_type_getattr_union_2():
    d = eval_typing(GetAttr[TA, Literal["x"] | Literal["y"]])
    assert d == int | list[float]


def test_type_getattr_union_3():
    d = eval_typing(GetAttr[TA | TB, Literal["x"] | Literal["y"]])
    assert d == int | list[float] | str | list[object]


def test_type_getattr_union_4():
    d = eval_typing(GetAttr[TA, Literal["x", "y"]])
    assert d == int | list[float]


def test_type_getattr_union_5():
    d = eval_typing(GetAttr[TA, Literal["x", "y"] | Literal["z"]])
    assert d == int | list[float] | TB


def test_type_strings_1():
    d = eval_typing(Uppercase[Literal["foo"]])
    assert d == Literal["FOO"]


def test_type_strings_2():
    d = eval_typing(Uppercase[Literal["foo", "bar"]])
    assert d == Literal["FOO"] | Literal["BAR"]


def test_type_strings_3():
    d = eval_typing(StrConcat[Literal["foo"], Literal["bar"]])
    assert d == Literal["foobar"]


def test_type_strings_4():
    d = eval_typing(StrConcat[Literal["a", "b"], Literal["c", "d"]])
    assert d == Literal["ac"] | Literal["ad"] | Literal["bc"] | Literal["bd"]


def test_type_strings_5():
    d = eval_typing(StrSlice[Literal["abcd"], Literal[0], Literal[1]])
    assert d == Literal["a"]


def test_type_strings_6():
    d = eval_typing(StrSlice[Literal["abcd"], Literal[1], Literal[None]])
    assert d == Literal["bcd"]


def test_type_asdf():
    d = eval_typing(FromUnion[int | bool])
    arg = FromUnion[int | str]
    d = eval_typing(arg)
    assert d == tuple[int, str] or d == tuple[str, int]


def test_getarg_never():
    d = eval_typing(GetArg[Never, object, 0])
    assert d is Never


def test_uppercase_never():
    d = eval_typing(Uppercase[Never])
    assert d is Never


def test_never_is():
    d = eval_typing(Is[Never, Never])
    assert d is True


def test_eval_iter():
    d = eval_typing(Iter[tuple[int, str]])
    assert tuple(d) == (int, str)

    d = eval_typing(Iter[Tuple[int, str]])
    assert tuple(d) == (int, str)

    d = eval_typing(Iter[tuple[(int, str)]])
    assert tuple(d) == (int, str)

    d = eval_typing(Iter[tuple[()]])
    assert tuple(d) == ()


def test_eval_length_01():
    d = eval_typing(Length[tuple[int, str]])
    assert d == Literal[2]

    d = eval_typing(Length[Tuple[int, str]])
    assert d == Literal[2]

    d = eval_typing(Length[tuple[(int, str)]])
    assert d == Literal[2]

    d = eval_typing(Length[tuple[()]])
    assert d == Literal[0]

    d = eval_typing(Length[tuple[int, ...]])
    assert d == Literal[None]
