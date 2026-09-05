# bad test

**Does the case go red when the spec claim it cites is broken?** break the code path the claim names and rerun the case.

each flag is a way the case stays green under that break; count(flags) ≥ 1 → bad test.

1. **trivial** — does an assert read back a literal or a declaration, with no computation between the claim and the artifact?
2. **tautological** — does an assert take its expectation from the subject's own path, i.e. the setup's write or a shared helper?
3. **coupled** — does an assert reach past world.facts into an internal, a style, or a layout?
4. **mocked** — is the asserted fact produced by a fixture rather than by the subject?
5. **redundant** — does a co-case in the exp settle the same fact?
6. **irrelevant** — does the case cite a spec rule the spec no longer states, or no spec rule at all?

## exceptions

boot cases — a trivial assert is correct when the claim is that the subject starts — the assert names the boot fact, not a literal.

layered cases — a redundant assert is correct when the co-case pins the same fact at another layer — the case cites the layer it pins.

contract cases — coupling is correct when the spec claims the shape — the assert cites the spec rule that claims it.
