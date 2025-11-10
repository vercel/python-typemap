from dataclasses import dataclass

import functools
import inspect
import itertools
import types
import typing

from typemap import type_eval
from typemap.type_eval import _typing_inspect


_SpecialForm: typing.Any = typing._SpecialForm


class _NoCacheSpecialForm(_SpecialForm, _root=True):  # type: ignore[call-arg]
    def __getitem__(self, parameters):
        return self._getitem(self, parameters)


@dataclass(frozen=True)
class CallSpec:
    pass


@dataclass(frozen=True)
class _CallSpecWrapper:
    _args: tuple[typing.Any]
    _kwargs: dict[str, typing.Any]
    # TODO: Support MethodType!
    _func: types.FunctionType  # | types.MethodType

    @property
    def args(self) -> None:
        pass

    @property
    def kwargs(self) -> None:
        pass


@_SpecialForm
def CallSpecKwargs(self, spec: _CallSpecWrapper):
    ff = types.FunctionType(
        spec._func.__code__,
        spec._func.__globals__,
        spec._func.__name__,
        None,
        (),
    )

    # We can't call `inspect.signature` on `spec` directly --
    # signature() will attempt to resolve annotations and fail.
    # So we run it on a copy of the function that doesn't have
    # annotations set.
    sig = inspect.signature(ff)
    bound = sig.bind(*spec._args, **spec._kwargs)

    # TODO: Get the real type instead of Never
    return tuple[  # type: ignore[misc]
        *[
            Member[
                typing.Literal[name],  # type: ignore[valid-type]
                typing.Never,
            ]
            for name in bound.kwargs
        ]
    ]


##################################################################


def _from_literal(val):
    val = type_eval.eval_typing(val)
    if _typing_inspect.is_literal(val):
        val = val.__args__[0]
    return val


class Member[N: str, T, Q: str = typing.Never, D = typing.Never]:
    pass


type GetName[T: Member] = GetArg[T, Member, 0]  # type: ignore[valid-type]
type GetType[T: Member] = GetArg[T, Member, 1]  # type: ignore[valid-type]
type GetQuals[T: Member] = GetArg[T, Member, 2]  # type: ignore[valid-type]
type GetDefiner[T: Member] = GetArg[T, Member, 3]  # type: ignore[valid-type]


##################################################################


def get_annotated_type_hints(cls, **kwargs):
    """Get the type hints for a cls annotated with definition site.

    This traverses the mro and finds the definition site for each annotation.
    """
    ohints = typing.get_type_hints(cls, **kwargs)
    hints = {}
    for acls in cls.__mro__:
        if not hasattr(acls, "__annotations__"):
            continue
        for k in acls.__annotations__:
            if k not in hints:
                hints[k] = ohints[k], acls

        # Stop early if we are done.
        if len(hints) == len(ohints):
            break
    return hints


def _split_args(func):
    @functools.wraps(func)
    def wrapper(self, arg):
        if isinstance(arg, tuple):
            return func(self, *arg)
        else:
            return func(self, arg)

    return wrapper


def _union_elems(tp):
    tp = type_eval.eval_typing(tp)
    if isinstance(tp, types.UnionType):
        return tuple(y for x in tp.__args__ for y in _union_elems(x))
    elif _typing_inspect.is_literal(tp) and len(tp.__args__) > 1:
        return tuple(typing.Literal[x] for x in tp.__args__)
    else:
        return (tp,)


def _lift_over_unions(func):
    @functools.wraps(func)
    def wrapper(*args):
        args2 = [_union_elems(x) for x in args]
        # XXX: Never
        parts = [func(*x) for x in itertools.product(*args2)]
        return typing.Union[*parts]

    return wrapper


class Attrs[T]:
    pass


@type_eval.register_evaluator(Attrs)
def _eval_attrs(tp):
    hints = get_annotated_type_hints(tp, include_extras=True)

    return tuple[
        *[
            Member[typing.Literal[n], t, typing.Never, d]
            for n, (t, d) in hints.items()
        ]
    ]


class Param[N: str | None, T, Q: str = typing.Never]:
    pass


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


class Members[T]:
    pass


@type_eval.register_evaluator(Members)
@_lift_over_unions
def _eval_members(tp):
    hints = get_annotated_type_hints(tp, include_extras=True)

    attrs = [
        Member[typing.Literal[n], t, typing.Never, d]
        for n, (t, d) in hints.items()
    ]

    for name, attr in tp.__dict__.items():
        if isinstance(attr, (types.FunctionType, types.MethodType)):
            if attr is typing._no_init_or_replace_init:
                continue

            # XXX: populate the source field
            attrs.append(
                Member[
                    typing.Literal[name],
                    _function_type(attr, is_method=True),
                    typing.Literal["ClassVar"],
                ]
            )

    return tuple[*attrs]


##################################################################


# NB - Iter needs to be interpreted, I think!
# XXX: Can we figure a way around this?
@_SpecialForm
def Iter(self, tp):
    tp = type_eval.eval_typing(tp)
    if (
        _typing_inspect.is_generic_alias(tp)
        and tp.__origin__ is tuple
        and (not tp.__args__ or tp.__args__[-1] is not Ellipsis)
    ):
        return tp.__args__
    else:
        # XXX: Or should we return []?
        raise TypeError(
            f"Invalid type argument to Iter: {tp} is not a fixed-length tuple"
        )


class FromUnion[T]:
    pass


@type_eval.register_evaluator(FromUnion)
def _eval_from_union(tp):
    return tuple[*_union_elems(tp)]


##################################################################


class GetAttr[Lhs, Prop]:
    pass


@type_eval.register_evaluator(GetAttr)
@_lift_over_unions
def _eval_GetAttr(lhs, prop):
    # TODO: the prop missing, etc!
    # XXX: extras?
    name = _from_literal(prop)
    return typing.get_type_hints(lhs)[name]


def _get_args(tp, base) -> typing.Any:
    # XXX: check against base!!
    evaled = type_eval.eval_typing(tp)

    tp_head = _typing_inspect.get_head(tp)
    base_head = _typing_inspect.get_head(base)
    # XXX: not sure this is what we want!
    # at the very least we want unions I think
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


class GetArg[Tp, Base, Idx: int]:
    pass


@type_eval.register_evaluator(GetArg)
@_lift_over_unions
def _eval_GetArg(tp, base, idx) -> typing.Any:
    args = _get_args(tp, base)
    if args is None:
        return typing.Never

    try:
        return args[_from_literal(idx)]
    except IndexError:
        return typing.Never


##################################################################

# N.B: These handle unions on their own


# NB - Is needs to be interpreted, I think!
# XXX: Can we figure a way around this?
# By registering a handler??


@_SpecialForm
@_split_args
def IsSubtype(self, lhs, rhs):
    return type_eval.issubtype(
        type_eval.eval_typing(lhs),
        type_eval.eval_typing(rhs),
    )


@_SpecialForm
@_split_args
def IsSubSimilar(self, lhs, rhs):
    return type_eval.issubsimilar(
        type_eval.eval_typing(lhs),
        type_eval.eval_typing(rhs),
    )


Is = IsSubSimilar


##################################################################


class Uppercase[S: str]:
    pass


class Lowercase[S: str]:
    pass


class Capitalize[S: str]:
    pass


class Uncapitalize[S: str]:
    pass


class StrConcat[S: str, T: str]:
    pass


class StrSlice[S: str, Start: int | None, End: int | None]:
    pass


def _string_literal_op(typ, op):
    @_lift_over_unions
    def func(*args):
        return typing.Literal[op(*[_from_literal(x) for x in args])]

    type_eval.register_evaluator(typ)(func)


_string_literal_op(Uppercase, op=str.upper)
_string_literal_op(Lowercase, op=str.lower)
_string_literal_op(Capitalize, op=str.capitalize)
_string_literal_op(Uncapitalize, op=lambda s: s[0:1].lower() + s[1:])
_string_literal_op(StrConcat, op=lambda s, t: s + t)
_string_literal_op(StrSlice, op=lambda s, start, end: s[start:end])


##################################################################


# XXX: We definitely can't use the normal _SpecialForm cache here
# directly, since we depend on the context's current_alias.
# Maybe we can add that to the cache, though.
# (Or maybe we need to never use the cache??)
@_NoCacheSpecialForm
def NewProtocol(self, val: Member | tuple[Member, ...]):
    if not isinstance(val, tuple):
        val = (val,)

    etyps = [type_eval.eval_typing(t) for t in val]

    dct: dict[str, object] = {}
    dct["__annotations__"] = {
        # XXX: Should eval_typing on the etyps evaluate the arguments??
        _from_literal(type_eval.eval_typing(typing.get_args(prop)[0])):
        # XXX: We maybe (probably?) want to eval_typing the RHS, but
        # we have infinite recursion issues in test_eval_types_2...
        # type_eval.eval_typing(typing.get_args(prop)[1])
        typing.get_args(prop)[1]
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
    return cls
