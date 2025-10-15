# import annotationlib

# import contextlib
# import contextvars
# import dataclasses
# import functools
# import inspect
# import sys
# import types
import typing


# from . import _eval_type
from . import _typing_inspect


__all__ = ("issubtype",)


def issubtype(lhs: typing.Any, rhs: typing.Any) -> bool:
    # TODO: Need to handle a lot of cases!

    # N.B: All of the 'bool's in these are because black otherwise
    # formats the two-conditional chains in an unconscionably bad way.

    # Unions first
    if _typing_inspect.is_union_type(rhs):
        return any(issubtype(lhs, r) for r in typing.get_args(rhs))
    elif _typing_inspect.is_union_type(lhs):
        return all(issubtype(t, rhs) for t in typing.get_args(lhs))

    elif bool(
        _typing_inspect.is_valid_isinstance_arg(lhs)
        and _typing_inspect.is_valid_isinstance_arg(rhs)
    ):
        return issubclass(lhs, rhs)

    # literal <:? literal
    elif bool(
        _typing_inspect.is_literal(lhs) and _typing_inspect.is_literal(rhs)
    ):
        rhs_args = set(typing.get_args(rhs))
        return all(lv in rhs_args for lv in typing.get_args(lhs))

    # XXX: This case is kind of a hack, to support NoLiterals.
    elif rhs is typing.Literal:
        return _typing_inspect.is_literal(lhs)

    # literal <:? type
    elif _typing_inspect.is_literal(lhs):
        return issubtype(type(typing.get_args(lhs)[0]), rhs)

    # C[A] <:? D
    elif bool(
        _typing_inspect.is_generic_alias(lhs)
        # and _typing_inspect.is_valid_isinstance_arg(rhs)
    ):
        # print(lhs)
        # breakpoint()
        return issubclass(lhs.__origin__, rhs)
        # return issubtype(lhs.__origin__, rhs)
        # return issubtype(_typing_inspect.get_origin(lhs), rhs)
    # C <:? D[A]
    elif bool(
        _typing_inspect.is_valid_isinstance_arg(lhs)
        and _typing_inspect.is_generic_alias(rhs)
    ):
        return issubtype(lhs, _typing_inspect.get_origin(rhs))

    # XXX: I think this is probably wrong, but a test currently has
    # an unbound type variable...
    elif _typing_inspect.is_type_var(lhs):
        return lhs is rhs

    # TODO: What to do about C[A] <:? D[B]???

    # TODO: Protocols???

    # TODO: We will need to have some sort of hook to support runtime
    # checking of typechecker extensions.
    #
    # We could have restrictions if we are willing to document them.

    # This will probably fail
    return issubclass(lhs, rhs)
