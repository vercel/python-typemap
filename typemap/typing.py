from dataclasses import dataclass

import functools
import inspect
import types
import typing

from typemap import type_eval
from typemap.type_eval import _typing_inspect


_SpecialForm: typing.Any = typing._SpecialForm


@dataclass(frozen=True)
class CallSpec:
    pass


@dataclass(frozen=True)
class _CallSpecWrapper:
    _args: tuple[typing.Any]
    _kwargs: dict[str, typing.Any]
    # TODO: Support MethodType!
    _func: types.FunctionType  # | types.MethodType

    @property
    def args(self) -> None:
        pass

    @property
    def kwargs(self) -> None:
        pass


@_SpecialForm
def CallSpecKwargs(self, spec: _CallSpecWrapper):
    ff = types.FunctionType(
        spec._func.__code__,
        spec._func.__globals__,
        spec._func.__name__,
        None,
        (),
    )

    # We can't call `inspect.signature` on `spec` directly --
    # signature() will attempt to resolve annotations and fail.
    # So we run it on a copy of the function that doesn't have
    # annotations set.
    sig = inspect.signature(ff)
    bound = sig.bind(*spec._args, **spec._kwargs)

    # TODO: Get the real type instead of Never
    return tuple[  # type: ignore[misc]
        *[
            Member[
                typing.Literal[name],  # type: ignore[valid-type]
                typing.Never,
            ]
            for name in bound.kwargs
        ]
    ]


##################################################################


class Member[N: str, T, Q: str = typing.Never, D = typing.Never]:
    pass


type GetName[T: Member] = GetArg[T, Member, 0]  # type: ignore[valid-type]
type GetType[T: Member] = GetArg[T, Member, 1]  # type: ignore[valid-type]
type GetQuals[T: Member] = GetArg[T, Member, 2]  # type: ignore[valid-type]
type GetDefiner[T: Member] = GetArg[T, Member, 3]  # type: ignore[valid-type]


class Attrs[T]:
    pass


class Param[N: str | None, T, Q: str = typing.Never]:
    pass


class Members[T]:
    pass


class FromUnion[T]:
    pass


class GetAttr[Lhs, Prop]:
    pass


class GetArg[Tp, Base, Idx: int]:
    pass


class Uppercase[S: str]:
    pass


class Lowercase[S: str]:
    pass


class Capitalize[S: str]:
    pass


class Uncapitalize[S: str]:
    pass


class StrConcat[S: str, T: str]:
    pass


class StrSlice[S: str, Start: int | None, End: int | None]:
    pass


class NewProtocol[*T]:
    pass


##################################################################


def _split_args(func):
    @functools.wraps(func)
    def wrapper(self, arg):
        if isinstance(arg, tuple):
            return func(self, *arg)
        else:
            return func(self, arg)

    return wrapper


# NB - Iter needs to be interpreted, I think!
# XXX: Can we figure a way around this?
@_SpecialForm
def Iter(self, tp):
    tp = type_eval.eval_typing(tp)
    if (
        _typing_inspect.is_generic_alias(tp)
        and tp.__origin__ is tuple
        and (not tp.__args__ or tp.__args__[-1] is not Ellipsis)
    ):
        return tp.__args__
    else:
        # XXX: Or should we return []?
        raise TypeError(
            f"Invalid type argument to Iter: {tp} is not a fixed-length tuple"
        )


# N.B: These handle unions on their own


# NB - Is needs to be interpreted, I think!
# XXX: Can we figure a way around this?
# By registering a handler??


@_SpecialForm
@_split_args
def IsSubtype(self, lhs, rhs):
    return type_eval.issubtype(
        type_eval.eval_typing(lhs),
        type_eval.eval_typing(rhs),
    )


@_SpecialForm
@_split_args
def IsSubSimilar(self, lhs, rhs):
    return type_eval.issubsimilar(
        type_eval.eval_typing(lhs),
        type_eval.eval_typing(rhs),
    )


Is = IsSubSimilar
