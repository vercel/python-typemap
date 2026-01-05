import collections
import collections.abc
import contextlib
import functools
import inspect
import itertools
import re
import types
import typing

from typemap import type_eval
from typemap.type_eval import _typing_inspect
from typemap.type_eval._eval_typing import _eval_types
from typemap.typing import (
    Attrs,
    Capitalize,
    FromUnion,
    GetArg,
    GetAttr,
    IsSubSimilar,
    IsSubtype,
    Iter,
    Length,
    Lowercase,
    Member,
    Members,
    NewProtocol,
    Param,
    SpecialFormEllipsis,
    StrConcat,
    StrSlice,
    Uncapitalize,
    Uppercase,
)

##################################################################


def _from_literal(val, ctx):
    val = _eval_types(val, ctx)
    if _typing_inspect.is_literal(val):
        val = val.__args__[0]
    return val


def get_annotated_type_hints(cls, **kwargs):
    """Get the type hints/quals for a cls annotated with definition site.

    This traverses the mro and finds the definition site for each annotation.
    """
    ohints = typing.get_type_hints(cls, **kwargs)
    hints = {}
    for acls in cls.__mro__:
        if not hasattr(acls, "__annotations__"):
            continue
        for k in acls.__annotations__:
            if k not in hints:
                # XXX: TODO: Strip ClassVar/Final
                hints[k] = ohints[k], (), acls

        # Stop early if we are done.
        if len(hints) == len(ohints):
            break
    return hints


def get_annotated_method_hints(tp):
    hints = {}
    for ptp in reversed(tp.mro()):
        for name, attr in ptp.__dict__.items():
            if isinstance(attr, (types.FunctionType, types.MethodType)):
                if attr is typing._no_init_or_replace_init:
                    continue

                hints[name] = (
                    _function_type(attr, is_method=True),
                    ("ClassVar",),
                    ptp,
                )

    return hints


def _union_elems(tp, ctx):
    tp = _eval_types(tp, ctx)
    if tp is typing.Never:
        return ()
    elif isinstance(tp, types.UnionType):
        return tuple(y for x in tp.__args__ for y in _union_elems(x, ctx))
    elif _typing_inspect.is_literal(tp) and len(tp.__args__) > 1:
        return tuple(typing.Literal[x] for x in tp.__args__)
    else:
        return (tp,)


# TODO: Need to be able to do this in type system!
def _mk_union(*parts):
    if not parts:
        return typing.Never
    else:
        return typing.Union[*parts]


def _mk_literal_union(*parts):
    if not parts:
        return typing.Never
    else:
        return typing.Literal[*parts]


def _lift_over_unions(func):
    @functools.wraps(func)
    def wrapper(*args, ctx):
        args2 = [_union_elems(x, ctx) for x in args]
        parts = [func(*x, ctx=ctx) for x in itertools.product(*args2)]
        return _mk_union(*parts)

    return wrapper


##################################################################


@type_eval.register_evaluator(Iter)
def _eval_Iter(tp, *, ctx):
    tp = _eval_types(tp, ctx)
    if (
        _typing_inspect.is_generic_alias(tp)
        and tp.__origin__ is tuple
        and (not tp.__args__ or tp.__args__[-1] is not Ellipsis)
    ):
        return iter(tp.__args__)
    else:
        # XXX: Or should we return []?
        raise TypeError(
            f"Invalid type argument to Iter: {tp} is not a fixed-length tuple"
        )


# N.B: These handle unions on their own


@type_eval.register_evaluator(IsSubtype)
def _eval_IsSubtype(lhs, rhs, *, ctx):
    return type_eval.issubtype(
        _eval_types(lhs, ctx),
        _eval_types(rhs, ctx),
    )


@type_eval.register_evaluator(IsSubSimilar)
def _eval_IsSubSimilar(lhs, rhs, *, ctx):
    return type_eval.issubsimilar(
        _eval_types(lhs, ctx),
        _eval_types(rhs, ctx),
    )


##################################################################


def _function_type(func, *, is_method):
    root = inspect.unwrap(func)
    sig = inspect.signature(root)
    # XXX: __type_params__!!!

    empty = inspect.Parameter.empty

    def _ann(x):
        return typing.Any if x is empty else x

    params = []
    for _i, p in enumerate(sig.parameters.values()):
        # XXX: what should we do about self?
        # should we track classmethod/staticmethod somehow?
        # mypy stores all this stuff in the SymbolNodes (FuncDef, etc),
        # even though it kind of really is a type/descriptor thing
        # if i == 0 and is_method:
        #     continue
        has_name = p.kind in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        )
        quals = []
        if p.kind == inspect.Parameter.VAR_POSITIONAL:
            quals.append("*")
        if p.kind == inspect.Parameter.VAR_KEYWORD:
            quals.append("**")
        if p.default is not empty:
            quals.append("=")
        params.append(
            Param[
                typing.Literal[p.name if has_name else None],
                _ann(p.annotation),
                typing.Literal[*quals] if quals else typing.Never,
            ]
        )

    return typing.Callable[params, _ann(sig.return_annotation)]


@type_eval.register_evaluator(Attrs)
def _eval_Attrs(tp, *, ctx):
    hints = get_annotated_type_hints(tp, include_extras=True)

    return tuple[
        *[
            Member[typing.Literal[n], t, _mk_literal_union(*qs), d]
            for n, (t, qs, d) in hints.items()
        ]
    ]


@type_eval.register_evaluator(Members)
@_lift_over_unions
def _eval_Members(tp, *, ctx):
    hints = {
        **get_annotated_type_hints(tp, include_extras=True),
        **get_annotated_method_hints(tp),
    }

    attrs = [
        Member[typing.Literal[n], t, _mk_literal_union(*qs), d]
        for n, (t, qs, d) in hints.items()
    ]

    return tuple[*attrs]


##################################################################


@type_eval.register_evaluator(FromUnion)
def _eval_FromUnion(tp, *, ctx):
    return tuple[*_union_elems(tp, ctx)]


##################################################################


@type_eval.register_evaluator(GetAttr)
@_lift_over_unions
def _eval_GetAttr(lhs, prop, *, ctx):
    # TODO: the prop missing, etc!
    # XXX: extras?
    name = _from_literal(prop, ctx)
    return typing.get_type_hints(lhs)[name]


def _get_args(tp, base, ctx) -> typing.Any:
    # XXX: check against base!!
    evaled = _eval_types(tp, ctx)

    tp_head = _typing_inspect.get_head(tp)
    base_head = _typing_inspect.get_head(base)
    if not tp_head or not base_head:
        return None

    if tp_head is base_head:
        return typing.get_args(evaled)

    # Scan the fully-annotated MRO to find the base
    elif gen_mro := getattr(evaled, "__generalized_mro__", None):
        for box in gen_mro:
            if box.cls is base_head:
                return tuple(box.args.values())
        return None

    else:
        # or error??
        return None


def _fix_type(tp):
    """Fix up a type getting returned from GetArg

    In particular, this means turning a list into a tuple of the list
    elements and turning ... into SpecialFormEllipsis.
    """
    if isinstance(tp, (tuple, list)):
        return tuple[*tp]
    elif tp is ...:
        return SpecialFormEllipsis
    else:
        return tp


# The number of generic parameters to all the builtin types that had
# subscripting added in PEP 585.
_BUILTIN_GENERIC_ARITIES = {
    tuple: 2,  # variadic, like Callable...
    list: 1,
    dict: 2,
    set: 1,
    frozenset: 1,
    type: 1,
    collections.deque: 1,
    collections.defaultdict: 2,
    collections.OrderedDict: 2,
    collections.Counter: 1,
    collections.ChainMap: 2,
    collections.abc.Awaitable: 1,
    collections.abc.Coroutine: 3,
    collections.abc.AsyncIterable: 1,
    collections.abc.AsyncIterator: 1,
    collections.abc.AsyncGenerator: 2,
    collections.abc.Iterable: 1,
    collections.abc.Iterator: 1,
    collections.abc.Generator: 3,
    collections.abc.Reversible: 1,
    collections.abc.Container: 1,
    collections.abc.Collection: 1,
    collections.abc.Callable: 2,  # special syntax
    collections.abc.Set: 1,
    collections.abc.MutableSet: 1,
    collections.abc.Mapping: 2,
    collections.abc.MutableMapping: 2,
    collections.abc.Sequence: 1,
    collections.abc.MutableSequence: 1,
    collections.abc.KeysView: 1,
    collections.abc.ItemsView: 2,
    collections.abc.ValuesView: 1,
    contextlib.AbstractContextManager: 1,
    contextlib.AbstractAsyncContextManager: 1,
    re.Pattern: 1,
    re.Match: 1,
}


def _get_params(base_head):
    if (params := getattr(base_head, "__parameters__", None)) is not None:
        return params
    elif (params := getattr(base_head, "__type_params__", None)) is not None:
        return params
    else:
        return None


def _get_generic_arity(base_head):
    if (n := _BUILTIN_GENERIC_ARITIES.get(base_head)) is not None:
        return n
    # XXX: check the type?
    elif (n := getattr(base_head, "_nparams", None)) is not None:
        return n
    elif (params := _get_params(base_head)) is not None:
        # TODO: also check for TypeVarTuple!
        return len(params)
    else:
        return -1


def _get_defaults(base_head):
    """Get the *default* type params for a type

    `list` is equivalent to `list[Any]`, so `GetArg[list, list, 0]
    ought to return `Any`, while `GetArg[list, list, 1]` ought to
    return `Never` because the index is invalid.

    Annoyingly we need to consult a table for built-in arities for this.
    """
    arity = _get_generic_arity(base_head)
    if arity < 0:
        return None

    # Callable and tuple need to produce a SpecialFormEllipsis for arg
    # 0 and 1, respectively.
    if base_head is collections.abc.Callable:
        return (SpecialFormEllipsis, typing.Any)
    elif base_head is tuple:
        return (typing.Any, SpecialFormEllipsis)

    if params := _get_params(base_head):
        return tuple(
            typing.Any if t.__default__ == typing.NoDefault else t.__default__
            for t in params
        )

    return (typing.Any,) * arity


@type_eval.register_evaluator(GetArg)
@_lift_over_unions
def _eval_GetArg(tp, base, idx, *, ctx) -> typing.Any:
    base_head = _typing_inspect.get_head(base)
    args = _get_args(tp, base_head, ctx)
    if args == ():
        args = _get_defaults(base_head)
    if args is None:
        return typing.Never

    try:
        return _fix_type(args[_from_literal(idx, ctx)])
    except IndexError:
        return typing.Never


@type_eval.register_evaluator(Length)
@_lift_over_unions
def _eval_Length(tp, *, ctx) -> typing.Any:
    tp = _eval_types(tp, ctx)
    if _typing_inspect.is_generic_alias(tp) and tp.__origin__ is tuple:
        # TODO: Unpack in the middle?
        if not tp.__args__ or tp.__args__[-1] is not Ellipsis:
            return typing.Literal[len(tp.__args__)]
        else:
            return typing.Literal[None]
    else:
        # XXX: Or should we return Never?
        raise TypeError(f"Invalid type argument to Length: {tp} is not a tuple")


def _string_literal_op(typ, op):
    @_lift_over_unions
    def func(*args, ctx):
        return typing.Literal[op(*[_from_literal(x, ctx) for x in args])]

    type_eval.register_evaluator(typ)(func)


_string_literal_op(Uppercase, op=str.upper)
_string_literal_op(Lowercase, op=str.lower)
_string_literal_op(Capitalize, op=str.capitalize)
_string_literal_op(Uncapitalize, op=lambda s: s[0:1].lower() + s[1:])
_string_literal_op(StrConcat, op=lambda s, t: s + t)
_string_literal_op(StrSlice, op=lambda s, start, end: s[start:end])


##################################################################


@type_eval.register_evaluator(NewProtocol)
def _eval_NewProtocol(*etyps: Member, ctx):
    dct: dict[str, object] = {}
    dct["__annotations__"] = {
        # XXX: Should eval_typing on the etyps evaluate the arguments??
        _from_literal(typing.get_args(prop)[0], ctx): _eval_types(
            typing.get_args(prop)[1], ctx
        )
        for prop in etyps
    }

    module_name = __name__
    name = "NewProtocol"

    # If the type evaluation context
    ctx = type_eval._get_current_context()
    if ctx.current_alias:
        if isinstance(ctx.current_alias, types.GenericAlias):
            name = str(ctx.current_alias)
        else:
            name = f"{ctx.current_alias.__name__}[...]"
        module_name = ctx.current_alias.__module__

    dct["__module__"] = module_name

    mcls: type = type(typing.cast(type, typing.Protocol))
    cls = mcls(name, (typing.Protocol,), dct)
    cls = _eval_types(cls, ctx)
    return cls
