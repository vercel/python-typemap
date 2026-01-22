import pytest
import textwrap

from typing import Callable, Literal, Unpack

from typemap.type_eval import eval_call
from typemap.typing import (
    Attrs,
    BaseTypedDict,
    GetName,
    Iter,
    Member,
    NewProtocol,
    Param,
)

from . import format_helper


def func[*T, K: BaseTypedDict](
    *args: Unpack[T],
    **kwargs: Unpack[K],
) -> NewProtocol[*[Member[GetName[c], int] for c in Iter[Attrs[K]]]]: ...


def test_eval_call_01():
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


def test_eval_call_02():
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


def test_eval_call_03():
    ret = eval_call(wrapped, 1)
    fmt = format_helper.format_class(ret)

    assert fmt == textwrap.dedent("""\
        class Wrapped[typing.Literal[1]]:
            value: typing.Literal[1]
            def __init__(self: Self, value: Literal[1]) -> None: ...
        """)


def module_return_callable(
    x: int,
) -> Callable[[Param[Literal["y"], int]], int]: ...
def module_param_callable(
    x: Callable[[Param[Literal["y"], int]], int],
) -> int: ...


def type_eval_call_higher_order_callable_01():
    # Return a callable

    # Module function
    ret = eval_call(module_return_callable, 1)
    assert ret == Callable[[Param[Literal["y"], int]], int]

    # Local function
    def local_return_callable(
        x: int,
    ) -> Callable[[Param[Literal["y"], int]], int]: ...

    ret = eval_call(local_return_callable, 1)
    assert ret == Callable[[Param[Literal["y"], int]], int]


def test_eval_call_higher_order_callable_02():
    # Param is a callable
    def f(y: int) -> int: ...

    class C:
        @staticmethod
        def g(y: int) -> int: ...

    # Module function
    ret = eval_call(module_param_callable, f)
    assert ret is int
    ret = eval_call(module_param_callable, C.g)
    assert ret is int

    # Local function
    def local_param_callable(
        x: Callable[[Param[Literal["y"], int]], int],
    ) -> int: ...

    ret = eval_call(local_param_callable, f)
    assert ret is int
    ret = eval_call(local_param_callable, C.g)
    assert ret is int


def module_generic_return_callable[T](
    x: T,
) -> Callable[[Param[Literal["y"], int]], T]: ...
def module_generic_param_callable[T](
    x: Callable[[Param[Literal["y"], int]], T],
) -> T: ...


class WithGenericHigherOrderCallable:
    @staticmethod
    def static_return_callable[T](
        x: T,
    ) -> Callable[[Param[Literal["y"], int]], T]: ...

    @staticmethod
    def static_param_callable[T](
        x: Callable[[Param[Literal["y"], int]], T],
    ) -> T: ...


@pytest.mark.xfail(reason="T is bound to Literal[1], which is not helpful")
def test_eval_call_generic_higher_order_callable_01():
    # Return a callable

    # Module function
    ret = eval_call(module_generic_return_callable, 1)
    assert ret == Callable[[Param[Literal["y"], int]], int]

    # Local function
    def local_return_generic_callable[T](
        x: T,
    ) -> Callable[[Param[Literal["y"], int]], T]: ...

    ret = eval_call(local_return_generic_callable, 1)
    assert ret == Callable[[Param[Literal["y"], int]], int]

    # Static method
    ret = eval_call(
        WithGenericHigherOrderCallable.static_return_callable,
        1,
    )
    assert ret == Callable[[Param[Literal["y"], int]], int]


def test_eval_call_generic_higher_order_callable_02():
    # Param is a callable
    def f(y: int) -> int: ...

    class C:
        @staticmethod
        def g(y: int) -> int: ...

    # Module function
    ret = eval_call(module_generic_param_callable, f)
    assert ret is int
    ret = eval_call(module_generic_param_callable, C.g)
    assert ret is int

    # Local function
    def local_param_generic_callable[T](
        x: Callable[[Param[Literal["y"], int]], T],
    ) -> T: ...

    ret = eval_call(local_param_generic_callable, f)
    assert ret is int
    ret = eval_call(local_param_generic_callable, C.g)
    assert ret is int

    # static method
    ret = eval_call(
        WithGenericHigherOrderCallable.static_param_callable,
        f,
    )
    assert ret is int
    ret = eval_call(
        WithGenericHigherOrderCallable.static_param_callable,
        C.g,
    )
    assert ret is int
