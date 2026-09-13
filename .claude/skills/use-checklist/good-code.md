# code quality

- count(false facts) ≥ 1 → fail

## checks

- [ ] faithful = does code satisfy the spec for all supported states, entry points, configurations, and consumers?
- [ ] readable = does the code read naturally without comments, with names that follow skills.guides.code.names?
- [ ] functional = is the code written in a functional style?
- [ ] guarded = do early checks reject invalid states and narrow the states handled by subsequent code?
- [ ] modular = do module layout and imports follow skills.guides.code.modules, with justified exceptions?
- [ ] verified = do tests pass, cover distinct spec claims, follow skills.guides.code.tests, and omit regression cases?
- [ ] conformant = does code satisfy skills.guides.code, including package, environment, and language rules?
