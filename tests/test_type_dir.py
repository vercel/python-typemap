import textwrap
import typing
from typing import Literal, Never, TypeVar, Union


from typemap.type_eval import eval_typing
from typemap.typing import (
    Attrs,
    FromUnion,
    GetArg,
    GetName,
    GetQuals,
    GetType,
    Is,
    Iter,
    Member,
    Members,
    NewProtocol,
    Uppercase,
)

from . import format_helper

type OrGotcha[K] = K | Literal['gotcha!']

type StrForInt[X] = (str | OrGotcha[X]) if X is int else (X | OrGotcha[X])


class Ordinary:
    ordinary: str


class AnotherBase[I]:
    iii: OrGotcha[StrForInt[I]]


class Base[T]:
    # This K is dodgy
    K = TypeVar("K")

    t: dict[str, StrForInt[T]]
    kkk: K

    fin: typing.Final[int]

    def foo(self, a: T | None, *, b: int = 0) -> dict[str, T]:
        pass

    def base[Z](self, a: T | Z | None, b: K) -> dict[str, T | Z]:
        pass

    @classmethod
    def cbase(cls, a: T | None, b: K) -> dict[str, T]:
        pass

    @staticmethod
    def sbase[Z](a: OrGotcha[T] | Z | None, b: K) -> dict[str, T | Z]:
        pass


class Wrapper[X](Base[X], AnotherBase[X]):
    x: "Wrapper[X | None]"


class Mine(Wrapper[int]):
    pass


class Last[O]:
    last: O | Literal[True]


class Final(Mine, Ordinary, Wrapper[float], AnotherBase[float], Last[int]):
    pass


type BaseArg[T] = GetArg[T, Base, 0] if Is[T, Base] else Never


type AllOptional[T] = NewProtocol[
    *[
        Member[GetName[p], GetType[p] | None, GetQuals[p]]
        for p in Iter[Attrs[T]]
    ]
]

type OptionalFinal = AllOptional[Final]


type Capitalize[T] = NewProtocol[
    *[
        Member[Uppercase[GetName[p]], GetType[p], GetQuals[p]]
        for p in Iter[Attrs[T]]
    ]
]

type Prims[T] = NewProtocol[
    *[p for p in Iter[Attrs[T]] if Is[GetType[p], int | str]]
]

type NoLiterals1[T] = NewProtocol[
    *[
        Member[
            GetName[p],
            Union[
                *[
                    t
                    for t in Iter[FromUnion[GetType[p]]]
                    # XXX: 'typing.Literal' is not *really* a type...
                    # Maybe we can't do this, which maybe is fine.
                    if not Is[t, Literal]
                ]
            ],
            GetQuals[p],
        ]
        for p in Iter[Attrs[T]]
    ]
]


# Try to implement IsLiteral. This is basically what is recommended
# for doing it in TS.
# XXX: This doesn't work in python! We can subtype str!
type IsLiteral[T] = (
    Literal[True]
    if (
        (Is[T, str] and not Is[str, T])
        or (Is[T, bytes] and not Is[bytes, T])
        or (Is[T, bool] and not Is[bool, T])
        or (Is[T, int] and not Is[int, T])
        # XXX: enum, None
    )
    else Literal[False]
)

type NoLiterals2[T] = NewProtocol[
    *[
        Member[
            GetName[p],
            Union[
                *[
                    t
                    for t in Iter[FromUnion[GetType[p]]]
                    # XXX: 'typing.Literal' is not *really* a type...
                    # Maybe we can't do this, which maybe is fine.
                    # if not IsSubtype[t, Literal]
                    if not Is[IsLiteral[t], Literal[True]]
                ]
            ],
            GetQuals[p],
        ]
        for p in Iter[Attrs[T]]
    ]
]


# Subtyping this forces real type evaluation
class Eval[T]:
    pass


class Loop(Eval[int]):
    loop: Loop


class Foo(Eval[int]):
    bar: Bar


class Bar(Eval[float]):
    foo: Foo


def test_type_dir_link_1():
    d = eval_typing(Loop)
    loop = d.__annotations__["loop"]
    assert loop is d
    assert loop is not Foo


def test_type_dir_link_2():
    d = eval_typing(Foo)
    loop = d.__annotations__["bar"].__annotations__["foo"]
    assert loop is d
    assert loop is not Foo


def test_type_dir_1():
    d = eval_typing(Final)

    assert format_helper.format_class(d) == textwrap.dedent("""\
        class Final:
            last: int | typing.Literal[True]
            iii: str | int | typing.Literal['gotcha!']
            t: dict[str, str | int | typing.Literal['gotcha!']]
            kkk: ~K
            fin: typing.Final[int]
            x: tests.test_type_dir.Wrapper[int | None]
            ordinary: str
            def foo(self, a: int | None, *, b: int = 0) -> dict[str, int]: ...
            def base[Z](self, a: int | Z | None, b: ~K) -> dict[str, int | Z]: ...
            @classmethod
            def cbase(cls, a: int | None, b: ~K) -> dict[str, int]: ...
            @staticmethod
            def sbase[Z](a: int | Literal['gotcha!'] | Z | None, b: ~K) -> dict[str, int | Z]: ...
    """)


def test_type_dir_2():
    d = eval_typing(OptionalFinal)

    # XXX: `Atrs` skips methods, true to its name. Perhaps we just need
    #      `Members` that would iterate over everything
    assert format_helper.format_class(d) == textwrap.dedent("""\
        class AllOptional[tests.test_type_dir.Final]:
            last: int | typing.Literal[True] | None
            iii: str | int | typing.Literal['gotcha!'] | None
            t: dict[str, str | int | typing.Literal['gotcha!']] | None
            kkk: ~K | None
            fin: typing.Final[int | None]
            x: tests.test_type_dir.Wrapper[int | None] | None
            ordinary: str | None
    """)


def test_type_dir_3():
    d = eval_typing(Capitalize[Final])

    assert format_helper.format_class(d) == textwrap.dedent("""\
        class Capitalize[tests.test_type_dir.Final]:
            LAST: int | typing.Literal[True]
            III: str | int | typing.Literal['gotcha!']
            T: dict[str, str | int | typing.Literal['gotcha!']]
            KKK: ~K
            FIN: typing.Final[int]
            X: tests.test_type_dir.Wrapper[int | None]
            ORDINARY: str
    """)


def test_type_dir_4():
    d = eval_typing(Prims[Final])

    assert format_helper.format_class(d) == textwrap.dedent("""\
        class Prims[tests.test_type_dir.Final]:
            last: int | typing.Literal[True]
            fin: typing.Final[int]
            ordinary: str
    """)


def test_type_dir_5():
    global fuck
    d = eval_typing(NoLiterals1[Final])

    assert format_helper.format_class(d) == textwrap.dedent("""\
        class NoLiterals1[tests.test_type_dir.Final]:
            last: int
            iii: str | int
            t: dict[str, str | int | typing.Literal['gotcha!']]
            kkk: ~K
            fin: typing.Final[int]
            x: tests.test_type_dir.Wrapper[int | None]
            ordinary: str
    """)


def test_type_dir_6():
    d = eval_typing(NoLiterals2[Final])

    assert format_helper.format_class(d) == textwrap.dedent("""\
        class NoLiterals2[tests.test_type_dir.Final]:
            last: int
            iii: str | int
            t: dict[str, str | int | typing.Literal['gotcha!']]
            kkk: ~K
            fin: typing.Final[int]
            x: tests.test_type_dir.Wrapper[int | None]
            ordinary: str
    """)


def test_type_dir_7():
    d = eval_typing(BaseArg[Final])
    assert d is int


class Simple[T]:
    simple: T


class Funny[T](Simple[list[T]]):
    pass


class Funny2(Funny[int]):
    pass


def test_type_dir_8():
    d = eval_typing(Funny2)

    assert format_helper.format_class(d) == textwrap.dedent("""\
        class Funny2:
            simple: list[int]
    """)


def test_type_dir_9():
    d = eval_typing(Last[bool])

    assert format_helper.format_class(d) == textwrap.dedent("""\
        class Last[bool]:
            last: bool | typing.Literal[True]
    """)


def _get_member(members, name):
    return next(
        iter(m for m in members.__args__ if m.__args__[0].__args__[0] == name)
    )


def test_type_members_attr_():
    d = eval_typing(Members[Final])
    member = _get_member(d, "ordinary")
    assert typing.get_origin(member) is Member
    _, _, _, origin = typing.get_args(member)
    assert origin.__name__ == "Ordinary"


def test_type_members_func_1a():
    d = eval_typing(Members[Final])
    member = _get_member(d, "foo")
    assert typing.get_origin(member) is Member
    name, typ, quals, origin = typing.get_args(member)
    assert name == typing.Literal["foo"]
    assert quals == typing.Literal["ClassVar"]

    assert (
        str(typ)
        == "\
typing.Callable[[\
typemap.typing.Param[typing.Literal['self'], tests.test_type_dir.Base[int], typing.Never], \
typemap.typing.Param[typing.Literal['a'], int | None, typing.Never], \
typemap.typing.Param[typing.Literal['b'], int, typing.Literal['keyword', \
'default']]], \
dict[str, int]]"
    )

    assert origin.__name__ == "Base[int]"


def test_type_members_func_2():
    d = eval_typing(Members[Final])
    member = _get_member(d, "cbase")
    assert typing.get_origin(member) is Member
    name, typ, quals, _origin = typing.get_args(member)
    assert name == typing.Literal["cbase"]
    assert quals == typing.Literal["ClassVar"]

    assert (
        str(typ)
        == "\
classmethod[tests.test_type_dir.Base[int], tuple[typemap.typing.Param[typing.Literal['a'], int | None, typing.Never], typemap.typing.Param[typing.Literal['b'], ~K, typing.Never]], dict[str, int]]"
    )


def test_type_members_func_3():
    d = eval_typing(Members[Final])
    member = _get_member(d, "sbase")
    assert typing.get_origin(member) is Member
    name, typ, quals, _origin = typing.get_args(member)
    assert name == typing.Literal["sbase"]
    assert quals == typing.Literal["ClassVar"]

    assert (
        str(typ)
        == "\
staticmethod[tuple[typemap.typing.Param[typing.Literal['a'], int | typing.Literal['gotcha!'] | Z | None, typing.Never], typemap.typing.Param[typing.Literal['b'], ~K, typing.Never]], dict[str, int | Z]]"
    )
