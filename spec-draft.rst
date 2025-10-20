
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

* ``Member[N: Literal & str, T]``
# These names are too long -- but we can't do ``Type`` !!
* ``GetName[T: Member]``
* ``GetType[T: Member]``

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

Can we actually implement Is (IsSubtype) at runtime in a satisfactory way?
 - Could we slightly dodge the question by *not* adding the evaluation library to the standard library, and letting the operations be opaque.

   Then we would promise to have a third-party library, which would need to be "fit for purpose" for people to want to use, but would be free of the burden of being canonical?

There is a lot that needs to happen, like protocols and variance inference and
callable subtyping (which might require matching against type vars...)

How do we deal with modifiers? ClassVar, Final, Required, ReadOnly
 - One option is to treat them not as types by as *modifiers* and have them
   in a separate field where they are a union of Literals.
   So ``x: Final[ClassVar[int]]`` would appear in ``Attrs`` as
   ``Member[Literal['x'], int, Literal['Final' | 'ClassVar']]``


How do we deal with Callables? We need to support extended callable syntax basically.
Or something like it.


=====

This proposal is less "well-typed" than typescript... (Well-kinded, maybe?)
Typescript has better typechecking at the alias definition site:
For ``P[K]``, ``K`` needs to have ``keyof P``...
