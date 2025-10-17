from dataclasses import dataclass

import inspect
import types
import typing

from typemap import type_eval
from typemap.type_eval import _typing_inspect


_SpecialForm: typing.Any = typing._SpecialForm


class _NoCacheSpecialForm(_SpecialForm, _root=True):  # type: ignore[call-arg]
    def __getitem__(self, parameters):
        return self._getitem(self, parameters)


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


def _from_literal(val):
    val = type_eval.eval_typing(val)
    if _typing_inspect.is_literal(val):
        val = val.__args__[0]
    return val


class Member[N: str, T]:
    pass


type GetName[T: Member] = GetArg[T, 0]  # type: ignore[valid-type]
type GetType[T: Member] = GetArg[T, 1]  # type: ignore[valid-type]


##################################################################


@_SpecialForm
def Attrs(self, tp):
    # TODO: Support unions
    o = type_eval.eval_typing(tp)
    hints = typing.get_type_hints(o, include_extras=True)
    return tuple[*[Member[typing.Literal[n], t] for n, t in hints.items()]]


##################################################################


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


@_SpecialForm
def FromUnion(self, tp):
    tp = type_eval.eval_typing(tp)
    if isinstance(tp, types.UnionType):
        return tuple[*tp.__args__]
    else:
        return tuple[tp]


##################################################################


@_SpecialForm
def GetAttr(self, arg):
    # TODO: Unions, the prop missing, etc!
    lhs, prop = arg
    # XXX: extras?
    name = _from_literal(type_eval.eval_typing(prop))
    return typing.get_type_hints(type_eval.eval_typing(lhs))[name]


@_SpecialForm
def GetArg(self, arg):
    tp, idx = arg
    args = typing.get_args(type_eval.eval_typing(tp))
    try:
        return args[idx]
    except IndexError:
        return typing.Never


##################################################################


@_SpecialForm
def Is(self, arg):
    lhs, rhs = arg
    return type_eval.issubtype(
        type_eval.eval_typing(lhs),
        type_eval.eval_typing(rhs),
    )


##################################################################


class _StringLiteralOp:
    def __init__(self, op: typing.Callable[[str], str]):
        self.op = op

    def __getitem__(self, arg):
        return typing.Literal[self.op(_from_literal(arg))]


Uppercase = _StringLiteralOp(op=str.upper)
Lowercase = _StringLiteralOp(op=str.lower)
Capitalize = _StringLiteralOp(op=str.capitalize)
Uncapitalize = _StringLiteralOp(op=lambda s: s[0:1].lower() + s[1:])


##################################################################


# XXX: We definitely can't use the normal _SpecialForm cache here
# directly, since we depend on the context's current_alias.
# Maybe we can add that to the cache, though.
# (Or maybe we need to never use the cache??)
@_NoCacheSpecialForm
def NewProtocol(self, val: Member | tuple[Member, ...]):
    if not isinstance(val, tuple):
        val = (val,)

    etyps = [type_eval.eval_typing(t) for t in val]

    dct: dict[str, object] = {}
    dct["__annotations__"] = {
        # XXX: Should eval_typing on the etyps evaluate the arguments??
        _from_literal(type_eval.eval_typing(typing.get_args(prop)[0])):
        # XXX: We maybe (probably?) want to eval_typing the RHS, but
        # we have infinite recursion issues in test_eval_types_2...
        # type_eval.eval_typing(typing.get_args(prop)[1])
        typing.get_args(prop)[1]
        for prop in etyps
    }

    module_name = __name__
    name = "NewProtocol"

    # If the type evaluation context
    ctx = type_eval._get_current_context()
    if ctx.current_alias:
        if isinstance(ctx.current_alias, types.GenericAlias):
            name = str(ctx.current_alias)
        else:
            name = f"{ctx.current_alias.__name__}[...]"
        module_name = ctx.current_alias.__module__

    dct["__module__"] = module_name

    mcls: type = type(typing.cast(type, typing.Protocol))
    cls = mcls(name, (typing.Protocol,), dct)
    return cls
