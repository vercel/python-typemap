A minor proposal that could be split out maybe:

Supporting ``Unpack`` of typevars for ``**kwargs``::

    def f[K: BaseTypedDict](**kwargs: Unpack[K]) -> K:
        return kwargs

Here ``BaseTypedDict`` is defined as::
    class BaseTypedDict(typing.TypedDict):
        pass

But any typeddict would be allowed there. (Or, maybe we should allow ``dict``?)

This is basically a combination of "PEP 692 – Using TypedDict for more precise **kwargs typing" and the behavior of ``Unpack`` for ``*args`` from "PEP 646 – Variadic Generics".


-----------------------------------------------------------------------

Grammar specification of the extensions to the type language.

It's important that there be a clearly specified type language for the type-level computation---we can't just be using some poorly specified subset of all Python.

TODO:
- Look into TupleTypeVar stuff for iteration

Big Q: what should be an error and what should return Never?


::

   <type> = ...
        | <type> if <type-bool> else <type>

        # Types with variadic arguments can have
        # *[... for t in ...] arguments
        | <ident>[<variadic-type-arg(<type>)> +]

        | <string-or-int-literal>  # Only accepted in arguments to new functions?


   # Type conditional checks are just boolean compositions of
   # subtype checking.
   <type-bool> =
         Is[<type>, <type>]
       | not <type-bool>
       | <type-bool> and <type-bool>
       | <type-bool> or <type-bool>

       # Do we want these next two? Probably not.
       | Any[<type-for(<type-bool>)>]
       | All[<type-for(<type-bool>)>]

   <variadic-type-arg(T)> =
         T ,
       | * <type-for-iter(T)> ,


   <type-for(T)> = [ T <type-for-iter>+ <type-for-if>* ]
   <type-for-iter> =
         # Iterate over a tuple type
         for <var> in Iter[<type>]
   <type-for-if> =
         if <type-bool>


``type-for(T)`` is a parameterized grammar rule, which can take different types. Not sure if we actually need this though---now it is only used for Any/All.

---

* ``GetArg[T, Base, Idx: Literal[str]]`` - returns the type argument number ``Idx`` to ``T`` when interpreted as ``Base``, or ``Never`` if it cannot be. (That is, if we have  ``class A(B[C]): ...``, then ``GetArg[A, B, 0] == C`` while ``GetArg[A, A, 0] == Never``)
* ``GetArgs[T, Base]`` - returns a tuple containing all of the type arguments of ``T`` when interpreted as ``Base``, or ``Never`` if it cannot be.
* ``FromUnion[T]`` - returns a tuple containing all of the union elements, or a 1-ary tuple containing T if it is not a union.


# TODO: NewProtocol needs a way of doing bases also...
# TODO: New TypedDict setup

* ``NewProtocol[*Ps: Member]``

* ``Members[T]`` produces a ``tuple`` of ``Member`` types.
* ``Member[N: Literal[str], T, Q: Quals, D]``

# These names are too long -- but we can't do ``Type`` !!
# Kind of want to do the *longer* ``MemberName``

* ``GetName[T: Member]``
* ``GetType[T: Member]``
* ``GetQuals[T: Member]``
* ``GetDefiner[T: Member]``
* Could we also put the defining type there??

---

* ``GetAttr[T, S: Literal[str]]``
  TODO: How should GetAttr interact with descriptors/classmethod? I am leaning towards it should apply the descriptor...

# TODO: how to deal with special forms like Callable and tuple[T, ...]

# TODO: How to do IsUnion? Might need a ``Length`` for tuples?


String manipulation operations for string Literal types.
We can put more in, but this is what typescript has.
``Slice`` and ``Concat`` are a poor man's literal template.
We can actually implement the case functions in terms of them and a
bunch of conditionals.


* ``Slice[S: Literal[str], Start: Literal[int | None], End: Literal[int | None]]``
* ``Concat[S1: Literal[str], S2: Literal[str]]``

* ``Uppercase[S: Literal[str]]``
* ``Lowercase[S: Literal[str]]``
* ``Capitalize[S: Literal[str]]``
* ``Uncapitalize[S: Literal[str]]``



-------------------------------------------------------------------------


Big open questions?

1.
PROBABLE DECISION: external library *and* restricted checking.

Can we actually implement Is (IsSubtype) at runtime in a satisfactory way?
 - There is a lot that needs to happen, like protocols and variance inference and callable subtyping (which might require matching against type vars...)
   Jukka points out that lots of type information is frequently missing at runtime too: attributes are frequently unannotated and

 - Could we slightly dodge the question by *not* adding the evaluation library to the standard library, and letting the operations be opaque.

   Then we would promise to have a third-party library, which would need to be "fit for purpose" for people to want to use, but would be free of the burden of being canonical?

 - I think we probably *can't* try to put it in the standard library. I think it would by nature bless the implementation with some degree of canonicity that I'm not sure we can back up. Different typecheckers don't always match on subtyping behavior, *and* it sometimes depends on config flags (like strict_optional in mypy). *And* we could imagine a bunch of other config flags: whether to be strict about argument names in protocols, for example.

 - We can instead have something simpler, which I will call ``IsSubSimilar``. ``IsSubSimilar`` would do *simple* checking of the *head* of types, essentially, without looking at type parameters. It would still lift over unions and would check literals.

   Probably need a better name.
   Honestly this is basically what is currently implemented for the examples, so it is probably good enough.

   It's unsatisfying, though.

2.
DECISION: quals string literals seems fine

How do we deal with modifiers? ClassVar, Final, Required, ReadOnly
 - One option is to treat them not as types by as *modifiers* and have them
   in a separate field where they are a union of Literals.
   So ``x: Final[ClassVar[int]]`` would appear in ``Attrs`` as
   ``Member[Literal['x'], int, Literal['Final' | 'ClassVar']]``

   This is kind of unsatisfying but I think it's probably right.
   We could also have a ``MemberUpdate[M: Member, T]`` that updates
   the type of a member but preserves its name and modifiers.

 - Otherwise need to treat them as types.


3.
How do we deal with Callables? We need to support extended callable syntax basically.
Or something like it.

4.
What do we do about ``Members`` on built-in types? ``typing.get_type_hints(int)`` returns ``{}`` but mypy will not agree!

An object of an empty user-defined class has 29 entries in ``dir`` (all dunders), and ``object()`` has 24. (In 3.14. In 3.12, it was 27 for the user-defined object).

5.
Polymorphic callables? How do we represent their type and how do we construct their type?

What does TS do here? - TS has full impredactive polymorphic functions. You can do System F stuff. *But* trying to do type level operations on them seems to lose track of the polymorphism: the type vars will get instantiated with ``unknown``.

6.
Want to be graceful at runtime, since **many** classes don't have full annotations.

=====

This proposal is less "well-typed" than typescript... (Well-kinded, maybe?)
Typescript has better typechecking at the alias definition site:
For ``P[K]``, ``K`` needs to have ``keyof P``...

Oh, we could maybe do better but it would require some new machinery.

* ``KeyOf[T]`` - literal keys of ``T``
* ``Member[T]``, when statically checking a type alias, could be treated as having some type like ``tuple[Member[KeyOf[T], object???, str], ...]``
* ``GetAttr[T, S: KeyOf[T]]`` - but this isn't supported yet. TS supports it.
* We would also need to do context sensitive type bound inference
