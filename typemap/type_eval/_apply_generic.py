import annotationlib
import dataclasses
import inspect
import types
import typing

from . import _eval_typing

if typing.TYPE_CHECKING:
    from typing import Any


@dataclasses.dataclass(frozen=True)
class Boxed:
    cls: type[Any]
    bases: list[Boxed]
    args: dict[Any, Any]

    str_args: dict[str, Any] = dataclasses.field(init=False)

    def __post_init__(self):
        object.__setattr__(
            self,
            "str_args",
            {str(k): v for k, v in self.args.items()},
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


def box(cls: type[Any]) -> Boxed:
    def _box(cls: type[Any], args: dict[str, Any]) -> Boxed:
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
                        boxed_args = {}
                        for param, arg in zip(
                            base_params, obase.__args__, strict=True
                        ):
                            if arg in args:
                                boxed_args[param] = args[arg]
                            else:
                                boxed_args[param] = arg
                    else:
                        boxed_args = {}

                    boxed_bases.append(_box(base, boxed_args))
                else:
                    boxed_bases.append(_box(base, {}))

        return Boxed(cls, boxed_bases, args)

    if isinstance(cls, (typing._GenericAlias, types.GenericAlias)):  # type: ignore[attr-defined]
        # XXX this feels out of place, `box()` needs to only accept types.
        args = dict(
            zip(cls.__origin__.__parameters__, cls.__args__, strict=True)
        )
        cls = cls.__origin__
    else:
        if params := getattr(cls, "__parameters__", None):
            args = {p: p for p in params}
        else:
            args = {}

    return _box(cls, args)


def merge_boxed_mro(seqs: list[list[Boxed]]) -> list[Boxed]:
    res: list[Boxed] = []
    i = 0
    cand: Boxed | None = None
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
    return merge_boxed_mro(
        [[C]] + list(map(_compute_mro, C.bases)) + [list(C.bases)]
    )


def compute_mro(C: type[Any]) -> list[Boxed]:
    return _compute_mro(box(C))


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


def apply(
    cls: type[Any], ctx: _eval_typing.EvalContext
) -> type[_eval_typing._EvalProxy]:
    mro_boxed = compute_mro(cls)

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

    # Run through the mro
    for boxed in reversed(mro_boxed):
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

    for k, v in annos.items():
        annos[k] = _eval_typing._eval_types(v, ctx=ctx)

    for k, v in dct.items():
        dct[k] = _eval_typing._eval_types(v, ctx=ctx)

    dct["__annotations__"] = annos
    dct["__generalized_mro__"] = mro_boxed

    for k, v in dct.items():
        setattr(ret, k, v)

    return ret
