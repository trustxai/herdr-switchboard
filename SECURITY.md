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
telemetry, and it opens no network connection of its own: it reaches other machines through
`ssh` and through herdr. With the cross-machine jump off, which is the default, the sections
below up to the state directory are everything it reaches outside its own process. The jump
adds what its own section describes. All of it is the scope of this policy.

### The programs it runs

`herdr` is the binary in `HERDR_BIN_PATH` (herdr sets it for plugin commands), or `herdr` on
`PATH`; `fzf` is found on `PATH`. So that a herdr server started without Homebrew's directories
still finds them, Switchboard appends `/opt/homebrew/bin`, `/home/linuxbrew/.linuxbrew/bin`,
`/usr/local/bin` and `~/.local/bin` to the end of its own `PATH` when they exist: they fill
gaps and never shadow what comes first. The helpers it starts (herdr, ssh, osascript and the
like) get `/dev/null` or one of its own pipes as their input, never the popup's terminal.

### The local herdr

It reads the workspaces, tabs, panes and agents of the local herdr (`herdr api snapshot`), the
machines saved in it (`herdr machine list --json`; disabled ones are skipped), and the recent
output of a pane (`herdr pane read`) for the preview, `ctrl-y` and `ctrl-o`. The one change it
makes is focusing the pane you choose (`herdr agent focus`, or `herdr tab focus` for a plain
terminal). It does not create or close anything, and it renames nothing unless the optional jump
below is enabled.

### What comes back from herdr is untrusted

Any process in a pane sets its own title, and a saved machine sends whatever it sends, so every
snapshot is checked before use. Ids (machine, pane, tab) must look like herdr's, letters, digits
and `_:.@+=-`, starting with a letter, digit or `_`, at most 128 characters, or the row is
dropped; only then do they reach herdr's command line or a row. Labels, titles and working
directories lose escape sequences and control characters before they are shown, numbers must be
numbers, and an answer that is not a snapshot counts as no answer. Pane output in the preview
keeps its colours and line breaks and loses every other escape sequence (clipboard writes, title
changes, screen clears).

### ssh to your saved machines

For each enabled machine saved in herdr with an ssh target, it runs `ssh` to that machine to read
its snapshot, show previews and focus panes there. It uses your own ssh configuration, keys and
agent, with `BatchMode=yes` (it never prompts) and `ConnectTimeout=5`, and the destination goes
after `--` so it can never be read as an option. Switchboard itself never handles a password or
a key. What it runs on the other side is the `[remote] herdr` value of your config, a command
line for the remote shell, followed by quoted arguments: that value is as trusted as your config
file.

It keeps one multiplexed connection per machine (OpenSSH `ControlMaster=auto`,
`ControlPersist=600`: the connection stays open for ten minutes after its last use). The control
sockets go in `$XDG_RUNTIME_DIR/switchboard` when that runtime directory is yours and nobody else
can write to it, else in `/tmp/switchboard-<uid>`. Either one must be a real directory, not a
symlink, owned by you, with no access for group or others; a directory someone else created at
that path is refused, and then connections are simply not shared.

When that ssh fails, or the saved machine has no ssh target, the same command goes through
`herdr --machine <id>` instead, which uses herdr's own connection to that machine and herdr's
own way of authenticating to it.

With the jump off, it only reaches machines that are already saved in herdr.

### The clipboard (OSC 52)

When you press `ctrl-y` it copies the agent's last reply, and when you select text in the
`ctrl-o` viewer it copies that selection, at most 100,000 characters either way. It writes the
text with an OSC 52 escape sequence; herdr forwards it to the terminal you are typing in, so the
text reaches the clipboard of that machine even when the pane lives on another one. The reply
comes from the pane's screen or, for an agent session on the local machine, from that session's
transcript (the newest file matching `~/.*/projects/*/<session id>.jsonl`, the last 4 MiB of it),
read at that moment and not kept. Nothing is written to the clipboard unless you ask for it.

### The run directory and the fzf socket

Each popup creates a private directory, `/tmp/switchboard-XXXXXXXX` (`mkdtemp`, mode 0700; `/tmp`
because a Unix socket path is limited to 104 bytes on macOS; the tests move it with
`SWITCHBOARD_RUN_ROOT`). It holds:

- `fzf.sock`, the socket fzf listens on (`--listen`) so the list can update while it is open.
  It is a Unix socket in a directory only your user can open, never a TCP port: a socket other
  local users could reach would let them drive fzf, and that is in scope.
- `rows`, the list fzf reloads;
- `acks` and `focus-<pid>-<ms>` files, for Enter on another machine's row (below).

The parts of Switchboard that use the directory after the popup has started open it once, check
that it is a real directory (not a symlink) owned by you with no access for group or others, and
from then on work only through that descriptor: files are created with `O_NOFOLLOW` and mode
0600, result files also with `O_EXCL`, and only regular files are read. The popup always
removes the directory when it closes. A refresh still under way at that moment cannot write
anywhere else: its writes go through the removed directory's descriptor and fail, and fzf's
socket is contacted only after such a write succeeded.

The popup also closes this way when its window or session goes away: SIGHUP and SIGTERM exit
through the same cleanup, which removes the run directory (and, for `--demo`, its temporary
state directory). A second SIGHUP or SIGTERM during that cleanup is ignored, so it finishes.
The detached focus worker and the jump helper run in sessions of their own and do not get the
popup's hangup.

### Enter on another machine's row

With the jump off, Enter on another machine's row records the row's tab as seen (one line in
`acks`) and starts a worker, `bin/switchboard --focus`, in a session of its own, so neither Esc nor
the popup closing can stop it. The worker runs the focus on that machine, by ssh or
`herdr --machine` as above, writes a one-line result file in the run directory, and exits. It
never receives the directory's name: it inherits a descriptor of it, opened and checked while
the popup still owned the directory, and its command line holds only the bare name of its result
file, which must match `focus-<digits>-<digits>`. If the popup has already removed the directory,
the worker writes nothing; the focus has happened all the same. In the popup, a background fzf
action waits for that file for up to twice the remote timeout plus three seconds and shows it in
the footer.

### The state directory

It keeps two things in the plugin's state directory: `$HERDR_PLUGIN_STATE_DIR`, or
`${XDG_STATE_HOME:-~/.local/state}/herdr-switchboard` when it runs outside herdr.

- **`snapshots/<machine>.json`, the last snapshot of each saved machine** (not of the local
  one), so the list appears at once while fresh data arrives. It is the snapshot object exactly
  as herdr returned it, plus the time it was read, so it holds whatever herdr puts in a
  snapshot; that includes the workspace, tab and pane labels, pane titles and working
  directories, and each agent's kind, status, session id and change counters. It is written even
  with `cache_max_age = 0`, which only stops it from being shown.
- **`recency.json`**: per machine and agent pane, the last change counter seen, when it was seen,
  its rank among the changes seen together, up to which counter finished work counts as seen,
  and the counter at which herdr last reported it done; and per machine, the tab that was
  focused at the last read.

Switchboard writes no pane output and no credentials there. Deleting the directory is safe: the
order inside each status and the `done` marks start over.

### The optional cross-machine jump (off by default)

With `[jump] enabled = true` in the config, choosing a pane on another machine also switches your
herdr window to that machine. The window is driven from the Mac it runs on, so the machine where
the popup runs (the herdr server) has to reach that Mac over ssh. When there is at least one
saved machine, that connection is opened as soon as the popup opens, so Enter only has to send
one line; Esc, or a row of the local machine, makes the Mac side exit without doing anything.

**Which Mac.** If `[jump] client` is set, that ssh target is the Mac (`local` means the server
itself), and nothing is detected. Otherwise Switchboard looks for it:

- if the herdr server is itself a Mac with a herdr window open, that machine is a candidate, and
  for it everything below runs locally instead of over ssh;
- it finds herdr's `remote-client-bridge` processes, the windows attached to this server from
  other machines, and takes each one's source address from the `SSH_CONNECTION` variable of its
  environment (`/proc/<pid>/environ` on Linux, `ps -E` on macOS); nothing else is kept from it;
- if a `tailscale` binary is installed, it runs `tailscale status --json` to put a name and an
  operating system on those addresses; Tailscale is never required;
- an address it cannot identify that way gets `ssh <address> uname -s`, to see whether it is a
  Mac;
- when more than one Mac qualifies, it runs `ioreg -c IOHIDSystem` on each one to read how long it
  has been idle, and picks the one touched last.

**What runs on that Mac.** Over ssh, with your keys and in batch mode:

- `herdr plugin list --json` (through `[remote] herdr`), to find where the plugin is installed
  there, unless `[jump] helper` gives the command;
- the plugin's own helper, `python3 <plugin directory>/bin/switchboard --jump-server`. It finds
  the terminal of the herdr window on that Mac (`ps`), starts `osascript`, and waits for one line
  with the chosen row; a line that is not exactly the nine string arguments it expects is
  dropped. Then it uses AppleScript to send keystrokes to the Ghostty terminal on that tty:
  herdr's prefix and navigator key (`[jump] prefix` and `goto`, by default `ctrl+b` and `g`,
  herdr's own defaults), `/` (which focuses the navigator's search), a query that matches only
  the chosen pane, and Enter. When no query matches only that pane, the helper gives the pane a
  unique name with `herdr pane rename` for a moment and restores the original name afterwards.
  Last, it asks herdr to focus that pane. These herdr commands run on the Mac with
  `--machine <label>`, the label the server knows the machine by (none when that label is the
  Mac's own name).

**What can be typed is a closed set.** Everything that ends up in the AppleScript is checked
whole against a fixed pattern, so nothing can leave its `text:` string or add a line break (an
extra Enter):

- `[jump] prefix` must be `ctrl+` and one lower-case letter, and `[jump] goto` must be `prefix+`
  and one key out of `a-z`, `0-9` and a few punctuation characters, or herdr's name for one of
  them; `config.example.toml` lists the set. A value outside it turns the jump off for that run
  (the popup's header says which value), and never falls back to other keys. The keys are
  checked when the config is read and again on the Mac, when the script is built.
- the query may hold only `a-z 0-9 : . _ -` and space, and the tty must look like `/dev/<name>`
  (ASCII letters, digits, `_` and `.`).

The helper checks all of that before it renames or types anything. When something is refused,
or there is no herdr window on that Mac, it renames nothing, types nothing, stops the waiting
`osascript` and only asks herdr to focus the pane. The server also sends the usual focus
through herdr's API, so if the keystrokes do not arrive the pane is still focused on its
machine.

This is the most sensitive part of the plugin, for two reasons. The herdr server must be able to
log in to your Mac over ssh, and anyone who controls the account that runs the herdr server can
then type into your terminal. And without `[jump] client`, the detection connects to addresses
it learned from the system, not from your herdr configuration. So:

- turn the jump on only when the server is as trusted as the Mac;
- **set `[jump] client`** to the Mac's ssh target, so the server connects to that host and
  nothing else;
- give the server a key of its own for this, and restrict it in the Mac's `authorized_keys`
  (for example with a `from=` option).

With the jump off (by `enabled = false` or by a refused key), or when anything it needs is
missing, Switchboard only focuses the pane through herdr on that pane's machine.

## Out of scope

- Vulnerabilities in herdr, fzf, OpenSSH, Ghostty or macOS themselves: please report them to
  those projects.
- Attacks that already require control of your user account, or of a machine you saved in
  herdr, beyond what that access already gives.
