---
name: mk
description: only-if-asked
argument-hint: "[key=breakdown|skill|sketch|recs|handoff|table|model]"
---

skills.mk.{key}(args…)
  load ./_{key}.md
  apply the key instructions with args

brief()
  summarize intent, assumptions, and the current model
  use canonical terms, asd-ste100 voice and lexicon, and minimal prose
  prefer pseudocode and sketches
  do not include a log of errors we made or changes to the design (frontier only)
  do not include metacommentary

vocab()
  vocab and lexicon must either be defined in the glossary or in asd-ste100
  if a line contains names not in the glossary or asd-ste100 then names must be defined in the glossary or rephrased
  the glossary is for names not for terms; each name in the glossary should be unique, distinct, and not overlap unnecessarily with other names
  order the glossary such that any given row is always fully defined by everything that came before it and asd-ste100
  sections: glossary, background, model verification, current model