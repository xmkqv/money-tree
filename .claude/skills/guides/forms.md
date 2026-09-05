# forms

- a form is a named, language-keyed glob pattern, e.g. `*` matches any content
- a fence form is tagged `{lang}:form:{name}` and its body is the pattern
- an inline form is `{lang}:form:{name}` followed by the pattern in backticks

```ts:types
type Form = { lang: string; name: string; pattern: string }
```

```sh
inline='()([a-z]+):form:([^\s`]+)`([^`]+)`'
block='(`{3,})([a-z]+):form:(\S+)\n([\s\S]*?)\n\1'
content='...'
rg --pcre2 --null-data --only-matching --replace $'$2\t$3\t$4' "(?|${inline}|${block})" - <<< "$content"
```

## response diff

- a response diff is a unified diff in a `diff` fence
- each diff fence covers exactly one file
- file paths are workspace-relative
- hunk ranges match their hunk bodies
- non-contiguous changes occupy separate hunks
- omitted content is represented by hunk boundaries, not ellipses

````md:form:response-diff
{summary?}

```diff
--- {a/{path}|/dev/null}
+++ {b/{path}|/dev/null}
@@ -{old-range} +{new-range} @@{heading?}
 {context}
-{removed}
+{added}
…
```

{notes?}
````
