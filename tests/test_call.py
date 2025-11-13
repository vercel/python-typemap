import textwrap


from typemap.type_eval import eval_call
from typemap.typing import (
    Attrs,
    NewProtocol,
    Member,
    GetName,
    Iter,
)

from . import format_helper


def func[**C](
    *args: C.args, **kwargs: C.kwargs
) -> NewProtocol[*[Member[GetName[c], int] for c in Iter[Attrs[C.kwargs]]]]: ...


def test_call_1():
    ret = eval_call(func, a=1, b=2, c="aaa")
    fmt = format_helper.format_class(ret)

    assert fmt == textwrap.dedent("""\
        class func[...]:
            a: int
            b: int
            c: int
        """)
