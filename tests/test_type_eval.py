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
    And,
    Attrs,
    Equals,
    FromUnion,
    GetArg,
    GetArgs,
    GetAttr,
    GetName,
    GetType,
    GreaterThan,
    GreaterThanOrEqual,
    If,
    Is,
    Iter,
    Length,
    LessThan,
    LessThanOrEqual,
    Member,
    NewProtocol,
    Not,
    NotEquals,
    Or,
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

    # XXX: I don't have a good intuition about whether the inner MapRecursive ought to expand or not.
    #
    # Currently there are two test implementations for flatten_class
    # and the canonical one does not expand it and the
    # NewProtocol-based one does.
    #
    # I don't really think they ought to differ; something funny is
    # going on with recursively alias handling.
    res = format_helper.format_class(evaled)
    res = res.replace('tests.test_type_eval.MapRecursive', 'MapRecursive')

    assert res == textwrap.dedent("""\
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


type UnlabeledTree = list[UnlabeledTree]
type IntTree = int | list[IntTree]
type GenericTree[T] = T | list[GenericTree[T]]
type XNode[X, Y] = X | list[YNode[X, Y]]
type YNode[X, Y] = Y | list[XNode[X, Y]]
type XYTree[X, Y] = XNode[X, Y] | YNode[X, Y]
type NestedTree = str | list[NestedTree] | list[IntTree]


class TA:
    x: int
    y: list[float]
    z: TB


class TB:
    x: str
    y: list[object]


type GetA1[A, B] = A
type GetA2[B, A] = A


def test_eval_arg_order():
    d = eval_typing(GetA1[int, str])
    assert d is int
    d = eval_typing(GetA2[str, int])
    assert d is int


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


type ReplacePrefix[S: str, P: str, N: str] = (
    StrConcat[N, StrSlice[S, 2, Literal[None]]]
    if Is[StrSlice[S, 0, Length[P]], P]
    else S
)


def test_type_strings_7():
    d = eval_typing(
        ReplacePrefix[Literal["x_a"], Literal["x_"], Literal["hi_"]]
    )
    assert d == Literal["hi_a"]
    d = eval_typing(
        ReplacePrefix[Literal["x_a"], Literal["y_"], Literal["hi_"]]
    )
    assert d == Literal["x_a"]


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
    d = eval_typing(FromUnion[UnlabeledTree])
    assert _is_generic_permutation(d, tuple[list[UnlabeledTree]])

    d = eval_typing(GetArg[d, tuple, 0])
    assert d == list[UnlabeledTree]
    d = eval_typing(GetArg[d, list, 0])
    assert d == list[UnlabeledTree]
    d = eval_typing(FromUnion[d])
    assert _is_generic_permutation(d, tuple[list[UnlabeledTree]])


def test_type_from_union_03():
    d = eval_typing(FromUnion[IntTree])
    assert _is_generic_permutation(d, tuple[int, list[IntTree]])

    d = eval_typing(GetArg[d, tuple, 1])
    assert d == list[IntTree]
    d = eval_typing(GetArg[d, list, 0])
    assert d == int | list[IntTree]
    d = eval_typing(FromUnion[d])
    assert _is_generic_permutation(d, tuple[int, list[IntTree]])


def test_type_from_union_04():
    d = eval_typing(FromUnion[GenericTree[str]])
    assert _is_generic_permutation(d, tuple[str, list[GenericTree[str]]])

    d = eval_typing(GetArg[d, tuple, 1])
    assert d == list[GenericTree[str]]
    d = eval_typing(GetArg[d, list, 0])
    assert d == str | list[GenericTree[str]]
    d = eval_typing(FromUnion[d])
    assert _is_generic_permutation(d, tuple[str, list[GenericTree[str]]])


def test_type_from_union_05():
    d = eval_typing(FromUnion[XYTree[int, str]])
    assert _is_generic_permutation(
        d,
        tuple[XNode[int, str], YNode[int, str]],
    )

    x = eval_typing(GetArg[d, tuple, 0])
    assert x == int | list[str | list[XNode[int, str]]]

    x = eval_typing(FromUnion[x])
    assert _is_generic_permutation(
        x, tuple[int, list[str | list[XNode[int, str]]]]
    )
    x = eval_typing(GetArg[x, tuple, 1])
    assert x == list[str | list[XNode[int, str]]]
    x = eval_typing(GetArg[x, list, 0])
    assert x == str | list[XNode[int, str]]
    x = eval_typing(FromUnion[x])
    assert _is_generic_permutation(x, tuple[str, list[XNode[int, str]]])
    x = eval_typing(GetArg[x, tuple, 1])
    assert x == list[XNode[int, str]]
    x = eval_typing(GetArg[x, list, 0])
    assert x == int | list[str | list[XNode[int, str]]]

    y = eval_typing(GetArg[d, tuple, 1])
    assert y == str | list[int | list[YNode[int, str]]]

    y = eval_typing(FromUnion[y])
    assert _is_generic_permutation(
        y, tuple[str, list[int | list[YNode[int, str]]]]
    )
    y = eval_typing(GetArg[y, tuple, 1])
    assert y == list[int | list[YNode[int, str]]]
    y = eval_typing(GetArg[y, list, 0])
    assert y == int | list[YNode[int, str]]
    y = eval_typing(FromUnion[y])
    assert _is_generic_permutation(y, tuple[int, list[YNode[int, str]]])
    y = eval_typing(GetArg[y, tuple, 1])
    assert y == list[YNode[int, str]]
    y = eval_typing(GetArg[y, list, 0])
    assert y == str | list[int | list[YNode[int, str]]]


def test_type_from_union_06():
    d = eval_typing(FromUnion[NestedTree])
    assert _is_generic_permutation(
        d,
        tuple[str, list[NestedTree], list[IntTree]],
    )

    n = eval_typing(GetArg[d, tuple, 1])
    assert n == list[NestedTree]
    n = eval_typing(GetArg[n, list, 0])
    assert n == str | list[NestedTree] | list[IntTree]
    n = eval_typing(FromUnion[n])
    assert _is_generic_permutation(
        n, tuple[str, list[NestedTree], list[IntTree]]
    )

    n = eval_typing(FromUnion[GetArg[GetArg[n, tuple, 1], list, 0]])
    assert _is_generic_permutation(
        n, tuple[str, list[NestedTree], list[IntTree]]
    )

    i = eval_typing(GetArg[d, tuple, 2])
    assert i == list[IntTree]
    i = eval_typing(GetArg[i, list, 0])
    assert i == int | list[IntTree]

    n = eval_typing(FromUnion[GetArg[GetArg[d, tuple, 2], list, 0]])
    assert _is_generic_permutation(n, tuple[int, list[IntTree]])


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


TestTypeVar = TypeVar("TestTypeVar")


def test_eval_getarg_custom_05():
    # TypeVar declared outside of scope of class
    class ATree(Generic[TestTypeVar]):
        val: list[ATree[TestTypeVar]]

    t = ATree[int]
    assert eval_typing(GetArg[t, ATree, 0]) is int
    assert eval_typing(GetArg[t, ATree, -1]) is int
    assert eval_typing(GetArg[t, ATree, 1]) == Never

    t = ATree
    assert eval_typing(GetArg[t, ATree, 0]) is Any
    assert eval_typing(GetArg[t, ATree, -1]) is Any
    assert eval_typing(GetArg[t, ATree, 1]) == Never


def test_eval_getarg_custom_06():
    # TypeVar declared inside scope of class
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


def test_eval_getarg_custom_07():
    # Doubly recursive generic types
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


def test_eval_getarg_custom_08():
    # Generic class with generic methods
    T = TypeVar("T")

    class Container(Generic[T]):
        data: list[T]

        def get[T](self, index: int, default: T) -> int | T: ...
        def map[U](self, func: Callable[[int], U]) -> list[U]: ...
        def convert[T](self, func: Callable[[int], T]) -> Container2[T]: ...

    class Container2[T]: ...

    t = Container[int]
    assert eval_typing(GetArg[t, Container, 0]) is int
    assert eval_typing(GetArg[t, Container, -1]) is int
    assert eval_typing(GetArg[t, Container, 1]) == Never

    t = Container
    assert eval_typing(GetArg[t, Container, 0]) is Any
    assert eval_typing(GetArg[t, Container, -1]) is Any
    assert eval_typing(GetArg[t, Container, 1]) == Never


type _Works[Ts, I] = Literal[True]
type Works[Ts] = _Works[Ts, Length[Ts]]

type _Fails[Ts, I] = Literal[False]
type Fails[Ts] = _Fails[Ts, Literal[0]]


def test_consistency_01():
    t = eval_typing(Works[tuple[int, str]])
    assert t == Literal[True]

    t = eval_typing(Fails[tuple[int, str]])
    assert t == Literal[False]


def test_eval_equals():
    d = eval_typing(Equals[Literal[1], Literal[1]])
    assert d == Literal[True]
    d = eval_typing(Equals[Literal[1], Literal[2]])
    assert d == Literal[False]

    d = eval_typing(Equals[1, 1])
    assert d == Literal[True]
    d = eval_typing(Equals[1, 2])
    assert d == Literal[False]


def test_eval_not_equals():
    d = eval_typing(NotEquals[Literal[1], Literal[1]])
    assert d == Literal[False]
    d = eval_typing(NotEquals[Literal[1], Literal[2]])
    assert d == Literal[True]

    d = eval_typing(NotEquals[1, 1])
    assert d == Literal[False]
    d = eval_typing(NotEquals[1, 2])
    assert d == Literal[True]


def test_eval_greater_than():
    d = eval_typing(GreaterThan[Literal[1], Literal[1]])
    assert d == Literal[False]
    d = eval_typing(GreaterThan[Literal[1], Literal[2]])
    assert d == Literal[False]
    d = eval_typing(GreaterThan[Literal[2], Literal[1]])
    assert d == Literal[True]

    d = eval_typing(GreaterThan[1, 1])
    assert d == Literal[False]
    d = eval_typing(GreaterThan[1, 2])
    assert d == Literal[False]
    d = eval_typing(GreaterThan[2, 1])
    assert d == Literal[True]


def test_eval_greater_than_or_equal():
    d = eval_typing(GreaterThanOrEqual[Literal[1], Literal[1]])
    assert d == Literal[True]
    d = eval_typing(GreaterThanOrEqual[Literal[1], Literal[2]])
    assert d == Literal[False]
    d = eval_typing(GreaterThanOrEqual[Literal[2], Literal[1]])
    assert d == Literal[True]

    d = eval_typing(GreaterThanOrEqual[1, 1])
    assert d == Literal[True]
    d = eval_typing(GreaterThanOrEqual[1, 2])
    assert d == Literal[False]
    d = eval_typing(GreaterThanOrEqual[2, 1])
    assert d == Literal[True]


def test_eval_less_than():
    d = eval_typing(LessThan[Literal[1], Literal[1]])
    assert d == Literal[False]
    d = eval_typing(LessThan[Literal[1], Literal[2]])
    assert d == Literal[True]
    d = eval_typing(LessThan[Literal[2], Literal[1]])
    assert d == Literal[False]

    d = eval_typing(LessThan[1, 1])
    assert d == Literal[False]
    d = eval_typing(LessThan[1, 2])
    assert d == Literal[True]
    d = eval_typing(LessThan[2, 1])
    assert d == Literal[False]


def test_eval_less_than_or_equal():
    d = eval_typing(LessThanOrEqual[Literal[1], Literal[1]])
    assert d == Literal[True]
    d = eval_typing(LessThanOrEqual[Literal[1], Literal[2]])
    assert d == Literal[True]
    d = eval_typing(LessThanOrEqual[Literal[2], Literal[1]])
    assert d == Literal[False]

    d = eval_typing(LessThanOrEqual[1, 1])
    assert d == Literal[True]
    d = eval_typing(LessThanOrEqual[1, 2])
    assert d == Literal[True]
    d = eval_typing(LessThanOrEqual[2, 1])
    assert d == Literal[False]


def test_eval_not():
    d = eval_typing(Not[Literal[True]])
    assert d == Literal[False]
    d = eval_typing(Not[Literal[False]])
    assert d == Literal[True]

    d = eval_typing(Not[True])
    assert d == Literal[False]
    d = eval_typing(Not[False])
    assert d == Literal[True]


def test_eval_and():
    d = eval_typing(And[Literal[True], Literal[True]])
    assert d == Literal[True]
    d = eval_typing(And[Literal[True], Literal[False]])
    assert d == Literal[False]
    d = eval_typing(And[Literal[False], Literal[True]])
    assert d == Literal[False]
    d = eval_typing(And[Literal[False], Literal[False]])
    assert d == Literal[False]

    d = eval_typing(And[True, True])
    assert d == Literal[True]
    d = eval_typing(And[True, False])
    assert d == Literal[False]
    d = eval_typing(And[False, True])
    assert d == Literal[False]
    d = eval_typing(And[False, False])
    assert d == Literal[False]


def test_eval_or():
    d = eval_typing(Or[Literal[True], Literal[True]])
    assert d == Literal[True]
    d = eval_typing(Or[Literal[True], Literal[False]])
    assert d == Literal[True]
    d = eval_typing(Or[Literal[False], Literal[True]])
    assert d == Literal[True]
    d = eval_typing(Or[Literal[False], Literal[False]])
    assert d == Literal[False]

    d = eval_typing(Or[True, True])
    assert d == Literal[True]
    d = eval_typing(Or[True, False])
    assert d == Literal[True]
    d = eval_typing(Or[False, True])
    assert d == Literal[True]
    d = eval_typing(Or[False, False])
    assert d == Literal[False]


type ShorterTuple[L, R] = If[LessThan[Length[L], Length[R]], L, R]


def test_eval_if():
    d = eval_typing(If[Literal[True], int, str])
    assert d is int
    d = eval_typing(If[Literal[False], int, str])
    assert d is str

    d = eval_typing(If[True, int, str])
    assert d is int
    d = eval_typing(If[False, int, str])
    assert d is str

    d = eval_typing(ShorterTuple[tuple[int], tuple[str, str]])
    assert d == tuple[int]
    d = eval_typing(ShorterTuple[tuple[int, int], tuple[str]])
    assert d == tuple[str]

    d = eval_typing(If[True, Literal[True], Literal[False]])
    assert d == Literal[True]
    d = eval_typing(If[False, Literal[True], Literal[False]])
    assert d == Literal[False]


class Prefixed:
    x_a: int
    x_b: str
    x_c: float
    y_a: int
    y_b: str
    y_c: float


type FilterPrefix[T, P: str] = NewProtocol[
    *[x for x in Iter[Attrs[T]] if Is[StrSlice[GetName[x], 0, Length[P]], P]]
]
type FilterPrefix2[T, Pint: str, Pstr: str] = NewProtocol[
    *[
        x
        for x in Iter[Attrs[T]]
        if (
            Is[StrSlice[GetName[x], 0, Length[Pint]], Pint]
            if Is[GetType[x], int]
            else (
                Is[StrSlice[GetName[x], 0, Length[Pstr]], Pstr]
                and Is[GetType[x], str]
            )
        )
    ]
]
type FilterPrefix3[T, P: str, N: str] = NewProtocol[
    *[
        (
            x
            if not Is[StrSlice[GetName[x], 0, Length[P]], P]
            else Member[
                StrConcat[N, StrSlice[GetName[x], Length[P], Literal[None]]],
                GetType[x],
            ]
        )
        for x in Iter[Attrs[T]]
    ]
]


def test_filter_prefix_1():
    d = eval_typing(FilterPrefix[Prefixed, Literal["x_"]])
    fmt = format_helper.format_class(d)
    assert fmt == textwrap.dedent("""\
        class FilterPrefix[tests.test_type_eval.Prefixed, typing.Literal['x_']]:
            x_a: int
            x_b: str
            x_c: float
        """)


def test_filter_prefix_2():
    d = eval_typing(FilterPrefix2[Prefixed, Literal["x_"], Literal["y_"]])
    fmt = format_helper.format_class(d)
    assert fmt == textwrap.dedent("""\
        class FilterPrefix2[tests.test_type_eval.Prefixed, typing.Literal['x_'], typing.Literal['y_']]:
            x_a: int
            y_b: str
        """)


def test_filter_prefix_3():
    d = eval_typing(FilterPrefix3[Prefixed, Literal["y_"], Literal["z_"]])
    fmt = format_helper.format_class(d)
    assert fmt == textwrap.dedent("""\
        class FilterPrefix3[tests.test_type_eval.Prefixed, typing.Literal['y_'], typing.Literal['z_']]:
            x_a: int
            x_b: str
            x_c: float
            z_a: int
            z_b: str
            z_c: float
        """)


def test_uppercase_never():
    d = eval_typing(Uppercase[Never])
    assert d is Never


def test_never_is():
    d = eval_typing(Is[Never, Never])
    assert d is True


def test_eval_iter_01():
    d = eval_typing(Iter[tuple[int, str]])
    assert tuple(d) == (int, str)

    d = eval_typing(Iter[Tuple[int, str]])
    assert tuple(d) == (int, str)

    d = eval_typing(Iter[tuple[(int, str)]])
    assert tuple(d) == (int, str)

    d = eval_typing(Iter[tuple[()]])
    assert tuple(d) == ()


type DuplicateTuple[T] = tuple[*[x for x in Iter[T]], *[x for x in Iter[T]]]
type ConcatTupleWithSelf[T] = ConcatTuples[T, T]


def test_eval_iter_02():
    # ensure iterating duplicate tuples can be iterated multiple times
    d = eval_typing(ConcatTuples[tuple[int, str], tuple[int, str]])
    assert d == tuple[int, str, int, str]

    d = eval_typing(DuplicateTuple[tuple[int, str]])
    assert d == tuple[int, str, int, str]

    d = eval_typing(ConcatTupleWithSelf[tuple[int, str]])
    assert d == tuple[int, str, int, str]


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


def test_eval_literal_idempotent_01():
    t = Literal[int]
    for _ in range(5):
        nt = eval_typing(t)
        assert t == nt
        t = nt
