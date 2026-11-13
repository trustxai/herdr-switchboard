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
telemetry, and it opens no network connection of its own. This is everything it reaches outside
its own process, which is also the scope of this policy.

### The local herdr

It reads the workspaces, tabs, panes and agents of the local herdr through the herdr CLI (the
binary in `HERDR_BIN_PATH`, or `herdr` on `PATH`), shows the recent output of a pane in the
preview, and focuses the pane you choose. It does not create or close anything, and it renames
nothing unless the optional jump below is enabled.

### ssh to your saved machines

For every machine you already saved in herdr, it runs `ssh` to that machine to read its
snapshot, show previews and focus panes there. It uses your own ssh configuration, keys and
agent, and reuses one multiplexed connection per machine (OpenSSH `ControlMaster`). Switchboard
itself never handles a password or a key, and it only reaches machines that are already saved in
herdr. What it runs on the other side is the herdr CLI of that machine.

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

It keeps the last snapshot of each machine, so the list appears at once while fresh data
arrives, and a small ledger of which agents changed and which finished work you have already
seen. Both live in the plugin's state directory: `$HERDR_PLUGIN_STATE_DIR`, or
`${XDG_STATE_HOME:-~/.local/state}/herdr-switchboard` when it runs outside herdr. They hold
machine labels, workspace, tab and pane names, pane titles and working directories, and nothing
else: no pane output, no credentials. Deleting the directory is safe.

### The optional cross-machine jump (off by default)

With `[jump] enabled = true` in the config, choosing a pane on another machine also switches your
herdr window to that machine. To do that, the herdr server runs `ssh` back to the Mac where your
herdr window is open and, through AppleScript (`osascript`), sends keystrokes to the Ghostty
terminal there: the herdr shortcut that opens its own navigator, the name of the pane, and
Enter. When the pane's name is not unique, it gives the pane a unique name for a moment and then
restores the original one.

This is the most sensitive part of the plugin. It only works if the herdr server can log in to
your Mac over ssh, and anyone who controls the account that runs the herdr server can then type
into your terminal. Turn it on only when the server is as trusted as the Mac, give the server a
key of its own for this, and restrict that key in the Mac's `authorized_keys` (for example with a
`from=` option). With the jump disabled, or when anything it needs is missing, Switchboard only
focuses the pane through herdr on its own machine.

## Out of scope

- Vulnerabilities in herdr, fzf, OpenSSH, Ghostty or macOS themselves: please report them to
  those projects.
- Attacks that already require control of your user account, or of a machine you saved in
  herdr, beyond what that access already gives.
