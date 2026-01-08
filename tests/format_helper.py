import annotationlib
import inspect
import types
import typing


def format_class(cls: type) -> str:
    def format_meth(meth):
        root = inspect.unwrap(meth)
        sig = inspect.signature(root)

        ts = ""
        if params := root.__type_params__:
            ts = "[" + ", ".join(str(p) for p in params) + "]"

        return f"{root.__name__}{ts}{sig}"

    code = f"class {cls.__name__}:\n"
    for attr_name, attr_type in cls.__annotations__.items():
        attr_type_s = annotationlib.type_repr(attr_type)
        code += f"    {attr_name}: {attr_type_s}\n"

    for attr in cls.__dict__.values():
        if attr is typing._no_init_or_replace_init:
            continue
        if isinstance(attr, classmethod):
            attr = inspect.unwrap(attr)
            code += f"    @classmethod\n"
        elif isinstance(attr, staticmethod):
            attr = inspect.unwrap(attr)
            code += f"    @staticmethod\n"
        # Intentionally not elif; classmethod and staticmethod cases
        # fall through
        if isinstance(attr, (types.FunctionType, types.MethodType)):
            code += f"    def {format_meth(attr)}: ...\n"
    return code
