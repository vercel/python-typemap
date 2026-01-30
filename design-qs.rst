Big (open?) questions
---------------------

1.
Can we actually implement IsSubtype at runtime in a satisfactory way?
(PROBABLE DECISION: external library *and* "full" best effort checking.)

 - There is a lot that needs to happen, like protocols and variance
   inference and callable subtyping (which might require matching
   against type vars...).  Jukka points out that lots of type
   information is frequently missing at runtime too: attributes might
   be inferred, which is a *feature*.

 - Could we slightly dodge the question by *not* adding the evaluation
   library to the standard library, and letting the operations be
   opaque.

   Then we would promise to have a third-party library, which would
   need to be "fit for purpose" for people to want to use, but would
   be free of the burden of being canonical?

 - I think we probably *can't* try to put it in the standard
   library. I think it would by nature bless the implementation with
   some degree of canonicity that I'm not sure we can back
   up. Different typecheckers don't always match on subtyping
   behavior, *and* it sometimes depends on config flags (like
   strict_optional in mypy). *And* we could imagine a bunch of other
   config flags: whether to be strict about argument names in
   protocols, for example.

 - We can instead have something simpler, which I will call
   ``IsSubSimilar``. ``IsSubSimilar`` would do *simple* checking of
   the *head* of types, essentially, without looking at type
   parameters. It would still lift over unions and would check
   literals.

   Probably need a better name.

   Honestly this is basically what is currently implemented for the
   examples, so it is probably good enough.

   It's unsatisfying, though.



----
