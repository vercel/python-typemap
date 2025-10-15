from dataclasses import dataclass

import inspect
import types
import typing

from typemap import type_eval


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
    name: str


@typing._SpecialForm  # type: ignore[call-arg]
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

    return [_CallKwarg(name=name) for name in bound.kwargs]


##################################################################


def _from_literal(val):
    if isinstance(val, typing._LiteralGenericAlias):  # type: ignore[attr-defined]
        val = val.__args__[0]
    return val


class PropertyMeta(type):
    def __getitem__(cls, val: tuple[str | types.GenericAlias, type]):
        name, type = val
        # We allow str or Literal so that string literals work too
        return cls(name=_from_literal(name), type=type)


@dataclass(frozen=True)
class Property(metaclass=PropertyMeta):
    name: str
    type: type


##################################################################


class DirPropertiesMeta(type):
    def __getitem__(cls, tp):
        # TODO: Support unions
        o = type_eval.eval_typing(tp)
        hints = typing.get_type_hints(o, include_extras=True)
        return [Property(typing.Literal[n], t) for n, t in hints.items()]


class DirProperties(metaclass=DirPropertiesMeta):
    pass


##################################################################

# IDEA: If we wanted to be more like typescript, we could make this
# the only acceptable argument to an `in` loop (and possibly rename it
# Iter?). We'd maybe drop DirProperties and use KeyOf or something
# instead...


class IterUnionMeta(type):
    def __getitem__(cls, tp):
        if isinstance(tp, types.UnionType):
            return tp.__args__
        else:
            return [tp]


class IterUnion(metaclass=IterUnionMeta):
    pass


##################################################################


class GetAttrMeta(type):
    def __getitem__(cls, arg):
        lhs, prop = arg
        # XXX: extras?
        return typing.get_type_hints(lhs)[prop]


class GetAttr(metaclass=GetAttrMeta):
    pass


##################################################################

# The type operators don't really need to be types...
# Maybe we should make all of them like this.


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


class NewProtocolMeta(type):
    def __getitem__(cls, val: list[Property]):
        dct: dict[str, object] = {}
        dct["__annotations__"] = {prop.name: prop.type for prop in val}

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


class NewProtocol(metaclass=NewProtocolMeta):
    pass
