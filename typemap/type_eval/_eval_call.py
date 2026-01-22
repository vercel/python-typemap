import annotationlib
import collections.abc
import enum
import inspect
import types
import typing
import typing_extensions

from typing import Any


from . import _eval_operators
from . import _eval_typing
from . import _typing_inspect
from ._eval_operators import (
    _callable_type_to_signature,
    _canonicalize_callable_type,
    _function_type,
    _is_method_like,
)
from ._apply_generic import substitute, _get_closure_types

RtType = Any

from typing import _UnpackGenericAlias  # type: ignore [attr-defined]  # noqa: PLC2701


def _type(t):
    if t is None or isinstance(t, (int, str, bool, bytes, enum.Enum)):
        return typing.Literal[t]
    elif isinstance(t, type):
        return type[t]
    elif isinstance(t, types.FunctionType):
        return _function_type(t, receiver_type=None)
    else:
        return type(t)


def eval_call(func: types.FunctionType, /, *args: Any, **kwargs: Any) -> RtType:
    arg_types = tuple(_type(t) for t in args)
    kwarg_types = {k: _type(t) for k, t in kwargs.items()}
    return eval_call_with_types(func, *arg_types, **kwarg_types)


def _get_bound_type_args(
    func: types.FunctionType,
    arg_types: tuple[RtType, ...],
    kwarg_types: dict[str, RtType],
) -> dict[str, RtType]:
    sig = inspect.signature(func)
    bound = sig.bind(*arg_types, **kwarg_types)

    return {
        tv.__name__: tp
        for tv, tp in _get_bound_type_args_from_bound_args(sig, bound).items()
    }


def _get_bound_type_args_from_bound_args(
    sig: inspect.Signature,
    bound: inspect.BoundArguments,
) -> dict[typing.TypeVar | typing.TypeVarTuple, RtType]:
    vars: dict[typing.TypeVar | typing.TypeVarTuple, RtType] = {}
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
            vars[tv] = tuple[tps]  # type: ignore[valid-type]
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
            vars[tv] = tp
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
            vars[tv] = arg.__args__[0]
        # trivial T bindings
        elif isinstance(
            param.annotation, typing.TypeVar
        ) or _typing_inspect.is_generic_alias(param.annotation):
            param_value = bound.arguments[param.name]
            _update_bound_typevar(
                param.name, param.annotation, param_value, vars
            )
        # TODO: simple bindings to other variables too

    return vars


def _update_bound_typevar(
    param_name: str,
    tv: Any,
    param_value: Any,
    vars: dict[typing.TypeVar | typing.TypeVarTuple, RtType],
) -> None:
    if isinstance(tv, typing.TypeVar):
        if tv not in vars:
            vars[tv] = param_value
        elif vars[tv] != param_value:
            raise ValueError(
                f"Type variable {tv.__name__} "
                f"is already bound to {vars[tv].__name__}, "
                f"but got {param_value.__name__}"
            )
    elif _typing_inspect.is_literal(tv):
        if not _typing_inspect.is_literal(param_value):
            raise ValueError(f"Argument type mismatch for {param_name}")
        if not all(p in tv.__args__ for p in param_value.__args__):
            raise ValueError(f"Argument type mismatch for {param_name}")
    elif _typing_inspect.is_generic_alias(tv):
        tv_args = tv.__args__

        param_args: Any | None = None
        if (
            isinstance(tv.__origin__, typing.TypeAliasType)
            and _typing_inspect.is_generic_type_alias(param_value)
            and param_value.__origin__ is tv.__origin__
        ):
            # Type aliases should match their arguments 1 to 1
            # For example, binding C[A] to C[B] should bind A to B
            param_args = param_value.__args__

        elif tv.__origin__ in (typing.Callable, collections.abc.Callable):
            if not (
                _typing_inspect.is_generic_alias(param_value)
                and _is_method_like(param_value)
            ):
                raise ValueError(f"Argument type mismatch for {param_name}")

            # Callables use a list for their params.
            # Convert the params list into a tuple to simplify processing.
            tv_params, tv_ret = typing.get_args(tv)
            tv_args = (tuple[*tv_params], tv_ret)  # type: ignore[valid-type]

            # Canonicalize the param value, it might be a classmethod or
            # staticmethod, both of which can match Callable[[...], _].
            param_value = _canonicalize_callable_type(None, param_value)
            param_params, param_ret = typing.get_args(param_value)
            param_args = (tuple[*param_params], param_ret)  # type: ignore[valid-type]

        else:
            with _eval_typing._ensure_context() as ctx:
                param_args = _eval_operators._get_args(
                    param_value, tv.__origin__, ctx
                )

        if param_args is None:
            raise ValueError(f"Argument type mismatch for {param_name}")

        for p_arg, c_arg in zip(tv_args, param_args, strict=True):
            _update_bound_typevar(param_name, p_arg, c_arg, vars)

    elif tv != param_value:
        raise ValueError(f"Argument type mismatch for {param_name}")


def eval_call_with_types(
    func: types.FunctionType | typing.Callable,
    *arg_types: tuple[RtType, ...],
    **kwarg_types: dict[str, RtType],
) -> RtType:
    if isinstance(func, types.FunctionType):
        vars: dict[str, Any] = _get_bound_type_args(
            func, arg_types, kwarg_types
        )
        for p in func.__type_params__:
            if p.__name__ not in vars:
                vars[p.__name__] = p

        return eval_func_with_type_vars(func, vars)

    else:
        from typemap.typing import GenericCallable

        resolved_callable = _eval_typing.eval_typing(func)

        if (
            _typing_inspect.is_generic_alias(resolved_callable)
            and resolved_callable.__origin__ is GenericCallable
        ):
            _, resolved_callable = typing.get_args(resolved_callable)

        sig = _callable_type_to_signature(resolved_callable)
        bound = sig.bind(*arg_types, **kwarg_types)
        bound_args = _get_bound_type_args_from_bound_args(sig, bound)
        res = substitute(sig.return_annotation, bound_args)

        return _eval_typing.eval_typing(res)


def eval_func_with_type_vars(
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
        af = typing.cast(types.FunctionType, func.__annotate__)
    except AttributeError:
        raise ValueError("func has no __annotate__ attribute")
    if not af:
        raise ValueError("func has no __annotate__ attribute")

    closure_types = _get_closure_types(af)
    for name, value in closure_types.items():
        if name not in vars:
            vars[name] = value

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
