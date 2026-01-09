import contextvars
import typing
from typing import _GenericAlias  # type: ignore

_SpecialForm: typing.Any = typing._SpecialForm

# Not type-level computation but related


class BaseTypedDict(typing.TypedDict):
    pass


class SpecialFormEllipsis:
    pass


###

MemberQuals = typing.Literal["ClassVar", "Final"]


class Member[N: str, T, Q: MemberQuals = typing.Never, D = typing.Never]:
    pass


type GetName[T: Member] = GetArg[T, Member, 0]  # type: ignore[valid-type]
type GetType[T: Member] = GetArg[T, Member, 1]  # type: ignore[valid-type]
type GetQuals[T: Member] = GetArg[T, Member, 2]  # type: ignore[valid-type]
type GetDefiner[T: Member] = GetArg[T, Member, 3]  # type: ignore[valid-type]


ParamQuals = typing.Literal["*", "**", "="]


class Param[N: str | None, T, Q: ParamQuals = typing.Never]:
    pass


type GetParamName[T: Param] = GetArg[T, Param, 0]  # type: ignore[valid-type]
type GetParamType[T: Param] = GetArg[T, Param, 1]  # type: ignore[valid-type]
type GetParamQuals[T: Param] = GetArg[T, Param, 2]  # type: ignore[valid-type]


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


class Equals[L, R]:
    pass


class NotEquals[L, R]:
    pass


class GreaterThan[L, R]:
    pass


class LessThan[L, R]:
    pass


class GreaterThanOrEqual[L, R]:
    pass


class LessThanOrEqual[L, R]:
    pass


class Not[T]:
    pass


class And[L, R]:
    pass


class Or[L, R]:
    pass


class If[Cond, Then, Else]:
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


Is = IsSubSimilar
