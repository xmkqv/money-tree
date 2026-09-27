# rules

- skills.guides.spec
- count(bad) ≥ 1 → bad rule
- count(good) ≤ 4 → bad rule

## good

- [ ] relevance = removing the rule would permit a known or plausible recurring mistake
- [ ] scope = the affected tasks, files, or operations are identifiable
- [ ] precedence = overlapping instructions have a determinate resolution
- [ ] freshness = a source of truth or revision trigger is identifiable
- [ ] economy = the rule does not duplicate discoverable or self-evident information
- [ ] validation = agent behavior before and after the rule can be compared
- [ ] checkable = ∃ pseudo-math representation

## bad

- [ ] imperative = is the rule an instruction rather than a declaration?
- [ ] coded = does the rule carry code tokens where the design register suffices?
- [ ] inferrable = does the pseudocode or another rule already imply it?
- [ ] compound = does the rule bundle claims that could be tested apart?
- [ ] misplaced = does the rule govern behavior owned by another layer?
- [ ] crowded = does the rule push its layer past 7 exps or 7 invs?
- [ ] long = does the rule exceed 20 words?
