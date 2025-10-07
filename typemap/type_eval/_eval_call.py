import annotationlib
import types
import typing

if typing.TYPE_CHECKING:
    from typing import Any

from typemap import typing as next

from . import _eval_typing


def eval_call(func: types.FunctionType, /, *args: Any, **kwargs: Any) -> Any:
    vars = {}

    params = func.__type_params__
    for p in params:
        if p.__bound__ is next.CallSpec:
            vars[p.__name__] = next._CallSpecWrapper(args, kwargs, func)
        else:
            vars[p.__name__] = p

    try:
        af = func.__annotate__
    except AttributeError:
        raise ValueError("func has no __annotate__ attribute")

    af_args = tuple(types.CellType(vars[name]) for name in af.__code__.co_freevars)

    ff = types.FunctionType(af.__code__, af.__globals__, af.__name__, None, af_args)
    rr = ff(annotationlib.Format.VALUE)

    return _eval_typing.eval_typing(rr["return"])
