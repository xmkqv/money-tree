---
name: is-it-ready
description: only-if-asked
disable-model-invocation: true
---

is-it-ready()
  skills.solo(yolo)
  skills.guides(code/tests, code/infer())
  log spec.exps
  align tests to spec.exps
  review code and spec
  if bug discovered in code, align code to spec
  if bug discovered in spec, design and implement its demonstrative test case
  log bug fixes
  log failing cases

# rules

- no spec is edited
- an issue that does not resolve as a failing test case is not mentioned
- code is a reflection of spec
- a silent workaround is removed and its bug is raised as a failing test case
