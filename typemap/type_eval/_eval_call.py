from dataclasses import dataclass

import annotationlib
import inspect
import types
import typing

from typing import Any

from typemap import typing as next

from . import _eval_typing

RtType = Any


@dataclass(frozen=True, eq=False)
class _CallSpecWrapper:
    _args: tuple[typing.Any]
    _kwargs: dict[str, typing.Any]
    # _args: type[tuple]
    # _kwargs: type

    @property
    def args(self) -> typing.Any:
        return self._args

    @property
    def kwargs(self) -> typing.Any:
        return self._kwargs


def eval_call(func: types.FunctionType, /, *args: Any, **kwargs: Any) -> RtType:
    # N.B: This doesn't *really* work!!
    # TODO: Do Literals for bool, int, str, None?
    arg_types = tuple(type(t) for t in args)
    kwarg_types = {k: type(t) for k, t in kwargs.items()}
    return eval_call_with_types(func, arg_types, kwarg_types)


def _get_bound_args(
    func: types.FunctionType,
    arg_types: tuple[RtType, ...],
    kwarg_types: dict[str, RtType],
) -> inspect.BoundArguments:
    # XXX: I don't think this really does anything useful.
    # We should try to be smarter about this.
    ff = types.FunctionType(
        func.__code__,
        func.__globals__,
        func.__name__,
        None,
        (),
    )

    # We can't call `inspect.signature` on `spec` directly --
    # signature() will attempt to resolve annotations and fail.
    # So we run it on a copy of the function that doesn't have
    # annotations set.
    sig = inspect.signature(ff)
    bound = sig.bind(*arg_types, **kwarg_types)

    return bound


def eval_call_with_types(
    func: types.FunctionType,
    arg_types: tuple[RtType, ...],
    kwarg_types: dict[str, RtType],
) -> RtType:
    vars: dict[str, Any] = {}
    params = func.__type_params__
    for p in params:
        if hasattr(p, "__bound__") and p.__bound__ is next.CallSpec:
            bound = _get_bound_args(func, arg_types, kwarg_types)
            vars[p.__name__] = _CallSpecWrapper(bound.args, bound.kwargs)
        else:
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

    old_obj = ctx.current_alias
    ctx.current_alias = func
    try:
        rr = ff(annotationlib.Format.VALUE)
        return _eval_typing.eval_typing(rr["return"])
    finally:
        ctx.current_alias = old_obj
