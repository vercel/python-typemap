import annotationlib
import dataclasses
import inspect
import types
import typing

from typing import _GenericAlias as typing_GenericAlias  # type: ignore [attr-defined]  # noqa: PLC2701


from . import _eval_typing
from . import _typing_inspect

if typing.TYPE_CHECKING:
    from typing import Any


@dataclasses.dataclass(frozen=True)
class Boxed:
    cls: type[Any]
    bases: list[Boxed]
    args: dict[Any, Any]

    str_args: dict[str, Any] = dataclasses.field(init=False)
    mro: list[Boxed] = dataclasses.field(init=False)

    def __post_init__(self):
        object.__setattr__(
            self,
            "str_args",
            {str(k): v for k, v in self.args.items()},
        )
        object.__setattr__(
            self,
            "mro",
            _compute_mro(self),
        )

    def __repr__(self):
        return f"Boxed<{self.cls} {self.args}>"

    def __hash__(self):
        return hash(self.cls)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Boxed):
            return NotImplemented
        return self.cls == other.cls

    def dump(self, *, _level: int = 0):
        print("    " * _level, self.cls)
        print("    " * _level, self.args)

        for b in self.bases:
            b.dump(_level=_level + 1)


def substitute(ty, args):
    if ty in args:
        return args[ty]
    elif isinstance(ty, (typing_GenericAlias, types.GenericAlias)):
        return ty.__origin__[*[substitute(t, args) for t in ty.__args__]]
    else:
        return ty


def box(cls: type[Any]) -> Boxed:
    def _box(cls: type[Any], args: dict[Any, Any]) -> Boxed:
        boxed_bases: list[Boxed] = []

        orig_bases = cls.__dict__.get("__orig_bases__")
        if orig_bases is None:
            # Regular Python class, not a generic
            for base in cls.__bases__:
                boxed_bases.append(_box(base, {}))
        else:
            assert len(cls.__bases__) == len(orig_bases)
            for i, base in enumerate(cls.__bases__):
                obase = orig_bases[i]

                if issubclass(base, typing.Generic):
                    if base_params := getattr(base, "__parameters__", None):
                        # obase should be _GenericAlias...
                        boxed_args = {}
                        for param, arg in zip(
                            base_params, obase.__args__, strict=True
                        ):
                            boxed_args[param] = substitute(arg, args)
                    else:
                        boxed_args = {}

                    boxed_bases.append(_box(base, boxed_args))
                else:
                    boxed_bases.append(_box(base, {}))

        return Boxed(cls, boxed_bases, args)

    if isinstance(cls, (typing._GenericAlias, types.GenericAlias)):  # type: ignore[attr-defined]
        # XXX this feels out of place, `box()` needs to only accept types.
        # this never gets activated now, but I want to basically
        # support this later -sully
        args = dict(
            zip(cls.__origin__.__parameters__, cls.__args__, strict=True)
        )
        cls = cls.__origin__
    else:
        if params := getattr(cls, "__parameters__", None):
            args = {p: _typing_inspect.param_default(p) for p in params}
        else:
            args = {}

    return _box(cls, args)


def merge_boxed_mro[T](seqs: list[list[T]]) -> list[T]:
    res: list[T] = []
    i = 0
    cand: T | None = None
    while 1:
        nonemptyseqs = [seq for seq in seqs if seq]
        if not nonemptyseqs:
            return res
        i += 1
        for seq in nonemptyseqs:
            cand = seq[0]
            nothead = [s for s in nonemptyseqs if cand in s[1:]]
            if nothead:
                cand = None
            else:
                break
        if cand is None:
            raise TypeError("Inconsistent hierarchy")
        res.append(cand)
        for seq in nonemptyseqs:
            if seq[0] == cand:
                del seq[0]

    raise RuntimeError("unreachable")


def _compute_mro(C: Boxed) -> list[Boxed]:
    return merge_boxed_mro([[C]] + [b.mro for b in C.bases] + [list(C.bases)])


def make_func(
    orig_func: types.FunctionType
    | types.MethodType
    | staticmethod
    | classmethod,
    annos: dict[str, Any],
) -> types.FunctionType:
    func = inspect.unwrap(orig_func)  # type: ignore[arg-type]

    new_func: Any = types.FunctionType(
        func.__code__,
        func.__globals__,
        "__call__",
        func.__defaults__,
        (),
        func.__kwdefaults__,
    )

    new_func.__module__ = func.__module__
    new_func.__name__ = func.__name__
    new_func.__annotations__ = annos
    new_func.__type_params__ = func.__type_params__

    if isinstance(orig_func, staticmethod):
        new_func = staticmethod(new_func)
    elif isinstance(orig_func, classmethod):
        new_func = classmethod(new_func)

    return new_func


def _get_local_defns(boxed: Boxed) -> tuple[dict[str, Any], dict[str, Any]]:
    annos: dict[str, Any] = {}
    dct: dict[str, Any] = {}

    if af := getattr(boxed.cls, "__annotate__", None):
        # Class has annotations, let's resolve generic arguments

        args = tuple(
            types.CellType(
                boxed.cls.__dict__
                if name == "__classdict__"
                else boxed.str_args[name]
            )
            for name in af.__code__.co_freevars
        )

        ff = types.FunctionType(
            af.__code__, af.__globals__, af.__name__, None, args
        )
        rr = ff(annotationlib.Format.VALUE)

        if rr:
            for k, v in rr.items():
                if isinstance(v, str):
                    # Handle cases where annotation is explicitly a string,
                    # e.g.:
                    #
                    #   class Foo[X]:
                    #       x: "Foo[X | None]"

                    annos[k] = eval(v, af.__globals__, boxed.str_args)
                else:
                    annos[k] = v
    elif af := getattr(boxed.cls, "__annotations__", None):
        annos.update(af)

    for name, orig in boxed.cls.__dict__.items():
        if name in typing.EXCLUDED_ATTRIBUTES:  # type: ignore[attr-defined]
            continue

        stuff = inspect.unwrap(orig)

        if isinstance(stuff, types.FunctionType):
            if af := getattr(stuff, "__annotate__", None):
                params = dict(
                    zip(
                        map(str, stuff.__type_params__),
                        stuff.__type_params__,
                        strict=True,
                    )
                )

                args = tuple(
                    types.CellType(
                        boxed.cls.__dict__
                        if name == "__classdict__"
                        else params[name]
                        if name in params
                        else boxed.str_args[name]
                    )
                    for name in af.__code__.co_freevars
                )

                ff = types.FunctionType(
                    af.__code__, af.__globals__, af.__name__, None, args
                )
                rr = ff(annotationlib.Format.VALUE)

                dct[name] = make_func(orig, rr)
            elif af := getattr(stuff, "__annotations__", None):
                dct[name] = stuff

    return annos, dct


def apply(
    cls: type[Any], ctx: _eval_typing.EvalContext
) -> type[_eval_typing._EvalProxy]:
    cls_boxed = box(cls)
    mro_boxed = cls_boxed.mro

    annos: dict[str, Any] = {}
    dct: dict[str, Any] = {}

    # We create it early so we can add it to seen, to handle recursion
    ctx.seen[cls] = ret = type(
        cls.__name__,
        (_eval_typing._EvalProxy,),
        {
            "__module__": cls.__module__,
            "__name__": cls.__name__,
            "__origin__": cls,
        },
    )

    # TODO: I think we want to create the whole mro chain...
    # before we evaluate the contents?

    # Run through the mro
    for boxed in reversed(mro_boxed):
        lannos, ldct = _get_local_defns(boxed)
        annos.update(lannos)
        dct.update(ldct)

    for k, v in annos.items():
        annos[k] = _eval_typing._eval_types(v, ctx=ctx)

    for k, v in dct.items():
        dct[k] = _eval_typing._eval_types(v, ctx=ctx)

    dct["__annotations__"] = annos
    dct["__generalized_mro__"] = mro_boxed

    for k, v in dct.items():
        setattr(ret, k, v)

    return ret
