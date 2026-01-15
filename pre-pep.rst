PEP: <REQUIRED: pep number>
Title: Type-level Computation
Author: Michael J. Sullivan <sully@msully.net>, Daniel Park <dnwpark@protonmail.com>, Yury Selivanov <yury@vercel.com>
Sponsor: <name of sponsor>
PEP-Delegate: <PEP delegate's name>
Discussions-To: Pending
Status: DRAFT
Type: Standards Track
Topic: Typing
Requires: <pep numbers>
Created: <date created on, in dd-mmm-yyyy format>
Python-Version: 3.15 or 3.16
Post-History: Pending
Resolution: <url>


Abstract
========

We propose to add powerful type-level type introspection and type
construction facilities to the type system, inspired in large part by
TypeScript's conditional and mapping types, but adapted to the quite
different conditions of Python typing.

Motivation
==========

[Clearly explain why the existing language specification is inadequate to address the problem that the PEP solves.]


Rationale
=========

Python has a gradual type system, but at the heart of it is a fairly
conventional and tame static type system.  In Python as a language, on
the other hand, it is not unusual to perform complex metaprogramming,
especially at the library layer.

Typically, type safety is lost when doing these sorts of things. Some
libraries come with custom mypy plugins, and a special-case
``@dataclass_transform`` decorator was added specifically to cover the
case of dataclass-like transformations (:pep:`PEP 681 <681>`).

pydantic, dataclasses, sqlalchemy

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
        GetFieldItem[Init, Literal["default"]] if Sub[Init, Field] else Init
    )

    # Create takes everything but the primary key and preserves defaults
    type Create[T] = NewProtocol[
        *[
            Member[GetName[p], GetType[p], GetQuals[p], GetDefault[GetInit[p]]]
            for p in Iter[Attrs[T]]
            if not Sub[
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


Prisma-style ORMs
-----------------

`Prisma <#prisma_>`_, a popular ORM for TypeScript, allows writing
queries like (adapted from `this example <#prisma-example_>`_::

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


Implementation
''''''''''''''

We have a more `worked example <#qb-test_>`_ in our test suite.



Specification
=============

[Describe the syntax and semantics of any new language feature.]


Backwards Compatibility
=======================

[Describe potential impact and severity on pre-existing code.]


Security Implications
=====================

None are expected.


How to Teach This
=================

Honestly this seems very hard!


Reference Implementation
========================

[Link to any existing implementation and details about its state, e.g. proof-of-concept.]


Rejected Ideas
==============

[Why certain ideas that were brought while discussing this PEP were not ultimately pursued.]


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
