import ast
import contextvars
import dataclasses
import typing
from typing import _GenericAlias  # type: ignore


_SpecialForm: typing.Any = typing._SpecialForm


# TODO: type better
_special_form_evaluator: contextvars.ContextVar[
    typing.Callable[[typing.Any], typing.Any] | None
] = contextvars.ContextVar("special_form_evaluator", default=None)


class _IterGenericAlias(_GenericAlias, _root=True):  # type: ignore[call-arg]
    def __iter__(self):
        evaluator = _special_form_evaluator.get()
        if evaluator:
            return evaluator(self)
        else:
            return iter(typing.TypeVarTuple("_IterDummy"))


class _BoolGenericAlias(_GenericAlias, _root=True):  # type: ignore[call-arg]
    def __bool__(self):
        evaluator = _special_form_evaluator.get()
        if evaluator:
            return evaluator(self)
        else:
            return False


_IsGenericAlias = _BoolGenericAlias


_bool_special_form_registry: dict[typing.Any, BoolSpecialMetadata] = {}


@dataclasses.dataclass(frozen=True, kw_only=True)
class BoolSpecialMetadata:
    cls: type
    type_params: tuple[type]
    expr_node: ast.AST


def _register_bool_special_form(cls):
    import inspect
    import textwrap

    type_params = getattr(cls, '__type_params__', ())

    if '__expr__' not in cls.__dict__:
        raise TypeError(f"{cls.__name__} must have an '__expr__' field")

    # Parse __expr__ to get the assigned expression
    source = inspect.getsource(cls)
    source = textwrap.dedent(source)
    tree = ast.parse(source)

    expr_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.AnnAssign):
                    # __expr__: SomeType = expression
                    if (
                        isinstance(item.target, ast.Name)
                        and item.target.id == '__expr__'
                    ):
                        expr_node = item.value
                        break
                elif isinstance(item, ast.Assign):
                    # __expr__ = expression
                    for target in item.targets:
                        if (
                            isinstance(target, ast.Name)
                            and target.id == '__expr__'
                        ):
                            expr_node = item.value
                            break
                    if expr_node:
                        break
            if expr_node:
                break

    if expr_node is None:
        raise TypeError(f"Could not find __expr__ assignment in {cls.__name__}")

    def impl_func(self, params):
        return _BoolGenericAlias(self, params)

    sf = _SpecialForm(impl_func)

    _bool_special_form_registry[sf] = BoolSpecialMetadata(
        cls=cls,
        type_params=type_params,
        expr_node=expr_node,
    )

    return sf
