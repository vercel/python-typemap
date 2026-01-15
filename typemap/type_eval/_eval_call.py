import annotationlib
import enum
import inspect
import types
import typing
import typing_extensions

from typing import Any


from . import _eval_typing

RtType = Any

from typing import _UnpackGenericAlias  # type: ignore [attr-defined]  # noqa: PLC2701


def _type(t):
    if t is None or isinstance(t, (int, str, bool, bytes, enum.Enum)):
        return typing.Literal[t]
    else:
        return type(t)


def eval_call(
    func: types.FunctionType | types.MethodType, /, *args: Any, **kwargs: Any
) -> RtType:
    bound_self: Any | None = None
    if isinstance(func, types.MethodType):
        bound_self = func.__self__
        func = func.__func__  # type: ignore[assignment]

    arg_types = tuple(_type(t) for t in args)
    kwarg_types = {k: _type(t) for k, t in kwargs.items()}
    return eval_call_with_types(func, arg_types, kwarg_types, bound_self)


def _get_bound_type_args(
    func: types.FunctionType | types.MethodType,
    arg_types: tuple[RtType, ...],
    kwarg_types: dict[str, RtType],
    bound_self: Any | None = None,
) -> dict[str, RtType]:
    sig = inspect.signature(func)
    bound = (
        sig.bind(bound_self, *arg_types, **kwarg_types)
        if bound_self
        else sig.bind(*arg_types, **kwarg_types)
    )

    vars: dict[str, RtType] = {}

    # Extract type parameters for bound methods
    if bound_self and hasattr(bound_self, '__orig_class__'):
        # Bound to a generic class
        orig_class = bound_self.__orig_class__
        origin = orig_class.__origin__
        type_args = orig_class.__args__

        for type_param, arg in zip(
            origin.__type_params__,
            type_args,
            strict=False,
        ):
            vars[type_param.__name__] = arg

        if hasattr(origin, '__dict__'):
            vars['__classdict__'] = dict(origin.__dict__)
    elif bound_self:
        # Bound to a non-generic class
        bound_class = type(bound_self)
        if hasattr(bound_class, '__dict__'):
            vars['__classdict__'] = dict(bound_class.__dict__)

    # TODO: duplication, error cases
    for param in sig.parameters.values():
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
        elif (
            isinstance(param.annotation, typing.TypeVar)
            and param.name in bound.arguments
        ):
            param_value = bound.arguments[param.name]
            vars[param.annotation.__name__] = param_value
        # TODO: simple bindings to other variables too

    return vars


def eval_call_with_types(
    func: types.FunctionType | types.MethodType,
    arg_types: tuple[RtType, ...],
    kwarg_types: dict[str, RtType],
    bound_self: Any | None = None,
) -> RtType:
    vars: dict[str, Any] = {}
    params = (
        func.__type_params__ if isinstance(func, types.FunctionType) else ()
    )
    vars = _get_bound_type_args(func, arg_types, kwarg_types, bound_self)
    for p in params:
        if p.__name__ not in vars:
            vars[p.__name__] = p

    return eval_call_with_type_vars(func, vars)


def eval_call_with_type_vars(
    func: types.FunctionType | types.MethodType,
    vars: dict[str, RtType],
) -> RtType:
    with _eval_typing._ensure_context() as ctx:
        return _eval_call_with_type_vars(func, vars, ctx)


def _eval_call_with_type_vars(
    func: types.FunctionType | types.MethodType,
    vars: dict[str, RtType],
    ctx: _eval_typing.EvalContext,
) -> RtType:
    try:
        af = (
            func.__annotate__
            if isinstance(func, types.FunctionType)
            else func.__call__.__annotate__
        )
    except AttributeError:
        raise ValueError("func has no __annotate__ attribute")
    if not af:
        raise ValueError("func has no __annotate__ attribute")

    closure_vars_by_name = dict(
        zip(func.__code__.co_freevars, func.__closure__ or (), strict=True)
    )

    af_args = tuple(
        types.CellType(vars[name])
        if name in vars
        else closure_vars_by_name[name]
        for name in af.__code__.co_freevars
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
