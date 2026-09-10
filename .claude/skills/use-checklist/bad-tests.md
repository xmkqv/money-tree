# bad test

- count(true facts) ≥ 1 → bad test

## checks

- [ ] trivial = does an assert read back a literal or a declaration, with no computation between the claim and the artifact?
- [ ] tautological = does an assert take its expectation from the subject's own path, i.e. the setup's write or a shared helper?
- [ ] coupled = does an assert reach past world.facts into an internal, a style, or a layout?
- [ ] mocked = is the asserted fact produced by a fixture rather than by the subject?
- [ ] redundant = does a co-case in the exp settle the same fact?
- [ ] irrelevant = does the case cite a spec rule the spec no longer states, or no spec rule at all?
