---
name: checkpoint
description: only-if-asked
disable-model-invocation: true
---

checkpoint()
  bundle the changes below the current working directory into coherent layers
  commit each layer

# rules

- only paths below the current working directory are staged and committed
- commit messages are reasonable summaries
- no file or dir is created or changed
- no verification runs
- nothing is stashed, reverted, discarded, amended, rebased, or reset
- other developers are working, so the working tree may change during the commit
