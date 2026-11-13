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
   the one touched last. The Goto query is the pane id only if no other row of any machine
   contains it; otherwise a temporary name. The AppleScript only carries [a-z0-9:._-].
   Order: rename, keys, restore the name, API focus.
12. Select (ctrl-o): long lines wrap at the width without losing text, a column lands on
   its character with wide characters, the text between two points is the same dragging
   forward or back, and on release exactly that is copied over OSC 52 (in a pty, with a
   real SGR 1006 drag).
13. The fast jump: the connection to the window's Mac opens with the popup (ssh with
   ControlMaster) and Enter sends one JSON line; on the other side --jump-server already has
   the tty and an osascript running. No line (Esc, or a row of this machine) exits without
   jumping. The query tries the title before renaming.
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
24. The jump is opt-in: off by default, Enter on a remote row then focuses it through the
   API and keeps the popup open with a footer; the client, Tailscale and the helper are
   optional, and anything missing falls back without an error.
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
import atexit as _atexit
_atexit.register(shutil.rmtree, _tmp_root, True)
for _k in list(os.environ):
    if _k.startswith("SWITCHBOARD_") or _k.startswith("HERDR_"):
        del os.environ[_k]
# HOME and the XDG directories too: even a regression that ignores the plugin directories
# must not write into the real home.
os.environ.update(NO_COLOR="1", PYTHONDONTWRITEBYTECODE="1",
                  HOME=os.path.join(_tmp_root, "home"),
                  XDG_CONFIG_HOME=os.path.join(_tmp_root, "xdg-config"),
                  XDG_STATE_HOME=os.path.join(_tmp_root, "xdg-state"),
                  HERDR_PLUGIN_CONFIG_DIR=os.path.join(_tmp_root, "config"),
                  HERDR_PLUGIN_STATE_DIR=os.path.join(_tmp_root, "state"))
os.makedirs(os.environ["HOME"])

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


# 1. Priority.
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
home = os.path.expanduser("~")
check("tilde-local", sb.tilde(home + "/src/x", remote=False) == "~/src/x")
check("tilde-remote-linux", sb.tilde("/home/someone/src/x", remote=True) == "~/src/x")
check("tilde-remote-mac", sb.tilde("/Users/someone", remote=True) == "~")
check("tilde-not-homeless", sb.tilde("/homeless/x", remote=True) == "/homeless/x")
check("tilde-root", sb.tilde("/root/x", remote=True) == "~/x")
check("tilde-not-rootfs", sb.tilde("/rootfs/x", remote=True) == "/rootfs/x")
check("tilde-local-not-a-prefix", sb.tilde(home + "x/y", remote=False) == home + "x/y")

# 5. Columns: status, machine, workspace, tab, pane and the dimmed tail.
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
e3 = sb.entries_from(snap([pane("a")], [agent("a", "idle", 1)]), "", "here", 0)[0]
check("machine-column-always", cols(e3)[1] == "here" and "here" in sb.render([e3], []))
check("claude-not-shown", "claude" not in cols(e3)[5], cols(e3))
cx = sb.entries_from(snap([pane("a")], [dict(agent("a", "idle", 1), agent="codex")]))[0]
check("other-kind-shown", "codex" in cols(cx)[5], cols(cx))

argv = sb.fzf_argv("fzf", "x", "/tmp/s.sock")
colors = dict(kv.split(":", 1) for kv in argv[argv.index("--color") + 1].split(","))
check("selected-row-has-background", colors.get("bg+") not in (None, "-1"), colors)

# 8. The preview without the agent's input box and status bar.
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
                      '  "--machine m2 api snapshot") sleep 5 ;;\n'
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

    def __init__(self, path, position=0):
        self.reqs, self.position = [], position
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
            c.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: %d\r\n\r\n" % len(body) + body)
            c.close()


with tempfile.TemporaryDirectory(dir="/tmp") as d:
    sock = os.path.join(d, "f.sock")
    fz = FakeFzf(sock, position=2)
    check("http-get-position", sb.fzf_position(sock) == 2)
    check("http-get-no-content-length", fz.reqs and b"Content-Length" not in fz.reqs[-1], fz.reqs[-1:])
    check("http-post", sb.fzf_request(sock, "POST", b"reload(x)") is not None
          and fz.reqs[-1].endswith(b"\r\n\r\nreload(x)") and b"Content-Length: 9" in fz.reqs[-1])
    check("http-no-fzf", sb.fzf_position(os.path.join(d, "missing.sock")) is None)

    # watch() end to end: a change sends a reload, no change sends nothing.
    sb.LOCAL_EVERY, sb.REMOTE_EVERY = 0.05, 0.05
    data.update(local=snap([pane("w1:p1")], [agent("w1:p1", "working", 1)]),
                m1=snap([pane("w1:p1")], [agent("w1:p1", "idle", 1)]))
    lv = sb.Live(machines, sb.entries_from(fake_fetch(), "", "here", 0), fetch=fake_fetch)
    lv.changed()
    rows_file, stop = os.path.join(d, "rows"), _threading.Event()
    _threading.Thread(target=sb.watch, args=(lv, sock, rows_file, stop), daemon=True).start()
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
    # With a slow local tick (5 s), a machine arriving still reloads at once.
    _time.sleep(0.2)
    sb.LOCAL_EVERY, sb.REMOTE_EVERY = 5.0, 5.0
    data["m1"] = snap([pane("w1:p9")], [agent("w1:p9", "blocked", 9)])
    lv2 = sb.Live(machines, sb.entries_from(fake_fetch(), "", "here", 0), fetch=fake_fetch, cache=False)
    lv2.changed()
    before = len([r for r in fz.reqs if b"reload-sync" in r])
    stop2 = _threading.Event()
    _threading.Thread(target=sb.watch, args=(lv2, sock, os.path.join(d, "rows2"), stop2), daemon=True).start()
    _time.sleep(0.6)
    check("watch-remote-reloads-now", len([r for r in fz.reqs if b"reload-sync" in r]) > before)
    stop2.set()
    sb.LOCAL_EVERY, sb.REMOTE_EVERY = 0.05, 0.05

# 10. Copy and terminals.
argv = sb.fzf_argv("fzf", "self", "/tmp/s.sock")
joined = " ".join(argv)
check("preview-half", "down,50%" in joined, joined)
check("ctrl-y-copies", "ctrl-y:transform-footer(self --copy {1})" in argv, argv)
check("ctrl-t-terminals", any(a.startswith("ctrl-t:transform-query:") for a in argv))
check("posix-shell", "--with-shell" in argv and argv[argv.index("--with-shell") + 1] == "sh -c")
for q, want in (("", "^› "), ("api", "^› "), ("^› ", ""), ("^› docs", "")):
    out = subprocess.run(["sh", "-c", sb.TOGGLE_TERMINALS], env=dict(os.environ, FZF_QUERY=q),
                         stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, universal_newlines=True).stdout
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
TUI = " 60526 ttys000  /opt/homebrew/bin/herdr\n 96578 ??  /opt/homebrew/bin/herdr server\n 7 ttys003 /opt/homebrew/bin/herdr agent list"
check("tty-of-the-window", sb.local_tui_tty(TUI) == "/dev/ttys000", sb.local_tui_tty(TUI))
check("tty-no-window", sb.local_tui_tty(" 96578 ??  /opt/homebrew/bin/herdr server") is None)


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
scr = sb.ghostty_keys_script("/dev/ttys000", "w3:p1d")
check("applescript-one-burst", 'tty is "/dev/ttys000"' in scr and scr.count("perform action") == 1
      and '"text:\\\\x02//w3:p1d\\\\r"' in scr and "delay" not in scr, scr)
for bad in (("/dev/ttys000", 'x" & do shell script "rm'), ("/dev/tty; rm", "w1:p1"), ("/dev/ttys000", "W1:P1")):
    try:
        sb.ghostty_keys_script(*bad)
        check("applescript-rejects %r" % (bad,), False)
    except ValueError:
        pass

calls = []
orig = (sb.run_out, sb.local_tui_tty, sb.subprocess.run, sb.time.sleep, sb.local_label)
sb.run_out = lambda argv, timeout=5: calls.append(("herdr", argv[1:])) or ""
sb.local_tui_tty = lambda ps_text=None: "/dev/ttys000"
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
    sb.run_out, sb.local_tui_tty, sb.subprocess.run, sb.time.sleep, sb.local_label = orig

args = sb.jump_argv({"machine": "m1", "kind": "a", "pane": "w1:p1", "tab": "w1:t1"}, "box1",
                    ents[:3] + [ent("m2", "w1:p1", pane_label="logs")])
check("jump-argv-renames-when-repeated", args[6] == "1" and args[5].startswith("sbj")
      and args[:5] == ["--jump", "box1", "a", "w1:p1", "w1:t1"], args)
check("jump-argv-name-of-that-machine", args[7] == "", args)
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
import select as _sel
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
    m = re.search(rb"\x1b\]52;c;([A-Za-z0-9+/=]+)\x07", out)
    copied = base64.b64decode(m.group(1)).decode() if m else None
    check("pty-copies-the-drag", copied == "world\nsecond", repr(copied))
    check("pty-exits-on-esc", done == pid)
    check("pty-restores-the-terminal", out.rstrip().endswith(b"\x1b[?1049l") or b"\x1b[?1006l" in out[-200:])

# 13. The fast jump.
ents2 = [ent("m1", "w1:p1", title="Plugin docs"), ent("m2", "w1:p1", title="something else"),
         ent("m1", "w2:p2", title="Fix (deploy)"), ent("m2", "w2:p2", title="x")]
check("goto-title-when-id-repeats", sb.goto_query({"machine": "m1", "pane": "w1:p1"}, ents2) == "plugin docs",
      sb.goto_query({"machine": "m1", "pane": "w1:p1"}, ents2))
check("goto-odd-title-no", sb.goto_query({"machine": "m1", "pane": "w2:p2"}, ents2) is None)
ents3 = ents2 + [ent("m3", "w9:p9", ws_label="plugin docs")]
check("goto-title-found-in-a-workspace-no", sb.goto_query({"machine": "m1", "pane": "w1:p1"}, ents3) is None)

with tempfile.TemporaryDirectory() as d:
    d = pathlib.Path(d)
    fake_ssh = executable(d / "ssh", '#!/bin/sh\necho "$@" > "%s/argv"\ncat > "%s/stdin"\n' % (d, d))
    old_ssh = sb.SSH
    sb.SSH = str(fake_ssh)
    link = sb.JumpLink(find=lambda: ("ssh", "mac1"), helper=lambda host: "sb-helper").start()
    args = ["--jump", "box1", "a", "w1:p1", "w1:t1", "w1:p1", "0", ""]
    check("link-sends", link.send(args))
    link.proc.wait(5)
    argv = (d / "argv").read_text()
    check("link-ssh-with-controlmaster", "ControlMaster=auto" in argv and "ControlPersist=600" in argv
          and argv.strip().endswith("sb-helper --jump-server") and "mac1" in argv, argv)
    check("link-one-json-line", json.loads((d / "stdin").read_text()) == args, (d / "stdin").read_text())
    sb.SSH = old_ssh
    nolink = sb.JumpLink(find=lambda: None).start()
    check("link-no-client", nolink.send(args, timeout=2) is False)
    calls2 = []
    orig_popen = sb.subprocess.Popen

    class P:
        def __init__(self, argv, **kw):
            calls2.append(argv)
            self.stdin = None

        def poll(self):
            return None
    sb.subprocess.Popen = P
    try:
        sb.JumpLink(find=lambda: ("local", None)).start().ready.wait(2)
    finally:
        sb.subprocess.Popen = orig_popen
    check("link-local-no-ssh", calls2 and calls2[0][-1] == "--jump-server" and calls2[0][0] == sys.executable, calls2)

import io as _io
got_jump = []
killed = []


class FakeOsa:
    def kill(self):
        killed.append(1)


orig = (sb.jump, sb.local_tui_tty, sb.subprocess.Popen)
sb.jump = lambda *a, **kw: got_jump.append((a, kw)) or 0
sb.local_tui_tty = lambda ps_text=None: "/dev/ttys000"
sb.subprocess.Popen = lambda argv, **kw: FakeOsa()
try:
    sb.jump_server(_io.StringIO(json.dumps(["--jump", "box1", "a", "w1:p1", "w1:t1", "w1:p1", "1", "logs"]) + "\n"))
    check("server-jumps-with-what-is-ready", got_jump and got_jump[0][0] == ("box1", "a", "w1:p1", "w1:t1", "w1:p1", True, "logs")
          and got_jump[0][1].get("tty") == "/dev/ttys000" and isinstance(got_jump[0][1].get("osa"), FakeOsa), got_jump)
    got_jump.clear()
    sb.jump_server(_io.StringIO(""))
    check("server-no-line-no-jump", not got_jump and killed, (got_jump, killed))
    killed.clear()
    sb.jump_server(_io.StringIO("not json\n"))
    check("server-broken-line-no-jump", not got_jump and killed)
finally:
    sb.jump, sb.local_tui_tty, sb.subprocess.Popen = orig

# 14. No child reads the popup's terminal.
tree = ast.parse(SOURCE)
no_stdin = []
for node in ast.walk(tree):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr in ("run", "Popen") and getattr(node.func.value, "id", "") == "subprocess":
        if not any(k.arg == "stdin" for k in node.keywords):
            no_stdin.append(node.lineno)
check("every-child-states-its-stdin", not no_stdin, "lines without stdin: %s" % no_stdin)

# 15. Another machine, fast.
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
    check("demo-enter-remote", len(out) == 2 and "--machine workstation agent focus w1:p3" in out[0]
          and "workstation" in out[1], out)
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

    def run_demo(keys, ready=b"rate-limiter-review"):
        """Run --demo in a pty, send `keys` once `ready` is on screen, return (output, rc)."""
        pid, fd = _pty.fork()
        if pid == 0:
            os.environ.update(TERM="xterm-256color", HERDR_BIN_PATH="/bin/false")
            os.execv(sys.executable, [sys.executable, "-B", str(TOOL), "--demo"])
        _f2.ioctl(fd, _tm2.TIOCSWINSZ, _st2.pack("HHHH", 40, 180, 0, 0))
        buf, sent, end = b"", False, _time.time() + 20
        while _time.time() < end:
            r, _, _ = _sel.select([fd], [], [], 0.1)
            chunk = None
            if r:
                try:
                    chunk = os.read(fd, 65536)
                except OSError:
                    chunk = b""
                if not chunk:  # the child closed the terminal: reap it
                    _, status = os.waitpid(pid, 0)
                    return buf, os.waitstatus_to_exitcode(status)
                buf += chunk
            if not sent and ready in buf:
                _time.sleep(0.5)
                os.write(fd, keys)
                sent = True
        os.kill(pid, 9)
        os.waitpid(pid, 0)
        return buf, None
    screen, rc = run_demo(b"\x1b")
    plain = sb.ANSI.sub("", screen.decode("utf-8", "replace"))
    check("demo-pty-renders", "18 agents" in plain and "laptop" in plain and "rate-limiter-review" in plain,
          plain[-500:])
    check("demo-pty-esc-exits-clean", rc == 0, rc)
    screen, rc = run_demo(b"\r")
    plain = sb.ANSI.sub("", screen.decode("utf-8", "replace"))
    check("demo-pty-enter-prints-what-it-would-do", rc == 0 and "demo: would run `herdr --machine workstation agent focus"
          in plain, (rc, plain[-400:]))
else:
    print("note: no fzf %s or newer here; the demo was not run in a terminal" % sb.version_text(sb.MIN_FZF))

# 24. The jump is opt-in.
check("jump-off-by-default", sb.DEFAULTS["jump"]["enabled"] is False and sb.JUMP_ENABLED is False)
check("enter-mode-off", sb.enter_mode([{"id": "m1"}]) == (False, True))
check("enter-mode-no-machines", sb.enter_mode([]) == (False, False))
check("enter-mode-demo", sb.enter_mode([{"id": "m1"}], demo=True) == (False, False))
sb.JUMP_ENABLED = True
try:
    check("enter-mode-on", sb.enter_mode([{"id": "m1"}]) == (True, False))
finally:
    sb.JUMP_ENABLED = False
argv = sb.fzf_argv("fzf", "self", "/tmp/s.sock", remote_enter=True)
check("enter-bound-when-off", "enter:transform(self --enter {1})" in argv, argv)
check("enter-not-bound-by-default", not any(a.startswith("enter:") for a in sb.fzf_argv("fzf", "self", "/tmp/s.sock")))
with tempfile.TemporaryDirectory() as d:
    d = pathlib.Path(d)
    (d / "machines.json").write_text(json.dumps([{"id": "m1", "label": "box1", "enabled": True}]))
    log = d / "log"
    fh = executable(d / "herdr", '#!/bin/sh\necho "$*" >> "%(d)s/log"\ncase "$*" in\n'
                                 '  "machine list --json") cat "%(d)s/machines.json" ;;\n'
                                 '  "--machine m2 "*) exit 1 ;;\n  *) exit 0 ;;\nesac\n' % {"d": d})
    run_dir = d / "run"
    run_dir.mkdir()

    def run_enter(row, cfg_dir=None):
        env = dict(os.environ, HERDR_BIN_PATH=str(fh), SWITCHBOARD_RUN_DIR=str(run_dir))
        if cfg_dir:
            env["HERDR_PLUGIN_CONFIG_DIR"] = str(cfg_dir)
        r = subprocess.run([sys.executable, str(TOOL), "--enter", row], stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE, universal_newlines=True, env=env, timeout=20)
        return r.stdout.strip()

    out = run_enter("m1|a|w1:p4|w1:t2")
    check("enter-remote-footer", out.startswith("change-footer:") and "ready on box1" in out, out)
    check("enter-remote-focuses-through-the-api", log.exists() and "--machine m1 agent focus w1:p4" in log.read_text(),
          log.read_text() if log.exists() else "")
    acks = (run_dir / "acks").read_text().splitlines() if (run_dir / "acks").exists() else []
    check("enter-remote-acks-the-tab", acks == ['["m1", "w1:t2"]'], acks)
    out = run_enter("m2|t|w1:p1|w1:t1")
    check("enter-remote-focus-fails-quietly", out.startswith("change-footer:") and "could not focus" in out, out)
    log.write_text("")
    out = run_enter("|a|w1:p1|w1:t1")
    check("enter-local-accepts", out == "accept" and "focus" not in log.read_text(), (out, log.read_text()))
    check("enter-header-nothing", run_enter("-") == "")
    cfg_on = d / "cfg-on"
    cfg_on.mkdir()
    (cfg_on / "config.toml").write_text("[jump]\nenabled = true\n")
    check("enter-remote-accepts-with-jump-on", run_enter("m1|a|w1:p4|w1:t2", cfg_on) == "accept")

    # The popup applies what --enter acknowledged: the done row turns idle.
    sb.STATE_DIR = str(d / "state")
    m1 = [{"id": "m1", "label": "box1"}]
    vivid = {"local": snap17(T1, ag17("p1", "working", 1, T1)), "m1": snap17(T1, ag17("p9", "working", 1, T1))}
    lv = sb.Live(m1, sb.entries_from(vivid["local"], "", "here", 0), fetch=lambda m="", t=None, i=None: vivid[m or "local"],
                 focus=T1)
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
    sock = os.path.join(str(d), "w.sock")
    fz = FakeFzf(sock, position=0)
    stop = _threading.Event()
    _threading.Thread(target=sb.watch, args=(lv, sock, str(d / "rows"), stop, str(ack_file)), daemon=True).start()
    _time.sleep(0.3)
    ack_file.write_text(json.dumps(["m1", T1]) + "\n")
    _time.sleep(0.5)
    stop.set()
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
            sent = link.send(["--jump"] * 8, timeout=5)
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


if FAILS:
    print("FAIL %d:\n  " % len(FAILS) + "\n  ".join(str(f) for f in FAILS))
    sys.exit(1)
print("ok")
