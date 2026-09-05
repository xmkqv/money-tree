# zero-config-code-scan

- subject: one-shot code quality analytics for agents
- window: 2026-02-18 through 2026-08-18
- language-agnostic: one scan covers unrelated language ecosystems or arbitrary source text
- scope: tools that answer `tool scan {dir}` with structured findings
- gate a: no config file is necessary in the target directory
- gate b: no git repository is necessary
- gate c: no vendor account, token, or analysis server is necessary
- gate d: output is JSON, JSON Lines, or SARIF
- verified: github `pushed_at` and stars on 2026-08-18
- local tests from 2026-08-16: scc 3.7.0, jscpd 5.0.15, multimetric 2.4.4, lizard 1.23.0, qlty 0.642.0, ast-grep 0.45.1
- network note: public rule, helper, or vulnerability database downloads are marked as conditional
- caution: repository stars can cover a monorepo, and source availability does not imply an OSI-approved license

## fit against the declared ddoc output types

[1] `scc`, `jscpd`, and `rg` have direct adapters to the current types.

`scc --by-file --format json2 DIR` supplies per-file code, comment, blank, and
lexical-complexity counts. `jscpd DIR --reporters json --output TMP` supplies
clone pairs. `rg --no-config --json '@TODO:?[ \t]+' DIR` supplies line spans and
text. The `no-comments` rule can be derived from an `scc` file result whose
comment count is zero.

Refs: [scc](https://github.com/boyter/scc),
[jscpd](https://github.com/kucherenko/jscpd), [ripgrep](https://github.com/BurntSushi/ripgrep)

[2] Broader results need one generic diagnostic shape.

Dead code, secrets, licenses, spelling, architecture, and per-function metrics
are not current ddoc `gen` categories. A useful common payload has `tool`, `rule`,
`severity`, `confidence`, `message`, `path`, `fragment`, `fingerprint`, and
tool-specific `data`. This keeps stable fields queryable without discarding
scanner evidence.

Refs: [Skylos](https://github.com/duriantaco/skylos),
[Fossil](https://github.com/yfedoseev/fossil-mcp), [Kingfisher](https://github.com/mongodb/kingfisher)

## recent library catalog

### pass all four gates

| link | last active | stars | developer experience | feature tags |
|------|-------------|-------|----------------------|--------------|
| [ripgrep](https://github.com/BurntSushi/ripgrep) | 2026-08-04 | 67,371 | Unlicense. One binary. `--no-config --json` gives a deterministic JSON Lines adapter for declared text rules | recommended, text-rules, todo, jsonl, arbitrary-text |
| [scc](https://github.com/boyter/scc) | 2026-08-18 | 8,626 | MIT. One binary. Exact fit for per-file code, comment, blank, and lexical-complexity counts. Stable release v3.7.0 | recommended, census, complexity, json2, 322-languages |
| [cloc](https://github.com/AlDanial/cloc) | 2026-08-08 | 23,443 | GPL-2.0. `cloc --by-file --json DIR` is a mature count-only fallback. v2.10 was released on 2026-07-04 | census, blank, comment, code, json, many-languages |
| [jscpd](https://github.com/kucherenko/jscpd) | 2026-08-18 | 6,017 | MIT. v5.0.16 is a native Rust binary. JSON and SARIF reporters cover 223 formats | recommended, duplication, clones, json, sarif, 223-formats |
| [Skylos](https://github.com/duriantaco/skylos) | 2026-08-18 | 539 | Apache-2.0. `skylos DIR --json` is local and key-free. It covers 11 programming languages plus deployment config | aggregator, dead-code, quality, security, json, sarif |
| [Fossil](https://github.com/yfedoseev/fossil-mcp) | 2026-06-22 | 65 | Apache-2.0. `fossil-mcp scan DIR --format json` uses optional config and covers 16 parsers in 15 language groups | dead-code, clones, scaffolding, call-graph, json, sarif |
| [dupehound](https://github.com/Rafaelpta/dupehound) | 2026-08-11 | 87 | MIT. `scan` works on any directory and emits versioned JSON. Only history and diff checks need git | structural-clones, renamed-clones, json, 15-languages, early |
| [arborist-cli](https://github.com/StrangeDaysTech/arborist-cli) | 2026-05-20 | 2 | Apache-2.0. Directory input and JSON stdout give per-function cognitive, cyclomatic, and SLOC metrics | cognitive, cyclomatic, sloc, json, 15-languages, early |
| [big-code-analysis](https://github.com/dekobon/big-code-analysis) | 2026-08-16 | 20 | MPL-2.0. `bca metrics DIR -O json` returns per-function metric trees across 20+ languages. Threshold gates need config | cognitive, cyclomatic, halstead, maintainability, json |
| [todos](https://github.com/ianlewis/todos) | 2026-08-17 | 64 | Apache-2.0. `todos DIR -o json` parses comment tags across 50+ languages. Git is needed only for optional blame | todo, fixme, comment-aware, jsonl, 50+-languages |
| [typos](https://github.com/crate-ci/typos) | 2026-08-07 | 4,094 | MIT or Apache-2.0. `typos DIR --format json` uses a built-in dictionary and optional config | spelling, identifiers, comments, jsonl, single-binary |
| [Gitleaks](https://github.com/gitleaks/gitleaks) | 2026-07-29 | 28,798 | MIT. `gitleaks dir DIR` is separate from git scanning and uses built-in rules. JSON and SARIF are native | secrets, entropy, json, sarif, built-in-rules |
| [TruffleHog](https://github.com/trufflesecurity/trufflehog) | 2026-08-18 | 27,508 | AGPL-3.0. `trufflehog filesystem DIR --no-verification --json` keeps provider validation offline | secrets, jsonl, sarif, 800+-detectors, offline-flag |
| [Kingfisher](https://github.com/mongodb/kingfisher) | 2026-08-18 | 1,204 | Apache-2.0. `kingfisher scan DIR --no-validate --format json` scans a plain folder with 1,089 built-in rules | secrets, bytecode, json, sarif, offline-flag |
| [ScanCode Toolkit](https://github.com/aboutcode-org/scancode-toolkit) | 2026-08-15 | 2,606 | Apache-2.0. Standalone directory scan with JSON, JSON Lines, SPDX, and CycloneDX. Installation is heavier | licenses, copyright, packages, dependencies, json |
| [Licensee](https://github.com/licensee/licensee) | 2026-08-17 | 904 | MIT. `licensee detect DIR --filesystem --json` makes filesystem mode explicit | license-detection, recursive, filesystem, json |
| [REUSE](https://github.com/fsfe/reuse-tool) | 2026-07-24 | 582 | Apache-2.0. `reuse --root DIR lint --json` works without its optional VCS integrations | license-compliance, copyright, spdx, json |
| [Ultimate Bug Scanner](https://github.com/Dicklesworthstone/ultimate_bug_scanner) | 2026-08-17 | 282 | MIT. `ubs DIR --format=json` auto-detects ten ecosystems. Helpers can download lazily | aggregator, bug-patterns, json, sarif, helper-downloads |
| [detect-secrets](https://github.com/Yelp/detect-secrets) | 2026-04-02 | 4,622 | Apache-2.0. `detect-secrets scan DIR --all-files` uses built-in plugins and emits JSON | secrets, json, default-plugins, all-files |
| [Aislop](https://github.com/scanaislop/aislop) | 2026-08-15 | 556 | MIT. `aislop scan DIR` has built-in AI-slop rules for eight language targets and emits JSON or SARIF | ai-slop, dead-code, json, sarif, 8-targets |

### useful with a wrapper, supplied data, or supplied rules

| link | last active | stars | developer experience | feature tags |
|------|-------------|-------|----------------------|--------------|
| [multimetric](https://github.com/priv-kweihmann/multimetric) | 2026-08-10 | 39 | JSON stdout, but it accepts files rather than a directory. A safe file-list adapter is necessary | wrapper, maintainability, halstead, cyclomatic, json |
| [lizard](https://github.com/terryyin/lizard) | 2026-08-18 | 2,451 | Broad per-function complexity, but no JSON or SARIF writer. CSV or XML parsing fails gate D as written | output-wrapper, per-function-ccn, 27-languages |
| [rust-code-analysis](https://github.com/mozilla/rust-code-analysis) | 2026-04-06 | 437 | MPL-2.0. AST metrics and JSON are useful, but the published CLI is stale and current source must be built | source-build, cognitive, halstead, maintainability, json |
| [Tokei](https://github.com/XAMPPRocky/tokei) | 2026-05-06 | 14,827 | Fast metrics across 150+ languages. JSON depends on a binary built with serialization features | conditional-output, census, json, 150+-languages |
| [Semgrep](https://github.com/semgrep/semgrep) | 2026-08-18 | 16,279 | Local scan is account-free, but useful rules must be supplied or fetched from the registry | supplied-rules, taint, security, json, sarif, 30+-languages |
| [Opengrep](https://github.com/opengrep/opengrep) | 2026-08-18 | 2,965 | LGPL-2.1. Self-contained Semgrep-compatible engine. A rule pack is still necessary | supplied-rules, taint, security, json, sarif |
| [ast-grep](https://github.com/ast-grep/ast-grep) | 2026-08-17 | 15,567 | MIT. `scan -r RULE` works without project setup, but the tool ships no rules | supplied-rules, structural-search, json, sarif |
| [PMD](https://github.com/pmd/pmd) | 2026-08-18 | 5,468 | BSD-style. Multi-language rules ship on the classpath. CPD is zero-config but has no direct JSON or SARIF reporter | supplied-rules, duplication, output-wrapper, jvm |
| [Trivy](https://github.com/aquasecurity/trivy) | 2026-08-17 | 37,472 | Filesystem scans cover vulnerabilities, secrets, IaC, and licenses. Databases normally download before use | public-database, json, sarif, multi-ecosystem |
| [OSV-Scanner](https://github.com/google/osv-scanner) | 2026-08-17 | 10,854 | Lockfile discovery is zero-config. Default scans call OSV.dev and deps.dev; offline mode needs a seeded database | public-database, dependencies, json, sarif |
| [alint](https://github.com/asamarts/alint) | 2026-08-17 | 62 | Apache-2.0. Broad repository hygiene and architecture checks, but `check` needs a supplied policy | supplied-config, repo-shape, hygiene, json, sarif |
| [s0-cli](https://github.com/antonellof/s0-cli) | 2026-04-24 | 3 | `--no-llm` is account-free and structured, but useful coverage depends on separately installed scanners | orchestrator, external-scanners, json, sarif, early |

The recent filter excludes dormant projects. Single-language and single-ecosystem
tools are also excluded. Repomix, Universal Ctags, and codebase-memory-mcp are
language-agnostic, but they produce packed source, symbols, or a persistent graph
rather than one-shot quality findings.

## tweaks that expand scanner usefulness

| tweak | scanners | effect |
|------|----------|--------|
| Build one canonical file policy and derive each adapter's selection arguments from it | all | applies the same generated, vendor, hidden, size, and binary exclusions so cross-tool totals remain comparable |
| Write every report and cache below a temporary directory outside the target | jscpd, Kingfisher, ScanCode, Gitleaks | preserves the zero-mutation promise and makes cleanup atomic |
| Derive `no-comments` from `scc` and use `todos` before the `rg` fallback | scc, todos, ripgrep | removes one file pass and reduces TODO false positives while retaining arbitrary-text coverage |
| Store run metadata and stable fingerprints | all | records tool version, duration, target hash, ruleset hash, and a deduplication key for trends and rescans |
| Keep lexical and structural clone results as separate algorithms | jscpd, dupehound | finds exact blocks and renamed functions without treating their scores as equivalent |
| Add optional `detector`, `similarity`, and `deletable_lines` fields to duplicate results | jscpd, dupehound, Fossil | supports clone prioritization while preserving the current mate, line, token, and format fields |
| Normalize broad findings into a generic diagnostic payload | Skylos, Fossil, security and license scanners | lets new rule families enter `gen` without a schema category for every scanner |
| Rank review work by joined evidence, not one score | scc, clone, secret, and license scanners | combines complexity density, duplicate span, severity, and confidence while retaining each raw finding |
| Run network-backed validation as an explicit second tier | Trivy, OSV-Scanner, Semgrep, secret validators | keeps the default scan deterministic and offline, with richer checks available by policy |

## retained local evidence

- [scc](https://github.com/boyter/scc) v3.7.0 has per-file JSON2, ULOC, and DRYness. Its lexical complexity is comparable only within one language. Git hotspot flags on `master` are not in v3.7.0.
- `scc`, `jscpd`, `lizard`, and `multimetric` ran against a plain mixed-language directory with no config or git metadata. A 44-file scan finished in 1.6 seconds and left the target byte-identical.
- [jscpd](https://jscpd.dev/) v5 is one native binary. The JSON reporter writes below `--output`; the adapter must use an external temporary directory.
- [multimetric](https://pypi.org/project/multimetric/) writes JSON to stdout but accepts a file list. The adapter must batch and merge explicitly to avoid concatenated JSON documents.
- [ast-grep](https://ast-grep.github.io/guide/scan-project.html) bare `scan` needs project configuration. `scan -r RULE` works without it, but the caller owns the rules.

## web search log

[1] The smallest direct stack is `scc` plus `jscpd` plus `todos` or `rg`.

Evidence: queries combined directory scanners, JSON/SARIF, metrics, duplication, and comment-aware TODO extraction. Primary docs confirm direct mappings to the declared counts, clone pairs, and TODO spans.  
Refs: [scc](https://github.com/boyter/scc), [jscpd](https://github.com/kucherenko/jscpd), [todos](https://github.com/ianlewis/todos), [ripgrep](https://github.com/BurntSushi/ripgrep)

[2] Recent broad analyzers add dead-code, structural-clone, and function-metric findings.

Evidence: queries for multi-language dead-code, clone, and metric CLIs found five active directory scanners whose payloads need normalization into `gen`.  
Refs: [Skylos](https://github.com/duriantaco/skylos), [Fossil](https://github.com/yfedoseev/fossil-mcp), [dupehound](https://github.com/Rafaelpta/dupehound), [arborist-cli](https://github.com/StrangeDaysTech/arborist-cli), [big-code-analysis](https://github.com/dekobon/big-code-analysis)

[3] Offline secret scans are a strong language-independent extension.

Evidence: filesystem-scanner queries found four structured tools. TruffleHog and Kingfisher need their offline flags to prevent provider validation.  
Refs: [Gitleaks](https://github.com/gitleaks/gitleaks), [TruffleHog](https://github.com/trufflesecurity/trufflehog), [Kingfisher](https://github.com/mongodb/kingfisher), [detect-secrets](https://github.com/Yelp/detect-secrets)

[4] License and copyright checks provide useful findings for every file type.

Evidence: standalone-license-scanner queries found three structured filesystem tools. They pass the gates but need the proposed generic diagnostic payload.  
Refs: [ScanCode Toolkit](https://github.com/aboutcode-org/scancode-toolkit), [Licensee](https://github.com/licensee/licensee), [REUSE](https://github.com/fsfe/reuse-tool)

[5] Several active tools remain conditional despite broad language support.

Evidence: primary docs require caller-supplied rules, policy, output conversion, or public data. These tools do not enter the four-gate table.  
Refs: [Semgrep CLI](https://docs.semgrep.dev/cli-reference/), [Opengrep](https://github.com/opengrep/opengrep), [ast-grep](https://ast-grep.github.io/guide/scan-project.html), [PMD](https://pmd.github.io/pmd/pmd_userdocs_cpd.html), [alint](https://github.com/asamarts/alint), [Trivy](https://github.com/aquasecurity/trivy), [OSV-Scanner](https://github.com/google/osv-scanner)
