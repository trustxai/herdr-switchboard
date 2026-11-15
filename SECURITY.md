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
`ssh` and through herdr. The cross-machine jump, which is on by default, adds what its own
section describes; with it off (`[jump] enabled = false`), the sections below up to the state
directory are everything it reaches outside its own process. All of it is the scope of this
policy.

### The programs it runs

`herdr` is the binary in `HERDR_BIN_PATH` (herdr sets it for plugin commands), or `herdr` on
`PATH`; `fzf` is found on `PATH`. So that a herdr server started without Homebrew's directories
still finds them, Switchboard appends `/opt/homebrew/bin`, `/home/linuxbrew/.linuxbrew/bin`,
`/usr/local/bin` and `~/.local/bin` to the end of its own `PATH` when they exist: they fill
gaps and never shadow what comes first. The helpers it starts (herdr, ssh, osascript and the
like) get `/dev/null` or one of its own pipes as their input, never the popup's terminal.

**What each child gets in its environment.** fzf gets the popup's environment plus
`SWITCHBOARD_RUN_DIR` (the run directory below, which its `--enter` and `--focus-wait` bindings
need) and `SWITCHBOARD_LABELS` (the machines' labels). fzf runs its commands through `sh -c`
(`--with-shell`): Switchboard itself with `--preview`, `--copy` (ctrl-y), `--select` (ctrl-o),
`--enter` (Enter, when other machines are saved) and `--focus-wait` (the
background footer `--enter` asks for); `cat` of the rows file, for each reload of the list; and
the ctrl-t query toggle, a `case` on `$FZF_QUERY`. All of them inherit fzf's environment,
including the `FZF_*` variables fzf exports, such as `FZF_SOCK`, a path inside the run
directory. Everything else Switchboard starts gets a cleaned copy of its environment:
without any `FZF_*` variable, without `SWITCHBOARD_RUN_DIR` and `SWITCHBOARD_RUN_FD`, and
without any other variable whose value contains the run directory's path. That covers herdr
(local, over ssh, or through `herdr --machine`), `ssh`, `ps`, `ioreg`, `tailscale`, `osascript`,
the jump's ssh connection to the Mac, the focus the popup sends after Enter, and the `--focus`
worker, which also gets `SWITCHBOARD_RUN_FD`, the number of the descriptor it inherits. The
check of the configured colours (`fzf --filter`) runs with the popup's own environment, which
holds no run directory.

### The local herdr

It reads the workspaces, tabs, panes and agents of the local herdr (`herdr api snapshot`), the
machines saved in it (`herdr machine list --json`; disabled ones are skipped), and the recent
output of a pane (`herdr pane read`) for the preview, `ctrl-y` and `ctrl-o`. The one change it
makes is focusing the pane you choose (`herdr agent focus`, or `herdr tab focus` for a plain
terminal). It does not create or close anything, and it renames nothing except, for a moment,
through the jump below.

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

With the jump off (`[jump] enabled = false`), it only reaches machines that are already saved in
herdr.

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
- `acks` and `focus-<pid>-<ms>` files, for Enter on another machine's row (below);
- `jump`, the state of the jump's connection to your Mac (`pending` or `ready`, one word), which
  `--enter` reads to decide whether Enter jumps (below);
- `closing`, an empty file the popup creates when it starts ending fzf on a signal (below).

The parts of Switchboard that use the directory after the popup has started open it once, check
that it is a real directory (not a symlink) owned by you with no access for group or others, and
from then on work only through that descriptor: files are created with `O_NOFOLLOW` and mode
0600, result files also with `O_EXCL`, and only regular files are read. The popup always removes
the directory when it closes, without waiting for a refresh still under way (a machine that does
not answer can take the whole remote timeout) or for the focus worker. The close starts when fzf
returns, or when a SIGHUP or SIGTERM arrives before that. From then on no rows write starts, so
fzf is asked for no further reload; one already under way finishes under a lock, and the popup
removes the directory once it holds that lock, or after two seconds without it (by then fzf is
gone, so a write's requests to it fail at once). A refresh that ends later cannot write anywhere
else: its writes go through the removed directory's descriptor and fail, and fzf's socket is
contacted only after such a write succeeded. Another process can still write into the directory
while it is being removed: the focus worker, whose result file (below) comes whenever its focus
is done. The last step of the removal then finds the directory not empty, so the popup repeats
the removal, for at most half a second, while the name is still that same directory (it keeps it
open, so a new directory under the same name cannot be taken for it); nothing in Switchboard
writes there for that long, and once the directory is gone nothing can be created in it any
more. A SIGHUP or SIGTERM that arrives once the close has started waits until the directory is
gone, then ends the popup with its usual status; from then on one ends it at once, also while a
message waits for Enter. In `--demo` the temporary state directory is removed when the popup
exits normally, and when a SIGHUP or SIGTERM that arrives at any moment from the directory's
creation on ends it: one that arrives while it is being created waits until its removal at exit
is in place, and one that cuts main's removal short has already turned SIGHUP and SIGTERM off,
so the removal runs again, whole, at exit. One that arrives once main's removal is done and the
popup is already exiting changes nothing: the removal at exit ignores SIGHUP and SIGTERM. Each
removal takes only the directory that process created, which it keeps open; a directory made
under the same name afterwards is left alone. A process killed with SIGKILL, or one that ends
without running its exit hooks, removes nothing. That includes a command `--demo` runs under
fzf, which has a state directory of its own: fzf kills with SIGKILL a preview it replaces and a
preview still running when fzf exits (on Esc or Enter), so a preview killed between creating its
state directory and removing it leaves that directory behind.

The popup also closes this way when its window or session goes away: SIGHUP and SIGTERM exit
through the same cleanup, which ends the popup's own fzf and removes the run directory (and, for
`--demo`, its temporary state directory, after which nothing writes there any more). fzf gets
SIGTERM, so it puts the terminal back (main screen, mouse off, echo), and up to two seconds to
leave. While fzf waits for a command it runs synchronously (`--copy` on ctrl-y, `--select` on
ctrl-o, `--enter`), it does not act on SIGTERM, and those commands share fzf's process group,
which fzf never kills. So if fzf is still there, every process below it, found by parent pid,
gets SIGTERM: the command leaves through its own cleanup, which ends its helpers, and fzf, back
from it, leaves as above. Only if fzf is still there two seconds later do everything below it
and fzf get SIGKILL. Whenever fzf did not leave on the first SIGTERM, whether it left after the
second step or was killed, the popup then also puts the terminal back itself (the settings it
saved before starting fzf, and the sequences that leave the alternate screen and turn the mouse
off). Ending fzf takes at most ten seconds: three waits of two seconds and two `ps` runs of up
to two seconds each. The removal of the run directory that follows adds at most two and a half
seconds (above). Before its first SIGTERM to fzf the popup creates `closing` in the run
directory, and a preview that fzf starts from then on reads nothing, nor does one that finds the
run directory already gone: the popup's search for what is below fzf may be over by then, and
fzf need not kill it on its way out. Only processes below the popup's fzf at that moment are
signalled; one that has already left that tree (its parent died) is not found, and a pid that
ends and is reused between the `ps` and the signal is the one exception. A second SIGHUP or
SIGTERM during that cleanup is ignored, so it finishes.

Which children get a session of their own. Every helper that goes through `run_child` does,
with its own process group, killed whole when its timeout passes and when the process that
started it exits, SIGHUP and SIGTERM included: herdr, ssh to the other machines and
`herdr --machine`, `ps`, `ioreg` and `tailscale` (the jump's lookups) and `fzf --version`. That
holds in the popup, `--rows`, `--copy`, `--select`, `--enter`, the focus worker and the jump's
helper. In `--preview` they stay instead in the preview's process group, which fzf kills with
SIGKILL only while that preview is still running (the cursor moves on, fzf exits). A helper that
times out there is killed with every process below it by parent pid, and so is one running when
the preview is told to stop; what still holds its output after that has left the tree (a daemon
whose parent exited): the preview waits for it two seconds at most, and it stays in the
preview's process group, which fzf kills only if the preview is still running then, so it can
outlive the preview and fzf until it ends by itself.

These are waited for, with a timeout, without a session of their own: the herdr that focuses a
row of this machine after Enter, the `fzf --filter` that checks the configured colours and, when
fzf refuses its command line (exit status 2), says why, the `ps` that lists what is below fzf or
below a preview's helper, and osascript in the jump's helper
(`--jump` and `--jump-server`). On a timeout, or an exit of the process waiting for it, that
child alone is killed. fzf runs in the popup's own process group and ends as described above.
Started and not waited for, each in a session of its own on purpose: the focus worker, the herdr
that focuses another machine's row after Enter, the jump's connection and its launch. A thread
of the popup reads the connection's output (its ready line, then until it ends); the popup's
close never waits for that thread, for the lookups that come before the connection, or for the
connection itself: after Enter it writes one line to the connection, or starts the launch.
`--enter` starts only the focus worker, and `--focus-wait` starts nothing. Nothing ends a helper in a
session of its own once the process that started it was killed with SIGKILL, which skips that
cleanup: it runs until it ends by itself (ssh's `ConnectTimeout=5` bounds only the connection,
not a remote herdr that stops answering).

### Enter on another machine's row

Enter on another machine's row runs `--enter`. It reads `jump` in the run directory (through the
checked descriptor, like everything there): when the jump is on and its connection says `ready`,
it lets fzf accept the row, the popup closes and the jump goes (next section). While the
connection is still `pending` it waits for it, two seconds at most. Otherwise, which is also
the case with the jump off, it records the row's tab as seen (one line in `acks`) and starts a
worker, `bin/switchboard --focus`, in a session of its own, so neither Esc nor
the popup closing can stop it. The worker runs the focus on that machine, by ssh or
`herdr --machine` as above, writes a one-line result file in the run directory, and exits. It
never receives the directory's path: it inherits a descriptor of it, opened and checked while
the popup still owned the directory; its environment is the cleaned one described under *The
programs it runs*, plus the descriptor's number; and its command line holds only the bare name
of its result file, which must match `focus-<digits>-<digits>`. If the popup has already removed
the directory, the worker writes nothing; the focus has happened all the same. In the popup, a
background fzf action waits for that file as long as the worker can take (its `herdr machine
list`, then ssh and `herdr --machine` with the remote timeout each, plus the waits after a
timeout: twice the remote timeout plus twelve seconds) and shows it in the footer.

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

### The cross-machine jump (on by default)

The jump is **on by default**. Choosing a pane on another machine then also switches your herdr
window to that machine. The window is driven from the Mac it runs on, so the machine where the
popup runs (the herdr server) connects back to that Mac over ssh, in batch mode, with the keys it
already has: it never asks for a password, so on a Mac it cannot log in to nothing happens beyond
the attempt. There, the helper sends keystrokes to Ghostty through AppleScript (below). When
there is at least one saved machine, that connection is opened as soon as the popup opens, so
Enter only has to send one line; Esc, or a row of the local machine, makes the Mac side exit
without doing anything.

**To turn it off**, put `enabled = false` under `[jump]` in the config. The popup then never looks
for the Mac of your window, never connects back to it for the jump and never types anything;
Enter on another machine's row only focuses the pane through herdr (see *Enter on another
machine's row* above).

The helper tells the popup when it is ready (one line on its output); until then, Enter takes the
focus path, and so it does when the helper never says so: no herdr window in Ghostty on that Mac,
herdr keys there that differ from `[jump]`'s (the helper says that instead, and the footer
repeats it), a Mac that cannot be reached, or a helper of an older version. The popup gives the
helper eight seconds from its start (ssh's `ConnectTimeout` plus three) to say either; after
that, Enter takes the focus path at once.

**Which Mac.** If `[jump] client` is set, that ssh target is the Mac (`local` means the server
itself), and nothing is detected. Otherwise Switchboard looks for it:

- if the herdr server is itself a Mac with a herdr window open in Ghostty, that machine is a
  candidate, and for it everything below runs locally instead of over ssh;
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
- the plugin's own helper, `python3 <plugin directory>/bin/switchboard --jump-server <keys>`,
  where `<keys>` is the text it would type to open the navigator (`[jump] prefix` and `goto`,
  then `/`, in the closed set below). It finds the terminal of a herdr window on that Mac that
  runs in Ghostty (`ps`: a herdr process with a terminal, no subcommand on its command line, and
  Ghostty among its parent processes; with several, the one whose terminal got input last, and
  none when that cannot be told). Without one it exits at once, starting nothing, so AppleScript
  is never pointed at a Ghostty that is not running or not installed. Then it reads that Mac's
  herdr config (`$HERDR_CONFIG_PATH`, else `$XDG_CONFIG_HOME/herdr/config.toml`, else
  `~/.config/herdr/config.toml`; only its `[keys] prefix` and `goto`, herdr's defaults when
  there is no file) and, when those are not `<keys>`, or the file cannot be read, says so and
  exits, starting nothing. Otherwise it starts `osascript`, prints that it is ready, and waits
  for one line with the chosen row; a line that is not exactly the nine string arguments it
  expects is dropped. Then
  it uses AppleScript to send keystrokes to the Ghostty terminal on that tty:
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

The helper checks all of that, and the keys against that Mac's herdr config again, before it
renames or types anything. When something is refused (or, for a jump started without the
waiting helper, there is no herdr window in Ghostty), it
renames nothing, types nothing, stops the waiting `osascript` and only asks herdr to focus the
pane. Once it has renamed the pane, the original name comes back and the focus is sent whatever
happens to the typing: `osascript` timing out
after 10 seconds (for example while macOS waits for an Automation permission), `osascript`
missing, or a SIGHUP or SIGTERM. The server also sends the usual focus through herdr's API, so
if the keystrokes do not arrive the pane is still focused on its machine.

This is the most sensitive part of the plugin, for two reasons. When the herdr server can log in
to your Mac over ssh, anyone who controls the account that runs the herdr server can then type
into your terminal. And without `[jump] client`, the detection connects to addresses it learned
from the system, not from your herdr configuration. So:

- keep the jump on only when the server is as trusted as the Mac; otherwise set
  `[jump] enabled = false`;
- **set `[jump] client`** to the Mac's ssh target, so the server connects to that host and
  nothing else;
- give the server a key of its own for this, and restrict it in the Mac's `authorized_keys`
  (for example with a `from=` option);
- set `[jump] prefix` and `goto` to your herdr `[keys] prefix` and `goto` when they are not
  herdr's defaults. The helper refuses to type when they differ from what it reads in that Mac's
  herdr config; if herdr reads its config from somewhere else there, keystrokes with the wrong
  keys land in the pane you are on, and the final Enter sends them there.

With the jump off (by `enabled = false` or by a refused key), or when anything it needs is
missing, Switchboard only focuses the pane through herdr on that pane's machine.

## Out of scope

- Vulnerabilities in herdr, fzf, OpenSSH, Ghostty or macOS themselves: please report them to
  those projects.
- Attacks that already require control of your user account, or of a machine you saved in
  herdr, beyond what that access already gives.
