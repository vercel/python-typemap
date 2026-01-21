import pytest
import textwrap

from types import GenericAlias
from typing import Callable, Literal, Self, TypeVar, Unpack
from typing_extensions import TypeAliasType

from typemap.type_eval import eval_call, eval_call_with_types
from typemap.typing import (
    Attrs,
    BaseTypedDict,
    NewProtocol,
    Member,
    GetAttr,
    GetName,
    Iter,
    Param,
)

from typing import _ProtocolMeta

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


def test_eval_call_with_types_01():
    ret = eval_call_with_types(func, a=int, b=int, c=str)
    fmt = format_helper.format_class(ret)

    assert fmt == textwrap.dedent("""\
        class func[...]:
            a: int
            b: int
            c: int
        """)


def test_eval_call_with_types_02():
    ret = eval_call_with_types(func_trivial, a=int, b=int, c=str)
    fmt = format_helper.format_class(ret)

    assert fmt == textwrap.dedent("""\
        class **kwargs:
            a: int
            b: int
            c: str
        """)


def test_eval_call_with_types_03():
    ret = eval_call_with_types(wrapped, int)
    fmt = format_helper.format_class(ret)

    assert fmt == textwrap.dedent("""\
        class Wrapped[int]:
            value: int
            def __init__(self: Self, value: int) -> None: ...
        """)


type AsWrapped[T] = Wrapped[T]


def test_eval_call_with_types_04():
    T = TypeVar("T")
    ret = eval_call_with_types(
        Callable[[Param[Literal["x"], T]], AsWrapped[T]], int
    )
    fmt = format_helper.format_class(ret)
    assert fmt == textwrap.dedent("""\
        class Wrapped[int]:
            value: int
            def __init__(self: Self, value: int) -> None: ...
        """)


def test_eval_call_with_types_05():
    class C[T]:
        pass

    def f[T](x: T) -> C[T]: ...

    ret = eval_call_with_types(f, int)
    fmt = format_helper.format_class(ret)
    assert fmt == textwrap.dedent("""\
        class C[int]:
        """)


def test_eval_call_with_types_06():
    T = TypeVar("T")

    class C[U]:
        pass

    ret = eval_call_with_types(Callable[[Param[Literal["x"], T]], C[T]], int)
    fmt = format_helper.format_class(ret)
    assert fmt == textwrap.dedent("""\
        class C[int]:
        """)


class ModuleClass:
    def a(self, x: int) -> str: ...
    @classmethod
    def b(self, x: int) -> str: ...
    @staticmethod
    def c(x: int) -> str: ...

    def d[T](self, x: T) -> T: ...
    @classmethod
    def e[T](cls, x: T) -> T: ...
    @staticmethod
    def f[T](x: T) -> T: ...


def test_eval_call_with_types_07():
    ret = eval_call_with_types(
        GetAttr[ModuleClass, Literal["a"]], ModuleClass, int
    )
    assert ret is str
    ret = eval_call_with_types(
        GetAttr[ModuleClass, Literal["b"]], type(ModuleClass), int
    )
    assert ret is str
    ret = eval_call_with_types(GetAttr[ModuleClass, Literal["c"]], int)
    assert ret is str

    ret = eval_call_with_types(
        GetAttr[ModuleClass, Literal["d"]], ModuleClass, int
    )
    assert ret is int
    ret = eval_call_with_types(
        GetAttr[ModuleClass, Literal["e"]], type(ModuleClass), int
    )
    assert ret is int
    ret = eval_call_with_types(GetAttr[ModuleClass, Literal["f"]], int)
    assert ret is int


class ModuleGeneric[T]:
    def a(self, x: int) -> str: ...
    @classmethod
    def b(self, x: int) -> str: ...
    @staticmethod
    def c(x: int) -> str: ...

    def d[T](self, x: T) -> T: ...
    @classmethod
    def e[T](cls, x: T) -> T: ...
    @staticmethod
    def f[T](x: T) -> T: ...

    def g[U](self, x: T, y: U) -> U: ...
    @classmethod
    def h[U](cls, x: T, y: U) -> U: ...
    @staticmethod
    def i[U](x: T, y: U) -> U: ...


def test_eval_call_with_types_08():
    ret = eval_call_with_types(
        GetAttr[ModuleGeneric[float], Literal["a"]], ModuleGeneric[float], int
    )
    assert ret is str

    ret = eval_call_with_types(
        GetAttr[ModuleGeneric[float], Literal["b"]],
        ModuleGeneric[float],
        int,
    )
    assert ret is str

    ret = eval_call_with_types(GetAttr[ModuleGeneric[float], Literal["c"]], int)
    assert ret is str

    ret = eval_call_with_types(
        GetAttr[ModuleGeneric[float], Literal["d"]], ModuleGeneric[float], int
    )
    assert ret is int

    ret = eval_call_with_types(
        GetAttr[ModuleGeneric[float], Literal["e"]],
        ModuleGeneric[float],
        int,
    )
    assert ret is int

    ret = eval_call_with_types(GetAttr[ModuleGeneric[float], Literal["f"]], int)
    assert ret is int

    ret = eval_call_with_types(
        GetAttr[ModuleGeneric[float], Literal["g"]],
        ModuleGeneric[float],
        float,
        int,
    )
    assert ret is int

    ret = eval_call_with_types(
        GetAttr[ModuleGeneric[float], Literal["h"]],
        ModuleGeneric[float],
        float,
        int,
    )
    assert ret is int

    ret = eval_call_with_types(
        GetAttr[ModuleGeneric[float], Literal["i"]], float, int
    )
    assert ret is int


def test_eval_call_with_types_09():
    class C:
        def a(self, x: int) -> str: ...

    ret = eval_call_with_types(GetAttr[C, Literal["a"]], C, int)
    assert ret is str

    class C:
        @classmethod
        def b(cls, x: int) -> str: ...

    ret = eval_call_with_types(GetAttr[C, Literal["b"]], type(C), int)
    assert ret is str

    class C:
        @staticmethod
        def c(x: int) -> str: ...

    ret = eval_call_with_types(GetAttr[C, Literal["c"]], int)
    assert ret is str

    class C:
        def d[T](self, x: T) -> T: ...

    ret = eval_call_with_types(GetAttr[C, Literal["d"]], C, int)
    assert ret is int

    class C:
        @classmethod
        def e[T](cls, x: T) -> T: ...

    ret = eval_call_with_types(GetAttr[C, Literal["e"]], type(C), int)
    assert ret is int

    class C:
        @staticmethod
        def f[T](x: T) -> T: ...

    ret = eval_call_with_types(GetAttr[C, Literal["f"]], int)
    assert ret is int


def test_eval_call_with_types_10():
    class C[T]:
        def a(self, x: int) -> str: ...

    ret = eval_call_with_types(GetAttr[C[float], Literal["a"]], C[float], int)
    assert ret is str

    class C[T]:
        @classmethod
        def b(cls, x: int) -> str: ...

    ret = eval_call_with_types(GetAttr[C[float], Literal["b"]], C[float], int)
    assert ret is str

    class C[T]:
        @staticmethod
        def c(x: int) -> str: ...

    ret = eval_call_with_types(GetAttr[C[float], Literal["c"]], int)
    assert ret is str

    class C[T]:
        def d[T](self, x: T) -> T: ...

    ret = eval_call_with_types(GetAttr[C[float], Literal["d"]], C[float], int)
    assert ret is int

    class C[T]:
        @classmethod
        def e[T](cls, x: T) -> T: ...

    ret = eval_call_with_types(GetAttr[C[float], Literal["e"]], C[float], int)
    assert ret is int

    class C[T]:
        @staticmethod
        def f[T](x: T) -> T: ...

    ret = eval_call_with_types(GetAttr[C[float], Literal["f"]], int)
    assert ret is int

    class C[T]:
        def g[U](self, x: T, y: U) -> U: ...

    ret = eval_call_with_types(
        GetAttr[C[float], Literal["g"]], C[float], float, int
    )
    assert ret is int

    class C[T]:
        @classmethod
        def h[U](cls, x: T, y: U) -> U: ...

    ret = eval_call_with_types(
        GetAttr[C[float], Literal["h"]], C[float], float, int
    )
    assert ret is int

    class C[T]:
        @staticmethod
        def i[U](x: float, y: U) -> U: ...

    ret = eval_call_with_types(GetAttr[C[float], Literal["i"]], float, int)
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


def unwrap_with_copy[T](value: Wrapped[T]) -> WithCopy[T]: ...
def unwrap_with_eq[T](value: Wrapped[T]) -> WithEq[T]: ...


def test_eval_call_with_types_11():
    # Member function of a protocol
    # Returns same protocol

    cls = eval_call_with_types(with_copy, Foo)
    assert type(cls) is _ProtocolMeta

    fmt = format_helper.format_class(cls)
    assert fmt == textwrap.dedent("""\
        class WithCopy[tests.test_call.Foo]:
            a: int
            def copy(self: Self) -> WithCopy[tests.test_call.Foo]: ...
        """)

    ret = eval_call_with_types(GetAttr[cls, Literal["copy"]], WithCopy[Foo])
    assert ret == WithCopy[Foo]

    # Note: ret here is a generic TypeAliasType
    assert isinstance(ret, GenericAlias)
    assert isinstance(ret.__origin__, TypeAliasType)

    # Still renders the same as the original protocol
    fmt = format_helper.format_class(ret)
    assert fmt == textwrap.dedent("""\
        class WithCopy[tests.test_call.Foo]:
            a: int
            def copy(self: Self) -> WithCopy[tests.test_call.Foo]: ...
        """)

    # Make sure we can keep calling the member function
    ret2 = eval_call_with_types(GetAttr[ret, Literal["copy"]], WithCopy[Foo])
    assert ret2 == ret


def test_eval_call_with_types_12():
    # Member function of a protocol
    # Param is the same protocol
    # Returns bool

    cls = eval_call_with_types(with_eq, Foo)
    fmt = format_helper.format_class(cls)
    assert fmt == textwrap.dedent("""\
        class WithEq[tests.test_call.Foo]:
            a: int
            def __eq__(self: Self, other: WithEq[tests.test_call.Foo]) -> bool: ...
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


def test_eval_call_with_types_13():
    # Member function of a protocol
    # Param is a different type
    # Returns bool

    cls = eval_call_with_types(with_contains, Foo)
    fmt = format_helper.format_class(cls)
    assert fmt == textwrap.dedent("""\
        class WithContains[tests.test_call.Foo]:
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


def test_eval_call_with_types_14():
    # Member function of a protocol
    # Param is a different type
    # Returns a protocol based on the param type

    cls = eval_call_with_types(with_add, Foo)
    fmt = format_helper.format_class(cls)
    assert fmt == textwrap.dedent("""\
        class WithAdd[tests.test_call.Foo]:
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
        class WithAdd[tests.test_call.Bar]:
            a: str
            def __add__(self: Self, other: ~U) -> WithAdd[~U]: ...
        """)

    # Make sure we can keep calling the member function
    ret2 = eval_call_with_types(
        GetAttr[ret, Literal["__add__"]], WithAdd[Bar], Foo
    )
    assert ret2 == WithAdd[Foo]


def test_eval_call_with_types_15():
    cls = eval_call_with_types(with_max, Foo)
    fmt = format_helper.format_class(cls)
    assert fmt == textwrap.dedent("""\
        class WithMax[tests.test_call.Foo]:
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
