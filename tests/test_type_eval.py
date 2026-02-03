import collections
import textwrap
import unittest
from typing import (
    Annotated,
    Any,
    Callable,
    Generic,
    List,
    Literal,
    Never,
    Self,
    Tuple,
    TypeVar,
    Union,
)

import pytest

from typemap.type_eval import eval_typing
from typemap.typing import (
    Attrs,
    Bool,
    FromUnion,
    GenericCallable,
    GetArg,
    GetArgs,
    GetMember,
    GetMemberType,
    GetName,
    GetSpecialAttr,
    GetType,
    GetAnnotations,
    IsSub,
    IsSubSimilar,
    IsSubtype,
    Iter,
    Length,
    Matches,
    Member,
    Members,
    NewProtocol,
    Param,
    Slice,
    SpecialFormEllipsis,
    StrConcat,
    Uppercase,
    _BoolLiteral,
    _Lambda,
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
            if not IsSub[GetType[p], A]
            else Member[GetName[p], OrGotcha[MapRecursive[A]]]
        )
        for p in Iter[tuple[*Attrs[A], *Attrs[F_int]]]
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


def test_eval_types_4():
    d = eval_typing(
        Callable[
            [
                Param[Literal["a"], int, Literal["positional"]],
                Param[Literal["b"], int],
                Param[Literal["c"], int, Literal["default"]],
                Param[None, int, Literal["*"]],
                Param[Literal["d"], int, Literal["keyword"]],
                Param[Literal["e"], int, Literal["default", "keyword"]],
                Param[None, int, Literal["**"]],
            ],
            int,
        ]
    )
    assert (
        d
        == Callable[
            [
                Param[Literal["a"], int, Literal["positional"]],
                Param[Literal["b"], int],
                Param[Literal["c"], int, Literal["default"]],
                Param[None, int, Literal["*"]],
                Param[Literal["d"], int, Literal["keyword"]],
                Param[Literal["e"], int, Literal["default", "keyword"]],
                Param[None, int, Literal["**"]],
            ],
            int,
        ]
    )


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
    d = eval_typing(GetMemberType[TA | TB, Literal["x"]])
    assert d == int | str


def test_type_getattr_union_2():
    d = eval_typing(GetMemberType[TA, Literal["x"] | Literal["y"]])
    assert d == int | list[float]


def test_type_getattr_union_3():
    d = eval_typing(GetMemberType[TA | TB, Literal["x"] | Literal["y"]])
    assert d == int | list[float] | str | list[object]


def test_type_getattr_union_4():
    d = eval_typing(GetMemberType[TA, Literal["x", "y"]])
    assert d == int | list[float]


def test_type_getattr_union_5():
    d = eval_typing(GetMemberType[TA, Literal["x", "y"] | Literal["z"]])
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
    d = eval_typing(Slice[Literal["abcd"], Literal[0], Literal[1]])
    assert d == Literal["a"]


def test_type_strings_6():
    d = eval_typing(Slice[Literal["abcd"], Literal[1], Literal[None]])
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
    d = eval_typing(FromUnion[UnlabeledTree])
    assert _is_generic_permutation(d, tuple[list[UnlabeledTree]])

    d = eval_typing(GetArg[d, tuple, Literal[0]])
    assert d == list[UnlabeledTree]
    d = eval_typing(GetArg[d, list, Literal[0]])
    assert d == list[UnlabeledTree]
    d = eval_typing(FromUnion[d])
    assert _is_generic_permutation(d, tuple[list[UnlabeledTree]])


def test_type_from_union_03():
    d = eval_typing(FromUnion[IntTree])
    assert _is_generic_permutation(d, tuple[int, list[IntTree]])

    d = eval_typing(GetArg[d, tuple, Literal[1]])
    assert d == list[IntTree]
    d = eval_typing(GetArg[d, list, Literal[0]])
    assert d == int | list[IntTree]
    d = eval_typing(FromUnion[d])
    assert _is_generic_permutation(d, tuple[int, list[IntTree]])


def test_type_from_union_04():
    d = eval_typing(FromUnion[GenericTree[str]])
    assert _is_generic_permutation(d, tuple[str, list[GenericTree[str]]])

    d = eval_typing(GetArg[d, tuple, Literal[1]])
    assert d == list[GenericTree[str]]
    d = eval_typing(GetArg[d, list, Literal[0]])
    assert d == str | list[GenericTree[str]]
    d = eval_typing(FromUnion[d])
    assert _is_generic_permutation(d, tuple[str, list[GenericTree[str]]])


def test_type_from_union_05():
    d = eval_typing(FromUnion[XYTree[int, str]])
    assert _is_generic_permutation(
        d,
        tuple[XNode[int, str], YNode[int, str]],
    )

    x = eval_typing(GetArg[d, tuple, Literal[0]])
    assert x == int | list[str | list[XNode[int, str]]]

    x = eval_typing(FromUnion[x])
    assert _is_generic_permutation(
        x, tuple[int, list[str | list[XNode[int, str]]]]
    )
    x = eval_typing(GetArg[x, tuple, Literal[1]])
    assert x == list[str | list[XNode[int, str]]]
    x = eval_typing(GetArg[x, list, Literal[0]])
    assert x == str | list[XNode[int, str]]
    x = eval_typing(FromUnion[x])
    assert _is_generic_permutation(x, tuple[str, list[XNode[int, str]]])
    x = eval_typing(GetArg[x, tuple, Literal[1]])
    assert x == list[XNode[int, str]]
    x = eval_typing(GetArg[x, list, Literal[0]])
    assert x == int | list[str | list[XNode[int, str]]]

    y = eval_typing(GetArg[d, tuple, Literal[1]])
    assert y == str | list[int | list[YNode[int, str]]]

    y = eval_typing(FromUnion[y])
    assert _is_generic_permutation(
        y, tuple[str, list[int | list[YNode[int, str]]]]
    )
    y = eval_typing(GetArg[y, tuple, Literal[1]])
    assert y == list[int | list[YNode[int, str]]]
    y = eval_typing(GetArg[y, list, Literal[0]])
    assert y == int | list[YNode[int, str]]
    y = eval_typing(FromUnion[y])
    assert _is_generic_permutation(y, tuple[int, list[YNode[int, str]]])
    y = eval_typing(GetArg[y, tuple, Literal[1]])
    assert y == list[YNode[int, str]]
    y = eval_typing(GetArg[y, list, Literal[0]])
    assert y == str | list[int | list[YNode[int, str]]]


def test_type_from_union_06():
    d = eval_typing(FromUnion[NestedTree])
    assert _is_generic_permutation(
        d,
        tuple[str, list[NestedTree], list[IntTree]],
    )

    n = eval_typing(GetArg[d, tuple, Literal[1]])
    assert n == list[NestedTree]
    n = eval_typing(GetArg[n, list, Literal[0]])
    assert n == str | list[NestedTree] | list[IntTree]
    n = eval_typing(FromUnion[n])
    assert _is_generic_permutation(
        n, tuple[str, list[NestedTree], list[IntTree]]
    )

    n = eval_typing(
        FromUnion[GetArg[GetArg[n, tuple, Literal[1]], list, Literal[0]]]
    )
    assert _is_generic_permutation(
        n, tuple[str, list[NestedTree], list[IntTree]]
    )

    i = eval_typing(GetArg[d, tuple, Literal[2]])
    assert i == list[IntTree]
    i = eval_typing(GetArg[i, list, Literal[0]])
    assert i == int | list[IntTree]

    n = eval_typing(
        FromUnion[GetArg[GetArg[d, tuple, Literal[2]], list, Literal[0]]]
    )
    assert _is_generic_permutation(n, tuple[int, list[IntTree]])


def test_getmember_01():
    d = eval_typing(GetMember[TA, Literal["x"]])
    assert d == Member[Literal["x"], int, Never, Never, TA]
    d = eval_typing(GetMemberType[TA, Literal["a"]])
    assert d == Never

    d = eval_typing(GetMember[TA | TB, Literal["x"]])
    assert d == (
        Member[Literal["x"], int, Never, Never, TA]
        | Member[Literal["x"], str, Never, Never, TB]
    )
    d = eval_typing(GetMember[TA | TB, Literal[""]])
    assert d == Never


def test_getarg_never():
    d = eval_typing(GetArg[Never, object, Literal[0]])
    assert d is Never


def test_eval_getargs():
    t = dict[int, str]
    args = eval_typing(GetArgs[t, dict])
    assert args == tuple[int, str]

    t = dict
    args = eval_typing(GetArgs[t, dict])
    assert args == tuple[Any, Any]


@unittest.skip
def test_eval_getarg_callable_old():
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


def test_eval_getarg_callable_01():
    t = Callable[[int, str], str]
    args = eval_typing(GetArg[t, Callable, Literal[0]])
    assert (
        args
        == tuple[
            Param[Literal[None], int, Never], Param[Literal[None], str, Never]
        ]
    )

    t = Callable[int, str]
    args = eval_typing(GetArg[t, Callable, Literal[0]])
    assert args == tuple[Param[Literal[None], int, Never]]

    t = Callable[[], str]
    args = eval_typing(GetArg[t, Callable, Literal[0]])
    assert args == tuple[()]

    # XXX: Is this what we want? Or should it be *args, **kwargs
    t = Callable[..., str]
    args = eval_typing(GetArg[t, Callable, Literal[0]])
    assert args == SpecialFormEllipsis

    t = Callable
    args = eval_typing(GetArg[t, Callable, Literal[0]])
    assert args == SpecialFormEllipsis

    t = Callable
    args = eval_typing(GetArg[t, Callable, Literal[1]])
    assert args == Any


def test_eval_getarg_callable_02():
    # GenericCallable
    T = TypeVar("T")

    # Params not wrapped
    f = Callable[[T], T]
    gc = GenericCallable[tuple[T], f]
    t = eval_typing(GetArg[gc, GenericCallable, Literal[0]])
    assert t == tuple[T]
    gc_f = eval_typing(GetArg[gc, GenericCallable, Literal[1]])
    assert gc_f == f
    t = eval_typing(GetArg[gc_f, Callable, Literal[0]])
    assert t == tuple[Param[Literal[None], T, Never]]
    t = eval_typing(GetArg[gc_f, Callable, Literal[1]])
    assert t is T

    # Params wrapped
    f = Callable[
        [
            Param[Literal[None], T, Literal["positional"]],
            Param[Literal["y"], T],
            Param[Literal["z"], T, Literal["keyword"]],
        ],
        T,
    ]
    gc = GenericCallable[
        tuple[T],
        f,
    ]
    t = eval_typing(GetArg[gc, GenericCallable, Literal[0]])
    assert t == tuple[T]
    gc_f = eval_typing(GetArg[gc, GenericCallable, Literal[1]])
    assert gc_f == f


type IndirectProtocol[T] = NewProtocol[*[m for m in Iter[Members[T]]],]
type GetMethodLike[T, Name] = GetArg[
    tuple[
        *[
            GetType[p]
            for p in Iter[Members[T]]
            if (
                IsSub[GetType[p], Callable]
                or IsSub[GetType[p], staticmethod]
                or IsSub[GetType[p], classmethod]
                or IsSub[GetType[p], GenericCallable]
            )
            and IsSub[Name, GetName[p]]
        ],
    ],
    tuple,
    Literal[0],
]


def test_eval_getarg_callable_03():
    # member function
    class C:
        def f(self, x: int, /, y: int, *, z: int) -> int: ...

    f = eval_typing(GetMethodLike[C, Literal["f"]])
    t = eval_typing(GetArg[f, Callable, Literal[0]])
    assert (
        t
        == tuple[
            Param[Literal["self"], C, Literal["positional"]],
            Param[Literal["x"], int, Literal["positional"]],
            Param[Literal["y"], int],
            Param[Literal["z"], int, Literal["keyword"]],
        ]
    )
    t = eval_typing(GetArg[f, Callable, Literal[1]])
    assert t is int

    f = eval_typing(GetMethodLike[IndirectProtocol[C], Literal["f"]])
    t = eval_typing(GetArg[f, Callable, Literal[0]])
    assert (
        t
        == tuple[
            Param[Literal["self"], Self, Literal["positional"]],
            Param[Literal["x"], int, Literal["positional"]],
            Param[Literal["y"], int],
            Param[Literal["z"], int, Literal["keyword"]],
        ]
    )
    t = eval_typing(GetArg[f, Callable, Literal[1]])
    assert t is int


def test_eval_getarg_callable_04():
    # classmethod
    class C:
        @classmethod
        def f(cls, x: int, /, y: int, *, z: int) -> int: ...

    f = eval_typing(GetMethodLike[C, Literal["f"]])
    t = eval_typing(GetArg[f, classmethod, Literal[0]])
    assert t == C
    t = eval_typing(GetArg[f, classmethod, Literal[1]])
    assert (
        t
        == tuple[
            Param[Literal["x"], int, Literal["positional"]],
            Param[Literal["y"], int],
            Param[Literal["z"], int, Literal["keyword"]],
        ]
    )
    t = eval_typing(GetArg[f, classmethod, Literal[2]])
    assert t is int

    f = eval_typing(GetMethodLike[IndirectProtocol[C], Literal["f"]])
    t = eval_typing(GetArg[f, classmethod, Literal[0]])
    t = eval_typing(GetArg[f, classmethod, Literal[1]])
    assert (
        t
        == tuple[
            Param[Literal["x"], int, Literal["positional"]],
            Param[Literal["y"], int],
            Param[Literal["z"], int, Literal["keyword"]],
        ]
    )
    t = eval_typing(GetArg[f, classmethod, Literal[2]])
    assert t is int


def test_eval_getarg_callable_05():
    # staticmethod
    class C:
        @staticmethod
        def f(x: int, /, y: int, *, z: int) -> int: ...

    f = eval_typing(GetMethodLike[C, Literal["f"]])
    t = eval_typing(GetArg[f, staticmethod, Literal[0]])
    assert (
        t
        == tuple[
            Param[Literal["x"], int, Literal["positional"]],
            Param[Literal["y"], int],
            Param[Literal["z"], int, Literal["keyword"]],
        ]
    )
    t = eval_typing(GetArg[f, staticmethod, Literal[1]])
    assert t is int

    f = eval_typing(GetMethodLike[IndirectProtocol[C], Literal["f"]])
    t = eval_typing(GetArg[f, staticmethod, Literal[0]])
    assert (
        t
        == tuple[
            Param[Literal["x"], int, Literal["positional"]],
            Param[Literal["y"], int],
            Param[Literal["z"], int, Literal["keyword"]],
        ]
    )
    t = eval_typing(GetArg[f, staticmethod, Literal[1]])
    assert t is int


def test_eval_getarg_callable_06():
    # member callable attr
    class C:
        f: Callable[[int], int]

    f = eval_typing(GetMethodLike[IndirectProtocol[C], Literal["f"]])
    t = eval_typing(GetArg[f, Callable, Literal[0]])
    assert t == tuple[Param[Literal[None], int, Never],]
    t = eval_typing(GetArg[f, Callable, Literal[1]])
    assert t is int


def test_eval_getarg_callable_07():
    # generic member function
    class C:
        def f[T](self, x: T, /, y: T, *, z: T) -> T: ...

    gc = eval_typing(GetMethodLike[C, Literal["f"]])
    _T = eval_typing(
        GetArg[GetArg[gc, GenericCallable, Literal[0]], tuple, Literal[0]]
    )
    f = eval_typing(GetArg[gc, GenericCallable, Literal[1]])
    t = eval_typing(GetArg[f, Callable, Literal[0]])
    assert (
        t
        == tuple[
            Param[Literal["self"], C, Literal["positional"]],
            Param[Literal["x"], _T, Literal["positional"]],
            Param[Literal["y"], _T],
            Param[Literal["z"], _T, Literal["keyword"]],
        ]
    )
    t = eval_typing(GetArg[f, Callable, Literal[1]])
    assert t is _T


def test_eval_getarg_callable_08():
    # generic classmethod
    class C:
        @classmethod
        def f[T](cls, x: T, /, y: T, *, z: T) -> T: ...

    gc = eval_typing(GetMethodLike[C, Literal["f"]])
    _T = eval_typing(
        GetArg[GetArg[gc, GenericCallable, Literal[0]], tuple, Literal[0]]
    )
    f = eval_typing(GetArg[gc, GenericCallable, Literal[1]])
    t = eval_typing(GetArg[f, classmethod, Literal[0]])
    assert t is C
    t = eval_typing(GetArg[f, classmethod, Literal[1]])
    assert (
        t
        == tuple[
            Param[Literal["x"], _T, Literal["positional"]],
            Param[Literal["y"], _T],
            Param[Literal["z"], _T, Literal["keyword"]],
        ]
    )
    t = eval_typing(GetArg[f, classmethod, Literal[2]])
    assert t is _T


def test_eval_getarg_callable_09():
    # generic staticmethod
    class C:
        @staticmethod
        def f[T](x: T, /, y: T, *, z: T) -> T: ...

    gc = eval_typing(GetMethodLike[C, Literal["f"]])
    _T = eval_typing(
        GetArg[GetArg[gc, GenericCallable, Literal[0]], tuple, Literal[0]]
    )
    f = eval_typing(GetArg[gc, GenericCallable, Literal[1]])
    t = eval_typing(GetArg[f, staticmethod, Literal[0]])
    assert (
        t
        == tuple[
            Param[Literal["x"], _T, Literal["positional"]],
            Param[Literal["y"], _T],
            Param[Literal["z"], _T, Literal["keyword"]],
        ]
    )
    t = eval_typing(GetArg[f, staticmethod, Literal[1]])
    assert t is _T


def test_eval_getarg_tuple():
    t = tuple[int, ...]
    args = eval_typing(GetArg[t, tuple, Literal[1]])
    assert args == SpecialFormEllipsis

    t = tuple
    args = eval_typing(GetArg[t, tuple, Literal[0]])
    assert args == Any

    args = eval_typing(GetArg[t, tuple, Literal[1]])
    assert args == SpecialFormEllipsis


def test_eval_getarg_list():
    t = list[int]
    arg = eval_typing(GetArg[t, list, Literal[0]])
    assert arg is int

    t = List[int]
    arg = eval_typing(GetArg[t, list, Literal[0]])
    assert arg is int

    t = list
    arg = eval_typing(GetArg[t, list, Literal[0]])
    assert arg == Any

    t = List
    arg = eval_typing(GetArg[t, list, Literal[0]])
    assert arg == Any

    t = list[int]
    arg = eval_typing(GetArg[t, List, Literal[0]])
    assert arg is int

    t = List[int]
    arg = eval_typing(GetArg[t, List, Literal[0]])
    assert arg is int

    t = list
    arg = eval_typing(GetArg[t, List, Literal[0]])
    assert arg == Any

    t = List
    arg = eval_typing(GetArg[t, List, Literal[0]])
    assert arg == Any

    # indexing with -1 equivalent to 0
    t = list[int]
    arg = eval_typing(GetArg[t, list, Literal[-1]])
    assert arg is int

    t = List[int]
    arg = eval_typing(GetArg[t, list, Literal[-1]])
    assert arg is int

    t = list
    arg = eval_typing(GetArg[t, list, Literal[-1]])
    assert arg == Any

    t = List
    arg = eval_typing(GetArg[t, list, Literal[-1]])
    assert arg == Any

    t = list[int]
    arg = eval_typing(GetArg[t, List, Literal[-1]])
    assert arg is int

    t = List[int]
    arg = eval_typing(GetArg[t, List, Literal[-1]])
    assert arg is int

    t = list
    arg = eval_typing(GetArg[t, List, Literal[-1]])
    assert arg == Any

    t = List
    arg = eval_typing(GetArg[t, List, Literal[-1]])
    assert arg == Any

    # indexing with 1 always fails
    t = list[int]
    arg = eval_typing(GetArg[t, list, Literal[1]])
    assert arg == Never

    t = List[int]
    arg = eval_typing(GetArg[t, list, Literal[1]])
    assert arg == Never

    t = list
    arg = eval_typing(GetArg[t, list, Literal[1]])
    assert arg == Never

    t = List
    arg = eval_typing(GetArg[t, list, Literal[1]])
    assert arg == Never

    t = list[int]
    arg = eval_typing(GetArg[t, List, Literal[1]])
    assert arg == Never

    t = List[int]
    arg = eval_typing(GetArg[t, List, Literal[1]])
    assert arg == Never

    t = list
    arg = eval_typing(GetArg[t, List, Literal[1]])
    assert arg == Never

    t = List
    arg = eval_typing(GetArg[t, List, Literal[1]])
    assert arg == Never


@pytest.mark.xfail(reason="Should this work?")
def test_eval_getarg_union_01():
    arg = eval_typing(GetArg[int | str, Union, Literal[0]])
    assert arg is int


@pytest.mark.xfail(reason="Should this work?")
def test_eval_getarg_union_02():
    arg = eval_typing(GetArg[GenericTree[int], GenericTree, Literal[0]])
    assert arg is int


def test_eval_getarg_custom_01():
    class A[T]:
        pass

    t = A[int]
    assert eval_typing(GetArg[t, A, Literal[0]]) is int
    assert eval_typing(GetArg[t, A, Literal[-1]]) is int
    assert eval_typing(GetArg[t, A, Literal[1]]) == Never

    t = A
    assert eval_typing(GetArg[t, A, Literal[0]]) == Any
    assert eval_typing(GetArg[t, A, Literal[-1]]) == Any
    assert eval_typing(GetArg[t, A, Literal[1]]) == Never


def test_eval_getarg_custom_02():
    T = TypeVar("T")

    class A(Generic[T]):
        pass

    t = A[int]
    assert eval_typing(GetArg[t, A, Literal[0]]) is int
    assert eval_typing(GetArg[t, A, Literal[-1]]) is int
    assert eval_typing(GetArg[t, A, Literal[1]]) == Never

    t = A
    assert eval_typing(GetArg[t, A, Literal[0]]) == Any
    assert eval_typing(GetArg[t, A, Literal[-1]]) == Any
    assert eval_typing(GetArg[t, A, Literal[1]]) == Never


def test_eval_getarg_custom_03():
    class A[T = str]:
        pass

    t = A[int]
    assert eval_typing(GetArg[t, A, Literal[0]]) is int
    assert eval_typing(GetArg[t, A, Literal[-1]]) is int
    assert eval_typing(GetArg[t, A, Literal[1]]) == Never

    t = A
    assert eval_typing(GetArg[t, A, Literal[0]]) is str
    assert eval_typing(GetArg[t, A, Literal[-1]]) is str
    assert eval_typing(GetArg[t, A, Literal[1]]) == Never


def test_eval_getarg_custom_04():
    T = TypeVar("T", default=str)

    class A(Generic[T]):
        pass

    t = A[int]
    assert eval_typing(GetArg[t, A, Literal[0]]) is int
    assert eval_typing(GetArg[t, A, Literal[-1]]) is int
    assert eval_typing(GetArg[t, A, Literal[1]]) == Never

    t = A
    assert eval_typing(GetArg[t, A, Literal[0]]) is str
    assert eval_typing(GetArg[t, A, Literal[-1]]) is str
    assert eval_typing(GetArg[t, A, Literal[1]]) == Never


TestTypeVar = TypeVar("TestTypeVar")


def test_eval_getarg_custom_05():
    # TypeVar declared outside of scope of class
    class ATree(Generic[TestTypeVar]):
        val: list[ATree[TestTypeVar]]

    t = ATree[int]
    assert eval_typing(GetArg[t, ATree, Literal[0]]) is int
    assert eval_typing(GetArg[t, ATree, Literal[-1]]) is int
    assert eval_typing(GetArg[t, ATree, Literal[1]]) == Never

    t = ATree
    assert eval_typing(GetArg[t, ATree, Literal[0]]) is Any
    assert eval_typing(GetArg[t, ATree, Literal[-1]]) is Any
    assert eval_typing(GetArg[t, ATree, Literal[1]]) == Never


def test_eval_getarg_custom_06():
    # TypeVar declared inside scope of class
    A = TypeVar("A")

    class ATree(Generic[A]):
        val: A | list[ATree[A]]

    t = ATree[int]
    assert eval_typing(GetArg[t, ATree, Literal[0]]) is int
    assert eval_typing(GetArg[t, ATree, Literal[-1]]) is int
    assert eval_typing(GetArg[t, ATree, Literal[1]]) == Never

    t = ATree
    assert eval_typing(GetArg[t, ATree, Literal[0]]) is Any
    assert eval_typing(GetArg[t, ATree, Literal[-1]]) is Any
    assert eval_typing(GetArg[t, ATree, Literal[1]]) == Never


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
    assert eval_typing(GetArg[t, ABTree, Literal[0]]) is int
    assert eval_typing(GetArg[t, ABTree, Literal[1]]) is str
    assert eval_typing(GetArg[t, ABTree, Literal[2]]) == Never

    t = ABTree
    assert eval_typing(GetArg[t, ABTree, Literal[0]]) is Any
    assert eval_typing(GetArg[t, ABTree, Literal[1]]) is Any
    assert eval_typing(GetArg[t, ABTree, Literal[2]]) == Never


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
    assert eval_typing(GetArg[t, Container, Literal[0]]) is int
    assert eval_typing(GetArg[t, Container, Literal[-1]]) is int
    assert eval_typing(GetArg[t, Container, Literal[1]]) == Never

    t = Container
    assert eval_typing(GetArg[t, Container, Literal[0]]) is Any
    assert eval_typing(GetArg[t, Container, Literal[-1]]) is Any
    assert eval_typing(GetArg[t, Container, Literal[1]]) == Never


class OuterType:
    class InnerType:
        pass


def test_eval_typename_01():
    d = eval_typing(GetSpecialAttr[int, Literal["__name__"]])
    assert d == Literal["int"]
    d = eval_typing(GetSpecialAttr[str, Literal["__name__"]])
    assert d == Literal["str"]
    d = eval_typing(GetSpecialAttr[list[int], Literal["__name__"]])
    assert d == Literal["list"]
    d = eval_typing(GetSpecialAttr[list[str], Literal["__name__"]])
    assert d == Literal["list"]

    class C:
        pass

    d = eval_typing(GetSpecialAttr[OuterType, Literal["__name__"]])
    assert d == Literal["OuterType"]
    d = eval_typing(GetSpecialAttr[OuterType.InnerType, Literal["__name__"]])
    assert d == Literal["InnerType"]
    d = eval_typing(GetSpecialAttr[C, Literal["__name__"]])
    assert d == Literal["C"]

    d = eval_typing(GetSpecialAttr[GetA1[int, str], Literal["__name__"]])
    assert d == Literal["int"]


def test_eval_typename_02():
    d = eval_typing(GetSpecialAttr[int, Literal["__module__"]])
    assert d == Literal["builtins"]
    d = eval_typing(GetSpecialAttr[str, Literal["__module__"]])
    assert d == Literal["builtins"]
    d = eval_typing(GetSpecialAttr[list[int], Literal["__module__"]])
    assert d == Literal["builtins"]
    d = eval_typing(GetSpecialAttr[list[str], Literal["__module__"]])
    assert d == Literal["builtins"]

    class C:
        pass

    d = eval_typing(GetSpecialAttr[OuterType, Literal["__module__"]])
    assert d == Literal["tests.test_type_eval"]
    d = eval_typing(GetSpecialAttr[OuterType.InnerType, Literal["__module__"]])
    assert d == Literal["tests.test_type_eval"]
    d = eval_typing(GetSpecialAttr[C, Literal["__module__"]])
    assert d == Literal["tests.test_type_eval"]

    d = eval_typing(GetSpecialAttr[GetA1[int, str], Literal["__module__"]])
    assert d == Literal["builtins"]


def test_eval_typename_03():
    d = eval_typing(GetSpecialAttr[int, Literal["__qualname__"]])
    assert d == Literal["int"]
    d = eval_typing(GetSpecialAttr[str, Literal["__qualname__"]])
    assert d == Literal["str"]
    d = eval_typing(GetSpecialAttr[list[int], Literal["__qualname__"]])
    assert d == Literal["list"]
    d = eval_typing(GetSpecialAttr[list[str], Literal["__qualname__"]])
    assert d == Literal["list"]

    class C:
        pass

    d = eval_typing(GetSpecialAttr[OuterType, Literal["__qualname__"]])
    assert d == Literal["OuterType"]
    d = eval_typing(
        GetSpecialAttr[OuterType.InnerType, Literal["__qualname__"]]
    )
    assert d == Literal["OuterType.InnerType"]
    d = eval_typing(GetSpecialAttr[C, Literal["__qualname__"]])
    assert d == Literal["test_eval_typename_03.<locals>.C"]

    d = eval_typing(GetSpecialAttr[GetA1[int, str], Literal["__qualname__"]])
    assert d == Literal["int"]


type _Works[Ts, I] = Literal[True]
type Works[Ts] = _Works[Ts, Length[Ts]]

type _Fails[Ts, I] = Literal[False]
type Fails[Ts] = _Fails[Ts, Literal[0]]


def test_consistency_01():
    t = eval_typing(Works[tuple[int, str]])
    assert t == Literal[True]

    t = eval_typing(Fails[tuple[int, str]])
    assert t == Literal[False]


def test_uppercase_never():
    d = eval_typing(Uppercase[Never])
    assert d is Never


def test_never_is():
    d = eval_typing(IsSub[Never, Never])
    assert d == _BoolLiteral[True]


def test_eval_list_is_sub_01():
    d = eval_typing(list[IsSub[int, str]])
    assert d == list[_BoolLiteral[False]]
    d = eval_typing(list[not IsSub[int, str]])
    assert d == list[_BoolLiteral[True]]


def test_matches_01():
    d = eval_typing(Matches[int, int])
    assert d == _BoolLiteral[True]

    d = eval_typing(Matches[int, str])
    assert d == _BoolLiteral[False]

    d = eval_typing(Matches[str, int])
    assert d == _BoolLiteral[False]


def test_matches_02():
    class A:
        pass

    class B(A):
        pass

    class C(B):
        pass

    class D(A):
        pass

    class X:
        pass

    d = eval_typing(Matches[A, A])
    assert d == _BoolLiteral[True]

    d = eval_typing(Matches[A, B])
    assert d == _BoolLiteral[False]
    d = eval_typing(Matches[B, A])
    assert d == _BoolLiteral[False]
    d = eval_typing(Matches[B, C])
    assert d == _BoolLiteral[False]
    d = eval_typing(Matches[C, B])
    assert d == _BoolLiteral[False]
    d = eval_typing(Matches[C, D])
    assert d == _BoolLiteral[False]
    d = eval_typing(Matches[D, C])
    assert d == _BoolLiteral[False]

    d = eval_typing(Matches[A, X])
    assert d == _BoolLiteral[False]


def test_matches_03():
    class A[T]:
        pass

    class B[T](A[T]):
        pass

    class C(B[int]):
        pass

    class D(A[str]):
        pass

    class X:
        pass

    d = eval_typing(Matches[A[int], A[int]])
    assert d == _BoolLiteral[True]
    d = eval_typing(Matches[A[int], A[str]])
    assert d == _BoolLiteral[True]

    d = eval_typing(Matches[A[int], B[int]])
    assert d == _BoolLiteral[False]
    d = eval_typing(Matches[B[int], A[int]])
    assert d == _BoolLiteral[False]
    d = eval_typing(Matches[A[int], B[str]])
    assert d == _BoolLiteral[False]
    d = eval_typing(Matches[B[str], A[int]])
    assert d == _BoolLiteral[False]
    d = eval_typing(Matches[B[int], C])
    assert d == _BoolLiteral[False]
    d = eval_typing(Matches[C, B[int]])
    assert d == _BoolLiteral[False]
    d = eval_typing(Matches[B[str], C])
    assert d == _BoolLiteral[False]
    d = eval_typing(Matches[C, B[str]])
    assert d == _BoolLiteral[False]
    d = eval_typing(Matches[C, D])
    assert d == _BoolLiteral[False]
    d = eval_typing(Matches[D, C])
    assert d == _BoolLiteral[False]

    d = eval_typing(Matches[A[int], X])
    assert d == _BoolLiteral[False]


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


type NotLiteralGeneric[T] = not T
type AndLiteralGeneric[L, R] = L and R
type OrLiteralGeneric[L, R] = L or R
type LiteralGenericToLiteral[T] = Literal[True] if T else Literal[False]
type NotLiteralGenericToLiteral[T] = Literal[True] if not T else Literal[False]


def test_eval_bool_01():
    d = eval_typing(Bool[Literal[True]])
    assert d == _BoolLiteral[True]

    d = eval_typing(Bool[Literal[False]])
    assert d == _BoolLiteral[False]

    d = eval_typing(Bool[Literal[1]])
    assert d == _BoolLiteral[False]

    d = eval_typing(Bool[Literal[0]])
    assert d == _BoolLiteral[False]

    d = eval_typing(Bool[Literal["true"]])
    assert d == _BoolLiteral[False]

    d = eval_typing(Bool[Literal["false"]])
    assert d == _BoolLiteral[False]

    d = eval_typing(Bool[_BoolLiteral[True]])
    assert d == _BoolLiteral[True]

    d = eval_typing(Bool[_BoolLiteral[False]])
    assert d == _BoolLiteral[False]

    d = eval_typing(Bool[Never])
    assert d == _BoolLiteral[False]

    d = eval_typing(Bool[int])
    assert d == _BoolLiteral[False]

    class C:
        pass

    d = eval_typing(Bool[C])
    assert d == _BoolLiteral[False]

    d = eval_typing(Bool[True])
    assert d == _BoolLiteral[True]

    d = eval_typing(Bool[False])
    assert d == _BoolLiteral[False]


def test_eval_bool_02():
    d = eval_typing(Bool[Literal[True] | Literal[False]])
    assert d == _BoolLiteral[True]
    d = eval_typing(Bool[Literal[False] | Literal[True]])
    assert d == _BoolLiteral[True]
    d = eval_typing(Bool[Literal[True] | Never])
    assert d == _BoolLiteral[True]
    d = eval_typing(Bool[Never | Literal[True]])
    assert d == _BoolLiteral[True]
    d = eval_typing(Bool[Literal[False] | Never])
    assert d == _BoolLiteral[False]
    d = eval_typing(Bool[Never | Literal[False]])
    assert d == _BoolLiteral[False]
    d = eval_typing(Bool[Literal[True] | int])
    assert d == _BoolLiteral[True]
    d = eval_typing(Bool[int | Literal[True]])
    assert d == _BoolLiteral[True]
    d = eval_typing(Bool[Literal[False] | int])
    assert d == _BoolLiteral[False]
    d = eval_typing(Bool[int | Literal[False]])
    assert d == _BoolLiteral[False]
    d = eval_typing(Bool[int | str])
    assert d == _BoolLiteral[False]


def test_eval_bool_03():
    d = eval_typing(NotLiteralGeneric[Bool[Literal[True]]])
    assert d == _BoolLiteral[False]

    d = eval_typing(NotLiteralGeneric[Bool[Literal[False]]])
    assert d == _BoolLiteral[True]


type NestedBool0[T] = Bool[T]
type NestedBool1[T] = NestedBool0[Bool[T]]
type NestedBool2[T] = NestedBool1[Bool[T]]
type NestedBool3[T] = NestedBool2[Bool[T]]
type NestedBool4[T] = NestedBool3[Bool[T]]
type NestedBool5[T] = NestedBool4[Bool[T]]


def test_eval_bool_04():
    d = eval_typing(NestedBool5[Literal[True]])
    assert d == _BoolLiteral[True]

    d = eval_typing(NestedBool5[Literal[False]])
    assert d == _BoolLiteral[False]


type IsIntBool[T] = Bool[IsSub[T, int]]
type IsIntLiteral[T] = Literal[True] if Bool[IsIntBool[T]] else Literal[False]


def test_eval_bool_05():
    d = eval_typing(IsIntLiteral[int])
    assert d == Literal[True]

    d = eval_typing(IsIntLiteral[str])
    assert d == Literal[False]


def test_eval_bool_literal_01():
    d = eval_typing(_BoolLiteral[True])
    assert d == _BoolLiteral[True]
    d = eval_typing(_BoolLiteral[False])
    assert d == _BoolLiteral[False]
    d = eval_typing(_BoolLiteral[1])
    assert d == _BoolLiteral[True]
    d = eval_typing(_BoolLiteral[0])
    assert d == _BoolLiteral[False]
    d = eval_typing(_BoolLiteral[_BoolLiteral[True]])
    assert d == _BoolLiteral[True]
    d = eval_typing(_BoolLiteral[_BoolLiteral[False]])
    assert d == _BoolLiteral[False]


def test_eval_bool_literal_02():
    d = eval_typing(not _BoolLiteral[True])
    assert d == _BoolLiteral[False]

    d = eval_typing(NotLiteralGeneric[_BoolLiteral[True]])
    assert d == _BoolLiteral[False]
    d = eval_typing(NotLiteralGeneric[_BoolLiteral[False]])
    assert d == _BoolLiteral[True]


def test_eval_bool_literal_03():
    d = eval_typing(AndLiteralGeneric[_BoolLiteral[True], _BoolLiteral[True]])
    assert d == _BoolLiteral[True]
    d = eval_typing(AndLiteralGeneric[_BoolLiteral[True], _BoolLiteral[False]])
    assert d == _BoolLiteral[False]
    d = eval_typing(AndLiteralGeneric[_BoolLiteral[False], _BoolLiteral[True]])
    assert d == _BoolLiteral[False]
    d = eval_typing(AndLiteralGeneric[_BoolLiteral[False], _BoolLiteral[False]])
    assert d == _BoolLiteral[False]


def test_eval_bool_literal_04():
    d = eval_typing(OrLiteralGeneric[_BoolLiteral[True], _BoolLiteral[True]])
    assert d == _BoolLiteral[True]
    d = eval_typing(OrLiteralGeneric[_BoolLiteral[True], _BoolLiteral[False]])
    assert d == _BoolLiteral[True]
    d = eval_typing(OrLiteralGeneric[_BoolLiteral[False], _BoolLiteral[True]])
    assert d == _BoolLiteral[True]
    d = eval_typing(OrLiteralGeneric[_BoolLiteral[False], _BoolLiteral[False]])
    assert d == _BoolLiteral[False]


def test_eval_bool_literal_05():
    d = eval_typing(LiteralGenericToLiteral[_BoolLiteral[True]])
    assert d == Literal[True]
    d = eval_typing(LiteralGenericToLiteral[_BoolLiteral[False]])
    assert d == Literal[False]


def test_eval_bool_literal_06():
    d = eval_typing(NotLiteralGenericToLiteral[_BoolLiteral[True]])
    assert d == Literal[False]
    d = eval_typing(NotLiteralGenericToLiteral[_BoolLiteral[False]])
    assert d == Literal[True]


def test_eval_bool_literal_07():
    d = eval_typing(IsSub[_BoolLiteral[True], Literal[True]])
    assert d == _BoolLiteral[True]
    d = eval_typing(IsSub[_BoolLiteral[False], Literal[False]])
    assert d == _BoolLiteral[True]

    d = eval_typing(IsSub[Literal[True], _BoolLiteral[True]])
    assert d == _BoolLiteral[True]
    d = eval_typing(IsSub[Literal[False], _BoolLiteral[False]])
    assert d == _BoolLiteral[True]

    d = eval_typing(IsSubtype[_BoolLiteral[True], Literal[True]])
    assert d == _BoolLiteral[True]
    d = eval_typing(IsSubtype[_BoolLiteral[False], Literal[False]])
    assert d == _BoolLiteral[True]

    d = eval_typing(IsSubtype[Literal[True], _BoolLiteral[True]])
    assert d == _BoolLiteral[True]
    d = eval_typing(IsSubtype[Literal[False], _BoolLiteral[False]])
    assert d == _BoolLiteral[True]

    d = eval_typing(Matches[_BoolLiteral[True], Literal[True]])
    assert d == _BoolLiteral[True]
    d = eval_typing(Matches[_BoolLiteral[False], Literal[False]])
    assert d == _BoolLiteral[True]


def test_eval_bool_literal_error_01():
    with pytest.raises(TypeError, match="Expected literal type, got 'int'"):
        eval_typing(_BoolLiteral[int])


def test_eval_lambda_01():
    type OnlyIntToSet[T] = set[T] if IsSub[T, int] else T

    a = lambda: int
    b = lambda T: T
    c = lambda T: list[T]
    d = lambda T: OnlyIntToSet[T]

    t = eval_typing(_Lambda[a])
    assert t == _Lambda[a]
    assert eval_typing(t()) is int

    t = eval_typing(_Lambda[b])
    assert t == _Lambda[b]
    assert eval_typing(t(int)) is int
    assert eval_typing(t(str)) is str

    t = eval_typing(_Lambda[c])
    assert t == _Lambda[c]
    assert eval_typing(t(int)) == list[int]
    assert eval_typing(t(str)) == list[str]

    t = eval_typing(_Lambda[d])
    assert t == _Lambda[d]
    assert eval_typing(t(int)) == set[int]
    assert eval_typing(t(str)) is str


def test_eval_lambda_02():
    # different lambdas with same bytecode are treated as the same
    a1 = lambda: int
    a2 = lambda: int

    t1 = eval_typing(_Lambda[a1])
    t2 = eval_typing(_Lambda[a2])
    assert t1 == t2

    t = eval_typing(IsSubtype[_Lambda[a1], _Lambda[a2]])
    assert t == _BoolLiteral[True]
    t = eval_typing(IsSubSimilar[_Lambda[a1], _Lambda[a2]])
    assert t == _BoolLiteral[True]
    t = eval_typing(Matches[_Lambda[a1], _Lambda[a2]])
    assert t == _BoolLiteral[True]

    t = eval_typing(IsSubtype[_Lambda[lambda T: T], _Lambda[lambda U: U]])
    assert t == _BoolLiteral[True]
    t = eval_typing(IsSubSimilar[_Lambda[lambda T: T], _Lambda[lambda U: U]])
    assert t == _BoolLiteral[True]
    t = eval_typing(Matches[_Lambda[lambda T: T], _Lambda[lambda U: U]])
    assert t == _BoolLiteral[True]


def test_eval_lambda_03():
    # different lambdas with different bytecode are treated as different
    a1 = lambda: int
    a2 = lambda: str

    t1 = eval_typing(_Lambda[a1])
    t2 = eval_typing(_Lambda[a2])
    assert t1 != t2

    t = eval_typing(IsSubtype[_Lambda[a1], _Lambda[a2]])
    assert t == _BoolLiteral[False]
    t = eval_typing(IsSubSimilar[_Lambda[a1], _Lambda[a2]])
    assert t == _BoolLiteral[False]
    t = eval_typing(Matches[_Lambda[a1], _Lambda[a2]])
    assert t == _BoolLiteral[False]

    t = eval_typing(IsSubtype[_Lambda[lambda T: T], _Lambda[lambda T: list[T]]])
    assert t == _BoolLiteral[False]
    t = eval_typing(
        IsSubSimilar[_Lambda[lambda T: T], _Lambda[lambda T: list[T]]]
    )
    assert t == _BoolLiteral[False]
    t = eval_typing(Matches[_Lambda[lambda T: T], _Lambda[lambda T: list[T]]])
    assert t == _BoolLiteral[False]


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


def test_eval_slice_01():
    t = tuple[Literal[0], Literal[1], Literal[2], Literal[3], Literal[4]]
    d = eval_typing(Slice[t, Literal[1], Literal[3]])
    assert d == tuple[Literal[1], Literal[2]]
    d = eval_typing(Slice[t, Literal[1], Literal[None]])
    assert d == tuple[Literal[1], Literal[2], Literal[3], Literal[4]]
    d = eval_typing(Slice[t, Literal[None], Literal[3]])
    assert d == tuple[Literal[0], Literal[1], Literal[2]]
    d = eval_typing(Slice[t, Literal[None], Literal[None]])
    assert (
        d == tuple[Literal[0], Literal[1], Literal[2], Literal[3], Literal[4]]
    )
    d = eval_typing(Slice[t, Literal[1], Literal[1]])
    assert d == tuple[()]


def test_eval_slice_02():
    t = Literal["abcde"]
    d = eval_typing(Slice[t, Literal[1], Literal[3]])
    assert d == Literal["bc"]
    d = eval_typing(Slice[t, Literal[1], Literal[None]])
    assert d == Literal["bcde"]
    d = eval_typing(Slice[t, Literal[None], Literal[3]])
    assert d == Literal["abc"]
    d = eval_typing(Slice[t, Literal[None], Literal[None]])
    assert d == Literal["abcde"]
    d = eval_typing(Slice[t, Literal[1], Literal[1]])
    assert d == Literal[""]


def test_eval_slice_03():
    d = eval_typing(Slice[int, Literal[1], Literal[2]])
    assert d == Never
    d = eval_typing(Slice[dict[int, str], Literal[1], Literal[2]])
    assert d == Never


def test_eval_literal_idempotent_01():
    t = Literal[int]
    for _ in range(5):
        nt = eval_typing(t)
        assert t == nt
        t = nt


def test_is_literal_true_vs_one():
    assert eval_typing(IsSub[Literal[True], Literal[1]]) == _BoolLiteral[False]


def test_callable_to_signature_01():
    from typemap.type_eval._eval_operators import _callable_type_to_signature

    # Test the example from the docstring:
    # def func(
    #     a: int,
    #     /,
    #     b: int,
    #     c: int = 0,
    #     *args: int,
    #     d: int,
    #     e: int = 0,
    #     **kwargs: int
    # ) -> int:
    callable_type = Callable[
        [
            Param[None, int],
            Param[Literal["b"], int],
            Param[Literal["c"], int, Literal["default"]],
            Param[None, int, Literal["*"]],
            Param[Literal["d"], int, Literal["keyword"]],
            Param[Literal["e"], int, Literal["default", "keyword"]],
            Param[None, int, Literal["**"]],
        ],
        int,
    ]

    sig = _callable_type_to_signature(callable_type)

    params = list(sig.parameters.values())
    assert len(params) == 7

    assert str(sig) == (
        '(_arg0: int, /, b: int, c: int = ..., *args: int, '
        'd: int, e: int = ..., **kwargs: int) -> int'
    )


def test_callable_to_signature_02():
    from typemap.type_eval._eval_operators import _callable_type_to_signature

    class C:
        pass

    callable_type = classmethod[
        C,
        tuple[
            Param[None, int],
            Param[Literal["b"], int],
            Param[Literal["c"], int, Literal["default"]],
            Param[None, int, Literal["*"]],
            Param[Literal["d"], int, Literal["keyword"]],
            Param[Literal["e"], int, Literal["default", "keyword"]],
            Param[None, int, Literal["**"]],
        ],
        int,
    ]
    sig = _callable_type_to_signature(callable_type)
    assert str(sig) == (
        '(cls: tests.test_type_eval.test_callable_to_signature_02.<locals>.C, '
        '_arg1: int, /, b: int, c: int = ..., *args: int, '
        'd: int, e: int = ..., **kwargs: int) -> int'
    )


def test_callable_to_signature_03():
    from typemap.type_eval._eval_operators import _callable_type_to_signature

    class C:
        pass

    callable_type = staticmethod[
        tuple[
            Param[None, int],
            Param[Literal["b"], int],
            Param[Literal["c"], int, Literal["default"]],
            Param[None, int, Literal["*"]],
            Param[Literal["d"], int, Literal["keyword"]],
            Param[Literal["e"], int, Literal["default", "keyword"]],
            Param[None, int, Literal["**"]],
        ],
        int,
    ]
    sig = _callable_type_to_signature(callable_type)
    assert str(sig) == (
        '(_arg0: int, /, b: int, c: int = ..., *args: int, '
        'd: int, e: int = ..., **kwargs: int) -> int'
    )


def test_new_protocol_with_methods_01():
    class C:
        def member_method(self, x: int) -> int: ...
        @classmethod
        def class_method(cls, x: int) -> int: ...
        @staticmethod
        def static_method(x: int) -> int: ...

    res = eval_typing(IndirectProtocol[C])
    fmt = format_helper.format_class(res)
    assert fmt == textwrap.dedent("""\
        class IndirectProtocol[tests.test_type_eval.test_new_protocol_with_methods_01.<locals>.C]:
            def member_method(self: Self, x: int) -> int: ...
            @classmethod
            def class_method(cls: type[typing.Self], x: int) -> int: ...
            @staticmethod
            def static_method(x: int) -> int: ...
    """)


def test_new_protocol_with_methods_02():
    C = NewProtocol[
        Member[
            Literal["member_method"],
            Callable[
                [Param[Literal["self"], Self], Param[Literal["x"], int]], int
            ],
            Literal["ClassVar"],
        ],
        Member[
            Literal["class_method"],
            classmethod[type[Self], tuple[Param[Literal["x"], int]], int],
            Literal["ClassVar"],
        ],
        Member[
            Literal["static_method"],
            staticmethod[tuple[Param[Literal["x"], int]], int],
            Literal["ClassVar"],
        ],
    ]

    res = eval_typing(IndirectProtocol[C])
    fmt = format_helper.format_class(res)
    assert fmt == textwrap.dedent("""\
        class IndirectProtocol[typemap.type_eval._eval_operators.NewProtocol]:
            def member_method(self: Self, x: int) -> int: ...
            @classmethod
            def class_method(cls: type[typing.Self], x: int) -> int: ...
            @staticmethod
            def static_method(x: int) -> int: ...
    """)


##############

type XTest[X] = Annotated[X, 'blah']


class AnnoTest:
    a: XTest[int]
    b: XTest[Literal["test"]]


def test_type_eval_annotated_01():
    res = format_helper.format_class(eval_typing(AnnoTest))

    assert res == textwrap.dedent("""\
        class AnnoTest:
            a: typing.Annotated[int, 'blah']
            b: typing.Annotated[typing.Literal['test'], 'blah']
    """)


def test_type_eval_annotated_02():
    res = eval_typing(IsSub[GetMemberType[AnnoTest, Literal["a"]], int])
    assert res == _BoolLiteral[True]


def test_type_eval_annotated_03():
    res = eval_typing(Uppercase[GetMemberType[AnnoTest, Literal["b"]]])
    assert res == Literal["TEST"]


def test_type_eval_annotated_04():
    res = eval_typing(GetAnnotations[GetMemberType[AnnoTest, Literal["b"]]])
    assert res == Literal["blah"]


##############
# RaiseError tests

from typemap.typing import RaiseError
from typemap.type_eval import TypeMapError


def test_raise_error_basic():
    with pytest.raises(TypeMapError, match="Test error message"):
        eval_typing(RaiseError[Literal["Test error message"]])


def test_raise_error_with_types():
    with pytest.raises(TypeMapError, match="Broadcast mismatch.*int.*str"):
        eval_typing(RaiseError[Literal["Broadcast mismatch"], int, str])


def test_raise_error_with_literal_types():
    with pytest.raises(
        TypeMapError, match="Shape mismatch.*Literal\\[4\\].*Literal\\[3\\]"
    ):
        eval_typing(
            RaiseError[Literal["Shape mismatch"], Literal[4], Literal[3]]
        )
