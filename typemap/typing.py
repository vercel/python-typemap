import contextvars
import typing
from typing import Literal
from typing import _GenericAlias  # type: ignore

_SpecialForm: typing.Any = typing._SpecialForm

# Not type-level computation but related


class BaseTypedDict(typing.TypedDict):
    pass


class SpecialFormEllipsis:
    pass


###


# We really need to be able to represent generic function types but it
# is a problem for all kinds of reasons...
# Can we bang it into Callable??
class GenericCallable[
    TVs: tuple[typing.TypeVar, ...],
    C: typing.Callable | staticmethod | classmethod,
]:
    pass


###


class InitField[KwargDict: BaseTypedDict]:
    """Base class to support dataclass.Field type initializers!

    Will require some magical treatment in typecheckers...
    """

    __kwargs: KwargDict

    def __init__(self, **kwargs: typing.Unpack[KwargDict]) -> None:  # type: ignore[misc]
        self.__kwargs = kwargs  # type: ignore[assignment]

    def get_kwargs(self) -> KwargDict:
        return self.__kwargs

    def __repr__(self) -> str:
        args = ', '.join(f'{k}={v!r}' for k, v in self.__kwargs.items())
        return f'{type(self).__name__}({args})'


###


class GetAnnotations[T]:
    """Fetch the annotations of a potentially Annotated type, as Literals.

    GetAnnotations[Annotated[int, 'xxx']] = Literal['xxx']
    GetAnnotations[Annotated[int, 'xxx', 5]] = Literal['xxx', 5]
    GetAnnotations[int] = Never
    """


class DropAnnotations[T]:
    """Drop the annotations of a potentially Annotated type

    DropAnnotations[Annotated[int, 'xxx']] = int
    DropAnnotations[Annotated[int, 'xxx', 5]] = int
    DropAnnotations[int] = int
    """


###


MemberQuals = Literal["ClassVar", "Final"]


class Member[
    N: str,
    T,
    Q: MemberQuals = typing.Never,
    I = typing.Never,
    D = typing.Never,
]:
    name: N
    typ: T
    quals: Q
    init: I
    definer: D


ParamQuals = Literal["*", "**", "keyword", "positional", "default"]


class Param[N: str | None, T, Q: ParamQuals = typing.Never]:
    name: N
    typ: T
    quals: Q


type PosParam[T] = Param[Literal[None], T]
type PosDefaultParam[T] = Param[Literal[None], T, Literal["default"]]
type DefaultParam[N: str, T] = Param[N, T, Literal["default"]]
type NamedParam[N: str, T] = Param[N, T, Literal["keyword"]]
type NamedDefaultParam[N: str, T] = Param[N, T, Literal["keyword", "default"]]
type ArgsParam[T] = Param[Literal[None], T, Literal["*"]]
type KwargsParam[T] = Param[Literal[None], T, Literal["**"]]


type GetName[T: Member | Param] = GetAttr[T, Literal["name"]]
type GetType[T: Member | Param] = GetAttr[T, Literal["typ"]]
type GetQuals[T: Member | Param] = GetAttr[T, Literal["quals"]]
type GetInit[T: Member] = GetAttr[T, Literal["init"]]
type GetDefiner[T: Member] = GetAttr[T, Literal["definer"]]


class Attrs[T]:
    pass


class Members[T]:
    pass


class FromUnion[T]:
    pass


class GetAttr[Lhs, Prop]:
    pass


class GetArg[Tp, Base, Idx: int]:
    pass


class GetArgs[Tp, Base]:
    pass


class Length[S: tuple]:
    pass


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


class NewProtocol[*T]:
    pass


##################################################################

# TODO: type better
special_form_evaluator: contextvars.ContextVar[
    typing.Callable[[typing.Any], typing.Any] | None
] = contextvars.ContextVar("special_form_evaluator", default=None)


class _IterGenericAlias(_GenericAlias, _root=True):  # type: ignore[call-arg]
    def __iter__(self):
        evaluator = special_form_evaluator.get()
        if evaluator:
            return evaluator(self)
        else:
            return iter(typing.TypeVarTuple("_IterDummy"))


@_SpecialForm
def Iter(self, tp):
    return _IterGenericAlias(self, (tp,))


class _IsGenericAlias(_GenericAlias, _root=True):  # type: ignore[call-arg]
    def __bool__(self):
        evaluator = special_form_evaluator.get()
        if evaluator:
            return evaluator(self)
        else:
            return False


@_SpecialForm
def IsSubtype(self, tps):
    return _IsGenericAlias(self, tps)


@_SpecialForm
def IsSubSimilar(self, tps):
    return _IsGenericAlias(self, tps)


IsSub = IsSubSimilar
