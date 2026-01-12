import typing

from .type_eval._special_form import (
    _IterGenericAlias,
    _IsGenericAlias,
    _SpecialForm,
    _register_bool_special_form,
)

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


@_SpecialForm
def Iter(self, tp):
    return _IterGenericAlias(self, (tp,))


@_SpecialForm
def IsSubtype(self, tps):
    return _IsGenericAlias(self, tps)


@_SpecialForm
def IsSubSimilar(self, tps):
    return _IsGenericAlias(self, tps)


Is = IsSubSimilar


def bool_special_form(cls):
    return _register_bool_special_form(cls)
