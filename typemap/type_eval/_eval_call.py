import annotationlib
import enum
import inspect
import types
import typing
import typing_extensions

from typing import Any


from . import _eval_typing
from . import _typing_inspect

RtType = Any

from typing import _UnpackGenericAlias  # type: ignore [attr-defined]  # noqa: PLC2701


def _type(t):
    if t is None or isinstance(t, (int, str, bool, bytes, enum.Enum)):
        return typing.Literal[t]
    elif isinstance(t, type):
        return type[t]
    else:
        return type(t)


def eval_call(func: types.FunctionType, /, *args: Any, **kwargs: Any) -> RtType:
    arg_types = tuple(_type(t) for t in args)
    kwarg_types = {k: _type(t) for k, t in kwargs.items()}
    return eval_call_with_types(func, arg_types, kwarg_types)


def _get_bound_type_args(
    func: types.FunctionType,
    arg_types: tuple[RtType, ...],
    kwarg_types: dict[str, RtType],
) -> dict[str, RtType]:
    sig = inspect.signature(func)
    bound = sig.bind(*arg_types, **kwarg_types)

    vars: dict[str, RtType] = {}
    # TODO: duplication, error cases
    for param in sig.parameters.values():
        # Unpack[TypeVarType] for *args
        if (
            param.kind == inspect.Parameter.VAR_POSITIONAL
            # XXX: typing_extensions also
            and isinstance(param.annotation, _UnpackGenericAlias)
            and param.annotation.__args__
            and (tv := param.annotation.__args__[0])
            # XXX: should we allow just a regular one with a tuple bound also?
            # maybe! it would match what I want to do for kwargs!
            and isinstance(tv, typing.TypeVarTuple)
        ):
            tps = bound.arguments.get(param.name, ())
            vars[tv.__name__] = tuple[tps]  # type: ignore[valid-type]
        # Unpack[T] for **kwargs
        elif (
            param.kind == inspect.Parameter.VAR_KEYWORD
            # XXX: typing_extensions also
            and isinstance(param.annotation, _UnpackGenericAlias)
            and param.annotation.__args__
            and (tv := param.annotation.__args__[0])
            # XXX: should we allow just a regular one with a tuple bound also?
            # maybe! it would match what I want to do for kwargs!
            and isinstance(tv, typing.TypeVar)
            and tv.__bound__
            and typing_extensions.is_typeddict(tv.__bound__)
        ):
            tp = typing.TypedDict(f"**{param.name}", bound.kwargs)  # type: ignore[misc, operator]
            vars[tv.__name__] = tp
        # trivial type[T] bindings
        elif (
            _typing_inspect.is_generic_alias(param.annotation)
            and param.annotation.__origin__ is type
            and (tv := param.annotation.__args__[0])
            and isinstance(tv, typing.TypeVar)
            and (arg := bound.arguments.get(param.name))
            and _typing_inspect.is_generic_alias(arg)
            and arg.__origin__ is type
        ):
            vars[tv.__name__] = arg.__args__[0]
        # trivial T bindings
        elif (
            isinstance(param.annotation, typing.TypeVar)
            and param.name in bound.arguments
        ):
            param_value = bound.arguments[param.name]
            vars[param.annotation.__name__] = param_value
        # TODO: simple bindings to other variables too

    return vars


def eval_call_with_types(
    func: types.FunctionType,
    arg_types: tuple[RtType, ...],
    kwarg_types: dict[str, RtType],
) -> RtType:
    vars: dict[str, Any] = {}
    params = func.__type_params__
    vars = _get_bound_type_args(func, arg_types, kwarg_types)
    for p in params:
        if p.__name__ not in vars:
            vars[p.__name__] = p

    return eval_call_with_type_vars(func, vars)


def eval_call_with_type_vars(
    func: types.FunctionType, vars: dict[str, RtType]
) -> RtType:
    with _eval_typing._ensure_context() as ctx:
        return _eval_call_with_type_vars(func, vars, ctx)


def _eval_call_with_type_vars(
    func: types.FunctionType,
    vars: dict[str, RtType],
    ctx: _eval_typing.EvalContext,
) -> RtType:
    try:
        af = func.__annotate__
    except AttributeError:
        raise ValueError("func has no __annotate__ attribute")
    if not af:
        raise ValueError("func has no __annotate__ attribute")

    af_args = tuple(
        types.CellType(vars[name]) for name in af.__code__.co_freevars
    )

    ff = types.FunctionType(
        af.__code__, af.__globals__, af.__name__, None, af_args
    )

    old_obj = ctx.current_generic_alias
    ctx.current_generic_alias = func
    try:
        rr = ff(annotationlib.Format.VALUE)
        return _eval_typing.eval_typing(rr["return"])
    finally:
        ctx.current_generic_alias = old_obj
