import contextvars
import typing
from typing import _GenericAlias  # type: ignore


_SpecialForm: typing.Any = typing._SpecialForm


# TODO: type better
_special_form_evaluator: contextvars.ContextVar[
    typing.Callable[[typing.Any], typing.Any] | None
] = contextvars.ContextVar("special_form_evaluator", default=None)


class _IterGenericAlias(_GenericAlias, _root=True):  # type: ignore[call-arg]
    def __iter__(self):
        evaluator = _special_form_evaluator.get()
        if evaluator:
            return evaluator(self)
        else:
            return iter(typing.TypeVarTuple("_IterDummy"))


class _IsGenericAlias(_GenericAlias, _root=True):  # type: ignore[call-arg]
    def __bool__(self):
        evaluator = _special_form_evaluator.get()
        if evaluator:
            return evaluator(self)
        else:
            return False
