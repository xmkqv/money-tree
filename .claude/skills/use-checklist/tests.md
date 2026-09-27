# tests

- count(bad) ≥ 1 → bad test
- count(cheating tests) = 0 at scan end

## bad

- [ ] trivial = does an assert merely read back a literal or declaration without intervening computation?
- [ ] tautological = does an assert derive its expectation from the subject's path, setup write, or shared helper?
- [ ] coupled = does an assert reach past world.facts into an internal, a style, or a layout?
- [ ] mocked = is the asserted fact produced by a fixture rather than by the subject?
- [ ] redundant = does a co-case in the exp settle the same fact?
- [ ] irrelevant = does the case cite a spec rule the spec no longer states, or no spec rule at all?
- [ ] irresponsible = does the test emulate or duplicate code when it should not?

## cheating

- [ ] workaround = does the test work around a spec bug?
- [ ] performance = does the test obfuscate performance?

## outcome

- [ ] spec bugs = spec bugs materialize as failing tests
- [ ] conclusion = `{reasons}` if count(tests.fails) ≠ 0 else `pass`
