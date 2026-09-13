# dead code

- checks are evaluated across supported entry points, configurations, and consumers
- references include dynamic lookup, framework registration, and external contracts
- count(true facts) ≥ 1 → dead code

## checks

- [ ] unused = is the declaration unreferenced by any reachable code or supported consumer?
- [ ] unreachable = is the statement or branch impossible to execute in every supported state?
- [ ] disabled = is the implementation excluded by every supported build or runtime configuration?
- [ ] unread = is a value overwritten or expired before any read, with no required effect from its write?
- [ ] discarded = is the computation's result unused, with no required side effect, exception, or control-flow effect?
- [ ] isolated = do the declarations reference only one another, with no path from a supported entry point or consumer?
