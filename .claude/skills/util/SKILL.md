---
name: util
description: only-if-asked
---

key ∈ { loop, try }

util(key)
  api.{key}()

api:
  loop()
    step 1 → emit infer()
    wait for feedback
    apply instruction if any, continue to step 1 without pause

  try(max-suggestion=2,diff?)
    loop(
      log suggestions
      if diff, log diffs where diffs are concrete diffs on current files
    )

  browser-testing()
    read lib/ui* and lib/web specs and log expected user experiences (both explicit and implicit)
    wipe previous app state e.g. indexeddb
    run e2e tests
    if error
      skills.scan
      investigate
      attempt fixes
      if it is a spec bug or untractable → log report and exit
    boot the full stack and use the in-app browser; methodically and manually test each of the logged user experiences; log insights and observations
    log report proposing next steps
