from ._eval_typing import (
    eval_typing,
    _get_current_context,
    register_evaluator,
    _EvalProxy,
)
from ._apply_generic import flatten_class

# XXX: this needs to go second due to nasty circularity -- try to fix that!!
from ._eval_call import eval_call, eval_type_call
from ._subtype import issubtype
from ._subsim import issubsimilar

# This one is imported for registering handlers
from . import _eval_operators  # noqa


__all__ = (
    "eval_typing",
    "register_evaluator",
    "eval_call",
    "eval_type_call",
    "flatten_class",
    "issubtype",
    "issubsimilar",
    "_EvalProxy",
    "_get_current_context",
)
