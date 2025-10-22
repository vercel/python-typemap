
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

        # This is syntax because taking an int literal makes it a
        # special form.
        | GetArg[<type>, <int-literal>]


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


``type-for(T)`` is a parameterized grammar rule, which can take
different types. Not sure if we actually need this though---now it is
only used for Any/All.

---

# TODO: NewProtocol needs a way of doing bases also...
# TODO: New TypedDict setup
* ``NewProtocol[*Ps: Member]``

* ``Members[T]`` produces a ``tuple`` of ``Member`` types.
* ``Member[N: Literal & str, T]``
# These names are too long -- but we can't do ``Type`` !!
* ``GetName[T: Member]``
* ``GetType[T: Member]``
* Could we also put the defining type there??

---

* ``GetAttr[T, S: Literal & str]``

# TODO: how to deal with special forms like Callable and tuple[T, ...]
* ``GetArgs[T]`` - returns a tuple containing all of the type arguments
* ``FromUnion[T]`` - returns a tuple containing all of the union
  elements, or a 1-ary tuple containing T if it is not a union.

# TODO: How to do IsUnion?


String manipulation operations for string Literal types.
We can put more in, but this is what typescript has.

* ``Uppercase[S: Literal & str]``
* ``Lowercase[S: Literal & str]``
* ``Capitalize[S: Literal & str]``
* ``Uncapitalize[S: Literal & str]``


-------------------------------------------------------------------------


Big open questions?

1.
Can we actually implement Is (IsSubtype) at runtime in a satisfactory way?
 - Could we slightly dodge the question by *not* adding the evaluation library to the standard library, and letting the operations be opaque.

   Then we would promise to have a third-party library, which would need to be "fit for purpose" for people to want to use, but would be free of the burden of being canonical?

  There is a lot that needs to happen, like protocols and variance inference and
callable subtyping (which might require matching against type vars...)

 - I think we probably *can't* try to put it in the standard library. I think it would by nature bless the implementation with some degree of canonicity that I'm not sure we can back up. Different typecheckers don't always match on subtyping behavior, *and* it sometimes depends on config flags (like strict_optional in mypy). *And* we could imagine a bunch of other config flags: whether to be strict about argument names in protocols, for example.

 - We can instead have something simpler, which I will call ``Matches``. ``Matches`` would do *simple* checking of the *head* of types, essentially, without looking at type parameters. It would still lift over unions and would check literals.
   Honestly this is basically what is currently implemented for the examples, so it is probably good enough.

   It's unsatisfying, though.

2.
How do we deal with modifiers? ClassVar, Final, Required, ReadOnly
 - One option is to treat them not as types by as *modifiers* and have them
   in a separate field where they are a union of Literals.
   So ``x: Final[ClassVar[int]]`` would appear in ``Attrs`` as
   ``Member[Literal['x'], int, Literal['Final' | 'ClassVar']]``

   This is kind of unsatisfying but I think it's probably right.
   We could also have a ``MemberUpdate[M: Member, T]`` that updates
   the type of a member but preserves its name and modifiers.

 -


3.
How do we deal with Callables? We need to support extended callable syntax basically.
Or something like it.

4.
What do we do about ``Members`` on built-in types? ``typing.get_type_hints(int)`` returns ``{}`` but mypy will not agree!

An object of an empty user-defined class has 29 entries in ``dir`` (all dunders), and ``object()`` has 24. (In 3.14. In 3.12, it was 27 for the user-defined object).

=====

This proposal is less "well-typed" than typescript... (Well-kinded, maybe?)
Typescript has better typechecking at the alias definition site:
For ``P[K]``, ``K`` needs to have ``keyof P``...

Oh, we could maybe do better but it would require some new machinery.
* ``KeyOf[T]`` - literal keys of ``T``
* ``Member[T]``, when statically checking a type alias, could be treated as having some type like ``tuple[Member[KeyOf[T], object???, str], ...]``
* ``GetAttr[T, S: KeyOf[T]]`` - but this isn't supported yet. TS supports it.
* We would also need to do context sensitive type bound inference
