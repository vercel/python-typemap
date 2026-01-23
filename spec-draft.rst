I AM INCREMENTALLY SHIFTING THINGS TO ``pre-pep.rst``


-----

Type operators
--------------

* ``GetArg[T, Base, Idx: Literal[int]]`` - returns the type argument number ``Idx`` to ``T`` when interpreted as ``Base``, or ``Never`` if it cannot be. (That is, if we have  ``class A(B[C]): ...``, then ``GetArg[A, B, 0] == C`` while ``GetArg[A, A, 0] == Never``).
  N.B: *Unfortunately* ``Base`` must be a proper class, *not* a protocol. So, for example, ``GetArg[Ty, Iterable, 0]]`` to get the type of something
  iterable *won't* work. This is because we can't do protocol checks at runtime in general.
  Special forms unfortunately require some special handling: the arguments list of a ``Callable`` will be packed in a tuple, and a ``...`` will become ``SpecialFormEllipsis``.


* ``GetArgs[T, Base]`` - returns a tuple containing all of the type arguments of ``T`` when interpreted as ``Base``, or ``Never`` if it cannot be.
* ``FromUnion[T]`` - returns a tuple containing all of the union elements, or a 1-ary tuple containing T if it is not a union.


Object inspection and creation
''''''''''''''''''''''''''''''

* ``NewProtocol[*Ps: Member]``


* ``Members[T]`` produces a ``tuple`` of ``Member`` types.
* ``Member[N: Literal[str], T, Q: MemberQuals, Init, D]`` - ``N`` is the name, ``T`` is the type, ``Q`` is a union of qualifiers, ``Init`` is the literal type of the class initializer (under what conditions!?) and ``D`` is the defining class of the member
* ``MemberQuals = Literal['ClassVar', 'Final']`` - ``MemberQuals`` is the type of "qualifiers" that can apply to a member; currently ClassVar and Final

Methods are returned as callables using the new ``Param`` based extended callables. staticmethod and classmethod will return ``staticmethod`` and ``classmethod`` types, which are subscriptable as of 3.14.

TODO: What do we do about decorators in general, *at runtime*... This seems pretty cursed. We can probably sometimes evaluate them, if there are annotations at runtime.

We also have helpers for extracting those names; they are all definable in terms of ``GetArg``. (Some of them are shared with ``Param``, discussed below.)
(These names are too long -- but we can't do ``Type``.)

* ``GetName[T: Member | Param]``
* ``GetType[T: Member | Param]``
* ``GetQuals[T: Member | Param]``
* ``GetInit[T: Member]``
* ``GetDefiner[T: Member]``

* ``NewProtocolWithBases[Bases, Ps: tuple[Member]]`` - A variant that allows specifying bases too. (UNIMPLEMENTED)

* ``NewTypedDict[*Ps: Member]`` -- TODO: Needs fleshing out; will work similarly to ``NewProtocol`` but has different flags


* ``GetAttr[T, S: Literal[str]]``
  TODO: How should GetAttr interact with descriptors/classmethod? I am leaning towards it should apply the descriptor...


Callable inspection and creation
''''''''''''''''''''''''''''''''

``Callable`` types always have their arguments exposed in the extended Callable format discussed above.

The names, type, and qualifiers share getter operations with ``Member``.

TODO: Should we make ``GetInit`` be literal types of default parameter values too?


----

* ``Length[T: tuple]`` - get the length of a tuple as an int literal (or ``Literal[None]`` if it is unbounded)

Annotated
'''''''''

Libraries like FastAPI use annotations heavily, and we would like to be able to use annotations to drive type-level computation decision making.

We understand that this may be controversial, as currently Annotated may be fully ignored by typecheckers. The operations proposed are:

* ``GetAnnotations[T]`` - Fetch the annotations of a potentially Annotated type, as Literals. Examples::

    GetAnnotations[Annotated[int, 'xxx']] = Literal['xxx']
    GetAnnotations[Annotated[int, 'xxx', 5]] = Literal['xxx', 5]
    GetAnnotations[int] = Never


* ``DropAnnotations[T]`` - Drop the annotations of a potentially Annotated type. Examples::

    DropAnnotations[Annotated[int, 'xxx']] = int
    DropAnnotations[Annotated[int, 'xxx', 5]] = int
    DropAnnotations[int] = int


InitField
'''''''''

We want to be able to support transforming types based on dataclasses/attrs/pydantic style field descriptors.  In order to do that, we need to be able to consume things like calls to ``Field``.

Our strategy for this is to introduce a new type ``InitField[KwargDict]`` that collects arguments defined by a ``KwargDict: TypedDict``::

  class InitField[KwargDict: BaseTypedDict]:
      def __init__(self, **kwargs: typing.Unpack[KwargDict]) -> None:
          ...

      def _get_kwargs(self) -> KwargDict:
          ...

When ``InitField`` or (more likely) a subtype of it is instantiated inside a class body, we infer a *more specific* type for it, based on ``Literal`` types for all the arguments passed.

So if we write::

  class A:
      foo: int = InitField(default=0)

then we would infer the type ``InitField[TypedDict('...', {'default': Literal[0]})]`` for the initializer, and that would be made available as the ``Init`` field of the ``Member``.

String manipulation
'''''''''''''''''''

String manipulation operations for string Literal types.
We can put more in, but this is what typescript has.
``Slice`` and ``Concat`` are a poor man's literal template.
We can actually implement the case functions in terms of them and a
bunch of conditionals, but shouldn't (especially if we want it to work for all unicode!).


* ``Slice[S: Literal[str], Start: Literal[int | None], End: Literal[int | None]]``
* ``Concat[S1: Literal[str], S2: Literal[str]]``

* ``Uppercase[S: Literal[str]]``
* ``Lowercase[S: Literal[str]]``
* ``Capitalize[S: Literal[str]]``
* ``Uncapitalize[S: Literal[str]]``

----

Two possibilities for creating parameterized functions/types. They are kind of more syntax than functions exactly.  I like the lambda one more.

* ``NewParameterized[V, Ty]`` - ``V`` should be a ``TypeVar`` (ugh!) and ``Ty`` should be a ``Callable`` or a ``NewProtocol`` or some such.
* ``NewParameterized[lambda v: Ty]`` - The lambda could take multiple params, and introduce multiple variables. The biggest snag is how to specify bounds; one option is via default arguments.

How to *inspect* generic function types? Honestly, it doesn't really work in Typescript. Maybe we don't need to deal with it either.

Big (open?) questions
---------------------

1.
Can we actually implement IsSubtype at runtime in a satisfactory way? (PROBABLE DECISION: external library *and* restricted checking.)
 - There is a lot that needs to happen, like protocols and variance inference and callable subtyping (which might require matching against type vars...)
   Jukka points out that lots of type information is frequently missing at runtime too: attributes are frequently unannotated and

 - Could we slightly dodge the question by *not* adding the evaluation library to the standard library, and letting the operations be opaque.

   Then we would promise to have a third-party library, which would need to be "fit for purpose" for people to want to use, but would be free of the burden of being canonical?

 - I think we probably *can't* try to put it in the standard library. I think it would by nature bless the implementation with some degree of canonicity that I'm not sure we can back up. Different typecheckers don't always match on subtyping behavior, *and* it sometimes depends on config flags (like strict_optional in mypy). *And* we could imagine a bunch of other config flags: whether to be strict about argument names in protocols, for example.

 - We can instead have something simpler, which I will call ``IsSubSimilar``. ``IsSubSimilar`` would do *simple* checking of the *head* of types, essentially, without looking at type parameters. It would still lift over unions and would check literals.

   Probably need a better name.
   Honestly this is basically what is currently implemented for the examples, so it is probably good enough.

   It's unsatisfying, though.

2. How do we deal with modifiers? ClassVar, Final, Required, ReadOnly (DECISION: quals string literals seems fine)
 - One option is to treat them not as types by as *modifiers* and have them
   in a separate field where they are a union of Literals.
   So ``x: Final[ClassVar[int]]`` would appear in ``Attrs`` as
   ``Member[Literal['x'], int, Literal['Final' | 'ClassVar']]``

   This is kind of unsatisfying but I think it's probably right.
   We could also have a ``MemberUpdate[M: Member, T]`` that updates
   the type of a member but preserves its name and modifiers.

 - Otherwise need to treat them as types.


3.
How do we deal with Callables? We need to support extended callable syntax basically. Or something like it. (ANSWER: ``Param``)

4.
What do we do about ``Members`` on built-in types? ``typing.get_type_hints(int)`` returns ``{}`` but mypy will not agree!

An object of an empty user-defined class has 29 entries in ``dir`` (all dunders), and ``object()`` has 24. (In 3.14. In 3.12, it was 27 for the user-defined object).

5.
Polymorphic callables? How do we represent their type and how do we construct their type?

What does TS do here? - TS has full impredactive polymorphic functions. You can do System F stuff. *But* trying to do type level operations on them seems to lose track of the polymorphism: the type vars will get instantiated with ``unknown``.

6.
What operations should be error and what should return Never?


----

This proposal is less "well-typed" than typescript... (Well-kinded, maybe?)
Typescript has better typechecking at the alias definition site:
For ``P[K]``, ``K`` needs to have ``keyof P``...

Oh, we could maybe do better but it would require some new machinery.

* ``KeyOf[T]`` - literal keys of ``T``
* ``Member[T]``, when statically checking a type alias, could be treated as having some type like ``tuple[Member[KeyOf[T], object???, str], ...]``
* ``GetAttr[T, S: KeyOf[T]]`` - but this isn't supported yet. TS supports it.
* We would also need to do context sensitive type bound inference
