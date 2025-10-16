import typing
import textwrap

from typemap.type_eval import eval_typing
from typemap import typing as next

from . import format_helper


type OrGotcha[K] = K | typing.Literal["gotcha!"]

type StrForInt[X] = (str | OrGotcha[X]) if X is int else (X | OrGotcha[X])


class Ordinary:
    ordinary: str


class AnotherBase[I]:
    iii: OrGotcha[StrForInt[I]]


class Base[T]:
    K = typing.TypeVar("K")

    t: dict[str, StrForInt[T]]
    kkk: K

    def base[Z](self, a: T | Z | None, b: K) -> dict[str, T | Z]:
        pass

    @classmethod
    def cbase(cls, a: T | None, b: K) -> dict[str, T]:
        pass

    @staticmethod
    def sbase[Z](cls, a: OrGotcha[T] | Z | None, b: K) -> dict[str, T | Z]:
        pass


class Wrapper[X](Base[X], AnotherBase[X]):
    x: "Wrapper[X | None]"


class Mine(Wrapper[int]):
    pass


class Last[O]:
    last: O | typing.Literal[True]


class Final(Mine, Ordinary, Wrapper[float], AnotherBase[float], Last[int]):
    pass


type AllOptional[T] = next.NewProtocol[
    *[
        next.Member[next.GetName[p], next.GetType[p] | None]
        for p in next.Iter[next.Attrs[T]]
    ]
]

type OptionalFinal = AllOptional[Final]


type Capitalize[T] = next.NewProtocol[
    *[
        next.Member[next.Uppercase[next.GetName[p]], next.GetType[p]]
        for p in next.Iter[next.Attrs[T]]
    ]
]

type Prims[T] = next.NewProtocol[
    *[
        p
        for p in next.Iter[next.Attrs[T]]
        if next.Is[next.GetType[p], int | str]
    ]
]

type NoLiterals1[T] = next.NewProtocol[
    *[
        next.Member[
            next.GetName[p],
            typing.Union[
                *[
                    t
                    for t in next.Iter[next.FromUnion[next.GetType[p]]]
                    # XXX: 'typing.Literal' is not *really* a type...
                    # Maybe we can't do this, which maybe is fine.
                    if not next.Is[t, typing.Literal]
                ]
            ],
        ]
        for p in next.Iter[next.Attrs[T]]
    ]
]


# Try to implement IsLiteral. This is basically what is recommended
# for doing it in TS.
# XXX: This doesn't work in python! We can subtype str!
type IsLiteral[T] = (
    typing.Literal[True]
    if (
        (next.Is[T, str] and not next.Is[str, T])
        or (next.Is[T, bytes] and not next.Is[bytes, T])
        or (next.Is[T, bool] and not next.Is[bool, T])
        or (next.Is[T, int] and not next.Is[int, T])
        # XXX: enum, None
    )
    else typing.Literal[False]
)

type NoLiterals2[T] = next.NewProtocol[
    *[
        next.Member[
            next.GetName[p],
            typing.Union[
                *[
                    t
                    for t in next.Iter[next.FromUnion[next.GetType[p]]]
                    # XXX: 'typing.Literal' is not *really* a type...
                    # Maybe we can't do this, which maybe is fine.
                    # if not next.IsSubtype[t, typing.Literal]
                    if not next.Is[IsLiteral[t], typing.Literal[True]]
                ]
            ],
        ]
        for p in next.Iter[next.Attrs[T]]
    ]
]


def test_type_dir_1():
    d = eval_typing(Final)

    assert format_helper.format_class(d) == textwrap.dedent("""\
        class Final:
            last: int | typing.Literal[True]
            iii: str | int | typing.Literal['gotcha!']
            t: dict[str, str | int | typing.Literal['gotcha!']]
            kkk: ~K
            x: tests.test_type_dir.Wrapper[int | None]
            ordinary: str
            def base[Z](self, a: int | Z | None, b: ~K) -> dict[str, int | Z]: ...
            def cbase(cls, a: int | None, b: ~K) -> dict[str, int]: ...
            def sbase[Z](cls, a: int | Literal['gotcha!'] | Z | None, b: ~K) -> dict[str, int | Z]: ...
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
            X: tests.test_type_dir.Wrapper[int | None]
            ORDINARY: str
    """)


def test_type_dir_4():
    d = eval_typing(Prims[Final])

    assert format_helper.format_class(d) == textwrap.dedent("""\
        class Prims[tests.test_type_dir.Final]:
            last: int | typing.Literal[True]
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
            x: tests.test_type_dir.Wrapper[int | None]
            ordinary: str
    """)
