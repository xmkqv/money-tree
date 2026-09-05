---
name: use
description: only-if-asked
disable-model-invocation: true
argument-hint: "[module={name}]"
---

use(module, subject=infer())
  load ./{module}.md
  apply it to subject
