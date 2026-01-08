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

    # We want to resolve recursive type aliases correctly, but not have
    # haphazardly expanded results which vary based on order of evaluation,
    # nesting, etc.
    #
    # To produce consistent results, we leave recursive type aliases unexpanded,
    # unless they are the final result.
    #
    # For example, given A = int|list[A],
    #   A expands to int|list[A]
    #   list[A] remains as list[A]
    #
    # IMPLEMENTATION
    #
    # To achieve this behavior, we resolve recursive type aliases in a way that
    # prevents them from interacting with each other's evaluations.
    #
    # Once a recursive alias is fully resolved, we discard all intermediate
    # evaluations and only keep the final result. We then mark the resolve value
    # for the alias as itself, ensure that external evaluations don't expand it.
    # We keep the actual expanded value in `known_recursive_types` for future
    # reference.
    #
    # We identify recursive type aliases by tracking any aliases we see in
    # `alias_stack`. If an alias is seen again, we know it is a recursive alias
    # and note it in `recursive_type_alias`. When we finally unwind to the
    # previous time we saw the alias, we know it is fully resolved.
    #
    # Intermediate evaluations are discarded because evaluating recursive
    # generic classes use the `seen` dictionary as a cache. Sharing this cache
    # would cause inconsistent expansion results.
    #
    # For example, given A = C|list[B] and B = D|list[A], A|B could expand to
    # C|D|list[D|list[A]]|list[A] which is technically correct, but not
    # consistent in the way we want.
    #
    # The alias stack is also used to evaluate generic classes. The current
    # generic alias is tracked in `current_generic_alias`.
    # See `_eval_types_generic`.
    alias_stack: set[typing.TypeAliasType | types.GenericAlias] = (
        dataclasses.field(default_factory=set)
    )
    recursive_type_alias: typing.TypeAliasType | types.GenericAlias | None = (
        None
    )
    known_recursive_types: dict[
        typing.TypeAliasType | types.GenericAlias, typing.Any
    ] = dataclasses.field(default_factory=dict)

    # The typing.Any is really a types.FunctionType, but mypy gets
    # confused and wants to treat it as a MethodType.
    current_generic_alias: types.GenericAlias | typing.Any | None = None


# `eval_types()` calls can be nested, context must be preserved
_current_context: contextvars.ContextVar[EvalContext | None] = (
    contextvars.ContextVar('_current_context', default=None)
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
                # Drop resolved recursive aliases.
                # This is to allow other recursive aliases to expand them out
                # independently. For example, if we have a recursive types
                # A = B|C and B = A|D, we want B to expand even if we already
                # know A.
                k: v
                for k, v in ctx.resolved.items()
                if k not in ctx.known_recursive_types
            },
            seen=ctx.seen.copy(),
            alias_stack=ctx.alias_stack.copy(),
            recursive_type_alias=ctx.recursive_type_alias,
            known_recursive_types=ctx.known_recursive_types.copy(),
            current_generic_alias=ctx.current_generic_alias,
        )
        _current_context.set(child_ctx)
        yield child_ctx
    finally:
        _current_context.set(ctx)


def eval_typing(obj: typing.Any):
    with _ensure_context() as ctx:
        result = _eval_types(obj, ctx)
        if not isinstance(result, list) and result in ctx.known_recursive_types:
            result = ctx.known_recursive_types[result]
        return result


def _is_type_alias_type(obj: typing.Any) -> bool:
    return isinstance(obj, typing.TypeAliasType) or (
        isinstance(obj, types.GenericAlias)
        and isinstance(obj.__origin__, typing.TypeAliasType)
    )


def _eval_types(obj: typing.Any, ctx: EvalContext):
    # Found a recursive alias, we need to unwind it
    if obj in ctx.alias_stack:
        if _is_type_alias_type(obj):
            ctx.recursive_type_alias = obj
        return obj

    # Already resolved or seen, return the result
    if obj in ctx.resolved:
        return ctx.resolved[obj]
    if obj in ctx.seen:
        return ctx.seen[obj]

    if _is_type_alias_type(obj):
        with _child_context() as child_ctx:
            child_ctx.alias_stack.add(obj)
            evaled = _eval_types_impl(obj, child_ctx)
    else:
        evaled = _eval_types_impl(obj, ctx)
        child_ctx = None

    # If we have identified a recursive alias, discard evaluation results.
    # This prevents external evaluations from being polluted by partial
    # evaluations.
    keep_intermediate = True
    if child_ctx:
        if child_ctx.recursive_type_alias:
            if child_ctx.recursive_type_alias == obj:
                # Finished unwinding.
                ctx.known_recursive_types[obj] = evaled
                evaled = obj
                keep_intermediate = False

            else:
                ctx.recursive_type_alias = child_ctx.recursive_type_alias

        if keep_intermediate:
            ctx.resolved |= child_ctx.resolved
            ctx.seen |= child_ctx.seen

        # In case a child context evaluated a nested recursive alias, we can
        # keep those results as they are already "consistent".
        ctx.resolved |= {x: x for x in child_ctx.known_recursive_types.keys()}
        ctx.known_recursive_types |= child_ctx.known_recursive_types

    ctx.resolved[obj] = evaled
    return evaled


@functools.singledispatch
def _eval_types_impl(obj: typing.Any, ctx: EvalContext):
    return obj


@_eval_types_impl.register
def _eval_func(
    func: types.FunctionType | types.MethodType | staticmethod | classmethod,
    ctx: EvalContext,
):
    root = inspect.unwrap(func)  # type: ignore[arg-type]
    annos = typing.get_type_hints(root)

    annos = {name: _eval_types(tp, ctx) for name, tp in annos.items()}

    return _apply_generic.make_func(func, annos)


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

    with _child_context() as child_ctx:
        child_ctx.current_generic_alias = new_obj
        if not _is_type_alias_type(new_obj):
            # Type alias types are already added in _eval_types
            child_ctx.alias_stack.add(new_obj)

        ff = types.FunctionType(func.__code__, mod.__dict__, None, None, args)
        unpacked = ff(annotationlib.Format.VALUE)

        child_ctx.seen[obj] = unpacked
        evaled = _eval_types(unpacked, child_ctx)

    ctx.seen[obj] = unpacked
    ctx.recursive_type_alias = child_ctx.recursive_type_alias

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
