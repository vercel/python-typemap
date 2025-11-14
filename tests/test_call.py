import textwrap

from typing import Unpack

from typemap.type_eval import eval_call
from typemap.typing import (
    Attrs,
    NewProtocol,
    Member,
    GetName,
    Iter,
)

from . import format_helper


def func[*T, K: dict](
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
