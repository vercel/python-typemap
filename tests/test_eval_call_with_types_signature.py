from typemap.type_eval import eval_call_with_types


def test_eval_call_with_types_accepts_positional_type_objects() -> None:
    def func[T](value: T) -> T:
        raise NotImplementedError

    assert eval_call_with_types(func, int) is int


def test_eval_call_with_types_accepts_keyword_type_objects() -> None:
    def func[T](*, value: T) -> T:
        raise NotImplementedError

    assert eval_call_with_types(func, value=str) is str
