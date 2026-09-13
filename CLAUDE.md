@mise.toml
@.claude/AGENTS.md
do not write tests
read when needed: /use-docs limits,pydantic,pydantic-settings,redis

# voice

- communicate in simple statements
- do not tell me your opinions
- do not hedge

# sync skills

mirror each inherited skill; leave unique skills alone

for d in ../ddoc/agents/skills/*/; do
  rsync -a --delete "$d" ".claude/skills/$(basename "$d")/"
done
