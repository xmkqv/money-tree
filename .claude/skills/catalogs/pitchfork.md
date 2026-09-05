# pitchfork

- verified: current configuration and scheduling docs and a local pitchfork 2.20.0 binary on 2026-08-18
- the docs site declares 2.21.0, so the local binary is one minor version behind.
- pitchfork supervises processes and also watches files; the two are separate features.

[home][home]
    pitchfork is a process manager for developers, written by jdx, the author of mise
    the project is mit and the docs are a vitepress site
    the tag line is "summon your daemons", and the vocabulary stays with the theme

[config][config]
    a repository declares its daemons in a root pitchfork.toml
    the top level holds daemons, groups, namespace, namespaces, env, settings, and slugs
    `namespace = "x"` prefixes every daemon id as `x/<name>`, which `pitchfork daemons` prints
    a group is `[groups.<name>] daemons = [...]`, and holds nothing else
    a group that names a daemon with no block fails the start on the unknown id
    an omitted daemon dir defaults to the directory that contains pitchfork.toml

[cron][cron]
    the default cron retrigger mode is finish
    finish starts a new run only after the prior run has finished

[daemon keys][daemon-keys]
    a daemon block accepts run, dir, env, user, mise, pty, and port
    readiness accepts ready_output, ready_cmd, ready_http, ready_port, and ready_delay
    lifecycle accepts retry, depends, auto, cron, hooks, boot_start, and stop_signal
    limits accept cpu_limit and memory_limit
    logs accept logs, time_retention, line_retention, and archive_hook
    watching accepts watch and watch_mode

[retry][retry]
    the schema reads "true = indefinite, false/0 = none, number = count"
    retry accepts a boolean or a non-negative integer, and nothing else
    a daemon with no retry key does not restart after it fails
    the docs state that restarts use configurable retry limits and exponential backoff

[ready][ready]
    ready_output takes a regex string, or `{ pattern, timeout }` with an overall polling timeout
    the regex matches against ansi-stripped stdout and stderr lines
    the default ready delay is three seconds when no check is declared
    `pitchfork start` also takes --delay, --output, --http, --port, and --cmd for one run

[watch][watch]
    watch is an array of glob patterns, and watch_mode selects native, poll, or auto
    a matched change restarts the daemon; it does not signal a running process
    the notify crate detects the change and debounces it for one second
    patterns resolve against the pitchfork.toml directory, not the process directory
    only a running daemon restarts, so a stopped daemon stays stopped
    the documented syntax is include-only, so a pattern cannot express an exclusion
    an exclusion therefore needs an external watcher, or a filter inside the run script

[shell][shell]
    `settings.general.shell` defaults to `sh -c`, so a run script is posix, not bash
    `read -t` is a bash extension, so a timed drain works on macos and fails under dash
    `settings.general.interval` defaults to 10s and `autostop_delay` to 1m

[cli][cli]
    `pitchfork daemons` lists the merged configuration and exits 0 on a valid file
    `pitchfork start --group <name>` starts every daemon of one group
    -l starts every local daemon, -g every global one, and -a both
    -f stops a daemon that already runs, and restarts it
    `pitchfork logs`, `status`, `list`, `wait`, and `tui` read the running state

[auto][auto]
    `auto` is an array of the strings start and stop
    the shell hook starts a daemon on entry to the directory and stops it on exit
    `pitchfork activate` installs the hook into the shell session

[mcp][mcp]
    `pitchfork mcp` runs a model context protocol server over stdin and stdout
    the server lets an assistant start, stop, restart, and read the logs of a daemon

## refs

[home]: https://pitchfork.jdx.dev/
[config]: https://pitchfork.jdx.dev/reference/configuration.html
[cron]: https://pitchfork.jdx.dev/guides/scheduling.html
[daemon-keys]: https://pitchfork.jdx.dev/schema.json
[retry]: https://pitchfork.jdx.dev/guides/auto-restart.html
[ready]: https://pitchfork.jdx.dev/guides/ready-checks.html
[watch]: https://pitchfork.jdx.dev/guides/file-watching.html
[shell]: https://pitchfork.jdx.dev/reference/settings.html
[cli]: https://pitchfork.jdx.dev/cli/
[auto]: https://pitchfork.jdx.dev/guides/shell-hook.html
[mcp]: https://pitchfork.jdx.dev/guides/mcp.html
