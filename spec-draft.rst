
Grammar specification of the extensions to the type language.

It's important that there be a clearly specified type language for the type-level computation---we can't just be using some poorly specified subset of all Python.

TODO:
- Drop DirProperties - make it Members or something
- IsSubtype -> Is?
- Look into TupleTypeVar stuff for iteration
- Move some to a "primitives" section

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
         for <var> in Iter<type>
   <type-for-if> =
         if <type-bool>


``type-for(T)`` is a parameterized grammar rule, which can take
different types. Not sure if we actually want this though.

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



String manipulation operations for string Literal types.
We can put more in, but this is what typescript has.

* ``Uppercase[S: Literal & str]``
* ``Lowercase[S: Literal & str]``
* ``Capitalize[S: Literal & str]``
* ``Uncapitalize[S: Literal & str]``
