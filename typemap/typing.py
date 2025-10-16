from dataclasses import dataclass

import inspect
import types
import typing

from typemap import type_eval


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


@dataclass(frozen=True)
class _CallKwarg:
    _name: str


@_SpecialForm
def CallSpecKwargs(self, spec: _CallSpecWrapper) -> list[_CallKwarg]:
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

    return [_CallKwarg(_name=name) for name in bound.kwargs]


##################################################################


def _from_literal(val):
    if isinstance(val, typing._LiteralGenericAlias):  # type: ignore[attr-defined]
        val = val.__args__[0]
    return val


class PropertyMeta(type):
    def __getitem__(cls, val: tuple[str | types.GenericAlias, type]):
        name, type = val
        # We allow str or Literal so that string literals work too
        return cls(_name=_from_literal(name), _type=type)


@dataclass(frozen=True)
class Property(metaclass=PropertyMeta):
    _name: str
    _type: type


@_SpecialForm
def GetName(self, tp):
    return tp._name


@_SpecialForm
def GetType(self, tp):
    return tp._type


##################################################################


@_SpecialForm
def DirProperties(self, tp):
    # TODO: Support unions
    o = type_eval.eval_typing(tp)
    hints = typing.get_type_hints(o, include_extras=True)
    return [Property(typing.Literal[n], t) for n, t in hints.items()]


##################################################################

# IDEA: If we wanted to be more like typescript, we could make this
# the only acceptable argument to an `in` loop (and possibly rename it
# Iter?). We'd maybe drop DirProperties and use KeyOf or something
# instead...


@_SpecialForm
def IterUnion(self, tp):
    if isinstance(tp, types.UnionType):
        return tp.__args__
    else:
        return [tp]


##################################################################


@_SpecialForm
def GetAttr(self, arg):
    # TODO: Unions, the prop missing, etc!
    lhs, prop = arg
    # XXX: extras?
    return typing.get_type_hints(lhs)[prop]


@_SpecialForm
def GetArg(self, arg):
    tp, idx = arg
    args = typing.get_args(tp)
    try:
        return args[idx]
    except IndexError:
        return typing.Never


##################################################################


@_SpecialForm
def IsSubtype(self, arg):
    lhs, rhs = arg
    # return type_eval.issubtype(
    #     type_eval.eval_typing(lhs), type_eval.eval_typing(rhs)
    # )
    return type_eval.issubtype(lhs, rhs)


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


@_SpecialForm
def NewProtocol(self, val: Property | tuple[Property, ...]):
    if not isinstance(val, tuple):
        val = (val,)

    dct: dict[str, object] = {}
    dct["__annotations__"] = {
        _from_literal(GetName[prop]): GetType[prop] for prop in val
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
