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
    [next.Property[p.name, p.type | None] for p in next.DirProperties[T]]
]

type OptionalFinal = AllOptional[Final]


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

    # XXX: `DirProperties` skips methods, true to its name. Perhaps we just need
    #      `Dir` that would iterate over everything
    assert format_helper.format_class(d) == textwrap.dedent("""\
        class AllOptional[tests.test_type_dir.Final]:
            last: int | typing.Literal[True] | None
            iii: str | int | typing.Literal['gotcha!'] | None
            t: dict[str, str | int | typing.Literal['gotcha!']] | None
            kkk: ~K | None
            x: tests.test_type_dir.Wrapper[int | None] | None
            ordinary: str | None
    """)
