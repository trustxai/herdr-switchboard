# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- The cross-machine jump is on by default (`[jump] enabled = true`): Enter on another machine's
  row switches a herdr window running in Ghostty on macOS to that pane. When the jump cannot
  happen (no herdr window in Ghostty on a Mac the server can reach over ssh, herdr keys there
  that differ from `[jump]`'s, or a helper of an older version on that Mac), Enter works as with
  the jump off: it focuses the pane on its machine and the footer says so. `enabled = false`
  turns it off. If your herdr `[keys] prefix` or `goto` are not herdr's defaults, set the same
  values under `[jump]`.
- The demo's Enter line says that the demo never jumps between machines.

### Fixed

- With the jump on, Enter on another machine's row no longer holds the popup while the
  connection to the Mac is set up: it waits for it 2 seconds at most, then focuses the pane
  instead, and the popup's close never waits for an ssh lookup (before, up to about 12 seconds
  with a Mac that did not answer).
- The jump types only into a herdr window whose terminal is Ghostty's, so AppleScript is never
  pointed at a Ghostty that is not running or not installed. A `herdr` CLI call in a Ghostty tab
  (`herdr --machine x agent list`) is not taken for a window, `herdr session attach <name>` is,
  and with several windows the jump types into the one you typed into last.
- The jump no longer types keys that the window's herdr does not bind. The helper on the Mac
  finds the herdr config of the window it would type into from that window's own environment,
  reads its `[keys]` and `[[keys.command]]` bindings and runs `herdr config check` on it. It
  does not jump when `[jump] prefix` and `goto` differ from that config's, when another binding
  is on goto's key or the prefix, when herdr reports a parse or read error or anything about
  those keys, when the window uses the server's keys (`--remote-keybindings server` or
  `HERDR_REMOTE_KEYBINDINGS=server`), when a key letter is upper case (shift in herdr), or when
  it cannot be sure (no `HOME` in the window's environment, or, without `tomllib`, a value that
  spans lines): Enter focuses the pane and the footer says to set them under `[jump]`.
- A helper on the Mac that never says it is ready (an older version does not) no longer makes
  every Enter wait: after 8 seconds the popup stops waiting for it, and Enter focuses the pane
  at once.
- Work that finished in the tab in front on a machine no longer stays `done` after you left that
  tab there: once that machine's focus moves to another tab (not by Enter in the popup), the
  work counts as seen, as in herdr's own panel. Before, it stayed `done` until you opened the
  popup on that tab or picked it with Enter.

## [0.1.0] - 2026-11-15

First public release.

### Added

- A popup that lists every agent and terminal of every machine saved in herdr, sorted by what
  needs attention (blocked, done, working, idle, unknown, then terminals), with machines
  interleaved by their most recent change.
- Its own tracking of finished work, so an agent stays "done" until you have seen it, whichever
  machine you were looking at when it finished.
- A live preview of each pane, and a list that updates while it is open.
- Enter focuses the chosen pane, on this machine or on another one.
- `ctrl-y` copies the agent's last reply and `ctrl-o` opens the pane in a viewer where a mouse
  selection is copied, both through OSC 52.
- `ctrl-t` shows only the terminals.
- Configuration in `config.toml`: language, local machine label, refresh intervals and
  timeouts (`local_timeout` for this machine's herdr, `remote_timeout` for the others), colours,
  how to run herdr on other machines, and the cross-machine jump. A file or value it cannot use
  falls back to the default and is named in the popup's header.
- English and Spanish interface.
- A start-up check for Python 3.9 or newer and fzf 0.71 or newer that says what is missing and
  how to install it (without any `python3` on the herdr server's `PATH`, the pane says so and
  waits for Enter), and a message naming `[refresh] local_timeout` when this machine's herdr
  does not answer in time.
- `--demo`, which shows the interface over bundled sample data with no herdr, ssh or network.
- An optional jump that switches the herdr window on a macOS client running Ghostty to the
  chosen machine, typing the herdr keys set in `[jump] prefix` and `goto` (herdr's defaults,
  `ctrl+b` and `prefix+g`, unless changed). Off by default, and off for the run when a key is
  outside the accepted set; a pane it renames for the jump gets its name back even when the
  typing fails or a signal arrives. See [SECURITY.md](SECURITY.md) before enabling it.
- The popup removes its temporary files on every close, also when its window or session goes
  away (SIGHUP or SIGTERM), and in that case ends its own fzf.
- The programs it starts (herdr, ssh, osascript, the focus worker) get an environment without
  fzf's `FZF_*` variables or the path of the popup's run directory.
- README images made from `--demo`, and `docs/render.sh`, which regenerates them.
- Apache License 2.0, security policy, contributing guide and CI on Linux and macOS.

[Unreleased]: https://github.com/trustxai/herdr-switchboard/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/trustxai/herdr-switchboard/releases/tag/v0.1.0
