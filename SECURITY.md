# Security policy

## Supported versions

Only the latest release is supported. Fixes land on `main` and ship in the next release.

| Version | Supported |
| ------- | --------- |
| 0.1.x   | Yes       |

## Reporting a vulnerability

Report it privately through GitHub's private vulnerability reporting:
<https://github.com/trustxai/herdr-switchboard/security/advisories/new> (the **Report a
vulnerability** button under the repository's **Security** tab). Please do not open a public
issue, discussion or pull request for a security problem.

Include:

- the version (the `version` line of `herdr-plugin.toml`) and the herdr, fzf, Python and
  operating system versions;
- what an attacker needs (a local account, control of a saved machine, a crafted pane title…);
- steps to reproduce and the impact you observed.

Do not paste real hostnames, addresses, usernames or paths in the report unless they are needed
to reproduce the problem.

This is a small project maintained by one person. Expect an acknowledgement within a few
business days and a fix or a decision within 30 days. You will be credited in the advisory and
the changelog unless you prefer otherwise.

## What the plugin touches

Switchboard is one Python script that uses only the standard library and drives
[fzf](https://github.com/junegunn/fzf). It has no dependencies to install, no build step and no
telemetry, and it opens no network connection of its own. With the cross-machine jump off, which
is the default, the sections below up to the state directory are everything it reaches outside
its own process. The jump adds what its own section describes. All of it is the scope of this
policy.

### The local herdr

It reads the workspaces, tabs, panes and agents of the local herdr through the herdr CLI (the
binary in `HERDR_BIN_PATH`, or `herdr` on `PATH`), shows the recent output of a pane in the
preview, and focuses the pane you choose. It does not create or close anything, and it renames
nothing unless the optional jump below is enabled.

### ssh to your saved machines

For every machine you already saved in herdr, it runs `ssh` to that machine to read its
snapshot, show previews and focus panes there. It uses your own ssh configuration, keys and
agent, in batch mode (it never prompts), and reuses one multiplexed connection per machine
(OpenSSH `ControlMaster`). Switchboard itself never handles a password or a key. What it runs on
the other side is the herdr CLI of that machine. With the jump off, which is the default, it only
reaches machines that are already saved in herdr.

### The clipboard (OSC 52)

When you press `ctrl-y` it copies the agent's last reply, and when you select text in the
`ctrl-o` viewer it copies that selection. It writes the text with an OSC 52 escape sequence;
herdr forwards it to the terminal you are typing in, so the text reaches the clipboard of that
machine even when the pane lives on another one. The reply comes from the pane's screen or, for
an agent session on the local machine, from that session's transcript file, which is read only
at that moment. Nothing is written to the clipboard unless you ask for it.

### The fzf control socket

The list updates while it is open by talking to fzf through its `--listen` socket. That socket
must be a Unix socket in a temporary directory that only your user can open, never a TCP port: a
socket other local users could reach would let them drive fzf, and that is in scope.

### The state directory

It keeps two things in the plugin's state directory: `$HERDR_PLUGIN_STATE_DIR`, or
`${XDG_STATE_HOME:-~/.local/state}/herdr-switchboard` when it runs outside herdr.

- **The last snapshot of each machine**, so the list appears at once while fresh data arrives.
  It is herdr's snapshot as herdr returns it: workspace and tab labels; pane ids, titles and
  working directories; each agent's kind, status, session id and change counters; and the
  layout of every tab (pane sizes and positions). The herdr version comes along with it.
- **A small ledger** of which agents changed and which finished work you have already seen: per
  machine, the agents' change counters and the tab you last focused there.

Neither holds pane output, and neither holds credentials. Deleting the directory is safe.

### The optional cross-machine jump (off by default)

With `[jump] enabled = true` in the config, choosing a pane on another machine also switches your
herdr window to that machine. The window is driven from the Mac it runs on, so the machine where
the popup runs (the herdr server) has to reach that Mac over ssh.

**Which Mac.** If `[jump] client` is set, that ssh target is the Mac, and nothing is detected.
Otherwise Switchboard looks for it:

- if the herdr server is itself a Mac with a herdr window open, that machine is a candidate, and
  for it everything below runs locally instead of over ssh;
- it reads the source address of the ssh connections behind the herdr windows attached to this
  server (herdr's `remote-client-bridge` processes);
- if the `tailscale` binary is installed, it runs `tailscale status` to put a name and an
  operating system on those addresses; Tailscale is never required;
- an address it cannot identify that way gets `ssh <address> uname -s`, to see whether it is a
  Mac;
- when more than one Mac qualifies, it runs `ioreg` on each one to read how long it has been
  idle, and picks the one you touched last.

**What runs on that Mac.** Over ssh, with your keys and in batch mode:

- `herdr plugin list --json`, to find where the plugin is installed there (or the command in
  `[jump] helper`, if you set one);
- the plugin's own helper, `python3 <plugin directory>/bin/switchboard --jump-server`. It uses
  AppleScript (`osascript`) to send keystrokes to the Ghostty window that runs herdr: the herdr
  shortcut that opens its navigator, a search that matches only the chosen pane, and Enter. It
  then asks herdr to focus that pane. When no search matches only that pane, it gives the pane a
  unique name for a moment and then restores the original one.

This is the most sensitive part of the plugin, for two reasons. The herdr server must be able to
log in to your Mac over ssh, and anyone who controls the account that runs the herdr server can
then type into your terminal. And without `[jump] client`, the detection connects to addresses
it learned from the system, not from your herdr configuration. So:

- turn the jump on only when the server is as trusted as the Mac;
- **set `[jump] client`** to the Mac's ssh target, so the server connects to that host and
  nothing else;
- give the server a key of its own for this, and restrict it in the Mac's `authorized_keys`
  (for example with a `from=` option).

With the jump off, or when anything it needs is missing, Switchboard only focuses the pane
through herdr on its own machine.

## Out of scope

- Vulnerabilities in herdr, fzf, OpenSSH, Ghostty or macOS themselves: please report them to
  those projects.
- Attacks that already require control of your user account, or of a machine you saved in
  herdr, beyond what that access already gives.
