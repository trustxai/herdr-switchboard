#!/usr/bin/env python3
"""Tests for bin/switchboard. Standard library only; prints "ok" or the failures.

What it has to get right, and how it fails otherwise:

1. The order is herdr's native agent panel with agent_panel_sort = "priority": blocked,
   done, working, idle, unknown, and inside a status the most recent change first.
   unknown never rises above idle, and a terminal without an agent never goes before an
   agent.
2. With the same status and no recorded changes, this machine goes before a remote one.
   With recorded changes, block 16 decides.
3. Enter on an agent is `agent focus`; on a terminal, `tab focus`. On another machine,
   the same focus with `--machine` (never a remote id against the local server: pane ids
   repeat across machines). The header and an offline machine do nothing.
4. Paths: the local home and a remote one (/home/x, /Users/x, /root) become ~;
   /homeless and /rootfs do not.
5. Columns are machine > workspace > tab > pane, as in herdr's Goto: an unnamed tab ("1")
   leaves the column empty unless the number was set by hand; the pane shows its name (from
   `pane rename` or the agent) or else its agent's title (never the shell's "user@host:~");
   in a split tab, with its number first.
6. The machine is always shown; the agent kind only when it is not claude. The selected
   row has a background.
7. End to end with a fake herdr: a machine that does not answer in time shows as offline
   and does not take the list down; a disabled machine is never asked.
8. The preview loses the agent's input box and status bar, and nothing else: a table with
   separators, an old box higher up or an indented text stay.
9. Live: no change, no reload; a change makes fzf reload the rows already written. A remote
   machine that stops answering keeps its last rows. With the cursor on the first row it
   stays there; further down, track-current keeps it on the same agent. The GET to fzf has
   no Content-Length (fzf rejects it even when 0).
10. Copy: from the Claude Code transcript when the session is on this machine (without the
   screen's line breaks); else the last "● …" block of the screen that is not a tool call;
   else what is visible. Never the transcript for another machine. ctrl-t toggles between
   only terminals and everything.
11. Jump to another machine: the window is found through remote-client-bridge processes
   (not the outgoing ssh the window itself opens) and only a Mac qualifies; with several,
   the one touched last. The window to type into is a herdr window with Ghostty among its
   ancestors (not another terminal, not tmux). The Goto query is the pane id only if no
   other row of any machine contains it; otherwise a temporary name. The AppleScript only
   carries [a-z0-9:._-]. Order: rename, keys, restore the name, API focus.
12. Select (ctrl-o): long lines wrap at the width without losing text, a column lands on
   its character with wide characters, the text between two points is the same dragging
   forward or back, and on release exactly that is copied over OSC 52 (in a pty, with a
   real SGR 1006 drag).
13. The fast jump: the connection to the window's Mac opens with the popup (ssh with
   ControlMaster) and Enter sends one JSON line; on the other side --jump-server already has
   the tty and an osascript running, and says so with one line, which is what makes the link
   ready. Without a herdr window in Ghostty it says nothing and starts nothing. No line (Esc,
   or a row of this machine) exits without jumping. The query tries the title before renaming.
14. No child reads the popup's terminal: every subprocess.run/Popen call states its stdin.
15. Another machine, fast: herdr_on goes over ssh reusing the connection (with --session
   when it is not the default) and falls back to `herdr --machine` when ssh fails or there
   is no target. On open, the last snapshot of each machine shows at once with its age in
   the header and is replaced when the fresh one arrives; a cache older than the limit is
   not shown.
16. Inside a status machines interleave: first the agent whose change was seen last,
   whatever machine (like the native client), not all of one machine and then the other.
   Re-reading without a seq change moves nothing, and the status still decides. The order
   survives between openings; what changed while closed rises on open, interleaved across
   machines. The cache is not a read, and an agent that left is removed only from its own
   machine (pane ids repeat across machines).
17. `done` is "finished and not seen", and the tool keeps that count itself. Stays done:
   what finished in the active tab of another machine, or in the tab you were on and left.
   Counts as seen: what is in front of you when the popup opens, what you pick with Enter,
   what the server turned from done to idle, and what finished outside the active tab and
   is already idle. An idle that closed no work never becomes done. The first time a
   machine is seen everything counts as seen, and so does a file from before the count.
18. Config: the file location, the built-in TOML subset parser against tomllib, defaults
   for a missing file, defaults plus one warning for a broken one, per-key type checks,
   and config.example.toml documenting every option.
19. State and binary: the snapshot cache and the recency ledger under
   HERDR_PLUGIN_STATE_DIR or the XDG fallback; herdr from HERDR_BIN_PATH or PATH.
20. Language: English by default, Spanish with lang = "es", one table with the same keys
   and placeholders in both, and no literal text handed to print or input.
21. Colours: the default uses the terminal's ANSI palette; the example theme still works.
22. Dependencies: a missing or old fzf, or an old Python, gives a message with the version
   found and how to install, and a non-zero exit.
23. Demo: the fixtures load and cover the promised day, --demo never touches herdr, ssh or
   the state directory, and the fixtures carry nothing personal.
24. The jump is on by default, and enabled = false turns it off. Enter on a remote row jumps
   only when the popup's link to the window's Mac is ready; otherwise (the jump off, no client
   found, a link still being set up past JUMP_ENTER_WAIT) it focuses the row through the API
   at once and keeps the popup open with a footer, as with the jump off. The popup's close
   never looks anything up or waits for the link. The client, Tailscale and the helper are
   optional, and anything missing falls back without an error. Every popup the tests start
   gets SWITCHBOARD_NO_JUMP, so none looks for a real herdr window or Mac.
25. The manifest: the declared contract, and its pane and action commands actually work.
26. ssh control sockets go only in a directory that is provably this user's: a directory
   someone else created first, a symlink, or one open to group or others is refused, and
   with no safe directory connections are simply not shared.
27. A config can never crash the program: wrong types, out-of-range or non-finite numbers and
   huge integers each fall back to their default with a warning, on both parsers, and even
   --version survives. Lines end only at \n, so a file reads the same with tomllib and with
   the built-in parser (U+2028 stays inside a comment, \v and \f are errors).
28. Colours are exactly what fzf accepts; the extra fzf entries are checked by the installed
   fzf before the popup opens, and if fzf still refuses its command line the popup says why
   and waits instead of vanishing.
29. Snapshot text is untrusted: a newline in a title cannot fabricate a row, escape sequences
   and control characters never reach fzf or the header, ids that could pass for options or
   break a row are dropped, wrong types do not crash, and the preview keeps colours only.
30. Every ssh call puts "--" before the destination, and a destination that starts with "-"
   or holds whitespace is refused wherever it comes from (config, Tailscale, a bridge address).
31. Enter on a remote row never blocks fzf: the footer changes at once and the focus runs in a
   background transform. An ack written while the popup consumes acks is never lost, and the
   watch loop survives the popup removing its directory on close.
32. A focus already asked for finishes even when the popup closes right after Enter, and the
   tab still counts as seen.
33. No malformed snapshot, of any type at any level, can kill a thread or print a traceback:
   snapshot() refuses it, the refresh paths treat it as no answer, --rows and the popup say
   what failed, and neither watch loop can die.
34. In the selection viewer an arrow key whose bytes arrive in two reads scrolls instead of
   closing the viewer, and a lone Esc still closes it.
35. Nothing that can outlive the popup writes or reads through a name another user could
   take over: the run directory is used only through a checked descriptor (ours, 0700),
   files are created new and never through a symlink, and the worker gets a descriptor,
   not the directory's path. A removed and recreated directory with planted links catches
   nothing.
36. --focus-wait waits as long as the worker can take (its herdr machine list, then ssh and
   herdr --machine with the remote timeout each, and the waits after a timeout), so the footer
   never says it failed before a slow focus lands.
37. A hung local herdr cannot freeze anything: the local snapshot has a timeout at open and in
   every refresh, the refresh keeps the last rows, and the popup says what failed.
38. Closing the popup always removes its run directory, whatever local_seconds is and however
   slow the local snapshot (without waiting for it), and also when its terminal goes away
   (SIGHUP); stop wakes the watch loop at once.
39. The detached worker checks again what it was handed: a result name that is not a plain
   focus-N-N (such as ../x) or a directory that is not ours and 0700 gets nothing written.
40. The selected row reads well: no gutter column, a pointer in the selected row's text colour,
   and only the glyph coloured, so the status word takes the selection's colour. ctrl-t still
   finds the terminals by their glyph.
41. The keys the jump types come from [jump] prefix and goto, herdr's defaults unless set, and
   are checked against closed character sets in the config, on the way and in the AppleScript.
53. What the program counts on from fzf, with the real fzf: only a preview (and a bg-transform)
   gets a process group of its own; --copy, --select and --enter run in fzf's own group, which
   fzf never kills; what a finished command left outlives fzf; and fzf acts on SIGTERM only once
   the command it waits for returns.
54. herdr_on_bound covers the worker's lookup, both reads and the waits after a kill, from the
   named timeouts, and --focus-wait waits that long.
55. Nothing the watch loop started writes into a directory while it is removed.
56. Reads started by the commands fzf runs end with them, with the real fzf: cursor moves and
   Esc, a preview read's timeout, and the popup told to leave (SIGTERM, SIGHUP) while --copy or
   --select waits, whether the popup leads its terminal's session or not: the command and its
   read end, the terminal comes back, and it is quick.
57. A read that times out leaves nothing holding its pipe, in each mode; a preview started once
   the popup is closing reads nothing; end_fzf's last step ends everything below fzf and nothing
   else, within its bound, and puts the terminal back.
58. A close never waits for a read that can hang: with a machine whose snapshot read hangs, Esc
   and Enter on a local row act at once, and a signal during a close never leaves the run
   directory behind. watch() does not wait for its remote reads, and once close_state() ran
   nothing more is written into the state directory.
59. No ps line the program matches is cut by $COLUMNS, which fzf sets for its commands: every
   ps it runs asks for whole lines.
60. The run directory goes also when another process (the focus worker) writes into it during
   the removal, and a directory made under the same name afterwards is left alone. Once a close
   by signal starts, no rows are written and fzf is asked for no reload.
61. --demo: a SIGTERM or SIGHUP at the message that waits for Enter ends the popup at once, and
   the temporary state directory goes on a normal exit and on a SIGHUP or SIGTERM at any moment
   from its creation, also when a signal cuts main's finally block short; a signal during the
   removal at exit cuts nothing short, and that removal never takes another directory made under
   the same name. The wait for Enter misses no signal, also one that lands just before it reads,
   and acts on it within one step of its select (WAIT_POLL), not only before a long timeout.

    python3 tests/test_switchboard.py
"""
import ast
import base64
import importlib.machinery
import importlib.util
import json
import os
import pathlib
import re
import shutil
import stat
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOOL = ROOT / "bin" / "switchboard"
sys.dont_write_bytecode = True

# Nothing of the user's leaks in: no config, no state, no overrides, no colours.
_tmp_root = tempfile.mkdtemp(prefix="switchboard-test-")
# The runtime directory holds ssh control sockets, and the program refuses one whose socket
# path would pass macOS's 104-byte limit. macOS's own temporary directory is long, so the
# runtime root is a short private directory under /tmp, removed at the end like the rest.
_run_root = tempfile.mkdtemp(prefix="sbt-", dir="/tmp")
import atexit as _atexit
_atexit.register(shutil.rmtree, _tmp_root, True)
_atexit.register(shutil.rmtree, _run_root, True)
for _k in list(os.environ):
    if _k.startswith("SWITCHBOARD_") or _k.startswith("HERDR_"):
        del os.environ[_k]
# HOME and the XDG directories too, the runtime one included (ssh control sockets go
# there): even a regression that ignores the plugin directories must not write outside.
os.environ.update(NO_COLOR="1", PYTHONDONTWRITEBYTECODE="1",
                  HOME=os.path.join(_tmp_root, "home"),
                  XDG_CONFIG_HOME=os.path.join(_tmp_root, "xdg-config"),
                  XDG_STATE_HOME=os.path.join(_tmp_root, "xdg-state"),
                  XDG_RUNTIME_DIR=_run_root,
                  HERDR_PLUGIN_CONFIG_DIR=os.path.join(_tmp_root, "config"),
                  HERDR_PLUGIN_STATE_DIR=os.path.join(_tmp_root, "state"))
os.makedirs(os.environ["HOME"])
os.chmod(_run_root, 0o700)
# The jump is on by default: a popup opens a link to the Mac of the herdr window, found among
# this machine's real processes (and, over ssh, the real Mac). No popup a test starts may do
# that, so each one gets SWITCHBOARD_NO_JUMP (read only where the popup opens the link; block 24
# drives the link in this process, with fakes).
os.environ["SWITCHBOARD_NO_JUMP"] = "1"

_socks = [0]


def short_sock(name):
    """A unix socket path under the short runtime root: a socket path is limited to about
    104 bytes, and TMPDIR can be far longer (macOS, CI runners)."""
    _socks[0] += 1
    return os.path.join(_run_root, "%s-%d.sock" % (name, _socks[0]))


loader = importlib.machinery.SourceFileLoader("switchboard", str(TOOL))
spec = importlib.util.spec_from_loader("switchboard", loader)
sb = importlib.util.module_from_spec(spec)
loader.exec_module(sb)
STATE = os.environ["HERDR_PLUGIN_STATE_DIR"]
SOURCE = TOOL.read_text()

FAILS = []


def check(name, cond, detail=""):
    if not cond:
        FAILS.append("%s %s" % (name, detail))


# A stuck test must fail, and say where, well inside CI's job timeout. Each block announces
# itself on stderr and gets BLOCK_LIMIT seconds; past that, faulthandler prints the stack of
# every thread (file, line, function: never a variable, so never the environment) and ends
# the process. stdout is block-buffered in CI, so nothing else would show where it stopped.
import faulthandler as _faulthandler
import select as _sel
import signal as _signal
import time as _time

BLOCK_LIMIT = 120.0
_T0 = _time.time()
_faulthandler.enable()


def block(name):
    sys.stderr.write("[%6.1f s] %s\n" % (_time.time() - _T0, name))
    sys.stderr.flush()
    _faulthandler.dump_traceback_later(BLOCK_LIMIT, exit=True)


block("setup")


def finish(pid, fd, timeout=10.0):
    """Wait for a child started with pty.fork, without ever blocking: returns its exit code,
    or None when it had to be killed.

    The terminal is read the whole time. An exiting session leader waits for its terminal's
    output to drain on macOS, and a program writing to a full terminal blocks: a wait that
    stops reading can wait forever. Past `timeout` the child's whole process group is
    killed (fzf included) and reaped within 5 s more. Whatever is left of the group after
    it exits is killed too, and fd is closed. fd may be None when the terminal is closed
    already."""
    end, killed, status = _time.time() + timeout, False, None
    while True:
        try:
            done, st = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            done, st = pid, 0
        if done:
            status = st
            break
        if _time.time() > end:
            if killed:
                break  # not reaped within 5 s of SIGKILL: give up rather than block
            for kill in (lambda: os.killpg(pid, _signal.SIGKILL), lambda: os.kill(pid, _signal.SIGKILL)):
                try:
                    kill()
                except OSError:
                    pass
            killed, end = True, _time.time() + 5
        try:
            r, _, _ = _sel.select([fd], [], [], 0.05) if fd is not None else ([], [], [])
            if fd is None or (r and not os.read(fd, 65536)):
                _time.sleep(0.05)
        except OSError:
            _time.sleep(0.05)
    try:
        os.killpg(pid, _signal.SIGKILL)  # what the child left in its group (an orphaned fzf)
    except OSError:
        pass
    if fd is not None:
        try:
            os.close(fd)
        except OSError:
            pass
    if killed or status is None:
        return None
    return os.waitstatus_to_exitcode(status)


def read_until(fd, pred, timeout):
    """Read fd into a buffer until pred(buffer) or timeout; returns the buffer. Never blocks."""
    buf, end = b"", _time.time() + timeout
    while _time.time() < end and not pred(buf):
        try:
            r, _, _ = _sel.select([fd], [], [], 0.05)
            if r:
                chunk = os.read(fd, 65536)
                if not chunk:
                    break
                buf += chunk
        except OSError:
            break
    return buf


def executable(path, text):
    path = pathlib.Path(path)
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


def snap(panes, agents, ws=None, tabs=None):
    return {
        "workspaces": ws or [{"workspace_id": "w1", "label": "Repo", "number": 1}],
        "tabs": tabs or [{"tab_id": "w1:t1", "label": "1", "number": 1, "workspace_id": "w1"}],
        "panes": panes,
        "agents": agents,
    }


def pane(pid, tab="w1:t1", title="", cwd="/tmp"):
    return {"pane_id": pid, "tab_id": tab, "workspace_id": "w1",
            "terminal_title_stripped": title, "cwd": cwd}


def agent(pid, status, seq, title="", tab="w1:t1"):
    return dict(pane(pid, tab, title), agent="claude", agent_status=status, state_change_seq=seq)


def order(entries):
    return [e["pane"] for e in sorted(entries, key=sb.sort_key)]


# Started here, checked in block 52: a remote read that spends the whole remote timeout on
# ssh and then most of it again on the `herdr --machine` fallback. It needs remote_timeout = 6
# s and about 12 s in all (a backstop as short as the old one, the timeout plus 5 s, gives up
# 0.6 s before the answer), so it runs while the rest of the suite does.
_late_dir = tempfile.mkdtemp(prefix="late-", dir=_tmp_root)
with open(os.path.join(_late_dir, "machines.json"), "w") as _f:
    json.dump([{"id": "m1", "label": "box1", "enabled": True, "target": "box1-host"}], _f)
with open(os.path.join(_late_dir, "local.json"), "w") as _f:
    json.dump({"result": {"snapshot": snap([pane("w1:p1")], [agent("w1:p1", "idle", 1, title="here-row")])}}, _f)
with open(os.path.join(_late_dir, "m1.json"), "w") as _f:
    json.dump({"result": {"snapshot": snap([pane("w1:p7")], [agent("w1:p7", "idle", 1, title="late-remote")])}}, _f)
# The ssh also leaves a child holding its output pipe, as a real one's helpers can: killing
# only the ssh would leave the read waiting on that pipe.
_late_ssh = executable(os.path.join(_late_dir, "ssh"), '#!/bin/sh\nsleep 300 &\necho $! > "%s/ssh-child.pid"\n'
                       'echo $$ > "%s/ssh.pid"\nexec sleep 300\n' % (_late_dir, _late_dir))


def _late_cleanup():
    """Whatever the late ssh left (only a regression leaves anything) goes when the suite ends."""
    for name in ("ssh.pid", "ssh-child.pid"):
        try:
            os.kill(int(open(os.path.join(_late_dir, name)).read()), _signal.SIGKILL)
        except (OSError, ValueError):
            pass


_atexit.register(_late_cleanup)
_late_herdr = executable(os.path.join(_late_dir, "herdr"),
                         '#!/bin/sh\ncase "$*" in\n  "machine list --json") cat "%(d)s/machines.json" ;;\n'
                         '  "api snapshot") cat "%(d)s/local.json" ;;\n'
                         '  "--machine m1 api snapshot") sleep 5.6; cat "%(d)s/m1.json" ;;\n'
                         '  *) exit 1 ;;\nesac\n' % {"d": _late_dir})
_late_t0 = _time.time()
_late = subprocess.Popen([sys.executable, str(TOOL), "--rows"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, universal_newlines=True, start_new_session=True,
                         env=dict(os.environ, HERDR_BIN_PATH=str(_late_herdr), SWITCHBOARD_SSH=str(_late_ssh),
                                  SWITCHBOARD_REMOTE_TIMEOUT="6", HERDR_PLUGIN_STATE_DIR=os.path.join(_late_dir, "state")))

# Also started here, checked in block 54: the --focus worker's worst case (a slow `herdr
# machine list`, an ssh that hangs and leaves its pipe held from another session, then a
# fallback that focuses), against --focus-wait's deadline. About 7.5 s with remote_timeout
# 1.5, beyond the old deadline (twice the timeout plus 3 s).
_slowfocus_dir = tempfile.mkdtemp(prefix="slowfocus-", dir=_tmp_root)
_slowfocus_run = os.path.join(_slowfocus_dir, "run")
os.mkdir(_slowfocus_run, 0o700)
with open(os.path.join(_slowfocus_dir, "machines.json"), "w") as _f:
    json.dump([{"id": "m1", "label": "box1", "enabled": True, "target": "box1-host"}], _f)
_slowfocus_ssh = executable(os.path.join(_slowfocus_dir, "ssh"),
                            '#!/bin/sh\n"%(py)s" -c "import os, time; os.setsid(); time.sleep(60)" &\n'
                            'echo $! > "%(d)s/holder.pid"\nexec sleep 60\n' % {"py": sys.executable, "d": _slowfocus_dir})
_slowfocus_herdr = executable(os.path.join(_slowfocus_dir, "herdr"),
                              '#!/bin/sh\ncase "$*" in\n  "machine list --json") sleep 2.6; cat "%(d)s/machines.json" ;;\n'
                              '  "--machine m1 agent focus w1:p1") sleep 1.2 ;;\n  *) exit 1 ;;\nesac\n'
                              % {"d": _slowfocus_dir})
_slowfocus_env = dict(os.environ, HERDR_BIN_PATH=str(_slowfocus_herdr), SWITCHBOARD_SSH=str(_slowfocus_ssh),
                      SWITCHBOARD_REMOTE_TIMEOUT="1.5", SWITCHBOARD_RUN_DIR=_slowfocus_run,
                      SWITCHBOARD_LABELS=json.dumps({"m1": "box1"}))
_slowfocus_enter = subprocess.run([sys.executable, str(TOOL), "--enter", "m1|a|w1:p1|w1:t1"], stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE, universal_newlines=True, env=_slowfocus_env, timeout=20).stdout
_slowfocus_name = re.search(r"--focus-wait (focus-[0-9]+-[0-9]+) ", _slowfocus_enter)
_slowfocus_wait = subprocess.Popen([sys.executable, str(TOOL), "--focus-wait",
                                    _slowfocus_name.group(1) if _slowfocus_name else "focus-0-0", "m1|a|w1:p1|w1:t1"],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                   universal_newlines=True, env=_slowfocus_env)


def _slowfocus_cleanup():
    try:
        os.kill(int(open(os.path.join(_slowfocus_dir, "holder.pid")).read()), _signal.SIGKILL)
    except (OSError, ValueError):
        pass


_atexit.register(_slowfocus_cleanup)

# 1. Priority.
block('1. Priority')
s = snap(
    panes=[pane(p) for p in ("idle", "unk", "blk", "done", "wrk", "sh", "idle2")],
    agents=[agent("idle", "idle", 10), agent("unk", "unknown", 99), agent("blk", "blocked", 1),
            agent("done", "done", 5), agent("wrk", "working", 7), agent("idle2", "idle", 20)],
)
got = order(sb.entries_from(s))
check("priority", got == ["blk", "done", "wrk", "idle2", "idle", "unk", "sh"], got)
check("unknown-stays-below-idle", got.index("unk") > got.index("idle"), got)
check("terminal-last", got[-1] == "sh", got)
weird = sb.entries_from(snap([pane("x")], [agent("x", "strange", 1)]))
check("unknown-status-is-unknown", weird[0]["status"] == "unknown", weird[0]["status"])

# 2. No history: local before remote with the same status; a remote blocked still beats a
# local done.
block('2. No history: local before remote with the same status; a remote blocked')
local = sb.entries_from(snap([pane("L")], [agent("L", "done", 1)]))
remote = sb.entries_from(snap([pane("R"), pane("RB")], [agent("R", "done", 999), agent("RB", "blocked", 1)]),
                         "m1", "box1", 1)
got = order(local + remote)
check("no-history-local-first", got == ["RB", "L", "R"], got)
term = sb.entries_from(snap([pane("T")], []))
runk = sb.entries_from(snap([pane("RU")], [agent("RU", "unknown", 0)]), "m1", "box1", 1)
got = order(term + runk)
check("local-terminal-after-remote-agent", got == ["RU", "T"], got)

# 3. Actions.
block('3. Actions')
labels = {"m1": "box1"}
check("enter-agent", sb.action_for(sb.make_id("", "a", "w1:p2", "w1:t1"), labels) == ["agent", "focus", "w1:p2"])
check("enter-terminal", sb.action_for(sb.make_id("", "t", "w1:p3", "w1:t4"), labels) == ["tab", "focus", "w1:t4"])
rem = sb.action_for(sb.make_id("m1", "a", "w1:p2", "w1:t1"), labels) or []
check("enter-remote-focuses-on-its-machine", rem == ["--machine", "m1", "agent", "focus", "w1:p2"], rem)
remt = sb.action_for(sb.make_id("m1", "t", "w1:p3", "w1:t4"), labels) or []
check("enter-remote-terminal", remt == ["--machine", "m1", "tab", "focus", "w1:t4"], remt)
check("enter-remote-no-notification", "notification" not in rem + remt)
check("enter-header", sb.action_for("-", labels) is None)
check("enter-broken-id", sb.action_for("m1|x|w1:p2|w1:t1", labels) is None)

# 4. Paths.
block('4. Paths')
home = os.path.expanduser("~")
check("tilde-local", sb.tilde(home + "/src/x", remote=False) == "~/src/x")
check("tilde-remote-linux", sb.tilde("/home/someone/src/x", remote=True) == "~/src/x")
check("tilde-remote-mac", sb.tilde("/Users/someone", remote=True) == "~")
check("tilde-not-homeless", sb.tilde("/homeless/x", remote=True) == "/homeless/x")
check("tilde-root", sb.tilde("/root/x", remote=True) == "~/x")
check("tilde-not-rootfs", sb.tilde("/rootfs/x", remote=True) == "/rootfs/x")
check("tilde-local-not-a-prefix", sb.tilde(home + "x/y", remote=False) == home + "x/y")

# 5. Columns: status, machine, workspace, tab, pane and the dimmed tail.
block('5. Columns: status, machine, workspace, tab, pane and the dimmed tail')
WIDTHS = (10, sb.MACHINE_WIDTH, 15, 26, 42)


def cols(e):
    row = sb.format_row(e).split("\t", 1)[1]
    out, pos = [], 0
    for w in WIDTHS:
        out.append(row[pos:pos + w].strip())
        pos += w + 1
    return out + [row[pos:].strip()]


def tab(label, custom=False):
    return [{"tab_id": "w1:t1", "label": label, "number": 1, "custom_label": custom}]


e = sb.entries_from(snap([pane("a")], [agent("a", "idle", 1, title="fix-login")]))[0]
c = cols(e)
check("unnamed-tab-shows-its-number", c[3] == "1" and c[4] == "fix-login" and c[5] == "/tmp", c)
c = cols(sb.entries_from(snap([pane("a")], [agent("a", "idle", 1, title="fix-login")], tabs=tab("Login")))[0])
check("named-tab", c[3] == "Login" and c[4] == "fix-login", c)
c = cols(sb.entries_from(snap([pane("a")], [agent("a", "idle", 1)], tabs=tab("2", custom=True)))[0])
check("numeric-tab-set-by-hand", c[3] == "2", c)

split = snap([pane("p1"), dict(pane("p2"), label="logs"), pane("p3")],
             [agent("p1", "idle", 1, title="t1"), dict(agent("p3", "idle", 1), name="rev")], tabs=tab("B"))
c1, c2, c3 = [cols(x) for x in sb.entries_from(split)]
check("pane-number-and-title", c1[4] == "1 · t1", c1)
check("pane-with-label", c2[4] == "2 · logs", c2)
check("pane-agent-name", c3[4] == "3 · rev", c3)
c = cols(sb.entries_from(snap([pane("solo")], [agent("solo", "idle", 1)], tabs=tab("B")))[0])
check("single-pane-no-number", c[4] == "", c)
c = cols(sb.entries_from(snap([pane("a")], [agent("a", "idle", 1, title="Login")], tabs=tab("Login")))[0])
check("title-equal-to-tab-not-repeated", c[4] == "" and c[5] == "/tmp", c)
c = cols(sb.entries_from(snap([pane("s", title="me@box1:~/x")], [], tabs=tab("B")))[0])
check("shell-title-is-not-a-name", c[4] == "", c)
c = cols(sb.entries_from(snap([pane("s1", title="me@box1:~/x"), pane("s2", title="btop")], [], tabs=tab("B")))[0])
check("shell-in-split-only-number", c[4] == "1", c)
c = cols(sb.entries_from(snap([pane("a")], [agent("a", "idle", 1)]), "m1", "workstation", 1)[0])
check("long-machine-name-fits", c[1] == "workstation", c)

# 6. The machine always; the agent kind only when it is not claude.
block('6. The machine always; the agent kind only when it is not claude')
e3 = sb.entries_from(snap([pane("a")], [agent("a", "idle", 1)]), "", "here", 0)[0]
check("machine-column-always", cols(e3)[1] == "here" and "here" in sb.render([e3], []))
check("claude-not-shown", "claude" not in cols(e3)[5], cols(e3))
cx = sb.entries_from(snap([pane("a")], [dict(agent("a", "idle", 1), agent="codex")]))[0]
check("other-kind-shown", "codex" in cols(cx)[5], cols(cx))

argv = sb.fzf_argv("fzf", "x", "/tmp/s.sock")
colors = dict(kv.split(":", 1) for kv in argv[argv.index("--color") + 1].split(","))
check("selected-row-has-background", colors.get("bg+") not in (None, "-1"), colors)

# 8. The preview without the agent's input box and status bar.
block("8. The preview without the agent's input box and status bar")
BOX = ["agent text", "last paragraph", "",
       "\x1b[2m" + "─" * 40 + " my-session ─\x1b[0m", "❯ \x1b[2mhalf typed\x1b[0m", "─" * 50,
       "  box1 | model | repo | ctx 15%", "  ⏵⏵ auto mode on"]
t = sb.trim_footer("\n".join(BOX))
check("trims-box", sb.ANSI.sub("", t).rstrip().endswith("last paragraph") and "auto mode" not in t, repr(t[-60:]))
hint = BOX[:2] + [" " * 60 + "new task? /clear to save 128k tokens"] + BOX[3:]
check("trims-right-aligned-hint", "new task" not in sb.trim_footer("\n".join(hint)))
table = ["| a | b |", "─" * 30, "| 1 | 2 |", "─" * 30, "end"]
check("table-untouched", sb.trim_footer("\n".join(table)) == "\n".join(table))
plain = "one\ntwo\nthree"
check("no-box-untouched", sb.trim_footer(plain) == plain)
far = BOX[3:6] + ["line %d" % i for i in range(30)]
check("old-box-higher-up-untouched", sb.trim_footer("\n".join(far)) == "\n".join(far))
check("normal-indent-stays", "  - (c) an item" in sb.trim_footer("\n".join(["  - (c) an item"] + BOX[3:])))

# 7. End to end, with a fake herdr.
block('7. End to end, with a fake herdr')
with tempfile.TemporaryDirectory() as d:
    d = pathlib.Path(d)
    (d / "local.json").write_text(json.dumps({"result": {"snapshot": snap([pane("w1:p1")], [agent("w1:p1", "working", 3)])}}))
    (d / "m1.json").write_text(json.dumps({"result": {"snapshot": snap([pane("w1:p1")], [agent("w1:p1", "blocked", 2)])}}))
    (d / "machines.json").write_text(json.dumps([
        {"id": "m1", "label": "alive", "enabled": True},
        {"id": "m2", "label": "hung", "enabled": True},
        {"id": "m3", "label": "disabled", "enabled": False},
    ]))
    fake = executable(d / "herdr",
                      "#!/bin/sh\n"
                      'case "$*" in\n'
                      '  "machine list --json") cat "%(d)s/machines.json" ;;\n'
                      '  "--machine m1 api snapshot") cat "%(d)s/m1.json" ;;\n'
                      '  "--machine m2 api snapshot") exec sleep 5 ;;\n'
                      '  "--machine m3 api snapshot") echo "must not be asked" >&2; exit 9 ;;\n'
                      '  "api snapshot") cat "%(d)s/local.json" ;;\n'
                      "  *) exit 2 ;;\n"
                      "esac\n" % {"d": d})
    env = dict(os.environ, HERDR_BIN_PATH=str(fake), SWITCHBOARD_REMOTE_TIMEOUT="1", SWITCHBOARD_LABEL="here")
    r = subprocess.run([sys.executable, str(TOOL), "--rows"], stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, universal_newlines=True, env=env, timeout=20)
    lines = r.stdout.splitlines()
    visible = [l.split("\t", 1)[1] for l in lines[1:]]
    check("e2e-rc", r.returncode == 0, r.stderr)
    check("e2e-header", lines and "2 agents" in lines[0] and "hung offline" in lines[0], lines[:1])
    check("e2e-remote-blocked-first", visible and re.match(r"● blocked\s+alive", visible[0]), visible)
    check("e2e-offline-last", visible and "hung" in visible[-1] and "offline" in visible[-1], visible)
    check("e2e-disabled-not-asked", "disabled" not in r.stdout and "must not" not in r.stderr)

# 9. Live.
block('9. Live')
import socket as _socket
import threading as _threading
import time as _time

data = {"local": snap([pane("w1:p1")], [agent("w1:p1", "working", 1)]),
        "m1": snap([pane("w1:p1")], [agent("w1:p1", "idle", 1)])}


def fake_fetch(machine="", timeout=None, info=None):
    v = data[machine or "local"]
    if v is None:
        raise RuntimeError("down")
    return v


machines = [{"id": "m1", "label": "other"}]
live = sb.Live(machines, sb.entries_from(fake_fetch(), "", "here", 0), fetch=fake_fetch)
first = live.changed()
check("live-loading", "loading other" in first, first.splitlines()[0])
check("live-no-change", live.changed() is None)
live.refresh_remote(0, machines[0])
check("live-remote-arrives", "other" in (live.changed() or "").split("\n", 1)[1])
data["m1"] = None
live.refresh_remote(0, machines[0])
check("live-down-keeps-rows", live.changed() is None and "offline" not in live.text())
live2 = sb.Live(machines, [], fetch=fake_fetch, cache=False)
live2.refresh_remote(0, machines[0])
check("live-never-answered", "other offline" in live2.text())
data["local"] = snap([pane("w1:p1")], [agent("w1:p1", "done", 2)])
live.refresh_local()
t = live.changed() or ""
check("live-status-change", "● done" in t, t[:200])

check("reload-top-no-track", not sb.reload_action("/tmp/r", 0).startswith("track-current"))
check("reload-unknown-no-track", not sb.reload_action("/tmp/r", None).startswith("track-current"))
check("reload-lower-tracks", sb.reload_action("/tmp/r", 3).startswith("track-current+reload-sync(cat /tmp/r)"))


class FakeFzf:
    """A fzf --listen on a unix socket: records each request and answers like fzf."""

    def __init__(self, path, position=0, status=b"200 OK"):
        self.reqs, self.position, self.status = [], position, status
        self.srv = _socket.socket(_socket.AF_UNIX)
        self.srv.bind(path)
        self.srv.listen(8)
        _threading.Thread(target=self.loop, daemon=True).start()

    def loop(self):
        while True:
            try:
                c, _ = self.srv.accept()
            except OSError:
                return
            raw = c.recv(65536)
            self.reqs.append(raw)
            if raw.startswith(b"GET") and b"Content-Length" in raw:
                body = b"invalid content length\n"
            elif raw.startswith(b"GET"):
                body = json.dumps({"position": self.position}).encode()
            else:
                body = b""
            c.sendall(b"HTTP/1.1 %s\r\nContent-Length: %d\r\n\r\n" % (self.status, len(body)) + body)
            c.close()


with tempfile.TemporaryDirectory(dir="/tmp") as d:
    sock = short_sock("f")
    fz = FakeFzf(sock, position=2)
    check("http-get-position", sb.fzf_position(sock) == 2)
    check("http-get-no-content-length", fz.reqs and b"Content-Length" not in fz.reqs[-1], fz.reqs[-1:])
    check("http-post", sb.fzf_request(sock, "POST", b"reload(x)") is not None
          and fz.reqs[-1].endswith(b"\r\n\r\nreload(x)") and b"Content-Length: 9" in fz.reqs[-1])
    check("http-no-fzf", sb.fzf_position(short_sock("missing")) is None)

    # watch() end to end: a change sends a reload, no change sends nothing.
    sb.LOCAL_EVERY, sb.REMOTE_EVERY = 0.05, 0.05
    data.update(local=snap([pane("w1:p1")], [agent("w1:p1", "working", 1)]),
                m1=snap([pane("w1:p1")], [agent("w1:p1", "idle", 1)]))
    # The first rows as a local pass renders them, with this machine's label: otherwise the
    # first local pass is a change of its own, and when the other machine answers after it (a
    # slow runner) fzf gets two reloads.
    lv = sb.Live(machines, sb.entries_from(fake_fetch(), "", sb.local_label(), 0), fetch=fake_fetch)
    lv.changed()
    rows_file, stop = os.path.join(d, "rows"), _threading.Event()
    w9a = _threading.Thread(target=sb.watch, args=(lv, sock, rows_file, stop), daemon=True)
    w9a.start()
    _time.sleep(0.5)
    posts = [r for r in fz.reqs if r.startswith(b"POST") and b"reload-sync" in r]
    check("watch-reloads-when-remote-arrives", len(posts) == 1, len(posts))
    check("watch-tracks-when-lower", posts and b"track-current+reload-sync(cat " in posts[-1])
    check("watch-rows-are-live-text", os.path.exists(rows_file) and open(rows_file).read() == lv.text())
    _time.sleep(0.3)
    check("watch-no-change-no-reload", len([r for r in fz.reqs if b"reload-sync" in r]) == 1)
    data["local"] = snap([pane("w1:p1")], [agent("w1:p1", "done", 2)])
    _time.sleep(0.4)
    check("watch-reloads-on-change", len([r for r in fz.reqs if b"reload-sync" in r]) == 2)
    stop.set()
    w9a.join(5)  # each watch loop is done before its directory goes
    # With a slow local tick (5 s), a machine arriving still reloads at once.
    _time.sleep(0.2)
    sb.LOCAL_EVERY, sb.REMOTE_EVERY = 5.0, 5.0
    data["m1"] = snap([pane("w1:p9")], [agent("w1:p9", "blocked", 9)])
    lv2 = sb.Live(machines, sb.entries_from(fake_fetch(), "", "here", 0), fetch=fake_fetch, cache=False)
    lv2.changed()
    before = len([r for r in fz.reqs if b"reload-sync" in r])
    stop2 = _threading.Event()
    w9b = _threading.Thread(target=sb.watch, args=(lv2, sock, os.path.join(d, "rows2"), stop2), daemon=True)
    w9b.start()
    _time.sleep(0.6)
    check("watch-remote-reloads-now", len([r for r in fz.reqs if b"reload-sync" in r]) > before)
    stop2.set()
    w9b.join(5)
    check("watch-loops-done-before-the-directory-goes", not w9a.is_alive() and not w9b.is_alive())
    sb.LOCAL_EVERY, sb.REMOTE_EVERY = 0.05, 0.05

# A change that happens before fzf opens --listen (a machine that answers at once) reaches
# fzf as soon as it listens, even if nothing changes again; and a reload fzf refuses counts
# as not sent.
with tempfile.TemporaryDirectory(dir="/tmp") as d:
    sock = short_sock("refuses")
    FakeFzf(sock, status=b"400 Bad Request")
    check("http-refused-is-not-sent", sb.fzf_request(sock, "POST", b"reload(x)") is None)
    late = short_sock("late")
    sb.LOCAL_EVERY, sb.REMOTE_EVERY = 0.1, 0.1
    data.update(local=snap([pane("w1:p1")], [agent("w1:p1", "working", 1)]),
                m1=snap([pane("w1:p1")], [agent("w1:p1", "idle", 1)]))
    lv = sb.Live(machines, sb.entries_from(fake_fetch(), "", "here", 0), fetch=fake_fetch, cache=False)
    lv.changed()  # what fzf gets on its stdin: the other machine still loading
    stop = _threading.Event()
    t = _threading.Thread(target=sb.watch, args=(lv, late, os.path.join(d, "rows"), stop), daemon=True)
    t.start()
    _time.sleep(0.6)  # the other machine answered, and passes ran with nobody listening
    fz = FakeFzf(late)
    _time.sleep(0.6)
    posts = [r for r in fz.reqs if r.startswith(b"POST") and b"reload-sync" in r]
    check("watch-sends-what-fzf-missed", len(posts) == 1 and "loading" not in open(os.path.join(d, "rows")).read(),
          len(posts))
    _time.sleep(0.4)
    check("watch-sends-it-only-once", len([r for r in fz.reqs if b"reload-sync" in r]) == 1)
    stop.set()
    t.join(3)
    sb.LOCAL_EVERY, sb.REMOTE_EVERY = 0.05, 0.05

# 10. Copy and terminals.
block('10. Copy and terminals')
argv = sb.fzf_argv("fzf", "self", "/tmp/s.sock")
joined = " ".join(argv)
check("preview-half", "down,50%" in joined, joined)
check("ctrl-y-copies", "ctrl-y:transform-footer(self --copy {1})" in argv, argv)
check("ctrl-t-terminals", any(a.startswith("ctrl-t:transform-query:") for a in argv))
check("posix-shell", "--with-shell" in argv and argv[argv.index("--with-shell") + 1] == "sh -c")
for q, want in (("", "^› "), ("api", "^› "), ("^› ", ""), ("^› docs", "")):
    out = subprocess.run(["sh", "-c", sb.TOGGLE_TERMINALS], env=dict(os.environ, FZF_QUERY=q),
                         stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, universal_newlines=True, timeout=20).stdout
    check("toggle-terminals %r" % q, out == want, repr(out))
check("terminal-glyph-own", sb.MARK["shell"][1] != sb.MARK["unknown"][1])
check("footer-cleared-on-move", "focus:change-footer()" in argv and not any("prefix+w" in a for a in argv), argv)

with tempfile.TemporaryDirectory() as d:
    tr_path = os.path.join(d, "t.jsonl")

    def entry(mid, kind, text="", side=False, typ="assistant"):
        c = {"type": kind, "text": text} if kind == "text" else {"type": kind}
        return json.dumps({"type": typ, "isSidechain": side, "message": {"id": mid, "content": [c]}})
    with open(tr_path, "w") as f:
        f.write("\n".join(["{broken", entry("m1", "text", "old"), entry("m2", "text", "first part"),
                           entry("m2", "tool_use"), entry("m2", "text", "second part"),
                           entry("m3", "text", "from a subagent", side=True),
                           entry("m4", "thinking"), entry("u", "text", "from the user", typ="user")]) + "\n")
    got = sb.last_reply_from_transcript(tr_path)
    check("transcript-last-reply", got == "first part\n\nsecond part", repr(got))
    check("transcript-missing", sb.last_reply_from_transcript(os.path.join(d, "no")) is None)
    raw = open(tr_path, "rb").read()
    tail = len(raw) - raw.index(entry("m2", "text", "second part").encode()) + 10  # 10 bytes into the line before
    got = sb.last_reply_from_transcript(tr_path, tail_bytes=tail)
    check("transcript-from-the-middle", got == "second part", repr(got))

screen = "\n".join(["● An old reply", "", "● New reply, line 1", "  line 2", "  - an item", "",
                    "● Bash(ls)", "  ⎿  output", "", "✻ Baked for 3m", "※ recap: something"])
got = sb.last_reply_from_screen(screen)
check("screen-skips-tool", got == "New reply, line 1\nline 2\n- an item", repr(got))
check("screen-no-block", sb.last_reply_from_screen("just\ntext") is None)
check("osc52", sb.osc52("hola ñ") == "\x1b]52;c;aG9sYSDDsQ==\x07", repr(sb.osc52("hola ñ")))

with tempfile.TemporaryDirectory() as d:
    d = pathlib.Path(d)
    sid = "0123abcd-0000-4000-8000-000000000001"
    (d / ".claude" / "projects" / "-repo").mkdir(parents=True)
    (d / ".claude" / "projects" / "-repo" / (sid + ".jsonl")).write_text(
        json.dumps({"type": "assistant", "message": {"id": "m", "content": [{"type": "text", "text": "from the transcript"}]}}) + "\n")
    a1 = dict(agent("w1:p1", "done", 1), agent_session={"value": sid})
    (d / "snap.json").write_text(json.dumps({"result": {"snapshot": snap([pane("w1:p1")], [a1])}}))
    (d / "screen.txt").write_text("● from the screen\n\n✻ Baked for 1m\n")
    fake = executable(d / "herdr", '#!/bin/sh\ncase "$*" in\n  "api snapshot") cat "%(d)s/snap.json" ;;\n'
                                   '  *"pane read"*) echo "$*" >> "%(d)s/reads"; cat "%(d)s/screen.txt" ;;\n  *) exit 2 ;;\nesac\n' % {"d": d})
    tty = d / "tty"

    def run_copy(row):
        env = dict(os.environ, HOME=str(d), HERDR_BIN_PATH=str(fake), SWITCHBOARD_TTY=str(tty))
        r = subprocess.run([sys.executable, str(TOOL), "--copy", row], stdout=subprocess.PIPE,
                           universal_newlines=True, env=env, timeout=20)
        raw = tty.read_text() if tty.exists() else ""
        return r.stdout.strip(), (base64.b64decode(raw.split(";")[2].rstrip("\x07")).decode() if raw else "")

    out, txt = run_copy(sb.make_id("", "a", "w1:p1", "w1:t1"))
    check("copy-local-from-transcript", txt == "from the transcript" and "last reply" in out, (out, txt))
    out, txt = run_copy(sb.make_id("m1", "a", "w1:p1", "w1:t1"))
    check("copy-remote-from-screen", txt == "from the screen" and "screen" in out, (out, txt))
    check("copy-remote-asks-its-machine", (d / "reads").exists() and "--machine m1" in (d / "reads").read_text())
    out, txt = run_copy("-")
    check("copy-header-nothing", out == "", out)

# 11. Jump to another machine.
block('11. Jump to another machine')
PS = "\n".join([
    " 367912 /usr/local/bin/herdr remote-client-bridge --idle-timeout-v1",
    " 97790 ssh -C -T box1 exec /usr/local/bin/herdr remote-client-bridge --idle-timeout-v1",
    " 400001 /opt/homebrew/bin/herdr remote-client-bridge --idle-timeout-v1",
    " 500 /opt/homebrew/bin/herdr server",
])
orig_origin = sb.ssh_origin
sb.ssh_origin = lambda pid: {367912: "addr-1", 97790: "addr-3", 400001: "addr-2"}.get(pid)
got = sb.client_bridges(PS)
check("bridges-not-outgoing-ssh", got == [(367912, "addr-1"), (400001, "addr-2")], got)
sb.ssh_origin = orig_origin
HOSTS = {"addr-1": ("mac1", "macOS"), "addr-2": ("mac2", "macOS"), "addr-9": ("box1", "linux")}
check("client-one-mac", sb.find_client([(1, "addr-1")], HOSTS, "", platform="linux") == ("ssh", "mac1"))
check("client-linux-does-not-qualify", sb.find_client([(1, "addr-9")], HOSTS, "", platform="linux") is None)
check("client-nothing", sb.find_client([], HOSTS, "", platform="linux") is None)
check("client-local", sb.find_client([], HOSTS, "/dev/ttys000", platform="darwin") == ("local", None))
idle = {None: 900.0, "mac1": 0.4, "mac2": 50.0}
got = sb.find_client([(1, "addr-2"), (2, "addr-1")], HOSTS, "/dev/ttys000", idle=idle.get, platform="darwin")
check("client-touched-last", got == ("ssh", "mac1"), got)
idle2 = {None: 0.2, "mac1": 30.0}
check("client-local-when-touched", sb.find_client([(2, "addr-1")], HOSTS, "/dev/ttys000", idle=idle2.get,
                                                   platform="darwin") == ("local", None))
# A herdr window in Ghostty and its ancestors, as `ps -axo pid=,ppid=,tty=,command=` prints them.
TUI = "\n".join([
    "    1     0 ??       /sbin/launchd",
    "  700     1 ??       /Applications/Ghostty.app/Contents/MacOS/ghostty",
    "  701   700 ttys000  /usr/bin/login -flp user /bin/zsh",
    "  702   701 ttys000  -zsh",
    " 7000   702 ttys000  /opt/homebrew/bin/herdr agent list",
    "60526   702 ttys000  /opt/homebrew/bin/herdr",
    "96578     1 ??       /opt/homebrew/bin/herdr server",
])
check("tty-of-the-window", sb.ghostty_tty(TUI) == "/dev/ttys000", sb.ghostty_tty(TUI))
# The same window in another terminal, or inside tmux (its server hangs from launchd), or
# with no window at all: nothing to type into.
other = TUI.replace("/Applications/Ghostty.app/Contents/MacOS/ghostty",
                    "/System/Applications/Utilities/Terminal.app/Contents/MacOS/Terminal")
check("tty-window-in-another-terminal", sb.ghostty_tty(other) is None, sb.ghostty_tty(other))
in_tmux = "\n".join(TUI.splitlines()[:4] + ["  703   702 ttys000  tmux", "  800     1 ??       tmux",
                                             "  801   800 ttys001  -zsh",
                                             "60526   801 ttys001  /opt/homebrew/bin/herdr"])
check("tty-window-inside-tmux", sb.ghostty_tty(in_tmux) is None, sb.ghostty_tty(in_tmux))
check("tty-no-window", sb.ghostty_tty("  700 1 ??  /Applications/Ghostty.app/Contents/MacOS/ghostty\n"
                                      "96578 700 ??  /opt/homebrew/bin/herdr server") is None)
check("tty-parent-loop-ends", sb.ghostty_tty("5 6 ttys000 /opt/homebrew/bin/herdr\n6 5 ttys000 -zsh") is None)
# A window is herdr with options only; a subcommand anywhere makes it a CLI call.
check("herdr-window-words", sb.herdr_window(["herdr"]) and sb.herdr_window("/x/herdr --remote server --handoff".split())
      and sb.herdr_window("herdr --session work".split()) and not sb.herdr_window(["herdr", "server"])
      and not sb.herdr_window("herdr --machine server agent list".split()) and not sb.herdr_window(["zsh"]))
# A one-off `herdr --machine server agent list` in a Ghostty tab is not a window...
cli_call = ["  720   700 ttys002  /usr/bin/login -flp user /bin/zsh", "  721   720 ttys002  -zsh",
            "  722   721 ttys002  /opt/homebrew/bin/herdr --machine server agent list"]
cli_only = "\n".join(TUI.splitlines()[:4] + cli_call)
check("tty-cli-call-is-not-a-window", sb.ghostty_tty(cli_only, atime=lambda t: 1.0) is None, sb.ghostty_tty(cli_only))
check("tty-window-beside-a-cli-call", sb.ghostty_tty(TUI + "\n" + "\n".join(cli_call), atime=lambda t: 1.0)
      == "/dev/ttys000", sb.ghostty_tty(TUI + "\n" + "\n".join(cli_call), atime=lambda t: 1.0))
# ...and with two windows in Ghostty the jump goes to the one whose terminal got input last
# (the newer process here, so not simply the lowest pid), or to none when that cannot be told.
two = "\n".join(TUI.splitlines() + ["  710   700 ttys001  /usr/bin/login -flp user /bin/zsh",
                                    "  711   710 ttys001  -zsh",
                                    "70000   711 ttys001  /opt/homebrew/bin/herdr --remote server"])
typed = {"/dev/ttys000": 100.0, "/dev/ttys001": 200.0}
check("tty-two-windows-the-one-typed-into-last", sb.ghostty_tty(two, atime=typed.get) == "/dev/ttys001"
      and sb.ghostty_tty(two, atime={"/dev/ttys000": 300.0, "/dev/ttys001": 200.0}.get) == "/dev/ttys000",
      sb.ghostty_tty(two, atime=typed.get))
# The window process comes along: its environment and arguments decide its keys (block 41).
check("window-process-of-the-tty", sb.ghostty_window(two, atime=typed.get) == (70000, "/dev/ttys001",
                                                                             ["/opt/homebrew/bin/herdr", "--remote", "server"]))
# `herdr session attach <name>` is a window too, and --remote-keybindings takes a value.
attach = "\n".join(TUI.splitlines()[:4] + ["  730   702 ttys000  /opt/homebrew/bin/herdr session attach work"])
check("tty-session-attach-is-a-window", sb.ghostty_tty(attach) == "/dev/ttys000"
      and sb.herdr_window("herdr --remote server --remote-keybindings server".split())
      and sb.herdr_window("herdr --remote server --remote-keybindings=local".split())
      and not sb.herdr_window("herdr session list".split()) and not sb.herdr_window("herdr session attach".split()),
      sb.ghostty_tty(attach))
check("server-keybindings-seen", sb.server_keybindings("herdr --remote s --remote-keybindings server".split())
      and sb.server_keybindings("herdr --remote-keybindings=server".split())
      and not sb.server_keybindings("herdr --remote-keybindings local".split()) and not sb.server_keybindings(["herdr"]))
check("tty-two-windows-ambiguous-is-none", sb.ghostty_tty(two, atime=lambda t: 100.0) is None
      and sb.ghostty_tty(two, atime=lambda t: None) is None and sb.ghostty_tty(two, atime={"/dev/ttys000": 1.0}.get) is None)


def ent(machine, pane_id, **kw):
    e = {"machine": machine, "pane": pane_id, "ws_label": "Repo", "tab_auto": "1", "title": "", "cwd": "~/x",
         "pane_name": "", "agent": "claude", "pane_label": ""}
    e.update(kw)
    return e


ents = [ent("", "w3:p19"), ent("m1", "w3:p1D"), ent("m1", "w1:p1"), ent("m2", "w1:p1")]
check("goto-unique-id", sb.goto_query({"pane": "w3:p1D"}, ents) == "w3:p1d")
check("goto-repeated-id", sb.goto_query({"pane": "w1:p1"}, ents) is None)
check("goto-id-inside-another", sb.goto_query({"pane": "w3:p1"}, ents + [ent("m1", "w3:p1")]) is None)
check("goto-id-in-a-title", sb.goto_query({"pane": "w3:p1D"}, ents + [ent("", "w9:p2", title="see W3:P1D")]) is None)
scr = sb.ghostty_keys_script("/dev/ttys000", "w3:p1d", "\\x02//")
check("applescript-one-burst", 'tty is "/dev/ttys000"' in scr and scr.count("perform action") == 1
      and '"text:\\\\x02//w3:p1d\\\\r"' in scr and "delay" not in scr, scr)
for bad in (("/dev/ttys000", 'x" & do shell script "rm'), ("/dev/tty; rm", "w1:p1"), ("/dev/ttys000", "W1:P1")):
    try:
        sb.ghostty_keys_script(*bad)
        check("applescript-rejects %r" % (bad,), False)
    except ValueError:
        pass

calls = []
orig = (sb.run_out, sb.ghostty_window, sb.window_keys_match, sb.subprocess.run, sb.time.sleep, sb.local_label)
sb.run_out = lambda argv, timeout=5: calls.append(("herdr", argv[1:])) or ""
sb.ghostty_window = lambda ps_text=None, atime=None: (60526, "/dev/ttys000", ["herdr"])
sb.window_keys_match = lambda keys, window, env_of=None: True  # its own checks are in block 41
sb.subprocess.run = lambda argv, **kw: calls.append(("osa", argv[0])) or None
sb.time.sleep = lambda s: None
sb.local_label = lambda: "mac1"
try:
    sb.jump("box1", "a", "w1:p1", "w1:t1", "sbjabc", True, "")
    seq = [c[0] + ":" + " ".join(c[1]) if c[0] == "herdr" else "osa" for c in calls]
    check("jump-order", seq == ["herdr:--machine box1 pane rename w1:p1 sbjabc", "osa",
                                "herdr:--machine box1 pane rename w1:p1 --clear",
                                "herdr:--machine box1 agent focus w1:p1"], seq)
    calls.clear()
    sb.jump("mac1", "t", "w2:p3", "w2:t4", "w2:p3", False, "")
    seq = [c[0] + ":" + " ".join(c[1]) if c[0] == "herdr" else "osa" for c in calls]
    check("jump-local-no-rename", seq == ["osa", "herdr:tab focus w2:t4"], seq)
    calls.clear()
    sb.jump("box1", "a", "w1:p1", "w1:t1", "sbjabc", True, "logs")
    check("jump-restores-the-name", ("herdr", ["--machine", "box1", "pane", "rename", "w1:p1", "logs"]) in calls, calls)
finally:
    sb.run_out, sb.ghostty_window, sb.window_keys_match, sb.subprocess.run, sb.time.sleep, sb.local_label = orig

args = sb.jump_argv({"machine": "m1", "kind": "a", "pane": "w1:p1", "tab": "w1:t1"}, "box1",
                    ents[:3] + [ent("m2", "w1:p1", pane_label="logs")])
check("jump-argv-renames-when-repeated", args[6] == "1" and args[5].startswith("sbj")
      and args[:5] == ["--jump", "box1", "a", "w1:p1", "w1:t1"], args)
check("jump-argv-name-of-that-machine", args[7] == "", args)
check("jump-argv-carries-the-keys", len(args) == 9 and args[8] == sb.JUMP_KEYS, args)
popen = []
orig_popen = sb.subprocess.Popen
sb.subprocess.Popen = lambda argv, **kw: popen.append((argv, kw))
try:
    launched = sb.launch_jump(["--jump", "box1", "a", "w1:p1", "w1:t1", "w1:p1", "0", ""], ("ssh", "mac1"),
                              helper="python3 /opt/sb/bin/switchboard")
finally:
    sb.subprocess.Popen = orig_popen
argv, kw = popen[0]
check("launches-over-ssh-detached", launched and argv[0] == sb.SSH and "mac1" in argv and kw.get("start_new_session")
      and argv[-1].startswith("python3 /opt/sb/bin/switchboard --jump box1 a w1:p1"), argv)

# 12. Select with the mouse.
block('12. Select with the mouse')
rows = sb.wrap_rows(["abcdefghij", "", "xy"], 4)
check("wrap", rows == [(0, 0, 4), (0, 4, 8), (0, 8, 10), (1, 0, 0), (2, 0, 2)], rows)
check("wrap-wide", sb.wrap_rows(["a中b"], 3) == [(0, 0, 2), (0, 2, 3)], sb.wrap_rows(["a中b"], 3))
check("col-wide", [sb.col_to_index("a中b", 0, 3, c) for c in range(4)] == [0, 1, 1, 2])
L = ["first line here", "second", "third line here"]
check("sel-one-line", sb.selected_text(L, (0, 6), (0, 9)) == "line")
check("sel-several", sb.selected_text(L, (0, 6), (2, 4)) == "line here\nsecond\nthird")
check("sel-backwards", sb.selected_text(L, (2, 4), (0, 6)) == sb.selected_text(L, (0, 6), (2, 4)))
S = sb.Selector(L, 20, 4)
check("starts-at-bottom", S.top == 0 and S.view == 3)
S.mouse(0, 7, 1, False)
S.mouse(32, 10, 1, False)
check("drag-does-not-copy", S.mouse(32, 10, 1, False) is None and S.anchor == (0, 6))
check("release-copies", S.mouse(0, 10, 1, True) == "line")
S2 = sb.Selector(["a"] * 30, 20, 6)
before = S2.top
S2.mouse(64, 1, 1, False)
check("wheel-up", S2.top == before - 3, (before, S2.top))
S2.mouse(0, 1, 1, False)
check("click-copies-one-char", S2.mouse(0, 1, 1, True) == "a")
S3 = sb.Selector(["   ", "x"], 20, 4)
S3.mouse(0, 1, 1, False)
check("only-spaces-not-copied", S3.mouse(0, 3, 1, True) is None)
check("frame-inverts-selection", "\x1b[7mline" in S.frame())

import pty as _pty
with tempfile.TemporaryDirectory() as d:
    d = pathlib.Path(d)
    (d / "pane.txt").write_text("hello world\nsecond line of the agent\n")
    fake = executable(d / "herdr", '#!/bin/sh\ncat "%s/pane.txt"\n' % d)
    pid, fd = _pty.fork()
    if pid == 0:
        os.environ.update(HERDR_BIN_PATH=str(fake), TERM="xterm-256color")
        os.execv(sys.executable, [sys.executable, "-B", str(TOOL), "--select", "|a|w1:p1|w1:t1"])
    import fcntl as _f
    import struct as _st
    import termios as _tm
    _f.ioctl(fd, _tm.TIOCSWINSZ, _st.pack("HHHH", 10, 40, 0, 0))
    out = b""

    def pump(sec):
        global out
        end = _time.time() + sec
        while _time.time() < end:
            r, _, _ = _sel.select([fd], [], [], 0.05)
            if r:
                try:
                    out += os.read(fd, 65536)
                except OSError:
                    return
    pump(1.0)
    # Less text than screen, at the top: "hello world" on row 1, the other on row 2.
    os.write(fd, b"\x1b[<0;7;1M")
    pump(0.1)
    os.write(fd, b"\x1b[<32;6;2M")
    pump(0.1)
    os.write(fd, b"\x1b[<0;6;2m")
    pump(0.5)
    os.write(fd, b"\x1b")
    pump(0.6)
    done, st = os.waitpid(pid, os.WNOHANG)
    finish(pid, fd, 5)
    m = re.search(rb"\x1b\]52;c;([A-Za-z0-9+/=]+)\x07", out)
    copied = base64.b64decode(m.group(1)).decode() if m else None
    check("pty-copies-the-drag", copied == "world\nsecond", repr(copied))
    check("pty-exits-on-esc", done == pid)
    check("pty-restores-the-terminal", out.rstrip().endswith(b"\x1b[?1049l") or b"\x1b[?1006l" in out[-200:])

# 13. The fast jump.
block('13. The fast jump')
ents2 = [ent("m1", "w1:p1", title="Plugin docs"), ent("m2", "w1:p1", title="something else"),
         ent("m1", "w2:p2", title="Fix (deploy)"), ent("m2", "w2:p2", title="x")]
check("goto-title-when-id-repeats", sb.goto_query({"machine": "m1", "pane": "w1:p1"}, ents2) == "plugin docs",
      sb.goto_query({"machine": "m1", "pane": "w1:p1"}, ents2))
check("goto-odd-title-no", sb.goto_query({"machine": "m1", "pane": "w2:p2"}, ents2) is None)
ents3 = ents2 + [ent("m3", "w9:p9", ws_label="plugin docs")]
check("goto-title-found-in-a-workspace-no", sb.goto_query({"machine": "m1", "pane": "w1:p1"}, ents3) is None)

import io as _io

with tempfile.TemporaryDirectory() as d:
    d = pathlib.Path(d)
    # The helper on the Mac, over ssh: it says it can type, then takes one line.
    fake_ssh = executable(d / "ssh", '#!/bin/sh\nprintf "%%s\\n" "$*" > "%s/argv"\necho %s\ncat > "%s/stdin"\n'
                          % (d, sb.JUMP_READY, d))
    old_ssh = sb.SSH
    sb.SSH = str(fake_ssh)
    run13 = tempfile.mkdtemp(dir=str(d))
    os.chmod(run13, 0o700)
    fd13 = sb.open_private_dir(run13)

    def state13(want, seconds=5.0):
        end = _time.time() + seconds
        while sb.jump_state(fd13) != want and _time.time() < end:
            _time.sleep(0.02)
        return sb.jump_state(fd13)

    link = sb.JumpLink(find=lambda: ("ssh", "mac1"), helper=lambda host: "sb-helper").start(run13)
    args = ["--jump", "box1", "a", "w1:p1", "w1:t1", "w1:p1", "0", ""]
    check("link-up-on-the-ready-line", link.up.wait(5))
    ready13 = state13("ready")
    check("link-sends", link.send(args))
    link.proc.wait(5)
    # The state --enter reads: ready once the helper said so, gone once the helper ended.
    check("link-state-ready-then-gone", ready13 == "ready" and state13("") == "", (ready13, sb.jump_state(fd13)))
    os.close(fd13)
    argv = (d / "argv").read_text()
    # The keys it will type go to the helper, which checks them against the window's herdr.
    check("link-ssh-with-controlmaster", "ControlMaster=auto" in argv and "ControlPersist=600" in argv
          and argv.strip().endswith("sb-helper --jump-server " + sb.shlex.quote(sb.JUMP_KEYS)) and "mac1" in argv, argv)
    check("link-one-json-line", json.loads((d / "stdin").read_text()) == args, (d / "stdin").read_text())
    # A helper that ends without the ready line (an older one, or no herdr window in Ghostty
    # there): the link is never up, and nothing is sent.
    executable(d / "ssh", '#!/bin/sh\necho "a profile line"\ncat > "%s/stdin2"\n' % d)
    silent = sb.JumpLink(find=lambda: ("ssh", "mac1"), helper=lambda host: "sb-helper").start()
    silent.started.wait(5)
    silent.close()
    if silent.proc:
        silent.proc.wait(5)
    check("link-not-up-without-the-ready-line", not silent.up.is_set() and silent.send(args) is False
          and silent.jump(args) is False, silent.proc)
    sb.SSH = old_ssh
    nolink = sb.JumpLink(find=lambda: None).start()
    nolink.started.wait(5)
    check("link-no-client", nolink.send(args) is False and nolink.jump(args) is False)
    calls2 = []
    orig_popen = sb.subprocess.Popen

    class P:
        def __init__(self, argv, **kw):
            calls2.append(argv)
            self.stdin, self.stdout = None, _io.BytesIO(b"")

        def poll(self):
            return None
    sb.subprocess.Popen = P
    try:
        sb.JumpLink(find=lambda: ("local", None)).start().started.wait(2)
    finally:
        sb.subprocess.Popen = orig_popen
    check("link-local-no-ssh", calls2 and calls2[0][-2:] == ["--jump-server", sb.JUMP_KEYS]
          and calls2[0][0] == sys.executable, calls2)

got_jump = []
killed = []
osas = []


class FakeOsa:
    def __init__(self):
        osas.append(self)

    def kill(self):
        killed.append(1)


orig = (sb.jump, sb.ghostty_window, sb.window_env, sb.herdr_config_check, sb.subprocess.Popen)
WIN13 = (60526, "/dev/ttys000", ["/opt/homebrew/bin/herdr"])
sb.jump = lambda *a, **kw: got_jump.append((a, kw)) or 0
sb.ghostty_window = lambda ps_text=None, atime=None: WIN13
sb.herdr_config_check = lambda path: True  # its own checks are in block 41
sb.subprocess.Popen = lambda argv, **kw: FakeOsa()
keys_dir = tempfile.mkdtemp(dir=_tmp_root)
os.mkdir(os.path.join(keys_dir, "home"))
herdr_cfg = os.path.join(keys_dir, "config.toml")
with open(herdr_cfg, "w") as f:
    f.write('[keys]\ngoto = "prefix+/"\n\n[[keys.command]]\nkey = "prefix+space"\ntype = "plugin_action"\n')
sb.window_env = lambda pid: {"HERDR_CONFIG_PATH": herdr_cfg} if pid == WIN13[0] else None
try:
    said = _io.StringIO()
    sb.jump_server(_io.StringIO(json.dumps(["--jump", "box1", "a", "w1:p1", "w1:t1", "w1:p1", "1", "logs", "\\x02//"])
                                + "\n"), said, keys="\\x02//")
    check("server-says-it-is-ready", said.getvalue() == sb.JUMP_READY + "\n", said.getvalue())
    check("server-jumps-with-what-is-ready", got_jump and got_jump[0][0] == ("box1", "a", "w1:p1", "w1:t1", "w1:p1", True, "logs")
          and got_jump[0][1].get("tty") == "/dev/ttys000" and isinstance(got_jump[0][1].get("osa"), FakeOsa)
          and got_jump[0][1].get("keys") == "\\x02//", got_jump)
    # A line whose keys it did not check (an older popup passes none): jump() gets no tty and
    # finds and checks the window itself.
    got_jump.clear()
    sb.jump_server(_io.StringIO(json.dumps(["--jump", "box1", "a", "w1:p1", "w1:t1", "w1:p1", "1", "logs", "\\x02//"])
                                + "\n"), _io.StringIO())
    check("server-unchecked-keys-go-to-jump-without-the-tty", got_jump and "tty" not in got_jump[0][1]
          and "osa" not in got_jump[0][1], got_jump)
    got_jump.clear()
    sb.jump_server(_io.StringIO(""), _io.StringIO(), keys="\\x02//")
    check("server-no-line-no-jump", not got_jump and killed, (got_jump, killed))
    killed.clear()
    sb.jump_server(_io.StringIO("not json\n"), _io.StringIO(), keys="\\x02//")
    check("server-broken-line-no-jump", not got_jump and killed)
    # No herdr window in Ghostty on this Mac: it says nothing, starts no osascript and reads no
    # line, so the popup's Enter takes the focus path.
    sb.ghostty_window = lambda ps_text=None, atime=None: None
    said, line, osas[:] = _io.StringIO(), _io.StringIO(json.dumps(["--jump"] * 9) + "\n"), []
    rc = sb.jump_server(line, said, keys="\\x02//")
    check("server-without-a-window-says-nothing", rc == 0 and said.getvalue() == "" and not osas
          and line.tell() == 0 and not got_jump, (rc, said.getvalue(), osas, line.tell()))
    # The keys the popup will type (--jump-server KEYS) against the window's herdr config, found
    # from the window's own environment: when they match it says it is ready; when they differ it
    # says so instead, starts no osascript and reads no line, and the popup's Enter takes the
    # focus path. No config file (the window's HOME without one): herdr's defaults.
    sb.ghostty_window = lambda ps_text=None, atime=None: WIN13
    told = {}
    for name, keys, env in (("match", "\\x02//", {"HERDR_CONFIG_PATH": herdr_cfg}),
                            ("goto", "\\x02g/", {"HERDR_CONFIG_PATH": herdr_cfg}),
                            ("prefix", "\\x01//", {"HERDR_CONFIG_PATH": herdr_cfg}),
                            ("none", "\\x02g/", {"HOME": os.path.join(keys_dir, "home")}),
                            ("none-differs", "\\x02//", {"HOME": os.path.join(keys_dir, "home")})):
        sb.window_env = lambda pid, env=env: env
        said, line, osas[:], got_jump[:] = _io.StringIO(), _io.StringIO(json.dumps(["--jump"] * 9) + "\n"), [], []
        sb.jump_server(line, said, keys=keys)
        told[name] = (said.getvalue().strip(), len(osas), line.tell() > 0)
    check("server-ready-when-the-keys-match", told["match"] == (sb.JUMP_READY, 1, True)
          and told["none"] == (sb.JUMP_READY, 1, True), told)
    check("server-says-the-keys-differ", all(told[k] == (sb.JUMP_KEYS_DIFFER, 0, False)
                                             for k in ("goto", "prefix", "none-differs")), told)
    check("main-hands-the-keys-to-the-helper", "return jump_server(keys=argv[1] if len(argv) > 1 else None)" in SOURCE)
finally:
    sb.jump, sb.ghostty_window, sb.window_env, sb.herdr_config_check, sb.subprocess.Popen = orig

# 14. No child reads the popup's terminal.
block("14. No child reads the popup's terminal")
tree = ast.parse(SOURCE)
no_stdin = []
for node in ast.walk(tree):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr in ("run", "Popen") and getattr(node.func.value, "id", "") == "subprocess":
        if not any(k.arg == "stdin" for k in node.keywords):
            no_stdin.append(node.lineno)
check("every-child-states-its-stdin", not no_stdin, "lines without stdin: %s" % no_stdin)

# 15. Another machine, fast.
block('15. Another machine, fast')
with tempfile.TemporaryDirectory() as d:
    d = pathlib.Path(d)
    calls_ssh = d / "ssh-calls"
    fake_ssh = executable(d / "ssh", '#!/bin/sh\nfor last; do :; done\necho "$last" >> "%s"\nexec sh -c "$last"\n' % calls_ssh)
    remote_herdr = executable(d / "remote-herdr", '#!/bin/sh\necho "{\\"result\\":{\\"snapshot\\":{\\"via\\":\\"ssh $*\\"}}}"\n')
    local_herdr = executable(d / "herdr", '#!/bin/sh\necho "{\\"result\\":{\\"snapshot\\":{\\"via\\":\\"herdr $*\\"}}}"\n')
    saved = (sb.SSH, sb.REMOTE_HERDR, sb.HERDR)
    sb.SSH, sb.REMOTE_HERDR, sb.HERDR = str(fake_ssh), str(remote_herdr), str(local_herdr)
    try:
        got = sb.snapshot("m1", 5, {"id": "m1", "target": "mac1", "session": "default"})
        check("remote-over-ssh", got.get("via") == "ssh api snapshot", got)
        got = sb.snapshot("m1", 5, {"id": "m1", "target": "mac1", "session": "agents"})
        check("remote-with-session", got.get("via") == "ssh --session agents api snapshot", got)
        sb.SSH = "/bin/false"
        got = sb.snapshot("m1", 5, {"id": "m1", "target": "mac1"})
        check("remote-falls-back-to-machine", got.get("via") == "herdr --machine m1 api snapshot", got)
        sb.SSH = str(fake_ssh)
        got = sb.snapshot("m1", 5, {"id": "m1"})
        check("remote-no-target", got.get("via") == "herdr --machine m1 api snapshot", got)
        got = sb.snapshot("", 5)
        check("local-direct", got.get("via") == "herdr api snapshot", got)
    finally:
        sb.SSH, sb.REMOTE_HERDR, sb.HERDR = saved

    sb.STATE_DIR = str(d / "state")
    msnap = snap([pane("w1:p1")], [agent("w1:p1", "done", 4, title="from-cache")])
    sb.save_cache("m1", msnap, now=1000.0)
    check("cache-reads", sb.load_cache("m1", now=1040.0) == (msnap, 40.0))
    check("cache-too-old", sb.load_cache("m1", now=1000.0 + sb.CACHE_MAX_AGE + 1) is None)
    check("cache-none", sb.load_cache("other") is None)
    sb.save_cache("m1", msnap)
    fresh = snap([pane("w1:p1")], [agent("w1:p1", "working", 5, title="fresh")])
    lv = sb.Live([{"id": "m1", "label": "other"}], [], fetch=lambda m="", t=None, i=None: fresh)
    first = lv.changed()
    check("cache-on-open", "from-cache" in first and "other from" in first.split("\n", 1)[0], first[:200])
    lv.refresh_remote(0, {"id": "m1", "label": "other"})
    t2 = lv.changed() or ""
    check("fresh-replaces", "fresh" in t2 and " ago" not in t2.split("\n", 1)[0], t2[:200])
    check("fresh-is-saved", sb.load_cache("m1")[0] == fresh)
    sb.STATE_DIR = STATE


# 16. The order across machines.
block('16. The order across machines')
def ents16(machine, idx, *ags):
    """The entries of a machine with those agents: (pane, status, seq[, title])."""
    return sb.entries_from(snap([pane(a[0]) for a in ags], [agent(*a) for a in ags]),
                           machine, machine or "here", idx)


rc = sb.Recency(persist=False, now=1000.0)
loc = ents16("", 0, ("L1", "idle", 5), ("L2", "idle", 9))
rem = ents16("m1", 1, ("R1", "idle", 3), ("R2", "idle", 7))
rc.observe("", loc)
rc.observe("m1", rem, now=1000.4)  # arrives later, but it is its first read
got = order(loc + rem)
check("recency-on-open-interleaves", got == ["L2", "R2", "L1", "R1"], got)
rem = ents16("m1", 1, ("R1", "idle", 8), ("R2", "idle", 7))  # R1 changed and is still idle
check("recency-sees-the-change", rc.observe("m1", rem, now=1005.0) is True)
got = order(loc + rem)
check("recency-remote-first", got == ["R1", "L2", "R2", "L1"], got)
loc = ents16("", 0, ("L1", "idle", 10), ("L2", "idle", 9))
rc.observe("", loc, now=1006.0)
got = order(loc + rem)
check("recency-local-first", got == ["L1", "R1", "L2", "R2"], got)
check("recency-no-change-no-record", rc.observe("", loc, now=2000.0) is False)
got = order(loc + rem)
check("recency-no-change-no-move", got == ["L1", "R1", "L2", "R2"], got)
old = dict(ents16("m1", 1, ("RD", "done", 1))[0], stamp=1.0, rank=0)
got = order(loc + rem + [old])
check("recency-status-decides", got[0] == "RD", got)
rp = sb.Recency(persist=False, now=10.0)
rp.observe("", ents16("", 0, ("X", "idle", 1)))
rp.observe("m1", ents16("m1", 1, ("X", "idle", 1), ("Y", "idle", 2)))
check("recency-prune-records", rp.observe("m1", ents16("m1", 1, ("Y", "idle", 2)), now=11.0) is True)
check("recency-prune-only-its-machine", "X" not in rp.seen["m1"] and "X" in rp.seen[""], rp.seen)

with tempfile.TemporaryDirectory() as d:
    sb.STATE_DIR = d
    r1 = sb.Recency(now=1000.0)
    r1.observe("", ents16("", 0, ("L1", "idle", 5), ("L2", "idle", 9)))
    r1.observe("m1", ents16("m1", 1, ("R1", "idle", 3), ("R2", "idle", 7)))
    r1.observe("m1", ents16("m1", 1, ("R1", "idle", 8), ("R2", "idle", 7)), now=1005.0)
    check("recency-writes", os.path.exists(os.path.join(d, "recency.json")))
    r2 = sb.Recency(now=2000.0)
    loc = r2.apply(ents16("", 0, ("L1", "idle", 5), ("L2", "idle", 9)))
    rem = r2.apply(ents16("m1", 1, ("R1", "idle", 8), ("R2", "idle", 7)))
    got = order(loc + rem)
    check("recency-persists", got == ["R1", "L2", "R2", "L1"], got)
    check("recency-reopen-no-record", r2.observe("", loc) is False and r2.observe("m1", rem) is False)
    # While closed, L1 changed here and R2 there: they rise, interleaved.
    r3 = sb.Recency(now=3000.0)
    loc = ents16("", 0, ("L1", "idle", 6), ("L2", "idle", 9))
    rem = ents16("m1", 1, ("R1", "idle", 8), ("R2", "idle", 11))
    r3.observe("", loc)
    r3.observe("m1", rem, now=3000.5)
    got = order(loc + rem)
    check("recency-closed-rises", got == ["L1", "R2", "R1", "L2"], got)
    with open(os.path.join(d, "recency.json"), "w") as f:
        f.write("{not json")
    check("recency-broken-file", sb.Recency().seen == {})

    # In the popup: the cache carries its order but is not a read.
    m1 = [{"id": "m1", "label": "other"}]
    vivid = {"local": snap([pane("w1:p1")], [agent("w1:p1", "idle", 1, title="here-one")]),
             "m1": snap([pane("w1:p1")], [agent("w1:p1", "idle", 1, title="other-one")])}

    def fetch16(machine="", timeout=None, info=None):
        return vivid[machine or "local"]

    sb.save_cache("m1", vivid["m1"])
    lv = sb.Live(m1, sb.entries_from(fetch16(), "", "here", 0), fetch=fetch16)
    check("recency-cache-is-not-a-read", "m1" not in lv.recency.fresh and "" in lv.recency.fresh)
    lv.refresh_remote(0, m1[0])
    t = lv.text()
    check("recency-live-tie-local", t.index("here-one") < t.index("other-one"), t)
    vivid["m1"] = snap([pane("w1:p1")], [agent("w1:p1", "idle", 2, title="other-one")])
    lv.refresh_remote(0, m1[0])
    t = lv.text()
    check("recency-live-remote-rises", t.index("other-one") < t.index("here-one"), t)
    vivid["local"] = snap([pane("w1:p1")], [agent("w1:p1", "idle", 2, title="here-one")])
    lv.refresh_local()
    t = lv.text()
    check("recency-live-local-rises", t.index("here-one") < t.index("other-one"), t)
    sb.STATE_DIR = STATE

# 17. done: finished and not seen.
block('17. done: finished and not seen')
T1, T2 = "w1:t1", "w1:t2"
TABS17 = [{"tab_id": T1, "label": "one", "number": 1, "workspace_id": "w1"},
          {"tab_id": T2, "label": "two", "number": 2, "workspace_id": "w1"}]


def ag17(pid, status, seq, tab=T1, compl=None):
    a = agent(pid, status, seq, tab=tab)
    if compl is not None:
        a["completion_seq"] = compl
    return a


def snap17(focus, *ags):
    s = snap([pane(a["pane_id"], a["tab_id"]) for a in ags], list(ags), tabs=TABS17)
    s["focused_tab_id"] = focus
    return s


def ents17(machine, idx, *ags):
    return sb.entries_from(snap17(None, *ags), machine, machine or "here", idx)


def st(entries):
    return {e["pane"]: e["status"] for e in entries}


rd = sb.Recency(persist=False, now=100.0)
e = ents17("m1", 1, ag17("A", "idle", 5, T1, 5))
rd.observe("m1", e, focus=T1)
check("done-first-time-all-seen", st(e) == {"A": "idle"}, st(e))
# Another machine: A finishes in the tab left open there (the server says idle) and B in
# another tab that is already idle (someone went there).
rd = sb.Recency(persist=False, now=100.0)
rd.observe("m1", ents17("m1", 1, ag17("A", "working", 5, T1), ag17("B", "working", 6, T2)), focus=T1)
e = ents17("m1", 1, ag17("A", "idle", 7, T1, 7), ag17("B", "idle", 8, T2, 8))
rd.observe("m1", e, now=105.0, focus=T1)
check("done-finished-in-the-open-tab-of-another", st(e) == {"A": "done", "B": "idle"}, st(e))
check("done-counted-in-the-header", "1 done" in sb.header(e, [], [], []), sb.header(e, [], [], []))
e = ents17("m1", 1, ag17("A", "idle", 7, T1, 7), ag17("B", "idle", 8, T2, 8))
check("done-stays-without-changes", rd.observe("m1", e, now=110.0, focus=T1) is False and st(e)["A"] == "done", st(e))
check("done-enter-other-machine-no", rd.ack_tab("", T1, e) is False and st(rd.apply(e))["A"] == "done")
check("done-enter-other-tab-no", rd.ack_tab("m1", T2, e) is False and st(rd.apply(e))["A"] == "done")
check("done-enter-marks-seen", rd.ack_tab("m1", T1, e) is True and st(rd.apply(e))["A"] == "idle", st(e))
# The server had it done and turns it idle: you went there some other way.
rd = sb.Recency(persist=False, now=100.0)
rd.observe("m1", ents17("m1", 1, ag17("C", "working", 1, T2)), focus=T1)
e = ents17("m1", 1, ag17("C", "done", 2, T2, 2))
rd.observe("m1", e, now=101.0, focus=T1)
check("done-from-the-server-respected", st(e) == {"C": "done"}, st(e))
e = ents17("m1", 1, ag17("C", "idle", 2, T2, 2))
rd.observe("m1", e, now=102.0, focus=T1)
check("done-server-turned-it-idle", st(e) == {"C": "idle"}, st(e))
# On the popup's machine: what is in front of you counts as seen.
rd = sb.Recency(persist=False, now=100.0)
rd.observe("", ents17("", 0, ag17("L", "working", 1, T1)), focus=T1, here=True)
e = ents17("", 0, ag17("L", "idle", 2, T1, 2))
rd.observe("", e, now=101.0, focus=T1, here=True)
check("done-in-front-of-you-no", st(e) == {"L": "idle"}, st(e))
# Finished in the tab you were on and left: done until you open the popup there.
rd = sb.Recency(persist=False, now=100.0)
rd.observe("", ents17("", 0, ag17("L", "working", 1, T1)), focus=T1, here=True)
e = ents17("", 0, ag17("L", "idle", 2, T1, 2))
rd.observe("", e, now=101.0, focus=T2, here=True)
check("done-you-left-the-tab", st(e) == {"L": "done"}, st(e))
e = ents17("", 0, ag17("L", "idle", 2, T1, 2))
rd.observe("", e, now=102.0, focus=T1, here=True)
check("done-back-on-the-tab", st(e) == {"L": "idle"}, st(e))
# An idle that closed no work does not rise; working and blocked do not change.
rd = sb.Recency(persist=False, now=100.0)
rd.observe("m1", ents17("m1", 1, ag17("N", "working", 1, T1), ag17("O", "working", 2, T1),
                         ag17("W", "idle", 3, T1), ag17("X", "idle", 4, T1)), focus=T1)
e = ents17("m1", 1, ag17("N", "idle", 5, T1), ag17("O", "idle", 6, T1, 4),
           ag17("W", "working", 7, T1, 3), ag17("X", "blocked", 8, T1))
rd.observe("m1", e, now=101.0, focus=T1)
check("done-only-when-it-closed-work", st(e) == {"N": "idle", "O": "idle", "W": "working", "X": "blocked"}, st(e))

with tempfile.TemporaryDirectory() as d:
    sb.STATE_DIR = d
    r1 = sb.Recency(now=100.0)
    r1.observe("m1", ents17("m1", 1, ag17("A", "working", 5, T1)), focus=T1)
    r1.observe("m1", ents17("m1", 1, ag17("A", "idle", 7, T1, 7)), now=105.0, focus=T1)
    e = ents17("m1", 1, ag17("A", "idle", 7, T1, 7))
    r2 = sb.Recency(now=200.0)
    check("done-persists-in-the-ledger", st(r2.apply(e)) == {"A": "done"}, st(e))
    r2.observe("m1", e, focus=T1)
    check("done-persists-on-reread", st(e) == {"A": "done"}, st(e))
    r2.ack_tab("m1", T1, e)
    check("done-seen-persists", st(sb.Recency(now=300.0).apply(e)) == {"A": "idle"}, st(e))
    with open(os.path.join(d, "recency.json"), "w") as f:
        json.dump({"v": 1, "machines": {"m1": {"A": [7, 100.0, 0]}}}, f)
    r3 = sb.Recency(now=400.0)
    e = ents17("m1", 1, ag17("A", "idle", 7, T1, 7))
    r3.observe("m1", e, focus=T1)
    check("done-old-file-all-seen", st(e) == {"A": "idle"}, st(e))

    # In the popup: the other machine finishes something in its open tab and it shows done on top.
    os.remove(os.path.join(d, "recency.json"))
    m1 = [{"id": "m1", "label": "other"}]
    vivid = {"local": snap17(T1, ag17("p1", "working", 1, T1)),
             "m1": snap17(T1, ag17("p9", "working", 1, T1))}

    def fetch17(machine="", timeout=None, info=None):
        return vivid[machine or "local"]

    lv = sb.Live(m1, sb.entries_from(fetch17(), "", "here", 0), fetch=fetch17, focus=T1)
    lv.refresh_remote(0, m1[0])
    vivid["m1"] = snap17(T1, ag17("p9", "idle", 2, T1, 2))
    vivid["local"] = snap17(T1, ag17("p1", "idle", 2, T1, 2))
    lv.refresh_remote(0, m1[0])
    lv.refresh_local()
    rows = lv.text().splitlines()
    check("done-live-remote-on-top", "1 done" in rows[0] and rows[1].startswith("m1|a|p9|") and "● done" in rows[1]
          and rows[2].startswith("|a|p1|") and "○ idle" in rows[2], rows[:3])
    lv.recency.ack_tab("m1", T1, lv.entries())
    with lv.lock:
        lv.recency.apply(lv.remote["m1"])
    check("done-live-enter-clears-it", "done" not in lv.text().split("\n", 1)[1], lv.text())
    sb.STATE_DIR = STATE

check("done-enter-acks", "live.recency.ack_tab(target[\"machine\"], target[\"tab\"], live.entries())" in SOURCE)

# 18. Config.
block('18. Config')
check("config-path-plugin-dir", sb.config_path({"HERDR_PLUGIN_CONFIG_DIR": "/x"}) == "/x/config.toml")
check("config-path-xdg", sb.config_path({"XDG_CONFIG_HOME": "/y", "HOME": "/h"}) == "/y/herdr-switchboard/config.toml")
check("config-path-home", sb.config_path({"HOME": "/h"}) == "/h/.config/herdr-switchboard/config.toml")

SAMPLE = r'''
# a comment
lang = "es"   # trailing comment
local_label = 'my box'

[refresh]
local_seconds = 2
remote_seconds = 4.5
remote_timeout = 1_0
cache_max_age = 600

[colors]
accent = "#bd93f9"
"selected_bg" = "blue"
fzf = "info:8"

[remote]
herdr = "PATH=\"/opt/x/bin:$PATH\" herdr --flag \u00e9\t"

[jump]
enabled = true
client = "mac1"
helper = "python3 /opt/sb/bin/switchboard"
'''
WANT = {"lang": "es", "local_label": "my box",
        "refresh": {"local_seconds": 2, "remote_seconds": 4.5, "remote_timeout": 10, "cache_max_age": 600},
        "colors": {"accent": "#bd93f9", "selected_bg": "blue", "fzf": "info:8"},
        "remote": {"herdr": 'PATH="/opt/x/bin:$PATH" herdr --flag \u00e9\t'},
        "jump": {"enabled": True, "client": "mac1", "helper": "python3 /opt/sb/bin/switchboard"}}
builtin = sb.toml_loads(SAMPLE, use_tomllib=False)
check("parser-builtin-reads-the-sample", builtin == WANT, builtin)
HAVE_TOMLLIB = sb.tomllib is not None
if HAVE_TOMLLIB:
    check("parser-matches-tomllib", sb.toml_loads(SAMPLE, use_tomllib=True) == builtin)
else:
    print("note: no tomllib on Python %d.%d; only the built-in parser was compared" % sys.version_info[:2])
BROKEN = ['lang = "es', "a = 1\na = 2", "[x]\n[x]", "= 1", "a = ", "a = 1 2", 'a = "x\\q"',
          "[x\nb = 1", "a = tru", "a = 01", 'a = "\x01"']
for text in BROKEN:
    for use in ([False, True] if HAVE_TOMLLIB else [False]):
        try:
            sb.toml_loads(text, use_tomllib=use)
            check("parser-rejects %r (tomllib=%s)" % (text, use), False)
        except ValueError:
            pass
for text in ("a = [1, 2]", "a = {b = 1}", '[[x]]\na = 1', 'a = """x"""', "a.b = 1"):
    try:
        sb.toml_loads(text, use_tomllib=False)
        check("parser-builtin-rejects-unsupported %r" % text, False)
    except ValueError:
        pass

with tempfile.TemporaryDirectory() as d:
    d = pathlib.Path(d)
    cfg, warn = sb.load_config(str(d / "missing.toml"))
    check("config-missing-is-defaults", cfg == sb.DEFAULTS and warn is None, (cfg, warn))
    (d / "sample.toml").write_text(SAMPLE)
    for use in ([False, True] if HAVE_TOMLLIB else [False]):
        cfg, warn = sb.load_config(str(d / "sample.toml"), use_tomllib=use)
        check("config-sample-loads (tomllib=%s)" % use, warn is None and cfg["lang"] == "es"
              and cfg["refresh"]["remote_timeout"] == 10.0 and cfg["jump"]["enabled"] is True
              and cfg["colors"]["muted"] == "bright-black", (cfg, warn))
    (d / "broken.toml").write_text('lang = "es\n[refresh\n')
    for use in ([False, True] if HAVE_TOMLLIB else [False]):
        cfg, warn = sb.load_config(str(d / "broken.toml"), use_tomllib=use)
        check("config-broken-defaults-and-warning (tomllib=%s)" % use,
              cfg == sb.DEFAULTS and warn and "broken.toml" in warn and "\n" not in warn, (cfg, warn))
    (d / "types.toml").write_text('bogus = 1\n[refresh]\nlocal_seconds = "fast"\nremote_seconds = -1\n'
                                  '[jump]\nenabled = "yes"\n[colors]\naccent = "red,blue"\n')
    cfg, warn = sb.load_config(str(d / "types.toml"), use_tomllib=False)
    check("config-bad-types-keep-defaults", cfg == sb.DEFAULTS, cfg)
    check("config-bad-types-warn", warn and all(w in warn for w in ("bogus", "refresh.local_seconds",
                                                                      "refresh.remote_seconds", "jump.enabled",
                                                                      "colors.accent")), warn)
    (d / "table.toml").write_text("refresh = 3\nlang = \"fr\"\n")
    cfg, warn = sb.load_config(str(d / "table.toml"), use_tomllib=False)
    check("config-not-a-table-and-bad-lang", cfg == sb.DEFAULTS and "[refresh]" in warn and "lang" in warn, warn)

    # End to end: a broken config never stops the tool, and says so in the header.
    cdir = d / "cfg"
    cdir.mkdir()
    (cdir / "config.toml").write_text("lang = \n")
    env = dict(os.environ, HERDR_PLUGIN_CONFIG_DIR=str(cdir), HERDR_BIN_PATH="/bin/false")
    r = subprocess.run([sys.executable, str(TOOL), "--demo", "--rows"], stdin=subprocess.DEVNULL,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, env=env, timeout=20)
    head = r.stdout.splitlines()[0] if r.stdout else ""
    check("config-broken-e2e", r.returncode == 0 and "config.toml" in head and "defaults in use" in head
          and "18 agents" in head, (r.returncode, head, r.stderr[-300:]))

# The example documents every option, with the defaults, and loads cleanly both ways.
EXAMPLE = (ROOT / "config.example.toml").read_text()
for use in ([False, True] if HAVE_TOMLLIB else [False]):
    raw = sb.toml_loads(EXAMPLE, use_tomllib=use)
    missing = [k for k, v in sb.DEFAULTS.items() if k not in raw] + \
        ["%s.%s" % (k, s) for k, v in sb.DEFAULTS.items() if isinstance(v, dict)
         for s in v if s not in raw.get(k, {})]
    check("example-documents-every-option (tomllib=%s)" % use, not missing, missing)
    cfg, problems = sb.merge_config(raw)
    check("example-is-the-defaults (tomllib=%s)" % use, cfg == sb.DEFAULTS and not problems, (cfg, problems))

# Environment overrides win over the file.
os.environ["SWITCHBOARD_REMOTE_TIMEOUT"] = "2.5"
sb.configure(sb.merge_config({"refresh": {"remote_timeout": 9}})[0])
check("env-override-wins", sb.REMOTE_TIMEOUT == 2.5, sb.REMOTE_TIMEOUT)
del os.environ["SWITCHBOARD_REMOTE_TIMEOUT"]
sb.configure(sb.merge_config({"refresh": {"remote_timeout": 9}})[0])
check("config-value-applies", sb.REMOTE_TIMEOUT == 9.0, sb.REMOTE_TIMEOUT)
sb.configure(sb.load_config()[0])
sb.LOCAL_EVERY, sb.REMOTE_EVERY = 0.05, 0.05

# 19. State and the herdr binary.
block('19. State and the herdr binary')
check("state-plugin-dir", sb.state_dir({"HERDR_PLUGIN_STATE_DIR": "/s"}) == "/s")
check("state-xdg", sb.state_dir({"XDG_STATE_HOME": "/x", "HOME": "/h"}) == "/x/herdr-switchboard")
check("state-home", sb.state_dir({"HOME": "/h"}) == "/h/.local/state/herdr-switchboard")
check("herdr-from-env", sb.find_herdr({"HERDR_BIN_PATH": "/opt/h/herdr", "PATH": "/usr/bin"}) == "/opt/h/herdr")
with tempfile.TemporaryDirectory() as d:
    h = executable(os.path.join(d, "herdr"), "#!/bin/sh\nexit 0\n")
    check("herdr-from-path", sb.find_herdr({"PATH": d}) == str(h), sb.find_herdr({"PATH": d}))
    check("herdr-fallback-name", sb.find_herdr({"PATH": os.path.join(d, "none")}) == "herdr")

    # End to end: --rows writes the ledger under HERDR_PLUGIN_STATE_DIR, else under XDG.
    snapfile = os.path.join(d, "snap.json")
    with open(snapfile, "w") as f:
        json.dump({"result": {"snapshot": snap([pane("w1:p1")], [agent("w1:p1", "idle", 1)])}}, f)
    fh = executable(os.path.join(d, "fake-herdr"),
                    '#!/bin/sh\ncase "$*" in\n  "api snapshot") cat "%s" ;;\n  "machine list --json") echo "[]" ;;\n'
                    '  *) exit 2 ;;\nesac\n' % snapfile)
    sdir, home_dir, xdg = os.path.join(d, "plugin-state"), os.path.join(d, "home"), os.path.join(d, "xdg")
    env = dict(os.environ, HERDR_BIN_PATH=str(fh), HERDR_PLUGIN_STATE_DIR=sdir, HOME=home_dir)
    subprocess.run([sys.executable, str(TOOL), "--rows"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                   env=env, timeout=20)
    check("state-in-plugin-dir", os.path.exists(os.path.join(sdir, "recency.json")) and not os.path.exists(home_dir))
    env = dict(os.environ, HERDR_BIN_PATH=str(fh), XDG_STATE_HOME=xdg, HOME=home_dir)
    del env["HERDR_PLUGIN_STATE_DIR"]
    subprocess.run([sys.executable, str(TOOL), "--rows"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                   env=env, timeout=20)
    check("state-xdg-fallback", os.path.exists(os.path.join(xdg, "herdr-switchboard", "recency.json")))
sb.STATE_DIR = STATE
sb.save_cache("box1", {"x": 1})
check("cache-under-state", os.path.exists(os.path.join(STATE, "snapshots", "box1.json")))

# 20. Language.
block('20. Language')
en, es = sb.STRINGS["en"], sb.STRINGS["es"]
check("strings-same-keys", set(en) == set(es), sorted(set(en) ^ set(es)))
ph = re.compile(r"%[sd]")
bad_ph = [k for k in en if k in es and ph.findall(en[k]) != ph.findall(es[k])]
check("strings-same-placeholders", not bad_ph, bad_ph)
used = set(k for k in re.findall(r'\btr\(\s*"([a-z_]+)"', SOURCE) if not k.endswith("_")) | \
    set("st_" + s for s in list(sb.PRIORITY) + ["shell"])
check("strings-every-used-key-exists", used <= set(en), sorted(used - set(en)))
check("default-language-english", sb.LANG == "en" and "agents" in sb.header([], [], [], []))
e_es = sb.entries_from(snap([pane("a")], [agent("a", "blocked", 1)]), "m1", "box1", 1)
sb.configure(sb.merge_config({"lang": "es"})[0])
try:
    h = sb.header(e_es, [], [], ["box2"])
    check("spanish-header", "1 agentes" in h and "se actualiza solo" in h and "box2 sin conexión" in h, h)
    check("spanish-offline-row", "sin conexión" in sb.down_row("box2"))
    check("spanish-copy-text", sb.tr("copied", "x", 3).startswith("copiado"))
finally:
    sb.configure(sb.load_config()[0])
    sb.LOCAL_EVERY, sb.REMOTE_EVERY = 0.05, 0.05
check("back-to-english", "1 agents" in sb.header(e_es, [], [], []))
with tempfile.TemporaryDirectory() as d:
    (pathlib.Path(d) / "config.toml").write_text('lang = "es"\n')
    r = subprocess.run([sys.executable, str(TOOL), "--help"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                       universal_newlines=True, env=dict(os.environ, HERDR_PLUGIN_CONFIG_DIR=d), timeout=20)
    check("spanish-from-the-config-file", "todos los agentes" in r.stdout, r.stdout[:200])
# No literal text handed to print() or input(): it all comes from the table.
literal_out = []
for node in ast.walk(tree):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("print", "input") and node.args:
        a0 = node.args[0]
        if isinstance(a0, ast.Constant) and isinstance(a0.value, str) or isinstance(a0, ast.JoinedStr) \
                or isinstance(a0, ast.BinOp) and isinstance(a0.left, ast.Constant):
            literal_out.append(node.lineno)
check("no-literal-text-to-the-user", not literal_out, literal_out)

# 21. Colours.
block('21. Colours')
default_colors = sb.fzf_colors(sb.DEFAULTS["colors"])
check("default-colors-ansi-only", "#" not in default_colors and "bg+:magenta" in default_colors, default_colors)
theme = "[colors]\n" + "\n".join(l[2:] for l in EXAMPLE.splitlines()
                                  if re.match(r"^# (accent|selected_fg|selected_bg|muted) = ", l))
tcfg, tproblems = sb.merge_config(sb.toml_loads(theme, use_tomllib=False))
check("example-theme-has-four-keys", theme.count(" = ") == 4, theme)
themed = sb.fzf_colors(tcfg["colors"])
check("example-theme-still-works", not tproblems and "bg+:#bd93f9" in themed and "fg+:#282a36:bold" in themed
      and "border:#6272a4" in themed, (tproblems, themed))
check("fzf-extra-appended", sb.fzf_colors(dict(sb.DEFAULTS["colors"], fzf="info:8")).endswith(",info:8"))

# 22. Dependencies.
block('22. Dependencies')
check("deps-ok", sb.dependency_problems(python=(3, 9, 0), fzf=False) == [])
p38 = sb.dependency_problems(python=(3, 8, 10), fzf=False, platform="linux", executable="/usr/bin/python3")
check("deps-old-python", len(p38) == 2 and "3.8.10" in p38[0] and "3.9" in p38[0] and "package manager" in p38[1], p38)
check("deps-old-python-macos", "xcode-select" in sb.dependency_problems(python=(3, 8, 2), fzf=False, platform="darwin")[1])
with tempfile.TemporaryDirectory() as d:
    old = executable(os.path.join(d, "fzf-old"), "#!/bin/sh\necho '0.44.1 (debian)'\n")
    new = executable(os.path.join(d, "fzf-new"), "#!/bin/sh\necho '0.74.2 (brew)'\n")
    edge = executable(os.path.join(d, "fzf-edge"), "#!/bin/sh\necho '0.71.0 (abc)'\n")
    quiet = executable(os.path.join(d, "fzf-quiet"), "#!/bin/sh\nexit 1\n")
    po = sb.dependency_problems(python=(3, 12, 0), fzf=str(old), platform="linux")
    check("deps-old-fzf", len(po) == 2 and "0.44.1" in po[0] and "0.71" in po[0] and "releases" in po[1], po)
    check("deps-old-fzf-macos", "brew install fzf" in sb.dependency_problems(python=(3, 12, 0), fzf=str(old),
                                                                             platform="darwin")[1])
    check("deps-new-fzf", sb.dependency_problems(python=(3, 12, 0), fzf=str(new)) == [])
    check("deps-fzf-exactly-the-minimum", sb.dependency_problems(python=(3, 12, 0), fzf=str(edge)) == [])
    pm = sb.dependency_problems(python=(3, 12, 0), fzf=None, platform="linux")
    check("deps-missing-fzf", pm and "not found" in pm[0], pm)
    check("deps-silent-fzf-is-missing", "not found" in sb.dependency_problems(python=(3, 12, 0), fzf=str(quiet))[0])
    # End to end: the popup refuses to start, says why, waits, and exits non-zero.
    for name, fzf_path, want in (("old", str(old), "0.44.1"), ("missing", "", "not found")):
        env = dict(os.environ, SWITCHBOARD_FZF=fzf_path, HERDR_BIN_PATH="/bin/false")
        r = subprocess.run([sys.executable, str(TOOL), "--demo"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, universal_newlines=True, env=env, timeout=20)
        check("deps-e2e-%s-fzf" % name, r.returncode != 0 and want in r.stdout and "0.71" in r.stdout
              and "Press Enter" in r.stdout, (r.returncode, r.stdout, r.stderr[-300:]))
# An old Python, simulated: the version check runs before anything else.
code = ("import runpy, sys; sys.version_info = (3, 8, 10, 'final', 0); sys.argv = ['switchboard', '--rows'];"
        " runpy.run_path(%r, run_name='__main__')" % str(TOOL))
r = subprocess.run([sys.executable, "-c", code], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                   stderr=subprocess.PIPE, universal_newlines=True, env=dict(os.environ, HERDR_BIN_PATH="/bin/false"),
                   timeout=20)
check("deps-e2e-old-python", r.returncode != 0 and "Python 3.9" in r.stdout and "3.8.10" in r.stdout,
      (r.returncode, r.stdout, r.stderr[-300:]))
# And a real one, when the machine has it (SWITCHBOARD_TEST_OLD_PYTHON or python3.8 on PATH).
old_py = os.environ.get("SWITCHBOARD_TEST_OLD_PYTHON") or shutil.which("python3.8")
if old_py:
    r = subprocess.run([old_py, str(TOOL), "--rows"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, universal_newlines=True, env=dict(os.environ, HERDR_BIN_PATH="/bin/false"),
                       timeout=20)
    check("deps-e2e-real-old-python", r.returncode != 0 and "Python 3.9" in r.stdout and "found Python 3." in r.stdout,
          (old_py, r.returncode, r.stdout, r.stderr[-300:]))

# 23. Demo.
block('23. Demo')
demo = sb.Demo()
check("demo-machines", demo.local == "laptop" and [m["label"] for m in demo.machines] == ["workstation", "server"],
      (demo.local, demo.machines))
all_ws, statuses, n_agents, n_terms, no_preview = set(), set(), 0, 0, []
for m, s in demo.snapshots.items():
    all_ws |= set(w["label"] for w in s["workspaces"])
    agent_ids = set(a["pane_id"] for a in s["agents"])
    statuses |= set(a["agent_status"] for a in s["agents"])
    n_agents += len(s["agents"])
    n_terms += sum(1 for p in s["panes"] if p["pane_id"] not in agent_ids)
    no_preview += ["%s %s" % (m, p["pane_id"]) for p in s["panes"]
                   if len(demo.previews.get(m, {}).get(p["pane_id"]) or []) < 3]
    check("demo-unique-panes %s" % m, len(set(p["pane_id"] for p in s["panes"])) == len(s["panes"]))
check("demo-workspaces", all_ws == {"api", "web", "infra", "docs"}, all_ws)
check("demo-every-status", statuses == set(sb.PRIORITY), statuses)
check("demo-about-18-agents", 16 <= n_agents <= 20, n_agents)
check("demo-some-terminals", n_terms >= 3, n_terms)
check("demo-a-preview-per-pane", not no_preview, no_preview)
check("demo-several-kinds", len(set(a["agent"] for s in demo.snapshots.values() for a in s["agents"])) >= 3)
d0 = sb.Demo(t0=0.0)
early = {a["pane_id"]: a["agent_status"] for a in d0.snapshot("workstation", now=1.0)["agents"]}
late = {a["pane_id"]: a["agent_status"] for a in d0.snapshot("workstation", now=100.0)["agents"]}
check("demo-timeline-changes-a-status", early != late and set(early) == set(late), (early, late))
saved_demo = sb.DEMO
sb.DEMO = demo
try:
    check("demo-answers-herdr", json.loads(sb.herdr(["machine", "list", "--json"])) == demo.machines)
    check("demo-preview-for-remote", "rate limiter" in sb.herdr_on("workstation", ["pane", "read", "w1:p3"]))
    out = sb.demo_outcome(sb.make_id("", "a", "w1:p1", "w1:t1"), {"workstation": "workstation"})
    check("demo-enter-local", out == ["demo: would run `herdr agent focus w1:p1`"], out)
    out = sb.demo_outcome(sb.make_id("workstation", "a", "w1:p3", "w1:t2"), {"workstation": "workstation"})
    # The demo never jumps, whatever the jump's setting (on by default), and says only that.
    check("demo-enter-remote", len(out) == 2 and "--machine workstation agent focus w1:p3" in out[0]
          and out[1] == "demo: the demo never jumps between machines; the pane would be ready on workstation"
          " when you switch to that machine", out)
finally:
    sb.DEMO = saved_demo
with tempfile.TemporaryDirectory() as d:
    d = pathlib.Path(d)
    marker_h, marker_s = d / "herdr-called", d / "ssh-called"
    fh = executable(d / "herdr", '#!/bin/sh\ntouch "%s"\nexit 3\n' % marker_h)
    fs = executable(d / "ssh", '#!/bin/sh\ntouch "%s"\nexit 3\n' % marker_s)
    sdir = d / "state"
    sdir.mkdir()
    env = dict(os.environ, HERDR_BIN_PATH=str(fh), SWITCHBOARD_SSH=str(fs), HERDR_PLUGIN_STATE_DIR=str(sdir),
               PATH=str(d) + os.pathsep + os.environ.get("PATH", ""))
    r = subprocess.run([sys.executable, str(TOOL), "--demo", "--rows"], stdin=subprocess.DEVNULL,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, env=env, timeout=20)
    head = r.stdout.splitlines()[0] if r.stdout else ""
    check("demo-rows", r.returncode == 0 and "18 agents" in head
          and all(m in r.stdout for m in ("laptop", "workstation", "server")), (head, r.stderr[-300:]))
    check("demo-no-herdr-no-ssh", not marker_h.exists() and not marker_s.exists())
    check("demo-writes-no-state", not any(sdir.iterdir()), list(sdir.iterdir()))
    r = subprocess.run([sys.executable, str(TOOL), "--demo", "--preview", "workstation|a|w1:p3|w1:t2"],
                       stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, universal_newlines=True, env=env, timeout=20)
    check("demo-preview-trimmed", "Which of these" in r.stdout and "accept edits" not in r.stdout, r.stdout[-300:])

# The demo in a real terminal, with the real fzf, when there is one recent enough.
fzf_real = shutil.which("fzf")
if fzf_real and not sb.dependency_problems(python=(3, 12, 0), fzf=fzf_real):
    import fcntl as _f2
    import struct as _st2
    import termios as _tm2

    # The whole interface: the full header and a row of each of the three machines. Keys go
    # only once all of it has been drawn, so a slow runner cannot cut the test short.
    DEMO_MARKERS = ("18 agents", "laptop", "workstation", "server", "rate-limiter-review", "terraform-plan-staging")

    def demo_missing(raw):
        plain = sb.ANSI.sub("", raw.decode("utf-8", "replace"))
        return [m for m in DEMO_MARKERS if m not in plain]

    def run_demo(keys):
        """Run --demo in a pty, send `keys` once the whole interface is on screen, and return
        (output, rc, the markers still missing when the keys went or time ran out)."""
        pid, fd = _pty.fork()
        if pid == 0:
            os.environ.update(TERM="xterm-256color", HERDR_BIN_PATH="/bin/false")
            os.execv(sys.executable, [sys.executable, "-B", str(TOOL), "--demo"])
        _f2.ioctl(fd, _tm2.TIOCSWINSZ, _st2.pack("HHHH", 40, 180, 0, 0))
        buf, missing, end = b"", None, _time.time() + 30
        while _time.time() < end:
            r, _, _ = _sel.select([fd], [], [], 0.1)
            if r:
                try:
                    chunk = os.read(fd, 65536)
                except OSError:
                    chunk = b""
                if not chunk:  # the child closed the terminal: reap it
                    return buf, finish(pid, fd, 5), missing
                buf += chunk
            else:
                done, st = os.waitpid(pid, os.WNOHANG)
                if done:  # exited while something still holds the terminal
                    finish(pid, fd, 0)  # reaped already: only sweeps its group and closes fd
                    return buf, os.waitstatus_to_exitcode(st), missing
            if missing is None and not demo_missing(buf):
                missing = []
                _time.sleep(0.3)
                os.write(fd, keys)
        finish(pid, fd, 0)
        return buf, None, demo_missing(buf) if missing is None else missing
    screen, rc, missing = run_demo(b"\x1b")
    check("demo-pty-renders", missing == [], missing)
    # fzf 0.66+ draws its gutter as a ▌ on every row; with a blank gutter only the pointer of
    # the selected row is one (a few redraws), against one per visible row without it.
    halves = screen.decode("utf-8", "replace").count("\u258c")
    check("demo-pty-no-gutter-column", 0 < halves < 10, halves)
    check("demo-pty-esc-exits-clean", rc == 0, rc)
    screen, rc, missing = run_demo(b"\r")
    plain = sb.ANSI.sub("", screen.decode("utf-8", "replace"))
    check("demo-pty-enter-prints-what-it-would-do", rc == 0 and "demo: would run `herdr --machine workstation agent focus"
          in plain, (rc, plain[-400:]))
else:
    print("note: no fzf %s or newer here; the demo was not run in a terminal" % sb.version_text(sb.MIN_FZF))

# 24. The jump is on by default; when it cannot happen, Enter takes the focus path at once.
block('24. The jump is on by default')
cfg24, warn24 = sb.load_config(os.path.join(_tmp_root, "no-such-config.toml"))
check("jump-on-by-default", sb.DEFAULTS["jump"]["enabled"] is True and cfg24["jump"]["enabled"] is True
      and warn24 is None and sb.JUMP_ENABLED is True, (sb.DEFAULTS["jump"], sb.JUMP_ENABLED))
check("enter-mode-on", sb.enter_mode([{"id": "m1"}]) == (True, True))
check("enter-mode-no-machines", sb.enter_mode([]) == (False, False))
check("enter-mode-demo", sb.enter_mode([{"id": "m1"}], demo=True) == (False, False))
sb.configure(sb.merge_config({"jump": {"enabled": False}})[0])
try:
    check("enter-mode-off", sb.JUMP_ENABLED is False and sb.enter_mode([{"id": "m1"}]) == (False, True))
finally:
    sb.configure(sb.load_config()[0])
    sb.LOCAL_EVERY, sb.REMOTE_EVERY = 0.05, 0.05
argv = sb.fzf_argv("fzf", "self", "/tmp/s.sock", remote_enter=True)
check("enter-bound-with-other-machines", "enter:transform(self --enter {1})" in argv, argv)
check("enter-not-bound-without", not any(a.startswith("enter:") for a in sb.fzf_argv("fzf", "self", "/tmp/s.sock")))
with tempfile.TemporaryDirectory() as d:
    d = pathlib.Path(d)
    (d / "machines.json").write_text(json.dumps([{"id": "m1", "label": "box1", "enabled": True}]))
    log = d / "log"
    fh = executable(d / "herdr", '#!/bin/sh\necho "$*" >> "%(d)s/log"\ncase "$*" in\n'
                                 '  "machine list --json") cat "%(d)s/machines.json" ;;\n'
                                 '  "--machine m2 "*) exit 1 ;;\n'
                                 '  "--machine m1 agent focus"*) exec sleep 1.5 ;;\n  *) exit 0 ;;\nesac\n' % {"d": d})
    run_dir = d / "run"
    run_dir.mkdir(mode=0o700)  # like the popup's own (mkdtemp): helpers refuse anything looser
    run_dir.chmod(0o700)

    def run_mode(mode, *args, **kw):
        env = dict(os.environ, HERDR_BIN_PATH=str(fh), SWITCHBOARD_RUN_DIR=str(run_dir),
                   SWITCHBOARD_LABELS=json.dumps({"m1": "box1", "m2": "box2"}),
                   SWITCHBOARD_REMOTE_TIMEOUT=kw.get("timeout", "8"))
        if kw.get("cfg_dir"):
            env["HERDR_PLUGIN_CONFIG_DIR"] = str(kw["cfg_dir"])
        # Past --focus-wait's own deadline, which comes from the program's bound.
        cap = sb.herdr_on_bound(float(env["SWITCHBOARD_REMOTE_TIMEOUT"])) + 10
        r = subprocess.run([sys.executable, str(TOOL), mode] + list(args), stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE, universal_newlines=True, env=env, timeout=cap)
        return r.stdout.strip()

    def wait_for(path, seconds=6.0):
        end = _time.time() + seconds
        while _time.time() < end:
            if os.path.exists(path) and open(path).read().strip():
                return open(path).read().strip()
            _time.sleep(0.05)
        return None

    # Enter returns at once although the focus takes 1.5 s: it records the ack, starts a
    # detached worker and prints a footer now plus a background wait for the result.
    t0 = _time.time()
    out = run_mode("--enter", "m1|a|w1:p4|w1:t2")
    took = _time.time() - t0
    check("enter-remote-returns-at-once", took < 1.2, took)
    check("enter-remote-footer-now", out.startswith("change-footer(focusing it on box1…)+bg-transform-footer"), out)
    m = re.search(r"--focus-wait (\S+) 'm1\|a\|w1:p4\|w1:t2'\)$", out)
    check("enter-remote-waits-in-background", m is not None, out)
    acks = (run_dir / "acks").read_text().splitlines() if (run_dir / "acks").exists() else []
    check("enter-remote-acks-the-tab-at-once", acks == ['["m1", "w1:t2"]'], acks)
    name = m.group(1) if m else ""
    # Only the bare file name travels on a command line; the run directory's path never does.
    check("enter-remote-only-a-name-in-argv", re.fullmatch(r"focus-[0-9]+-[0-9]+", name) is not None
          and str(run_dir) not in out, out)
    result = str(run_dir / name) if name else ""
    got = wait_for(result) if result else None
    check("enter-worker-delivers-the-result", got == "ready on box1: switch to that machine to see it · esc closes", got)
    check("enter-worker-focused-through-the-api", log.exists() and "--machine m1 agent focus w1:p4" in log.read_text(),
          log.read_text() if log.exists() else "")
    check("focus-wait-shows-the-result", name and run_mode("--focus-wait", name, "m1|a|w1:p4|w1:t2") == got)
    check("focus-wait-gives-up", "could not focus it on box2" in run_mode("--focus-wait", "focus-1-1",
                                                                       "m2|t|w1:p1|w1:t1", timeout="1"))
    acks = (run_dir / "acks").read_text().splitlines() if (run_dir / "acks").exists() else []
    check("worker-does-not-ack-again", acks == ['["m1", "w1:t2"]'], acks)
    out = run_mode("--focus", "m2|t|w1:p1|w1:t1")
    check("focus-remote-fails-quietly", "could not focus it on box2" in out, out)
    log.write_text("")
    out = run_mode("--enter", "|a|w1:p1|w1:t1")
    check("enter-local-accepts", out == "accept" and "focus" not in log.read_text(), (out, log.read_text()))
    check("enter-header-nothing", run_mode("--enter", "-") == "")
    check("focus-local-row-nothing", run_mode("--focus", "|a|w1:p1|w1:t1") == "" and "focus" not in log.read_text())
    # Everything above ran with the jump on (no config file: the default) and no link: the
    # focus path. Now with the link's state in the run directory, as the popup's JumpLink keeps it.
    state = run_dir / sb.JUMP_STATE
    cfg_off = d / "cfg-off"
    cfg_off.mkdir()
    (cfg_off / "config.toml").write_text("[jump]\nenabled = false\n")

    def set_state(text):  # atomically, as the link does: --enter never reads half a write
        (run_dir / "state.tmp").write_text(text)
        os.rename(str(run_dir / "state.tmp"), str(state))

    def enter_timed(cfg_dir=None, cap=None):
        """--enter on a remote row: (output, seconds), or (None, None) past `cap` seconds."""
        env = dict(os.environ, HERDR_BIN_PATH=str(fh), SWITCHBOARD_RUN_DIR=str(run_dir),
                   SWITCHBOARD_LABELS=json.dumps({"m1": "box1", "m2": "box2"}))
        if cfg_dir:
            env["HERDR_PLUGIN_CONFIG_DIR"] = str(cfg_dir)
        t0 = _time.time()
        try:
            r = subprocess.run([sys.executable, str(TOOL), "--enter", "m1|a|w1:p4|w1:t2"], stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, universal_newlines=True, env=env,
                               timeout=cap or sb.JUMP_ENTER_WAIT + 10)
        except subprocess.TimeoutExpired:
            return None, None
        return r.stdout.strip(), round(_time.time() - t0, 3)

    FOOTER = "change-footer(focusing it on box1…)+bg-transform-footer"
    set_state("ready\n")
    on_ready, _ = enter_timed()
    off_ready, _ = enter_timed(cfg_off)
    check("enter-jumps-when-the-link-is-ready", on_ready == "accept", on_ready)
    check("enabled-false-turns-it-off", on_ready == "accept" and (off_ready or "").startswith(FOOTER),
          (on_ready, off_ready))
    # No client found: the popup's link settles at once and leaves no state; Enter takes the
    # focus path without waiting, as with the jump off. (on_ready shows the jump is on here.)
    if state.exists():
        state.unlink()
    nolink24 = sb.JumpLink(find=lambda: None).start(str(run_dir))
    settled = nolink24.started.wait(5)
    end24 = _time.time() + 5
    while state.exists() and _time.time() < end24:
        _time.sleep(0.02)
    nolink24.detach()
    out_none, took_none = enter_timed()
    out_off, took_off = enter_timed(cfg_off)
    check("no-client-enter-takes-the-focus-path-at-once", on_ready == "accept" and settled and not state.exists()
          and (out_none or "").startswith(FOOTER) and took_none is not None and took_none < 1.2,
          (out_none, took_none, "off:", took_off))
    # A link still being set up (a Mac that does not answer fails only at ssh's ConnectTimeout):
    # Enter waits for it JUMP_ENTER_WAIT at most, then takes the focus path.
    set_state("pending\n")
    out_stuck, took_stuck = enter_timed(cap=sb.JUMP_ENTER_WAIT + 8)
    check("enter-waits-for-a-pending-link-at-most-its-bound", (out_stuck or "").startswith(FOOTER)
          and took_stuck is not None and sb.JUMP_ENTER_WAIT - 0.1 <= took_stuck < sb.JUMP_ENTER_WAIT + 1.2,
          (out_stuck, took_stuck))
    # ...and one that becomes ready meanwhile jumps.
    set_state("pending\n")
    flip = _threading.Timer(0.5, set_state, args=("ready\n",))
    flip.start()
    out_flip, took_flip = enter_timed()
    flip.join(5)
    check("enter-jumps-once-a-pending-link-is-ready", out_flip == "accept" and took_flip is not None
          and 0.4 <= took_flip < sb.JUMP_ENTER_WAIT + 1.0, (out_flip, took_flip))
    if state.exists():
        state.unlink()

    # A helper that starts and never says it is ready (one of an older version, or a shell
    # profile that prints instead): the link gives it READY_WAIT from its start, then settles as
    # not ready, so later Enters take the focus path at once instead of waiting
    # JUMP_ENTER_WAIT each. It is still running then: the deadline did it, not its end.
    # (No exec: the shell keeps its output open, as a helper that is still running does.)
    silent_ssh = executable(d / "ssh-silent", '#!/bin/sh\necho "a profile line"\ncat > /dev/null\n')
    saved_link = (sb.SSH, sb.READY_WAIT)
    sb.SSH, sb.READY_WAIT = str(silent_ssh), 0.6
    try:
        silent24 = sb.JumpLink(find=lambda: ("ssh", "mac1"), helper=lambda h: "sb-helper").start(str(run_dir))
        t0 = _time.time()
        pending24 = state.read_text() if state.exists() else None
        end24 = t0 + 5
        while state.exists() and _time.time() < end24:
            _time.sleep(0.02)
        gave_up = round(_time.time() - t0, 3)
        alive24 = silent24.proc is not None and silent24.proc.poll() is None
        later = [enter_timed() for _ in range(2)]
    finally:
        sb.SSH, sb.READY_WAIT = saved_link
        silent24.close()
        silent24.detach()
    check("silent-helper-later-enters-take-the-focus-path-at-once", pending24 == "pending\n"
          and 0.5 <= gave_up < 3 and alive24 and not silent24.up.is_set()
          and all((o or "").startswith(FOOTER) and t is not None and t < 1.2 for o, t in later),
          (pending24, gave_up, alive24, later))
    if silent24.proc:
        silent24.proc.wait(5)

    # A helper that says the window's herdr keys differ from [jump]'s: the state stays "keys",
    # Enter takes the focus path at once, and its footer, then the focus result, say why.
    keys_ssh = executable(d / "ssh-keys", '#!/bin/sh\necho %s\n' % sb.JUMP_KEYS_DIFFER)
    saved_link = sb.SSH
    sb.SSH = str(keys_ssh)
    try:
        keys24 = sb.JumpLink(find=lambda: ("ssh", "mac1"), helper=lambda h: "sb-helper").start(str(run_dir))
        keys24.started.wait(5)
        if keys24.proc:
            keys24.proc.wait(5)
        end24 = _time.time() + 5
        while not (state.exists() and state.read_text() == "keys\n") and _time.time() < end24:
            _time.sleep(0.02)
        _time.sleep(0.1)  # the link is done with the helper: "keys" stays
        kept24 = state.read_text() if state.exists() else None
    finally:
        sb.SSH = saved_link
        keys24.detach()
    out_keys, took_keys = enter_timed()
    note = " · no jump: set [jump] prefix and goto to this window's herdr keys"
    m24 = re.search(r"--focus-wait (\S+) ", out_keys or "")
    waited24 = run_mode("--focus-wait", m24.group(1), "m1|a|w1:p4|w1:t2") if m24 else ""
    check("keys-differ-footer-says-why", kept24 == "keys\n" and not keys24.was_up
          and (out_keys or "").startswith("change-footer(focusing it on box1…" + note + ")+bg-transform-footer")
          and took_keys is not None and took_keys < 1.2
          and waited24 == "ready on box1: switch to that machine to see it · esc closes" + note,
          (kept24, out_keys, took_keys, waited24))
    if state.exists():
        state.unlink()

    # The popup's close never waits for the link: neither one still looking for the client
    # (stuck here, as on a Mac that does not answer) nor one whose helper never said it was
    # ready. jump() only writes to the helper's pipe or starts a process.
    args24 = ["--jump", "box1", "a", "w1:p4", "w1:t2", "w1:p4", "0", "", "\\x02g/"]
    stuck = _threading.Event()
    slow24 = sb.JumpLink(find=lambda: stuck.wait(30) and None).start(str(run_dir))
    # "pending" from the moment start() returns: an Enter right then waits instead of giving up.
    check("link-pending-from-its-start", state.exists() and state.read_text() == "pending\n",
          state.read_text() if state.exists() else None)
    _time.sleep(0.1)
    t0 = _time.time()
    jumped24 = slow24.jump(args24)
    slow24.close()
    slow24.detach()
    took24 = _time.time() - t0
    check("close-never-waits-for-a-link-being-set-up", jumped24 is False and took24 < 0.2 and slow24.proc is None,
          (jumped24, took24))
    stuck.set()
    if state.exists():
        state.unlink()  # a detached link leaves it: the popup removes the whole directory
    spawned24 = []
    saved24 = (sb.subprocess.Popen, sb.resolve_helper)
    sb.subprocess.Popen = lambda argv, **kw: spawned24.append(argv)
    sb.resolve_helper = lambda host: spawned24.append("lookup") or "sb-helper"
    try:
        gone = sb.JumpLink(find=lambda: None)
        gone.client, gone.command, gone.was_up = ("ssh", "mac1"), None, True
        never = sb.JumpLink(find=lambda: None)
        never.client, never.command = ("ssh", "mac1"), "sb-helper"
        ended = sb.JumpLink(find=lambda: None)
        ended.client, ended.command, ended.was_up = ("ssh", "mac1"), "sb-helper", True
        got24 = (gone.jump(args24), never.jump(args24), ended.jump(args24))
    finally:
        sb.subprocess.Popen, sb.resolve_helper = saved24
    check("close-relaunches-only-what-was-up-and-looks-nothing-up", got24 == (False, False, True)
          and len(spawned24) == 1 and spawned24[0][0] == sb.SSH and "lookup" not in spawned24, (got24, spawned24))
    _popup_fn = next(n for n in ast.walk(ast.parse(SOURCE)) if isinstance(n, ast.FunctionDef) and n.name == "popup")
    _popup_calls = {n.func.id if isinstance(n.func, ast.Name) else n.func.attr for n in ast.walk(_popup_fn)
                    if isinstance(n, ast.Call) and isinstance(n.func, (ast.Name, ast.Attribute))}
    check("popup-close-looks-nothing-up", not _popup_calls & {"find_client", "resolve_helper", "launch_jump",
                                                              "answers_as_mac", "client_bridges", "send"},
          sorted(_popup_calls))

    # The popup applies what --enter acknowledged: the done row turns idle.
    sb.STATE_DIR = str(d / "state")
    m1 = [{"id": "m1", "label": "box1"}]
    vivid = {"local": snap17(T1, ag17("p1", "working", 1, T1)), "m1": snap17(T1, ag17("p9", "working", 1, T1))}
    # No snapshot cache: the watch loop's threads would otherwise still be writing it into this
    # temporary directory while it is removed (seen on a slow macOS runner).
    lv = sb.Live(m1, sb.entries_from(vivid["local"], "", "here", 0), fetch=lambda m="", t=None, i=None: vivid[m or "local"],
                 focus=T1, cache=False)
    lv.refresh_remote(0, m1[0])
    vivid["m1"] = snap17(T1, ag17("p9", "idle", 2, T1, 2))
    lv.refresh_remote(0, m1[0])
    check("acks-before", "● done" in lv.text())
    ack_file = d / "acks-live"
    ack_file.write_text(json.dumps(["m1", T1]) + "\nnot json\n")
    check("acks-consumed", lv.consume_acks(str(ack_file)) is True and not ack_file.exists())
    check("acks-clear-done", "● done" not in lv.text(), lv.text())
    check("acks-missing-file-is-fine", lv.consume_acks(str(ack_file)) is False)

    # And while the popup is open, the watch loop applies them and reloads fzf.
    vivid["m1"] = snap17(T1, ag17("p9", "working", 3, T1))
    lv.refresh_remote(0, m1[0])
    vivid["m1"] = snap17(T1, ag17("p9", "idle", 4, T1, 4))
    lv.refresh_remote(0, m1[0])
    lv.changed()  # the loops re-read the same data from here on: only the ack can change the rows
    check("acks-watch-before", "● done" in lv.text())
    sock = short_sock("w")
    fz = FakeFzf(sock, position=0)
    stop = _threading.Event()
    watcher24 = _threading.Thread(target=sb.watch, args=(lv, sock, str(d / "rows"), stop, str(ack_file)), daemon=True)
    watcher24.start()
    _time.sleep(0.3)
    ack_file.write_text(json.dumps(["m1", T1]) + "\n")
    _time.sleep(0.5)
    stop.set()
    watcher24.join(5)  # the loop is done with this directory before it goes
    check("acks-watch-applies-and-reloads", not ack_file.exists() and "● done" not in lv.text()
          and any(b"reload-sync" in r for r in fz.reqs), (ack_file.exists(), lv.text()[:300]))
    sb.STATE_DIR = STATE

check("client-from-config", sb.find_client(configured="mac9") == ("ssh", "mac9"))
check("client-local-from-config", sb.find_client(configured="local") == ("local", None))
saved_ts = sb.TAILSCALE
sb.TAILSCALE = ("/nonexistent/tailscale",)
try:
    check("no-tailscale-no-hosts", sb.tailnet_hosts() == {})
    check("no-tailscale-asks-over-ssh", sb.find_client([(1, "addr-1")], None, "", platform="linux", configured="",
                                                       is_mac=lambda h: h == "addr-1") == ("ssh", "addr-1"))
    check("no-tailscale-not-a-mac", sb.find_client([(1, "addr-1")], None, "", platform="linux", configured="",
                                                   is_mac=lambda h: False) is None)
finally:
    sb.TAILSCALE = saved_ts
check("plugin-root-parsed", sb.plugin_root_from(json.dumps({"result": {"plugins": [
    {"plugin_id": "other.plugin", "plugin_root": "/opt/other"},
    {"plugin_id": "trustxai.switchboard", "plugin_root": "/opt/plugins/sb"}]}})) == "/opt/plugins/sb")
check("plugin-root-absent", sb.plugin_root_from('{"result": {"plugins": []}}') is None and sb.plugin_root_from("") is None)
with tempfile.TemporaryDirectory() as d:
    d = pathlib.Path(d)
    listing = json.dumps({"result": {"plugins": [{"plugin_id": "trustxai.switchboard", "plugin_root": "/opt/p/sb dir"}]}})
    fs_ok = executable(d / "ssh-ok", "#!/bin/sh\necho '%s'\n" % listing)
    fs_none = executable(d / "ssh-none", "#!/bin/sh\nexit 255\n")
    saved_ssh, saved_helper = sb.SSH, sb.JUMP_HELPER
    try:
        sb.SSH = str(fs_ok)
        check("helper-discovered", sb.resolve_helper("mac1") == "python3 '/opt/p/sb dir/bin/switchboard'",
              sb.resolve_helper("mac1"))
        sb.JUMP_HELPER = "python3 /srv/sb/bin/switchboard"
        check("helper-from-config", sb.resolve_helper("mac1") == "python3 /srv/sb/bin/switchboard")
        sb.JUMP_HELPER = ""
        sb.SSH = str(fs_none)
        check("helper-unknown", sb.resolve_helper("mac1") is None)
        spawned = []
        orig_popen = sb.subprocess.Popen
        sb.subprocess.Popen = lambda argv, **kw: spawned.append(argv) or orig_popen(argv, **kw)
        try:
            link = sb.JumpLink(find=lambda: ("ssh", "mac1")).start()
            link.started.wait(5)
            sent = link.send(["--jump"] * 8) or link.jump(["--jump"] * 8)
            launched = sb.launch_jump(["--jump"] * 8, ("ssh", "mac1"))
        finally:
            sb.subprocess.Popen = orig_popen
        jumps = [a for a in spawned if "--jump" in a[-1]]
        lookups = [a for a in spawned if a[-1].endswith("plugin list --json")]
        check("link-without-helper-does-not-connect", sent is False and not jumps and lookups, spawned)
        check("launch-without-helper-falls-back", launched is False and not jumps, spawned)
    finally:
        sb.SSH, sb.JUMP_HELPER = saved_ssh, saved_helper
check("no-fixed-helper-path", "REMOTE_SELF" not in SOURCE and "~/.local/bin/switchboard" not in SOURCE
      and "~/.local/bin/herdr" not in SOURCE)

# 25. The manifest, and the program file itself.
block('25. The manifest, and the program file itself')
MANIFEST = (ROOT / "herdr-plugin.toml").read_text()
if HAVE_TOMLLIB:
    man = sb.tomllib.loads(MANIFEST)
    check("manifest-metadata", man.get("id") == "trustxai.switchboard" and man.get("name")
          and man.get("version") == sb.VERSION and man.get("min_herdr_version") == "0.9.5"
          and man.get("platforms") == ["linux", "macos"] and man.get("description"), man)
    panes = man.get("panes") or []
    actions = man.get("actions") or []
    check("manifest-one-popup-pane", len(panes) == 1 and panes[0].get("placement") == "popup"
          and str(panes[0].get("width", "")).endswith("%") and str(panes[0].get("height", "")).endswith("%"), panes)
    check("manifest-open-action", [a.get("id") for a in actions] == ["open"], actions)
    with tempfile.TemporaryDirectory() as d:
        log = os.path.join(d, "log")
        fh = executable(os.path.join(d, "herdr"), '#!/bin/sh\necho "$*" > "%s"\n' % log)
        env = dict(os.environ, HERDR_BIN_PATH=str(fh), HERDR_PLUGIN_ID="trustxai.switchboard")
        subprocess.run(actions[0]["command"], cwd=str(ROOT), env=env, stdin=subprocess.DEVNULL, timeout=20)
        got = open(log).read().strip() if os.path.exists(log) else ""
        check("manifest-action-opens-the-pane",
              got == "plugin pane open --plugin trustxai.switchboard --entrypoint %s" % panes[0]["id"], got)
        # The pane command reaches the program from any directory (here it stops at the fzf check).
        # python3 is this interpreter: a version-manager shim on PATH would need the real HOME.
        env = dict(os.environ, HERDR_PLUGIN_ROOT=str(ROOT), SWITCHBOARD_FZF="", HERDR_BIN_PATH="/bin/false",
                   PATH=os.path.dirname(sys.executable) + os.pathsep + os.environ.get("PATH", ""))
        r = subprocess.run(panes[0]["command"], cwd=d, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           universal_newlines=True, timeout=20)
        check("manifest-pane-runs-the-program", r.returncode != 0 and "fzf" in r.stdout, r.stdout[-200:])
else:
    for line in ('id = "trustxai.switchboard"', 'version = "%s"' % sb.VERSION, 'min_herdr_version = "0.9.5"',
                 'platforms = ["linux", "macos"]', 'placement = "popup"', 'id = "open"', "[[panes]]", "[[actions]]"):
        check("manifest-has %s" % line, line in MANIFEST)
CHANGELOG = (ROOT / "CHANGELOG.md").read_text()
heads = re.findall(r"^## \[([^\]]+)\]", CHANGELOG, re.M)
check("changelog-latest-release-is-VERSION", heads[:1] == ["Unreleased"] and heads[1:2] == [sb.VERSION]
      and ("[%s]: https://github.com/trustxai/herdr-switchboard/releases/tag/v%s" % (sb.VERSION, sb.VERSION)) in CHANGELOG
      and ("[Unreleased]: https://github.com/trustxai/herdr-switchboard/compare/v%s...HEAD" % sb.VERSION) in CHANGELOG,
      heads[:3])
check("program-executable", os.access(str(TOOL), os.X_OK) and SOURCE.startswith("#!/usr/bin/env python3\n"))
std = set(getattr(sys, "stdlib_module_names", ())) or {
    "base64", "copy", "glob", "json", "os", "re", "select", "shlex", "shutil", "socket", "subprocess", "sys",
    "tempfile", "threading", "time", "unicodedata", "tomllib", "termios", "tty", "stat", "math", "signal",
    "atexit"}
imported = set()
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        imported |= set(a.name.split(".")[0] for a in node.names)
    elif isinstance(node, ast.ImportFrom):
        imported.add((node.module or "").split(".")[0])
check("program-stdlib-only", imported <= std, sorted(imported - std))
try:
    ast.parse(SOURCE, feature_version=(3, 9))
except SyntaxError as exc:
    check("program-python-3.9-syntax", False, exc)
# Nothing personal in what ships: no addresses, no e-mail, no home directory of a person.
leaks = []
for path in [TOOL, ROOT / "herdr-plugin.toml", ROOT / "config.example.toml", pathlib.Path(__file__)] + \
        sorted((ROOT / "demo").rglob("*")):
    if not path.is_file():
        continue
    text = path.read_text()
    for pat in (r"\b(?:\d{1,3}\.){3}\d{1,3}\b", r"[\w.+-]+@[\w-]+\.[A-Za-z]{2,}", r"\b[0-9a-f]{0,4}(?::[0-9a-f]{0,4}){5,7}\b"):
        leaks += ["%s: %s" % (path.name, m) for m in re.findall(pat, text)]
    for user in re.findall(r"/(?:home|Users)/([A-Za-z0-9._-]+)", text):
        if user not in ("linuxbrew", "someone", "x"):
            leaks.append("%s: home of %s" % (path.name, user))
check("nothing-personal", not leaks, leaks)
demo_text = (ROOT / "demo" / "fixtures.json").read_text()
names = set(re.findall(r'"(?:local|label|machine)": "([^"]+)"', demo_text))
check("demo-only-generic-machine-names", names <= {"laptop", "workstation", "server", "api", "web", "infra", "docs",
                                                   "checkout", "e2e", "guides", "release", "auth", "rate-limit",
                                                   "orders", "cache", "landing", "k8s", "terraform", "monitoring",
                                                   "logs", "load-test", "db", "2", "4"}, names)

# 26. The ssh control sockets go only in a directory that is provably this user's.
block('26. The ssh control sockets go only in a directory that is provably this u')
with tempfile.TemporaryDirectory(dir="/tmp") as d:
    fresh = os.path.join(d, "fresh")
    check("ctl-dir-created-private", sb.private_dir(fresh) and stat.S_IMODE(os.lstat(fresh).st_mode) == 0o700)
    check("ctl-dir-reused", sb.private_dir(fresh))
    loose = os.path.join(d, "loose")
    os.mkdir(loose)
    os.chmod(loose, 0o755)
    check("ctl-dir-preexisting-open-mode-refused", sb.private_dir(loose) is False)
    shared = os.path.join(d, "shared")
    os.mkdir(shared)
    os.chmod(shared, 0o770)
    check("ctl-dir-group-access-refused", sb.private_dir(shared) is False)
    target = os.path.join(d, "target")
    os.mkdir(target, 0o700)
    link = os.path.join(d, "link")
    os.symlink(target, link)
    check("ctl-dir-symlink-refused", sb.private_dir(link) is False)
    afile = os.path.join(d, "file")
    open(afile, "w").close()
    check("ctl-dir-file-refused", sb.private_dir(afile) is False)
    real_getuid = sb.os.getuid
    sb.os.getuid = lambda: real_getuid() + 1
    try:
        check("ctl-dir-other-owner-refused", sb.private_dir(fresh) is False)
    finally:
        sb.os.getuid = real_getuid

    # Where: the user's runtime directory first, then the shared temporary directory.
    uid = os.getuid()
    runtime = os.path.join(d, "run")
    os.mkdir(runtime, 0o700)
    tmp_ok = os.path.join(d, "t1")
    os.mkdir(tmp_ok)
    got = sb.find_ssh_control_dir({"XDG_RUNTIME_DIR": runtime}, tmp=tmp_ok)
    check("ctl-dir-prefers-runtime", got == os.path.join(runtime, "switchboard"), got)
    os.chmod(runtime, 0o777)
    got = sb.find_ssh_control_dir({"XDG_RUNTIME_DIR": runtime}, tmp=tmp_ok)
    check("ctl-dir-open-runtime-skipped", got == os.path.join(tmp_ok, "switchboard-%d" % uid), got)
    got = sb.find_ssh_control_dir({"XDG_RUNTIME_DIR": os.path.join(d, "x" * 80)}, tmp=tmp_ok)
    check("ctl-dir-too-long-skipped", got == os.path.join(tmp_ok, "switchboard-%d" % uid), got)
    tmp_bad = os.path.join(d, "t2")
    os.mkdir(tmp_bad)
    os.mkdir(os.path.join(tmp_bad, "switchboard-%d" % uid), 0o755)
    os.chmod(os.path.join(tmp_bad, "switchboard-%d" % uid), 0o755)
    check("ctl-dir-planted-refused", sb.find_ssh_control_dir({}, tmp=tmp_bad) is None)
    tmp_link = os.path.join(d, "t3")
    os.mkdir(tmp_link)
    os.symlink(target, os.path.join(tmp_link, "switchboard-%d" % uid))
    check("ctl-dir-planted-symlink-refused", sb.find_ssh_control_dir({}, tmp=tmp_link) is None)
    saved_dir = list(sb._SSH_DIR)
    try:
        sb._SSH_DIR[:] = [None]
        check("no-safe-dir-no-sharing", sb.ssh_mux() == [])
        sb._SSH_DIR[:] = [fresh]
        mux = sb.ssh_mux()
        check("safe-dir-shares", "ControlMaster=auto" in mux and "ControlPath=%s/ssh-%%C" % fresh in mux, mux)
    finally:
        sb._SSH_DIR[:] = saved_dir

# 27. A config can never crash the program, and reads the same on every Python.
block('27. A config can never crash the program, and reads the same on every Pyth')
PARSERS = [False, True] if HAVE_TOMLLIB else [False]
with tempfile.TemporaryDirectory() as d:
    d = pathlib.Path(d)
    BAD = [
        ("[lang]\n", "lang"),
        ('lang = ["es"]\n', "lang"),
        ("[refresh]\ncache_max_age = 1e400\n", "refresh.cache_max_age"),
        ("[refresh]\nlocal_seconds = nan\n", "refresh.local_seconds"),
        ("[refresh]\nremote_seconds = inf\n", "refresh.remote_seconds"),
        ("[refresh]\nremote_timeout = -inf\n", "refresh.remote_timeout"),
        ("[refresh]\nremote_timeout = %s\n" % ("9" * 400), "refresh.remote_timeout"),
        ("[refresh]\nlocal_seconds = 0.1\n", "refresh.local_seconds"),
        ("[refresh]\nlocal_seconds = 61\n", "refresh.local_seconds"),
        ("[refresh]\ncache_max_age = -1\n", "refresh.cache_max_age"),
        ("[refresh]\ncache_max_age = 100000\n", "refresh.cache_max_age"),
        ("[refresh.local_seconds]\n", "refresh.local_seconds"),
        ("[local_label]\n", "local_label"),
        ("[jump]\nenabled = 1\n", "jump.enabled"),
    ]
    for i, (text, key) in enumerate(BAD):
        path = d / ("bad%d.toml" % i)
        path.write_bytes(text.encode())
        for use in PARSERS:
            try:
                cfg, warn = sb.load_config(str(path), use_tomllib=use)
            except Exception as exc:
                check("config-never-raises %r (tomllib=%s)" % (text[:40], use), False, repr(exc))
                continue
            check("config-bad-value-is-default %r (tomllib=%s)" % (text[:40], use), cfg == sb.DEFAULTS, cfg)
            check("config-bad-value-warns %r (tomllib=%s)" % (text[:40], use), bool(warn) and "\n" not in warn, warn)
            # The built-in parser rejects arrays as a whole; tomllib reads them and the key is refused.
            if use or "[" not in text.split("=")[-1]:
                # Only after the path: the path itself could contain a short key by chance.
                after_path = (warn or "").split(str(path), 1)[-1]
                check("config-warning-names-the-key %r (tomllib=%s)" % (text[:40], use), key in after_path, warn)
        env = dict(os.environ, HERDR_PLUGIN_CONFIG_DIR=str(d / ("dir%d" % i)))
        os.makedirs(env["HERDR_PLUGIN_CONFIG_DIR"])
        (pathlib.Path(env["HERDR_PLUGIN_CONFIG_DIR"]) / "config.toml").write_bytes(text.encode())
        r = subprocess.run([sys.executable, str(TOOL), "--version"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, universal_newlines=True, env=env, timeout=20)
        check("config-version-survives %r" % text[:40], r.returncode == 0 and r.stdout == "switchboard %s\n" % sb.VERSION
              and not r.stderr, (r.returncode, r.stderr[-200:]))
    # In range, a fraction is kept as it is (it used to be truncated to an integer).
    (d / "half.toml").write_text("[refresh]\ncache_max_age = 0.5\nlocal_seconds = 0.2\nremote_timeout = 120\n")
    cfg, warn = sb.load_config(str(d / "half.toml"), use_tomllib=False)
    check("config-fraction-kept", warn is None and cfg["refresh"]["cache_max_age"] == 0.5
          and cfg["refresh"]["local_seconds"] == 0.2 and cfg["refresh"]["remote_timeout"] == 120.0, (cfg, warn))
    # Whatever goes wrong inside, loading still returns the defaults and a warning.
    saved_merge = sb.merge_config
    sb.merge_config = lambda raw: 1 / 0
    try:
        cfg, warn = sb.load_config(str(d / "half.toml"), use_tomllib=False)
        check("config-unexpected-error-is-defaults", cfg == sb.DEFAULTS and bool(warn), (cfg, warn))
    finally:
        sb.merge_config = saved_merge
    # The refresh loops never see a non-finite interval, from the file or the environment.
    os.environ["SWITCHBOARD_LOCAL_EVERY"] = "nan"
    try:
        sb.configure(sb.merge_config({})[0])
        check("env-nan-ignored", sb.LOCAL_EVERY == sb.DEFAULTS["refresh"]["local_seconds"], sb.LOCAL_EVERY)
    finally:
        del os.environ["SWITCHBOARD_LOCAL_EVERY"]
        sb.configure(sb.load_config()[0])
        sb.LOCAL_EVERY, sb.REMOTE_EVERY = 0.05, 0.05

# The same bytes read the same through both parsers: only \n ends a line.
SAME = [
    ("# note [jump]\nenabled = true\n", {"enabled": True}),
    ("# a\u0085b\nlang = \"es\"\n", {"lang": "es"}),
    ("lang = \"es\"\r\nlocal_label = \"x\"\r\n", {"lang": "es", "local_label": "x"}),
    ("lang = \"a\tb\"\n", {"lang": "a\tb"}),
    ("# a\x0bb\n", None),
    ("# a\x0cb\n", None),
    ("# a\x1cb\n", None),
    ("x = 1 # a\x7fb\n", None),
    ("lang = \"es\"\rlocal_label = \"x\"\n", None),
    ("[jump]\nenabled = true\r", None),
    ("[jump]\nenabled = true\r\n", {"jump": {"enabled": True}}),
    (" lang = \"es\"\n", None),
    ("lang = \"es\" \n", None),
    ("[jump] enabled = true\n", None),
    ("lang = \"e\x01s\"\n", None),
]
for text, want in SAME:
    for use in PARSERS:
        try:
            got = sb.toml_loads(text, use_tomllib=use)
        except ValueError:
            got = None
        check("parsers-agree %r (tomllib=%s)" % (text, use), got == want, got)
# A [jump] table hidden behind U+2028 in a comment does not reach the jump (on by default).
cfg, problems = sb.merge_config(sb.toml_loads("# note [jump]\nenabled = false\n", use_tomllib=False))
check("hidden-line-break-does-not-reach-the-jump", cfg["jump"] == sb.DEFAULTS["jump"] and problems,
      (cfg["jump"], problems))
special = sb.toml_loads("a = inf\nb = -inf\nc = nan\n", use_tomllib=False)
check("builtin-reads-special-floats", special["a"] == float("inf") and special["b"] == float("-inf")
      and special["c"] != special["c"], special)

# 28. Colours fzf accepts, and a popup that never vanishes on an fzf error.
block('28. Colours fzf accepts, and a popup that never vanishes on an fzf error')
for v in ("magenta", "bright-black", "bright-white", "gray", "grey", "0", "16", "99", "255", "-1", "#bd93f9"):
    check("color-accepted %s" % v, sb.COLOR_VALUE.fullmatch(v) is not None)
for v in ("purple", "256", "999", "01", "#bd93f", "Magenta", "bright-gray", "", "-2", "red,blue"):
    check("color-refused %r" % v, sb.COLOR_VALUE.fullmatch(v) is None)
cfg, problems = sb.merge_config({"colors": {"accent": "purple", "muted": "999", "selected_bg": "blue"}})
check("color-bad-value-is-default", cfg["colors"]["accent"] == "magenta" and cfg["colors"]["muted"] == "bright-black"
      and cfg["colors"]["selected_bg"] == "blue" and len(problems) == 2, (cfg["colors"], problems))
for v in ("", "info:8", "dark,fg+:#282a36:bold", "bogus"):
    check("fzf-spec-shape-ok %r" % v, sb.FZF_COLOR_SPEC.fullmatch(v) is not None)
for v in ("a b", "x,,y", ",x", "hl:x(y)", "hl:magenta;rm"):
    check("fzf-spec-shape-refused %r" % v, sb.FZF_COLOR_SPEC.fullmatch(v) is None)
with tempfile.TemporaryDirectory() as d:
    d = pathlib.Path(d)
    # An fzf that refuses any colour spec mentioning "bogus", as the real one does.
    picky = executable(d / "fzf-picky", '#!/bin/sh\ncase "$*" in\n  --version) echo "0.74.0 (test)" ;;\n'
                                        '  *bogus*) echo "invalid color specification: bogus" >&2; exit 2 ;;\n'
                                        '  *) exit 1 ;;\nesac\n')
    check("fzf-rejects-reports", sb.fzf_rejects(str(picky), ["--color", "bogus"]) == "invalid color specification: bogus")
    check("fzf-rejects-accepts", sb.fzf_rejects(str(picky), ["--color", "hl:magenta"]) is None)
    saved = (dict(sb.COLORS), sb.CONFIG_WARNING)
    try:
        sb.COLORS = dict(sb.DEFAULTS["colors"], fzf="bogus")
        sb.CONFIG_WARNING = None
        note = sb.verify_colors(str(picky))
        check("colors-refused-by-fzf-fall-back", note and sb.COLORS == sb.DEFAULTS["colors"]
              and note in sb.header([], [], [], []), (note, sb.COLORS))
        sb.COLORS = dict(sb.DEFAULTS["colors"], fzf="info:8")
        check("colors-taken-by-fzf-kept", sb.verify_colors(str(picky)) is None and sb.COLORS["fzf"] == "info:8")
    finally:
        sb.COLORS, sb.CONFIG_WARNING = saved
    if fzf_real and not sb.dependency_problems(python=(3, 12, 0), fzf=fzf_real):
        check("real-fzf-refuses-an-unknown-colour", "purple" in (sb.fzf_rejects(fzf_real, ["--color", "hl:purple"]) or ""))
        check("real-fzf-takes-the-default-colours", sb.fzf_rejects(fzf_real, ["--color", sb.fzf_colors(sb.DEFAULTS["colors"])])
              is None)
        argv = sb.fzf_argv(fzf_real, "self", "/tmp/s.sock", remote_enter=True)
        check("real-fzf-takes-the-whole-command-line", sb.fzf_rejects(fzf_real, [a for a in argv[1:]
                                                                                  if not a.startswith("--listen")]) is None)
    # End to end: an fzf that exits 2 on the real command line; the popup explains and waits.
    broken = executable(d / "fzf-broken", '#!/bin/sh\n[ "$1" = --version ] && { echo "0.74.0 (test)"; exit 0; }\n'
                                          'echo "unknown action: whatever" >&2; exit 2\n')
    snapfile = d / "snap.json"
    snapfile.write_text(json.dumps({"result": {"snapshot": snap([pane("w1:p1")], [agent("w1:p1", "idle", 1)])}}))
    fh = executable(d / "herdr", '#!/bin/sh\ncase "$*" in\n  "api snapshot") cat "%s" ;;\n'
                                 '  "machine list --json") echo "[]" ;;\n  *) exit 2 ;;\nesac\n' % snapfile)
    env = dict(os.environ, SWITCHBOARD_FZF=str(broken), HERDR_BIN_PATH=str(fh))
    r = subprocess.run([sys.executable, str(TOOL)], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, universal_newlines=True, env=env, timeout=30)
    check("fzf-error-is-shown-not-swallowed", r.returncode != 0 and "fzf could not start: unknown action: whatever"
          in r.stdout and "Press Enter" in r.stdout, (r.returncode, r.stdout[-300:], r.stderr[-300:]))

# 29. Untrusted snapshot text.
block('29. Untrusted snapshot text')
EVIL = {
    "workspaces": [{"workspace_id": "w1", "label": "ws\tx\x1b]0;title\x07", "number": "1"},
                   {"workspace_id": ["list"], "label": "odd"}],
    "tabs": [{"tab_id": "w1:t1", "label": "t\x00ab", "number": 1}],
    "panes": [
        {"pane_id": "w1:p1", "tab_id": "w1:t1", "workspace_id": "w1", "label": "\x1b[31mred\x1b]52;c;QUFB\x07",
         "terminal_title_stripped": "x", "cwd": "/tmp/\x07bell"},
        {"pane_id": "w1:p2", "tab_id": "w1:t1", "workspace_id": "w1",
         "terminal_title_stripped": "x\nevil|a|--help|w9:t9\tforged", "cwd": "/tmp"},
        {"pane_id": "--help", "tab_id": "w1:t1", "workspace_id": "w1", "terminal_title_stripped": "dash id"},
        {"pane_id": "w1:p|3", "tab_id": "w1:t1", "workspace_id": "w1", "terminal_title_stripped": "pipe id"},
        {"pane_id": "w1:p4", "tab_id": "w1:t1\n", "workspace_id": "w1", "terminal_title_stripped": "newline tab"},
        {"pane_id": "w1:p5", "tab_id": "w1:t1", "workspace_id": ["list"], "terminal_title_stripped": "list ws"},
        "not a dict",
    ],
    "agents": [{"pane_id": "w1:p1", "agent": "codex\x1b[2J", "agent_status": ["blocked"], "state_change_seq": "9",
                "completion_seq": True},
               {"pane_id": "w1:p2", "agent": "claude", "agent_status": "idle", "state_change_seq": 4,
                "terminal_title_stripped": "x\nevil|a|--help|w9:t9\tforged"}],
}
try:
    evil = sb.entries_from(EVIL, "m1", "box\x1b[31m1\n", 1)
    text = sb.render(evil, [{"id": "m1", "label": "box1"}], pending=["lo\x1bading"], down=["dow\nn"])
except Exception as exc:
    evil, text = [], ""
    check("evil-snapshot-does-not-crash", False, repr(exc))
lines = text.splitlines()
check("evil-only-safe-panes", sorted(e["pane"] for e in evil) == ["w1:p1", "w1:p2", "w1:p5"], [e["pane"] for e in evil])
check("evil-list-is-not-a-label", all("[" not in e["ws_label"] for e in evil), [e["ws_label"] for e in evil])
check("safe-id-no-trailing-newline", not sb.safe_id("w1:t1\n") and sb.safe_id("w1:t1"))
check("evil-one-line-per-row", len(lines) == 1 + len(evil) + 1, lines)
check("evil-no-forged-row", all(l.startswith("-\t") or sb.parse_id(l.split("\t", 1)[0]) for l in lines)
      and not any(l.startswith("evil|") for l in lines), lines)
check("evil-no-escape-or-control", not re.search(r"[\x00-\x08\x0a-\x1f\x7f-\x9f]", text.replace("\n", "").replace("\t", "")),
      repr(text[:300]))
check("evil-text-kept-plain", "box1" in text and "red" in text and "codex" in text and "forged" in text, text)
check("evil-wrong-types", [(e["status"], e["seq"], e["completion"]) for e in evil if e["pane"] == "w1:p1"]
      == [("unknown", 0, None)], [(e["status"], e["seq"], e["completion"]) for e in evil])
check("parse-id-refuses-option-like", sb.parse_id("|a|--help|w9:t9") is None and sb.parse_id("-x|a|w1:p1|w1:t1") is None
      and sb.parse_id("|a|w1:p1|w1:t1") is not None)
check("evil-machine-id-refused", sb.entries_from(snap([pane("w1:p1")], []), "--machine", "x", 1) == [])
saved_warning = sb.CONFIG_WARNING
sb.CONFIG_WARNING = "config: bad\x1b[2J\x07 value"
try:
    check("warning-cleaned-in-header", "\x1b" not in sb.header([], [], [], []) and "bad value" in sb.header([], [], [], []))
finally:
    sb.CONFIG_WARNING = saved_warning
screen_in = "a\x1b[31mred\x1b[0m\x1b]52;c;QUFB\x07\x1b[2J\x07\rb\tc\x1bPq#0\x1b\\d\n"
check("preview-keeps-only-colours", sb.clean_screen(screen_in) == "a\x1b[31mred\x1b[0mb\tcd\n", repr(sb.clean_screen(screen_in)))
with tempfile.TemporaryDirectory() as d:
    d = pathlib.Path(d)
    (d / "machines.json").write_text(json.dumps([
        {"id": "m1", "label": "box\x1b[31m1\n", "enabled": True}, {"id": "-x", "label": "dash", "enabled": True},
        {"id": ["l"], "label": "list", "enabled": True}, {"id": "m2", "label": "", "enabled": True}, "junk"]))
    (d / "screen.txt").write_text(screen_in)
    fh = executable(d / "herdr", '#!/bin/sh\ncase "$*" in\n  "machine list --json") cat "%(d)s/machines.json" ;;\n'
                                 '  *"pane read"*) cat "%(d)s/screen.txt" ;;\n  *) exit 2 ;;\nesac\n' % {"d": d})
    saved_herdr = sb.HERDR
    sb.HERDR = str(fh)
    try:
        ms = sb.saved_machines()
        check("machines-cleaned", [(m["id"], m["label"]) for m in ms] == [("m1", "box1"), ("m2", "m2")], ms)
    finally:
        sb.HERDR = saved_herdr
    r = subprocess.run([sys.executable, str(TOOL), "--preview", "|a|w1:p1|w1:t1"], stdin=subprocess.DEVNULL,
                       stdout=subprocess.PIPE, universal_newlines=True, env=dict(os.environ, HERDR_BIN_PATH=str(fh)),
                       timeout=20)
    check("preview-e2e-no-osc", "\x1b]52" not in r.stdout and "\x1b[2J" not in r.stdout and "\x1b[31mred" in r.stdout,
          repr(r.stdout))
calls = []
orig = (sb.run_out, sb.ghostty_tty, sb.time.sleep, sb.local_label)
sb.run_out = lambda argv, timeout=5: calls.append(argv[1:]) or ""
sb.ghostty_tty = lambda ps_text=None: None
sb.time.sleep = lambda s: None
sb.local_label = lambda: "mac1"


class _QuietOsa:
    def communicate(self, data, timeout=None):
        pass

    def kill(self):
        pass


try:
    sb.jump("box1", "a", "w1:p1", "w1:t1", "sbjabc", True, "-logs", tty="/dev/ttys000", osa=_QuietOsa())
    # herdr 0.9.5 keeps a "--" as part of the label, so a dash-leading label goes as it is.
    check("jump-dash-label-as-is", ["--machine", "box1", "pane", "rename", "w1:p1", "-logs"] in calls, calls)
finally:
    sb.run_out, sb.ghostty_tty, sb.time.sleep, sb.local_label = orig

# 30. ssh destinations.
block('30. ssh destinations')
argv = sb.ssh_argv("mac1", "uname -s", mux=False)
check("ssh-double-dash-before-host", argv and argv[-3:] == ["--", "mac1", "uname -s"], argv)
for bad in ("-oProxyCommand=touch /tmp/x", "-x", "", "mac 1", "mac1\n", "mac\x001", None, ["mac1"]):
    check("ssh-destination-refused %r" % (bad,), sb.ssh_argv(bad, "cmd") is None and not sb.valid_host(bad))
check("only-ssh-argv-builds-ssh-commands", SOURCE.count("[SSH]") == 1, SOURCE.count("[SSH]"))
with tempfile.TemporaryDirectory() as d:
    d = pathlib.Path(d)
    log = d / "ssh-log"
    fs = executable(d / "ssh", '#!/bin/sh\nprintf "%%s\\037" "$@" >> "%s"\nprintf "\\n" >> "%s"\n'
                               'case "$*" in *"plugin list"*) echo \'{"result":{"plugins":[]}}\' ;; esac\nexit 0\n'
                    % (log, log))
    fh = executable(d / "herdr", '#!/bin/sh\necho "$*" >> "%s/herdr-log"\necho "{\\"result\\":{\\"snapshot\\":{}}}"\n' % d)
    saved = (sb.SSH, sb.HERDR, sb.JUMP_HELPER)
    sb.SSH, sb.HERDR, sb.JUMP_HELPER = str(fs), str(fh), ""
    try:
        sb.herdr_on("m1", ["api", "snapshot"], 5, {"id": "m1", "target": "mac1"})
        sb.answers_as_mac("mac1")
        sb.idle_seconds("mac1")
        sb.resolve_helper("mac1")
        link = sb.JumpLink(find=lambda: ("ssh", "mac1"), helper=lambda h: "sb-helper").start()
        link.started.wait(5)
        link.proc.wait(5)
        orig_popen = sb.subprocess.Popen
        sb.subprocess.Popen = lambda argv, **kw: orig_popen(argv, **kw).wait(20) and None
        try:
            sb.launch_jump(["--jump"] * 8, ("ssh", "mac1"), helper="sb-helper")
        finally:
            sb.subprocess.Popen = orig_popen
        calls = [l.rstrip("\x1f").split("\x1f") for l in log.read_text().splitlines() if l]
        check("ssh-all-six-call-kinds-logged", len(calls) == 6, calls)
        check("ssh-every-call-double-dash", calls and all(c[c.index("mac1") - 1] == "--" for c in calls), calls)
        log.write_text("")
        # Malicious destinations: never handed to ssh.
        got = sb.herdr_on("m1", ["api", "snapshot"], 5, {"id": "m1", "target": "-oProxyCommand=touch x"})
        check("ssh-dash-target-falls-back-to-machine", "--machine m1 api snapshot" in (d / "herdr-log").read_text(), got)
        probed = []
        check("ssh-dash-configured-client-refused", sb.find_client(configured="-oProxyCommand=x") is None)
        check("ssh-dash-tailscale-name-refused", sb.find_client([(1, "addr-1")], {"addr-1": ("-evil", "macOS")}, "",
                                                                platform="linux", configured="") is None)
        check("ssh-dash-bridge-address-not-probed", sb.find_client([(1, "-addr")], {}, "", platform="linux", configured="",
                                                                   is_mac=lambda h: probed.append(h) or True) is None
              and not probed, probed)
        check("ssh-dash-everywhere-refused", sb.answers_as_mac("-x") is False and sb.idle_seconds("-x") == float("inf")
              and sb.resolve_helper("-x") is None
              and sb.launch_jump(["--jump"] * 8, ("ssh", "-x"), helper="sb-helper") is False)
        dash_link = sb.JumpLink(find=lambda: ("ssh", "-x"), helper=lambda h: "sb-helper").start()
        check("ssh-dash-link-does-not-connect", dash_link.started.wait(5) and dash_link.proc is None
              and dash_link.send(["--jump"] * 8) is False)
        check("ssh-nothing-ran-for-bad-destinations", log.read_text() == "", log.read_text())
    finally:
        sb.SSH, sb.HERDR, sb.JUMP_HELPER = saved

# 31. A remote Enter that never blocks, acks that are never lost, a quiet close.
block('31. A remote Enter that never blocks, acks that are never lost, a quiet cl')
check("fzf-action-plain", sb.fzf_action("execute", "a --b {1}") == "execute(a --b {1})")
check("fzf-action-avoids-its-delimiter", sb.fzf_action("execute", "/opt/my (x)/sb {1}") == "execute[/opt/my (x)/sb {1}]")
check("fzf-action-none-when-impossible", sb.fzf_action("x", "".join(sb.FZF_DELIMITERS)) is None)
with tempfile.TemporaryDirectory() as d:
    d = pathlib.Path(d)
    sb.STATE_DIR = str(d / "state")
    m1 = [{"id": "m1", "label": "box1"}]
    vivid = {"local": snap17(T1, ag17("p1", "working", 1, T1)), "m1": snap17(T1, ag17("p9", "working", 1, T1))}
    # No snapshot cache: the watch loop's threads would otherwise still be writing it into this
    # temporary directory while it is removed.
    lv = sb.Live(m1, sb.entries_from(vivid["local"], "", "here", 0), fetch=lambda m="", t=None, i=None: vivid[m or "local"],
                 focus=T1, cache=False)
    # A --focus that appends exactly while the file is being removed: its line must survive.
    acks = d / "acks"
    acks.write_text(json.dumps(["m1", T1]) + "\n")
    real_remove = sb.os.remove

    def racing_remove(path, **kw):
        with open(str(acks), "a") as f:
            f.write(json.dumps(["m1", "w1:t2"]) + "\n")
        real_remove(path, **kw)
    sb.os.remove = racing_remove
    try:
        lv.consume_acks(str(acks))
    finally:
        sb.os.remove = real_remove
    left = acks.read_text().splitlines() if acks.exists() else []
    check("acks-written-during-consume-survive", left == ['["m1", "w1:t2"]'], left)
    check("acks-no-private-leftovers", sorted(x.name for x in d.iterdir() if x.name.startswith("acks.")) == [])
    # watch() keeps quiet when the popup removes its directory under it.
    errors = []
    saved_hook = sb.threading.excepthook
    sb.threading.excepthook = lambda a: errors.append(a.exc_type.__name__)
    try:
        gone = d / "gone"
        gone.mkdir(mode=0o700)
        gone.chmod(0o700)
        sock = short_sock("q")
        FakeFzf(sock)
        stop = _threading.Event()
        lv.changed()
        writes31 = _threading.Lock()  # as the popup does: the directory goes only while no rows write runs
        t = _threading.Thread(target=sb.watch, args=(lv, sock, str(gone / "rows"), stop, None, writes31), daemon=True)
        t.start()
        with writes31:
            shutil.rmtree(str(gone))
        vivid["local"] = snap17(T1, ag17("p1", "blocked", 7, T1))
        _time.sleep(0.4)
        stop.set()
        t.join(3)
    finally:
        sb.threading.excepthook = saved_hook
    check("watch-survives-a-removed-directory", not errors and not t.is_alive(), errors)
    sb.STATE_DIR = STATE

if fzf_real and not sb.dependency_problems(python=(3, 12, 0), fzf=fzf_real):
    with tempfile.TemporaryDirectory() as d:
        d = pathlib.Path(d)
        (d / "local.json").write_text(json.dumps({"result": {"snapshot": snap([pane("w1:p1")], [agent("w1:p1", "idle", 1)])}}))
        (d / "m1.json").write_text(json.dumps({"result": {"snapshot": snap([pane("w1:p7")],
                                                                          [agent("w1:p7", "blocked", 5, title="remote-task")])}}))
        (d / "machines.json").write_text(json.dumps([{"id": "m1", "label": "box1", "enabled": True}]))
        fh = executable(d / "herdr", '#!/bin/sh\necho "$*" >> "%(d)s/log"\ncase "$*" in\n'
                                     '  "machine list --json") cat "%(d)s/machines.json" ;;\n'
                                     '  "api snapshot") cat "%(d)s/local.json" ;;\n'
                                     '  "--machine m1 api snapshot") cat "%(d)s/m1.json" ;;\n'
                                     '  "--machine m1 agent focus"*) exec sleep 2 ;;\n'
                                     '  *"pane read"*) echo "pane text" ;;\n'
                                     '  *) exit 0 ;;\nesac\n' % {"d": d})
        pid, fd = _pty.fork()
        if pid == 0:
            os.environ.update(TERM="xterm-256color", HERDR_BIN_PATH=str(fh), HERDR_PLUGIN_STATE_DIR=str(d / "state"))
            os.execv(sys.executable, [sys.executable, "-B", str(TOOL)])
        import fcntl as _f3
        import struct as _st3
        import termios as _tm3
        _f3.ioctl(fd, _tm3.TIOCSWINSZ, _st3.pack("HHHH", 40, 180, 0, 0))
        buf, marks, rc, end = b"", {}, None, _time.time() + 25
        while _time.time() < end:
            r, _, _ = _sel.select([fd], [], [], 0.05)
            if r:
                try:
                    chunk = os.read(fd, 65536)
                except OSError:
                    chunk = b""
                if not chunk:
                    rc, fd = finish(pid, fd, 5), None  # finish closed it
                    break
                buf += chunk
            plain = sb.ANSI.sub("", buf.decode("utf-8", "replace"))
            if "enter" not in marks and "remote-task" in plain:
                _time.sleep(0.5)
                os.write(fd, b"\r")
                marks["enter"] = _time.time()
            if "enter" in marks and "focusing" not in marks and "focusing it on box1" in plain:
                marks["focusing"] = _time.time()
            if "focusing" in marks and "ready" not in marks and "ready on box1" in plain:
                marks["ready"] = _time.time()
                os.write(fd, b"\x1b")
        if fd is not None:  # each descriptor is closed once
            finish(pid, fd, 0)
        check("enter-pty-footer-at-once", "focusing" in marks and marks["focusing"] - marks["enter"] < 1.5, marks)
        check("enter-pty-focus-arrives-later", "ready" in marks and marks["ready"] - marks["enter"] >= 1.5, marks)
        check("enter-pty-popup-stays-then-esc", rc == 0, rc)
        check("enter-pty-focused-through-herdr", "--machine m1 agent focus w1:p7" in (d / "log").read_text())

# 32. Enter on a remote row, then Esc at once: the focus still happens, the ack is kept.
block('32. Enter on a remote row, then Esc at once: the focus still happens, the ')
if fzf_real and not sb.dependency_problems(python=(3, 12, 0), fzf=fzf_real):
    with tempfile.TemporaryDirectory() as d:
        d = pathlib.Path(d)
        (d / "local.json").write_text(json.dumps({"result": {"snapshot": snap([pane("w1:p1")], [agent("w1:p1", "idle", 1)])}}))
        remote_agent = dict(agent("w1:p7", "idle", 5, title="remote-done"), completion_seq=5)
        (d / "m1.json").write_text(json.dumps({"result": {"snapshot": snap([pane("w1:p7")], [remote_agent])}}))
        (d / "machines.json").write_text(json.dumps([{"id": "m1", "label": "box1", "enabled": True}]))
        state = d / "state"
        state.mkdir()
        # The ledger says the remote agent finished something not seen yet: the row shows done.
        (state / "recency.json").write_text(json.dumps({"v": 2, "machines": {"m1": {"w1:p7": [5, 1000.0, 0, 4, -1]}},
                                                        "focus": {}}))
        fh = executable(d / "herdr", '#!/bin/sh\ncase "$*" in\n'
                                     '  "machine list --json") cat "%(d)s/machines.json" ;;\n'
                                     '  "api snapshot") cat "%(d)s/local.json" ;;\n'
                                     '  "--machine m1 api snapshot") cat "%(d)s/m1.json" ;;\n'
                                     '  "--machine m1 agent focus"*) sleep 2; touch "%(d)s/focused" ;;\n'
                                     '  *"pane read"*) echo "pane text" ;;\n'
                                     '  *) exit 0 ;;\nesac\n' % {"d": d})
        pid, fd = _pty.fork()
        if pid == 0:
            os.environ.update(TERM="xterm-256color", HERDR_BIN_PATH=str(fh), HERDR_PLUGIN_STATE_DIR=str(state))
            os.execv(sys.executable, [sys.executable, "-B", str(TOOL)])
        import fcntl as _f4
        import struct as _st4
        import termios as _tm4
        _f4.ioctl(fd, _tm4.TIOCSWINSZ, _st4.pack("HHHH", 40, 180, 0, 0))
        buf, sent, rc, exited_at, end = b"", set(), None, None, _time.time() + 25
        while _time.time() < end:
            r, _, _ = _sel.select([fd], [], [], 0.05)
            if r:
                try:
                    chunk = os.read(fd, 65536)
                except OSError:
                    chunk = b""
                if not chunk:
                    rc, exited_at, fd = finish(pid, fd, 5), _time.time(), None  # finish closed it
                    break
                buf += chunk
            plain = sb.ANSI.sub("", buf.decode("utf-8", "replace"))
            if "enter" not in sent and "remote-done" in plain and "● done" in plain:
                _time.sleep(0.5)
                os.write(fd, b"\r")
                sent.add("enter")
            if "enter" in sent and "esc" not in sent and "focusing it on box1" in plain:
                os.write(fd, b"\x1b")
                sent.add("esc")
        if fd is not None:  # each descriptor is closed once
            finish(pid, fd, 0)
        check("close-after-enter-exits-at-once", rc == 0 and "esc" in sent and not (d / "focused").exists(),
              (rc, sorted(sent), (d / "focused").exists()))
        waited = 0.0
        while waited < 5 and not (d / "focused").exists():
            _time.sleep(0.1)
            waited += 0.1
        check("close-after-enter-focus-still-happens", (d / "focused").exists(), waited)
        try:
            ledger = json.loads((state / "recency.json").read_text())["machines"]["m1"]["w1:p7"]
        except (OSError, ValueError, KeyError) as exc:
            ledger = repr(exc)
        check("close-after-enter-ack-kept", isinstance(ledger, list) and ledger[3] == 5, ledger)

# 33. Malformed snapshots everywhere.
block('33. Malformed snapshots everywhere')
BAD_SNAPSHOTS = ['{"result":{"snapshot":[]}}', "[]", '{"result":[]}', '"x"', '{"result":{"snapshot":"x"}}', "null",
                 '{"result":{"snapshot":null}}', "not json", "{}"]
with tempfile.TemporaryDirectory() as d:
    d = pathlib.Path(d)
    out_file = d / "out.json"
    fh = executable(d / "herdr", '#!/bin/sh\ncat "%s"\n' % out_file)
    saved_herdr = sb.HERDR
    sb.HERDR = str(fh)
    try:
        for raw in BAD_SNAPSHOTS:
            out_file.write_text(raw)
            try:
                sb.snapshot()
                check("snapshot-refuses %r" % raw, False)
            except ValueError:
                pass
            except Exception as exc:
                check("snapshot-refuses-with-valueerror %r" % raw, False, repr(exc))
        out_file.write_text(json.dumps({"result": {"snapshot": {"focused_tab_id": ["x"], "panes": "x", "agents": {}}}}))
        odd = sb.snapshot()
        check("snapshot-odd-fields-survive", sb.focused_tab(odd) is None and sb.entries_from(odd) == [], odd)
    finally:
        sb.HERDR = saved_herdr
check("focused-tab-only-a-string", sb.focused_tab({"focused_tab_id": "w1:t1"}) == "w1:t1"
      and sb.focused_tab({"focused_tab_id": 3}) is None and sb.focused_tab([]) is None)

# The two refresh paths take any value from fetch without raising, and a bad value is no answer.
# Neither title may contain the other, or one half of the check could never fail.
good_local = snap([pane("w1:p1")], [agent("w1:p1", "working", 1, title="alpha-local")])
good_remote = snap([pane("w1:p2")], [agent("w1:p2", "idle", 1, title="omega-remote")])
feed = {"local": good_local, "m1": good_remote}


def fetch33(machine="", timeout=None, info=None):
    v = feed[machine or "local"]
    if isinstance(v, BaseException):
        raise v
    return v


lv = sb.Live([{"id": "m1", "label": "box1"}], sb.entries_from(good_local, "", "here", 0), fetch=fetch33, cache=False)
lv.refresh_remote(0, {"id": "m1", "label": "box1"})
for bad in ([], "x", None, 7, b"x", TypeError("odd"), KeyError("odd")):
    feed["local"], feed["m1"] = bad, bad
    try:
        lv.refresh_local()
        lv.refresh_remote(0, {"id": "m1", "label": "box1"})
        text = lv.text()
        check("refresh-bad-value-keeps-last-rows %r" % (bad,), "alpha-local" in text and "omega-remote" in text, text)
    except Exception as exc:
        check("refresh-never-raises %r" % (bad,), False, repr(exc))
lv2 = sb.Live([{"id": "m1", "label": "box1"}], [], fetch=lambda m="", t=None, i=None: [], cache=False)
lv2.refresh_remote(0, {"id": "m1", "label": "box1"})
check("refresh-malformed-first-answer-is-offline", "box1 offline" in lv2.text(), lv2.text())

# Neither watch loop can die, whatever a pass hits.
errors = []
saved_hook = sb.threading.excepthook
sb.threading.excepthook = lambda a: errors.append(a.exc_type.__name__)
try:
    with tempfile.TemporaryDirectory(dir="/tmp") as d:
        sock = short_sock("x")
        FakeFzf(sock)
        feed["local"], feed["m1"] = good_local, good_remote
        lv3 = sb.Live([{"id": "m1", "label": "box1"}], sb.entries_from(good_local, "", "here", 0), fetch=fetch33,
                      cache=False)
        calls33 = {"remote": 0, "local": 0}

        def broken_remote(i, m):
            calls33["remote"] += 1
            raise RuntimeError("remote pass")

        def broken_changed():
            calls33["local"] += 1
            raise AttributeError("local pass")
        lv3.refresh_remote = broken_remote
        lv3.changed = broken_changed
        stop = _threading.Event()
        t = _threading.Thread(target=sb.watch, args=(lv3, sock, os.path.join(d, "rows"), stop, None), daemon=True)
        t.start()
        _time.sleep(0.5)
        alive = t.is_alive()
        stop.set()
        t.join(3)
    check("watch-loops-survive-any-error", not errors and alive and calls33["remote"] > 2 and calls33["local"] > 2,
          (errors, alive, calls33))
finally:
    sb.threading.excepthook = saved_hook

# End to end: a malformed remote is offline in --rows, a malformed local is a message, never a traceback.
with tempfile.TemporaryDirectory() as d:
    d = pathlib.Path(d)
    (d / "machines.json").write_text(json.dumps([{"id": "m1", "label": "box1", "enabled": True}]))
    (d / "local.json").write_text(json.dumps({"result": {"snapshot": good_local}}))
    (d / "bad.json").write_text('{"result":{"snapshot":[]}}')
    fh = executable(d / "herdr", '#!/bin/sh\ncase "$*" in\n  "machine list --json") cat "%(d)s/machines.json" ;;\n'
                                 '  "api snapshot") cat "%(d)s/${LOCAL_FILE:-local.json}" ;;\n'
                                 '  "--machine m1 api snapshot") cat "%(d)s/bad.json" ;;\n  *) exit 2 ;;\nesac\n' % {"d": d})
    env = dict(os.environ, HERDR_BIN_PATH=str(fh), SWITCHBOARD_REMOTE_TIMEOUT="2")
    r = subprocess.run([sys.executable, str(TOOL), "--rows"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, universal_newlines=True, env=env, timeout=30)
    check("rows-malformed-remote-is-offline", r.returncode == 0 and "box1 offline" in r.stdout and not r.stderr,
          (r.returncode, r.stdout[:200], r.stderr[-300:]))
    r = subprocess.run([sys.executable, str(TOOL), "--rows"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, universal_newlines=True, env=dict(env, LOCAL_FILE="bad.json"), timeout=30)
    check("rows-malformed-local-is-a-message", r.returncode == 1 and "herdr api snapshot failed" in r.stderr
          and "Traceback" not in r.stderr, (r.returncode, r.stderr[-300:]))
    fzf_ok = executable(d / "fzf", '#!/bin/sh\nif [ "$1" = --version ]; then echo "0.74.0 (test)"; exit 0; fi\nexit 1\n')
    r = subprocess.run([sys.executable, str(TOOL)], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, universal_newlines=True,
                       env=dict(env, LOCAL_FILE="bad.json", SWITCHBOARD_FZF=str(fzf_ok)), timeout=30)
    check("popup-malformed-local-is-a-message", r.returncode == 1 and "herdr api snapshot failed" in r.stdout
          and "Traceback" not in r.stderr, (r.returncode, r.stdout[-200:], r.stderr[-300:]))

# 34. The selection viewer tells a split arrow key from a lone Esc.
block('34. The selection viewer tells a split arrow key from a lone Esc')
def viewer_alive_after(chunks, gap):
    """Run --select in a pty, write the chunks `gap` seconds apart, and say whether the viewer
    is still running 0.4 s later; then quit it."""
    with tempfile.TemporaryDirectory() as d:
        d = pathlib.Path(d)
        (d / "pane.txt").write_text("\n".join("line %d" % i for i in range(60)) + "\n")
        fake = executable(d / "herdr", '#!/bin/sh\ncat "%s/pane.txt"\n' % d)
        pid, fd = _pty.fork()
        if pid == 0:
            os.environ.update(HERDR_BIN_PATH=str(fake), TERM="xterm-256color")
            os.execv(sys.executable, [sys.executable, "-B", str(TOOL), "--select", "|a|w1:p1|w1:t1"])
        import fcntl as _f5
        import struct as _st5
        import termios as _tm5
        _f5.ioctl(fd, _tm5.TIOCSWINSZ, _st5.pack("HHHH", 10, 40, 0, 0))

        seen = [b""]

        def drain(sec, until=None):
            end = _time.time() + sec
            while _time.time() < end:
                r, _, _ = _sel.select([fd], [], [], 0.02)
                if r:
                    try:
                        seen[0] += os.read(fd, 65536)
                    except OSError:
                        return
                if until and until in seen[0]:
                    return
        # Keys only after the viewer's first frame: it switches the terminal to raw mode just
        # before drawing it, and raw mode (TCSAFLUSH) throws away anything typed earlier.
        drain(15.0, until=b"\x1b[?1049h")
        if b"\x1b[?1049h" not in seen[0]:
            finish(pid, fd, 0)
            return None
        for i, chunk in enumerate(chunks):
            if i:
                _time.sleep(gap)
            os.write(fd, chunk)
        drain(0.4)
        done, _ = os.waitpid(pid, os.WNOHANG)
        alive = done == 0
        if alive:
            os.write(fd, b"q")
        finish(pid, fd, 2)
        return alive


check("viewer-split-arrow-keeps-it-open", viewer_alive_after([b"\x1b", b"[A"], 0.02) is True)
check("viewer-lone-esc-closes-it", viewer_alive_after([b"\x1b"], 0) is False)

# 35. The run directory: descriptors, not names.
block('35. The run directory: descriptors, not names')
def private_tmp(base, name):
    path = os.path.join(base, name)
    os.mkdir(path, 0o700)
    os.chmod(path, 0o700)
    return path


def decoy_in(base):
    path = os.path.join(base, "victim")
    with open(path, "w") as f:
        f.write("precious\n")
    return path


with tempfile.TemporaryDirectory(dir="/tmp") as d:
    run = private_tmp(d, "run")
    fd = sb.open_private_dir(run)
    check("private-dir-opens", fd is not None)
    loose = os.path.join(d, "loose")
    os.mkdir(loose)
    os.chmod(loose, 0o755)
    link = os.path.join(d, "link-to-run")
    os.symlink(run, link)
    plain_file = os.path.join(d, "plain")
    open(plain_file, "w").close()
    check("private-dir-refuses-loose-mode", sb.open_private_dir(loose) is None)
    check("private-dir-refuses-a-symlink", sb.open_private_dir(link) is None)
    check("private-dir-refuses-a-file", sb.open_private_dir(plain_file) is None and sb.open_private_dir("") is None)
    real_getuid = sb.os.getuid
    sb.os.getuid = lambda: real_getuid() + 1
    try:
        check("private-dir-refuses-another-owner", sb.open_private_dir(run) is None and not sb.private_fd(fd))
    finally:
        sb.os.getuid = real_getuid

    check("write-new-writes", sb.write_new(fd, "res", "hello\n") and open(os.path.join(run, "res")).read() == "hello\n"
          and stat.S_IMODE(os.stat(os.path.join(run, "res")).st_mode) == 0o600)
    decoy = decoy_in(d)
    os.symlink(decoy, os.path.join(run, "planted.tmp"))
    check("write-new-never-follows-a-link", sb.write_new(fd, "planted", "x\n") is False
          and open(decoy).read() == "precious\n")
    os.symlink(decoy, os.path.join(run, "final"))
    check("write-new-replaces-a-link-not-its-target", sb.write_new(fd, "final", "mine\n")
          and open(decoy).read() == "precious\n" and not os.path.islink(os.path.join(run, "final")))
    os.symlink(decoy, os.path.join(run, "acks"))
    check("append-never-follows-a-link", sb.append_line(fd, "acks", "x") is False and open(decoy).read() == "precious\n")
    os.remove(os.path.join(run, "acks"))
    check("append-appends", sb.append_line(fd, "acks", "one") and sb.append_line(fd, "acks", "two")
          and open(os.path.join(run, "acks")).read() == "one\ntwo\n")
    os.symlink(decoy, os.path.join(run, "readlink"))
    os.mkfifo(os.path.join(run, "pipe"))
    check("read-refuses-links-and-reads-files", sb.read_small(fd, "readlink") is None
          and sb.read_small(fd, "res") == "hello\n")
    # The pipe in a thread with a deadline: a read that blocked would hang the whole suite.
    piped = []
    reader = _threading.Thread(target=lambda: piped.append(sb.read_small(fd, "pipe")), daemon=True)
    reader.start()
    reader.join(1.5)
    blocked = reader.is_alive()
    if blocked:  # release it: a writer lets the blocked open return
        try:
            os.close(os.open(os.path.join(run, "pipe"), os.O_WRONLY | os.O_NONBLOCK))
        except OSError:
            pass
        reader.join(2)
    check("read-never-blocks-on-a-pipe", not blocked and piped == [None], (blocked, piped))

    # The directory goes away and someone recreates it with links planted: nothing reaches them.
    shutil.rmtree(run)
    os.mkdir(run)
    os.symlink(decoy, os.path.join(run, "late.tmp"))
    os.symlink(decoy, os.path.join(run, "late"))
    check("write-new-in-a-removed-directory-writes-nothing", sb.write_new(fd, "late", "x\n") is False
          and open(decoy).read() == "precious\n" and sorted(os.listdir(run)) == ["late", "late.tmp"])
    check("append-in-a-removed-directory-writes-nothing", sb.append_line(fd, "acks", "x") is False
          and "acks" not in os.listdir(run))
    os.close(fd)

    # consume_acks: an acks file that is a link is read as nothing, and its target survives.
    acks_dir = private_tmp(d, "acks-dir")
    os.symlink(decoy, os.path.join(acks_dir, "acks"))
    lv = sb.Live([], [], fetch=lambda m="", t=None, i=None: snap([], []), cache=False)
    check("consume-acks-ignores-a-link", lv.consume_acks(os.path.join(acks_dir, "acks")) is False
          and open(decoy).read() == "precious\n")

    # watch(): a rows.tmp planted as a link is never written through.
    rows_dir = private_tmp(d, "rows-dir")
    os.symlink(decoy, os.path.join(rows_dir, "rows.tmp"))
    sock = short_sock("r")
    FakeFzf(sock)
    feed35 = {"n": 1}
    lv = sb.Live([], [], fetch=lambda m="", t=None, i=None: snap([pane("w1:p1")], [agent("w1:p1", "idle", feed35["n"])]),
                 cache=False)
    stop = _threading.Event()
    t = _threading.Thread(target=sb.watch, args=(lv, sock, os.path.join(rows_dir, "rows"), stop, None), daemon=True)
    t.start()
    _time.sleep(0.3)
    feed35["n"] = 2
    _time.sleep(0.3)
    stop.set()
    t.join(3)
    check("watch-rows-never-follow-a-link", open(decoy).read() == "precious\n")

# End to end: Enter, the popup's directory removed and recreated with links planted, the
# worker finishing afterwards. The decoy cannot change, and the focus still happens.
with tempfile.TemporaryDirectory(dir="/tmp") as d:
    run = private_tmp(d, "run")
    decoy = decoy_in(d)
    (pathlib.Path(d) / "machines.json").write_text(json.dumps([{"id": "m1", "label": "box1", "enabled": True}]))
    fh = executable(os.path.join(d, "herdr"), '#!/bin/sh\ncase "$*" in\n  "machine list --json") cat "%(d)s/machines.json" ;;\n'
                                             '  *"agent focus"*) { [ -n "${SWITCHBOARD_RUN_DIR+x}" ] && echo has_run_dir; '
                                             '[ -n "${SWITCHBOARD_RUN_FD+x}" ] && echo has_run_fd; '
                                             'env | grep -qF -- "%(run)s" && echo has_path; '
                                             'env | grep -q "^FZF_" && echo has_fzf; } > "%(d)s/worker-flags"; '
                                             'sleep 1.5; touch "%(d)s/focused" ;;\n'
                                             'esac\n' % {"d": d, "run": run})
    # --enter runs under fzf's transform, and fzf (0.66+) exports its state to it: FZF_SOCK
    # is the socket inside the run directory. Set the way fzf sets them.
    env = dict(os.environ, HERDR_BIN_PATH=str(fh), SWITCHBOARD_RUN_DIR=run, SWITCHBOARD_LABELS=json.dumps({"m1": "box1"}),
               FZF_SOCK=os.path.join(run, "fzf.sock"), FZF_QUERY="", FZF_ACTION="enter", FZF_KEY="enter",
               FZF_CURRENT_ITEM="m1|a|w1:p1|w1:t1\tbox1 row")
    out = subprocess.run([sys.executable, str(TOOL), "--enter", "m1|a|w1:p1|w1:t1"], stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE, universal_newlines=True, env=env, timeout=20).stdout
    m = re.search(r"--focus-wait (focus-[0-9]+-[0-9]+) ", out)
    check("attack-only-a-name-in-argv", m is not None and run not in out, out)
    name = m.group(1) if m else "focus-0-0"
    shutil.rmtree(run)
    os.mkdir(run)
    os.symlink(decoy, os.path.join(run, name + ".tmp"))
    os.symlink(decoy, os.path.join(run, name))
    waited = 0.0
    while waited < 8 and not os.path.exists(os.path.join(d, "focused")):
        _time.sleep(0.1)
        waited += 0.1
    _time.sleep(0.5)
    check("attack-focus-still-happens", os.path.exists(os.path.join(d, "focused")), waited)
    check("attack-decoy-unchanged", open(decoy).read() == "precious\n", open(decoy).read())
    check("attack-nothing-written-in-the-new-directory", sorted(os.listdir(run)) == sorted([name, name + ".tmp"]),
          os.listdir(run))
    # The fake herdr records yes/no flags, never the environment itself (it can hold secrets):
    # neither variable that names the directory, its path under no name at all, nothing of
    # fzf's. herdr runs with child_env(), so it does not see the descriptor's variable either.
    worker_flags = open(os.path.join(d, "worker-flags")).read().split() if os.path.exists(os.path.join(d, "worker-flags")) else None
    check("attack-worker-env-has-no-path", worker_flags == [], worker_flags)
    # And the worker's own environment, as enter() builds it (marks computed here, nothing kept).
    captured, run2 = [], private_tmp(d, "run2")
    saved_popen, saved_env, saved_out = sb.subprocess.Popen, dict(os.environ), sys.stdout
    os.environ.update(SWITCHBOARD_RUN_DIR=run2, FZF_SOCK=os.path.join(run2, "fzf.sock"), FZF_QUERY="x",
                      OTHER_HOLDS_IT="prefix:" + run2)
    sb.subprocess.Popen = lambda argv, **kw: captured.append(kw.get("env") or {}) or None
    sys.stdout = _io.StringIO()  # enter() prints fzf actions
    try:
        sb.enter("m1|a|w1:p1|w1:t1")
    finally:
        sb.subprocess.Popen, sys.stdout = saved_popen, saved_out
        os.environ.clear()
        os.environ.update(saved_env)
    marks = [("fzf" if any(k.startswith("FZF_") for k in e) else "")
             + ("path" if any(run2 in v for v in e.values()) else "")
             + ("fd" if "SWITCHBOARD_RUN_FD" in e else "") for e in captured]
    check("worker-env-nothing-of-fzf-nor-the-path", marks == ["fd"], marks)

# 36. --focus-wait outlasts the slowest worker.
block('36. --focus-wait outlasts the slowest worker')
with tempfile.TemporaryDirectory(dir="/tmp") as d:
    run = private_tmp(d, "run")
    env = dict(os.environ, SWITCHBOARD_RUN_DIR=run, SWITCHBOARD_REMOTE_TIMEOUT="2",
               SWITCHBOARD_LABELS=json.dumps({"m1": "box1"}))
    waiter = subprocess.Popen([sys.executable, str(TOOL), "--focus-wait", "focus-7-7", "m1|a|w1:p1|w1:t1"],
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, universal_newlines=True, env=env)
    # 2 x 2 s + 3 s = 7 s; with only 2 s + 3 s it would already have given up at 5 s.
    _time.sleep(5.8)
    with open(os.path.join(run, "focus-7-7"), "w") as f:
        f.write("ready on box1: late but fine\n")
    out, _ = waiter.communicate(timeout=10)
    check("focus-wait-outlasts-a-double-timeout", out.strip() == "ready on box1: late but fine", out)

# 37. A hung local herdr.
block('37. A hung local herdr')
with tempfile.TemporaryDirectory() as d:
    d = pathlib.Path(d)
    slow = executable(d / "herdr", '#!/bin/sh\ncase "$*" in\n  "api snapshot") exec sleep 6 ;;\n'
                                   '  "machine list --json") echo "[]" ;;\nesac\n')
    saved = (sb.HERDR, sb.LOCAL_TIMEOUT)
    sb.HERDR, sb.LOCAL_TIMEOUT = str(slow), 1.0
    try:
        lv = sb.Live([], sb.entries_from(snap([pane("w1:p1")], [agent("w1:p1", "idle", 1, title="kept-row")]), "", "here", 0),
                     fetch=sb.snapshot, cache=False)
        t0 = _time.time()
        lv.refresh_local()
        took = _time.time() - t0
        check("local-refresh-has-a-timeout", took < 3 and "kept-row" in lv.text(), took)
        t0 = _time.time()
        try:
            sb.snapshot()
            check("local-snapshot-times-out", False)
        except Exception:
            check("local-snapshot-times-out", _time.time() - t0 < 3, _time.time() - t0)
    finally:
        sb.HERDR, sb.LOCAL_TIMEOUT = saved
    fzf_ok = executable(d / "fzf", '#!/bin/sh\nif [ "$1" = --version ]; then echo "0.74.0 (test)"; exit 0; fi\nexit 1\n')
    env = dict(os.environ, HERDR_BIN_PATH=str(slow), SWITCHBOARD_FZF=str(fzf_ok), SWITCHBOARD_LOCAL_TIMEOUT="1")
    t0 = _time.time()
    r = subprocess.run([sys.executable, str(TOOL)], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, universal_newlines=True, env=env, timeout=30)
    took = _time.time() - t0
    cfg_path = os.path.join(os.environ["HERDR_PLUGIN_CONFIG_DIR"], "config.toml")
    check("popup-hung-herdr-says-what-to-raise", r.returncode == 1 and "within 1 s" in r.stdout
          and "[refresh] local_timeout" in r.stdout and cfg_path in r.stdout and took < 4,
          (r.returncode, took, r.stdout[-300:]))
    # The option itself, from a config file and without the test override.
    cfg_dir = d / "cfg-timeout"
    cfg_dir.mkdir()
    (cfg_dir / "config.toml").write_text("[refresh]\nlocal_timeout = 1\n")
    env = dict(os.environ, HERDR_BIN_PATH=str(slow), SWITCHBOARD_FZF=str(fzf_ok), HERDR_PLUGIN_CONFIG_DIR=str(cfg_dir))
    t0 = _time.time()
    r = subprocess.run([sys.executable, str(TOOL)], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, universal_newlines=True, env=env, timeout=30)
    took = _time.time() - t0
    check("local-timeout-option-applies", r.returncode == 1 and "within 1 s" in r.stdout and took < 4,
          (r.returncode, took, r.stdout[-200:]))
    r = subprocess.run([sys.executable, str(TOOL), "--rows"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, universal_newlines=True, env=env, timeout=30)
    check("rows-timeout-says-what-to-raise", r.returncode == 1 and "[refresh] local_timeout" in r.stderr
          and "Traceback" not in r.stderr, (r.returncode, r.stderr[-200:]))
    (cfg_dir / "config.toml").write_text("lang = \"es\"\n[refresh]\nlocal_timeout = 1\n")
    r = subprocess.run([sys.executable, str(TOOL)], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, universal_newlines=True, env=env, timeout=30)
    check("local-timeout-message-in-spanish", "no contestó api snapshot en 1 s" in r.stdout, r.stdout[-200:])
cfg, warn = sb.merge_config({"refresh": {"local_timeout": 30}})
check("local-timeout-in-range", cfg["refresh"]["local_timeout"] == 30.0 and not warn, (cfg["refresh"], warn))
for bad in (0.5, 121, "fast"):
    cfg, warn = sb.merge_config({"refresh": {"local_timeout": bad}})
    check("local-timeout-out-of-range %r" % (bad,), cfg["refresh"]["local_timeout"] == 5.0 and warn, (cfg["refresh"], warn))

# 38. Closing always removes the run directory.
block('38. Closing always removes the run directory')
def close_popup(local_seconds, slow, signals=False, leader=True):
    """Open the popup over a fake herdr, press Esc, and return (rc, seconds from Esc to exit,
    what is left in the popup's run root, whether a process still names that root). slow:
    every snapshot after the first hangs. signals: instead of Esc, SIGTERM and 0.4 s later
    SIGHUP, while a refresh hangs (the close no longer waits for it, so the second signal may
    come after the exit; block 56 sends one during a close that waits). leader=False: a parent
    leads the terminal's session and outlives the popup, so the kernel hangs nothing up
    when the popup exits; whatever ends fzf then is the popup itself."""
    import signal as _sig8
    with tempfile.TemporaryDirectory(dir="/tmp") as d:
        root = private_tmp(d, "runs")
        cfg = os.path.join(d, "cfg")
        os.mkdir(cfg)
        with open(os.path.join(cfg, "config.toml"), "w") as f:
            f.write("[refresh]\nlocal_seconds = %s\n" % local_seconds)
        snapfile = os.path.join(d, "snap.json")
        with open(snapfile, "w") as f:
            json.dump({"result": {"snapshot": snap([pane("w1:p1")], [agent("w1:p1", "idle", 1, title="only-row")])}}, f)
        hang = 'echo $$ > "%s/hung"; exec sleep 30' % d if slow else "true"
        fh = executable(os.path.join(d, "herdr"),
                        '#!/bin/sh\ncase "$*" in\n  "machine list --json") echo "[]" ;;\n'
                        '  "api snapshot") if [ -e "%(d)s/once" ]; then %(hang)s; fi; touch "%(d)s/once"; cat "%(s)s" ;;\n'
                        '  *) exit 0 ;;\nesac\n' % {"d": d, "hang": hang, "s": snapfile})
        popup_pid, popup_rc = os.path.join(d, "popup.pid"), os.path.join(d, "popup.rc")
        pid, fd = _pty.fork()
        if pid == 0:
            os.environ.update(TERM="xterm-256color", HERDR_BIN_PATH=str(fh), HERDR_PLUGIN_CONFIG_DIR=cfg,
                              HERDR_PLUGIN_STATE_DIR=os.path.join(d, "state"), SWITCHBOARD_RUN_ROOT=root)
            if leader:
                os.execv(sys.executable, [sys.executable, "-B", str(TOOL)])
            inner = os.fork()
            if inner == 0:
                os.execv(sys.executable, [sys.executable, "-B", str(TOOL)])
            with open(popup_pid + ".tmp", "w") as f:
                f.write(str(inner))
            os.rename(popup_pid + ".tmp", popup_pid)
            done, st, quit_at = 0, 0, _time.time() + 60
            while not done and _time.time() < quit_at:
                done, st = os.waitpid(inner, os.WNOHANG)
                _time.sleep(0.02)
            ec = os.waitstatus_to_exitcode(st) if done else -9
            with open(popup_rc + ".tmp", "w") as f:
                f.write(str(ec))
            os.rename(popup_rc + ".tmp", popup_rc)
            _time.sleep(30)  # still leading the session; the test kills this group when done
            os._exit(0)
        import fcntl as _f6
        import struct as _st6
        import termios as _tm6
        _f6.ioctl(fd, _tm6.TIOCSWINSZ, _st6.pack("HHHH", 30, 140, 0, 0))
        buf, t_esc, rc, end = b"", None, None, _time.time() + 30
        while _time.time() < end:
            r, _, _ = _sel.select([fd], [], [], 0.05)
            if r:
                try:
                    chunk = os.read(fd, 65536)
                except OSError:
                    chunk = b""
                if not chunk:
                    rc, fd = finish(pid, fd, 5), None  # finish closed it
                    break
                buf += chunk
            elif leader:  # exited while a child still holds the terminal open
                done, status = os.waitpid(pid, os.WNOHANG)
                if done:
                    rc = os.waitstatus_to_exitcode(status)
                    break
            if not leader and os.path.exists(popup_rc):
                rc = int(open(popup_rc).read())
                break
            if t_esc is None and b"only-row" in buf:
                # With a slow snapshot, wait until a refresh is hanging before closing; the
                # terminal is read all along (see finish).
                buf += read_until(fd, lambda _b: not slow or os.path.exists(os.path.join(d, "hung")), 5)
                buf += read_until(fd, lambda _b: leader or os.path.exists(popup_pid), 5)
                target = pid if leader else int(open(popup_pid).read())
                t_esc, mark = _time.time(), len(buf)
                if signals:
                    os.kill(target, _sig8.SIGTERM)
                    buf += read_until(fd, lambda _b: False, 0.4)
                    try:
                        os.kill(target, _sig8.SIGHUP)
                    except ProcessLookupError:
                        pass  # the close was already over (it waits for no read)
                else:
                    os.write(fd, b"\x1b")
        took = _time.time() - t_esc if t_esc else None
        # The terminal after the popup left: what fzf wrote on its way out, and whether echo
        # and signal keys are back (on a pty master, tcgetattr reads the terminal's settings).
        terminal = {}
        if fd is not None:
            buf += read_until(fd, lambda _b: False, 0.3)
            after = buf[mark:] if t_esc else b""
            lflag = _tm6.tcgetattr(fd)[3]
            terminal = {"main-screen": b"\x1b[?1049l" in after, "echo": bool(lflag & _tm6.ECHO),
                        "isig": bool(lflag & _tm6.ISIG)}
        left = sorted(os.listdir(root))
        # fzf's command line names its socket under the run root: yes/no, from the command
        # lines only, before anything else here ends what is left.
        ps = subprocess.run(["ps", "-ww", "-axo", "command="], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            universal_newlines=True, timeout=20).stdout
        lingering = any(root in line and "ps -ww -axo" not in line for line in ps.splitlines())
        if fd is not None:
            finish(pid, fd, 0)  # reaps, or kills, what is left of the terminal's session, and closes fd
        if os.path.exists(os.path.join(d, "hung")):  # the hanging fake herdr outlives the popup
            try:
                os.kill(int(open(os.path.join(d, "hung")).read().strip()), 9)
            except (ValueError, OSError):
                pass
        return rc, took, left, lingering, terminal


rc, took, left, _, _ = close_popup(10, False)
check("close-with-a-long-interval-removes-the-run-dir", rc == 0 and left == [] and took is not None and took < 1.5,
      (rc, took, left))
rc, took, left, _, _ = close_popup(1, True)
# ...without waiting for the hung local read (it used to wait 2 s for it; now about 0.2 s).
check("close-during-a-slow-snapshot-removes-the-run-dir", rc == 0 and left == [] and took is not None and took < 1.0,
      (rc, took, left))
# SIGTERM while a refresh hangs: the first signal's exit code and nothing left. (The SIGHUP
# sent 0.4 s later comes after the exit: the close waits for no read. A second signal while
# the close is under way is block 56's two_signals.) fzf does not outlive the popup either
# (the popup ends it, and here the kernel's hang-up of a session leader's terminal would too).
rc, took, left, lingering, _ = close_popup(1, True, signals=True)
check("signal-during-a-slow-snapshot-removes-the-run-dir", rc == 128 + 15 and left == [] and took is not None
      and took < 5, (rc, took, left))
check("signal-leaves-no-fzf", not lingering)
# The same with a parent leading the terminal's session: no hang-up from the kernel, so only
# the popup's own kill ends fzf (on macOS the kernel's hang-up could not be counted on).
rc, took, left, lingering, terminal = close_popup(1, True, signals=True, leader=False)
check("signal-popup-ends-its-own-fzf", rc == 128 + 15 and left == [] and not lingering, (rc, took, left, lingering))
# ...gently: fzf gets the chance to put the terminal back (main screen, echo, signal keys).
check("signal-popup-leaves-the-terminal-usable", terminal == {"main-screen": True, "echo": True, "isig": True},
      terminal)


# A popup whose terminal goes away (SIGHUP) still removes its directories: the run directory
# and, in the demo, the temporary state directory.
if fzf_real and not sb.dependency_problems(python=(3, 12, 0), fzf=fzf_real):
    with tempfile.TemporaryDirectory(dir="/tmp") as d:
        root = private_tmp(d, "runs")
        tmpdir = private_tmp(d, "tmp")
        pid, fd = _pty.fork()
        if pid == 0:
            os.environ.update(TERM="xterm-256color", HERDR_BIN_PATH="/bin/false", SWITCHBOARD_RUN_ROOT=root,
                              TMPDIR=tmpdir)
            os.execv(sys.executable, [sys.executable, "-B", str(TOOL), "--demo"])
        import fcntl as _f7
        import struct as _st7
        import termios as _tm7
        _f7.ioctl(fd, _tm7.TIOCSWINSZ, _st7.pack("HHHH", 30, 160, 0, 0))
        buf, end = b"", _time.time() + 20
        while _time.time() < end and b"rate-limiter-review" not in buf:
            r, _, _ = _sel.select([fd], [], [], 0.05)
            if r:
                try:
                    buf += os.read(fd, 65536)
                except OSError:
                    break
        seen_before = (sorted(os.listdir(root)), sorted(os.listdir(tmpdir)))
        os.close(fd)  # the terminal goes away: the session leader gets SIGHUP
        done = pid if finish(pid, None, 5) is not None else 0
        # The run directory, and at least the demo's state directory (a preview child has its own).
        check("hangup-was-really-mid-run", len(seen_before[0]) == 1 and len(seen_before[1]) >= 1, seen_before)
        check("hangup-removes-every-directory", done == pid and os.listdir(root) == [] and os.listdir(tmpdir) == [],
              (done, os.listdir(root), os.listdir(tmpdir)))
with tempfile.TemporaryDirectory(dir="/tmp") as d:
    rows_dir = private_tmp(d, "rows")
    saved_every = sb.LOCAL_EVERY
    sb.LOCAL_EVERY = 10.0
    try:
        lv = sb.Live([], [], fetch=lambda m="", t=None, i=None: snap([], []), cache=False)
        stop = _threading.Event()
        t = _threading.Thread(target=sb.watch, args=(lv, short_sock("none"), os.path.join(rows_dir, "rows"),
                                                    stop, None), daemon=True)
        t.start()
        _time.sleep(0.5)
        t0 = _time.time()
        stop.set()
        t.join(3)
        check("stop-wakes-the-watch-loop", not t.is_alive() and _time.time() - t0 < 1, _time.time() - t0)
    finally:
        sb.LOCAL_EVERY = saved_every

# 39. The worker re-checks the name and the directory it inherits.
block('39. The worker re-checks the name and the directory it inherits')
with tempfile.TemporaryDirectory(dir="/tmp") as d:
    (pathlib.Path(d) / "machines.json").write_text(json.dumps([{"id": "m1", "label": "box1", "enabled": True}]))
    fh = executable(os.path.join(d, "herdr"), '#!/bin/sh\ncase "$*" in\n  "machine list --json") cat "%s/machines.json" ;;\n'
                                             '  *) exit 0 ;;\nesac\n' % d)
    parent = private_tmp(d, "parent")

    def run_worker(dir_path, name):
        fd = os.open(dir_path, os.O_RDONLY)
        try:
            env = dict(os.environ, HERDR_BIN_PATH=str(fh), SWITCHBOARD_RUN_FD=str(fd))
            subprocess.run([sys.executable, str(TOOL), "--focus", "m1|a|w1:p1|w1:t1", name], stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env, pass_fds=(fd,), timeout=30)
        finally:
            os.close(fd)

    run_dir = private_tmp(parent, "run")
    run_worker(run_dir, "focus-1-1")
    check("worker-writes-a-valid-result", sorted(os.listdir(run_dir)) == ["focus-1-1"], os.listdir(run_dir))
    run_worker(run_dir, "../escape")
    check("worker-refuses-a-name-that-climbs-out", sorted(os.listdir(parent)) == ["run"]
          and sorted(os.listdir(run_dir)) == ["focus-1-1"], (os.listdir(parent), os.listdir(run_dir)))
    loose = os.path.join(parent, "loose")
    os.mkdir(loose)
    os.chmod(loose, 0o755)
    run_worker(loose, "focus-2-2")
    check("worker-refuses-a-directory-that-is-not-private", os.listdir(loose) == [], os.listdir(loose))

# 40. A readable selected row.
block('40. A readable selected row')
argv = sb.fzf_argv("fzf", "self", "/tmp/s.sock")
check("blank-gutter", "--gutter" in argv and argv[argv.index("--gutter") + 1] == " ", argv)
colors = dict(kv.split(":", 1) for kv in sb.fzf_colors(sb.DEFAULTS["colors"]).split(","))
check("pointer-in-the-selected-text-colour", colors.get("pointer") == sb.DEFAULTS["colors"]["selected_fg"], colors)
env = dict(os.environ, HERDR_BIN_PATH="/bin/false")
del env["NO_COLOR"]
r = subprocess.run([sys.executable, str(TOOL), "--demo", "--rows"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                   universal_newlines=True, env=env, timeout=20)
rows = [l.split("\t", 1)[1] for l in r.stdout.splitlines()[1:] if "\t" in l]
glyph_only = re.compile(r"^\x1b\[[0-9;]+m[●○·›]\x1b\[0m (blocked|done|working|idle|unknown|shell) ")
check("only-the-glyph-is-coloured", rows and all(glyph_only.match(x) for x in rows),
      [x[:40] for x in rows if not glyph_only.match(x)][:3])
plain_rows = [sb.ANSI.sub("", x) for x in rows]
check("terminals-still-start-with-their-glyph", sum(1 for x in plain_rows if x.startswith("› ")) == 5,
      [x[:12] for x in plain_rows])

# 41. The jump's keys are configurable and cannot escape the AppleScript string.
block("41. The jump's keys are configurable and cannot escape the AppleScript str")
check("jump-keys-default-is-herdrs", sb.DEFAULTS["jump"]["prefix"] == "ctrl+b" and sb.DEFAULTS["jump"]["goto"] == "prefix+g"
      and sb.JUMP_KEYS == "\\x02g/", sb.JUMP_KEYS)
check("jump-keys-custom", sb.goto_keys("ctrl+a", "prefix+/") == "\\x01//" and sb.goto_keys("ctrl+z", "prefix+;") == "\\x1a;/")
for prefix, goto in (("f12", "prefix+g"), ("ctrl+B", "prefix+g"), ("ctrl+b", "g"), ("ctrl+b", "prefix+shift+g"),
                     ("ctrl+b", 'prefix+"'), ("ctrl+b", "prefix+\\"), ("ctrl+b", "prefix+gg"), ("ctrl+b\n", "prefix+g"),
                     ("ctrl+b", "prefix+g\n"), ("", "")):
    check("jump-keys-refused %r" % ((prefix, goto),), sb.goto_keys(prefix, goto) is None)
# The window's herdr keys, read from that window's config.toml: [keys] prefix and goto, herdr's
# defaults for what it does not set, and every other key bound in [keys] and [[keys.command]].
# Without tomllib (Python 3.9 and 3.10, the /usr/bin/python3 of the Macs) the file is read line
# by line, [keys] and the keys of [[keys.command]] only; what that cannot be sure of is None.
HERDR_CFG = ('onboarding = false\n[keys]\nsettings = "prefix+."\ngoto = "prefix+/"  # the navigator\n\n'
             '[[keys.command]]\nkey = "prefix+space"\ntype = "plugin_action"\n[ui]\nprefix = "ctrl+z"\nlist = [1, 2]\n')
check("herdr-keys-read", sb.herdr_keys(HERDR_CFG) == ("ctrl+b", "prefix+/")
      and sb.herdr_bindings(HERDR_CFG) == ("ctrl+b", "prefix+/", ["prefix+.", "prefix+space"]), sb.herdr_bindings(HERDR_CFG))
check("herdr-keys-without-tomllib", sb._keys_table(HERDR_CFG) == ({"settings": "prefix+.", "goto": "prefix+/"}, ["prefix+space"])
      and sb._keys_table('[keys]\nprefix = "ctrl+a"\n') == ({"prefix": "ctrl+a"}, []), sb._keys_table(HERDR_CFG))
check("herdr-keys-defaults", sb.herdr_keys("") == ("ctrl+b", "prefix+g") and sb._keys_table("") == ({}, []))
check("herdr-keys-unreadable", sb._keys_table('[keys]\ngoto =\n') is None and sb._keys_table('[keys]\ngoto = 7\n') is None
      and sb.herdr_keys('[keys]\ngoto = 7\n') is None and sb.herdr_keys("[keys\n") is None)
# What the line reader cannot be sure of is None (the keys count as differing): before, a dotted
# or inline `keys` at the top, a quoted header and a [keys] inside a multi-line string all read
# as herdr's defaults or as real.
UNSURE = {
    "dotted": 'keys.prefix = "ctrl+a"\n',
    "inline": 'keys = { prefix = "ctrl+a" }\n',
    "quoted-header": '["keys"]\nprefix = "ctrl+a"\n',
    # (the string ends in a [[keys.command]] it opens, so read line by line it would pass)
    "multiline": ('[keys]\ngoto = "prefix+/"\n[[keys.command]]\nkey = "prefix+space"\ncommand = """\n[keys]\n'
                  'goto = "prefix+g"\n[[keys.command]]\nkey = "x"\n"""\n'),
    "sub-table": '[keys.extra]\nx = "prefix+g"\n',
    "array-value": '[keys]\ngoto = ["prefix+g"]\n',
    # A value that spans lines: its element `[1]` on a line of its own looked like a header, so
    # what came after was read in the wrong table (on 3.9 these matched; tomllib says differ).
    "array-then-dotted": 'x = [\n  [1]\n]\nkeys.goto = "prefix+/"\n',
    "array-then-inline": 'x = [\n  [1]\n]\nkeys = { goto = "prefix+/" }\n',
    "array-in-command": '[[keys.command]]\nargs = [\n  [1]\n]\nkey = "prefix+g"\n',
    "inline-table-spans": '[keys]\nx = { a = 1,\n  b = 2 }\n',
}
check("keys-reader-refuses-what-it-cannot-be-sure-of", all(sb._keys_table(t) is None for t in UNSURE.values()),
      [k for k, t in UNSURE.items() if sb._keys_table(t) is not None])
check("spans-lines", all(sb.spans_lines(l) for l in ("x = [", "x = {", 'x = "abc', "]", "x = [[1], [2]")) and not any(
    sb.spans_lines(l) for l in ("[keys]", "[[keys.command]]", "x = [1, [2]]", 'x = "a][" # [', 'x = "a\\"b"',
                                "x = 'a{'", "[1]", "  [1],")))
saved_tomllib = sb.tomllib
sb.tomllib = None
try:
    check("keys-without-tomllib-unsure-is-none", all(sb.herdr_bindings(t) is None for t in UNSURE.values()),
          [k for k, t in UNSURE.items() if sb.herdr_bindings(t) is not None])
finally:
    sb.tomllib = saved_tomllib
with tempfile.TemporaryDirectory() as d41:
    cfg41 = os.path.join(d41, "h.toml")
    open(cfg41, "w").close()
    xdg41, home41 = os.path.join(d41, "xdg"), os.path.join(d41, "home")
    os.makedirs(os.path.join(xdg41, "herdr"))
    os.mkdir(home41)
    P = sb.window_config_path
    check("window-config-path", P({"HERDR_CONFIG_PATH": cfg41, "XDG_CONFIG_HOME": xdg41, "HOME": home41}) == cfg41
          and P({"XDG_CONFIG_HOME": xdg41, "HOME": home41}) == os.path.join(xdg41, "herdr", "config.toml")
          and P({"HOME": home41}) == os.path.join(home41, ".config", "herdr", "config.toml"))
    # As herdr 0.9.5 does, a variable that is set wins even when empty; an empty, relative or
    # missing one cannot be relied on (and a value with a space comes out of ps cut short).
    check("window-config-path-unsure-is-none", all(P(e) is None for e in (
        {"HERDR_CONFIG_PATH": "", "HOME": home41}, {"HERDR_CONFIG_PATH": "h.toml"}, {"HERDR_CONFIG_PATH": cfg41 + "-cut"},
        {"XDG_CONFIG_HOME": "", "HOME": home41}, {"XDG_CONFIG_HOME": "rel"}, {"XDG_CONFIG_HOME": xdg41 + "-cut"},
        {"HOME": home41 + "-cut"}, {"HOME": "rel"}, {}, {"HERDR_REMOTE_KEYBINDINGS": "local"})))
    # The window's own environment, not the helper's: a process started with these variables.
    child41 = subprocess.Popen(["sleep", "30"], stdin=subprocess.DEVNULL,
                               env={"PATH": os.environ["PATH"], "HERDR_CONFIG_PATH": cfg41, "XDG_CONFIG_HOME": xdg41,
                                    "HOME": home41, "HERDR_REMOTE_KEYBINDINGS": "server", "OTHER": "x"})
    try:
        _time.sleep(0.3)
        env41 = sb.window_env(child41.pid)
    finally:
        child41.kill()
        child41.wait(5)
    check("window-env-of-the-window", env41 == {"HERDR_CONFIG_PATH": cfg41, "XDG_CONFIG_HOME": xdg41, "HOME": home41,
                                                "HERDR_REMOTE_KEYBINDINGS": "server"}, sorted(env41) if env41 else env41)
    saved41 = sb.run_out
    sb.run_out = lambda argv, timeout=5: ("/opt/homebrew/bin/herdr TERM=xterm HERDR_CONFIG_PATH=/x/My Configs/h.toml "
                                          "HOME=/x/home\n" if argv[:2] == ["ps", "-wwE"] else "")
    try:
        cut41 = sb.window_env(2 ** 22 + 12345)  # no such process in /proc: the macOS way, through ps -E
    finally:
        sb.run_out = saved41
    check("window-env-from-ps", cut41 == {"HERDR_CONFIG_PATH": "/x/My", "HOME": "/x/home"}
          and sb.window_config_path(cut41) is None, cut41)

    def match41(text, keys, words=("herdr",), check_ok=True, env=None):
        """window_keys_match with that config as the window's, `herdr config check` answering check_ok."""
        path = os.path.join(d41, "config.toml")
        with open(path, "wb") as f:
            f.write(text if isinstance(text, bytes) else text.encode())
        saved = sb.herdr_config_check
        sb.herdr_config_check = lambda p: check_ok
        try:
            return sb.window_keys_match(keys, (1, "/dev/ttys000", list(words)),
                                        env_of=lambda pid: {"HERDR_CONFIG_PATH": path} if env is None else env)
        finally:
            sb.herdr_config_check = saved
    nofile = {"HOME": home41}  # no config there: herdr's defaults
    check("window-keys-match", match41('[keys]\ngoto = "prefix+slash"\n', "\\x02//")
          and match41('[keys]\nprefix = "ctrl+a"\n', "\\x01g/") and match41(HERDR_CFG, "\\x02//")
          and match41("", "\\x02g/", env=nofile))
    check("window-keys-differ", not match41('[keys]\ngoto = "prefix+/"\n', "\\x02g/")
          and not match41('[keys]\nprefix = "ctrl+a"\n', "\\x02g/")
          and not match41('[keys]\ngoto = "prefix+shift+g"\n', "\\x02g/") and not match41("", "\\x02//", env=nofile))
    check("window-keys-unreadable-is-no", not match41(b'[keys]\ngoto = "prefix+\xff"\n', "\\x02g/")
          and not match41('[keys]\ngoto = 7\n', "\\x02g/") and not match41("", "\\x02g/", env={"HOME": "rel"}))
    # Another binding on goto's key (herdr then disables goto) or on the prefix, in [keys] or in
    # a [[keys.command]]: before, these matched.
    check("window-keys-another-binding-on-goto", not match41('[keys]\ngoto = "prefix+g"\nnew_worktree = "prefix+g"\n', "\\x02g/")
          and not match41('[[keys.command]]\nkey = "prefix+g"\ntype = "plugin_action"\ncommand = "x.y"\n', "\\x02g/")
          and not match41('[keys]\ngoto = "prefix+/"\nsettings = "prefix+slash"\n', "\\x02//")
          and not match41('[keys]\nnew_tab = "ctrl+b"\n', "\\x02g/"))
    # herdr's own check decides too: a type error elsewhere makes herdr use every default, and
    # the file's `prefix = "ctrl+a"` is then not what the window uses.
    typo = '[keys]\nprefix = "ctrl+a"\n[ui]\nsidebar_width = "abc"\n'
    check("window-keys-herdr-check-decides", not match41(typo, "\\x01g/", check_ok=False) and match41(typo, "\\x01g/"))
    # A window on the server's keys, and a window whose environment cannot be read.
    check("window-keys-server-keybindings", not match41("", "\\x02g/", words=("herdr", "--remote", "s", "--remote-keybindings", "server"))
          and not match41("", "\\x02g/", words=("herdr", "--remote-keybindings=server"))
          and match41("", "\\x02g/", words=("herdr", "--remote", "s", "--remote-keybindings", "local"))
          and not match41("", "\\x02g/", env={"HOME": home41, "HERDR_REMOTE_KEYBINDINGS": "server"})
          and match41("", "\\x02g/", env={"HOME": home41, "HERDR_REMOTE_KEYBINDINGS": "local"}))
    # An upper-case key letter is shift in herdr (`ctrl+B` is ctrl+shift+b), which the jump does
    # not type: it differs. Modifiers in any case are fine. Before, `ctrl+B` matched \x02.
    check("window-keys-uppercase-key-is-shift", not match41('[keys]\nprefix = "ctrl+B"\n', "\\x02g/")
          and not match41('[keys]\nprefix = "CTRL+B"\n', "\\x02g/") and not match41('[keys]\ngoto = "prefix+G"\n', "\\x02g/")
          and match41('[keys]\nprefix = "Ctrl+b"\n', "\\x02g/") and match41('[keys]\ngoto = "Prefix+Slash"\n', "\\x02//"))
    check("herdr-keys-text", sb.herdr_keys_text("Ctrl+b", "prefix+g") == "\\x02g/" and sb.herdr_keys_text("ctrl+B", "prefix+g") is None
          and sb.herdr_keys_text("ctrl+b", "prefix+G") is None and sb.herdr_keys_text("ctrl+b", "PREFIX+slash") == "\\x02//")
    # `ps -E` can print the command and no environment: no HOME of the window's own, so no
    # config can be located, rather than the helper's home (before: its defaults, a match).
    saved41 = sb.run_out
    sb.run_out = lambda argv, timeout=5: "/opt/homebrew/bin/herdr\n" if argv[:2] == ["ps", "-wwE"] else ""
    try:
        bare41 = sb.window_env(2 ** 22 + 12346)
        saved_check = sb.herdr_config_check
        sb.herdr_config_check = lambda p: True
        try:
            bare_match = sb.window_keys_match("\\x02g/", (2 ** 22 + 12346, "/dev/ttys000", ["herdr"]))
        finally:
            sb.herdr_config_check = saved_check
    finally:
        sb.run_out = saved41
    check("window-env-without-home-is-no", bare41 == {} and bare_match is False, (bare41, bare_match))
    # The owner's own herdr config (goto on prefix+/, settings on prefix+., a command on
    # prefix+space) with [jump] goto = "prefix+/": it matches, with and without tomllib.
    OWNER = ('onboarding = false\n\n[keys]\nsettings = "prefix+."\ngoto = "prefix+/"\n\n# a comment\n[[keys.command]]\n'
             'key = "prefix+space"\ntype = "plugin_action"\ndescription = "agents by priority (switchboard)"\n'
             'command = "trustxai.switchboard.open"\n\n[theme]\nname = "dracula"\nauto_switch = false\n\n'
             '[ui.toast]\ndelivery = "system"\n\n[ui]\nshow_agent_labels_on_pane_borders = true\n'
             'agent_panel_sort = "priority"\n')
    owner_ok = [match41(OWNER, "\\x02//"), not match41(OWNER, "\\x02g/")]
    saved_tomllib = sb.tomllib
    sb.tomllib = None
    try:
        owner_ok += [match41(OWNER, "\\x02//"), not match41(OWNER, "\\x02g/")]
    finally:
        sb.tomllib = saved_tomllib
    check("window-keys-owner-like-config-matches", all(owner_ok), owner_ok)
    with open(os.path.join(xdg41, "herdr", "config.toml"), "w") as f:
        f.write('[keys]\ngoto = "prefix+/"\n')
    saved41 = sb.herdr_config_check
    sb.herdr_config_check = lambda p: True
    try:
        win41 = (1, "/dev/ttys000", ["herdr"])
        from_window = (sb.window_keys_match("\\x02//", win41, env_of=lambda pid: {"XDG_CONFIG_HOME": xdg41}),
                       sb.window_keys_match("\\x02g/", win41, env_of=lambda pid: {"XDG_CONFIG_HOME": xdg41}),
                       sb.window_keys_match("\\x02g/", win41, env_of=lambda pid: None))
    finally:
        sb.herdr_config_check = saved41
    check("window-keys-from-the-window-environment", from_window == (True, False, False), from_window)
    # `herdr config check` on that file, read as herdr 0.9.5 prints it (these are its outputs).
    with open(os.path.join(d41, "check-out"), "w") as f:
        f.write("")
    fake41 = executable(os.path.join(d41, "herdr"), '#!/bin/sh\nprintf "%%s" "$HERDR_CONFIG_PATH" > "%s/seen"\n'
                        'cat "%s/check-out"\nexit "$(cat "%s/check-rc")"\n' % (d41, d41, d41))
    CHECKS = {
        "ok": ("config: ok\n", 0, True),
        "unrelated": ("config: issues found\nunknown config key ui.bogus; ignoring key\n", 1, True),
        "conflict": ("config: issues found\nprefix+g: kept keys.new_worktree, disabled keys.goto\n", 1, False),
        "parse-error": ('config: issues found\nconfig parse error: TOML parse error at line 4, column 17\n  |\n'
                        '4 | sidebar_width = "abc"\n  |                 ^^^^^\ninvalid type: string "abc", expected u16\n'
                        '; using defaults\n', 1, False),
        "read-error": ("config: issues found\nconfig read error: Permission denied (os error 13); using defaults\n", 1, False),
        "prefix": ("config: issues found\nctrl+b: kept keys.prefix, disabled keys.new_tab\n", 1, False),
        "other-output": ("something else\n", 0, False),
        "failed": ("config: ok\n", 2, False),
    }
    saved41 = sb.HERDR
    sb.HERDR = str(fake41)
    got41 = {}
    try:
        for name, (out, rc, _) in CHECKS.items():
            with open(os.path.join(d41, "check-out"), "w") as f:
                f.write(out)
            with open(os.path.join(d41, "check-rc"), "w") as f:
                f.write(str(rc))
            got41[name] = (sb.herdr_config_check(cfg41), open(os.path.join(d41, "seen")).read())
        sb.HERDR = os.path.join(d41, "no-such-herdr")
        missing41 = sb.herdr_config_check(cfg41)
        sb.HERDR = str(executable(os.path.join(d41, "slow-herdr"), "#!/bin/sh\nsleep 30\n"))
        saved_wait = sb.HERDR_CHECK_TIMEOUT
        sb.HERDR_CHECK_TIMEOUT = 0.5
        t41 = _time.time()
        try:
            slow41 = sb.herdr_config_check(cfg41)
        finally:
            sb.HERDR_CHECK_TIMEOUT = saved_wait
        took41 = _time.time() - t41
    finally:
        sb.HERDR = saved41
    check("herdr-config-check-reads-herdr", all(got41[k][0] == want for k, (_, _, want) in CHECKS.items())
          and all(seen == cfg41 for _, seen in got41.values()), got41)
    check("herdr-config-check-no-herdr-or-slow-is-no", missing41 is False and slow41 is False and took41 < 4,
          (missing41, slow41, took41))
cfg, problems = sb.merge_config({"jump": {"prefix": "ctrl+a", "goto": 'prefix+" & do shell script "x'}})
check("jump-keys-bad-config-is-default", cfg["jump"]["prefix"] == "ctrl+a" and cfg["jump"]["goto"] == "prefix+g"
      and any("jump.goto" in p for p in problems), (cfg["jump"], problems))
sb.configure(cfg)
try:
    check("jump-keys-from-config", sb.JUMP_KEYS == "\\x01g/", sb.JUMP_KEYS)
    check("jump-keys-used-in-the-script", '"text:\\\\x01g/w1:p1\\\\r"' in sb.ghostty_keys_script("/dev/ttys000", "w1:p1"))
finally:
    sb.configure(sb.load_config()[0])
    sb.LOCAL_EVERY, sb.REMOTE_EVERY = 0.05, 0.05
for bad in ('\\x02g/" & do shell script "touch x', "\\x02g/\\r", "\\x00g/", "\\x1bg/", "x/", "\\x02G/"):
    try:
        sb.ghostty_keys_script("/dev/ttys000", "w1:p1", bad)
        check("applescript-refuses-keys %r" % bad, False)
    except ValueError:
        pass

# 42. A refused jump key turns the jump off, instead of typing herdr's default keys into a
# herdr bound differently. Enter then works as with enabled = false.
block("42. A refused jump key turns the jump off, instead of typing herdr's defau")
cfg, problems = sb.merge_config({"jump": {"enabled": True, "goto": "prefix+shift+g"}})
check("jump-refused-goto-turns-it-off", cfg["jump"]["enabled"] is False
      and any("jump.goto" in p and "jump is off" in p for p in problems), (cfg["jump"], problems))
cfg, problems = sb.merge_config({"jump": {"prefix": "f12", "enabled": True}})  # enabled comes after the bad key
check("jump-refused-prefix-turns-it-off", cfg["jump"]["enabled"] is False
      and any("jump.prefix" in p and "jump is off" in p for p in problems), (cfg["jump"], problems))
cfg, problems = sb.merge_config({"lang": "es", "jump": {"enabled": True, "goto": 7}})
check("jump-off-message-in-spanish", cfg["jump"]["enabled"] is False
      and any("jump.goto" in p and "salto queda apagado" in p for p in problems), problems)
cfg, problems = sb.merge_config({"jump": {"enabled": True, "client": 7}})
check("jump-other-bad-value-keeps-it-on", cfg["jump"]["enabled"] is True and problems, (cfg["jump"], problems))
untypeable = json.loads(json.dumps(sb.DEFAULTS))
untypeable["jump"].update(enabled=True, goto="prefix+\\")  # not through merge_config
sb.configure(untypeable)
try:
    check("jump-configure-refuses-untypeable-keys", sb.JUMP_ENABLED is False and sb.enter_mode([{"id": "m1"}]) == (False, True),
          sb.JUMP_ENABLED)
finally:
    sb.configure(sb.load_config()[0])
    sb.LOCAL_EVERY, sb.REMOTE_EVERY = 0.05, 0.05
# herdr's named punctuation, for the characters the jump already types, in any case.
for name, ch in (("minus", "-"), ("comma", ","), ("period", "."), ("slash", "/"), ("quote", "'"), ("semicolon", ";"),
                 ("backtick", "`")):
    check("jump-named-key %s" % name, sb.goto_keys("ctrl+b", "prefix+" + name) == "\\x02%s/" % ch
          and sb.goto_keys("ctrl+b", "prefix+" + name.upper()) == "\\x02%s/" % ch, sb.goto_keys("ctrl+b", "prefix+" + name))
for name in ("backslash", "double_quote", "double-quote", "colon", "percent", "ampersand", "plus", "space", "enter",
             "f1", "G", "bac\u212atick", "m\u0131nus", "minus\n"):
    check("jump-named-key-refused %r" % name, sb.goto_keys("ctrl+b", "prefix+" + name) is None)
check("jump-named-keys-closed", all(len(c) == 1 and sb.KEYS_TEXT.fullmatch("\\x02%s/" % c) for c in sb.NAMED_KEYS.values()),
      sb.NAMED_KEYS)
check("jump-named-key-in-the-script", '"text:\\\\x02,/w1:p1\\\\r"'
      in sb.ghostty_keys_script("/dev/ttys000", "w1:p1", sb.goto_keys("ctrl+b", "prefix+comma")))
with tempfile.TemporaryDirectory(dir="/tmp") as d:
    (pathlib.Path(d) / "machines.json").write_text(json.dumps([{"id": "m1", "label": "box1", "enabled": True}]))
    fh = executable(os.path.join(d, "herdr"), '#!/bin/sh\ncase "$*" in\n  "machine list --json") cat "%s/machines.json" ;;\n'
                                             '  *) exit 0 ;;\nesac\n' % d)
    cfg_dir = os.path.join(d, "cfg")
    os.mkdir(cfg_dir)

    def enter_with(jump_toml):
        """--enter on a remote row with that [jump] table, the popup's link being ready."""
        with open(os.path.join(cfg_dir, "config.toml"), "w") as f:
            f.write("[jump]\n" + jump_toml)
        run42 = private_tmp(d, "run-%d" % len(os.listdir(d)))
        with open(os.path.join(run42, sb.JUMP_STATE), "w") as f:
            f.write("ready\n")
        env = dict(os.environ, HERDR_BIN_PATH=str(fh), HERDR_PLUGIN_CONFIG_DIR=cfg_dir, SWITCHBOARD_RUN_DIR=run42,
                   SWITCHBOARD_LABELS=json.dumps({"m1": "box1"}))
        out = subprocess.run([sys.executable, str(TOOL), "--enter", "m1|a|w1:p1|w1:t1"], stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, universal_newlines=True, env=env, timeout=20).stdout
        rows = subprocess.run([sys.executable, str(TOOL), "--demo", "--rows"], stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, universal_newlines=True, env=env, timeout=20).stdout
        return out, rows.splitlines()[0] if rows else ""

    out, header = enter_with('enabled = true\ngoto = "prefix+shift+g"\n')
    check("jump-refused-key-enter-is-api-focus", out.startswith("change-footer") and "accept" not in out, out)
    check("jump-refused-key-says-so-in-the-header", "jump.goto" in header and "jump is off" in header, header)
    out, header = enter_with('enabled = true\ngoto = "prefix+slash"\n')
    check("jump-good-key-enter-accepts", out.strip() == "accept" and "jump" not in header, (out, header))

# 43. What the jump types is matched whole: a final newline is not let through.
block('43. What the jump types is matched whole: a final newline is not let throu')
for tty, query in (("/dev/ttys000", "w1:p1\n"), ("/dev/ttys000", "w1:p1\r"), ("/dev/ttys000\n", "w1:p1"),
                   ("/dev/ttys\u00e9", "w1:p1"), ('/dev/ttys000"', "w1:p1")):
    try:
        sb.ghostty_keys_script(tty, query)
        check("applescript-refuses %r" % ((tty, query),), False)
    except ValueError:
        pass
check("typeable-whole-query", not sb.typeable("w1:p1\n", "\\x02g/") and sb.typeable("w1:p1", "\\x02g/"))
for sub, value in (("accent", "red\n"), ("selected_bg", "#ff00ff\n"), ("fzf", "fg:red\n")):
    cfg, problems = sb.merge_config({"colors": {sub: value}})
    check("colour-whole-value %s" % sub, cfg["colors"][sub] == sb.DEFAULTS["colors"][sub] and problems, cfg["colors"][sub])
_proj = os.path.join(os.environ["HOME"], ".agent", "projects", "p")
os.makedirs(_proj)
for _name in ("0123abcd-ef.jsonl", "0123abcd-ef\n.jsonl"):
    open(os.path.join(_proj, _name), "w").close()
check("transcript-id-whole", sb.transcript_path("0123abcd-ef\n") is None
      and sb.transcript_path("0123abcd-ef") == os.path.join(_proj, "0123abcd-ef.jsonl"), sb.transcript_path("0123abcd-ef\n"))
shutil.rmtree(os.path.join(os.environ["HOME"], ".agent"))

# 44. The jump checks what it would type before it renames anything.
block('44. The jump checks what it would type before it renames anything')
with tempfile.TemporaryDirectory(dir="/tmp") as d:
    calls = os.path.join(d, "calls")
    fh = executable(os.path.join(d, "herdr"), '#!/bin/sh\necho "$*" >> "%s"\n' % calls)

    def took_calls():
        if not os.path.exists(calls):
            return []
        lines = open(calls).read().splitlines()
        os.remove(calls)
        return lines

    class Osa44:
        def __init__(self):
            self.killed, self.script = False, None

        def kill(self):
            self.killed = True

        def communicate(self, data, timeout=None):
            self.script = data

    saved_herdr = sb.HERDR
    sb.HERDR = str(fh)
    try:
        good = dict(label="box1", kind="a", pane="w1:p1", tab="w1:t1", query="sbjabc", rename=True, old_label="logs",
                    keys="\\x02g/", wait=0, tty="/dev/ttys000")
        for what, bad in (("keys", dict(keys="\\x02g/\n")), ("query", dict(query="sbjabc\n")),
                          ("tty", dict(tty="/dev/ttys000\n")), ("keys-type", dict(keys=7))):
            osa = Osa44()
            rc = sb.jump(osa=osa, **dict(good, **bad))
            lines = took_calls()
            check("jump-refused-%s-renames-nothing" % what, rc == 2 and lines == ["--machine box1 agent focus w1:p1"]
                  and osa.killed and osa.script is None, (rc, lines))
        osa = Osa44()
        rc = sb.jump(osa=osa, **good)
        lines = took_calls()
        check("jump-good-renames-types-restores", rc == 0 and lines == [
            "--machine box1 pane rename w1:p1 sbjabc", "--machine box1 pane rename w1:p1 logs",
            "--machine box1 agent focus w1:p1"] and osa.script and b"sbjabc" in osa.script, (rc, lines))
        # Without a tty (a jump the helper did not check: `--jump`, or a line from an older
        # popup), jump() finds the window and checks its keys itself. Its herdr's goto is
        # prefix+/ here: nothing renamed or typed, only the focus. With matching keys, it types.
        cfg44 = os.path.join(d, "herdr-config.toml")
        with open(cfg44, "w") as f:
            f.write('[keys]\ngoto = "prefix+/"\n')
        saved44 = (sb.ghostty_window, sb.window_env, sb.herdr_config_check)
        sb.ghostty_window = lambda ps_text=None, atime=None: (60526, "/dev/ttys000", ["herdr"])
        sb.window_env = lambda pid: {"HERDR_CONFIG_PATH": cfg44}
        sb.herdr_config_check = lambda path: True
        unchecked = dict(good)
        del unchecked["tty"]
        try:
            osa = Osa44()
            rc = sb.jump(osa=osa, **unchecked)
            lines = took_calls()
            osa_ok = Osa44()
            rc_ok = sb.jump(osa=osa_ok, **dict(unchecked, keys="\\x02//"))
            lines_ok = took_calls()
        finally:
            sb.ghostty_window, sb.window_env, sb.herdr_config_check = saved44
        check("jump-refuses-keys-the-window-does-not-bind", rc == 2 and lines == ["--machine box1 agent focus w1:p1"]
              and osa.killed and osa.script is None and rc_ok == 0 and osa_ok.script and b"sbjabc" in osa_ok.script
              and len(lines_ok) == 3, (rc, lines, rc_ok, lines_ok))
        # Through --jump-server, a line with a refused query.
        orig44 = (sb.ghostty_window, sb.window_keys_match, sb.subprocess.Popen)
        osa = Osa44()
        sb.ghostty_window = lambda ps_text=None, atime=None: (60526, "/dev/ttys000", ["herdr"])
        sb.window_keys_match = lambda keys, window, env_of=None: True
        sb.subprocess.Popen = lambda argv, **kw: osa if argv[0] == sb.OSASCRIPT else orig44[2](argv, **kw)
        try:
            rc = sb.jump_server(_io.StringIO(json.dumps(["--jump", "box1", "a", "w1:p1", "w1:t1", "sbjabc\n", "1", "logs",
                                                         "\\x02g/"]) + "\n"), _io.StringIO(), keys="\\x02g/")
        finally:
            sb.ghostty_window, sb.window_keys_match, sb.subprocess.Popen = orig44
        lines = took_calls()
        check("jump-server-refused-renames-nothing", rc == 2 and osa.killed and not any("rename" in l for l in lines),
              (rc, lines))
        osa = Osa44()
        sb.ghostty_window = lambda ps_text=None, atime=None: (60526, "/dev/ttys000", ["herdr"])
        sb.window_keys_match = lambda keys, window, env_of=None: True
        sb.subprocess.Popen = lambda argv, **kw: osa if argv[0] == sb.OSASCRIPT else orig44[2](argv, **kw)
        try:
            sb.jump_server(_io.StringIO(json.dumps(["--jump", "box1", "a", "w1:p1", "w1:t1", 5, "1", "logs", "\\x02g/"])
                                        + "\n"), _io.StringIO(), keys="\\x02g/")
        finally:
            sb.ghostty_window, sb.window_keys_match, sb.subprocess.Popen = orig44
        check("jump-server-non-text-argument", osa.killed and took_calls() == [])
    finally:
        sb.HERDR = saved_herdr
    # Through main's --jump, in a process of its own.
    r = subprocess.run([sys.executable, str(TOOL), "--jump", "box1", "a", "w1:p1", "w1:t1", "sbjabc", "1", "logs", "x/"],
                       stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
                       env=dict(os.environ, HERDR_BIN_PATH=str(fh)), timeout=30)
    lines = took_calls()
    check("jump-main-refused-renames-nothing", r.returncode == 2 and lines == ["--machine box1 agent focus w1:p1"]
          and "Traceback" not in r.stderr, (r.returncode, lines, r.stderr[-200:]))

# 45. The other machines' rows show up even when fzf opens --listen late (they answered
# before it listened). The demo, behind an fzf that starts listening 0.3 s late.
block("45. The other machines' rows show up even when fzf opens --listen late (th")
if fzf_real and not sb.dependency_problems(python=(3, 12, 0), fzf=fzf_real):
    with tempfile.TemporaryDirectory(dir="/tmp") as d:
        slow_fzf = executable(os.path.join(d, "fzf"), '#!/bin/sh\nsleep 0.3\nexec "%s" "$@"\n' % fzf_real)
        root = private_tmp(d, "runs")
        t0 = _time.time()
        pid, fd = _pty.fork()
        if pid == 0:
            os.environ.update(TERM="xterm-256color", HERDR_BIN_PATH="/bin/false", SWITCHBOARD_FZF=str(slow_fzf),
                              SWITCHBOARD_RUN_ROOT=root)
            os.execv(sys.executable, [sys.executable, "-B", str(TOOL), "--demo"])
        import fcntl as _f45
        import struct as _st45
        import termios as _tm45
        _f45.ioctl(fd, _tm45.TIOCSWINSZ, _st45.pack("HHHH", 40, 180, 0, 0))
        buf, seen, end = b"", None, _time.time() + 8
        while _time.time() < end and seen is None:
            r, _, _ = _sel.select([fd], [], [], 0.05)
            if r:
                try:
                    buf += os.read(fd, 65536)
                except OSError:
                    break
            plain = sb.ANSI.sub("", buf.decode("utf-8", "replace"))
            if "rate-limiter-review" in plain and "terraform-plan-staging" in plain:  # one row of each other machine
                seen = _time.time() - t0
        os.write(fd, b"\x1b")
        # Read the terminal while it exits: on macOS, fzf restoring the screen into a terminal
        # nobody reads blocks, and so does a session leader exiting with output not drained.
        rc = finish(pid, fd, 10)
        # Before: they showed only with the demo's first change, at about 9 s.
        check("late-listen-rows-arrive", seen is not None and seen < 5, seen)
        check("late-listen-esc-exits", rc == 0, rc)

# 46. Nothing fzf exports, and nothing that names the run directory, reaches the programs
# the popup and its helpers start: herdr, ssh, osascript. The fakes record yes/no marks.
block("46. children's environment")
MARKS_SH = ('#!/bin/sh\n{ env | grep -q "^FZF_" && echo fzf; env | grep -q "^SWITCHBOARD_RUN_" && echo runvar; '
            'env | grep -qF -- "%(run)s" && echo path; echo ran; } >> "%(out)s"\n')
with tempfile.TemporaryDirectory(dir="/tmp") as d:
    run = private_tmp(d, "run")
    marks = {k: os.path.join(d, k + ".marks") for k in ("herdr", "ssh", "osa")}
    fakes = {k: executable(os.path.join(d, k), MARKS_SH % {"run": run, "out": marks[k]}) for k in marks}
    fzf_env = dict(FZF_SOCK=os.path.join(run, "fzf.sock"), FZF_QUERY="", FZF_CURRENT_ITEM="row",
                   SWITCHBOARD_RUN_DIR=run)

    def took(k, wait=5.0):
        end = _time.time() + wait
        while _time.time() < end and not (os.path.exists(marks[k]) and "ran" in open(marks[k]).read()):
            _time.sleep(0.05)
        got = open(marks[k]).read().split() if os.path.exists(marks[k]) else None
        if os.path.exists(marks[k]):
            os.remove(marks[k])
        return got

    # herdr from a child of fzf (the preview), in a process of its own.
    subprocess.run([sys.executable, str(TOOL), "--preview", "|a|w1:p1|w1:t1"], stdin=subprocess.DEVNULL,
                   stdout=subprocess.DEVNULL, env=dict(os.environ, HERDR_BIN_PATH=str(fakes["herdr"]), **fzf_env),
                   timeout=30)
    check("child-env-herdr-from-preview", took("herdr") == ["ran"])
    saved = (sb.HERDR, sb.SSH, sb.OSASCRIPT, dict(os.environ))
    os.environ.update(fzf_env)
    sb.HERDR, sb.SSH, sb.OSASCRIPT = str(fakes["herdr"]), str(fakes["ssh"]), str(fakes["osa"])
    try:
        sb.launch_jump(["--jump", "box1"], ("ssh", "mac1"), helper="sb-helper")
        check("child-env-ssh-of-the-jump", took("ssh") == ["ran"])
        link = sb.JumpLink(find=lambda: ("ssh", "mac1"), helper=lambda host: "sb-helper").start()
        link.started.wait(5)
        if link.proc:
            link.proc.wait(10)
        check("child-env-ssh-of-the-link", took("ssh") == ["ran"])
        sb.jump("box1", "a", "w1:p1", "w1:t1", "sbjabc", False, "", keys="\\x02g/", wait=0, tty="/dev/ttys000")
        check("child-env-osascript", took("osa") == ["ran"])
        check("child-env-herdr-of-the-jump", took("herdr") == ["ran"])
    finally:
        sb.HERDR, sb.SSH, sb.OSASCRIPT = saved[:3]
        os.environ.clear()
        os.environ.update(saved[3])
    env_in = dict(fzf_env, PATH="/bin", KEEP="1", HOLDS_IT="x" + run)
    saved_env = dict(os.environ)
    os.environ.clear()
    os.environ.update(env_in)
    try:
        got = sb.child_env()
    finally:
        os.environ.clear()
        os.environ.update(saved_env)
    check("child-env-keeps-the-rest", sorted(got) == ["KEEP", "PATH"], sorted(got))

# 47. No python3 on PATH: the pane says what is missing and waits, instead of closing.
block("47. pane without python3")
pane_line = next(l for l in MANIFEST.split("[[panes]]", 1)[1].splitlines() if l.startswith("command = "))
pane_cmd = json.loads(pane_line.split("=", 1)[1])  # TOML basic strings use JSON's escapes
if HAVE_TOMLLIB:
    check("manifest-pane-command-read-right", pane_cmd == sb.tomllib.loads(MANIFEST)["panes"][0]["command"])
with tempfile.TemporaryDirectory() as d:
    bare = os.path.join(d, "bin")
    os.mkdir(bare)
    os.symlink(shutil.which("sh"), os.path.join(bare, "sh"))  # a shell and nothing else
    p = subprocess.Popen(pane_cmd, cwd=d, env=dict(os.environ, PATH=bare, HERDR_PLUGIN_ROOT=str(ROOT)),
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         universal_newlines=True)
    _time.sleep(1.0)
    waiting = p.poll() is None
    out, _ = p.communicate("\n", timeout=10)
    check("no-python-pane-waits-for-enter", waiting, out)
    check("no-python-pane-says-what-is-needed", p.returncode == 127 and "Python 3.9 or newer" in out
          and "PATH the herdr server runs with" in out and "Press Enter" in out, (p.returncode, out))
    # With python3 there, the same command runs the program (it stops at the fzf check here).
    env = dict(os.environ, HERDR_PLUGIN_ROOT=str(ROOT), SWITCHBOARD_FZF="", HERDR_BIN_PATH="/bin/false",
               PATH=os.path.dirname(sys.executable) + os.pathsep + os.environ.get("PATH", ""))
    r = subprocess.run(pane_cmd, cwd=d, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                       universal_newlines=True, timeout=20)
    check("pane-with-python-runs-the-program", r.returncode != 0 and "fzf" in r.stdout, r.stdout[-200:])

# 48. Once the pane may carry the temporary name, the name comes back and the focus goes out,
# whatever happens to the typing.
block("48. jump restores the name")
with tempfile.TemporaryDirectory(dir="/tmp") as d:
    calls48 = os.path.join(d, "calls")
    fh48 = executable(os.path.join(d, "herdr"), '#!/bin/sh\necho "$*" >> "%s"\n' % calls48)

    def calls_taken():
        lines = open(calls48).read().splitlines() if os.path.exists(calls48) else []
        if os.path.exists(calls48):
            os.remove(calls48)
        return lines

    class Osa48:
        def __init__(self, exc):
            self.exc, self.killed = exc, False

        def communicate(self, data, timeout=None):
            raise self.exc

        def kill(self):
            self.killed = True

    restored = ["--machine box1 pane rename w1:p1 sbjabc", "--machine box1 pane rename w1:p1 logs",
                "--machine box1 agent focus w1:p1"]
    saved48 = (sb.HERDR, sb.OSASCRIPT)
    sb.HERDR = str(fh48)
    try:
        args48 = dict(label="box1", kind="a", pane="w1:p1", tab="w1:t1", query="sbjabc", rename=True,
                      old_label="logs", keys="\\x02g/", wait=0, tty="/dev/ttys000")
        osa = Osa48(subprocess.TimeoutExpired(["osascript"], 10))
        rc = sb.jump(osa=osa, **args48)
        check("jump-osascript-timeout-restores", rc == 2 and calls_taken() == restored and osa.killed, rc)
        osa = Osa48(SystemExit(129))  # what main's handler raises on SIGHUP
        try:
            sb.jump(osa=osa, **args48)
            check("jump-hangup-propagates", False)
        except SystemExit:
            pass
        check("jump-hangup-restores", calls_taken() == restored and osa.killed)
        sb.OSASCRIPT = os.path.join(d, "no-such-osascript")
        rc = sb.jump(**args48)
        check("jump-no-osascript-restores", rc == 2 and calls_taken() == restored, rc)
    finally:
        sb.HERDR, sb.OSASCRIPT = saved48

# 49. The header says what happens with each value it refused, and nothing untrue: a refused
# jump key does not mean the default keys are in use.
block("49. config header wording")
with tempfile.TemporaryDirectory() as d:
    path = os.path.join(d, "config.toml")
    with open(path, "w") as f:
        f.write('[jump]\nenabled = true\ngoto = "prefix+shift+g"\n')
    _, warn = sb.load_config(path)
    check("header-refused-jump-key", warn == "config %s: bad value for jump.goto, so the jump is off" % path, warn)
    with open(path, "w") as f:
        f.write('lang = "es"\n[jump]\nenabled = true\ngoto = "prefix+shift+g"\n')
    _, warn = sb.load_config(path)
    check("header-refused-jump-key-es",
          warn == "config %s: valor inválido para jump.goto, así que el salto queda apagado" % path, warn)
    with open(path, "w") as f:
        f.write('nope = 1\n[refresh]\nlocal_seconds = 999\n')
    _, warn = sb.load_config(path)
    check("header-each-problem-says-what-happens",
          warn == "config %s: unknown option nope (ignored); bad value for refresh.local_seconds (default used)" % path,
          warn)

# 50. Nothing in the tests or the program waits without a bound on a child, a thread or a
# terminal. Exactly what is checked, in both files: every subprocess.run/check_output/call/
# check_call (also through an attribute, like sb.subprocess.run) passes timeout=; every
# communicate() passes a timeout (keyword or second argument) and every wait() and join() an
# argument or timeout=; select() has its fourth argument; os.wait() is never called, and
# os.waitpid/wait3/wait4 never with options 0. One exemption, pinned to its site: the popup's
# proc.communicate(first), its wait for fzf, which the user ends with a key or a signal.
block("50. bounded waits")
WAIT_EXEMPT = {("program", "popup", "proc.communicate(first)")}


def _calls_with_function(text):
    """(call node, name of the enclosing function or None) for every call in the source."""
    out = []

    def walk(node, fn):
        for child in ast.iter_child_nodes(node):
            name = child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else fn
            if isinstance(child, ast.Call):
                out.append((child, fn))
            walk(child, name)
    walk(ast.parse(text), None)
    return out


def _subprocess_call(func):
    """subprocess.X or anything.subprocess.X: the X, else None."""
    if not isinstance(func, ast.Attribute):
        return None
    owner = func.value
    owner_name = owner.id if isinstance(owner, ast.Name) else owner.attr if isinstance(owner, ast.Attribute) else ""
    return func.attr if owner_name == "subprocess" else None


for label, text in (("tests", pathlib.Path(__file__).read_text()), ("program", SOURCE)):
    unbounded, exempt_seen = [], set()
    for node, fn in _calls_with_function(text):
        func = node.func
        fname = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        owner = getattr(func.value, "id", "") if isinstance(func, ast.Attribute) else ""
        kws = {k.arg for k in node.keywords}
        seg = ast.get_source_segment(text, node) if fname == "communicate" else None  # slow: only where needed
        if (label, fn, seg) in WAIT_EXEMPT:
            exempt_seen.add((label, fn, seg))
            continue
        if _subprocess_call(func) in ("run", "check_output", "call", "check_call"):
            bad = "timeout" not in kws
        elif fname == "communicate" and isinstance(func, ast.Attribute):
            bad = "timeout" not in kws and len(node.args) < 2
        elif fname in ("wait", "join") and isinstance(func, ast.Attribute) and not isinstance(func.value, ast.Constant) \
                and owner != "os":
            bad = not node.args and "timeout" not in kws
        elif fname == "select" and isinstance(func, ast.Attribute):
            bad = len(node.args) < 4 and "timeout" not in kws
        elif owner == "os" and fname == "wait":
            bad = True
        elif owner == "os" and fname in ("waitpid", "wait3", "wait4"):
            opts = node.args[-1] if node.args else None
            bad = isinstance(opts, ast.Constant) and opts.value == 0
        else:
            bad = False
        if bad:
            unbounded.append(node.lineno)
    check("bounded-waits-%s" % label, not unbounded, unbounded)
    if label == "program":
        check("bounded-waits-exemption-pinned", exempt_seen == WAIT_EXEMPT, exempt_seen)

# 51. Everything the program starts gets env=child_env(), except the sites named here: fzf
# itself (it needs SWITCHBOARD_RUN_DIR), fzf_rejects (it runs before the run directory
# exists), and the --focus worker, whose env is child_env() plus the descriptor's variable.
block("51. every child gets child_env()")
ENV_EXCEPTIONS = {("popup", "dict(os.environ, SWITCHBOARD_RUN_DIR=tmp, SWITCHBOARD_LABELS=json.dumps(labels))"),
                  ("fzf_rejects", None), ("enter", "env")}
env_sites, env_exceptions = 0, set()
for node, fn in _calls_with_function(SOURCE):
    if _subprocess_call(node.func) not in ("run", "Popen", "check_output", "call", "check_call"):
        continue
    env_sites += 1
    env = next((k.value for k in node.keywords if k.arg == "env"), None)
    if isinstance(env, ast.Call) and getattr(env.func, "id", "") == "child_env":
        continue
    env_exceptions.add((fn, ast.get_source_segment(SOURCE, env) if env is not None else None))
check("child-env-at-every-site", env_exceptions == ENV_EXCEPTIONS and env_sites >= 8, (env_sites, env_exceptions))
enter_def = next(n for n in ast.walk(ast.parse(SOURCE)) if isinstance(n, ast.FunctionDef) and n.name == "enter")
check("worker-env-starts-from-child-env", "env = child_env(run_dir)" in ast.get_source_segment(SOURCE, enter_def))

# 52. A remote read may take the ssh timeout and then the fallback's: the wait for it is
# derived from that worst case, in one place, and nothing a read started outlives the program.
block("52. remote read bounds")
try:
    late_out, _ = _late.communicate(timeout=60)
except subprocess.TimeoutExpired:
    os.killpg(_late.pid, _signal.SIGKILL)
    late_out, _ = _late.communicate(timeout=10)
late_took = _time.time() - _late_t0
check("slow-ssh-then-late-fallback-is-listed", "late-remote" in late_out and "box1 offline" not in late_out
      and _late.returncode == 0, (late_took, [l for l in late_out.splitlines() if "box1" in l][:3]))
_ssh_left = []
for _name in ("ssh.pid", "ssh-child.pid"):
    try:
        _pid = int(open(os.path.join(_late_dir, _name)).read())
        os.kill(_pid, 0)
        _ssh_left.append(_name)
        os.kill(_pid, _signal.SIGKILL)
    except (OSError, ValueError):
        pass
check("timed-out-ssh-and-its-child-are-gone", not _ssh_left, _ssh_left)
check("remote-waits-from-one-place", SOURCE.count("herdr_on_bound(REMOTE_TIMEOUT)") == 2
      and sb.herdr_on_bound(6) >= 2 * 6, SOURCE.count("herdr_on_bound(REMOTE_TIMEOUT)"))
# A read still running when the program exits (its thread is abandoned) is killed with its
# group at exit, instead of running on without the timeout that was meant for it.
with tempfile.TemporaryDirectory(dir="/tmp") as d:
    pidfile = os.path.join(d, "pid")
    code = ("import importlib.machinery, importlib.util, os, sys, threading, time\n"
            "l = importlib.machinery.SourceFileLoader('sbx', sys.argv[1])\n"
            "m = importlib.util.module_from_spec(importlib.util.spec_from_loader('sbx', l))\n"
            "l.exec_module(m)\n"
            "threading.Thread(target=m.run_child, args=(['sh', '-c', 'echo $$ > %s; exec sleep 30'], 60),"
            " daemon=True).start()\n"
            "end = time.time() + 10\n"
            "while not os.path.exists(%r) and time.time() < end:\n"
            "    time.sleep(0.05)\n"
            "time.sleep(0.2)\n") % (pidfile, pidfile)
    subprocess.run([sys.executable, "-c", code, str(TOOL)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, timeout=30)
    try:
        orphan = int(open(pidfile).read())
    except (OSError, ValueError):
        orphan = None
    alive, end = orphan is not None, _time.time() + 3
    while alive and _time.time() < end:
        try:
            os.kill(orphan, 0)
            _time.sleep(0.05)
        except OSError:
            alive = False
    check("exit-ends-a-running-read", orphan is not None and not alive, orphan)
    if alive:
        os.kill(orphan, _signal.SIGKILL)
    # The same when a signal interrupts the read itself (main turns SIGTERM into an exit, the
    # read unwinds before the exit cleanup runs).
    os.remove(pidfile)
    code2 = ("import importlib.machinery, importlib.util, signal, sys\n"
             "l = importlib.machinery.SourceFileLoader('sbx', sys.argv[1])\n"
             "m = importlib.util.module_from_spec(importlib.util.spec_from_loader('sbx', l))\n"
             "l.exec_module(m)\n"
             "signal.signal(signal.SIGTERM, m._exit_on_signal)\n"
             "m.run_child(['sh', '-c', 'echo $$ > %s; exec sleep 30'], 60)\n") % pidfile
    reader = subprocess.Popen([sys.executable, "-c", code2, str(TOOL)], stdin=subprocess.DEVNULL,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    end = _time.time() + 10
    while not os.path.exists(pidfile) and _time.time() < end:
        _time.sleep(0.05)
    _time.sleep(0.2)
    reader.send_signal(_signal.SIGTERM)
    try:
        reader.wait(10)
    except subprocess.TimeoutExpired:
        reader.kill()
        reader.wait(10)
    try:
        orphan = int(open(pidfile).read())
    except (OSError, ValueError):
        orphan = None
    alive, end = orphan is not None, _time.time() + 3
    while alive and _time.time() < end:
        try:
            os.kill(orphan, 0)
            _time.sleep(0.05)
        except OSError:
            alive = False
    check("signal-ends-a-running-read", orphan is not None and not alive and reader.returncode == 128 + 15,
          (orphan, alive, reader.returncode))
    if alive:
        os.kill(orphan, _signal.SIGKILL)

# 53. What the program counts on from fzf, measured with the real fzf and a parent leading
# the terminal's session (so the kernel's hang-up ends nothing). Only a preview, and a
# bg-transform, run in a process group of their own; transform-footer (--copy), transform
# (--enter) and execute (--select) run in fzf's own group, which fzf never kills. What a
# command left behind when it finished outlives fzf, a preview's included. While fzf waits
# for a synchronous command it does not act on SIGTERM; it does as soon as the command
# returns, and puts the terminal back. If a later fzf changes any of this, these say so.
block("53. what fzf runs, and how it ends it")


def _alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def fzf_premise():
    """Returns ({kind: (in a group of its own, what it left still alive after fzf left)},
    fzf still there 1 s after SIGTERM while a command runs, fzf gone once that command
    returned, the main screen back)."""
    import fcntl as _f53
    import struct as _st53
    import termios as _tm53
    with tempfile.TemporaryDirectory(dir="/tmp") as d:
        log, fzf_pid_file, hold_pid_file = (os.path.join(d, n) for n in ("log", "fzf.pid", "hold.pid"))
        cmd = executable(os.path.join(d, "cmd"), '#!/bin/sh\nsleep 300 >/dev/null 2>&1 &\n'
                         'echo "$1 $(ps -ww -o pgid= -p $$ | tr -d " ") $!" >> "%s"\n' % log)
        hold = executable(os.path.join(d, "hold"), '#!/bin/sh\necho $$ > "%s"\nexec sleep 300\n' % hold_pid_file)
        argv = [fzf_real, "--with-shell", "sh -c", "--preview", "%s preview" % cmd,
                "--bind", "ctrl-y:transform-footer(%s transform-footer)" % cmd,
                "--bind", "ctrl-t:transform(%s transform)" % cmd,
                "--bind", "ctrl-b:bg-transform-footer(%s bg-transform-footer)" % cmd,
                "--bind", "ctrl-o:execute(%s execute)" % cmd,
                "--bind", "ctrl-x:execute(%s)" % hold]
        pid, fd = _pty.fork()
        if pid == 0:
            os.environ["TERM"] = "xterm-256color"
            r, w = os.pipe()
            os.write(w, b"a\nb\n")
            os.close(w)
            os.dup2(r, 0)
            inner = os.fork()
            if inner == 0:
                os.execv(fzf_real, argv)
            with open(fzf_pid_file + ".tmp", "w") as f:
                f.write(str(inner))
            os.rename(fzf_pid_file + ".tmp", fzf_pid_file)
            quit_at = _time.time() + 60
            while _time.time() < quit_at and not os.waitpid(inner, os.WNOHANG)[0]:
                _time.sleep(0.02)
            _time.sleep(30)  # still leading the session; finish() ends this group
            os._exit(0)
        leftovers, kinds = [], {}
        try:
            _f53.ioctl(fd, _tm53.TIOCSWINSZ, _st53.pack("HHHH", 30, 100, 0, 0))

            def logged():
                return [l.split() for l in open(log).read().splitlines()] if os.path.exists(log) else []
            read_until(fd, lambda _b: os.path.exists(fzf_pid_file) and any(r[0] == "preview" for r in logged()), 10)
            fzf_pid = int(open(fzf_pid_file).read())
            fzf_group = os.getpgid(fzf_pid)
            for key, kind in ((b"\x19", "transform-footer"), (b"\x14", "transform"),
                              (b"\x02", "bg-transform-footer"), (b"\x0f", "execute")):
                os.write(fd, key)
                read_until(fd, lambda _b: any(r[0] == kind for r in logged()), 5)
            for r in logged():
                if len(r) == 3 and r[0] not in kinds:
                    kinds[r[0]] = int(r[1]) != fzf_group
                    leftovers.append((r[0], int(r[2])))
            os.write(fd, b"\x18")  # ctrl-x: a command that waits
            read_until(fd, lambda _b: os.path.exists(hold_pid_file) and os.path.getsize(hold_pid_file), 5)
            hold_pid = int(open(hold_pid_file).read())
            os.kill(fzf_pid, _signal.SIGTERM)
            read_until(fd, lambda _b: False, 1.0)
            waited = _alive(fzf_pid)
            os.kill(hold_pid, _signal.SIGTERM)  # the command returns
            after = read_until(fd, lambda _b: not _alive(fzf_pid), 3)
            after += read_until(fd, lambda _b: False, 0.2)
            gone = not _alive(fzf_pid)
            result = {k: (kinds[k], _alive(p)) for k, p in leftovers}
            return result, waited, gone, b"\x1b[?1049l" in after
        finally:
            for _k, p in leftovers:
                try:
                    os.kill(p, _signal.SIGKILL)
                except OSError:
                    pass
            finish(pid, fd, 0)


if fzf_real and not sb.dependency_problems(python=(3, 12, 0), fzf=fzf_real):
    groups, waited, gone, main_screen = fzf_premise()
    check("fzf-runs-only-previews-and-bg-actions-in-a-group-of-their-own",
          {k: v[0] for k, v in groups.items()} == {"preview": True, "bg-transform-footer": True,
                                                   "transform-footer": False, "transform": False, "execute": False},
          groups)
    check("fzf-leaves-alive-what-a-finished-command-left", len(groups) == 5 and all(v[1] for v in groups.values()),
          groups)
    check("fzf-waits-for-a-command-before-acting-on-sigterm", waited)
    check("fzf-acts-on-sigterm-once-the-command-returns", gone and main_screen, (gone, main_screen))

# --enter starts one thing, the --focus worker, in a session of its own on purpose (the focus
# must land after Esc; herdr_on_bound bounds it, block 54); --focus-wait starts nothing.
_defs = {n.name: n for n in ast.walk(ast.parse(SOURCE)) if isinstance(n, ast.FunctionDef)}
_starts = ("Popen", "run", "run_child", "run_out", "herdr", "herdr_on", "snapshot", "machine_info", "saved_machines")
_focus_wait_calls = {(c.func.attr if isinstance(c.func, ast.Attribute) else getattr(c.func, "id", ""))
                     for c in ast.walk(_defs["focus_wait"]) if isinstance(c, ast.Call)}
check("focus-wait-starts-nothing", not (_focus_wait_calls & set(_starts)), sorted(_focus_wait_calls & set(_starts)))
_enter_starts = [c for c in ast.walk(_defs["enter"]) if isinstance(c, ast.Call)
                 and (c.func.attr if isinstance(c.func, ast.Attribute) else getattr(c.func, "id", "")) in _starts]
check("enter-starts-only-the-detached-worker", len(_enter_starts) == 1
      and any(k.arg == "start_new_session" and getattr(k.value, "value", None) is True for k in _enter_starts[0].keywords),
      len(_enter_starts))

# 54. herdr_on_bound covers everything herdr_on() can do, from the timeouts it uses, and
# --focus-wait waits that long: the focus above lands after the old deadline and is reported.
block("54. herdr_on's bound")
try:
    slowfocus_out, _ = _slowfocus_wait.communicate(timeout=60)
except subprocess.TimeoutExpired:
    _slowfocus_wait.kill()
    slowfocus_out, _ = _slowfocus_wait.communicate(timeout=10)
check("focus-wait-covers-the-workers-worst-case", _slowfocus_name is not None
      and slowfocus_out.strip().startswith("ready on box1"), slowfocus_out.strip())
_bound_def = next(n for n in ast.walk(ast.parse(SOURCE)) if isinstance(n, ast.FunctionDef) and n.name == "herdr_on_bound")
_bound_names = {n.id for n in ast.walk(_bound_def) if isinstance(n, ast.Name)}
_bound_numbers = [n.value for n in ast.walk(_bound_def) if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
                  and not isinstance(n.value, bool)]
check("bound-built-from-the-named-timeouts", {"MACHINE_LIST_TIMEOUT", "KILL_WAIT", "SPAWN_MARGIN", "timeout"} <= _bound_names
      and _bound_numbers == [2], (sorted(_bound_names), _bound_numbers))
check("bound-timeouts-are-the-ones-used", 'herdr(["machine", "list", "--json"], MACHINE_LIST_TIMEOUT)' in SOURCE
      and "p.communicate(timeout=KILL_WAIT)" in SOURCE and SOURCE.count("herdr_on_bound(REMOTE_TIMEOUT)") == 2)
check("bound-covers-lookup-two-reads-and-kill-waits",
      sb.herdr_on_bound(8) >= sb.MACHINE_LIST_TIMEOUT + sb.KILL_WAIT + 2 * (8 + sb.KILL_WAIT), sb.herdr_on_bound(8))
# find_client's wait for its HIDIdleTime probes, from the same constants: one probe's timeout,
# the wait after killing it, and the margin for starting it.
check("find-client-backstop-from-the-named-constants",
      "deadline = time.time() + IDLE_TIMEOUT + KILL_WAIT + SPAWN_MARGIN" in SOURCE
      and "run_out(argv, timeout=IDLE_TIMEOUT)" in SOURCE)

# 55. Nothing the watch loop started writes into a directory while it is removed: watch()
# writes the rows only under the lock the popup holds while it removes the run directory, and
# never after stop. (Its remote reads are not waited for: block 58.)
block("55. the watch loop and the directories it writes")
with tempfile.TemporaryDirectory(dir="/tmp") as d:
    rows55 = private_tmp(d, "rows55")

    # A rows write in progress holds the lock; the closer gets it only after; after stop, none.
    data55 = {"n": 1}
    lv = sb.Live([], sb.entries_from(snap([pane("w1:p1")], [agent("w1:p1", "idle", 1)]), "", "here", 0),
                 fetch=lambda m="", t=None, i=None: snap([pane("w1:p1")], [agent("w1:p1", "idle", data55["n"])]),
                 cache=False)
    lv.changed()
    entered, release, writes_done = _threading.Event(), _threading.Event(), [0]
    real_replace = sb.os.replace

    def held_replace(src, dst, *a, **kw):
        if "rows" in str(dst) and kw.get("dst_dir_fd") is not None:
            entered.set()
            release.wait(5)
            writes_done[0] += 1
        return real_replace(src, dst, *a, **kw)
    writes = _threading.Lock()
    stop = _threading.Event()
    sb.os.replace = held_replace
    try:
        t = _threading.Thread(target=sb.watch, args=(lv, short_sock("w55b"), os.path.join(rows55, "rows"), stop,
                                                     None, writes), daemon=True)
        t.start()
        data55["n"] = 2
        entered.wait(5)  # a pass is writing the rows
        early = writes.acquire(timeout=0.3)
        if early:
            writes.release()
        release.set()
        got = writes.acquire(timeout=5)
        data55["n"] = 3  # the next pass has something to write, and waits for the lock
        _time.sleep(0.4)
        stop.set()
        if got:
            writes.release()
        t.join(5)
    finally:
        sb.os.replace = real_replace
    check("closer-waits-for-a-write-in-progress", not early and got, (early, got))
    check("no-rows-write-after-stop", writes_done[0] == 1 and not t.is_alive(), writes_done[0])
check("popup-removes-the-run-dir-under-the-lock", "held = writes.acquire(timeout=WRITE_WAIT)\n        try:\n"
      "            remove_run_dir(tmp, run_fd)" in SOURCE)

# 56. Reads started by the commands fzf runs end with those commands, with the real fzf: a
# popup over a remote machine whose `pane read` over ssh hangs. The fake ssh records each
# read: which command started it (from that command's line), its pid and the command's pid
# (yes/no checks only). Previews: cursor moves and Esc leave none, and a preview's read is
# killed at its timeout. ctrl-y (--copy) and ctrl-o (--select), which fzf waits for in its
# own process group: the popup told to leave (SIGTERM, SIGHUP) while one hangs ends the
# command, its read and a helper the read left behind, fzf puts the terminal back, and it is
# quick, whether the popup leads its terminal's session or a parent does (then the kernel's
# hang-up ends nothing).
block("56. reads under fzf end with fzf")


def popup_with_hung_reads(drive, remote_timeout="60", leader=True, snapshot_hangs=False):
    """Open the popup on remote rows whose pane reads hang; drive(fd, pump, popup_pid, reads,
    leave) does the keys: pump(pred, seconds) reads the terminal, leave(sig) signals the popup.
    A read of --copy or --select also leaves a helper that is no longer below it (its parent
    exited), as a daemon does. leader=False: a parent leads the terminal's session and
    outlives the popup. Returns a dict: rc; took, seconds from leave() to the popup's exit;
    terminal, what fzf left on the way out (and, with a parent leading, the terminal's echo
    and signal keys); started and left, {command: [pid, ...]} of the hung reads and of the
    commands that started them ("helper": those helpers), and of those still alive 3 s after
    the popup left. snapshot_hangs: after the first one, every snapshot read of that machine
    hangs too ("snapshot"), and a read of it is under way whenever drive() acts."""
    import fcntl as _f56
    import struct as _st56
    import termios as _tm56
    with tempfile.TemporaryDirectory(dir="/tmp") as d:
        root = private_tmp(d, "runs")
        reads, popup_pid, popup_rc = (os.path.join(d, n) for n in ("reads", "popup.pid", "popup.rc"))
        with open(os.path.join(d, "machines.json"), "w") as f:
            json.dump([{"id": "m1", "label": "box1", "enabled": True, "target": "box1-host"}], f)
        with open(os.path.join(d, "local.json"), "w") as f:
            json.dump({"result": {"snapshot": snap([pane("w1:p1")], [agent("w1:p1", "idle", 1, title="here")])}}, f)
        remote = [pane("w1:p%d" % i, tab="w1:t%d" % i) for i in range(1, 6)]
        with open(os.path.join(d, "m1.json"), "w") as f:
            json.dump({"result": {"snapshot": snap(remote, [agent("w1:p%d" % i, "blocked", 9 - i, title="far-%d" % i,
                                                                   tab="w1:t%d" % i) for i in range(1, 6)])}}, f)
        # Each pane read also notes when it started and which pane: printed only when a check fails.
        executable(os.path.join(d, "now"), "#!%s\nimport time\nprint('%%.3f' %% time.time())\n" % sys.executable)
        fake_ssh = executable(os.path.join(d, "ssh"), '#!/bin/sh\ncase "$*" in\n'
                              '  *"pane read"*) k=other; p=; prev=\n'
                              '    for w in $*; do [ "$prev" = read ] && p=$w; prev=$w; done\n'
                              '    echo "$$ $("%(d)s/now") $p" >> "%(d)s/times"\n'
                              '    case "$(ps -ww -o command= -p $PPID)" in\n'
                              '      *--copy*) k=copy ;; *--select*) k=select ;; *--preview*) k=preview ;;\n'
                              '    esac\n'
                              '    case $k in copy|select)\n'
                              '      sh -c \'sleep 120 >/dev/null 2>&1 & echo "helper $!"\' >> "%(d)s/reads" ;;\n'
                              '    esac\n'
                              '    echo "$k $$ $PPID" >> "%(d)s/reads"; exec sleep 120 ;;\n'
                              '  *"api snapshot"*) if [ -e "%(d)s/answered" ] && [ -n "%(hang)s" ]; then\n'
                              '      echo "snapshot $$" >> "%(d)s/reads"; exec sleep 120; fi\n'
                              '    touch "%(d)s/answered"; cat "%(d)s/m1.json" ;;\n'
                              '  *) exit 1 ;;\nesac\n' % {"d": d, "hang": "yes" if snapshot_hangs else ""})
        fh = executable(os.path.join(d, "herdr"), '#!/bin/sh\ncase "$*" in\n'
                        '  "machine list --json") cat "%(d)s/machines.json" ;;\n'
                        '  "api snapshot") cat "%(d)s/local.json" ;;\n'
                        '  *) exit 1 ;;\nesac\n' % {"d": d})
        pid, fd = _pty.fork()
        if pid == 0:
            os.environ.update(TERM="xterm-256color", HERDR_BIN_PATH=str(fh), SWITCHBOARD_SSH=str(fake_ssh),
                              SWITCHBOARD_REMOTE_TIMEOUT=remote_timeout, SWITCHBOARD_RUN_ROOT=root,
                              SWITCHBOARD_REMOTE_EVERY="0.3", HERDR_PLUGIN_STATE_DIR=os.path.join(d, "state"))
            if leader:
                os.execv(sys.executable, [sys.executable, "-B", str(TOOL)])
            inner = os.fork()
            if inner == 0:
                os.execv(sys.executable, [sys.executable, "-B", str(TOOL)])
            with open(popup_pid + ".tmp", "w") as f:
                f.write(str(inner))
            os.rename(popup_pid + ".tmp", popup_pid)
            done, st, quit_at = 0, 0, _time.time() + 60
            while not done and _time.time() < quit_at:
                done, st = os.waitpid(inner, os.WNOHANG)
                _time.sleep(0.02)
            with open(popup_rc + ".tmp", "w") as f:
                f.write(str(os.waitstatus_to_exitcode(st) if done else -9))
            os.rename(popup_rc + ".tmp", popup_rc)
            _time.sleep(30)  # still leading the session; finish() ends this group
            os._exit(0)
        out, sent = [b""], {}

        def pump(pred, seconds):
            out[0] += read_until(fd, lambda b: pred(out[0] + b), seconds)

        def leave(sig):
            sent.update(t=_time.time(), mark=len(out[0]))
            os.kill(target, sig)
        _f56.ioctl(fd, _tm56.TIOCSWINSZ, _st56.pack("HHHH", 30, 160, 0, 0))
        pump(lambda b: b"far-1" in sb.ANSI.sub("", b.decode("utf-8", "replace")).encode(), 15)
        pump(lambda _b: os.path.exists(reads), 10)  # the first remote preview is hanging
        if snapshot_hangs:
            pump(lambda _b: any(l.startswith("snapshot ") for l in open(reads).read().splitlines()), 10)
        pump(lambda _b: leader or os.path.exists(popup_pid), 5)
        target = pid if leader else int(open(popup_pid).read())
        drive(fd, pump, target, reads, leave)
        rc, end = None, _time.time() + 30
        while rc is None and _time.time() < end:
            pump(lambda _b: False, 0.05)
            if leader:
                done, st = os.waitpid(pid, os.WNOHANG)
                if done:
                    rc = os.waitstatus_to_exitcode(st)
            elif os.path.exists(popup_rc):
                rc = int(open(popup_rc).read())
            _time.sleep(0.01)
        result = {"rc": rc, "took": _time.time() - sent["t"] if "t" in sent and rc is not None else None}
        pump(lambda _b: False, 0.3)
        after = out[0][sent.get("mark", len(out[0])):]
        result["terminal"] = {"main-screen": b"\x1b[?1049l" in after, "mouse-off": b"\x1b[?1000l" in after}
        if not leader:
            lflag = _tm56.tcgetattr(fd)[3]
            result["terminal"].update(echo=bool(lflag & _tm56.ECHO), isig=bool(lflag & _tm56.ISIG))
        started = {}
        for line in (open(reads).read().splitlines() if os.path.exists(reads) else []):
            kind, *found = line.split()
            started.setdefault(kind, []).extend(int(p) for p in found)
        everything = [p for ps in started.values() for p in ps]
        alive, end = list(everything), _time.time() + 3
        while alive and _time.time() < end:
            _time.sleep(0.1)
            alive = [p for p in alive if _alive(p)]
        for p in alive:  # never leave them behind, whatever the result
            try:
                os.kill(p, _signal.SIGKILL)
            except OSError:
                pass
        result["started"] = started
        result["left"] = {k: [p for p in v if p in alive] for k, v in started.items() if set(v) & set(alive)}
        result["run_dir_left"] = sorted(os.listdir(root))
        # For each read still alive: its command, its pane and when it started against the signal.
        times = {}
        for line in (open(os.path.join(d, "times")).read().splitlines() if os.path.exists(os.path.join(d, "times"))
                     else []):
            parts = line.split()
            if len(parts) >= 2:
                times[int(parts[0])] = (float(parts[1]), parts[2] if len(parts) > 2 else "")
        result["left_detail"] = sorted((k, times[p][1], round(times[p][0] - sent["t"], 2) if "t" in sent else None)
                                       for k, v in result["left"].items() for p in v if p in times)
        finish(pid, fd, 0)
        return result


def moves_then_esc(fd, pump, pid, reads, leave):
    for _ in range(3):
        os.write(fd, b"\x1b[B")
        pump(lambda _b: False, 1.0)
    os.write(fd, b"\x1b")


def key_then(key, kind, sig):
    def drive(fd, pump, pid, reads, leave):
        os.write(fd, key)
        pump(lambda _b: any(l.startswith(kind + " ") for l in open(reads).read().splitlines()), 5)  # it hangs now
        leave(sig)
    return drive


if fzf_real and not sb.dependency_problems(python=(3, 12, 0), fzf=fzf_real):
    r = popup_with_hung_reads(moves_then_esc)
    check("preview-reads-end-with-fzf", len(r["started"].get("preview", [])) >= 6 and not r["left"] and r["rc"] == 0,
          (r["started"].keys(), r["left"], r["rc"]))
    for key, kind, sig in ((b"\x19", "copy", _signal.SIGTERM), (b"\x0f", "select", _signal.SIGHUP)):
        for leader in (True, False):
            r = popup_with_hung_reads(key_then(key, kind, sig), leader=leader, snapshot_hangs=True)
            name = "%s-%s" % (kind, "leading" if leader else "not-leading")
            check(name + "-command-and-reads-end-with-the-popup", r["started"].get(kind) and r["started"].get("helper")
                  and r["started"].get("snapshot") and not r["left"] and not r["run_dir_left"]
                  and r["rc"] == 128 + sig, (r["rc"], sorted(r["started"]), r["left"], r["run_dir_left"],
                                             r["left_detail"]))
            check(name + "-terminal-comes-back", all(r["terminal"].values()), r["terminal"])
            # Left before end_fzf's last step (SIGKILL) was due: fzf ended on its own SIGTERM.
            check(name + "-quick", r["took"] is not None and r["took"] < 2 * sb.FZF_END_WAIT, r["took"])
    # A second signal while the close waits for fzf (end_fzf, after the first SIGTERM) changes
    # nothing: the first one's status, the run directory gone, nothing left, the terminal back.
    def two_signals(fd, pump, pid, reads, leave):
        key_then(b"\x19", "copy", _signal.SIGTERM)(fd, pump, pid, reads, leave)
        pump(lambda _b: False, 0.4)
        try:
            os.kill(pid, _signal.SIGHUP)
        except OSError:
            pass
    for leader in (False, True):
        r = popup_with_hung_reads(two_signals, leader=leader, snapshot_hangs=True)
        check("second-signal-during-the-close-is-ignored" + ("-leading" if leader else ""),
              r["rc"] == 128 + 15 and not r["left"] and not r["run_dir_left"] and all(r["terminal"].values()),
              (r["rc"], r["left"], r["run_dir_left"], r["terminal"], r["left_detail"]))
    # A read that times out inside a preview is killed then, with the popup still open and the
    # cursor where it was.
    timed_out = []

    def wait_past_the_timeout(fd, pump, pid, reads, leave):
        pump(lambda _b: False, 1.5 + sb.PS_TIMEOUT + 1.5)  # remote_timeout 1.5 s, the kill, a margin
        timed_out.extend(int(l.split()[1]) for l in open(reads).read().splitlines())
        timed_out[:] = [p for p in timed_out if _alive(p)]
        os.write(fd, b"\x1b")
    popup_with_hung_reads(wait_past_the_timeout, remote_timeout="1.5")
    check("preview-read-killed-at-its-timeout", not timed_out, timed_out)

# 57. Each mode's reads are bounded by what really ends that mode. A read that times out
# leaves nothing holding its output pipe: in --preview, the read and everything below it
# (fzf kills the preview's group only while the preview runs); in --copy and --select (fzf
# never kills those), the read's own process group, which also holds what left the read's
# tree, as a daemon does. And end_fzf's last step: with everything below fzf ignoring
# SIGTERM, within its stated bound, everything below fzf goes, nothing else does, and the
# terminal is put back.
block("57. each mode's reads; end_fzf's last step")


def holder_after_timeout(mode, orphan):
    """Run `switchboard MODE ROW` alone, in a session of its own with no terminal (so, as under
    fzf, nobody hangs anything up when it exits), over a fake ssh whose pane read hangs and
    leaves a process holding the read's output pipe: a child of the read, or (orphan) one
    whose parent has exited already. Returns (that process was started, it is still alive
    KILL_WAIT + PS_TIMEOUT + 2 s after the read's timeout of 1.5 s)."""
    with tempfile.TemporaryDirectory(dir="/tmp") as d:
        holder = os.path.join(d, "holder")
        with open(os.path.join(d, "machines.json"), "w") as f:
            json.dump([{"id": "m1", "label": "box1", "enabled": True, "target": "box1-host"}], f)
        spawn = ("sh -c 'sleep 120 & echo $! > \"%s\"'" if orphan else "sleep 120 & echo $! > \"%s\"") % holder
        fake_ssh = executable(os.path.join(d, "ssh"), '#!/bin/sh\ncase "$*" in\n'
                              '  *"pane read"*) %s; exec sleep 120 ;;\n  *) exit 1 ;;\nesac\n' % spawn)
        fh = executable(os.path.join(d, "herdr"), '#!/bin/sh\ncase "$*" in\n'
                        '  "machine list --json") cat "%s/machines.json" ;;\n  *) exit 1 ;;\nesac\n' % d)
        p = subprocess.Popen([sys.executable, "-B", str(TOOL), mode, "m1|a|w1:p1|w1:t1"], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
                             env=dict(os.environ, HERDR_BIN_PATH=str(fh), SWITCHBOARD_SSH=str(fake_ssh),
                                      SWITCHBOARD_REMOTE_TIMEOUT="1.5", HERDR_PLUGIN_STATE_DIR=os.path.join(d, "state")))
        hp, end = None, _time.time() + 10
        while hp is None and _time.time() < end:
            if os.path.exists(holder) and os.path.getsize(holder):
                hp = int(open(holder).read())
            _time.sleep(0.05)
        end = _time.time() + 1.5 + sb.KILL_WAIT + sb.PS_TIMEOUT + 2
        while hp is not None and _alive(hp) and _time.time() < end:
            _time.sleep(0.05)
        alive = hp is not None and _alive(hp)
        for kill in (lambda: os.kill(hp, _signal.SIGKILL), lambda: os.killpg(p.pid, _signal.SIGKILL)):
            try:
                kill()
            except (OSError, TypeError):
                pass
        p.wait(5)
        return hp is not None, alive


for mode, orphan in (("--preview", False), ("--copy", True), ("--select", True)):
    found, alive = holder_after_timeout(mode, orphan)
    check("%s-read-timeout-ends-what-holds-its-pipe" % mode[2:], found and not alive, (found, alive))

# A preview fzf starts once the popup has begun ending it reads nothing: end_fzf may have looked
# for what is below fzf already, and fzf need not kill it on its way out. Nor does one that gets
# going only after the popup has removed its run directory. Its run directory as usual: it reads.
# Outside the popup (no run directory given): it reads.
with tempfile.TemporaryDirectory(dir="/tmp") as d:
    run57 = private_tmp(d, "run")
    with open(os.path.join(d, "machines.json"), "w") as f:
        json.dump([{"id": "m1", "label": "box1", "enabled": True, "target": "box1-host"}], f)
    ssh57 = executable(os.path.join(d, "ssh"), '#!/bin/sh\ncase "$*" in\n'
                       '  *"pane read"*) echo read >> "%s/reads"; echo screen ;;\n  *) exit 1 ;;\nesac\n' % d)
    herdr57 = executable(os.path.join(d, "herdr"), '#!/bin/sh\ncase "$*" in\n'
                         '  "machine list --json") cat "%s/machines.json" ;;\n  *) exit 1 ;;\nesac\n' % d)
    env57 = dict(os.environ, HERDR_BIN_PATH=str(herdr57), SWITCHBOARD_SSH=str(ssh57),
                 HERDR_PLUGIN_STATE_DIR=os.path.join(d, "state"))
    reads57 = []
    for case in ("open", "closing", "removed", "outside"):
        if case == "closing":
            open(os.path.join(run57, "closing"), "w").close()
        env = dict(env57, SWITCHBOARD_RUN_DIR=run57 if case != "removed" else os.path.join(d, "gone"))
        if case == "outside":
            del env["SWITCHBOARD_RUN_DIR"]
        subprocess.run([sys.executable, "-B", str(TOOL), "--preview", "m1|a|w1:p1|w1:t1"], stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30, env=env)
        reads57.append(len(open(os.path.join(d, "reads")).read().split()) if os.path.exists(os.path.join(d, "reads"))
                       else 0)
    # Reads counted so far after each case: one, still one, still one, two.
    check("preview-reads-nothing-once-the-popup-is-closing", reads57[:2] == [1, 1], reads57)
    check("preview-reads-nothing-once-the-run-dir-is-gone", reads57[1:3] == [1, 1], reads57)
    check("preview-reads-outside-the-popup", reads57[0] == 1 and reads57[3] == 2, reads57)

# end_fzf's last step, on a stand-in for fzf that ignores SIGTERM, as do its child and
# grandchild. The terminal is a pty: the stand-in puts it in raw mode on the alternate screen.
with tempfile.TemporaryDirectory(dir="/tmp") as d:
    import termios as _tm57
    master, slave = os.openpty()
    saved = _tm57.tcgetattr(slave)
    pids = os.path.join(d, "pids")
    stand_in = ("import os, signal, sys, time, tty\n"
                "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
                "fd = int(sys.argv[1])\ntty.setraw(fd)\nos.write(fd, b'\\x1b[?1049h\\x1b[?1000h')\n"
                "if os.fork() == 0:\n"
                "    if os.fork() == 0:\n"
                "        open(sys.argv[2], 'a').write('%d\\n' % os.getpid())\n"
                "    else:\n"
                "        open(sys.argv[2], 'a').write('%d\\n' % os.getpid())\n"
                "time.sleep(60)\n")
    unrelated = subprocess.Popen(["sleep", "60"], stdin=subprocess.DEVNULL, start_new_session=True)
    fake_fzf = subprocess.Popen([sys.executable, "-c", stand_in, str(slave), pids], stdin=subprocess.DEVNULL,
                                pass_fds=(slave,))
    end = _time.time() + 10
    while _time.time() < end and not (os.path.exists(pids) and len(open(pids).read().split()) == 2):
        _time.sleep(0.05)
    below = [int(x) for x in open(pids).read().split()] if os.path.exists(pids) else []
    t0 = _time.time()
    sb.end_fzf(fake_fzf, (slave, saved))
    took = _time.time() - t0
    left, end = list(below), _time.time() + 3
    while left and _time.time() < end:
        _time.sleep(0.05)
        left = [p for p in left if _alive(p)]
    shown = read_until(master, lambda _b: False, 0.3)
    lflag = _tm57.tcgetattr(slave)[3]
    check("end-fzf-last-step-ends-everything-below-fzf", len(below) == 2 and not left and fake_fzf.poll() is not None,
          (below, left, fake_fzf.poll()))
    check("end-fzf-touches-nothing-else", unrelated.poll() is None)
    check("end-fzf-within-its-bound", 2 * sb.FZF_END_WAIT <= took <= 3 * sb.FZF_END_WAIT + 2 * sb.PS_TIMEOUT, took)
    check("end-fzf-last-step-puts-the-terminal-back", b"\x1b[?1049l" in shown and b"\x1b[?1000l" in shown
          and bool(lflag & _tm57.ECHO) and bool(lflag & _tm57.ICANON), (shown[-60:], lflag))
    for p in left + [unrelated.pid]:
        try:
            os.kill(p, _signal.SIGKILL)
        except OSError:
            pass
    unrelated.wait(5)
    if fake_fzf.poll() is None:
        fake_fzf.kill()
        fake_fzf.wait(5)
    os.close(master)
    os.close(slave)

# The same last step from the popup itself, with a stand-in fzf that ignores SIGTERM and
# leaves the terminal raw, on the alternate screen, with the mouse on: the popup told to leave
# puts the terminal back from what it saved before starting fzf. A parent leads the session.
with tempfile.TemporaryDirectory(dir="/tmp") as d:
    import fcntl as _f57
    import struct as _st57
    import termios as _tm57b
    ready, popup_pid, popup_rc = (os.path.join(d, n) for n in ("ready", "popup.pid", "popup.rc"))
    seen = os.path.join(d, "closing-seen")  # what the stand-in finds when the popup's SIGTERM comes
    stuck_fzf = executable(os.path.join(d, "fzf"), "#!%s\nimport os, signal, sys, time, tty\n"
                           "if '--version' in sys.argv:\n    print('0.74.2')\n    sys.exit(0)\n"
                           "def noted(*_):\n"
                           "    run = os.environ.get('SWITCHBOARD_RUN_DIR', '')\n"
                           "    mark = os.path.join(run, 'closing')\n"
                           "    size = os.path.getsize(mark) if os.path.exists(mark) else -1\n"
                           "    open(%r, 'a').write('%%s %%d\\n' %% (os.path.exists(mark), size))\n"
                           "signal.signal(signal.SIGTERM, noted)\n"
                           "fd = os.open('/dev/tty', os.O_RDWR)\ntty.setraw(fd)\n"
                           "os.write(fd, b'\\x1b[?1049h\\x1b[?1000h')\nopen(%r, 'w').close()\ntime.sleep(60)\n"
                           % (sys.executable, seen, ready))
    with open(os.path.join(d, "local.json"), "w") as f:
        json.dump({"result": {"snapshot": snap([pane("w1:p1")], [agent("w1:p1", "idle", 1, title="here")])}}, f)
    fh = executable(os.path.join(d, "herdr"), '#!/bin/sh\ncase "$*" in\n  "machine list --json") echo "[]" ;;\n'
                    '  "api snapshot") cat "%s/local.json" ;;\n  *) exit 1 ;;\nesac\n' % d)
    pid, fd = _pty.fork()
    if pid == 0:
        os.environ.update(TERM="xterm-256color", HERDR_BIN_PATH=str(fh), SWITCHBOARD_FZF=str(stuck_fzf),
                          SWITCHBOARD_RUN_ROOT=private_tmp(d, "runs"), HERDR_PLUGIN_STATE_DIR=os.path.join(d, "state"))
        inner = os.fork()
        if inner == 0:
            os.execv(sys.executable, [sys.executable, "-B", str(TOOL)])
        with open(popup_pid + ".tmp", "w") as f:
            f.write(str(inner))
        os.rename(popup_pid + ".tmp", popup_pid)
        done, st, quit_at = 0, 0, _time.time() + 60
        while not done and _time.time() < quit_at:
            done, st = os.waitpid(inner, os.WNOHANG)
            _time.sleep(0.02)
        with open(popup_rc + ".tmp", "w") as f:
            f.write(str(os.waitstatus_to_exitcode(st) if done else -9))
        os.rename(popup_rc + ".tmp", popup_rc)
        _time.sleep(30)  # still leading the session; finish() ends this group
        os._exit(0)
    _f57.ioctl(fd, _tm57b.TIOCSWINSZ, _st57.pack("HHHH", 30, 140, 0, 0))
    read_until(fd, lambda _b: os.path.exists(ready) and os.path.exists(popup_pid), 15)
    stuck = bool(os.path.exists(ready) and not _tm57b.tcgetattr(fd)[3] & _tm57b.ECHO)
    t0 = _time.time()
    os.kill(int(open(popup_pid).read()), _signal.SIGTERM)
    shown = read_until(fd, lambda _b: os.path.exists(popup_rc), 3 * sb.FZF_END_WAIT + 2 * sb.PS_TIMEOUT + 5)
    took = _time.time() - t0
    shown += read_until(fd, lambda _b: False, 0.3)
    lflag = _tm57b.tcgetattr(fd)[3]
    rc = int(open(popup_rc).read()) if os.path.exists(popup_rc) else None
    check("popup-puts-the-terminal-back-when-fzf-must-be-killed", stuck and rc == 128 + 15
          and b"\x1b[?1049l" in shown and b"\x1b[?1000l" in shown and bool(lflag & _tm57b.ECHO)
          and bool(lflag & _tm57b.ICANON), (stuck, rc, round(took, 1), shown[-40:], lflag))
    # The run directory says the popup is closing before fzf gets its first SIGTERM, with an
    # empty file.
    check("popup-marks-closing-before-ending-fzf", os.path.exists(seen) and open(seen).read().split()[:1] == ["True"],
          open(seen).read() if os.path.exists(seen) else None)
    check("closing-is-an-empty-file", os.path.exists(seen) and open(seen).read().split()[:2] == ["True", "0"],
          open(seen).read() if os.path.exists(seen) else None)
    finish(pid, fd, 0)

# 58. A close never waits for a read that can hang, and a signal during a close never leaves
# the run directory behind. A saved machine whose `api snapshot` over ssh hangs: Esc leaves at
# once, and Enter on a local row focuses it at once (both used to wait 2 s for that read). Esc
# followed by SIGHUP while the close runs, with the popup leading its terminal's session and
# not: the run directory goes. A close kept busy on purpose (a stand-in fzf whose socket
# accepts and never answers, so the last rows write waits on it): a SIGHUP in the middle waits
# for the run directory to go, then ends the popup with 129. watch() returns while a remote
# read is still under way, and once close_state() ran nothing more is written into the state
# directory (--demo removes it next).
block("58. a close waits for no read")
CLOSE_FAST = 1.0  # s: a close used to take at least 2 s here (the wait for the read); now ~0.2 s


def popup_in_pty(env, leader=True, args=()):
    """Start the popup (with `args`) in a terminal with `env` added. leader=False: a parent
    leads the terminal's session and outlives the popup. Returns (pid of the pty child, fd, d)
    where d holds popup.pid and popup.rc (leader=False) once known."""
    d = tempfile.mkdtemp(prefix="pty58-", dir=_tmp_root)
    popup_pid, popup_rc = os.path.join(d, "popup.pid"), os.path.join(d, "popup.rc")
    pid, fd = _pty.fork()
    if pid == 0:
        os.environ.update(env)
        if leader:
            os.execv(sys.executable, [sys.executable, "-B", str(TOOL)] + list(args))
        inner = os.fork()
        if inner == 0:
            os.execv(sys.executable, [sys.executable, "-B", str(TOOL)] + list(args))
        with open(popup_pid + ".tmp", "w") as f:
            f.write(str(inner))
        os.rename(popup_pid + ".tmp", popup_pid)
        done, st, quit_at = 0, 0, _time.time() + 60
        while not done and _time.time() < quit_at:
            done, st = os.waitpid(inner, os.WNOHANG)
            _time.sleep(0.01)
        with open(popup_rc + ".tmp", "w") as f:
            f.write(str(os.waitstatus_to_exitcode(st) if done else -9))
        os.rename(popup_rc + ".tmp", popup_rc)
        _time.sleep(30)  # still leading the session; finish() ends this group
        os._exit(0)
    import fcntl as _f58
    import struct as _st58
    import termios as _tm58
    _f58.ioctl(fd, _tm58.TIOCSWINSZ, _st58.pack("HHHH", 30, 140, 0, 0))
    if leader:
        with open(popup_pid, "w") as f:
            f.write(str(pid))
    return pid, fd, d


def popup_exit(pid, fd, d, leader, seconds):
    """Wait up to `seconds` for the popup's exit, reading its terminal: (rc, time) or (None, None)."""
    end = _time.time() + seconds
    while _time.time() < end:
        read_until(fd, lambda _b: False, 0.01)
        if leader:
            done, st = os.waitpid(pid, os.WNOHANG)
            if done:
                return os.waitstatus_to_exitcode(st), _time.time()
        elif os.path.exists(os.path.join(d, "popup.rc")):
            return int(open(os.path.join(d, "popup.rc")).read()), _time.time()
        _time.sleep(0.01)
    return None, None


def close_with_hung_remote(action, leader=True):
    """The popup with one saved machine whose snapshot read hangs (it is under way when the
    key comes). action: "esc", "enter" (on the local row), or "esc+hup" (SIGHUP 0.5 s after
    Esc). Returns (rc, seconds from the key to the exit, seconds from the key to the local
    focus or None, what is left in the run root, the hung read still alive 3 s later)."""
    with tempfile.TemporaryDirectory(dir="/tmp") as d:
        root = private_tmp(d, "runs")
        hung, focused = os.path.join(d, "hung"), os.path.join(d, "focused")
        with open(os.path.join(d, "machines.json"), "w") as f:
            json.dump([{"id": "m1", "label": "box1", "enabled": True, "target": "box1-host"}], f)
        with open(os.path.join(d, "local.json"), "w") as f:
            json.dump({"result": {"snapshot": snap([pane("w1:p1")], [agent("w1:p1", "idle", 1, title="here-row")])}}, f)
        fake_ssh = executable(os.path.join(d, "ssh"), '#!/bin/sh\ncase "$*" in\n'
                              '  *"api snapshot"*) echo $$ >> "%(d)s/hung"; exec sleep 120 ;;\n'
                              '  *) exit 1 ;;\nesac\n' % {"d": d})
        fh = executable(os.path.join(d, "herdr"), '#!/bin/sh\ncase "$*" in\n'
                        '  "machine list --json") cat "%(d)s/machines.json" ;;\n'
                        '  "api snapshot") cat "%(d)s/local.json" ;;\n'
                        '  *focus*) touch "%(d)s/focused" ;;\n'
                        '  *) exit 1 ;;\nesac\n' % {"d": d})
        env = dict(TERM="xterm-256color", HERDR_BIN_PATH=str(fh), SWITCHBOARD_SSH=str(fake_ssh),
                   SWITCHBOARD_REMOTE_TIMEOUT="60", SWITCHBOARD_RUN_ROOT=root,
                   HERDR_PLUGIN_STATE_DIR=os.path.join(d, "state"))
        pid, fd, pd = popup_in_pty(env, leader)
        read_until(fd, lambda b: b"here-row" in sb.ANSI.sub("", b.decode("utf-8", "replace")).encode(), 15)
        read_until(fd, lambda _b: os.path.exists(hung) and os.path.exists(os.path.join(pd, "popup.pid")), 10)
        target = int(open(os.path.join(pd, "popup.pid")).read())
        t0 = _time.time()
        os.write(fd, b"\r" if action == "enter" else b"\x1b")
        focus_at = None
        if action == "esc+hup":
            read_until(fd, lambda _b: False, 0.5)
            try:
                os.kill(target, _signal.SIGHUP)
            except OSError:
                pass  # already gone: the close was quicker than that
        rc, t_exit = popup_exit(pid, fd, pd, leader, 20)
        end = _time.time() + 5
        while action == "enter" and focus_at is None and _time.time() < end:
            if os.path.exists(focused):
                focus_at = _time.time() - t0
            _time.sleep(0.01)
        left = sorted(os.listdir(root))
        reads = [int(x) for x in open(hung).read().split()] if os.path.exists(hung) else []
        alive, end = list(reads), _time.time() + 3
        while alive and _time.time() < end:
            _time.sleep(0.05)
            alive = [p for p in alive if _alive(p)]
        for p in alive:
            try:
                os.kill(p, _signal.SIGKILL)
            except OSError:
                pass
        finish(pid, fd, 0)
        shutil.rmtree(pd, ignore_errors=True)
        return rc, (t_exit - t0) if t_exit else None, focus_at, left, bool(alive)


if fzf_real and not sb.dependency_problems(python=(3, 12, 0), fzf=fzf_real):
    rc, took, _, left, alive = close_with_hung_remote("esc")
    check("esc-does-not-wait-for-a-hung-read", rc == 0 and took is not None and took < CLOSE_FAST and not left
          and not alive, (rc, took, left, alive))
    rc, took, focus_at, left, alive = close_with_hung_remote("enter")
    check("enter-focuses-without-waiting-for-a-hung-read", rc == 0 and focus_at is not None and focus_at < CLOSE_FAST
          and not left, (rc, focus_at, left))
    # The review's case: Esc, then SIGHUP 0.5 s later. At cd73858 the close still waited for the
    # hung read, the SIGHUP landed in that wait and the run directory was left. Now the close
    # is over before it (about 0.1 s). A signal during a close: the busy close below.
    for leader in (True, False):
        rc, took, _, left, alive = close_with_hung_remote("esc+hup", leader)
        check("esc-then-sighup-half-a-second-later-leaves-no-run-dir-%s" % ("leading" if leader else "not-leading"),
              rc in (0, 128 + 1) and not left and not alive, (rc, took, left, alive))


def busy_close(leader):
    """A close kept busy on purpose: a stand-in fzf whose --listen socket accepts and never
    answers. The local snapshot changes once, so a rows write starts and waits on that socket
    (2 s for the position, 2 s for the reload) while holding the rows lock. The stand-in then
    exits like Esc, the close waits for that lock, and SIGHUP arrives 0.3 s into it. Returns
    (rc, seconds from the stand-in's exit to the popup's, what is left in the run root)."""
    with tempfile.TemporaryDirectory(dir="/tmp") as d:
        root = private_tmp(d, "runs")
        asked, gone, held = (os.path.join(d, n) for n in ("asked", "gone", "listener.pid"))
        stand_in = executable(os.path.join(d, "fzf"), "#!%s\nimport os, socket, sys, time\n"
                              "if '--version' in sys.argv:\n    print('0.74.2')\n    sys.exit(0)\n"
                              "sock = next(a.split('=', 1)[1] for a in sys.argv if a.startswith('--listen='))\n"
                              "srv = socket.socket(socket.AF_UNIX)\nsrv.bind(sock)\nsrv.listen(8)\n"
                              "if os.fork() == 0:\n"
                              "    null = os.open(os.devnull, os.O_RDWR)\n"
                              "    for fd in (0, 1, 2):\n        os.dup2(null, fd)\n"
                              "    open(%r, 'w').write(str(os.getpid()))\n"
                              "    kept = []\n"
                              "    while True:\n"
                              "        c, _ = srv.accept()\n        kept.append(c)\n"
                              "        open(%r, 'a').write('x')\n"
                              "end = time.time() + 15\n"
                              "while not os.path.exists(%r) and time.time() < end:\n    time.sleep(0.02)\n"
                              "open(%r, 'w').close()\nsys.exit(130)\n"
                              % (sys.executable, held, asked, asked, gone))
        snaps = [os.path.join(d, n) for n in ("one.json", "two.json")]
        for i, path in enumerate(snaps):
            with open(path, "w") as f:
                json.dump({"result": {"snapshot": snap([pane("w1:p1")], [agent("w1:p1", "idle", 1 + i,
                                                                                title="row-%d" % i)])}}, f)
        fh = executable(os.path.join(d, "herdr"), '#!/bin/sh\ncase "$*" in\n'
                        '  "machine list --json") echo "[]" ;;\n'
                        '  "api snapshot") if [ -e "%(d)s/once" ]; then cat "%(d)s/two.json"; '
                        'else touch "%(d)s/once"; cat "%(d)s/one.json"; fi ;;\n'
                        '  *) exit 1 ;;\nesac\n' % {"d": d})
        env = dict(TERM="xterm-256color", HERDR_BIN_PATH=str(fh), SWITCHBOARD_FZF=str(stand_in),
                   SWITCHBOARD_LOCAL_EVERY="0.2", SWITCHBOARD_RUN_ROOT=root, HERDR_PLUGIN_STATE_DIR=os.path.join(d, "state"))
        pid, fd, pd = popup_in_pty(env, leader)
        read_until(fd, lambda _b: os.path.exists(gone) and os.path.exists(os.path.join(pd, "popup.pid")), 15)
        target = int(open(os.path.join(pd, "popup.pid")).read())
        t0 = _time.time()
        read_until(fd, lambda _b: False, 0.3)
        try:
            os.kill(target, _signal.SIGHUP)
        except OSError:
            pass
        rc, t_exit = popup_exit(pid, fd, pd, leader, 20)
        left = sorted(os.listdir(root))
        try:
            os.kill(int(open(held).read()), _signal.SIGKILL)
        except (OSError, ValueError):
            pass
        finish(pid, fd, 0)
        shutil.rmtree(pd, ignore_errors=True)
        return rc, (t_exit - t0) if t_exit else None, left


for leader in (True, False):
    rc, took, left = busy_close(leader)
    check("signal-during-a-busy-close-still-removes-the-run-dir-%s" % ("leading" if leader else "not-leading"),
          rc == 128 + 1 and not left and took is not None and took < sb.WRITE_WAIT + 2, (rc, took, left))

# watch() does not wait for a remote read under way, and once close_state() ran, that read
# ending writes nothing into the state directory: no snapshot cache, no recency file.
with tempfile.TemporaryDirectory(dir="/tmp") as d:
    state58 = private_tmp(d, "state")
    rows58 = private_tmp(d, "rows")
    release58, started58 = _threading.Event(), _threading.Event()

    def held_fetch(m="", t=None, i=None):
        if m:
            started58.set()
            release58.wait(10)
            return snap([pane("w1:p2")], [agent("w1:p2", "idle", 3)])
        return snap([pane("w1:p1")], [agent("w1:p1", "idle", 1)])
    saved_state = sb.STATE_DIR
    sb.STATE_DIR = state58
    try:
        lv = sb.Live([{"id": "m1", "label": "box1"}], sb.entries_from(held_fetch(), "", sb.local_label(), 0),
                     fetch=held_fetch)
        stop = _threading.Event()
        t = _threading.Thread(target=sb.watch, args=(lv, short_sock("w58"), os.path.join(rows58, "rows"), stop),
                              daemon=True)
        t.start()
        started58.wait(5)
        t0 = _time.time()
        stop.set()
        t.join(5)
        returned = _time.time() - t0
        def contents58():
            return {n: open(os.path.join(state58, n), "rb").read() if os.path.isfile(os.path.join(state58, n)) else None
                    for n in os.listdir(state58)}
        before = contents58()
        sb.close_state()
        release58.set()  # the read ends now, after the close
        _time.sleep(0.5)
        after = contents58()
        check("watch-returns-while-a-remote-read-is-under-way", started58.is_set() and not t.is_alive() and returned < 0.5,
              returned)
        check("no-state-write-after-close-state", "snapshots" not in after and after == before,
              (sorted(before), sorted(after)))
    finally:
        release58.set()
        sb._STATE_CLOSED.discard(state58)
        sb.STATE_DIR = saved_state
check("demo-closes-its-state-before-removing-it", "    close_state()\n    if _DEMO_STATE:\n"
      "        remove_run_dir(STATE_DIR, _DEMO_STATE[0])" in SOURCE
      and "            hold_signals()\n            remove_demo_state()\n" in SOURCE)

# 59. No ps line the program matches is cut: ps cuts at $COLUMNS (fzf sets it for its
# commands, and child_env() passes it on). With COLUMNS=20, a herdr remote-client-bridge and a
# herdr window on a terminal below a ghostty process, all started from a long path, are still
# found. A `ps` wrapper first on PATH keeps only these (this machine may run a real herdr, or
# another run of this suite); a fake address stands for the ssh connection. And every `ps`
# the program runs asks for whole lines.
block("59. ps lines are never cut")
with tempfile.TemporaryDirectory(dir="/tmp") as d:
    mark = os.path.basename(d)  # unique to this run: other suites may run at the same time
    long_dir = os.path.join(d, "colmark59", "a-directory-name-long-enough-to-be-cut")
    os.makedirs(long_dir)
    os.symlink("/bin/sh", os.path.join(long_dir, "herdr"))
    os.symlink("/bin/sh", os.path.join(long_dir, "ghostty"))
    real_ps = shutil.which("ps")
    wrap = os.path.join(d, "wrap")
    os.mkdir(wrap)
    executable(os.path.join(wrap, "ps"), '#!/bin/sh\n"%s" "$@" | grep -F -e "%s"\n' % (real_ps, mark))
    bridge = subprocess.Popen([os.path.join(long_dir, "herdr"), "-c", "sleep 30; :", "remote-client-bridge"],
                              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              start_new_session=True, env=dict(os.environ, SSH_CONNECTION="box9 1 box9 22"))
    tui, tui_fd = _pty.fork()
    if tui == 0:
        # The window is `herdr` with no arguments (a shell reading the terminal, so it waits),
        # a child of "ghostty": the trailing ":" keeps that shell from exec'ing it.
        os.execv(os.path.join(long_dir, "ghostty"), [os.path.join(long_dir, "ghostty"), "-c",
                                                     '"%s"; :' % os.path.join(long_dir, "herdr")])
    try:
        _time.sleep(0.5)
        code59 = ("import importlib.machinery, importlib.util, json, sys\n"
                  "loader = importlib.machinery.SourceFileLoader('switchboard', sys.argv[1])\n"
                  "spec = importlib.util.spec_from_loader('switchboard', loader)\n"
                  "sb = importlib.util.module_from_spec(spec)\nloader.exec_module(sb)\n"
                  "print(json.dumps([sb.client_bridges(), sb.ghostty_tty() is not None]))\n")
        out = subprocess.run([sys.executable, "-c", code59, str(TOOL)], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, universal_newlines=True, timeout=30,
                             env=dict(os.environ, COLUMNS="20", PATH=wrap + os.pathsep + os.environ["PATH"])).stdout
        try:
            bridges59, tty59 = json.loads(out)
        except ValueError:
            bridges59, tty59 = None, None
        check("bridges-found-with-a-narrow-columns", bridges59 == [[bridge.pid, "box9"]], bridges59)
        check("window-tty-found-with-a-narrow-columns", tty59 is True, tty59)
    finally:
        for p in (bridge.pid, tui):
            try:
                os.killpg(p, _signal.SIGKILL)
            except OSError:
                pass
        bridge.wait(5)
        finish(tui, tui_fd, 0)
_ps_calls = [n for n in ast.walk(ast.parse(SOURCE)) if isinstance(n, ast.List) and n.elts
             and isinstance(n.elts[0], ast.Constant) and n.elts[0].value == "ps"]
check("every-ps-asks-for-whole-lines", len(_ps_calls) >= 4 and all(
    any(isinstance(e, ast.Constant) and isinstance(e.value, str) and e.value.startswith("-ww") for e in n.elts)
    for n in _ps_calls), [ast.get_source_segment(SOURCE, n) for n in _ps_calls])

# 60. The run directory goes, also when another process writes into it during the removal,
# and nothing more is written into it once the close starts. The focus worker (Enter on
# another machine's row, then Esc) writes its result file through a descriptor of the run
# directory whenever its focus is done: forced here to land just before the removal's last
# rmdir, which then finds the directory not empty. And a close by signal: no rows write, and
# no reload asked of fzf, after the signal (a stand-in fzf that ignores SIGTERM keeps the
# close in end_fzf for 4 s and logs every request it gets), leading the session and not.
block("60. the run directory goes, whoever writes in it")
with tempfile.TemporaryDirectory(dir="/tmp") as d:
    run60 = private_tmp(d, "run")
    open(os.path.join(run60, "rows"), "w").close()
    made60 = os.lstat(run60)
    worker_fd = sb.open_private_dir(run60)  # what the focus worker holds
    popup_fd = sb.open_private_dir(run60)  # what the popup holds
    real_rmdir, wrote60 = os.rmdir, []

    def rmdir_after_a_worker_write(path, *a, **kw):
        try:
            st = os.stat(path, dir_fd=kw.get("dir_fd"), follow_symlinks=False)
        except OSError:
            st = None
        if st is not None and (st.st_dev, st.st_ino) == (made60.st_dev, made60.st_ino) and not wrote60:
            wrote60.append(sb.write_new(worker_fd, "focus-1-1", "ready"))
        return real_rmdir(path, *a, **kw)
    remove60 = getattr(sb, "remove_run_dir", None) or (lambda path, fd: sb.shutil.rmtree(path, ignore_errors=True))
    os.rmdir = rmdir_after_a_worker_write
    try:
        remove60(run60, popup_fd)
    finally:
        os.rmdir = real_rmdir
        os.close(worker_fd)
        os.close(popup_fd)
    check("run-dir-goes-despite-a-worker-writing-in-it", wrote60 == [True] and not os.path.lexists(run60),
          (wrote60, sorted(os.listdir(run60)) if os.path.isdir(run60) else None))
    # Once it is gone, a directory someone else makes under the same name is not touched.
    run60b = private_tmp(d, "run-b")
    fd60b = sb.open_private_dir(run60b)

    stranger = []

    def rmdir_then_a_stranger(path, *a, **kw):
        result = real_rmdir(path, *a, **kw)
        if not stranger and not os.path.lexists(run60b):
            stranger.append(True)
            os.mkdir(run60b, 0o700)
            open(os.path.join(run60b, "theirs"), "w").close()
        return result
    os.rmdir = rmdir_then_a_stranger
    try:
        if hasattr(sb, "remove_run_dir"):
            sb.remove_run_dir(run60b, fd60b)
    finally:
        os.rmdir = real_rmdir
        os.close(fd60b)
    check("removal-leaves-a-new-directory-of-the-same-name-alone", stranger == [True]
          and os.path.exists(os.path.join(run60b, "theirs")), stranger)
check("popup-removes-its-run-dir-with-remove-run-dir", "            remove_run_dir(tmp, run_fd)" in SOURCE
      and "shutil.rmtree(tmp" not in SOURCE)


def requests_after_a_signal(leader):
    """A popup over a stand-in fzf that answers its socket, logs each request's time, and
    ignores SIGTERM; the local snapshot changes at every read, so every local pass (0.2 s)
    writes the rows and asks fzf to reload. SIGTERM once requests flow. Returns (requests
    received more than 0.5 s after the signal, rc, what is left in the run root)."""
    with tempfile.TemporaryDirectory(dir="/tmp") as d:
        root = private_tmp(d, "runs")
        log, ready, count = (os.path.join(d, n) for n in ("requests", "ready", "count"))
        stand_in = executable(os.path.join(d, "fzf"), "#!%s\nimport os, signal, socket, sys, time\n"
                              "if '--version' in sys.argv:\n    print('0.74.2')\n    sys.exit(0)\n"
                              "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
                              "sock = next(a.split('=', 1)[1] for a in sys.argv if a.startswith('--listen='))\n"
                              "srv = socket.socket(socket.AF_UNIX)\nsrv.bind(sock)\nsrv.listen(8)\n"
                              "open(%r, 'w').close()\n"
                              "while True:\n"
                              "    c, _ = srv.accept()\n"
                              "    data = c.recv(65536)\n"
                              "    open(%r, 'a').write('%%f %%s\\n' %% (time.time(), data.split(b' ', 1)[0].decode()))\n"
                              "    body = b'{\"position\": 0}' if data.startswith(b'GET') else b''\n"
                              "    c.sendall(b'HTTP/1.1 200 OK\\r\\nContent-Length: %%d\\r\\n\\r\\n' %% len(body) + body)\n"
                              "    c.close()\n" % (sys.executable, ready, log))
        fh = executable(os.path.join(d, "herdr"), "#!%s\nimport json, os, sys\n"
                        "args = ' '.join(sys.argv[1:])\n"
                        "if args == 'machine list --json':\n    print('[]')\n"
                        "elif args == 'api snapshot':\n"
                        "    n = int(open(%r).read()) + 1 if os.path.exists(%r) else 1\n"
                        "    open(%r, 'w').write(str(n))\n"
                        "    print(json.dumps({'result': {'snapshot': %r}}).replace('TITLE', 'row-%%d' %% n))\n"
                        "else:\n    sys.exit(1)\n"
                        % (sys.executable, count, count, count,
                           snap([pane("w1:p1")], [agent("w1:p1", "idle", 1, title="TITLE")])))
        env = dict(TERM="xterm-256color", HERDR_BIN_PATH=str(fh), SWITCHBOARD_FZF=str(stand_in),
                   SWITCHBOARD_LOCAL_EVERY="0.2", SWITCHBOARD_RUN_ROOT=root, HERDR_PLUGIN_STATE_DIR=os.path.join(d, "state"))
        pid, fd, pd = popup_in_pty(env, leader)
        read_until(fd, lambda _b: os.path.exists(log) and len(open(log).read().split("\n")) > 4
                   and os.path.exists(os.path.join(pd, "popup.pid")), 15)
        target = int(open(os.path.join(pd, "popup.pid")).read())
        t_sig = _time.time()
        os.kill(target, _signal.SIGTERM)
        rc, _ = popup_exit(pid, fd, pd, leader, 20)
        late = [l for l in open(log).read().splitlines() if float(l.split()[0]) > t_sig + 0.5]
        left = sorted(os.listdir(root))
        finish(pid, fd, 0)
        shutil.rmtree(pd, ignore_errors=True)
        return late, rc, left


for leader in (True, False):
    late, rc, left = requests_after_a_signal(leader)
    check("no-reload-asked-of-fzf-once-the-close-starts-%s" % ("leading" if leader else "not-leading"),
          not late and rc == 128 + 15 and not left, (len(late), late[:3], rc, left))

# In --demo, main removes the temporary state directory holding signals, and again at exit:
# block 61 checks both ways out. (The popup itself releases them once the run directory is gone.)
check("demo-state-dir-removed-in-main-and-at-exit", "        atexit.register(remove_demo_state_at_exit)" in SOURCE
      and "            hold_signals()\n            remove_demo_state()\n            release_signals()" in SOURCE)

# 61. --demo: a signal at the message that waits for Enter ends the popup at once, and the
# temporary state directory goes on a normal exit and on a SIGHUP or SIGTERM. fzf refuses to
# start when its socket path is too long (a run root of 100 characters more), the popup says
# why and waits for Enter: a SIGTERM or SIGHUP there exits with its status within a second,
# leading the session or not, and leaves nothing in the run root or in TMPDIR (where --demo
# keeps its state). It used to be held until Enter. And a signal handled in main's finally
# block before it holds signals (simulated: hold_signals raises the exit there, once) still
# leaves no state directory: the removal runs again at exit. So does a signal at the directory's
# creation, and one during the removal at exit.
block("61. --demo: a signal at the prompt, and the state directory on the way out")
PROMPT_FAST = 1.0  # s: it used to wait for Enter; now about 0.02 s


def signal_at_the_prompt(sig, leader):
    """(rc, seconds from the signal to the exit, what is left in the run root, in TMPDIR)."""
    with tempfile.TemporaryDirectory(dir="/tmp") as d:
        root = os.path.join(d, "r" * 100)
        os.makedirs(root, 0o700)
        tmpdir = private_tmp(d, "tmp")
        env = dict(TERM="xterm-256color", SWITCHBOARD_RUN_ROOT=root, TMPDIR=tmpdir, HERDR_BIN_PATH="/bin/false")
        pid, fd, pd = popup_in_pty(env, leader, args=("--demo",))
        read_until(fd, lambda b: b"Enter" in b and os.path.exists(os.path.join(pd, "popup.pid")), 15)
        prompt = bool(os.listdir(tmpdir))  # the state directory exists while the prompt waits
        target = int(open(os.path.join(pd, "popup.pid")).read())
        t0 = _time.time()
        try:
            os.kill(target, sig)
        except ProcessLookupError:
            pass  # it had already left: the checks below say so
        rc, t_exit = popup_exit(pid, fd, pd, leader, 5)
        took = (t_exit - t0) if t_exit else None
        left = (sorted(os.listdir(root)), sorted(os.listdir(tmpdir)))
        if rc is None:
            os.write(fd, b"\r")  # the old behaviour: only Enter ends it
            popup_exit(pid, fd, pd, leader, 5)
        finish(pid, fd, 0)
        shutil.rmtree(pd, ignore_errors=True)
        return prompt, rc, took, left


if fzf_real and not sb.dependency_problems(python=(3, 12, 0), fzf=fzf_real):
    for sig, leader in ((_signal.SIGTERM, True), (_signal.SIGTERM, False), (_signal.SIGHUP, False)):
        prompt, rc, took, left = signal_at_the_prompt(sig, leader)
        check("demo-prompt-%s-%s-ends-at-once" % ("sigterm" if sig == _signal.SIGTERM else "sighup",
                                                  "leading" if leader else "not-leading"),
              prompt and rc == 128 + sig and took is not None and took < PROMPT_FAST and left == ([], []),
              (prompt, rc, took, left))

# The wait for Enter misses no signal. input() could: a SIGTERM that lands after its prompt is
# written and before its read begins only marks the Python handler as due, and the read then
# waits for Enter (a slow CI runner hit it at the check above). Simulated: the main thread blocks
# SIGTERM, so the kernel hands it to another thread and the main thread's read is not
# interrupted, which is what that window leaves too. The wait ends with 143 (in about 0.4 s,
# 0.3 s of it the delay before the signal); input() still waits there after 5 s. And no
# message calls input() any more.
master61e, slave61e = os.openpty()
try:
    code61e = ("import importlib.machinery, importlib.util, os, signal, sys, threading, time\n"
               "loader = importlib.machinery.SourceFileLoader('switchboard', sys.argv[1])\n"
               "spec = importlib.util.spec_from_loader('switchboard', loader)\n"
               "sb = importlib.util.module_from_spec(spec)\nloader.exec_module(sb)\n"
               "for s in (signal.SIGHUP, signal.SIGTERM):\n"
               "    signal.signal(s, sb._exit_on_signal)\n"
               "def later():\n"
               "    time.sleep(0.3)\n"
               "    os.kill(os.getpid(), signal.SIGTERM)\n"
               "threading.Thread(target=later, daemon=True).start()\n"
               "signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM})\n"
               "sys.exit(sb.explain_and_wait(['a message']))\n")
    try:
        rc61e = subprocess.run([sys.executable, "-c", code61e, str(TOOL)], stdin=slave61e, stdout=slave61e,
                               stderr=slave61e, timeout=5).returncode
    except subprocess.TimeoutExpired:
        rc61e = None  # still waiting for Enter
finally:
    os.close(slave61e)
    os.close(master61e)
check("wait-for-enter-misses-no-signal", rc61e == 128 + 15, rc61e)
# ...and it acts within one step of its select, WAIT_POLL (0.05 s). The check above only asks for
# 143 within 5 s, which a step of 3 s also passes. The module's select is watched, and two things
# are held. The step itself: every timeout the wait passes to select must be WAIT_STEP, with
# nothing timed, so a longer step fails, one that grows after the first selects too, and so does
# a step of 0, which would spin. And that a signal there acts within that step: the same blind
# spot is set up, and the signal is sent just as the third select of the wait begins, the worst
# case, where the handler runs only when that select ends. The program notes the moment of the
# signal and the test the moment of the exit from its wait, both with time.time(): the wall
# clock reads the same in every process, and time.monotonic() does not, since CPython 3.9 on
# macOS starts it from zero in each process. That takes about 0.06 s on Python 3.15 and 0.07 to
# 0.11 s on 3.9 to 3.14, where the test's wait() polls with sleeps of up to 50 ms; up to 0.12 s
# on one CPU, also shared with three busy loops. The timed check alone would pass a step of
# 0.35 s; the check of the timeouts is what holds it at 0.05 s.
WAIT_STEP = 0.05  # s: the step wait_for_enter must use
WAIT_FAST = 0.4  # s: that step plus the exit, with room for a loaded runner
code61g = ("import importlib.machinery, importlib.util, os, signal, sys, threading, time, types\n"
           "loader = importlib.machinery.SourceFileLoader('switchboard', sys.argv[1])\n"
           "spec = importlib.util.spec_from_loader('switchboard', loader)\n"
           "sb = importlib.util.module_from_spec(spec)\nloader.exec_module(sb)\n"
           "for s in (signal.SIGHUP, signal.SIGTERM):\n"
           "    signal.signal(s, sb._exit_on_signal)\n"
           "real_select, steps, begun = sb.select.select, [], threading.Event()\n"
           "def watched(r, w, x, timeout):\n"
           "    steps.append(timeout)\n"
           "    if len(steps) >= 3:  # the loop has gone round: a step that changes shows by now\n"
           "        begun.set()\n"
           "    return real_select(r, w, x, timeout)\n"
           "sb.select = types.SimpleNamespace(select=watched)\n"
           "def later():\n"
           "    begun.wait(5)  # it runs on once the select has released the GIL: the signal lands in it\n"
           "    with open(sys.argv[2], 'w') as f:\n"
           "        f.write('%r %d %r %r' % (time.time(), len(steps), min(steps or [0.0]), max(steps or [0.0])))\n"
           "    os.kill(os.getpid(), signal.SIGTERM)\n"
           "threading.Thread(target=later, daemon=True).start()\n"
           "signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM})\n"
           "sys.exit(sb.explain_and_wait(['a message']))\n")
with tempfile.TemporaryDirectory(dir="/tmp") as d61g:
    sent61g = os.path.join(d61g, "sent")
    master61g, slave61g = os.openpty()
    try:
        proc61g = subprocess.Popen([sys.executable, "-c", code61g, str(TOOL), sent61g], stdin=slave61g,
                                   stdout=slave61g, stderr=slave61g)
        try:
            rc61g = proc61g.wait(timeout=10)
            exit61g = _time.time()
        except subprocess.TimeoutExpired:
            proc61g.kill()
            proc61g.wait(timeout=5)
            rc61g = exit61g = None  # still waiting for Enter
    finally:
        os.close(slave61g)
        os.close(master61g)
    try:
        with open(sent61g) as f61g:
            sent_at61g, selects61g, low61g, high61g = f61g.read().split()
        took61g = round(exit61g - float(sent_at61g), 3) if exit61g is not None else None
        selects61g, low61g, high61g = int(selects61g), float(low61g), float(high61g)
    except (OSError, ValueError):
        took61g = selects61g = low61g = high61g = None  # the signal was never sent
check("wait-for-enter-polls-in-steps-of-0.05-s", selects61g is not None and selects61g >= 3
      and low61g == high61g == WAIT_STEP, (selects61g, low61g, high61g))
check("wait-for-enter-acts-within-its-step", rc61g == 128 + 15 and bool(selects61g) and took61g is not None
      and 0 <= took61g < WAIT_FAST, (rc61g, selects61g, took61g))
# Enter and the end of the input end that wait as they did under input(): explain_and_wait
# returns 1. Each is typed into the terminal before the program reads it.
code61f = ("import importlib.machinery, importlib.util, sys\n"
           "loader = importlib.machinery.SourceFileLoader('switchboard', sys.argv[1])\n"
           "spec = importlib.util.spec_from_loader('switchboard', loader)\n"
           "sb = importlib.util.module_from_spec(spec)\nloader.exec_module(sb)\n"
           "sys.exit(sb.explain_and_wait(['a message']))\n")
for name61f, typed61f in (("enter", b"\r"), ("end-of-input", b"\x04")):
    master61f, slave61f = os.openpty()
    try:
        os.write(master61f, typed61f)
        try:
            rc61f = subprocess.run([sys.executable, "-c", code61f, str(TOOL)], stdin=slave61f, stdout=slave61f,
                                   stderr=slave61f, timeout=5).returncode
        except subprocess.TimeoutExpired:
            rc61f = None
    finally:
        os.close(slave61f)
        os.close(master61f)
    check("wait-for-enter-ends-on-%s" % name61f, rc61f == 1, rc61f)
check("no-message-waits-in-input", "input(tr(" not in SOURCE and SOURCE.count("wait_for_enter(tr(") == 3)

with tempfile.TemporaryDirectory(dir="/tmp") as d:
    tmpdir = private_tmp(d, "tmp")
    code61 = ("import importlib.machinery, importlib.util, signal, sys\n"
              "loader = importlib.machinery.SourceFileLoader('switchboard', sys.argv[1])\n"
              "spec = importlib.util.spec_from_loader('switchboard', loader)\n"
              "sb = importlib.util.module_from_spec(spec)\nloader.exec_module(sb)\n"
              "real_hold, cut = sb.hold_signals, []\n"
              "def cut_short():\n"
              "    # main's finally block, the first time: the demo's directory exists by then\n"
              "    if not cut and sys._getframe(1).f_code.co_name == 'main' and 'switchboard-demo-' in sb.STATE_DIR:\n"
              "        cut.append(True)\n"
              "        for s in (signal.SIGHUP, signal.SIGTERM):\n"
              "            signal.signal(s, signal.SIG_IGN)\n"
              "        raise SystemExit(128 + signal.SIGTERM)\n"
              "    real_hold()\n"
              "sb.hold_signals = cut_short\n"
              "sys.exit(sb.main(['--demo', '--rows']))\n")
    r61 = subprocess.run([sys.executable, "-c", code61, str(TOOL)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, timeout=30, env=dict(os.environ, TMPDIR=tmpdir))
    check("demo-state-dir-goes-when-a-signal-cuts-main-short", r61.returncode == 128 + 15 and os.listdir(tmpdir) == [],
          (r61.returncode, os.listdir(tmpdir)))

# The state directory from its very creation: a SIGTERM handled right after the mkdir inside
# tempfile.mkdtemp (simulated: mkdtemp sends it to its own process before returning) waits
# until the removal at exit is registered, then exits 143, and nothing is left. (CI has no
# strace to inject it at the mkdir itself.) And the second removal, at exit, takes only the
# directory this process created: one made under the same name once main's removal is done
# (simulated in rmdir) is left alone, with what is in it.
with tempfile.TemporaryDirectory(dir="/tmp") as d:
    tmpdir = private_tmp(d, "tmp")
    code61b = ("import importlib.machinery, importlib.util, os, signal, sys, tempfile, time\n"
               "loader = importlib.machinery.SourceFileLoader('switchboard', sys.argv[1])\n"
               "spec = importlib.util.spec_from_loader('switchboard', loader)\n"
               "sb = importlib.util.module_from_spec(spec)\nloader.exec_module(sb)\n"
               "real = tempfile.mkdtemp\n"
               "def signalled(*a, **kw):\n"
               "    path = real(*a, **kw)\n"
               "    os.kill(os.getpid(), signal.SIGTERM)\n"
               "    time.sleep(0.2)\n"
               "    return path\n"
               "tempfile.mkdtemp = signalled\n"
               "sys.exit(sb.main(['--demo', '--rows']))\n")
    r61b = subprocess.run([sys.executable, "-c", code61b, str(TOOL)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, timeout=30, env=dict(os.environ, TMPDIR=tmpdir))
    check("demo-state-dir-goes-on-a-signal-at-its-creation", r61b.returncode == 128 + 15 and os.listdir(tmpdir) == [],
          (r61b.returncode, os.listdir(tmpdir)))
with tempfile.TemporaryDirectory(dir="/tmp") as d:
    tmpdir = private_tmp(d, "tmp")
    code61c = ("import importlib.machinery, importlib.util, os, sys\n"
               "loader = importlib.machinery.SourceFileLoader('switchboard', sys.argv[1])\n"
               "spec = importlib.util.spec_from_loader('switchboard', loader)\n"
               "sb = importlib.util.module_from_spec(spec)\nloader.exec_module(sb)\n"
               "real, made = os.rmdir, []\n"
               "def rmdir_then_a_stranger(path, *a, **kw):\n"
               "    result = real(path, *a, **kw)\n"
               "    if not made and sb.STATE_DIR and not os.path.lexists(sb.STATE_DIR):\n"
               "        made.append(True)\n"
               "        os.mkdir(sb.STATE_DIR, 0o700)\n"
               "        open(os.path.join(sb.STATE_DIR, 'theirs'), 'w').close()\n"
               "    return result\n"
               "os.rmdir = rmdir_then_a_stranger\n"
               "sys.exit(sb.main(['--demo', '--rows']))\n")
    r61c = subprocess.run([sys.executable, "-c", code61c, str(TOOL)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, timeout=30, env=dict(os.environ, TMPDIR=tmpdir))
    kept = [n for n in os.listdir(tmpdir) if os.path.exists(os.path.join(tmpdir, n, "theirs"))]
    check("demo-removal-at-exit-leaves-a-new-directory-of-the-same-name-alone", r61c.returncode == 0 and len(kept) == 1,
          (r61c.returncode, os.listdir(tmpdir)))

# A signal during the removal at exit (simulated: main's removal leaves the directory, and the
# first removal at exit sends a SIGTERM to its own process) cuts nothing short: the exit is
# under way with its status (0), the directory goes, and nothing is reported on stderr. Python
# only reports a SystemExit raised in an exit hook, so the hook ignores both signals.
with tempfile.TemporaryDirectory(dir="/tmp") as d:
    tmpdir = private_tmp(d, "tmp")
    code61d = ("import importlib.machinery, importlib.util, os, shutil, signal, sys, time\n"
               "loader = importlib.machinery.SourceFileLoader('switchboard', sys.argv[1])\n"
               "spec = importlib.util.spec_from_loader('switchboard', loader)\n"
               "sb = importlib.util.module_from_spec(spec)\nloader.exec_module(sb)\n"
               "real, exiting, sent = shutil.rmtree, [], []\n"
               "def rmtree_at_exit(path, *a, **kw):\n"
               "    if not exiting:\n"
               "        return\n"
               "    if not sent:\n"
               "        sent.append(True)\n"
               "        os.kill(os.getpid(), signal.SIGTERM)\n"
               "        time.sleep(0.2)\n"
               "    return real(path, *a, **kw)\n"
               "shutil.rmtree = rmtree_at_exit\n"
               "rc = sb.main(['--demo', '--rows'])\n"
               "exiting.append(True)\n"
               "sys.exit(rc)\n")
    r61d = subprocess.run([sys.executable, "-c", code61d, str(TOOL)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                          stderr=subprocess.PIPE, timeout=30, env=dict(os.environ, TMPDIR=tmpdir))
    err61d = r61d.stderr.decode("utf-8", "replace")
    check("demo-signal-during-the-removal-at-exit-cuts-nothing-short",
          r61d.returncode == 0 and os.listdir(tmpdir) == [] and "Traceback" not in err61d
          and "Exception ignored" not in err61d, (r61d.returncode, os.listdir(tmpdir), err61d[-300:]))

sb.ssh_mux()
check("ssh-sockets-under-the-test-root", sb._SSH_DIR and sb._SSH_DIR[0]
      and sb._SSH_DIR[0] == os.path.join(_run_root, "switchboard"), sb._SSH_DIR)

# The end of the suite gets a limit too: a thread or a child left behind could hold the exit.
block("end of the suite")
if FAILS:
    print("FAIL %d:\n  " % len(FAILS) + "\n  ".join(str(f) for f in FAILS))
    sys.exit(1)
print("ok")
