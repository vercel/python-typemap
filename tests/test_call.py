import textwrap

from typemap.type_eval import eval_call
from typemap import typing as next

from . import format_helper


def func[C: next.CallSpec](
    *args: C.args, **kwargs: C.kwargs
) -> next.NewProtocol[
    [next.Property[c.name, int] for c in next.CallSpecKwargs[C]]
]: ...


def test_call_1():
    ret = eval_call(func, a=1, b=2, c="aaa")
    fmt = format_helper.format_class(ret)

    assert fmt == textwrap.dedent("""\
        class func[...]:
            a: int
            b: int
            c: int
        """)


# Basic filtering
class Tgt:
    pass


class A:
    x: int
    y: bool | None
    z: Tgt
    w: list[str]


def select[C: next.CallSpec](
    __rcv: A, *args: C.args, **kwargs: C.kwargs
) -> next.NewProtocol[
    [
        next.Property[
            c.name,
            next.GetAttr[A, c.name],
        ]
        for c in next.CallSpecKwargs[C]
    ]
]: ...


def test_call_2():
    ret = eval_call(
        select,
        A(),
        x=True,
        w=True,
    )
    fmt = format_helper.format_class(ret)

    print()
    print(fmt)
