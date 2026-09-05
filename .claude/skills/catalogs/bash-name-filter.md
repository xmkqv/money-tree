# bash-name-filter

- verified: official repositories and the github api on 2026-08-15
- stars and last-active dates are point-in-time facts, not rankings.
- each row has a default-branch commit on or after 2026-02-15.

| link | last active | stars | developer experience | feature tags |
|---|---:|---:|---|---|
| [ripgrep](https://github.com/BurntSushi/ripgrep) | [2026-08-04](https://github.com/BurntSushi/ripgrep/commit/3fce3b5bb0236da2df6d99672afb8a719642eca7) | 67,299 | existing dependency. fast discovery and mature glob controls | `regex`, `glob`, `stdin`, `pcre2`, `discovery` |
| [shellcheck](https://github.com/koalaman/shellcheck) | [2026-06-11](https://github.com/koalaman/shellcheck/commit/9af7ee28ce587baadd950b85dd6826a16b9c068d) | 39,879 | one-command diagnostics with mature editor and ci integrations | `static-analysis`, `bash`, `portability`, `json`, `ci` |
| [jq](https://github.com/jqlang/jq) | [2026-08-12](https://github.com/jqlang/jq/commit/4bb50d772bd35666dcd3ae460f2ddfae3864e16c) | 35,453 | installed locally. precise expressions. yaml needs conversion | `json`, `gsub`, `test`, `arithmetic`, `raw-input` |
| [mikefarah/yq](https://github.com/mikefarah/yq) | [2026-08-03](https://github.com/mikefarah/yq/commit/7862131c9c13c977e4ede55b5f6c44e5f8ac7268) | 15,833 | one go binary with jq-like yaml queries. best catalog extractor | `native-yaml`, `unique`, `sort`, `raw-output`, `multi-document` |
| [miller](https://github.com/johnkerl/miller) | [2026-08-14](https://github.com/johnkerl/miller/commit/e1e47925276c0c4a09df264559789274f1ca75cd) | 9,995 | one binary processes tsv directly. its expression language adds scope | `tsv`, `streaming`, `filter-dsl`, `strlen`, `regex` |
| [shfmt](https://github.com/mvdan/sh) | [2026-08-13](https://github.com/mvdan/sh/commit/a04df9f0d4b8947a42d176b5d22a814b61dd6ac4) | 8,981 | deterministic formatting with package and editor support | `formatter`, `parser`, `bash`, `posix`, `zsh`, `editorconfig` |
| [jc](https://github.com/kellyjonbrazil/jc) | [2026-06-18](https://github.com/kellyjonbrazil/jc/commit/8290734a87a30e5f0af7e1fba5ecbda2e1c145a8) | 8,663 | simple yaml-to-json bridge. python and a second filter remain necessary | `yaml-parser`, `json-output`, `multi-document`, `pipeline` |
| [dasel](https://github.com/TomWright/dasel) | [2026-08-01](https://github.com/TomWright/dasel/commit/70fd28f38c0e7eb35ef1a034813daf1976e90485) | 8,016 | one go binary with clear selectors and shell completion | `native-yaml`, `query`, `recursive-search`, `conversion`, `completion` |
| [watchexec](https://github.com/watchexec/watchexec) | [2026-08-12](https://github.com/watchexec/watchexec/commit/d941d564fa97e400c6392b5823cabc52456d606b) | 7,116 | one command reruns tests after coalesced changes | `watcher`, `recursive`, `ignore-files`, `coalescing`, `process-groups` |
| [bats-core](https://github.com/bats-core/bats-core) | [2026-07-26](https://github.com/bats-core/bats-core/commit/ae4b94d7cc35f62468297791aa4ab8c3af7377ba) | 6,215 | shell-command tests support bash 3.2 and tap output | `testing`, `tap`, `junit`, `bash-3.2`, `hooks`, `filters` |
| [fswatch](https://github.com/emcrisostomo/fswatch) | [2026-07-22](https://github.com/emcrisostomo/fswatch/commit/40dfff9938210059e08e318acc493aa19572a6a7) | 5,580 | a raw event stream composes with shell pipelines across platforms | `watcher`, `event-stream`, `fsevents`, `inotify`, `kqueue` |
| [gojq](https://github.com/itchyny/gojq) | [2026-07-20](https://github.com/itchyny/gojq/commit/2e210b5c28122b106d4cd1fade3ac9dad0482026) | 3,794 | one go binary uses jq syntax and reads yaml directly | `yaml-input`, `jq-compatible`, `unique`, `raw-output`, `big-integer` |
| [ugrep](https://github.com/Genivia/ugrep) | [2026-08-05](https://github.com/Genivia/ugrep/commit/550599a6434fc5315fb6ecd415a5d859e6d846a8) | 3,238 | capable search interface that duplicates the existing ripgrep dependency | `regex`, `boolean-search`, `fuzzy-search`, `stdin` |
| [kislyuk/yq](https://github.com/kislyuk/yq) | [2026-07-11](https://github.com/kislyuk/yq/commit/ff9fc4b18d0bcbfb7758ff82bf1f36b60020b48a) | 2,965 | exact jq workflow with python and jq runtime dependencies | `yaml-to-json`, `jq-forwarding`, `unique`, `raw-output` |
| [trdsql](https://github.com/noborus/trdsql) | [2026-07-17](https://github.com/noborus/trdsql/commit/1ef4b4685b27bd5c105d9459dfad874f0e43c06d) | 2,169 | direct sql queries fit row data but add an unrelated model | `yaml-input`, `sql`, `distinct`, `nested-selector` |
| [argc](https://github.com/sigoden/argc) | [2026-06-29](https://github.com/sigoden/argc/commit/60cc19a29fedf9aeeb306cede02343e63a71d8cb) | 1,158 | comment-driven cli generation adds too much for one option | `cli-framework`, `parser`, `completion`, `man-page`, `bash` |
| [bashunit](https://github.com/TypedDevs/bashunit) | [2026-08-15](https://github.com/TypedDevs/bashunit/commit/d8581320e7ad7f44069d8a8182a59592d14ed99b) | 424 | plain functions get 93 assertions, mocks, snapshots, and coverage | `testing`, `assertions`, `mocks`, `snapshots`, `coverage`, `parallel` |

## notes

- no mature bash 3.2 filtering library with recent activity improves the direct predicate.
- bashly was active but its ruby generator conflicts with the no-ruby constraint.
- shellspec, lobash, and json.bash missed the six-month activity cutoff.
