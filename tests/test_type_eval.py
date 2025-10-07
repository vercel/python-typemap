import textwrap
import typing

from typemap import typing as next
from typemap.type_eval import eval_typing

from . import format_helper


type A[T] = T | None | typing.Literal[False]
type B = A[int]

type OrGotcha[K] = K | typing.Literal["gotcha!"]


class F[T]:
    fff: T


class F_int(F[int]):
    pass


type MapRecursive[A] = next.NewProtocol[
    [
        (
            next.Property[p.name, OrGotcha[p.type]]
            if p.type is not A
            else next.Property[p.name, OrGotcha[MapRecursive[A]]]
        )
        for p in (next.DirProperties[A] + next.DirProperties[F_int])
    ]
    + [next.Property["control", float]]  # noqa: F821
]


class Recursive:
    n: int
    m: str
    t: typing.Literal[False]
    a: Recursive


def test_eval_types_1():
    assert str(eval_typing(B)) == "int | None | typing.Literal[False]"


def test_eval_types_2():
    evaled = eval_typing(MapRecursive[Recursive])

    # Validate that recursion worked properly and "Recursive" was only walked once
    assert evaled.__annotations__["a"].__args__[0] is evaled

    assert format_helper.format_class(evaled) == textwrap.dedent("""\
        class Protocol:
            n: int | typing.Literal['gotcha!']
            m: str | typing.Literal['gotcha!']
            t: typing.Literal[False] | typing.Literal['gotcha!']
            a: abc.Protocol | typing.Literal['gotcha!']
            fff: int | typing.Literal['gotcha!']
            control: float
        """)
