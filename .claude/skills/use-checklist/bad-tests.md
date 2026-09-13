# bad test

- count(true facts) ≥ 1 → bad test

## checks

- [ ] trivial = does an assert merely read back a literal or declaration without intervening computation?
- [ ] tautological = does an assert derive its expectation from the subject's path, setup write, or shared helper?
- [ ] coupled = does an assert reach past world.facts into an internal, a style, or a layout?
- [ ] mocked = is the asserted fact produced by a fixture rather than by the subject?
- [ ] redundant = does a co-case in the exp settle the same fact?
- [ ] irrelevant = does the case cite a spec rule the spec no longer states, or no spec rule at all?
- [ ] irresponsible = does the test emulate or duplicate code when it should not?
