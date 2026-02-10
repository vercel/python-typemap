import annotationlib
import inspect
import types
import typing


def format_class_basic(cls: type) -> str:
    def format_meth(name, meth):
        root = inspect.unwrap(meth)
        sig = inspect.signature(root)

        ts = ""
        if params := root.__type_params__:
            ts = "[" + ", ".join(p.__name__ for p in params) + "]"

        return f"{name}{ts}{sig}"

    code = f"class {cls.__name__}:\n"
    for attr_name, attr_type in cls.__annotations__.items():
        attr_type_s = annotationlib.type_repr(attr_type)
        if attr_name in cls.__dict__:
            eq = f' = {cls.__dict__[attr_name]!r}'
        else:
            eq = ''
        code += f"    {attr_name}: {attr_type_s}{eq}\n"

    for name, attr in cls.__dict__.items():
        if attr is typing._no_init_or_replace_init:  # type: ignore[attr-defined]
            continue
        if isinstance(attr, classmethod):
            attr = inspect.unwrap(attr)  # type: ignore[arg-type]
            code += f"    @classmethod\n"
        elif isinstance(attr, staticmethod):
            attr = inspect.unwrap(attr)
            code += f"    @staticmethod\n"
        # Intentionally not elif; classmethod and staticmethod cases
        # fall through
        if isinstance(attr, (types.FunctionType, types.MethodType)):
            code += f"    def {format_meth(name, attr)}: ...\n"
    return code


def format_class(cls):
    from typemap.type_eval import flatten_class

    return format_class_basic(flatten_class(cls))
