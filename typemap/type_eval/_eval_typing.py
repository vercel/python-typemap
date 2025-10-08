import annotationlib

import contextlib
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
    current_alias: types.GenericAlias | None = None


# `eval_types()` calls can be nested, context must be preserved
_current_context: contextvars.ContextVar[EvalContext | None] = (
    contextvars.ContextVar("_current_context", default=None)
)


@contextlib.contextmanager
def _ensure_context() -> typing.Iterator[EvalContext]:
    ctx = _current_context.get()
    ctx_set = False
    if ctx is None:
        ctx = EvalContext(
            seen=dict(),
        )
        _current_context.set(ctx)
        ctx_set = True

    try:
        yield ctx
    finally:
        if ctx_set:
            _current_context.set(None)


def _get_current_context() -> EvalContext:
    ctx = _current_context.get()
    if not ctx:
        raise RuntimeError(
            "type_eval._get_current_context() called outside of eval_types()"
        )
    return ctx


def eval_typing(obj: typing.Any):
    with _ensure_context() as ctx:
        return _eval_types(obj, ctx)


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
            (typing.cast(type, typing.Protocol),),
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
    assert obj.__module__  # FIXME: or can this really happen?
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
        return obj.__origin__[new_args]  # type: ignore[index]

    func = obj.evaluate_value

    args = tuple(types.CellType(_eval_types(arg, ctx)) for arg in obj.__args__)
    mod = sys.modules[obj.__module__]

    old_obj = ctx.current_alias
    ctx.current_alias = obj

    try:
        ff = types.FunctionType(func.__code__, mod.__dict__, None, None, args)
        unpacked = ff(annotationlib.Format.VALUE)

        ctx.seen[obj] = unpacked
        evaled = _eval_types(unpacked, ctx)
    except Exception:
        ctx.seen.pop(obj, None)
        raise
    finally:
        ctx.current_alias = old_obj

    return evaled


@_eval_types_impl.register
def _eval_union(obj: typing.Union, ctx: EvalContext):  # type: ignore
    args: typing.Sequence[typing.Any] = obj.__args__
    new_args = tuple(_eval_types(arg, ctx) for arg in args)
    return typing.Union[new_args]
