---
name: deep-plan
description: only-if-asked
disable-model-invocation: true
argument-hint: "[ok-spec?]"
---

deep-plan(ok-spec?)
  double the plan detail
  if ok-spec, state spec edits ok
  else explicitly and strongly state "do not edit spec"