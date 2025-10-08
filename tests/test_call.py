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
        class Protocol:
            a: int
            b: int
            c: int
        """)
