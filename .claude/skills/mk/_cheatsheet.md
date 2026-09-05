# cheatsheet

cheatsheet(subject=infer(), fov=infer())
  read fov manifests as installed
  installed.filter(the subject imports it) as libs
  skills.search(docs, libs) as apis
  log cheatsheet

# rules

- a cheatsheet covers one subject
- count(libs) ≤ 7
- the source foot lists dated evidence, oldest first

```md:form:cheatsheet
# {subject}

{libs}

{gaps?}

{sources}
```

## lib

- a lib is installed, i.e. the fov resolves its version
- the version is the installed version, not the manifest range
- an import line is verbatim, i.e. copyable into the subject
- entries order by the subject's call order
- count(entries) ≤ 9 per lib

```md:form:lib
## {lib} {version}

{import}

{entries}
```

## entry

- an entry covers one api
- an entry answers a call the subject makes
- a signature is verbatim from the docs
- the aside states the occasion, not the definition
- an exemplar uses the subject's own types and names
- count(lines(exemplar)) ≤ 12
- an exemplar is omitted when the signature carries the usage

````md:form:entry
`{signature}` → {return} — {occasion}

```{lang}
{exemplar?}
```

````

## gap

- a gap names an api the subject needs and the installed version lacks
- a gap names the substitute the installed version offers
- a gap cites the version that adds the api

```md:form:gap
{api} — {substitute} — {upgrade?}
```
