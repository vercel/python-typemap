class _BoolExpr:
    pass


class _BoolValue:
    class _WrappedInstance:
        def __init__(self, value: bool, type_name: str):
            self._value = value
            self._type_name = type_name

        def __bool__(self):
            return self._value

        def __repr__(self):
            return f"typemap.typing.{self._type_name}[{self._value!r}]"

        def __eq__(self, other):
            return (
                isinstance(other, self.__class__)
                and self._value == other._value
            )

        def __hash__(self):
            return hash((self._type_name, self._value))

    def __init_subclass__(cls):
        cls.__true_instance = cls._WrappedInstance(True, cls.__name__)
        cls.__false_instance = cls._WrappedInstance(False, cls.__name__)

    def __class_getitem__(cls, item):
        if isinstance(item, type):
            raise TypeError(f"Expected literal type, got '{item.__name__}'")

        return cls.__true_instance if bool(item) else cls.__false_instance
