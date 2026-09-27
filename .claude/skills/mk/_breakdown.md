# breakdown

breakdown()
    log breakdown

```md:form:breakdown
{glossary}

{skills.mk.sketch(architecture)}

{proof}

{takeaway}
```

```md:form:proof
- {claim}
…
```

## rules

- count(glossary.definition.chars) ≤ 60
- glossary.definition contains glossary.term ∈ asd-ste100 ∪ terms in previous rows
- count(claim.chars) ≤ 100
- claim.terms.each ∈ asd-ste100 ∪ glossary
- claim is a semantic logical statement, e.g.:
  - if … then …
  - therefore …
  - if … then … and …
- each claim may be followed by an exact extracted code snippet or an exemplar codeblock
- takeaway is a single normative sentence
