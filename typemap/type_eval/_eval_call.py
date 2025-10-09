import annotationlib
import types
import typing

if typing.TYPE_CHECKING:
    from typing import Any

from typemap import typing as next

from . import _eval_typing


def eval_call(func: types.FunctionType, /, *args: Any, **kwargs: Any) -> Any:
    with _eval_typing._ensure_context() as ctx:
        return _eval_call(func, ctx, *args, **kwargs)


def _eval_call(
    func: types.FunctionType,
    ctx: _eval_typing.EvalContext,
    /,
    *args: Any,
    **kwargs: Any,
) -> Any:
    vars: dict[str, Any] = {}

    params = func.__type_params__
    for p in params:
        if hasattr(p, "__bound__") and p.__bound__ is next.CallSpec:
            vars[p.__name__] = next._CallSpecWrapper(args, kwargs, func)
        else:
            vars[p.__name__] = p

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
