import textwrap

from typing import Generic, Literal, Self, TypeVar, Unpack

from typemap.type_eval import eval_call
from typemap.typing import (
    Attrs,
    BaseTypedDict,
    GetName,
    NewProtocol,
    Member,
    Iter,
)

from . import format_helper


def func[*T, K: BaseTypedDict](
    *args: Unpack[T],
    **kwargs: Unpack[K],
) -> NewProtocol[*[Member[GetName[c], int] for c in Iter[Attrs[K]]]]: ...


def test_call_1():
    ret = eval_call(func, a=1, b=2, c="aaa")
    fmt = format_helper.format_class(ret)

    assert fmt == textwrap.dedent("""\
        class func[...]:
            a: int
            b: int
            c: int
        """)


def func_trivial[*T, K: BaseTypedDict](
    *args: Unpack[T],
    **kwargs: Unpack[K],
) -> K:
    return kwargs


def test_call_2():
    ret = eval_call(func_trivial, a=1, b=2, c="aaa")
    fmt = format_helper.format_class(ret)

    assert fmt == textwrap.dedent("""\
        class **kwargs:
            a: typing.Literal[1]
            b: typing.Literal[2]
            c: typing.Literal['aaa']
        """)


class Wrapped[T]:  # noqa: B903
    value: T

    def __init__(self, value: T):
        self.value = value


def wrapped[T](value: T) -> Wrapped[T]:
    return Wrapped[T](value)


def test_call_3():
    ret = eval_call(wrapped, 1)
    fmt = format_helper.format_class(ret)

    assert fmt == textwrap.dedent("""\
        class Wrapped[typing.Literal[1]]:
            value: typing.Literal[1]
            def __init__(self: Self, value: Literal[1]) -> None: ...
        """)


def test_call_bound_method_01():
    # non-generic class, non-generic method
    class C:
        def invoke(self: Self, x: int) -> int:
            return x

    c = C()
    ret = eval_call(c.invoke, 1)
    assert ret is int


def test_call_bound_method_02():
    # non-generic class, generic method
    class C:
        def invoke[X](self: Self, x: X) -> X:
            return x

    c = C()
    ret = eval_call(c.invoke, 1)
    assert ret is Literal[1]


def test_call_bound_method_03():
    # generic class, non-generic method, with type var
    X = TypeVar("X")

    class C(Generic[X]):
        def invoke(self: Self, x: X) -> X:
            return x

    c = C[int]()
    ret = eval_call(c.invoke, 1)
    assert ret is Literal[1]


def test_call_bound_method_04():
    # generic class, non-generic method, PEP695 syntax
    class C[X]:
        def invoke(self: Self, x: X) -> X:
            return x

    c = C[int]()
    ret = eval_call(c.invoke, 1)
    assert ret is Literal[1]


def test_call_bound_method_05():
    # generic class, generic method, with type var
    X = TypeVar("X")

    class C(Generic[X]):
        def invoke[Y](self: Self, x: Y) -> Y:
            return x

    c = C[int]()
    ret = eval_call(c.invoke, "!!!")
    assert ret is Literal["!!!"]


def test_call_bound_method_06():
    # generic class, generic method, PEP695 syntax
    class C[X]:
        def invoke[Y](self: Self, x: Y) -> Y:
            return x

    c = C[int]()
    ret = eval_call(c.invoke, "!!!")
    assert ret is Literal["!!!"]


def test_call_local_type_01():
    class C: ...

    def invoke() -> C:
        return C()

    ret = eval_call(invoke)
    assert ret is C
