# Demonstrate how something like Pydantic might use this library to
# enforce type annotations.

import pytest

from typing import _GenericAlias  # type: ignore[attr-defined]

import typemap_extensions as typing

from typemap.type_eval import eval_typing, flatten_class


class BaseModel:
    def __init__(self, *, _alias=None, **kwargs):
        to_eval = _alias or type(self)
        # This is somewhat careless, a real implementation would
        # probably do more checking and produce better errors
        # Also, it would do caching.

        # * eval_typing evaluates the class, substituting in type variables
        # * flatten_class generates a merged class that has all the
        #   annotations from the whole mro present
        ocls = flatten_class(eval_typing(to_eval))
        annos = ocls.__annotations__

        for k, v in kwargs.items():
            # A real implementation would also have to do more here,
            # like handle containers, etc!
            if not isinstance(v, annos[k]):
                raise TypeError(
                    f'Invalid type for {k} - '
                    f'got {type(v)} but needed {annos[k]}'
                )
            setattr(self, k, v)

    @classmethod
    def __class_getitem__(cls, args):
        # Return an _BaseModelAlias instead of a _GenericAlias
        res = super().__class_getitem__(args)
        return _BaseModelAlias(res.__origin__, res.__args__)

    def __repr__(self):
        # Just debugging output
        return f'{type(self).__name__}(**{self.__dict__})'


class _BaseModelAlias(_GenericAlias, _root=True):  # type: ignore[call-arg]
    def __call__(self, *args, **kwargs):
        return self.__origin__(*args, **kwargs, _alias=self)


#######


class Foo[T](BaseModel):
    x: int
    y: T


def test_model_like_1():
    Foo[str](x=0, y='yes')  # OK
    with pytest.raises(TypeError):
        Foo[str](x=0, y=False)  # error


class MyModel[T](BaseModel):
    x: T
    y: int if typing.IsAssignable[T, int] else str


def test_model_like_2():
    MyModel[int](x=1, y=1)  # OK
    MyModel[float](x=1.0, y="x")  # OK
    with pytest.raises(TypeError):
        MyModel[float](x=1.0, y=1)  # error, second arg must be str
