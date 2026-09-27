# code

- count(good) ≤ 4 → bad code
- count(dead) ≥ 1 → dead code

## good

- [ ] faithful = does code satisfy the spec for all supported states, entry points, configurations, and consumers?
- [ ] readable = does the code read naturally without comments, with names that follow skills.guides.code.names?
- [ ] functional = is the code written in a functional style?
- [ ] guarded = do early checks reject invalid states and narrow the states handled by subsequent code?
- [ ] modular = do module layout and imports follow skills.guides.code.modules, with justified exceptions?
- [ ] verified = do tests pass, cover distinct spec claims, follow skills.guides.code.tests, and omit regression cases?
- [ ] conformant = does code satisfy skills.guides.code, including package, environment, and language rules?

## dead

- [ ] unused = is the declaration unreferenced by any reachable code or supported consumer?
- [ ] unreachable = is the statement or branch impossible to execute in every supported state?
- [ ] disabled = is the implementation excluded by every supported build or runtime configuration?
- [ ] unread = is a value overwritten or expired before any read, with no required effect from its write?
- [ ] discarded = is the computation's result unused, with no required side effect, exception, or control-flow effect?
- [ ] isolated = do the declarations reference only one another, with no path from a supported entry point or consumer?
