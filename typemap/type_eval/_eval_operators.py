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
from typemap.type_eval import _apply_generic, _typing_inspect
from typemap.type_eval._eval_typing import _eval_types
from typemap.typing import (
    Attrs,
    Capitalize,
    FromUnion,
    GetArg,
    GetArgs,
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


def _from_literal(val):
    assert _typing_inspect.is_literal(val)
    # XXX: check length?
    return val.__args__[0]


def _eval_literal(val, ctx):
    return _from_literal(_eval_types(val, ctx))


def get_annotated_type_hints(cls, **kwargs):
    """Get the type hints/quals for a cls annotated with definition site.

    This traverses the mro and finds the definition site for each annotation.
    """

    # TODO: Cache the box (slash don't need it??)
    box = _apply_generic.box(cls)

    hints = {}
    for abox in reversed(box.mro):
        acls = abox.alias_type()

        annos, _ = _apply_generic.get_local_defns(abox)
        for k, ty in annos.items():
            quals = set()

            # Strip ClassVar/Final from ty and add them to quals
            while True:
                for form in [typing.ClassVar, typing.Final]:
                    if _typing_inspect.is_special_form(ty, form):
                        quals.add(form.__name__)
                        ty = (
                            typing.get_args(ty)[0]
                            if typing.get_args(ty)
                            else typing.Any
                        )
                        break
                else:
                    break

            hints[k] = ty, tuple(sorted(quals)), acls

    return hints


def get_annotated_method_hints(cls):
    # TODO: Cache the box (slash don't need it??)
    box = _apply_generic.box(cls)

    hints = {}
    for abox in reversed(box.mro):
        acls = abox.alias_type()

        _, dct = _apply_generic.get_local_defns(abox)
        for name, attr in dct.items():
            if isinstance(
                attr,
                (
                    types.FunctionType,
                    types.MethodType,
                    staticmethod,
                    classmethod,
                ),
            ):
                if attr is typing._no_init_or_replace_init:
                    continue

                hints[name] = (
                    _function_type(attr, receiver_type=acls),
                    ("ClassVar",),
                    acls,
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

def _get_quals(quals_type):
    # Extract qualifiers from Literal["*", "**", ...] or Never
    quals: set[str] = set()
    if _typing_inspect.is_literal(quals_type):
        qual_args = typing.get_args(quals_type)
        return set(qual_args)
    else:
        return set()


class _DummyDefault:
    # A dummy class to assign to defaults that will display as '...'
    # Putting actual `...` displays as 'Ellipsis'.
    def __repr__(self):
        return "..."

_DUMMY_DEFAULT = _DummyDefault()


def _callable_type_to_signature(callable_type: object) -> inspect.Signature:
    """Convert a Callable type with Param specs to an inspect.Signature.

    The callable_type should be of the form:
        Callable[
            [
                Param[name, type, quals],
                ...
            ],
            return_type,
        ]

    Where:
        - name is None for positional-only or variadic params, or a string
        - type is the parameter type annotation
        - quals is a Literal with any of: "*", "**", "keyword", "default"
          or Never if no qualifiers
    """
    args = typing.get_args(callable_type)
    if len(args) != 2:
        raise TypeError(f"Expected Callable[[...], ret], got {callable_type}")

    param_types, return_type = args

    # Handle the case where param_types is a list of Param types
    if not isinstance(param_types, (list, tuple)):
        raise TypeError(f"Expected list of Param types, got {param_types}")

    parameters: list[inspect.Parameter] = []
    saw_keyword_only = False

    for param_type in param_types:
        # Extract Param arguments: Param[name, type, quals]
        origin = typing.get_origin(param_type)
        if origin is not Param:
            raise TypeError(f"Expected Param type, got {param_type}")

        param_args = typing.get_args(param_type)
        if len(param_args) < 2:
            raise TypeError(
                f"Param must have at least name and type, got {param_type}"
            )

        name_type = param_args[0]
        annotation = param_args[1]
        quals_type = param_args[2] if len(param_args) > 2 else typing.Never

        # Extract name from Literal[name] or None
        if _typing_inspect.is_literal(name_type):
            name = typing.get_args(name_type)[0]
        else:
            name = None

        # Extract qualifiers from Literal["*", "**", ...] or Never
        quals: set[str] = set()
        if quals_type is not typing.Never:
            if _typing_inspect.is_literal(quals_type):
                qual_args = typing.get_args(quals_type)
                quals = set(qual_args)
            else:
                quals = set()

        # Determine parameter kind and default
        kind: inspect._ParameterKind
        if "**" in quals:
            kind = inspect.Parameter.VAR_KEYWORD
            name = name or "kwargs"
        elif "*" in quals:
            kind = inspect.Parameter.VAR_POSITIONAL
            name = name or "args"
            # XXX: not sure we need this
            saw_keyword_only = True
        elif "keyword" in quals:
            kind = inspect.Parameter.KEYWORD_ONLY
            saw_keyword_only = True
        elif name is None:
            kind = inspect.Parameter.POSITIONAL_ONLY
        elif saw_keyword_only:
            kind = inspect.Parameter.KEYWORD_ONLY
        else:
            kind = inspect.Parameter.POSITIONAL_OR_KEYWORD

        # Handle default value
        default: typing.Any
        if "default" in quals:
            # We don't have the actual default value, use a sentinel
            default = _DUMMY_DEFAULT
        else:
            default = inspect.Parameter.empty

        # Generate a name for positional-only params if needed
        if name is None:
            name = f"_arg{len(parameters)}"

        parameters.append(
            inspect.Parameter(
                name=name,
                kind=kind,
                default=default,
                annotation=annotation,
            )
        )

    return inspect.Signature(
        parameters=parameters,
        return_annotation=return_type,
    )


def _signature_to_function(name: str, sig: inspect.Signature):
    """
    Creates a new function with a specific inspect.Signature.
    """

    def fn(*args, **kwargs):
        raise NotImplementedError

    fn.__name__ = fn.__qualname__ = name
    fn.__signature__ = sig  # type: ignore[attr-defined]
    fn.__annotations__ = {
        p.name: p.annotation
        for p in sig.parameters.values()
        if p.annotation is not inspect.Parameter.empty
    }

    return fn


def _is_pos_only(param):
    name, _, quals = typing.get_args(param)
    name = _from_literal(name)
    return name is None and not (_get_quals(quals) & {"*", "**"})


def _callable_type_to_method(name, typ):
    head = typing.get_origin(typ)
    # XXX: handle other amounts
    if head is classmethod:
        cls, params, ret = typing.get_args(typ)
        # We have to make class positional only if there is some other
        # positional only argument. Annoying!
        pname = "cls" if not any(_is_pos_only(p) for p in typing.get_args(params)) else None
        cls_param = Param[
            typing.Literal[pname],
            type[cls],
            typing.Never,
        ]
        typ = typing.Callable[[cls_param] + list(typing.get_args(params)), ret]
    elif head is staticmethod:
        params, ret = typing.get_args(typ)
        typ = typing.Callable[list(typing.get_args(params)), ret]
    else:
        head = lambda x: x

    return head(_signature_to_function(name, _callable_type_to_signature(typ)))


def _function_type(func, *, receiver_type):
    root = inspect.unwrap(func)
    sig = inspect.signature(root)
    # XXX: __type_params__!!!

    empty = inspect.Parameter.empty

    def _ann(x):
        return typing.Any if x is empty else x

    specified_receiver = receiver_type

    params = []
    for i, p in enumerate(sig.parameters.values()):
        ann = p.annotation
        # Special handling for first argument on methods.
        if i == 0 and receiver_type and not isinstance(func, staticmethod):
            if ann is empty:
                ann = receiver_type
            else:
                specified_receiver = ann

        has_name = p.kind in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        )
        quals = []
        if p.kind == inspect.Parameter.VAR_POSITIONAL:
            quals.append("*")
        if p.kind == inspect.Parameter.VAR_KEYWORD:
            quals.append("**")
        if p.kind == inspect.Parameter.KEYWORD_ONLY:
            quals.append("keyword")
        if p.default is not empty:
            quals.append("default")
        params.append(
            Param[
                typing.Literal[p.name if has_name else None],
                _ann(ann),
                typing.Literal[*quals] if quals else typing.Never,
            ]
        )

    ret = _ann(sig.return_annotation)

    # TODO: Is doing the tuple for staticmethod/classmethod legit?
    # Putting a list in makes it unhashable...
    if isinstance(func, staticmethod):
        return staticmethod[tuple[*params], ret]
    elif isinstance(func, classmethod):
        return classmethod[specified_receiver, tuple[*params[1:]], ret]
    else:
        return typing.Callable[params, ret]


@type_eval.register_evaluator(Attrs)
def _eval_Attrs(tp, *, ctx):
    hints = get_annotated_type_hints(tp, include_extras=True)

    return tuple[
        *[
            Member[
                typing.Literal[n],
                _eval_types(t, ctx),
                _mk_literal_union(*qs),
                d,
            ]
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
        Member[
            typing.Literal[n], _eval_types(t, ctx), _mk_literal_union(*qs), d
        ]
        for n, (t, qs, d) in hints.items()
    ]

    return tuple[*attrs]


##################################################################


@type_eval.register_evaluator(FromUnion)
def _eval_FromUnion(tp, *, ctx):
    if tp in ctx.known_recursive_types:
        return tuple[*_union_elems(ctx.known_recursive_types[tp], ctx)]
    else:
        return tuple[*_union_elems(tp, ctx)]


##################################################################


@type_eval.register_evaluator(GetAttr)
@_lift_over_unions
def _eval_GetAttr(lhs, prop, *, ctx):
    # TODO: the prop missing, etc!
    # XXX: extras?
    name = _eval_literal(prop, ctx)
    return typing.get_type_hints(lhs)[name]


def _get_raw_args(tp, base_head, ctx) -> typing.Any:
    evaled = _eval_types(tp, ctx)

    tp_head = _typing_inspect.get_head(tp)
    if not tp_head or not base_head:
        return None

    if tp_head is base_head:
        return typing.get_args(evaled)

    # Scan the fully-annotated MRO to find the base
    box = _apply_generic.box(tp)
    for anc in box.mro:
        if anc.cls is base_head:
            return tuple(anc.args.values())

    # or error??
    return None


def _get_args(tp, base, ctx) -> typing.Any:
    base_head = _typing_inspect.get_head(base)
    args = _get_raw_args(tp, base, ctx)
    if args == ():
        args = _get_defaults(base_head)
    return args


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
    collections.abc.Callable: 2,  # special syntax
    # TODO: Need special handling for the ParamSpec?
    staticmethod: 2,
    classmethod: 3,
    # Normal and boring stuff
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
        return tuple(_typing_inspect.param_default(p) for p in params)

    return (typing.Any,) * arity


@type_eval.register_evaluator(GetArg)
@_lift_over_unions
def _eval_GetArg(tp, base, idx, *, ctx) -> typing.Any:
    base_head = _typing_inspect.get_head(base)
    args = _get_args(tp, base_head, ctx)
    if args is None:
        return typing.Never

    try:
        return _fix_type(args[_eval_literal(idx, ctx)])
    except IndexError:
        return typing.Never


@type_eval.register_evaluator(GetArgs)
@_lift_over_unions
def _eval_GetArgs(tp, base, *, ctx) -> typing.Any:
    base_head = _typing_inspect.get_head(base)
    args = _get_args(tp, base_head, ctx)
    if args is None:
        return typing.Never
    return tuple[*args]  # type: ignore[valid-type]


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
        return typing.Literal[op(*[_eval_literal(x, ctx) for x in args])]

    type_eval.register_evaluator(typ)(func)


_string_literal_op(Uppercase, op=str.upper)
_string_literal_op(Lowercase, op=str.lower)
_string_literal_op(Capitalize, op=str.capitalize)
_string_literal_op(Uncapitalize, op=lambda s: s[0:1].lower() + s[1:])
_string_literal_op(StrConcat, op=lambda s, t: s + t)
_string_literal_op(StrSlice, op=lambda s, start, end: s[start:end])


##################################################################


def _add_quals(typ, quals):
    for qual in (typing.ClassVar, typing.Final):
        if type_eval.issubsimilar(typing.Literal[qual.__name__], quals):
            typ = qual[typ]
    return typ


def _is_method_like(typ):
    return typing.get_origin(typ) in (
        collections.abc.Callable,
        staticmethod,
        classmethod,
    )


@type_eval.register_evaluator(NewProtocol)
def _eval_NewProtocol(*etyps: Member, ctx):
    dct: dict[str, object] = {}
    dct["__annotations__"] = annos = {}

    for tname, typ, quals, _ in (typing.get_args(prop) for prop in etyps):
        name = _eval_literal(tname, ctx)
        typ = _eval_types(typ, ctx)
        tquals = _eval_types(quals, ctx)

        if type_eval.issubsimilar(
            typing.Literal["ClassVar"], tquals
        ) and _is_method_like(typ):
            dct[name] = _callable_type_to_method(name, typ)
        else:
            annos[name] = _add_quals(typ, tquals)

    module_name = __name__
    name = "NewProtocol"

    # If the type evaluation context
    ctx = type_eval._get_current_context()
    if ctx.current_generic_alias:
        if isinstance(ctx.current_generic_alias, types.GenericAlias):
            name = str(ctx.current_generic_alias)
        else:
            name = f"{ctx.current_generic_alias.__name__}[...]"
        module_name = ctx.current_generic_alias.__module__

    dct["__module__"] = module_name

    mcls: type = type(typing.cast(type, typing.Protocol))
    cls = mcls(name, (typing.Protocol,), dct)
    cls = _eval_types(cls, ctx)
    return cls
