import textwrap

from typing import Callable, Literal

from typemap.type_eval import eval_typing
from typemap_extensions import (
    NewProtocol,
    Iter,
    Attrs,
    Member,
    NamedParam,
    Param,
    StrConcat,
)

from . import format_helper


class Schema:
    pass


class Type:
    pass


class Expression:
    pass


# hmmmm... recursion with this sort of thing will be funny...
# how will we handle the decorators or __init_subclass__ or what have you


class Property:
    name: str
    required: bool
    multi: bool
    typ: Type
    expr: Expression | None


type Schemaify[T] = NewProtocol[
    *[p for p in Iter[Attrs[T]]],
    *[
        Member[
            StrConcat[Literal["get_"], p.name],
            Callable[
                [
                    Param[Literal["self"], Schemaify[T]],
                    NamedParam[Literal["schema"], Schema, Literal["keyword"]],
                ],
                p.type,
            ],
            Literal["ClassVar"],
        ]
        for p in Iter[Attrs[T]]
    ],
]


def test_schema_like_1():
    tgt = eval_typing(Schemaify[Property])
    fmt = format_helper.format_class(tgt)

    assert fmt == textwrap.dedent("""\
    class Schemaify[tests.test_schemalike.Property]:
        name: str
        required: bool
        multi: bool
        typ: tests.test_schemalike.Type
        expr: tests.test_schemalike.Expression | None
        def get_name(self: Self, *, schema: tests.test_schemalike.Schema) -> str: ...
        def get_required(self: Self, *, schema: tests.test_schemalike.Schema) -> bool: ...
        def get_multi(self: Self, *, schema: tests.test_schemalike.Schema) -> bool: ...
        def get_typ(self: Self, *, schema: tests.test_schemalike.Schema) -> tests.test_schemalike.Type: ...
        def get_expr(self: Self, *, schema: tests.test_schemalike.Schema) -> tests.test_schemalike.Expression | None: ...
    """)
