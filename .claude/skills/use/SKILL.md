---
name: use
description: only-if-asked
argument-hint: "[module={name}]"
---

use(module, subject=infer())
  load ./{module}.md
  apply it to subject
