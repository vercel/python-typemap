import annotationlib

import contextlib
import contextvars
import dataclasses
import functools
import inspect
import sys
import types
import typing

from typing import _GenericAlias  # type: ignore [attr-defined]  # noqa: PLC2701


if typing.TYPE_CHECKING:
    from typing import Any

from . import _apply_generic


__all__ = ("eval_typing",)


_eval_funcs: dict[type, typing.Callable[..., Any]] = {}


def register_evaluator[T: typing.Callable[..., Any]](
    typ: type,
) -> typing.Callable[[T], T]:
    def func(f: T) -> T:
        assert typ not in _eval_funcs
        _eval_funcs[typ] = f
        return f

    return func


# Base type for the proxy classes we generate to hold __annotations__
class _EvalProxy:
    # Make sure __origin__ doesn't show up at runtime...
    if typing.TYPE_CHECKING:
        __origin__: type


@dataclasses.dataclass
class EvalContext:
    # Fully resolved types
    resolved: dict[Any, Any] = dataclasses.field(default_factory=dict)
    # Types that have been seen, but may not be fully resolved
    seen: dict[Any, Any] = dataclasses.field(default_factory=dict)
    # The typing.Any is really a types.FunctionType, but mypy gets
    # confused and wants to treat it as a MethodType.
    current_alias_stack: set[types.GenericAlias | typing.Any] = (
        dataclasses.field(default_factory=set)
    )
    current_alias: types.GenericAlias | typing.Any | None = None

    unwind_stack: set[typing.TypeAliasType | types.GenericAlias] = (
        dataclasses.field(default_factory=set)
    )
    unwinding_until: typing.TypeAliasType | types.GenericAlias | None = None
    known_recursive_types: dict[
        typing.TypeAliasType | types.GenericAlias, typing.Any
    ] = dataclasses.field(default_factory=dict)


# `eval_types()` calls can be nested, context must be preserved
_current_context: contextvars.ContextVar[EvalContext | None] = (
    contextvars.ContextVar("_current_context", default=None)
)


@contextlib.contextmanager
def _ensure_context() -> typing.Iterator[EvalContext]:
    import typemap.typing as nt

    ctx = _current_context.get()
    ctx_set = False
    if ctx is None:
        ctx = EvalContext()
        _current_context.set(ctx)
        ctx_set = True
    evaluator_token = nt.special_form_evaluator.set(
        lambda t: _eval_types(t, ctx)
    )

    try:
        yield ctx
    finally:
        if ctx_set:
            _current_context.set(None)
        nt.special_form_evaluator.reset(evaluator_token)


def _get_current_context() -> EvalContext:
    ctx = _current_context.get()
    if not ctx:
        raise RuntimeError(
            "type_eval._get_current_context() called outside of eval_types()"
        )
    return ctx


@contextlib.contextmanager
def _child_context() -> typing.Iterator[EvalContext]:
    ctx = _current_context.get()
    if ctx is None:
        raise RuntimeError(
            "type_eval._create_child_context() called outside of eval_types()"
        )

    try:
        child_ctx = EvalContext(
            resolved={
                # Drop resolved recursive types.
                # This is to allow other recursive types to expand them out
                # independently. For example, if we have a recursive types
                # A = B|C and B = A|D, we want B to expand even if we already
                # know A.
                k: v
                for k, v in ctx.resolved.items()
                if k not in ctx.known_recursive_types
            },
            seen=ctx.seen.copy(),
            current_alias_stack=ctx.current_alias_stack.copy(),
            current_alias=ctx.current_alias,
            unwind_stack=ctx.unwind_stack.copy(),
            unwinding_until=ctx.unwinding_until,
            known_recursive_types=ctx.known_recursive_types.copy(),
        )
        _current_context.set(child_ctx)
        yield child_ctx
    finally:
        _current_context.set(ctx)


def eval_typing(obj: typing.Any):
    with _ensure_context() as ctx:
        result = _eval_types(obj, ctx)
        if result in ctx.known_recursive_types:
            result = ctx.known_recursive_types[result]
        return result


def _eval_types(obj: typing.Any, ctx: EvalContext):
    # Found a recursive type, we need to unwind it
    if obj in ctx.unwind_stack:
        ctx.unwinding_until = obj
        return obj

    # Don't recurse into any pending alias expansion
    if obj in ctx.current_alias_stack:
        return obj

    # Already resolved or seen, return the result
    if obj in ctx.resolved:
        return ctx.resolved[obj]
    if obj in ctx.seen:
        return ctx.seen[obj]

    if isinstance(obj, typing.TypeAliasType) or (
        isinstance(obj, types.GenericAlias)
        and isinstance(obj.__origin__, typing.TypeAliasType)
    ):
        with _child_context() as child_ctx:
            child_ctx.unwind_stack.add(obj)
            evaled = _eval_types_impl(obj, child_ctx)
    else:
        evaled = _eval_types_impl(obj, ctx)
        child_ctx = None

    # If we have identified a recursive type, discard evaluation results.
    # This prevents external evaluations from being polluted by partial
    # evaluations.
    keep_intermediate = True
    if child_ctx:
        if child_ctx.unwinding_until:
            if child_ctx.unwinding_until == obj:
                # Finished unwinding.
                ctx.known_recursive_types[obj] = evaled
                evaled = obj
                keep_intermediate = False

            else:
                ctx.unwinding_until = child_ctx.unwinding_until

        if keep_intermediate:
            ctx.resolved |= child_ctx.resolved
            ctx.seen |= child_ctx.seen

        ctx.known_recursive_types |= child_ctx.known_recursive_types

    ctx.resolved[obj] = evaled
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
        root.__code__,
        root.__globals__,
        "__call__",
        root.__defaults__,
        (),
        root.__kwdefaults__,
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
            (_EvalProxy,),
            {
                "__module__": obj.__module__,
                "__name__": obj.__name__,
                "__origin__": obj,
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
def _eval_types_generic(obj: types.GenericAlias, ctx: EvalContext):
    new_args = tuple(_eval_types(arg, ctx) for arg in obj.__args__)

    new_obj = obj.__origin__[new_args]  # type: ignore[index]
    if isinstance(obj.__origin__, type):
        # This is a GenericAlias over a Python class, e.g. `dict[str, int]`
        # Let's reconstruct it by evaluating all arguments
        return new_obj

    func = obj.evaluate_value

    args = tuple(types.CellType(_eval_types(arg, ctx)) for arg in obj.__args__)
    mod = sys.modules[obj.__module__]

    old_obj = ctx.current_alias
    ctx.current_alias = new_obj  # alias is the new_obj, so names look better
    ctx.current_alias_stack.add(new_obj)

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
        ctx.current_alias_stack.remove(new_obj)

    return evaled


@_eval_types_impl.register
def _eval_typing_generic(obj: _GenericAlias, ctx: EvalContext):
    # generic *classes* are typing._GenericAlias while generic type
    # aliases are # types.GenericAlias? Why in the world.
    if func := _eval_funcs.get(obj.__origin__):
        new_args = tuple(_eval_types(arg, ctx) for arg in obj.__args__)
        ret = func(*new_args, ctx=ctx)
        # return _eval_types(ret, ctx)  # ???
        return ret

    # TODO: Actually evaluate in this case!
    return obj


@_eval_types_impl.register
def _eval_union(obj: typing.Union, ctx: EvalContext):  # type: ignore
    args: typing.Sequence[typing.Any] = obj.__args__
    new_args = tuple(_eval_types(arg, ctx) for arg in args)
    return typing.Union[new_args]
