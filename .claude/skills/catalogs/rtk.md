# rtk

- verified: the upstream repository and a local rtk 0.45.0 binary on 2026-08-16
- rtk integrates per agent; the integration method decides whether manual prefixing is necessary.

[home][home]
    rtk is a cli proxy that filters command output before an agent reads it
    the project is apache-2.0, written in rust, and published to homebrew as `rtk`
    a name collision exists with rust type kit on crates.io

[repo][repo]
    the binary proxies more than 100 commands with less than 10 ms overhead
    the stated claim is "up to 90% of bash output", not 90% of spend
    bash output is one input contributor beside prompt, system prompt, and history

[agents][agents]
    integration method differs per agent and is not uniform
    claude code installs a pretooluse hook that rewrites bash commands
    codex receives agents.md and rtk.md instructions and gets no hook
    gemini uses a beforetool hook; cursor uses hooks.json; windsurf and cline write project rule files

[codex flag][codex-flag]
    `rtk init -g --codex` is the codex installer
    the local help states "target codex cli (uses agents.md + rtk.md, no claude hook patching)"
    `rtk hook` accepts claude, cursor, gemini, copilot, droid, and vibe, and rejects codex

[hook scope][codex-flag]
    the hook fires on bash tool calls only
    read, grep, and glob bypass the hook and stay unfiltered
    `rtk read`, `rtk grep`, and `rtk find` recover compaction for those paths

[rewrite][repo]
    `rtk rewrite` is the single source of truth that every hook calls
    `rtk hook check "<cmd>"` prints the rewrite without running it
    rewriting is idempotent: `rtk git status` stays `rtk git status`

[support][support]
    the supported-agents guide documents override controls and graceful degradation
    telemetry records the hook type in use and is documented in docs/TELEMETRY.md

## refs

[home]: https://www.rtk-ai.app/
[repo]: https://github.com/rtk-ai/rtk
[agents]: https://github.com/rtk-ai/rtk#supported-agents
[codex-flag]: https://github.com/rtk-ai/rtk#quick-start
[support]: https://www.rtk-ai.app/guide/troubleshooting
