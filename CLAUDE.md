@mise.toml
@./.claude/AGENTS.md

# voice

- communicate in simple statements
- assume the reader is unfamiliar with code and tooling
- draw ascii sketches where appropriate, where annotations are brief

# code quality checks

if any of the following are not true, refactor the code
if the spec is not satisfiable, raise an issue (max 3 lines) with the user stressing that your interpretation may be flawed

- [ ] config variables (incl constants) are declared in mise*.toml
- [ ] environment variables (i.e. secrets and config) are declared once, usages ≥1, are required (i.e. crash if missing), and are loaded into the runtime by pydantic-settings
- [ ] strategies are declared in the registry and inherit from base (directly or indirectly)
- [ ] functions/classes/types never duplicate installed packages functionality
- [ ] names/keys/conventions are consistent from spec to code

# triggers

after finalizing a plan, review:
    - have you been consistent about layer responsibilities?
    - are you inventing names where existing lexicon suffices?
    - are you inventing code where exising functionality suffices?
    - have you solved the original problem and no more?
    - is any code you wrote idiomatic?
    - have you considered available libraries, environment, and tools?
