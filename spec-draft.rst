
Grammar specification of the extensions to the type language.

It's important that there be a clearly specified type language for the type-level computation---we can't just be using some poorly specified subset of all Python.

TODO:
- Drop DirProperties - make it Members or something
- IsSubtype -> Is?
- Look into TupleTypeVar stuff for iteration
- Move some to a "primitives" section


::

   <type> = ...
        | <type> if <type-bool> else <type>

        # Create NewProtocols and Unions using for loops.
        # They can take either a single list comprehension as an
        # argument, or starred list comprehensions can be included
        # in the argument list.

        # TODO: NewProtocol needs a way of doing bases also...
        # TODO: Should probably support Callable, TypedDict, etc
        | NewProtocol[<variadic-type-arg(<prop-spec>)> +]

        | Union[<variadic-type-arg(<type-for>)> +]

        | GetAttr[<type>, <type>]
        | GetArg[<type>, <int-literal>]

        # String manipulation operations for string Literal types.
        # We can put more in, but this is what typescript has.
        | Uppercase[<type>] | Lowercase[<type>]
        | Capitalize[<type>] | Uncapitalize[<type>]

   # Type conditional checks are just boolean compositions of
   # subtype checking.
   <type-bool> =
         IsSubtype[<type>, <type>]
       | not <type-bool>
       | <type-bool> and <type-bool>
       | <type-bool> or <type-bool>
       # Do we want these next two?
       | Any[<type-for(<type-bool>)>]
       | All[<type-for(<type-bool>)>]

   <prop-spec> = Property[<type>, <type>]

   <variadic-type-arg(T)> =
         T ,
       | * <type-for-iter(T)> ,


   <type-for(T)> = [ T <type-for-iter>+ <type-for-if>* ]
   <type-for-iter> =
         for <var> in IterUnion<type>
       | for <var>, <var> in DirProperties<type>
       # TODO: callspecs
       # TODO: variadic args (tuples, callables)
   <type-for-if> =
         if <type-bool>



``type-for(T)`` and ``variadic-type-arg(T)`` are parameterized grammar
rules, which can take different
