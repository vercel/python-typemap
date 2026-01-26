PEP: 9999
Title: Type Manipulation
Author: Michael J. Sullivan <sully@msully.net>, Daniel W. Park <dnwpark@protonmail.com>, Yury Selivanov <yury@edgedb.com>
Sponsor: <name of sponsor>
PEP-Delegate: <PEP delegate's name>
Discussions-To: Pending
Status: Draft
Type: Standards Track
Topic: Typing
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


(Example code for implementing this :ref:`below <qb-impl>`.)



.. _fastapi-impl:

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

(Example code for implementing this :ref:`below <fastapi-impl>`.)


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

Make it possible for libraries to implement more of these patterns
directly in the type system will give better typing without needing
futher special casing, typechecker plugins, hardcoded support, etc.

(Example code for implementing this :ref:`below <init-impl>`.)


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


TODO: explain conditional types and iteration


Type operators
--------------

In some sections below we write things like ``Literal[int]]`` to mean
"a literal that is of type ``int``". I don't think I'm really
proposing to add that as a notion, but we could.

Boolean types
'''''''''''''

* ``IsSub[T, S]``: What we would **want** is that it returns a boolean
  literal type indicating whether ``T`` is a subtype of ``S``.
  To support runtime checking, we probably need something weaker.


Basic operators
'''''''''''''''

* ``GetArg[T, Base, Idx: Literal[int]]``: returns the type argument
  number ``Idx`` to ``T`` when interpreted as ``Base``, or ``Never``
  if it cannot be. (That is, if we have  ``class A(B[C]): ...``, then
  ``GetArg[A, B, 0] == C`` while ``GetArg[A, A, 0] == Never``).

  N.B: *Unfortunately* ``Base`` must be a proper class, *not* a
  protocol. So, for example, ``GetArg[Ty, Iterable, 0]]`` to get the
  type of something iterable *won't* work. This is because we can't do
  protocol checks at runtime in general.  Special forms unfortunately
  require some special handling: the arguments list of a ``Callable``
  will be packed in a tuple, and a ``...`` will become
  ``SpecialFormEllipsis``.


* ``GetArgs[T, Base]``: returns a tuple containing all of the type
  arguments of ``T`` when interpreted as ``Base``, or ``Never`` if it
  cannot be.


* ``GetAttr[T, S: Literal[str]]``: Extract the type of the member
  named ``S`` from the class ``T``.

* ``Length[T: tuple]`` - get the length of a tuple as an int literal
  (or ``Literal[None]`` if it is unbounded)


All of the operators in this section are "lifted" over union types.

Union processing
''''''''''''''''

* ``FromUnion[T]``: returns a tuple containing all of the union
  elements, or a 1-ary tuple containing T if it is not a union.



Object inspection
'''''''''''''''''

* ``Members[T]``: produces a ``tuple`` of ``Member`` types describing
  the members (attributes and methods) of class ``T``.

  In order to allow typechecking time and runtime evaluation coincide
  more closely, **only members with explicit type annotations are included**.

* ``Attrs[T]``: like ``Members[T]`` but only returns attributes (not
  methods).

* ``Member[N: Literal[str], T, Q: MemberQuals, Init, D]``: ``Member``,
  is a simple type, not an operator, that is used to describe members
  of classes.  Its type parameters encode the information about each
  member.

  * ``N`` is the name, as a literal string type
  * ``T`` is the type
  * ``Q`` is a union of qualifiers (see ``MemberQuals`` below)
  * ``Init`` is the literal type of the attribute initializer in the
    class (see :ref:`InitField <init-field>`)
  * ``D`` is the defining class of the member. (That is, which class
    the member is inherited from.)

* ``MemberQuals = Literal['ClassVar', 'Final']`` - ``MemberQuals`` is
  the type of "qualifiers" that can apply to a member; currently
  ``ClassVar`` and ``Final``


Methods are returned as callables using the new ``Param`` based
extended callables, and carrying the ``ClassVar``
qualifier. ``staticmethod`` and ``classmethod`` will return
``staticmethod`` and ``classmethod`` types, which are subscriptable as
of 3.14.

TODO: What do we do about decorators in general, *at runtime*... This
seems pretty cursed. We can probably sometimes evaluate them, if there
are annotations at runtime, but in general that would require full
subtype checking, which we can't do.

We also have helpers for extracting the fields of ``Members``; they
are all definable in terms of ``GetArg``. (Some of them are shared
with ``Param``, discussed below.)

* ``GetName[T: Member | Param]``
* ``GetType[T: Member | Param]``
* ``GetQuals[T: Member | Param]``
* ``GetInit[T: Member]``
* ``GetDefiner[T: Member]``



Object creation
'''''''''''''''

* ``NewProtocol[*Ps: Member]``

* ``NewProtocolWithBases[Bases, Ps: tuple[Member]]`` - A variant that
  allows specifying bases too. (UNIMPLEMENTED) - OR MAYBE SHOULD NOT EXIST

* ``NewTypedDict[*Ps: Member]`` -- TODO: Needs fleshing out; will work
  similarly to ``NewProtocol`` but has different flags



.. _init-field:

InitField
'''''''''

We want to be able to support transforming types based on
dataclasses/attrs/pydantic style field descriptors.  In order to do
that, we need to be able to consume things like calls to ``Field``.

Our strategy for this is to introduce a new type
``InitField[KwargDict]`` that collects arguments defined by a
``KwargDict: TypedDict``::

  class InitField[KwargDict: BaseTypedDict]:
      def __init__(self, **kwargs: typing.Unpack[KwargDict]) -> None:
          ...

      def _get_kwargs(self) -> KwargDict:
          ...

When ``InitField`` or (more likely) a subtype of it is instantiated
inside a class body, we infer a *more specific* type for it, based on
``Literal`` types for all the arguments passed.

So if we write::

  class A:
      foo: int = InitField(default=0)

then we would infer the type ``InitField[TypedDict('...', {'default':
Literal[0]})]`` for the initializer, and that would be made available
as the ``Init`` field of the ``Member``.


Annotated
'''''''''

This could maybe be dropped?

Libraries like FastAPI use annotations heavily, and we would like to
be able to use annotations to drive type-level computation decision
making.

We understand that this may be controversial, as currently ``Annotated``
may be fully ignored by typecheckers. The operations proposed are:

* ``GetAnnotations[T]`` - Fetch the annotations of a potentially
  Annotated type, as Literals. Examples::

    GetAnnotations[Annotated[int, 'xxx']] = Literal['xxx']
    GetAnnotations[Annotated[int, 'xxx', 5]] = Literal['xxx', 5]
    GetAnnotations[int] = Never


* ``DropAnnotations[T]`` - Drop the annotations of a potentially
  Annotated type. Examples::

    DropAnnotations[Annotated[int, 'xxx']] = int
    DropAnnotations[Annotated[int, 'xxx', 5]] = int
    DropAnnotations[int] = int


Callable inspection and creation
''''''''''''''''''''''''''''''''

``Callable`` types always have their arguments exposed in the extended
Callable format discussed above.

The names, type, and qualifiers share getter operations with
``Member``.

TODO: Should we make ``GetInit`` be literal types of default parameter
values too?

Generic Callable
''''''''''''''''

* ``GenericCallable[Vs, Ty]``: A generic callable. ``Vs`` are a tuple
  type of unbound type variables and ``Ty`` should be a ``Callable``,
  ``staticmethod``, or ``classmethod`` that has access to the
  variables in ``Vs``

This is kind of unsatisfying but we at least need some way to return
existing generic methods and put them back into a new protocol.


String manipulation
'''''''''''''''''''

String manipulation operations for string ``Literal`` types.
We can put more in, but this is what typescript has.
``Slice`` and ``Concat`` are a poor man's literal template.
We can actually implement the case functions in terms of them and a
bunch of conditionals, but shouldn't (especially if we want it to work
for all unicode!).


* ``Slice[S: Literal[str] | tuple, Start: Literal[int | None], End: Literal[int | None]]``:
  Slices a ``str`` or a tuple type.

* ``Concat[S1: Literal[str], S2: Literal[str]]``: concatenate two strings

* ``Uppercase[S: Literal[str]]``: uppercase a string literal
* ``Lowercase[S: Literal[str]]``: lowercase a string literal
* ``Capitalize[S: Literal[str]]``: capitalize a string literal
* ``Uncapitalize[S: Literal[str]]``: uncapitalize a string literal

All of the operators in this section are "lifted" over union types.

Raise error
'''''''''''

* ``RaiseError[S: Literal[str]]``: If this type needs to be evaluated
  to determine some actual type, generate a type error with the
  provided message.

Update class
''''''''''''

TODO: This is kind of sketchy but it is I think needed for defining
base classes and type decorators that do ``dataclass`` like things.

* ``UpdateClass[*Ps: Member]``: A special form that *updates* an
  existing nominal class with new members (possibly overriding old
  ones, or removing them by making them have type ``Never``).

  This can only be used in the return type of a type decorator
  or as the return type of ``__init_subclass__``.

One snag here: it introduces type-evaluation-order dependence; if the
``UpdateClass`` return type for some ``__init_subclass__`` inspects
some unrelated class's ``Members`` , and that class also has an
``__init_subclass__``, then the results might depend on what order they
are evaluated.

This does actually exactly mirror a potential **runtime**
evaluation-order dependence, though.

.. _lifting:

Lifting over Unions
-------------------

Many of the builtin operations are "lifted" over ``Union``.

For example::

    Concat[Literal['a'] | Literal['b'], Literal['c'] | Literal['d']] = (
        Literal['ac'] | Literal['ad'] | Literal['bc'] | Literal['bd']
    )


TODO: EXPLAIN


.. _rt-support:

Runtime evaluation support
--------------------------


Examples / Tutorial
===================

Here we will take something of a tutorial approach in discussing how
to achieve the goals in the examples in the motivation section,
explain the features being used as we use them.

.. _qb-impl:

Prisma-style ORMs
-----------------

More details were appear in the specification section.

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


.. _init-impl:

dataclasses-style method generation
-----------------------------------

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

Make the type-level operations more "strictly-typed"
----------------------------------------------------

This proposal is less "strictly-typed" than typescript
(strictly-kinded, maybe?).

Typescript has better typechecking at the alias definition site:
For ``P[K]``, ``K`` needs to have ``keyof P``...

We could do potentially better but it would require more meachinery.

* ``KeyOf[T]`` - literal keys of ``T``
* ``Member[T]``, when statically checking a type alias, could be
  treated as having some type like ``tuple[Member[KeyOf[T], object,
  str, ..., ...], ...]``
* ``GetAttr[T, S: KeyOf[T]]`` - but this isn't supported yet. TS supports it.
* We would also need to do context sensitive type bound inference


Open Issues
===========

* Should we support building new nominal types??

* What invalid operations should be errors and what should return ``Never``?

What exactly are the subtyping (etc) rules for unevaluated types
----------------------------------------------------------------

Because of generic functions, there will be plenty of cases where we
can't evaluate a type operator (because it's applied to an unresolved
type variable), and exactly what the type evaluation rules should be
in those cases is somewhat unclear.

Currently, in the proof of concept implementation in mypy, stuck type
evaluations implement subtype checking fully invariantly: we check
that the operators match and that every operand matches in both
arguments invariantly.


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
