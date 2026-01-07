import pytest

import collections
import textwrap
import unittest
from typing import (
    Any,
    Callable,
    Generic,
    List,
    Literal,
    Never,
    Tuple,
    TypeVar,
    Union,
)

from typemap.type_eval import eval_typing
from typemap.typing import (
    Attrs,
    FromUnion,
    GetArg,
    GetArgs,
    GetAttr,
    GetName,
    GetType,
    Is,
    Iter,
    Length,
    Member,
    NewProtocol,
    SpecialFormEllipsis,
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


type IntTree = int | list[IntTree]
type GenericTree[T] = T | list[GenericTree[T]]
type XNode[X, Y] = X | list[YNode[X, Y]]
type YNode[X, Y] = Y | list[XNode[X, Y]]
type XYTree[X, Y] = XNode[X, Y] | YNode[X, Y]


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


def _is_generic_permutation(t1, t2):
    return t1.__origin__ == t2.__origin__ and collections.Counter(
        t1.__args__
    ) == collections.Counter(t2.__args__)


def test_type_from_union_01():
    d = eval_typing(FromUnion[int | bool])
    arg = FromUnion[int | str]
    d = eval_typing(arg)
    assert _is_generic_permutation(d, tuple[int, str])


def test_type_from_union_02():
    d = eval_typing(FromUnion[IntTree])
    assert _is_generic_permutation(d, tuple[int, list[IntTree]])


def test_type_from_union_03():
    d = eval_typing(FromUnion[GenericTree[str]])
    assert _is_generic_permutation(d, tuple[str, list[GenericTree[str]]])


def test_type_from_union_04():
    d = eval_typing(FromUnion[XYTree[int, str]])
    assert _is_generic_permutation(
        d,
        tuple[XNode[int, str], YNode[int, str]],
    )


def test_getarg_never():
    d = eval_typing(GetArg[Never, object, 0])
    assert d is Never


def test_eval_getargs():
    t = dict[int, str]
    args = eval_typing(GetArgs[t, dict])
    assert args == tuple[int, str]

    t = dict
    args = eval_typing(GetArgs[t, dict])
    assert args == tuple[Any, Any]


def test_eval_getarg_callable():
    # oh hmmmmmmm -- yeah maybe callable could be fully bespoke if we
    # disallowed putting Callable here...!
    t = Callable[[int, str], str]
    args = eval_typing(GetArg[t, Callable, 0])
    assert args == tuple[int, str]

    t = Callable[int, str]
    args = eval_typing(GetArg[t, Callable, 0])
    assert args == tuple[int]

    t = Callable[[], str]
    args = eval_typing(GetArg[t, Callable, 0])
    assert args == tuple[()]

    t = Callable[..., str]
    args = eval_typing(GetArg[t, Callable, 0])
    assert args == SpecialFormEllipsis

    t = Callable
    args = eval_typing(GetArg[t, Callable, 0])
    assert args == SpecialFormEllipsis

    t = Callable
    args = eval_typing(GetArg[t, Callable, 1])
    assert args == Any


def test_eval_getarg_tuple():
    t = tuple[int, ...]
    args = eval_typing(GetArg[t, tuple, 1])
    assert args == SpecialFormEllipsis

    t = tuple
    args = eval_typing(GetArg[t, tuple, 0])
    assert args == Any

    args = eval_typing(GetArg[t, tuple, 1])
    assert args == SpecialFormEllipsis


def test_eval_getarg_list():
    t = list[int]
    arg = eval_typing(GetArg[t, list, 0])
    assert arg is int

    t = List[int]
    arg = eval_typing(GetArg[t, list, 0])
    assert arg is int

    t = list
    arg = eval_typing(GetArg[t, list, 0])
    assert arg == Any

    t = List
    arg = eval_typing(GetArg[t, list, 0])
    assert arg == Any

    t = list[int]
    arg = eval_typing(GetArg[t, List, 0])
    assert arg is int

    t = List[int]
    arg = eval_typing(GetArg[t, List, 0])
    assert arg is int

    t = list
    arg = eval_typing(GetArg[t, List, 0])
    assert arg == Any

    t = List
    arg = eval_typing(GetArg[t, List, 0])
    assert arg == Any

    # indexing with -1 equivalent to 0
    t = list[int]
    arg = eval_typing(GetArg[t, list, -1])
    assert arg is int

    t = List[int]
    arg = eval_typing(GetArg[t, list, -1])
    assert arg is int

    t = list
    arg = eval_typing(GetArg[t, list, -1])
    assert arg == Any

    t = List
    arg = eval_typing(GetArg[t, list, -1])
    assert arg == Any

    t = list[int]
    arg = eval_typing(GetArg[t, List, -1])
    assert arg is int

    t = List[int]
    arg = eval_typing(GetArg[t, List, -1])
    assert arg is int

    t = list
    arg = eval_typing(GetArg[t, List, -1])
    assert arg == Any

    t = List
    arg = eval_typing(GetArg[t, List, -1])
    assert arg == Any

    # indexing with 1 always fails
    t = list[int]
    arg = eval_typing(GetArg[t, list, 1])
    assert arg == Never

    t = List[int]
    arg = eval_typing(GetArg[t, list, 1])
    assert arg == Never

    t = list
    arg = eval_typing(GetArg[t, list, 1])
    assert arg == Never

    t = List
    arg = eval_typing(GetArg[t, list, 1])
    assert arg == Never

    t = list[int]
    arg = eval_typing(GetArg[t, List, 1])
    assert arg == Never

    t = List[int]
    arg = eval_typing(GetArg[t, List, 1])
    assert arg == Never

    t = list
    arg = eval_typing(GetArg[t, List, 1])
    assert arg == Never

    t = List
    arg = eval_typing(GetArg[t, List, 1])
    assert arg == Never


@pytest.mark.xfail(reason="Should this work?")
def test_eval_getarg_union_01():
    arg = eval_typing(GetArg[int | str, Union, 0])
    assert arg is int


@pytest.mark.xfail(reason="Should this work?")
def test_eval_getarg_union_02():
    arg = eval_typing(GetArg[GenericTree[int], GenericTree, 0])
    assert arg is int


def test_eval_getarg_custom_01():
    class A[T]:
        pass

    t = A[int]
    assert eval_typing(GetArg[t, A, 0]) is int
    assert eval_typing(GetArg[t, A, -1]) is int
    assert eval_typing(GetArg[t, A, 1]) == Never

    t = A
    assert eval_typing(GetArg[t, A, 0]) == Any
    assert eval_typing(GetArg[t, A, -1]) == Any
    assert eval_typing(GetArg[t, A, 1]) == Never


def test_eval_getarg_custom_02():
    T = TypeVar("T")

    class A(Generic[T]):
        pass

    t = A[int]
    assert eval_typing(GetArg[t, A, 0]) is int
    assert eval_typing(GetArg[t, A, -1]) is int
    assert eval_typing(GetArg[t, A, 1]) == Never

    t = A
    assert eval_typing(GetArg[t, A, 0]) == Any
    assert eval_typing(GetArg[t, A, -1]) == Any
    assert eval_typing(GetArg[t, A, 1]) == Never


def test_eval_getarg_custom_03():
    class A[T = str]:
        pass

    t = A[int]
    assert eval_typing(GetArg[t, A, 0]) is int
    assert eval_typing(GetArg[t, A, -1]) is int
    assert eval_typing(GetArg[t, A, 1]) == Never

    t = A
    assert eval_typing(GetArg[t, A, 0]) is str
    assert eval_typing(GetArg[t, A, -1]) is str
    assert eval_typing(GetArg[t, A, 1]) == Never


def test_eval_getarg_custom_04():
    T = TypeVar("T", default=str)

    class A(Generic[T]):
        pass

    t = A[int]
    assert eval_typing(GetArg[t, A, 0]) is int
    assert eval_typing(GetArg[t, A, -1]) is int
    assert eval_typing(GetArg[t, A, 1]) == Never

    t = A
    assert eval_typing(GetArg[t, A, 0]) is str
    assert eval_typing(GetArg[t, A, -1]) is str
    assert eval_typing(GetArg[t, A, 1]) == Never


@pytest.mark.xfail(reason="Should this work?")
def test_eval_getarg_custom_05():
    A = TypeVar("A")

    class ATree(Generic[A]):
        val: A | list[ATree[A]]

    t = ATree[int]
    assert eval_typing(GetArg[t, ATree, 0]) is int
    assert eval_typing(GetArg[t, ATree, -1]) is int
    assert eval_typing(GetArg[t, ATree, 1]) == Never

    t = ATree
    assert eval_typing(GetArg[t, ATree, 0]) is Any
    assert eval_typing(GetArg[t, ATree, -1]) is Any
    assert eval_typing(GetArg[t, ATree, 1]) == Never


@pytest.mark.xfail(reason="Should this work?")
def test_eval_getarg_custom_06():
    A = TypeVar("A")
    B = TypeVar("B")

    class ANode(Generic[A, B]):
        val: A | list[BNode[A, B]]

    class BNode(Generic[A, B]):
        val: B | list[ANode[A, B]]

    class ABTree(Generic[A, B]):
        root: ANode[A, B] | BNode[A, B]

    t = ABTree[int, str]
    assert eval_typing(GetArg[t, ABTree, 0]) is int
    assert eval_typing(GetArg[t, ABTree, 1]) is str
    assert eval_typing(GetArg[t, ABTree, 2]) == Never

    t = ABTree
    assert eval_typing(GetArg[t, ABTree, 0]) is Any
    assert eval_typing(GetArg[t, ABTree, 1]) is Any
    assert eval_typing(GetArg[t, ABTree, 2]) == Never


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
