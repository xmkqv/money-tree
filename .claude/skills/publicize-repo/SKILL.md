---
name: publicize-repo
description: only-if-asked
argument-hint: "[fov=infer()] [foe=infer()]"
---

publicize-repo(fov, foe)
  assert fov and foe resolve to one git repository
  skills.guides()
  log intent, fov, foe, repository status, and publication target
  log inspect-public-surface(fov) as report
  wait for approval
  prepare-public-surface(foe, report.approved)
  verify-public-surface(fov)

inspect-public-surface(fov)
  map the worktree, refs, history, submodules, lfs objects, symlinks, and generated files
  log secrets and personal data by class, location, reachability, and remedy
  log name mismatches across paths, code, configuration, packages, commands, and docs
  log dead files with evidence that they have no publication role
  log readme, license, security policy, contributing, citation, attribution, and metadata gaps
  log the repository-native build, check, example, and render commands

prepare-public-surface(foe, approved)
  sanitize-public-surface(foe, approved)
  align approved names and update all references in one change
  drop approved dead files
  fill approved gaps from the report
  regenerate derived files with repository-native commands
  foe.docs.each(doc → skills.humanizer(doc))

sanitize-public-surface(foe, approved)
  remove approved secrets and personal data
  replace required private inputs with named placeholders and setup instructions
  if a secret is live or reachable in history, require rotation or revocation
  if history must change, log the exact refs, remotes, and collaborator impact
  if history must change, wait for separate history-rewrite approval
  rewrite only approved refs and do not claim that remote copies were removed

verify-public-surface(fov)
  build a clean publication candidate from the files and refs intended for the target
  rescan its content, filenames, binary metadata, and full reachable history
  run the documented setup, checks, exemplars, link checks, and render commands
  compare names, paths, badges, links, and outputs against the publication candidate
  log changes, verification evidence, blockers, and remaining external actions

# rules

- the public surface contains every object and identity that the target refs make reachable
- preparation does not authorize publication or destructive history changes
- stop before push, visibility changes, release, credential rotation, or account changes
- missing license authority is a blocker
- legal terms are neither invented nor changed
- code cleanup beyond the approved report is out of scope

## secrets

- no log or finding reproduces a sensitive value
- redaction does not replace credential rotation or revocation

## surface

- a dead file has no runtime, build, check, doc, legal, operational, or publication role
- name normalization preserves each entity's canonical name and derived tkey across the full public surface
- approved attribution and legal notices remain intact
- a security policy names a private report channel
- metadata is complete when the description, topics, and social preview describe the current project

## readme

- a readme demonstrates rather than claims
- a readme command is copied from or added to repository configuration and is run as written
- an exemplar is minimal, complete, and derived from current behavior
- exemplars span basic use through the distinctive use case
- a badge states a verifiable live fact, e.g. build, version, license; otherwise it is omitted

## renders

- a render shows actual output, interfaces, or mechanisms, never decoration
- render sources and reproducible commands stay with the repository when practical
- a useful render is refined until composition, density, contrast, and scale are publication quality

```md:form:publicize-repo-report
| state | class | location | evidence | action |
|-------|-------|----------|----------|--------|
| {state} | {class} | {location} | {non-sensitive evidence} | {action} |
```

```md:form:public-readme
# {name}

{purpose, one or two lines}

{functional badges?}

{hero render?}

## quickstart

{install and first working command}

{usage exemplars, basic through distinctive}

## license

{license name}
```
