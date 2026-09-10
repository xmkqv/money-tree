@mise.toml
@./.claude/AGENTS.md
do not write tests
read when needed: /use-cheatsheets limits,pydantic,pydantic-settings,redis,reflex

# voice

- communicate in simple statements
- assume the reader is unfamiliar with code and tooling
- draw ascii sketches where appropriate, where annotations are brief
- do not tell me your opinions
- do not hedge

# triggers

after planning:
    - have you been consistent about layer responsibilities?
    - are you inventing names where existing lexicon suffices?
    - are you inventing code where existing functionality suffices?
    - have you solved the original problem and no more?
    - is any code you wrote idiomatic?
    - have you considered available libraries, environment, and tools?

# sync skills

rsync -a ../ddoc/agents/skills/ .claude/skills/

# ignore

- [x] data clients
- [x] storage
- [ ] framework
