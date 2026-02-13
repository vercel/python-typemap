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
Python-Version: 3.15
Post-History: Pending
Resolution: <url>


Abstract
========

We propose to add powerful type-level introspection and construction
facilities to the type system, inspired in large part by
TypeScript's conditional and mapped types, but adapted to the quite
different conditions of Python typing.

Motivation
==========

Python has a gradual type system, but at the heart of it is a *fairly*
conventional static type system.

In Python as a language, on the other hand, it is not unusual to
perform complex metaprogramming, especially in libraries and
frameworks. The type system typically cannot model metaprogramming.

To bridge the gap between metaprogramming and the type
system, some libraries come with custom mypy plugins (though then
other typecheckers suffer). The case of dataclass-like transformations
was considered common enough that a special-case
``@dataclass_transform`` decorator was added specifically to cover
that case (:pep:`681`).

We are proposing to add type manipulation facilities to the type
system that are more capable of keeping up with dynamic Python
code.

There does seem to be demand for this. In the analysis of the
responses to Meta's 2025 Typed Python Survey [#survey]_, the first
entry on the list of "Most Requested Features" was:

  **Missing Features From TypeScript and Other Languages**: Many respondents
  requested features inspired by TypeScript, such as **Intersection types**
  (like the & operator), **Mapped and Conditional types**, **Utility types**
  (like Pick, Omit, keyof, and typeof), and better **Structural typing** for
  dictionaries/dicts (e.g., more flexible TypedDict or anonymous types).

We will present a few examples of problems that could be solved with
more powerful type manipulation.

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
        author: Link[User]


    class User:
        id: Property[int]

        name: Property[str]
        email: Property[str]
        posts: Link[Post]

(In Prisma, a code generator generates type definitions based on a
prisma schema in its own custom format; you could imagine something
similar here, or that the definitions were hand-written)

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

    class <Post>:
        id: int
        title: str
        content: str


(Example code for implementing this :ref:`below <qb-impl>`.)


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

Despite the multiple types and duplication here, mechanical rules
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



While the implementation of ``Public``, ``Create``, and ``Update`` are
certainly more complex than duplicating code would be, they perform
quite mechanical operations and could be included in the framework
library.

A notable feature of this use case is that it **depends on performing
runtime evaluation of the type annotations**. FastAPI uses the
Pydantic models to validate and convert to/from JSON for both input
and output from endpoints.

Currently it is possible to do the runtime half of this: we could write
functions that generate Pydantic models at runtime based on whatever
rules we wished. But this is unsatisfying, because we would not be
able to properly statically typecheck the functions.

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

Making it possible for libraries to implement more of these patterns
directly in the type system will give better typing without needing
further special casing, typechecker plugins, hardcoded support, etc.

(Example code for implementing this :ref:`below <init-impl>`.)

More powerful decorator typing
------------------------------

The typing of decorator functions has long been a pain point in Python
typing. The situation was substantially improved by the introduction of
``ParamSpec`` in :pep:`612`, but a number of patterns remain
unsupported:

* Adding/removing/modifying a keyword parameter
* Adding/removing/modifying a variable number of parameters. (Though
  ``TypeVarTuple`` is close to being able to support adding and
  removing, if multiple unpackings were to be allowed, and Pyre
  implemented a ``Map`` operator that allowed modifying multiple.)

This proposal will cover those cases.

NumPy-style broadcasting
------------------------

One of the motivations for the introduction of ``TypeVarTuple`` in
:pep:`646` is to represent the shapes of multi-dimensional
arrays, such as::

  x: Array[float, L[480], L[640]] = Array()

The example in that PEP shows how ``TypeVarTuple`` can be used to
make sure that both sides of an arithmetic operation have matching
shapes. Most multi-dimensional array libraries, however, also support
broadcasting [#broadcasting]_, which allows the mixing of differently
shaped data.  With this PEP, we can define a ``Broadcast[A, B]`` type
alias, and then use it as a return type::

    class Array[DType, *Shape]:
        def __add__[*Shape2](
            self,
            other: Array[DType, *Shape2]
        ) -> Array[DType, *Broadcast[tuple[*Shape], tuple[*Shape2]]]:
            raise BaseException

(The somewhat clunky syntax of wrapping the ``TypeVarTuple`` in
another ``tuple`` is because typecheckers currently disallow having
two ``TypeVarTuple`` arguments. A possible improvement would be to
allow writing the bare (non-starred or ``Unpack``-ed) variable name to
mean its interpretation as a tuple.)

We can then do::

    a1: Array[float, L[4], L[1]]
    a2: Array[float, L[3]]
    a1 + a2  # Array[builtins.float, Literal[4], Literal[3]]

    b1: Array[float, int, int]
    b2: Array[float, int]
    b1 + b2  # Array[builtins.float, int, int]

    err1: Array[float, L[4], L[2]]
    err2: Array[float, L[3]]
    # err1 + err2  # E: Broadcast mismatch: Literal[2], Literal[3]


(Example code for implementing this :ref:`below <numpy-impl>`.)


Specification of Some Prerequisites
===================================

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

But any TypedDict would be allowed there.

Then, if we had a call like::

    x: int
    y: list[str]
    f(x=x, y=y)

the type inferred for ``K`` would be something like::

    TypedDict({'x': int, 'y': list[str]})

This is basically a combination of
"PEP 692 – Using TypedDict for more precise ``**kwargs`` typing"
and the behavior of ``Unpack`` for ``*args``
from "PEP 646 – Variadic Generics".

When inferring types here, the type checker should **infer literal
types when possible**.  This means inferring literal types for
arguments that **do not** appear in the bound, as well as
for arguments that **do** appear in the bound as read-only (TODO: Or
maybe we should make whether to do it for extra arguments
configurable in the ``TypedDict`` serving as the bound somehow? If
``readonly`` had been added as a parameter to ``TypedDict`` we would
use that.)

For each non-required item in the bound that does **not** have a
matching argument provided, then if the item is read-only, it will
have its type inferred as ``Never``, to indicate that it was not
provided.  (This can only be done for read-only items, since non
read-only items are invariant.)


This is potentially moderately useful on its own but is being done to
support processing ``**kwargs`` with type level computation.

---

Extended Callables, take 2
--------------------------

We introduce a ``Param`` type that contains all the information about a function param::

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

as (we are omitting the ``Literal`` in places)::

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
            DefaultParam["c", int],
            ArgsParam[int],
            NamedParam["d", int],
            NamedDefaultParam["e", int],
            KwargsParam[int],
        ],
        int,
    ]

(Rationale discussed :ref:`below <callable-rationale>`.)

TODO: Should the extended argument list be wrapped in a
``typing.Parameters[*Params]`` type (that will also kind of serve as a
bound for ``ParamSpec``)?


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

(It's also slightly imprecise to call this a grammar:
``<bool-operator>`` refers to any of the names defined in the
:ref:`Boolean Operators <boolean-ops>` section, which might be
imported qualified or with some other name)

::

   <type> = ...
        # Type booleans are all valid types too
        | <type-bool>

        # Conditional types
        | <type> if <type-bool> else <type>

        # Types with variadic arguments can have
        # *[... for t in ...] arguments
        | <ident>[<variadic-type-arg> +]

        | GenericCallable[<type>, lambda <args>: <type>]

   # Type conditional checks are boolean compositions of
   # boolean type operators
   <type-bool> =
         <bool-operator>[<type> +]
       | not <type-bool>
       | <type-bool> and <type-bool>
       | <type-bool> or <type-bool>
       | any(<type-bool-for>)
       | all(<type-bool-for>)

   <variadic-type-arg> =
         <type> ,
       | * [ <type-for-iter> ] ,


   <type-for> = <type> <type-for-iter>+ <type-for-if>*
   <type-for-iter> =
         # Iterate over a tuple type
         for <var> in Iter[<type>]
   <type-for-if> =
         if <type-bool>


(``<type-bool-for>`` is identical to ``<type-for>`` except that the
result type is a ``<type-bool>`` instead of a ``<type>``.)

There are three core syntactic features introduced: type booleans,
conditional types and unpacked comprehension types.

:ref:`"Generic callables" <generic-callable>` are also technically a
syntactic feature, but are discussed as an operator.

Type booleans
'''''''''''''

Type booleans are a special subset of the type language that can be
used in the body of conditionals.  They consist of the :ref:`Boolean
Operators <boolean-ops>`, defined below, potentially combined with
``and``, ``or``, ``not``, ``all``, and ``any``. For ``all`` and
``any``, the argument is a comprehension of type booleans, evaluated
in the same way as the :ref:`unpacked comprehensions <unpacked>`.

When evaluated, they will evaluate to ``Literal[True]`` or
``Literal[False]``.

(We want to restrict what operators may be used in a conditional
so that at runtime, we can have those operators produce "type" values
with appropriate behavior, without needing to change the behavior of
existing ``Literal[False]`` values and the like.)


Conditional types
'''''''''''''''''

The type ``true_typ if bool_typ else false_typ`` is a conditional
type, which resolves to ``true_typ`` if ``bool_typ`` is equivalent to
``Literal[True]`` and to ``false_typ`` otherwise.

``bool_typ`` is a type, but it needs syntactically be a type boolean,
defined above.

.. _unpacked:

Unpacked comprehension
''''''''''''''''''''''

An unpacked comprehension, ``*[ty for t in Iter[iter_ty]]`` may appear
anywhere in a type that ``Unpack[...]`` is currently allowed, and it
evaluates essentially to an ``Unpack`` of a tuple produced by a list
comprehension iterating over the arguments of tuple type ``iter_ty``.

The comprehension may also have ``if`` clauses, which filter in the
usual way.

Type operators
--------------

In some sections below we write things like ``Literal[int]`` to mean
"a literal that is of type ``int``". I don't think I'm really
proposing to add that as a notion, but we could.

.. _boolean-ops:

Boolean operators
'''''''''''''''''

* ``IsAssignable[T, S]``: Returns a boolean literal type indicating whether
  ``T`` is assignable to ``S``.

   (That is, it is a "consistent subtype". This is subtyping extended
   to gradual types.)

* ``IsEquivalent[T, S]``:
  Equivalent to ``IsAssignable[T, S] and IsAssignable[S, T]``.

* ``Bool[T]``: Returns ``Literal[True]`` if ``T`` is also
  ``Literal[True]`` or a union containing it.
  Equivalent to ``IsAssignable[T, Literal[True]] and not IsAssignable[T, Never]``.

  This is useful for invoking "helper aliases" that return a boolean
  literal type.

Basic operators
'''''''''''''''

* ``GetArg[T, Base, Idx: Literal[int]]``: returns the type argument
  number ``Idx`` to ``T`` when interpreted as ``Base``, or ``Never``
  if it cannot be. (That is, if we have  ``class A(B[C]): ...``, then
  ``GetArg[A, B, 0] == C`` while ``GetArg[A, A, 0] == Never``).

  Negative indexes work in the usual way.

  N.B: Runtime evaluation will only be able to support proper classes
  as ``Base``, *not* protocols. So, for example, ``GetArg[Ty,
  Iterable, 0]`` to get the type of something iterable will need to
  fail in a runtime evaluator. We should be able to allow it
  statically though.

  Special forms unfortunately
  require some special handling: the arguments list of a ``Callable``
  will be packed in a tuple, and a ``...`` will become
  ``SpecialFormEllipsis``.


* ``GetArgs[T, Base]``: returns a tuple containing all of the type
  arguments of ``T`` when interpreted as ``Base``, or ``Never`` if it
  cannot be.


* ``GetMemberType[T, S: Literal[str]]``: Extract the type of the
  member named ``S`` from the class ``T``.


* ``GetSpecialAttr[T: type, Attr: Literal[str]]``: Extracts the value
  of special attribute named ``Attr`` from the class ``T``. Valid
  attributes are ``__name__``, ``__module__``, and ``__qualname__``.
  Returns the value as a ``Literal[str]``.


* ``Length[T: tuple]`` - Gets the length of a tuple as an int literal
  (or ``Literal[None]`` if it is unbounded)


All of the operators in this section are :ref:`lifted over union types
<lifting>`.

Union processing
''''''''''''''''

* ``FromUnion[T]``: Returns a tuple containing all of the union
  elements, or a 1-ary tuple containing T if it is not a union.

* ``Union[*Ts]``: ``Union`` will become able to take variadic
  arguments, so that it can take unpacked comprehension arguments.


Object inspection
'''''''''''''''''

* ``Members[T]``: produces a ``tuple`` of ``Member`` types describing
  the members (attributes and methods) of class or typed dict ``T``.

  In order to allow typechecking time and runtime evaluation coincide
  more closely, **only members with explicit type annotations are included**.

* ``Attrs[T]``: like ``Members[T]`` but only returns attributes (not
  methods).

* ``GetMember[T, S: Literal[str]]``: Produces a ``Member`` type for the
  member named ``S`` from the class ``T``.

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
    the member is inherited from. Always ``Never``, for a ``TypedDict``)

* ``MemberQuals = Literal['ClassVar', 'Final', 'NotRequired', 'ReadOnly']`` -
  ``MemberQuals`` is the type of "qualifiers" that can apply to a
  member; currently ``ClassVar`` and ``Final`` apply to classes and
  ``NotRequired``, and ``ReadOnly`` to typed dicts


Methods are returned as callables using the new ``Param`` based
extended callables, and carrying the ``ClassVar``
qualifier. ``staticmethod`` and ``classmethod`` will return
``staticmethod`` and ``classmethod`` types, which are subscriptable as
of 3.14.

We also have helpers for extracting the fields of ``Members``; they
are all definable in terms of ``GetArg``. (Some of them are shared
with ``Param``, discussed below.)

* ``GetName[T: Member | Param]``
* ``GetType[T: Member | Param]``
* ``GetQuals[T: Member | Param]``
* ``GetInit[T: Member]``
* ``GetDefiner[T: Member]``

All of the operators in this section are :ref:`lifted over union types
<lifting>`.

Object creation
'''''''''''''''

* ``NewProtocol[*Ms: Member]``: Create a new structural protocol with members
  specified by ``Member`` arguments

* ``NewProtocolWithBases[Bases: tuple[type], *Ms: Member]`` - A variant that
  allows specifying bases too. TODO: Is this something we actually want?

* ``NewTypedDict[*Ps: Member]`` - Creates a new ``TypedDict`` with
  items specified by the ``Member`` arguments. TODO: Do we want a way
  to specify ``extra_items``?


N.B: Currently we aren't proposing any way to create nominal classes
or any way to make new *generic* types.


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
``Literal`` types where possible. (Though actually, this is just an
application of the rule that typevar unpacking in ``**kwargs`` should
use ``Literal`` types.)

So if we write::

  class A:
      foo: int = InitField(default=0, kw_only=True)

then we would infer the type ``InitField[TypedDict('...', {'default':
Literal[0], 'kw_only': Literal[True]})]`` for the initializer, and
that would be made available as the ``Init`` field of the ``Member``.


Annotated
'''''''''

TODO: This could maybe be dropped if it doesn't seem implementable?

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

.. _generic-callable:

Generic Callable
''''''''''''''''

* ``GenericCallable[Vs, lambda <vs>: Ty]``: A generic callable. ``Vs`` are a tuple
  type of unbound type variables and ``Ty`` should be a ``Callable``,
  ``staticmethod``, or ``classmethod`` that has access to the
  variables in ``Vs`` via the bound variables in ``<vs>``.

For now, we restrict the use of ``GenericCallable`` to
the type argument of ``Member`` (that is, to disallow its use for
locals, parameter types, return types, nested inside other types,
etc).

(This is a little unsatisfying. Rationale discussed :ref:`below
<generic-callable-rationale>`.)

TODO: Decide if we have any mechanisms to inspect/destruct
``GenericCallable``. Maybe can fetch the variable information and
maybe can apply it to concrete types?

Overloaded function types
'''''''''''''''''''''''''

* ``Overloaded[*Callables]`` - An overloaded function type, with the
  underlying types in order.

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

All of the operators in this section are :ref:`lifted over union types
<lifting>`.

Raise error
'''''''''''

* ``RaiseError[S: Literal[str], *Ts]``: If this type needs to be evaluated
  to determine some actual type, generate a type error with the
  provided message.

  Any additional type arguments should be included in the message.

Update class
''''''''''''

N.B: This is kind of sketchy but it is I think needed for defining
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


When an operation is lifted over union types, we take the cross
product of the union elements for each argument position, evaluate the
operator for each tuple in the cross product, and then union all of
the results together. In Python, the logic looks like::

    args_union_els = [get_union_elems(arg) for arg in args]
    results = [
        eval_operator(*xs)
        for xs in itertools.product(*args_union_els)
    ]
    if results:
        return Union[*results]
    else:
        return Never


.. _rt-support:

Runtime evaluation support
--------------------------

An important goal is supporting runtime evaluation of these computed
types.  We do not propose to add an official evaluator to the standard
library, but intend to release a third-party evaluator library.

While most of the extensions to the type system are "inert" type
operator applications, the syntax also includes list iteration and
conditionals, which will be automatically evaluated when the
``__annotate__`` method of a class, alias, or function is called.

In order to allow an evaluator library to trigger type evaluation in
those cases, we add a new hook to ``typing``:

* ``special_form_evaluator``: This is a ``ContextVar`` that holds a
  callable that will be invoked with a ``typing._GenericAlias``
  argument when ``__bool__`` is called on a
  :ref:`Boolean Operator <boolean-ops>` or ``__iter__`` is called
  on ``typing.Iter``.
  The returned value will then have ``bool`` or ``iter`` called upon
  it before being returned.

  If set to ``None`` (the default), the boolean operators will return
  ``False`` while ``Iter`` will evaluate to
  ``iter(typing.TypeVarTuple("_IterDummy"))``.


There has been some discussion of adding a ``Format.AST`` mode for
fetching annotations. That would combine extremely well with this
proposal, as it would make it easy to still fetch fully unevaluated
annotations.

Examples / Tutorial
===================

Here we will take something of a tutorial approach in discussing how
to achieve the goals in the examples in the motivation section,
explain the features being used as we use them.

.. _qb-impl:

Prisma-style ORMs
-----------------

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
``GetMemberType`` gets the type of an attribute from a class.

::

    def select[ModelT, K: typing.BaseTypedDict](
        typ: type[ModelT],
        /,
        **kwargs: Unpack[K],
    ) -> list[
        typing.NewProtocol[
            *[
                typing.Member[
                    typing.GetName[c],
                    ConvertField[typing.GetMemberType[ModelT, typing.GetName[c]]],
                ]
                for c in typing.Iter[typing.Attrs[K]]
            ]
        ]
    ]:
        raise NotImplementedError

ConvertField is our first type helper, and it is a conditional type
alias, which decides between two types based on a (limited)
subtype-ish check.

In ``ConvertField``, we wish to drop the ``Property`` or ``Link``
annotation and produce the underlying type, as well as, for links,
producing a new target type containing only properties and wrapping
``MultiLink`` in a list.

::

    type ConvertField[T] = (
        AdjustLink[PropsOnly[PointerArg[T]], T]
        if typing.IsAssignable[T, Link]
        else PointerArg[T]
    )

``PointerArg`` gets the type argument to ``Pointer`` or a subclass.

``GetArg[T, Base, I]`` is one of the core primitives; it fetches the
index ``I`` type argument to ``Base`` from a type ``T``, if ``T``
inherits from ``Base``.

(The subtleties of this will be discussed later; in this case, it just
grabs the argument to a ``Pointer``).

::

    type PointerArg[T] = typing.GetArg[T, Pointer, Literal[0]]

``AdjustLink`` sticks a ``list`` around ``MultiLink``, using features
we've discussed already.

::

    type AdjustLink[Tgt, LinkTy] = (
        list[Tgt] if typing.IsAssignable[LinkTy, MultiLink] else Tgt
    )

And the final helper, ``PropsOnly[T]``, generates a new type that
contains all the ``Property`` attributes of ``T``.

::

    type PropsOnly[T] = typing.NewProtocol[
        *[
            typing.Member[typing.GetName[p], PointerArg[typing.GetType[p]]]
            for p in typing.Iter[typing.Attrs[T]]
            if typing.IsAssignable[typing.GetType[p], Property]
        ]
    ]

The full test is `in our test suite <#qb-test_>`_.


.. _fastapi-impl:

Automatically deriving FastAPI CRUD models
------------------------------------------

We have a more `fully-worked example <#fastapi-test_>`_ in our test
suite, but here is a possible implementation of just ``Public``

::

    # Extract the default type from an Init field.
    # If it is a Field, then we try pulling out the "default" field,
    # otherwise we return the type itself.
    type GetDefault[Init] = (
        GetFieldItem[Init, Literal["default"]]
        if typing.IsAssignable[Init, Field]
        else Init
    )

    # Create takes everything but the primary key and preserves defaults
    type Create[T] = typing.NewProtocol[
        *[
            typing.Member[
                typing.GetName[p],
                typing.GetType[p],
                typing.GetQuals[p],
                GetDefault[typing.GetInit[p]],
            ]
            for p in typing.Iter[typing.Attrs[T]]
            if not typing.IsAssignable[
                Literal[True],
                GetFieldItem[typing.GetInit[p], Literal["primary_key"]],
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
    type InitFnType[T] = typing.Member[
        Literal["__init__"],
        Callable[
            [
                typing.Param[Literal["self"], Self],
                *[
                    typing.Param[
                        typing.GetName[p],
                        typing.GetType[p],
                        # All arguments are keyword-only
                        # It takes a default if a default is specified in the class
                        Literal["keyword"]
                        if typing.IsAssignable[
                            GetDefault[typing.GetInit[p]],
                            Never,
                        ]
                        else Literal["keyword", "default"],
                    ]
                    for p in typing.Iter[typing.Attrs[T]]
                ],
            ],
            None,
        ],
        Literal["ClassVar"],
    ]
    type AddInit[T] = typing.NewProtocol[
        InitFnType[T],
        *[x for x in typing.Iter[typing.Members[T]]],
    ]


.. _numpy-impl:

NumPy-style broadcasting
------------------------

::

    class Array[DType, *Shape]:
        def __add__[*Shape2](
            self, other: Array[DType, *Shape2]
        ) -> Array[DType, *Broadcast[tuple[*Shape], tuple[*Shape2]]]:
            raise BaseException

    type MergeOne[T, S] = (
        T
        if typing.IsEquivalent[T, S] or typing.IsEquivalent[S, Literal[1]]
        else S
        if typing.IsEquivalent[T, Literal[1]]
        else typing.RaiseError[Literal["Broadcast mismatch"], T, S]
    )

    type DropLast[T] = typing.Slice[T, Literal[0], Literal[-1]]
    type Last[T] = typing.GetArg[T, tuple, Literal[-1]]

    # Matching on Never here is intentional; it prevents infinite
    # recursions when T is not a tuple.
    type Empty[T] = typing.IsAssignable[typing.Length[T], Literal[0]]

    type Broadcast[T, S] = (
        S
        if typing.Bool[Empty[T]]
        else T
        if typing.Bool[Empty[S]]
        else tuple[
            *Broadcast[DropLast[T], DropLast[S]],
            MergeOne[Last[T], Last[S]],
        ]
    )


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


.. _generic-callable-rationale:

Generic Callable
----------------

Consider a method with the following signature::

    def process[T](self, x: T) -> T if IsAssignable[T, list] else list[T]:
        ...

The type of the method is generic, and the generic is bound at the
**method**, not the class. We need a way to represent such a generic
function both as a programmer might write it for a ``NewProtocol``.

One option that is somewhat appealing but doesn't work would be to use
unbound type variables and let them be generalized::

    type Foo = NewProtocol[
        Member[
            Literal["process"],
            Callable[[T], set[T] if IsAssignable[T, int] else T]
        ]
    ]

The problem is that this is basically incompatible with runtime
evaluation support, since evaluating the alias ``Foo`` will need to
evaluate the ``IsAssignable``, and so we will lose one side of the
conditional at least.  Similar problems will happen when evaluating
``Members`` on a class with generic functions.  By wrapping the body
in a lambda, we can delay evaluation in both of these cases.  (The
``Members`` case of delaying evaluation works quite nicely for
functions with explicit generic annotations. For old-style generics,
we'll probably have to try to evaluate it and then raise an error when
we encounter a variable.)


The reason we suggest restricting the use of ``GenericCallable`` to
the type argument of ``Member`` is because impredicative
polymorphism (where you can instantiate type variables with other
generic types) and rank-N types (where generics can be bound in nested
positions deep inside function types) are cans of worms when combined
with type inference [#undecidable]_.  While it would be nice to support,
we don't want to open that can of worms now.


The unbound type variable tuple is so that bounds and defaults and
``TypeVarTuple``-ness can be specified, though maybe we want to come
up with a new approach.


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

There is an in-progress proof-of-concept implementation in mypy [#ref-impl]_.

It can type check the ORM, FastAPI-style model derivation, and
NumPy-style broadcasting examples.

It is missing support for callables, ``UpdateClass``, annotation
processing, and various smaller things.

There is a demo of a runtime evaluator as well [#runtime]_.

Alternate syntax ideas
======================

AKA '"Rejected" Ideas That Maybe We Should Actually Do?'

Very interested in feedback about these!

The first one in particular I think has a lot of upside.

Support dot notation to access ``Member`` components
----------------------------------------------------

Code would read quite a bit nicer if we could write ``m.name`` instead
of ``GetName[m]``.
With dot notation, ``PropsOnly`` (from
:ref:`the query builder example <qb-impl>`) would look like::

    type PropsOnly[T] = typing.NewProtocol[
        *[
            typing.Member[p.name, PointerArg[p.type]]
            for p in typing.Iter[typing.Attrs[T]]
            if typing.IsAssignable[p.type, Property]
        ]
    ]

Which is a fair bit nicer.


We considered this but initially rejected it in part due to runtime
implementation concerns: an expression like ``Member[Literal["x"],
int].name`` would need to return an object that captures both the
content of the type alias while maintaining the ``_GenericAlias`` of
the applied class so that type variables may be substituted for.

We were mistaken about the runtime evaluation difficulty,
though: if we required a special base class in order for a type to use
this feature, it should work without too much trouble, and without
causing any backporting or compatibility problems.

We wouldn't be able to have the operation lift over unions or the like
(unless we were willing to modify ``__getattr__`` for
``types.UnionType`` and ``typing._UnionGenericAlias`` to do so!)

Or maybe it would be fine to have it only work on variables, and then
no special support would be required at the definition site.

That just leaves semantic and philosophical concerns: it arguably makes
the model more complicated, but a lot of code will read much nicer.

What would the mechanism be?
''''''''''''''''''''''''''''

A general mechanism to support this might look
like::

    class Member[
        N: str,
        T,
        Q: MemberQuals = typing.Never,
        I = typing.Never,
        D = typing.Never
    ]:
        type name = N
        type tp = T
        type quals = Q
        type init = I
        type definer = D

Where ``type`` aliases defined in a class can be accessed by dot notation.


Another option would be to skip introducing a general mechanism (for
now, at least), but at least make dot notation work on ``Member`` and
``Param``, which will be extremely common.


Dictionary comprehension based syntax for creating typed dicts and protocols
----------------------------------------------------------------------------

This is in some ways an extension of the :pep:`764` (still draft)
proposal for inline typed dictionaries.

Combined with the above proposal, using it for ``NewProtocol`` might
look (using something from :ref:`the query builder example <qb-impl>`)
something like:

::

    type PropsOnly[T] = typing.NewProtocol[
        {
            p.name: PointerArg[p.type]
            for p in typing.Iter[typing.Attrs[T]]
            if typing.IsAssignable[p.type, Property]
        }
    ]

Then we would probably also want to allow specifying a ``Member`` (but
reordered so that ``Name`` is last and has a default), for if we want
to specify qualifiers and/or an initializer type.

We could also potentially allow qualifiers to be written in the type,
though it is a little odd, since that is an annotation expression, not
a type expression, and you probably *wouldn't* be allowed to have an
annotation expression in an arm of a conditional type?

The main downside of this proposal is just complexity: it requires
introducing another kind of weird type form.

We'd also need to figure out the exact interaction between typeddicts
and new protocols. Would the dictionary syntax always produce a typed
dict, and then ``NewProtocol`` converts it to a protocol, or would
``NewProtocol[<dict type expr>]`` be a special form? Would we try to
allow ``ClassVar`` and ``Final``?

Destructuring?
''''''''''''''

The other potential "downside" (which might really be an upside!) is
that it suggests that we might want to be able to iterate over
``Attrs`` and ``Members`` with an ``items()`` style iterator, and that
raises more complicated questions.

First, the syntax would be something like::

    type PropsOnly[T] = typing.NewProtocol[
        {
            k: PointerArg[ty]
            for k, ty in typing.IterItems[typing.Attrs[T]]
            if typing.IsAssignable[ty, Property]
        }
    ]

This is looking pretty nice, but we only have access to the name and
the type, not the qualifiers or the initializers.

Potential options for dealing with this:

* It is fine, programmers can use this ``.items()`` style
  iterator for common cases and operate on full ``Member`` objects
  when they need to.
* We can put the qualifiers/initializer in the ``key``? Actually using
  the name would then require doing ``key.name`` or similar.

(We'd also need to figure out exactly what the rules are for what can
be iterated over this way.)

Call type operators using parens
--------------------------------

If people are having a bad time in Bracket City, we could also
consider making the built-in type operators use parens instead of
brackets.

Obviously this has some consistency issues but also maybe signals a
difference? Combined with dictionary-comprehensions and dot notation
(but not dictionary destructuring), it could look like::

    type PropsOnly[T] = typing.NewProtocol(
        {
            p.name: PointerArg[p.type]
            for p in typing.Iter(typing.Attrs(T))
            if typing.IsAssignable(p.type, Property)
        }
    )

(The user-defined type alias ``PointerArg`` still must be called with
brackets, despite being basically a helper operator.)


Rejected Ideas
==============

Renounce all cares of runtime evaluation
----------------------------------------

This would have a lot of simplifying features.

TODO: Expand

Support TypeScript style pattern matching in subtype checking
-------------------------------------------------------------

This would almost certainly only be possible if we also decide not to
care about runtime evaluation, as above.


Replace ``IsAssignable`` with something weaker than "assignable to" checking
----------------------------------------------------------------------------

Full python typing assignability checking is not fully implementable
at runtime (in particular, even if all the typeshed types for the
stdlib were made available, checking against protocols will often not
be possible, because class attributes may be inferred and have no visible
presence at runtime).

As proposed, a runtime evaluator will need to be "best effort",
ideally with the contours of that effort well-documented.

An alternative approach would be to have a weaker predicate as the
core primitive.

One possibility would be a "sub-similarity" check: ``IsAssignableSimilar``
would do *simple* checking of the *head* of types, essentially,
without looking at type parameters. It would not work with protocols.
It would still lift over unions and would check literals.

We decided it probably was not a good idea to introduce a new notion
that is similar to but not the same as subtyping, and that would need
to either have a long and weird name like ``IsAssignableSimilar`` or a
misleading short one like ``IsAssignable``.

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

Perform type manipulations with normal Python functions
-------------------------------------------------------

One suggestion has been, instead of defining a new type language
fragment for type-level manipulations, to support calling (some subset
of) Python functions that serve as kind-of "mini-mypy-plugins".

The main advantage (in our view) here would be leveraging a more
familiar execution model.

One suggested advantage is that it would be a simplification of the
proposal, but we feel that the simplifications promised by the idea
are mostly a mirage, and that calling Python functions to manipulate
types would be quite a bit *more* complicated.

It would require a well-defined and safe-to-run subset of the language
(and standard library) to be defined that could be run from within
typecheckers. Subsets like this have been defined in other system
(see `Starlark <#starlark_>`_, the configuration language for Bazel),
but it's still a lot of surface area, and programmers would need to
keep in mind the boundaries of it.

Additionally there would need to be a clear specification of how types
are represented in the "mini-plugin" functions, as well defining
functions/methods for performing various manipulations. Those
functions would have a pretty big overlap with what this PEP currently
proposes.

If runtime use is desired, then either the type representation would
need to be made compatible with how ``typing`` currently works or we'd
need to have two different runtime type representations.

Whether it would improve the syntax is more up for debate; I think
that adopting some of the syntactic cleanup ideas discussed above (but
not yet integrated into the main proposal) would improve the syntactic
situation at lower cost.


Make the type-level operations more "strictly-typed"
----------------------------------------------------

This proposal is less "strictly-typed" than typescript
(strictly-kinded, maybe?).

Typescript has better typechecking at the alias definition site:
For ``P[K]``, ``K`` needs to have ``keyof P``...

We could do potentially better but it would require more machinery.

* ``KeyOf[T]`` - literal keys of ``T``
* ``Member[T]``, when statically checking a type alias, could be
  treated as having some type like ``tuple[Member[KeyOf[T], object,
  str, ..., ...], ...]``
* ``GetMemberType[T, S: KeyOf[T]]`` - but this isn't supported yet.
  TS supports it.
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
.. _#fastapi-test: https://github.com/vercel/python-typemap/blob/main/tests/test_fastapilike_2.py
.. _#prisma: https://www.prisma.io/
.. _#prisma-example: https://github.com/prisma/prisma-examples/tree/latest/orm/express
.. _#qb-test: https://github.com/vercel/python-typemap/blob/main/tests/test_qblike_2.py
.. _#starlark: https://starlark-lang.org/

.. [#broadcasting] http://docs.scipy.org/doc/numpy/user/basics.broadcasting.html
.. [#ref-impl] https://github.com/msullivan/mypy/tree/typemap
.. [#runtime] https://github.com/vercel/python-typemap/
.. [#survey] https://engineering.fb.com/2025/12/22/developer-tools/python-typing-survey-2025-code-quality-flexibility-typing-adoption/
.. [#undecidable]

* "Partial polymorphic type inference is undecidable" by Hans Boehm: https://dl.acm.org/doi/10.1109/SFCS.1985.44
* "On the Undecidability of Partial Polymorphic Type Reconstruction" by Frank Pfenning: https://www.cs.cmu.edu/~fp/papers/CMU-CS-92-105.pdf

  Our setting does not try to infer generic types for functions,
  though, which might dodge some of the problems. On the other hand,
  we have subtyping. (Honestly we are already pretty deep into some
  of these cans of worms.)


Copyright
=========

This document is placed in the public domain or under the
CC0-1.0-Universal license, whichever is more permissive.
