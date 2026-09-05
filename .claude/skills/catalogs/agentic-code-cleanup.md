# agentic-code-cleanup

- subject: agent-code-quality
- window: 2026-02-15 through 2026-08-15
- scope: public-source analyzers, maintainability metrics, quality gates, review workflows, graph analysis, and controlled repair tools for agent-written code
- verified: github on 2026-08-15
| link                                                                                                                                  | last active |   stars | developer experience                                                                                        | feature tags                                                                                                              |
|---------------------------------------------------------------------------------------------------------------------------------------|------------:|--------:|-------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------|
| [Agent Skills: code-simplification](https://github.com/addyosmani/agent-skills/tree/main/skills/code-simplification)                  |  2026-08-14 |  87,410 | MIT. Repository-level star count. One model-agnostic skill documents Python and TypeScript examples         | lightweight, skill-only, python, typescript, behavior-preserving, changed-code, dead-code, duplication, incremental-tests |
| [Absolute](https://github.com/maddhruv/absolute)                                                                                      |  2026-07-06 |     206 | MIT. Separate simplify, prune, and debt skills include Python, TypeScript, and SQL guidance                 | lightweight, skill-only, python, typescript, sql, simplify, dead-code, lint-debt, hard-gates                              |
| [ECC refactor-clean](https://github.com/affaan-m/ECC/blob/main/commands/refactor-clean.md)                                            |  2026-08-15 | 240,232 | MIT. Claude and Codex plugin paths. It selects language tools, tests each deletion, and reverts failures    | cleanup-agent, python, typescript, dead-code, tool-backed, safety-tiers, rollback, duplication                            |
| [Hermes simplify-code](https://github.com/NousResearch/hermes-agent/blob/main/skills/software-development/simplify-code/SKILL.md)     |  2026-08-15 | 230,920 | MIT. Large Hermes install. Four-agent review increases model use                                            | cleanup-agent, python, typescript, changed-code, parallel-review, risk-tiers, targeted-tests, rollback                    |
| [Claude Command Suite cleanup-vibes](https://github.com/qdhenry/Claude-Command-Suite/blob/main/.claude/commands/dev/cleanup-vibes.md) |  2026-03-01 |   1,325 | No detected license. Claude Code pack creates a backup branch before multi-agent cleanup                    | cleanup-agent, python, typescript, dead-code, secrets, folder-restructure, verification                                   |
| [aislop](https://github.com/scanaislop/aislop)                                                                                        |  2026-08-15 |     552 | MIT. Zero-config deterministic scan with optional agent, hook, MCP, and CI modes                            | lightweight, deterministic, python, typescript, sql-security, ai-slop, dead-code, autofix, sarif                          |
| [AI-SLOP Detector](https://github.com/flamehaven01/AI-SLOP-Detector)                                                                  |  2026-08-10 |      78 | MIT. Offline deterministic core with repository-local calibration                                           | lightweight, deterministic, python, typescript, ai-slop, dead-code, duplication, ci-gate, mcp                             |
| [ai-slopcheck](https://github.com/Euraika-Labs/ai-slopcheck)                                                                          |  2026-06-19 |       0 | MIT. Early deterministic CLI with baselines and changed-file scans                                          | early, deterministic, python, typescript, sql, ai-slop, 72-rules, ci, sarif                                               |
| [TScanner](https://github.com/lucasvtiradentes/tscanner)                                                                              |  2026-06-03 |      35 | MIT. CLI, editor, and Action support regex, script, and model rules across both targets                     | early, policy-engine, python, typescript, diff-scope, custom-rules, ci                                                    |
| [Desloppify](https://github.com/peteromallet/desloppify)                                                                              |  2026-05-13 |   3,021 | OSNL-0.2 source-available license. Local state and broad full-repository scans                              | local-first, python, typescript, quality-score, dead-code, duplication, complexity, autofix                               |
| [PMAT](https://github.com/paiml/paiml-mcp-agent-toolkit)                                                                              |  2026-08-15 |     161 | MIT. One Rust CLI covers 20+ languages. Mutation runs increase execution time                               | deterministic-core, python, typescript, sql, complexity, duplication, mutation-testing, ci, mcp                           |
| [Qlty CLI](https://github.com/qltysh/qlty) | 2026-08-14 | 3,119 | BSL-1.1 with delayed GPL-3.0 publication. Native binaries need no container. The license limits competing services and AI coding services. Tested 2026-08-16: it needs a git repository and `.qlty/qlty.toml`, and no flag overrides either. `qlty metrics` has no machine-readable output | analyzer-suite, python, typescript, sql, complexity, duplication, coverage, autofix, ci, git-required, config-required, smells-sarif |
| [Super-Linter](https://github.com/super-linter/super-linter) | 2026-08-14 | 10,544 | MIT. One Action or OCI container runs a curated analyzer set. The full image is large | analyzer-suite, python, typescript, sql, lint, duplication, formatting, changed-files, ci |
| [MegaLinter](https://github.com/oxsecurity/megalinter) | 2026-08-12 | 2,557 | AGPL-3.0. Broad reports and many analyzers increase image size and configuration work | analyzer-suite, python, typescript, sql, lint, duplication, security, autofix, ci |
| [Qodana CLI](https://github.com/JetBrains/qodana-cli) | 2026-08-14 | 239 | Apache-2.0 CLI. It uses containers or JetBrains IDEs. TypeScript and SQL analysis need Qodana Ultimate | commercial-analyzer, python, typescript, sql, inspections, coverage, quality-gate, sarif, ci |
| [Codacy CLI v2](https://github.com/codacy/codacy-cli-v2) | 2026-06-11 | 26 | MIT. Local mode installs and runs language tools. Cloud configuration and uploads are optional | analyzer-suite, python, typescript, sql, language-discovery, lint, autofix, sarif, optional-cloud |
| [Codacy MCP Server](https://github.com/codacy/codacy-mcp-server) | 2026-07-30 | 62 | Apache-2.0. `npx` setup needs a Codacy token. It can also call Codacy CLI for local analysis | agent-substrate, python, typescript, sql, complexity, duplication, coverage, autofix, mcp |
| [big-code-analysis](https://github.com/dekobon/big-code-analysis) | 2026-08-11 | 19 | MPL-2.0. Early tree-sitter tool with binaries, Python bindings, baselines, and agent hooks | early, deterministic, python, typescript, complexity, maintainability-index, thresholds, hotspots |
| [rust-code-analysis](https://github.com/mozilla/rust-code-analysis) | 2026-04-06 | 434 | MPL-2.0. Rust library, CLI, and web API compute metrics through tree-sitter grammars | deterministic, python, typescript, complexity, maintainability-index, metrics, cli, rest |
| [Lizard](https://github.com/terryyin/lizard) | 2026-08-13 | 2,448 | MIT-style license. Python CLI and library use approximate structural complexity without building the project | lightweight, deterministic, python, typescript, sql, cyclomatic-complexity, duplication, thresholds |
| [scc](https://github.com/boyter/scc) | 2026-08-11 | 8,623 | MIT. One Go binary estimates complexity and cost. It does not perform semantic analysis | lightweight, deterministic, python, typescript, sql, complexity, code-size, hotspots, history, reports |
| [PMD and CPD](https://github.com/pmd/pmd) | 2026-08-15 | 5,467 | BSD-style license. Python and TypeScript support is limited to copy-paste detection. Rule analysis focuses other languages | deterministic, python, typescript, sql, duplication, cpd, thresholds, ci |
| [Drift](https://github.com/mick-gsk/drift)                                                                                            |  2026-08-03 |      14 | MIT. Standalone analyzer and agent hook cover eight languages                                               | deterministic, python, typescript, architecture-drift, duplicates, baseline-ratchet, sarif, mcp                           |
| [Fossil MCP](https://github.com/yfedoseev/fossil-mcp)                                                                                 |  2026-06-22 |      65 | MIT or Apache-2.0. One Rust binary detects findings but does not edit                                       | lightweight, deterministic, python, typescript, dead-code, clones, call-graph, detection-only                             |
| [jscpd](https://github.com/kucherenko/jscpd)                                                                                          |  2026-08-14 |   6,007 | MIT. V5 uses one Rust binary and supports 223 formats. Optional MCP still needs Node                        | deterministic, python, typescript, duplication, sarif, ai-reporter, agent-skill                                           |
| [brooks-lint](https://github.com/hyhmrright/brooks-lint)                                                                              |  2026-08-14 |   1,340 | MIT. Agent Skill, Action, SARIF output, safe fixes, and confirmation gates                                  | review-fix, python, typescript, code-smells, architecture, tech-debt, ci, sarif                                           |
| [Judges Panel](https://github.com/KevinRabun/judges)                                                                                  |  2026-06-22 |       7 | MIT. `npx` CLI, MCP, Action, editor extension, and deterministic patches. Some commands remain experimental | deterministic-core, python, typescript, code-quality, dead-code, autofix, ci, sarif, mcp                                  |
| [AgentSys](https://github.com/agent-sh/agentsys)                                                                                      |  2026-08-15 |     967 | MIT. One npm installer for major coding agents                                                              | cleanup-agent, python, typescript, deslop, dead-code, deterministic-detection, autofix, review-gates                      |
| [Skylos](https://github.com/duriantaco/skylos)                                                                                        |  2026-08-15 |     537 | Apache-2.0. PyPI or container install. Static work stays local                                              | deterministic-core, python, typescript, sql, dead-code, sast, diff-gate, sarif, mcp                                       |
| [VibeGuard](https://github.com/majiayu000/vibeguard)                                                                                  |  2026-08-15 |      38 | MIT. Hooks and guard packs target Codex and Claude Code                                                     | workflow-guard, python, typescript, ai-slop, duplicate-files, build-gate, test-weakening                                  |
| [Legion](https://github.com/9thLevelSoftware/legion)                                                                                  |  2026-07-30 |      73 | No detected license. One installer across major agent CLIs. Cleanup is capped at 50 files                   | cleanup-agent, python, typescript, four-pass-polish, test-rollback, scope-control                                         |
| [Reversa](https://github.com/sandeco/reversa)                                                                                         |  2026-08-05 |   1,478 | MIT. Language-independent legacy workflow with strong safeguards and many artifacts                         | cleanup-agent, python, typescript, legacy-code, behavior-preservation, dead-code-prune, approvals                         |
| [Bug Hunter](https://github.com/codexstar69/bug-hunter)                                                                               |  2026-08-03 |     484 | Agent-skill install across major coding agents. Dependency scanners vary by ecosystem                       | cleanup-agent, python, typescript, adversarial-review, autofix, safe-branch, test-rollback, security                      |
| [githubnext agentics](https://github.com/githubnext/agentics)                                                                         |  2026-07-29 |     901 | MIT. More than 50 language-independent workflows. It needs `gh-aw`, Actions, and agent authentication       | workflow, python, typescript, scheduled-cleanup, code-simplifier, duplicate-code, human-merge                             |
| [Elastic AI GitHub Actions](https://github.com/elastic/ai-github-actions)                                                             |  2026-08-13 |      11 | Language-independent reusable workflows need Actions and an AI engine                                       | workflow, python, typescript, scheduled-cleanup, detector-fixer, duplication, automatic-prs                               |
| [PR-Agent](https://github.com/The-PR-Agent/pr-agent)                                                                                  |  2026-08-13 |  12,554 | MIT. Language-independent CLI, Actions, Docker, and webhook workflows                                       | review-fix, python, typescript, pull-requests, code-improvement, suggestions, ci                                          |
| [Ralph Review](https://github.com/kenryu42/ralph-review)                                                                              |  2026-05-17 |      14 | MIT. Language-independent agent loop uses disposable worktrees and explicit handoff                         | review-fix, python, typescript, iterative-review, selected-remediation, priority-autofix                                  |
| [CodeScene PR Refactoring Agent](https://github.com/codescene-oss/pr-refactoring-agent) | 2026-07-29 | 6 | Action needs CodeScene and an AI-provider secret. A separate [MCP server](https://github.com/codescene-oss/codescene-mcp-server) exposes findings | review-fix, python, typescript, technical-debt, code-health, hotspots, apply-fixes, pr-comments, mcp |
| [CodeScene MCP Server](https://github.com/codescene-oss/codescene-mcp-server) | 2026-08-12 | 61 | Mixed Apache-2.0 and CodeScene terms. Local analysis is available. Historical analysis needs a subscription | agent-substrate, python, typescript, code-health, complexity, cohesion, hotspots, technical-debt, mcp |
| [GritQL](https://github.com/biomejs/gritql)                                                                                           |  2026-08-01 |   4,573 | MIT. CLI supports reusable search, lint, and rewrite rules                                                  | transformation, python, typescript, sql, structural-search, lint, rewrite                                                 |
| [Codemod](https://github.com/codemod/codemod)                                                                                         |  2026-08-14 |   1,068 | Apache-2.0. Local and CI runs, MCP, agent skills, and registry                                              | transformation, python, typescript, ast, multi-file, migrations, dry-run, checkpoints                                     |
| [OpenRewrite](https://github.com/openrewrite/rewrite) | 2026-08-15 | 3,649 | Apache-2.0 core. Python and JavaScript or TypeScript recipes need a Moderne license | transformation, python, typescript, lossless-semantic-tree, mass-refactor, migrations, commercial-target-support |
| [ast-grep](https://github.com/ast-grep/ast-grep)                                                                                      |  2026-08-14 |  15,526 | MIT. Fast CLI with package-manager installs and approachable YAML rules                                     | transformation, python, typescript, structural-search, lint, rewrite, tree-sitter                                         |
| [AFT](https://github.com/cortexkit/aft)                                                                                               |  2026-08-15 |     250 | MIT. One-command setup. Adapters currently target OpenCode and Pi                                           | agent-substrate, python, typescript, symbol-refactor, ast-rewrite, atomic-rollback, backups                               |
| [Graphify](https://github.com/Graphify-Labs/graphify)                                                                                 |  2026-08-14 | 106,541 | Apache-2.0 metadata conflicts with an MIT file. `uv` or `pipx` install                                      | agent-substrate, python, typescript, sql, code-graph, deterministic, edge-provenance, mcp                                 |
| [codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp)                                                                |  2026-08-15 |  39,012 | MIT. Native executable and package-manager installs. Detection only                                         | agent-substrate, python, typescript, dead-code, diff-impact, call-graph, local, mcp                                       |
| [SocratiCode](https://github.com/giancarloerra/SocratiCode)                                                                           |  2026-08-14 |   3,253 | AGPL-3.0 with a commercial license file. Local Docker stack                                                 | agent-substrate, python, typescript, sql-indexing, impact-analysis, call-flow, mcp                                        |
| [Axon](https://github.com/harshkedia177/axon)                                                                                         |  2026-08-03 |     767 | No detected license. Local Python package without Node or API keys                                          | agent-substrate, python, typescript, dead-code, blast-radius, structural-diff, read-only-mcp                              |
| [code-graph-rag](https://github.com/vitali87/code-graph-rag)                                                                          |  2026-08-15 |   4,338 | MIT. Heavy setup needs Python tools, Docker, Memgraph, Qdrant, CMake, and ripgrep                           | controlled-repair, python, typescript, code-graph, dead-code, ast-edit, diff-preview, mcp                                 |
| [CodeGraphContext](https://github.com/CodeGraphContext/CodeGraphContext)                                                              |  2026-08-13 |   4,083 | MIT. `pip` install with embedded or external graph databases                                                | agent-substrate, python, typescript, dead-code, complexity, hotspots, call-graph, mcp                                     |
| [agent-lsp](https://github.com/blackwell-systems/agent-lsp)                                                                           |  2026-08-15 |     108 | MIT. One Go binary plus language servers. CI tests 30 languages                                             | agent-substrate, python, typescript, sql, lsp, dead-code, safe-rename, speculative-edit, mcp                              |
| [OpenLore](https://github.com/clay-good/OpenLore)                                                                                     |  2026-08-13 |     279 | MIT. Local-first npm or brew setup. It intentionally does not delete code                                   | agent-substrate, python, typescript, dead-code-evidence, call-graph, test-impact, guardrails                              |
| [Gortex](https://github.com/zzet/gortex)                                                                                              |  2026-08-15 |   1,143 | Apache-2.0. Cross-repository graph and review use many MCP tools. Writes need an edit profile               | agent-substrate, python, typescript, graph, pr-review, rollback-receipts, controlled-writes, mcp                          |
| [Roam Code](https://github.com/Cranot/roam-code)                                                                                      |  2026-08-15 |     508 | Apache-2.0. Static analysis covers 28 languages. Changes need explicit `--apply`                            | agent-substrate, python, typescript, sql, dead-code, clones, architecture-gates, mcp                                      |
| [Enola](https://github.com/enola-labs/enola)                                                                                          |  2026-08-14 |     107 | Apache-2.0. Deterministic architecture gate. Default CI blocks only new cycles                              | agent-substrate, python, typescript, architecture-regression, cycles, boundaries, ci, mcp                                 |
| [Infigraph](https://github.com/intuit/infigraph)                                                                                      |  2026-08-13 |      61 | Apache-2.0. Setup can download models and SCIP indexers                                                     | agent-substrate, python, typescript, sql-security, semantic-diff, test-gaps, dead-code, mcp                               |
| [tokensave](https://github.com/aovestdipaperino/tokensave)                                                                            |  2026-08-08 |     576 | MIT. Broad analysis and atomic edit tools. No quality-gate workflow is documented                           | agent-substrate, python, typescript, impact-analysis, dead-code, test-map, atomic-edits, mcp                              |
| [codemap](https://github.com/JordanCoin/codemap)                                                                                      |  2026-08-13 |     658 | MIT. Read-only MCP covers 20 dependency languages                                                           | agent-substrate, python, typescript, dependency-graph, diff-impact, blast-radius, read-only-mcp                           |
| [ops-codegraph-tool](https://github.com/optave/ops-codegraph-tool)                                                                    |  2026-08-15 |      88 | Apache-2.0. Analysis covers 34 languages and reports problems without editing                               | agent-substrate, python, typescript, boundaries, complexity, dead-code, diff-impact, mcp                                  |
| [Repowise](https://github.com/repowise-dev/repowise)                                                                                  |  2026-08-16 |   5,933 | AGPL-3.0. Broad health index and pull-request gate. The command is `init`, not `scan`. It writes a `.repowise` index and `.mcp.json` into the repository root, and it can register itself into `~/.claude/settings.json`. Django indexes in about 367 s | agent-substrate, python, typescript, sql, health-score, dead-code, test-gaps, pr-gate, mcp, in-repo-state, slow-index      |
| [code-review-graph](https://github.com/tirth8205/code-review-graph)                                                                   |  2026-08-02 |  30,234 | MIT. Local `pip` or `pipx` setup configures agents, editor, and Actions                                     | agent-substrate, python, typescript, sql, blast-radius, dead-code, test-gaps, mcp, ci                                     |
| [Serena](https://github.com/oraios/serena)                                                                                            |  2026-08-14 |  28,061 | MIT. Mature local MCP toolkit. Optional JetBrains backend is paid                                           | agent-substrate, python, typescript, references, safe-delete, rename, diagnostics, symbolic-edit                          |
| [GitNexus](https://github.com/abhigyanpatwari/GitNexus)                                                                               |  2026-08-15 |  45,411 | PolyForm Noncommercial-1.0.0. Commercial use needs separate terms                                           | agent-substrate, python, typescript, dependency-graph, execution-flows, dry-run-rename, mcp                               |
| [Codanna](https://github.com/bartolli/codanna)                                                                                        |  2026-08-04 |     722 | Apache-2.0. Local CLI and MCP. Semantic search downloads an approximately 150 MB model                      | agent-substrate, python, typescript, call-graph, dependencies, impact-analysis, semantic-search                           |
| [code-graph-mcp](https://github.com/sdsrss/code-graph-mcp)                                                                            |  2026-08-13 |      62 | MIT. One Rust binary through `npx`. Stored-content limits can cause false positives                         | agent-substrate, python, typescript, project-map, call-graph, dead-code, similar-code, mcp                                |
| [CodeQL queries](https://github.com/github/codeql) | 2026-08-14 | 9,942 | MIT query libraries. The required CodeQL engine and CLI use separate terms | quality-gate, python, typescript, maintainability, reliability, semantic-analysis, data-flow, sarif, ci |
| [Semgrep](https://github.com/semgrep/semgrep)                                                                                         |  2026-08-14 |  16,229 | LGPL-2.1. Broad CLI and official MCP. Contextual autofix is hosted                                          | security, python, typescript, static-analysis, mcp, agent-hook, secrets, public-beta-autofix                              |
| [Opengrep](https://github.com/opengrep/opengrep) | 2026-08-14 | 2,951 | LGPL-2.1. Self-contained Semgrep-compatible fork with JSON and SARIF output | security, python, typescript, static-analysis, taint-analysis, custom-rules, sarif, ci |
| [SonarQube](https://github.com/SonarSource/sonarqube) | 2026-08-14 | 10,898 | LGPL-3.0. Mature server-backed analysis and gates. An official [MCP server](https://github.com/SonarSource/sonarqube-mcp-server) exposes findings | quality-gate, python, typescript, deterministic, coverage, duplication, security, ci, mcp |
| [Sloppy Joe](https://github.com/brennhill/sloppy-joe)                                                                                 |  2026-04-17 |      32 | Apache-2.0. Registry-backed npm and Python checks need network access                                       | security, python, typescript, slopsquatting, package-existence, osv, lockfiles, ci                                        |
| [trace-mcp](https://github.com/nikolai-vysotskyi/trace-mcp)                                                                           |  2026-08-15 |      99 | MIT. MCP and CI surface for change-impact evidence and pull-request risk                                    | deterministic, python, typescript, sql, dead-exports, test-gaps, blast-radius, pr-risk, ci                                |
| [diff-cover](https://github.com/Bachmann1234/diff_cover)                                                                              |  2026-08-08 |     842 | Apache-2.0. Gates changed-line coverage from existing reports. Tests cover Python and TypeScript lcov       | test-quality, python, typescript, sql-plugin, changed-lines, coverage-gate, ci                                            |
| [Coding Ethos](https://github.com/paudley/coding-ethos)                                                                               |  2026-08-05 |       6 | AGPL-3.0 or commercial license. Heavier policy platform with managed tools                                  | policy-as-code, python, typescript, sql, normalized-diagnostics, grouped-autofix, sarif, mcp                              |
| [Developer Kit](https://github.com/giuseppe-trisciuoglio/developer-kit)                                                               |  2026-06-22 |     329 | MIT. Broad plugin marketplace. Cleanup command is narrow                                                    | skill-pack, python, typescript, code-cleanup, import-cleanup, refactor-agents                                             |
| [pskoett AI skills](https://github.com/pskoett/pskoett-ai-skills)                                                                     |  2026-06-12 |     278 | No detected license. Language-independent simplify-and-harden skills for major agents                       | skill-pack, python, typescript, simplify-and-harden, verify-fix-loop, headless-ci, multi-agent-audit                      |

## gates

- required targets: python and typescript
- optional target: sql
- repository gates: more than one contributor, created before 2026-05-15, and pushed on or after 2026-02-15
- language gate: native analysis, tested transformation, or a documented language-independent agent workflow must cover both required targets
- exclusion: general coding agents without a dedicated analysis, quality, cleanup, repair, refactor, or migration workflow
- lightweight: no required database, container, hosted service, or broad agent runtime

## cautions

- passing tests alone does not prove structural cleanup quality
- feature counts and performance figures are project claims unless the evidence sections state independent results
- source availability does not imply an osi-approved license

## quality evidence

[slopcodebench][slopcodebench]
    the 2026-05-07 v2 evaluates 15 agents on 36 problems and 196 iterative checkpoints.
    no agent completes a full trajectory, and the best checkpoint pass rate is 14.8%.
    structural erosion rises in 77% of trajectories, and verbosity rises in 75.5%.
    quality prompting improves initial code but does not stop later degradation.

[swe ci][swe-ci]
    the benchmark contains 100 repository histories averaging 233 days and 71 commits.
    its ci loop measures sustained functional correctness through later requirements.
    the authors use this result as a maintainability proxy.

[code cleanliness][code-cleanliness]
    one controlled study runs 660 claude code trials on java and python repository pairs.
    clean variants change pass rate by -0.9 points, use 7.1% fewer tokens, and need 33.8% fewer file revisits.

[smellbench repair][smellbench-repair]
    experts classify 63.1% of 65 detected scikit-learn architecture findings as false positives.
    the most aggressive of 11 agent configurations introduces 140 new smells during repair.
    the study uses one python project and one detector.

[smellbench refactor][smellbench-refactor]
    the benchmark contains 294 cases from seven python repositories.
    most models pass more than 80% of tests, but the best smell-elimination score is 50.34.
    an llm judge evaluates structural quality.

[codetaste][codetaste]
    agents execute detailed refactor instructions better than they discover human refactor choices.
    propose-then-implement decomposition improves alignment with human changes.

[refactoring runaway][refactoring-runaway]
    tangled refactors appear in 21.43% of 3,691 agent patches.
    they correlate with lower compilability but not with functional-correctness scores.
    refactoring-aware refinement raises compilability from 19.34% to 38.33%.

[swe bench promax][swe-bench-promax]
    the benchmark has 170 expert-curated refactors across seven languages, including python and typescript.
    tasks average 11.4 files and 261.6 changed lines.
    the best tested model resolves 41.2% of tasks across the pooled language set.

## verification evidence

[building to the test][building-to-the-test]
    near-perfect hidden-test scores can coexist with an absent or unfinished requested library.
    a passing oracle score certifies checked behavior, not complete delivery of user intent.

[code review agent benchmark][code-review-agent-benchmark]
    four review agents score from 20.1% to 32.1% on 234 human-review oracles.
    their union reaches 41.5%, while maintainability pass rates range from 7.9% to 27.0%.

[coderabbit field study][coderabbit-field-study]
    the study examines 31,073 reviews with developer replies from 10,191 pull requests.
    it includes 45 typescript projects and 34 python projects, but reports pooled results.
    developers reject 56.3% of the reply-bearing review subset.

[agentlens][agentlens]
    10.7% of passing trajectories in the 1,815-run subset are lucky passes.
    regression cycles, blind retries, and missing verification are invisible to pass rate alone.

[scaffold cegis][scaffold-cegis]
    iterative refinement increases vulnerabilities in 43.7% of sampled gpt-4o chains after ten rounds.
    sast-only gating raises latent degradation from 12.5% to 20.8% in the reported experiment.
    the complete scaffold-cegis framework reduces latent degradation to 2.1%.

[swe mutation][swe-mutation]
    the benchmark contains 500 python tasks and 300 tasks across nine other languages.
    its non-python set includes typescript, but library differences prevent strict language comparisons.
    deepseek-v3.1 reaches 10.20% verification and 36.15% detection.

[swe skills bench][swe-skills-bench]
    39 of 49 tested skills provide no pass-rate improvement.
    three skills reduce performance by up to 10% when their guidance conflicts with project context.

[abtest][abtest]
    647 repository-grounded behavior tests expose 1,573 anomalies across three coding agents.
    manual review confirms 642 new anomalies at 40.8% precision.

## hosted controls

[github agent validation][github-agent-validation]
    github runs codeql, dependency advisory checks, and secret scanning on codex and claude changes.
    detected issues trigger an agent repair attempt before pull-request handoff.

[github agentic autofix][github-agentic-autofix]
    agentic autofix accepts codeql and third-party scanning alerts.
    it rescans proposed fixes and stops at a draft pull request for review.

[github code quality][github-code-quality]
    github combines deterministic analysis, ai-assisted detection, autofix, and ruleset gates.
    rulesets can block merges on findings or coverage thresholds.

[github agentic workflows][github-agentic-workflows]
    workflows use read-only defaults, a sandbox, a firewall, and structured safe outputs.
    threat detection runs before proposed changes are applied.

[codex security][codex-security]
    codex security builds a threat model and reproduces findings in sandboxed validation environments.
    patches remain review-oriented rather than applying automatically.

[benchmark audit][benchmark-audit]
    an automated filter flags 286 of 731 public swe-bench pro tasks.
    five engineers review that subset and classify 249 tasks as broken.
    failure modes include strict tests, underspecified prompts, and low test coverage.

## synthesis

- benchmark tests do not establish full requirement compliance or structural maintainability
- detector findings provide evidence, not truth or semantic equivalence

## refs

[slopcodebench]: https://arxiv.org/abs/2603.24755
[swe-ci]: https://arxiv.org/abs/2603.03823
[code-cleanliness]: https://arxiv.org/abs/2605.20049
[smellbench-repair]: https://arxiv.org/abs/2605.07001
[smellbench-refactor]: https://arxiv.org/abs/2606.05574
[codetaste]: https://arxiv.org/abs/2603.04177
[refactoring-runaway]: https://arxiv.org/abs/2605.22526
[swe-bench-promax]: https://arxiv.org/abs/2608.09802
[building-to-the-test]: https://arxiv.org/abs/2606.28430
[code-review-agent-benchmark]: https://arxiv.org/abs/2603.23448
[coderabbit-field-study]: https://arxiv.org/abs/2607.03316
[agentlens]: https://arxiv.org/abs/2605.12925
[scaffold-cegis]: https://arxiv.org/abs/2603.08520
[swe-mutation]: https://arxiv.org/abs/2605.22175
[swe-skills-bench]: https://arxiv.org/abs/2603.15401
[abtest]: https://arxiv.org/abs/2604.03362
[github-agent-validation]: https://github.blog/changelog/2026-06-09-security-validation-for-third-party-coding-agents/
[github-agentic-autofix]: https://github.blog/changelog/2026-07-10-agentic-autofix-for-code-scanning-alerts-in-public-preview/
[github-code-quality]: https://github.blog/changelog/2026-07-20-github-code-quality-is-now-generally-available/
[github-agentic-workflows]: https://github.blog/changelog/2026-06-11-github-agentic-workflows-is-now-in-public-preview/
[codex-security]: https://openai.com/index/codex-security-now-in-research-preview/
[benchmark-audit]: https://openai.com/index/separating-signal-from-noise-coding-evaluations/
