import annotationlib

import contextvars
import dataclasses
import functools
import inspect
import sys
import types
import typing


if typing.TYPE_CHECKING:
    from typing import Any

from . import _apply_generic


__all__ = ("eval_typing",)


@dataclasses.dataclass
class EvalContext:
    seen: dict[Any, Any]


# `eval_types()` calls can be nested, context must be preserved
_current_context: contextvars.ContextVar[EvalContext | None] = contextvars.ContextVar(
    "_current_context", default=None
)


def eval_typing(obj: typing.Any):
    ctx = _current_context.get()
    ctx_set = False
    if ctx is None:
        ctx = EvalContext(
            seen=dict(),
        )
        _current_context.set(ctx)
        ctx_set = True

    try:
        return _eval_types(obj, ctx)
    finally:
        if ctx_set:
            _current_context.set(None)


def _eval_types(obj: typing.Any, ctx: EvalContext):
    if obj in ctx.seen:
        return ctx.seen[obj]
    ctx.seen[obj] = evaled = _eval_types_impl(obj, ctx)
    return evaled


@functools.singledispatch
def _eval_types_impl(obj: typing.Any, ctx: EvalContext):
    return obj


@_eval_types_impl.register
def _eval_func(func: types.FunctionType | types.MethodType, ctx: EvalContext):
    root = inspect.unwrap(func)
    annos = typing.get_type_hints(root)

    annos = {name: _eval_types(tp, ctx) for name, tp in annos.items()}

    new_func = types.FunctionType(
        root.__code__, root.__globals__, "__call__", root.__defaults__, ()
    )

    new_func.__name__ = root.__name__
    new_func.__module__ = root.__module__
    new_func.__annotations__ = annos
    new_func.__type_params__ = root.__type_params__

    return new_func


@_eval_types_impl.register
def _eval_type_type(obj: type, ctx: EvalContext):
    if isinstance(obj, type) and issubclass(obj, typing.Generic):
        ret = type(
            obj.__name__,
            (typing.Protocol,),
            {
                "__module__": obj.__module__,
                "__name__": obj.__name__,
            },
        )

        # Need to add it to `seen` to handle recursion
        ctx.seen[obj] = ret
        try:
            ns = _apply_generic.apply(obj)
        except Exception:
            ctx.seen.pop(obj)
            raise

        for k, v in ns.items():
            setattr(ret, k, v)

        return ret

    return obj


@_eval_types_impl.register
def _eval_type_var(obj: typing.TypeVar, ctx: EvalContext):
    return obj


@_eval_types_impl.register
def _eval_type_alias(obj: typing.TypeAliasType, ctx: EvalContext):
    func = obj.evaluate_value
    mod = sys.modules[obj.__module__]
    ff = types.FunctionType(func.__code__, mod.__dict__, None, None, ())
    unpacked = ff(annotationlib.Format.VALUE)
    return _eval_types(unpacked, ctx)


@_eval_types_impl.register
def _eval_generic(obj: types.GenericAlias, ctx: EvalContext):
    if isinstance(obj.__origin__, type):
        # This is a GenericAlias over a Python class, e.g. `dict[str, int]`
        # Let's reconstruct it by evaluating all arguments
        new_args = tuple(_eval_types(arg, ctx) for arg in obj.__args__)
        return obj.__origin__[new_args]

    func = obj.evaluate_value

    args = tuple(types.CellType(_eval_types(arg, ctx)) for arg in obj.__args__)
    mod = sys.modules[obj.__module__]
    ff = types.FunctionType(func.__code__, mod.__dict__, None, None, args)
    unpacked = ff(annotationlib.Format.VALUE)

    ctx.seen[obj] = unpacked
    try:
        evaled = _eval_types(unpacked, ctx)
    except Exception:
        ctx.seen.pop(obj)
        raise

    return evaled


@_eval_types_impl.register
def _eval_union(obj: typing.Union, ctx: EvalContext):  # type: ignore
    new_args = tuple(_eval_types(arg, ctx) for arg in obj.__args__)
    return typing.Union[new_args]
