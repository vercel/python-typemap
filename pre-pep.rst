PEP: 9999
Title: Type Manipulation!
Author: Michael J. Sullivan <sully@msully.net>, Daniel W. Park <dnwpark@protonmail.com>, Yury Selivanov <yury@edgedb.com>
Sponsor: <name of sponsor>
PEP-Delegate: <PEP delegate's name>
Discussions-To: Pending
Status: Draft
Type: Standards Track
Topic: Typing
Requires: 0000
Created: <date created on, in dd-mmm-yyyy format>
Python-Version: 3.15 or 3.16
Post-History: Pending
Resolution: <url>


Abstract
========

We propose to add powerful type-level type introspection and type
construction facilities to the type system, inspired in large part by
TypeScript's conditional and mapped types, but adapted to the quite
different conditions of Python typing.

Motivation
==========

Python has a gradual type system, but at the heart of it is a fairly
conventional and tame static type system (apart from untagged union
types and type narrowing, which are common in gradual type systems but
not in traditional static ones).  In Python as a language, on the
other hand, it is not unusual to perform complex metaprogramming,
especially at the library layer.

Typically, type safety is lost when doing these sorts of things. Some
libraries come with custom mypy plugins, and a special-case
``@dataclass_transform`` decorator was added specifically to cover the
case of dataclass-like transformations (:pep:`PEP 681 <681>`).

Examples: pydantic/fastapi, dataclasses, sqlalchemy

Prisma-style ORMs
-----------------

`Prisma <#prisma_>`_, a popular ORM for TypeScript, allows writing
queries like (adapted from `this example <#prisma-example_>`_)::

  const user = await prisma.user.findMany({
    select: {
      name: true,
      email: true,
      posts: true,
    },
  });

for which the inferred type will be something like::

    {
        email: string;
        name: string | null;
        posts: {
            id: number;
            title: string;
            content: string | null;
            authorId: number | null;
        }[];
    }[]

Here, the output type is a combination of both existing information
about the type of ``prisma.user`` and the type of the argument to
``findMany``. It returns an array of objects containing the properties
of ``user`` that were requested; one of the requested elements,
``posts``, is a "relation" referencing another model; it has *all* of
its properties fetched but not its relations.

We would like to be able to do something similar in Python, perhaps
with a schema defined like::

    class Comment:
        id: Property[int]
        name: Property[str]
        poster: Link[User]


    class Post:
        id: Property[int]

        title: Property[str]
        content: Property[str]

        comments: MultiLink[Comment]
        author: Link[Comment]


    class User:
        id: Property[int]

        name: Property[str]
        email: Property[str]
        posts: Link[Post]

(In Prisma, a code generator generates type definitions based on a
prisma schema in its own custom format; you could imagine something
similar here, or that the definitions were hand written)

and a call like::

    db.select(
        User,
        name=True,
        email=True,
        posts=True,
    )

which would have return type ``list[<User>]`` where::

    class <User>:
        name: str
        email: str
        posts: list[<Post>]

    class <Post>
        id: int
        title: str
        content: str


Unlike the FastAPI-style example above, we probably don't have too
much need for runtime introspection of the types here, which is good:
inferring the type of a function is much less likely to be feasible.


.. _qb-impl:

Implementation
''''''''''''''

This will take something of a tutorial approach in discussing the
implementation, and explain the features being used as we use
them. More details were appear in the specification section.

First, to support the annotations we saw above, we have a collection
of dummy classes with generic types.

::

    class Pointer[T]:
        pass

    class Property[T](Pointer[T]):
        pass

    class Link[T](Pointer[T]):
        pass

    class SingleLink[T](Link[T]):
        pass

    class MultiLink[T](Link[T]):
        pass

The ``select`` method is where we start seeing new things.

The ``**kwargs: Unpack[K]`` is part of this proposal, and allows
*inferring* a TypedDict from keyword args.

``Attrs[K]`` extracts ``Member`` types corresponding to every
type-annotated attribute of ``K``, while calling ``NewProtocol`` with
``Member`` arguments constructs a new structural type.

``GetName`` is a getter operator that fetches the name of a ``Member``
as a literal type--all of these mechanisms lean very heavily on literal types.
``GetAttr`` gets the type of an attribute from a class.

::

    def select[ModelT, K: BaseTypedDict](
        typ: type[ModelT],
        /,
        **kwargs: Unpack[K],
    ) -> list[
        NewProtocol[
            *[
                Member[
                    GetName[c],
                    ConvertField[GetAttr[ModelT, GetName[c]]],
                ]
                for c in Iter[Attrs[K]]
            ]
        ]
    ]: ...

ConvertField is our first type helper, and it is a conditional type
alias, which decides between two types based on a (limited)
subtype-ish check.

In ``ConvertField``, we wish to drop the ``Property`` or ``Link``
annotation and produce the underlying type, as well as, for links,
producing a new target type containing only properties and wrapping
``MultiLink`` in a list.

::

    type ConvertField[T] = (
        AdjustLink[PropsOnly[PointerArg[T]], T] if IsSub[T, Link] else PointerArg[T]
    )

``PointerArg`` gets the type argument to ``Pointer`` or a subclass.

``GetArg[T, Base, I]`` is one of the core primitives; it fetches the
index ``I`` type argument to ``Base`` from a type ``T``, if ``T``
inherits from ``Base``.

(The subtleties of this will be discussed later; in this case, it just
grabs the argument to a ``Pointer``).

::

    type PointerArg[T: Pointer] = GetArg[T, Pointer, Literal[0]]

``AdjustLink`` sticks a ``list`` around ``MultiLink``, using features
we've discussed already.

::

    type AdjustLink[Tgt, LinkTy] = list[Tgt] if IsSub[LinkTy, MultiLink] else Tgt

And the final helper, ``PropsOnly[T]``, generates a new type that
contains all the ``Property`` attributes of ``T``.

::

    type PropsOnly[T] = list[
        NewProtocol[
            *[
                Member[GetName[p], PointerArg[GetType[p]]]
                for p in Iter[Attrs[T]]
                if IsSub[GetType[p], Property]
            ]
        ]
    ]

The full test is `in our test suite <#qb-test_>`_.


Automatically deriving FastAPI CRUD models
------------------------------------------

In the `FastAPI tutorial <#fastapi-tutorial_>`_, they show how to
build CRUD endpoints for a simple ``Hero`` type.  At its heart is a
series of class definitions used both to define the database interface
and to perform validation/filtering of the data in the endpoint::

    class HeroBase(SQLModel):
        name: str = Field(index=True)
        age: int | None = Field(default=None, index=True)


    class Hero(HeroBase, table=True):
        id: int | None = Field(default=None, primary_key=True)
        secret_name: str


    class HeroPublic(HeroBase):
        id: int


    class HeroCreate(HeroBase):
        secret_name: str


    class HeroUpdate(HeroBase):
        name: str | None = None
        age: int | None = None
        secret_name: str | None = None


The ``HeroPublic`` type is used as the return types of the read
endpoint (and is validated while being output, including having extra
fields stripped), while ``HeroCreate`` and ``HeroUpdate`` serve as
input types (automatically converted from JSON and validated based on
the types, using `Pydantic <#pydantic_>`_).

Despite all multiple types and duplication here, mechanical rules
could be written for deriving these types:

* Public should include all non-"hidden" fields, and the primary key
  should be made non-optional
* Create should include all fields except the primary key
* Update should include all fields except the primary key, but they
  should all be made optional and given a default value

With the definition of appropriate helpers, this proposal would allow writing::

    class Hero(NewSQLModel, table=True):
        id: int | None = Field(default=None, primary_key=True)

        name: str = Field(index=True)
        age: int | None = Field(default=None, index=True)

        secret_name: str = Field(hidden=True)

    type HeroPublic = Public[Hero]
    type HeroCreate = Create[Hero]
    type HeroUpdate = Update[Hero]

Those types, evaluated, would look something like::

    class HeroPublic:
        id: int
        name: str
        age: int | None


    class HeroCreate:
        name: str
        age: int | None = None
        secret_name: str


    class HeroUpdate:
        name: str | None = None
        age: int | None = None
        secret_name: str | None = None



While the implementation of ``Public``, ``Create``, and ``Update``
(presented in the next subsection) are certainly more complex than
duplicating code would be, they perform quite mechanical operations
and could be included in the framework library.

A notable feature of this use case is that it **depends on performing
runtime evaluation of the type annotations**. FastAPI uses the
Pydantic models to validate and convert to/from JSON for both input
and output from endpoints.


Implementation
''''''''''''''

We have a more `fully-worked example <#fastapi-test_>`_ in our test
suite, but here is a possible implementation of just ``Public``::

    # Extract the default type from an Init field.
    # If it is a Field, then we try pulling out the "default" field,
    # otherwise we return the type itself.
    type GetDefault[Init] = (
        GetFieldItem[Init, Literal["default"]] if IsSub[Init, Field] else Init
    )

    # Create takes everything but the primary key and preserves defaults
    type Create[T] = NewProtocol[
        *[
            Member[GetName[p], GetType[p], GetQuals[p], GetDefault[GetInit[p]]]
            for p in Iter[Attrs[T]]
            if not IsSub[
                Literal[True], GetFieldItem[GetInit[p], Literal["primary_key"]]
            ]
        ]
    ]

The ``Create`` type alias creates a new type (via ``NewProtocol``) by
iterating over the attributes of the original type.  It has access to
names, types, qualifiers, and the literal types of initializers (in
part through new facilities to handle the extremely common
``= Field(...)`` like pattern used here.

Here, we filter out attributes that have ``primary_key=True`` in their
``Field`` as well as extracting default arguments (which may be either
from a ``default`` argument to a field or specified directly as an
initializer).


dataclasses-style method generation
-----------------------------------

We would additionally like to be able to generate method signatures
based on the attributes of an object. The most well-known example of
this is probably generating ``__init__`` methods for dataclasses,
which we present a simplified example of. (In our test suites, this is
merged with the FastAPI-style example above, but it need not be).

This kind of pattern is widespread enough that :pep:`PEP 681 <681>`
was created to represent a lowest-common denominator subset of what
existing libraries do.

.. _init-impl:

Implementation
''''''''''''''

::

    # Generate the Member field for __init__ for a class
    type InitFnType[T] = Member[
        Literal["__init__"],
        Callable[
            [
                Param[Literal["self"], Self],
                *[
                    Param[
                        GetName[p],
                        GetType[p],
                        # All arguments are keyword-only
                        # It takes a default if a default is specified in the class
                        Literal["keyword"]
                        if IsSub[
                            GetDefault[GetInit[p]],
                            Never,
                        ]
                        else Literal["keyword", "default"],
                    ]
                    for p in Iter[Attrs[T]]
                ],
            ],
            None,
        ],
        Literal["ClassVar"],
    ]
    type AddInit[T] = NewProtocol[
        InitFnType[T],
        *[x for x in Iter[Members[T]]],
    ]


Specification of Needed Preliminaries
=====================================

(Some content is still in `spec-draft.rst <spec-draft.rst>`_).

We have two subproposals that are necessary to get mileage out of the
main part of this proposal.


Unpack of typevars for ``**kwargs``
-----------------------------------

A minor proposal that could be split out maybe:

Supporting ``Unpack`` of typevars for ``**kwargs``::

    def f[K: BaseTypedDict](**kwargs: Unpack[K]) -> K:
        return kwargs

Here ``BaseTypedDict`` is defined as::

    class BaseTypedDict(typing.TypedDict):
        pass

But any typeddict would be allowed there. (Or, maybe we should allow ``dict``?)

This is basically a combination of
"PEP 692 – Using TypedDict for more precise ``**kwargs`` typing"
and the behavior of ``Unpack`` for ``*args``
from "PEP 646 – Variadic Generics".

This is potentially moderately useful on its own but is being done to
support processing ``**kwargs`` with type level computation.

---

Extended Callables, take 2
--------------------------

We introduce a ``Param`` type the contains all the information about a function param::

    class Param[N: str | None, T, Q: ParamQuals = typing.Never]:
        pass

    ParamQuals = typing.Literal["*", "**", "default", "keyword"]

    type PosParam[N: str | None, T] = Param[N, T, Literal["positional"]]
    type PosDefaultParam[N: str | None, T] = Param[N, T, Literal["positional", "default"]]
    type DefaultParam[N: str, T] = Param[N, T, Literal["default"]]
    type NamedParam[N: str, T] = Param[N, T, Literal["keyword"]]
    type NamedDefaultParam[N: str, T] = Param[N, T, Literal["keyword", "default"]]
    type ArgsParam[T] = Param[Literal[None], T, Literal["*"]]
    type KwargsParam[T] = Param[Literal[None], T, Literal["**"]]

And then, we can represent the type of a function like::

    def func(
        a: int,
        /,
        b: int,
        c: int = 0,
        *args: int,
        d: int,
        e: int = 0,
        **kwargs: int
    ) -> int:
        ...

as (we are omiting the ``Literal`` in places)::

    Callable[
        [
            Param["a", int, "positional"],
            Param["b", int],
            Param["c", int, "default"],
            Param[None, int, "*"],
            Param["d", int, "keyword"],
            Param["e", int, Literal["default", "keyword"]],
            Param[None, int, "**"],
        ],
        int,
    ]


or, using the type abbreviations we provide::

    Callable[
        [
            PosParam["a", int],
            Param["b", int],
            DefaultParam["c", int,
            ArgsParam[int, "*"],
            NamedParam["d", int],
            NamedDefaultParam["e", int],
            KwargsParam[int],
        ],
        int,
    ]

(Rationale discussed :ref:`below <callable-rationale>`.)


Specification
=============

As was visible in the examples above, we introduce a few new syntactic
forms of valid types, but much of the power comes from type level
**operators** that will be defined in the ``typing`` module.


Grammar specification of the extensions to the type language
------------------------------------------------------------

Note first that no changes to the **Python** grammar are being
proposed, only to the grammar of what Python expressions are
considered as valid types.

(It's also slightly imprecise to call this a grammar: where operator
names are mentioned directly, like ``IsSub``, they require that name
to be imported, and it could also be used qualified as
``typing.IsSub`` or imported as a different name.)

::

   <type> = ...
        # Type booleans are all valid types too
        | <type-bool>

        # Conditional types
        | <type> if <type-bool> else <type>

        # Types with variadic arguments can have
        # *[... for t in ...] arguments
        | <ident>[<variadic-type-arg> +]

   # Type conditional checks are boolean compositions of
   # "subtype checking" and boolean Literal type checking.
   <type-bool> =
         IsSub[<type>, <type>]
       | Bool[<type>]
       | not <type-bool>
       | <type-bool> and <type-bool>
       | <type-bool> or <type-bool>

       # Do we want these next two? Maybe not.
       | Any[<variadic-type-arg> +]
       | All[<variadic-type-arg> +]

   <variadic-type-arg> =
         <type> ,
       | * <type-for-iter> ,


   <type-for> = [ <type> <type-for-iter>+ <type-for-if>* ]
   <type-for-iter> =
         # Iterate over a tuple type
         for <var> in Iter[<type>]
   <type-for-if> =
         if <type-bool>


.. _rt-support:


Runtime evaluation support
--------------------------

Rationale
=========

.. _callable-rationale:

Extended Callables
------------------

We need extended callable support, in order to inspect and produce
callables via type-level computation. mypy supports `extended
callables
<https://mypy.readthedocs.io/en/stable/additional_features.html#extended-callable-types>`__
but they are deprecated in favor of callback protocols.

Unfortunately callback protocols don't work well for type level
computation. (They probably could be made to work, but it would
require a separate facility for creating and introspecting *methods*,
which wouldn't be any simpler.)

I am proposing a fully new extended callable syntax because:
 1. The ``mypy_extensions`` functions are full no-ops, and we need
    real runtime objects
 2. They use parentheses and not brackets, which really goes against
    the philosophy here.
 3. We can make an API that more nicely matches what we are going to
    do for inspecting members (We could introduce extended callables that
    closely mimic the ``mypy_extensions`` version though, if something new
    is a non starter)


Backwards Compatibility
=======================

[Describe potential impact and severity on pre-existing code.]


Security Implications
=====================

None are expected.


How to Teach This
=================

I think some inspiration can be taken from how TypeScript teaches
their equivalent features.

(Though not complete inspiration---some important subtleties of things
like mapped types are unmentioned in current documentation
("homomorphic mappings").)


Reference Implementation
========================

[Link to any existing implementation and details about its state, e.g. proof-of-concept.]


Rejected Ideas
==============

Renounce all cares of runtime evaluation
----------------------------------------

This would have a lot of simplifying features.

We wouldn't need to worry about making ``IsSub`` be checkable at
runtime,

XXX


Support TypeScript style pattern matching in subtype checking
-------------------------------------------------------------

This would almost certainly only be possible if we also decide not to
care about runtime evaluation, as above.

.. _less_syntax:


Use type operators for conditional and iteration
------------------------------------------------

Instead of writing:
 * ``tt if tb else tf``
 * ``*[tres for T in Iter[ttuple]]``

we could use type operator forms like:
 * ``Cond[tb, tt, tf]``
 * ``UnpackMap[ttuple, lambda T: tres]``
 * or ``UnpackMap[ttuple, T, tres]`` where ``T`` must be a declared
   ``TypeVar``

Boolean operations would likewise become operators (``Not``, ``And``,
etc).

The advantage of this is that constructing a type annotation never
needs to do non-trivial computation, and thus we don't need
:ref:`runtime hooks <rt-support>` to support evaluating them.

It would also mean that it would be much easier to extract the raw
type annotation.  (The lambda form would still be somewhat fiddly.
The non-lambda form would be trivial to extract, but requiring the
declaration of a ``TypeVar`` goes against the grain of recent
changes.)

Another advantage is not needing any notion of a special
``<type-bool>`` class of types.

The disadvantage is that is that the syntax seems a *lot*
worse. Supporting filtering while mapping would make it even more bad
(maybe an extra argument for a filter?).

We can explore other options too if needed.


Open Issues
===========

* What is the best way to type base-class driven transformations using
  ``__init_subclass__`` or (*shudder* metaclasses).

* How to deal with situations where we are building new *nominal*
  types and might want to reference them?

[Any points that are still being decided/discussed.]


Acknowledgements
================

Jukka Lehtosalo

[Thank anyone who has helped with the PEP.]


Footnotes
=========

.. _#fastapi: https://fastapi.tiangolo.com/
.. _#pydantic: https://docs.pydantic.dev/latest/
.. _#fastapi-tutorial: https://fastapi.tiangolo.com/tutorial/sql-databases/#heroupdate-the-data-model-to-update-a-hero
.. _#fastapi-test: https://github.com/geldata/typemap/blob/main/tests/test_fastapilike_2.py
.. _#prisma: https://www.prisma.io/
.. _#prisma-example: https://github.com/prisma/prisma-examples/tree/latest/orm/express
.. _#qb-test: https://github.com/geldata/typemap/blob/main/tests/test_qblike_2.py

Copyright
=========

This document is placed in the public domain or under the
CC0-1.0-Universal license, whichever is more permissive.
