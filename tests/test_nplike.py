from typing import Literal

from typemap import typing

import pytest

# Begin PEP section


class Array[DType, *Shape]:
    def __add__[*Shape2](
        self, other: Array[DType, *Shape2]
    ) -> Array[DType, *Broadcast[tuple[*Shape], tuple[*Shape2]]]:
        raise BaseException


type MergeOne[T, S] = (
    T
    if typing.Matches[T, S] or typing.Matches[S, Literal[1]]
    else S
    if typing.Matches[T, Literal[1]]
    else typing.RaiseError[Literal["Broadcast mismatch"], T, S]
)

type DropLast[T] = typing.Slice[T, Literal[0], Literal[-1]]
type Last[T] = typing.GetArg[T, tuple, Literal[-1]]

# Matching on Never here is intentional; it prevents infinite
# recursions when T is not a tuple.
type Empty[T] = typing.IsSub[typing.Length[T], Literal[0]]

type Broadcast[T, S] = (
    S
    if typing.Bool[Empty[T]]
    else T
    if typing.Bool[Empty[S]]
    else tuple[
        *Broadcast[DropLast[T], DropLast[S]],
        MergeOne[Last[T], Last[S]],
    ]
)

# End PEP section

type GetElem[T] = typing.GetArg[T, Array, Literal[0]]
type GetShape[T] = typing.Slice[typing.GetArgs[T, Array], Literal[1], None]

type Apply[T, S] = Array[GetElem[T], *Broadcast[GetShape[T], GetShape[S]]]

######
from typemap.type_eval import eval_typing, TypeMapError

from typing import Literal as L


def test_nplike_1():
    a1 = Array[float, L[4], L[1]]
    a2 = Array[float, L[3]]
    res = eval_typing(Apply[a1, a2])

    assert res == Array[float, L[4], L[3]]


def test_nplike_2():
    b1 = Array[float, int, int]
    b2 = Array[float, int]
    res = eval_typing(Apply[b1, b2])

    assert res == Array[float, int, int]


def test_nplike_3():
    c1 = Array[float, L[4], L[1], L[5]]
    c2 = Array[float, L[4], L[3], L[1]]
    res = eval_typing(Apply[c1, c2])

    assert res == Array[float, L[4], L[3], L[5]]


def test_nplike_4():
    err1 = Array[float, L[4], L[2]]
    err2 = Array[float, L[3]]

    with pytest.raises(
        TypeMapError, match=r"Broadcast mismatch:.*Literal\[2\].*Literal\[3\]"
    ):
        eval_typing(Apply[err1, err2])
