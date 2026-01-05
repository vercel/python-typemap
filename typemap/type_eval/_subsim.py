import typing


from . import _typing_inspect


__all__ = ("issubsimilar",)


def issubsimilar(lhs: typing.Any, rhs: typing.Any) -> bool:
    # TODO: Need to handle some cases

    # N.B: All of the 'bool's in these are because black otherwise
    # formats the two-conditional chains in an unconscionably bad way.

    # Unions first
    if lhs is typing.Never:
        return True
    elif rhs is typing.Never:
        return False

    elif _typing_inspect.is_union_type(rhs):
        return any(issubsimilar(lhs, r) for r in typing.get_args(rhs))
    elif _typing_inspect.is_union_type(lhs):
        return all(issubsimilar(t, rhs) for t in typing.get_args(lhs))

    # For _EvalProxy's just blow through them, since we don't yet care
    # about the attribute types here.
    elif _typing_inspect.is_eval_proxy(lhs):
        return issubsimilar(lhs.__origin__, rhs)
    elif _typing_inspect.is_eval_proxy(rhs):
        return issubsimilar(lhs, rhs.__origin__)

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
        return all(issubsimilar(type(x), rhs) for x in typing.get_args(lhs))

    # C[A] <:? D
    elif bool(
        _typing_inspect.is_generic_alias(lhs)
        and _typing_inspect.is_valid_isinstance_arg(rhs)
    ):
        return issubsimilar(_typing_inspect.get_origin(lhs), rhs)

    # C <:? D[A]
    elif bool(
        _typing_inspect.is_valid_isinstance_arg(lhs)
        and _typing_inspect.is_generic_alias(rhs)
    ):
        return issubsimilar(lhs, _typing_inspect.get_origin(rhs))

    # C[A] <:? D[B] -- just match the heads!
    elif bool(
        _typing_inspect.is_generic_alias(lhs)
        and _typing_inspect.is_generic_alias(rhs)
    ):
        return issubsimilar(
            _typing_inspect.get_origin(lhs), _typing_inspect.get_origin(rhs)
        )

    # XXX: I think this is probably wrong, but a test currently has
    # an unbound type variable...
    elif _typing_inspect.is_type_var(lhs):
        return lhs is rhs

    # Check behavior?
    # TODO: Annotated
    # TODO: tuple
    # TODO: Callable
    # TODO: Any
    # TODO: TypedDict

    # This will often fail -- eventually should return False
    return issubclass(lhs, rhs)
