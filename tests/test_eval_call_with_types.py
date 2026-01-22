import pytest
import textwrap

from types import GenericAlias
from typing import Callable, Generic, Literal, Self, TypeVar, Unpack
from typing_extensions import TypeAliasType

from typemap.type_eval import eval_call_with_types
from typemap.typing import (
    Attrs,
    BaseTypedDict,
    NewProtocol,
    Member,
    GetAttr,
    Iter,
    Param,
)

from typing import _ProtocolMeta

from . import format_helper


class Wrapper[T]:
    value: T


class WrappedInt(Wrapper[int]):
    pass


class WrappedStr(Wrapper[str]):
    pass


class WrappedIntStr(WrappedInt, WrappedStr):
    pass


class Pair[T, U]:
    first: T
    second: U


def func_positional(x: int) -> int: ...
def func_named(*, x: int) -> int: ...
def func_generic_to_value[T](x: T) -> T: ...
def func_generic_to_wrapped[T](x: T) -> Wrapper[T]: ...
def func_generic_from_wrapped[T](x: Wrapper[T]) -> T: ...
def func_generic_partial[T](x: Pair[int, T]) -> T: ...


def func_unpack_tuple[*T](
    *args: Unpack[T],
) -> T: ...
def func_unpack_dict[K: BaseTypedDict](
    **kwargs: Unpack[K],
) -> K: ...


def test_eval_call_with_types_module_function_01():
    ret = eval_call_with_types(func_positional, int)
    assert ret is int


def test_eval_call_with_types_module_function_02():
    ret = eval_call_with_types(func_named, x=int)
    assert ret is int


def test_eval_call_with_types_module_function_03():
    ret = eval_call_with_types(func_generic_to_value, int)
    assert ret is int


def test_eval_call_with_types_module_function_04():
    ret = eval_call_with_types(func_generic_to_wrapped, int)
    assert ret is Wrapper[int]


def test_eval_call_with_types_module_function_05():
    ret = eval_call_with_types(func_generic_from_wrapped, Wrapper[int])
    assert ret is int
    ret = eval_call_with_types(func_generic_from_wrapped, WrappedInt)
    assert ret is int
    ret = eval_call_with_types(func_generic_from_wrapped, WrappedStr)
    assert ret is str
    ret = eval_call_with_types(func_generic_from_wrapped, WrappedIntStr)
    assert ret is int


def test_eval_call_with_types_module_function_06():
    ret = eval_call_with_types(func_generic_partial, Pair[int, int])
    assert ret is int
    ret = eval_call_with_types(func_generic_partial, Pair[int, str])
    assert ret is str


def test_eval_call_with_types_module_function_07():
    ret = eval_call_with_types(func_unpack_tuple, int, float, str)
    assert ret == tuple[int, float, str]


def test_eval_call_with_types_module_function_08():
    ret = eval_call_with_types(func_unpack_dict, a=int, b=float, c=str)
    fmt = format_helper.format_class(ret)

    assert fmt == textwrap.dedent("""\
        class **kwargs:
            a: int
            b: float
            c: str
        """)


def test_eval_call_with_types_local_function_01():
    def func(x: int) -> int: ...

    res = eval_call_with_types(func, int)
    assert res is int


def test_eval_call_with_types_local_function_02():
    def func(*, x: int) -> int: ...

    res = eval_call_with_types(func, x=int)
    assert res is int


def test_eval_call_with_types_local_function_03():
    def func[T](x: T) -> T: ...

    res = eval_call_with_types(func, int)
    assert res is int

    class C: ...

    res = eval_call_with_types(func, C)
    assert res is C


def test_eval_call_with_types_local_function_04():
    class C[T]:
        pass

    def f[T](x: T) -> C[T]: ...

    ret = eval_call_with_types(f, int)
    assert ret == C[int]


def test_eval_call_with_types_local_function_05():
    T = TypeVar("T")

    class C(Generic[T]): ...

    class D(C[int]): ...

    class E(C[str]): ...

    class F(D, E): ...

    def func[U](x: C[U]) -> U: ...

    res = eval_call_with_types(func, C[int])
    assert res is int
    res = eval_call_with_types(func, D)
    assert res is int
    res = eval_call_with_types(func, E)
    assert res is str
    res = eval_call_with_types(func, F)
    assert res is int


def test_eval_call_with_types_local_function_06():
    class C[T, U]: ...

    def func[V](x: C[int, V]) -> V: ...

    res = eval_call_with_types(func, C[int, str])
    assert res is str


class ModuleClass:
    def member_func(self, x: int) -> str: ...
    @classmethod
    def class_func(self, x: int) -> str: ...
    @staticmethod
    def static_func(x: int) -> str: ...

    def generic_member_func[T](self, x: T) -> T: ...
    @classmethod
    def generic_class_func[T](cls, x: T) -> T: ...
    @staticmethod
    def generic_static_func[T](x: T) -> T: ...


def test_eval_call_with_types_module_class_01():
    ret = eval_call_with_types(
        GetAttr[ModuleClass, Literal["member_func"]], ModuleClass, int
    )
    assert ret is str


def test_eval_call_with_types_module_class_02():
    ret = eval_call_with_types(
        GetAttr[ModuleClass, Literal["class_func"]], type(ModuleClass), int
    )
    assert ret is str


def test_eval_call_with_types_module_class_03():
    ret = eval_call_with_types(
        GetAttr[ModuleClass, Literal["static_func"]], int
    )
    assert ret is str


def test_eval_call_with_types_module_class_04():
    ret = eval_call_with_types(
        GetAttr[ModuleClass, Literal["generic_member_func"]], ModuleClass, int
    )
    assert ret is int


def test_eval_call_with_types_module_class_05():
    ret = eval_call_with_types(
        GetAttr[ModuleClass, Literal["generic_class_func"]],
        type(ModuleClass),
        int,
    )
    assert ret is int


def test_eval_call_with_types_module_class_06():
    ret = eval_call_with_types(
        GetAttr[ModuleClass, Literal["generic_static_func"]], int
    )
    assert ret is int


class ModuleGeneric[T]:
    def member_func(self, x: int) -> str: ...
    @classmethod
    def class_func(self, x: int) -> str: ...
    @staticmethod
    def static_func(x: int) -> str: ...

    def specialized_member_func[T](self, x: T) -> T: ...
    @classmethod
    def specialized_class_func[T](cls, x: T) -> T: ...
    @staticmethod
    def specialized_static_func[T](x: T) -> T: ...

    def generic_method[U](self, x: T, y: U) -> U: ...
    @classmethod
    def generic_class_method[U](cls, x: T, y: U) -> U: ...
    @staticmethod
    def generic_static_method[U](x: T, y: U) -> U: ...


def test_eval_call_with_types_module_generic_class_01():
    ret = eval_call_with_types(
        GetAttr[ModuleGeneric[float], Literal["member_func"]],
        ModuleGeneric[float],
        int,
    )
    assert ret is str


def test_eval_call_with_types_module_generic_class_02():
    ret = eval_call_with_types(
        GetAttr[ModuleGeneric[float], Literal["class_func"]],
        ModuleGeneric[float],
        int,
    )
    assert ret is str


def test_eval_call_with_types_module_generic_class_03():
    ret = eval_call_with_types(
        GetAttr[ModuleGeneric[float], Literal["static_func"]], int
    )
    assert ret is str


def test_eval_call_with_types_module_generic_class_04():
    ret = eval_call_with_types(
        GetAttr[ModuleGeneric[float], Literal["specialized_member_func"]],
        ModuleGeneric[float],
        int,
    )
    assert ret is int


def test_eval_call_with_types_module_generic_class_05():
    ret = eval_call_with_types(
        GetAttr[ModuleGeneric[float], Literal["specialized_class_func"]],
        ModuleGeneric[float],
        int,
    )
    assert ret is int


def test_eval_call_with_types_module_generic_class_06():
    ret = eval_call_with_types(
        GetAttr[ModuleGeneric[float], Literal["specialized_static_func"]], int
    )
    assert ret is int


def test_eval_call_with_types_module_generic_class_07():
    ret = eval_call_with_types(
        GetAttr[ModuleGeneric[float], Literal["generic_method"]],
        ModuleGeneric[float],
        float,
        int,
    )
    assert ret is int


def test_eval_call_with_types_module_generic_class_08():
    ret = eval_call_with_types(
        GetAttr[ModuleGeneric[float], Literal["generic_class_method"]],
        ModuleGeneric[float],
        float,
        int,
    )
    assert ret is int


def test_eval_call_with_types_module_generic_class_09():
    ret = eval_call_with_types(
        GetAttr[ModuleGeneric[float], Literal["generic_static_method"]],
        float,
        int,
    )
    assert ret is int


def test_eval_call_with_types_local_class_01():
    class C:
        def member_func(self, x: int) -> str: ...

    ret = eval_call_with_types(GetAttr[C, Literal["member_func"]], C, int)
    assert ret is str


def test_eval_call_with_types_local_class_02():
    class C:
        @classmethod
        def class_func(cls, x: int) -> str: ...

    ret = eval_call_with_types(GetAttr[C, Literal["class_func"]], type(C), int)
    assert ret is str


def test_eval_call_with_types_local_class_03():
    class C:
        @staticmethod
        def static_func(x: int) -> str: ...

    ret = eval_call_with_types(GetAttr[C, Literal["static_func"]], int)
    assert ret is str


def test_eval_call_with_types_local_class_04():
    class C:
        def generic_member_func[T](self, x: T) -> T: ...

    ret = eval_call_with_types(
        GetAttr[C, Literal["generic_member_func"]], C, int
    )
    assert ret is int


def test_eval_call_with_types_local_class_05():
    class C:
        @classmethod
        def generic_class_func[T](cls, x: T) -> T: ...

    ret = eval_call_with_types(
        GetAttr[C, Literal["generic_class_func"]], type(C), int
    )
    assert ret is int


def test_eval_call_with_types_local_class_06():
    class C:
        @staticmethod
        def generic_static_func[T](x: T) -> T: ...

    ret = eval_call_with_types(GetAttr[C, Literal["generic_static_func"]], int)
    assert ret is int


def test_eval_call_with_types_local_generic_class_01():
    class C[T]:
        def member_func(self, x: int) -> str: ...

    ret = eval_call_with_types(
        GetAttr[C[float], Literal["member_func"]], C[float], int
    )
    assert ret is str


def test_eval_call_with_types_local_generic_class_02():
    class C[T]:
        @classmethod
        def class_func(cls, x: int) -> str: ...

    ret = eval_call_with_types(
        GetAttr[C[float], Literal["class_func"]], C[float], int
    )
    assert ret is str


def test_eval_call_with_types_local_generic_class_03():
    class C[T]:
        @staticmethod
        def static_func(x: int) -> str: ...

    ret = eval_call_with_types(GetAttr[C[float], Literal["static_func"]], int)
    assert ret is str


def test_eval_call_with_types_local_generic_class_04():
    class C[T]:
        def specialized_member_func[T](self, x: T) -> T: ...

    ret = eval_call_with_types(
        GetAttr[C[float], Literal["specialized_member_func"]], C[float], int
    )
    assert ret is int


def test_eval_call_with_types_local_generic_class_05():
    class C[T]:
        @classmethod
        def specialized_class_func[T](cls, x: T) -> T: ...

    ret = eval_call_with_types(
        GetAttr[C[float], Literal["specialized_class_func"]], C[float], int
    )
    assert ret is int


def test_eval_call_with_types_local_generic_class_06():
    class C[T]:
        @staticmethod
        def specialized_static_func[T](x: T) -> T: ...

    ret = eval_call_with_types(
        GetAttr[C[float], Literal["specialized_static_func"]], int
    )
    assert ret is int


def test_eval_call_with_types_local_generic_class_07():
    class C[T]:
        def generic_method[U](self, x: T, y: U) -> U: ...

    ret = eval_call_with_types(
        GetAttr[C[float], Literal["generic_method"]], C[float], float, int
    )
    assert ret is int


def test_eval_call_with_types_local_generic_class_08():
    class C[T]:
        @classmethod
        def generic_class_method[U](cls, x: T, y: U) -> U: ...

    ret = eval_call_with_types(
        GetAttr[C[float], Literal["generic_class_method"]], C[float], float, int
    )
    assert ret is int


def test_eval_call_with_types_local_generic_class_09():
    class C[T]:
        @staticmethod
        def generic_static_method[U](x: float, y: U) -> U: ...

    ret = eval_call_with_types(
        GetAttr[C[float], Literal["generic_static_method"]], float, int
    )
    assert ret is int


class Foo:
    a: int


class Bar:
    a: str


U = TypeVar("U")
type WithCopy[T] = NewProtocol[
    *[c for c in Iter[Attrs[T]]],
    Member[
        Literal["copy"],
        Callable[[Param[Literal["self"], Self]], WithCopy[T]],
        Literal["ClassVar"],
    ],
]
type WithEq[T] = NewProtocol[
    *[c for c in Iter[Attrs[T]]],
    Member[
        Literal["__eq__"],
        Callable[
            [Param[Literal["self"], Self], Param[Literal["other"], WithEq[T]]],
            bool,
        ],
        Literal["ClassVar"],
    ],
]
type WithContains[T] = NewProtocol[
    *[c for c in Iter[Attrs[T]]],
    Member[
        Literal["__contains__"],
        Callable[
            [Param[Literal["self"], Self], Param[Literal["item"], U]], bool
        ],
        Literal["ClassVar"],
    ],
]
type WithAdd[T] = NewProtocol[
    *[c for c in Iter[Attrs[T]]],
    Member[
        Literal["__add__"],
        Callable[
            [Param[Literal["self"], Self], Param[Literal["other"], U]],
            WithAdd[U],
        ],
        Literal["ClassVar"],
    ],
]
type WithMax[T] = NewProtocol[
    *[c for c in Iter[Attrs[T]]],
    Member[
        Literal["from"],
        Callable[
            [Param[Literal["self"], Self], Param[Literal["other"], WithMax[U]]],
            U,
        ],
        Literal["ClassVar"],
    ],
]


def with_copy[T](value: T) -> WithCopy[T]: ...
def with_eq[T](value: T) -> WithEq[T]: ...
def with_contains[T](value: T) -> WithContains[T]: ...
def with_add[T](value: T) -> WithAdd[T]: ...
def with_max[T](value: T) -> WithMax[T]: ...


def test_eval_call_with_types_protocol_01():
    # Member function of a protocol
    # Returns same protocol

    cls = eval_call_with_types(with_copy, Foo)
    assert type(cls) is _ProtocolMeta

    fmt = format_helper.format_class(cls)
    assert fmt == textwrap.dedent("""\
        class WithCopy[tests.test_eval_call_with_types.Foo]:
            a: int
            def copy(self: Self) -> WithCopy[tests.test_eval_call_with_types.Foo]: ...
        """)

    ret = eval_call_with_types(GetAttr[cls, Literal["copy"]], WithCopy[Foo])
    assert ret == WithCopy[Foo]

    # Note: ret here is a generic TypeAliasType
    assert isinstance(ret, GenericAlias)
    assert isinstance(ret.__origin__, TypeAliasType)

    # Still renders the same as the original protocol
    fmt = format_helper.format_class(ret)
    assert fmt == textwrap.dedent("""\
        class WithCopy[tests.test_eval_call_with_types.Foo]:
            a: int
            def copy(self: Self) -> WithCopy[tests.test_eval_call_with_types.Foo]: ...
        """)

    # Make sure we can keep calling the member function
    ret2 = eval_call_with_types(GetAttr[ret, Literal["copy"]], WithCopy[Foo])
    assert ret2 == ret


def test_eval_call_with_types_protocol_02():
    # Member function of a protocol
    # Param is the same protocol
    # Returns bool

    cls = eval_call_with_types(with_eq, Foo)
    fmt = format_helper.format_class(cls)
    assert fmt == textwrap.dedent("""\
        class WithEq[tests.test_eval_call_with_types.Foo]:
            a: int
            def __eq__(self: Self, other: WithEq[tests.test_eval_call_with_types.Foo]) -> bool: ...
        """)

    ret = eval_call_with_types(
        GetAttr[cls, Literal["__eq__"]], WithEq[Foo], WithEq[Foo]
    )
    assert ret is bool

    with pytest.raises(ValueError, match="Argument type mismatch for other"):
        eval_call_with_types(GetAttr[cls, Literal["__eq__"]], WithEq[Foo], int)
    with pytest.raises(ValueError, match="Argument type mismatch for other"):
        eval_call_with_types(GetAttr[cls, Literal["__eq__"]], WithEq[Foo], Foo)
    with pytest.raises(ValueError, match="Argument type mismatch for other"):
        eval_call_with_types(
            GetAttr[cls, Literal["__eq__"]], WithEq[Foo], WithEq[Bar]
        )
    with pytest.raises(ValueError, match="Argument type mismatch for other"):
        eval_call_with_types(
            GetAttr[cls, Literal["__eq__"]], WithEq[Foo], WithAdd[Foo]
        )


def test_eval_call_with_types_protocol_03():
    # Member function of a protocol
    # Param is a different type
    # Returns bool

    cls = eval_call_with_types(with_contains, Foo)
    fmt = format_helper.format_class(cls)
    assert fmt == textwrap.dedent("""\
        class WithContains[tests.test_eval_call_with_types.Foo]:
            a: int
            def __contains__(self: Self, item: ~U) -> bool: ...
        """)

    ret = eval_call_with_types(
        GetAttr[cls, Literal["__contains__"]],
        WithContains[Foo],
        int,
    )
    assert ret is bool
    ret = eval_call_with_types(
        GetAttr[cls, Literal["__contains__"]],
        WithContains[Foo],
        str,
    )
    assert ret is bool
    ret = eval_call_with_types(
        GetAttr[cls, Literal["__contains__"]],
        WithContains[Foo],
        float,
    )
    assert ret is bool


def test_eval_call_with_types_protocol_04():
    # Member function of a protocol
    # Param is a different type
    # Returns a protocol based on the param type

    cls = eval_call_with_types(with_add, Foo)
    fmt = format_helper.format_class(cls)
    assert fmt == textwrap.dedent("""\
        class WithAdd[tests.test_eval_call_with_types.Foo]:
            a: int
            def __add__(self: Self, other: ~U) -> WithAdd[~U]: ...
        """)
    ret = eval_call_with_types(
        GetAttr[cls, Literal["__add__"]], WithAdd[Foo], Bar
    )
    assert ret == WithAdd[Bar]

    # Note: ret here is a generic TypeAliasType
    assert isinstance(ret, GenericAlias)
    assert isinstance(ret.__origin__, TypeAliasType)

    fmt = format_helper.format_class(ret)
    assert fmt == textwrap.dedent("""\
        class WithAdd[tests.test_eval_call_with_types.Bar]:
            a: str
            def __add__(self: Self, other: ~U) -> WithAdd[~U]: ...
        """)

    # Make sure we can keep calling the member function
    ret2 = eval_call_with_types(
        GetAttr[ret, Literal["__add__"]], WithAdd[Bar], Foo
    )
    assert ret2 == WithAdd[Foo]


def test_eval_call_with_types_protocol_05():
    cls = eval_call_with_types(with_max, Foo)
    fmt = format_helper.format_class(cls)
    assert fmt == textwrap.dedent("""\
        class WithMax[tests.test_eval_call_with_types.Foo]:
            a: int
            def from(self: Self, other: WithMax[~U]) -> ~U: ...
        """)
    ret = eval_call_with_types(
        GetAttr[cls, Literal["from"]], WithMax[Foo], WithMax[Bar]
    )
    assert ret is Bar

    with pytest.raises(ValueError, match="Argument type mismatch for other"):
        eval_call_with_types(GetAttr[cls, Literal["from"]], WithMax[Foo], int)
    with pytest.raises(ValueError, match="Argument type mismatch for other"):
        eval_call_with_types(
            GetAttr[cls, Literal["from"]], WithMax[Foo], WithEq[Foo]
        )


def test_eval_call_with_types_callable_01():
    res = eval_call_with_types(Callable[[], int])
    assert res is int


def test_eval_call_with_types_callable_02():
    res = eval_call_with_types(Callable[[Param[Literal["x"], int]], int], int)
    assert res is int


def test_eval_call_with_types_callable_03():
    res = eval_call_with_types(
        Callable[[Param[Literal["x"], int, Literal["keyword"]]], int], x=int
    )
    assert res is int


def test_eval_call_with_types_callable_04():
    class C: ...

    res = eval_call_with_types(Callable[[Param[Literal["self"], Self]], int], C)
    assert res is int


def test_eval_call_with_types_callable_05():
    class C: ...

    res = eval_call_with_types(Callable[[Param[Literal["self"], Self]], C], C)
    assert res is C


def test_eval_call_with_types_callable_06():
    class C: ...

    res = eval_call_with_types(
        Callable[[Param[Literal["self"], Self], Param[Literal["x"], int]], int],
        C,
        int,
    )
    assert res is int


def test_eval_call_with_types_callable_07():
    class C: ...

    res = eval_call_with_types(
        Callable[
            [
                Param[Literal["self"], Self],
                Param[Literal["x"], int, Literal["keyword"]],
            ],
            int,
        ],
        C,
        x=int,
    )
    assert res is int


def test_eval_call_with_types_callable_08():
    T = TypeVar("T")
    res = eval_call_with_types(Callable[[Param[Literal["x"], T]], str], int)
    assert res is str


def test_eval_call_with_types_callable_09():
    T = TypeVar("T")
    res = eval_call_with_types(Callable[[Param[Literal["x"], T]], T], int)
    assert res is int


def test_eval_call_with_types_callable_10():
    T = TypeVar("T")

    class C(Generic[T]): ...

    res = eval_call_with_types(Callable[[Param[Literal["x"], C[T]]], T], C[int])
    assert res is int


def test_eval_call_with_types_callable_11():
    T = TypeVar("T")

    class C(Generic[T]): ...

    class D(C[int]): ...

    class E(D): ...

    res = eval_call_with_types(Callable[[Param[Literal["x"], C[T]]], T], D)
    assert res is int
    res = eval_call_with_types(Callable[[Param[Literal["x"], C[T]]], T], E)
    assert res is int


def test_eval_call_with_types_callable_12():
    T = TypeVar("T")

    class C[U]: ...

    ret = eval_call_with_types(Callable[[Param[Literal["x"], T]], C[T]], int)
    assert ret == C[int]


def test_eval_call_with_types_callable_13():
    T = TypeVar("T")
    U = TypeVar("U")

    class C(Generic[T, U]): ...

    ret = eval_call_with_types(
        Callable[[Param[Literal["x"], C[int, T]]], T], C[int, str]
    )
    assert ret is str


def test_eval_call_with_types_bind_error_01():
    T = TypeVar("T")

    with pytest.raises(
        ValueError, match="Type variable T is already bound to int, but got str"
    ):
        eval_call_with_types(
            Callable[[Param[Literal["x"], T], Param[Literal["y"], T]], T],
            int,
            str,
        )


def test_eval_call_with_types_bind_error_02():
    def func[T](x: T, y: T) -> T: ...

    with pytest.raises(
        ValueError, match="Type variable T is already bound to int, but got str"
    ):
        eval_call_with_types(func, int, str)


def test_eval_call_with_types_bind_error_03():
    T = TypeVar("T")

    class C(Generic[T]): ...

    with pytest.raises(
        ValueError, match="Type variable T is already bound to int, but got str"
    ):
        eval_call_with_types(
            Callable[[Param[Literal["x"], C[T]], Param[Literal["y"], C[T]]], T],
            C[int],
            C[str],
        )


def test_eval_call_with_types_bind_error_04():
    class C[T]: ...

    def func[T](x: C[T], y: C[T]) -> T: ...

    with pytest.raises(
        ValueError, match="Type variable T is already bound to int, but got str"
    ):
        eval_call_with_types(func, C[int], C[str])


def test_eval_call_with_types_bind_error_05():
    class C[T]: ...

    class D[T]: ...

    def func[T](x: C[T]) -> T: ...

    with pytest.raises(ValueError, match="Argument type mismatch for x"):
        eval_call_with_types(func, D[int])


def test_eval_call_with_types_bind_error_06():
    T = TypeVar("T")
    U = TypeVar("U")

    class C(Generic[T, U]): ...

    with pytest.raises(ValueError, match="Argument type mismatch for x"):
        eval_call_with_types(
            Callable[[Param[Literal["x"], C[int, T]]], T], C[float, str]
        )


def module_return_callable(
    x: int,
) -> Callable[[Param[Literal["y"], int]], int]: ...
def module_param_callable(
    x: Callable[[Param[Literal["y"], int]], int],
) -> int: ...


class WithHigherOrderCallable:
    def member_return_callable(
        self, x: int
    ) -> Callable[[Param[Literal["y"], int]], int]: ...
    @classmethod
    def class_return_callable(
        cls, x: int
    ) -> Callable[[Param[Literal["y"], int]], int]: ...
    @staticmethod
    def static_return_callable(
        x: int,
    ) -> Callable[[Param[Literal["y"], int]], int]: ...

    def member_param_callable(
        self, x: Callable[[Param[Literal["y"], int]], int]
    ) -> int: ...
    @classmethod
    def class_param_callable(
        cls, x: Callable[[Param[Literal["y"], int]], int]
    ) -> int: ...
    @staticmethod
    def static_param_callable(
        x: Callable[[Param[Literal["y"], int]], int],
    ) -> int: ...


def test_eval_call_with_types_higher_order_callable_01():
    # Return a callable

    # Module function
    ret = eval_call_with_types(module_return_callable, int)
    assert ret == Callable[[Param[Literal["y"], int]], int]

    # Local function
    def local_return_callable(
        x: int,
    ) -> Callable[[Param[Literal["y"], int]], int]: ...

    ret = eval_call_with_types(local_return_callable, int)
    assert ret == Callable[[Param[Literal["y"], int]], int]

    # Member function
    ret = eval_call_with_types(
        GetAttr[WithHigherOrderCallable, Literal["member_return_callable"]],
        WithHigherOrderCallable,
        int,
    )
    assert ret == Callable[[Param[Literal["y"], int]], int]

    # Class method
    ret = eval_call_with_types(
        GetAttr[WithHigherOrderCallable, Literal["class_return_callable"]],
        type(WithHigherOrderCallable),
        int,
    )
    assert ret == Callable[[Param[Literal["y"], int]], int]

    # Static method
    ret = eval_call_with_types(
        GetAttr[WithHigherOrderCallable, Literal["static_return_callable"]],
        int,
    )
    assert ret == Callable[[Param[Literal["y"], int]], int]

    # typing.Callable
    func = Callable[
        [Param[Literal["x"], int]], Callable[[Param[Literal["y"], int]], int]
    ]
    ret = eval_call_with_types(
        func,
        int,
    )
    assert ret == Callable[[Param[Literal["y"], int]], int]


def test_eval_call_with_types_higher_order_callable_02():
    # Param is a callable

    # Module function
    ret = eval_call_with_types(
        module_param_callable, Callable[[Param[Literal["y"], int]], int]
    )
    assert ret is int

    # Local function
    def local_param_callable(
        x: Callable[[Param[Literal["y"], int]], int],
    ) -> int: ...

    ret = eval_call_with_types(
        local_param_callable, Callable[[Param[Literal["y"], int]], int]
    )
    assert ret is int

    # Member function
    ret = eval_call_with_types(
        GetAttr[WithHigherOrderCallable, Literal["member_param_callable"]],
        WithHigherOrderCallable,
        Callable[[Param[Literal["y"], int]], int],
    )
    assert ret is int

    # Class method
    ret = eval_call_with_types(
        GetAttr[WithHigherOrderCallable, Literal["class_param_callable"]],
        type(WithHigherOrderCallable),
        Callable[[Param[Literal["y"], int]], int],
    )
    assert ret is int

    # Static method
    ret = eval_call_with_types(
        GetAttr[WithHigherOrderCallable, Literal["static_param_callable"]],
        Callable[[Param[Literal["y"], int]], int],
    )
    assert ret is int

    # typing.Callable
    func = Callable[
        [Param[Literal["x"], Callable[[Param[Literal["y"], int]], int]]], int
    ]
    ret = eval_call_with_types(func, Callable[[Param[Literal["y"], int]], int])
    assert ret is int
    with pytest.raises(ValueError, match="Argument type mismatch for x"):
        eval_call_with_types(func, Callable[[Param[Literal["z"], str]], int])


def test_eval_call_with_types_higher_order_callable_03():
    # Both param and return are callables

    # typing.Callable
    func = Callable[
        [Param[Literal["x"], Callable[[Param[Literal["y"], int]], int]]],
        Callable[[Param[Literal["z"], int]], int],
    ]
    ret = eval_call_with_types(func, Callable[[Param[Literal["y"], int]], int])
    assert ret == Callable[[Param[Literal["z"], int]], int]
