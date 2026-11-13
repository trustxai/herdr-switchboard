# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - Unreleased

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
- Configuration in `config.toml`: language, local machine label, refresh intervals, colours,
  how to run herdr on other machines, and the cross-machine jump.
- English and Spanish interface.
- A start-up check for Python 3.9 or newer and fzf 0.71 or newer that says what is missing and
  how to install it.
- `--demo`, which shows the interface over bundled sample data with no herdr, ssh or network.
- An optional jump that switches the herdr window on a macOS client running Ghostty to the
  chosen machine. Off by default; see [SECURITY.md](SECURITY.md) before enabling it.
- Apache License 2.0, security policy, contributing guide and CI on Linux and macOS.

[Unreleased]: https://github.com/trustxai/herdr-switchboard/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/trustxai/herdr-switchboard/releases/tag/v0.1.0
