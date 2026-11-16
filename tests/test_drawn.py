#!/usr/bin/env python3
"""Tests for bin/drawn, the hook that notes what a window drew. Standard library only; prints
"ok" or the failures.

What it has to get right, and how it fails otherwise:

1. The token: "<seq> <cols>x<rows>" entries, highest seq first, at most 4 and 80 characters.
   A malformed token is read as far as it is valid and never crashes the hook.
2. What is noted: the agents of the focused tab only, under the focused tab's size, and only
   when that seq is higher than the one already noted for that size. The headless size (no
   window on the machine) is never noted.
3. The socket: herdr answers one request per connection and closes it, so every request opens
   its own (reusing one gave a broken pipe on the second request). An error answer raises.
4. The locks: a pass that cannot get the write lock in time is skipped, not queued; a watcher
   starts only when none holds the watch lock, detached in its own session with no terminal.
5. The watcher notes once a second, keeps noting when a check fails, and exits when the plugin
   is disabled, removed or moved to another root (an update), when its own file or root is
   gone, or when herdr's socket has not answered for GONE_AFTER seconds.
6. The manifest runs it on the startup and on the events that change what a window shows, and
   never on pane.updated: writing a token emits pane.updated, so that would loop.
7. The program as herdr runs it: no output, exit 0, whatever the environment.
"""
import fcntl
import importlib.machinery
import importlib.util
import json
import os
import pathlib
import socket
import subprocess
import sys
import tempfile
import threading
import time

sys.dont_write_bytecode = True
ROOT = pathlib.Path(__file__).resolve().parent.parent
TOOL = ROOT / "bin" / "drawn"
loader = importlib.machinery.SourceFileLoader("drawn", str(TOOL))
spec = importlib.util.spec_from_loader("drawn", loader)
d = importlib.util.module_from_spec(spec)
loader.exec_module(d)

FAILS = []


def check(name, cond, detail=""):
    if not cond:
        FAILS.append("%s: %r" % (name, detail))


def snap(focus, size, agents):
    cols, rows = size
    return {"focused_tab_id": focus,
            "layouts": [{"tab_id": focus, "area": {"x": 0, "y": 0, "width": cols, "height": rows}},
                        {"tab_id": "w1:t9", "area": {"x": 0, "y": 0, "width": 50, "height": 20}}],
            "agents": agents}


def ag(pane, tab, seq, token=None):
    a = {"pane_id": pane, "tab_id": tab, "state_change_seq": seq, "agent_status": "idle"}
    if token is not None:
        a["tokens"] = {d.TOKEN: token, "other": "x"}
    return a


# 1. The token.
check("parse", d.parse("12 239x63,9 250x63") == {"239x63": 12, "250x63": 9})
check("parse-keeps-the-highest-of-a-size", d.parse("3 10x10,7 10x10") == {"10x10": 7})
check("parse-skips-garbage", d.parse("x 10x10,5 10y10,6 0x5,7 10x10 extra,8 10x10,-1 5x5") == {"10x10": 8},
      d.parse("x 10x10,5 10y10,6 0x5,7 10x10 extra,8 10x10,-1 5x5"))
check("parse-not-a-string", d.parse(None) == {} and d.parse(42) == {} and d.parse("") == {})
check("serialize-highest-first", d.serialize({"10x10": 3, "20x20": 9}) == "9 20x20,3 10x10")
many = {"%dx%d" % (100 + i, 50 + i): 1000000000 + i for i in range(9)}
value = d.serialize(many)
check("serialize-keeps-at-most-4", len(value.split(",")) <= d.KEEP and len(value) <= d.MAX_LEN, value)
check("serialize-drops-the-lowest", "1000000008" in value and "1000000000 " not in value, value)
check("merge-new-size", d.merge("5 10x10", "20x20", 7) == "7 20x20,5 10x10")
check("merge-higher-seq", d.merge("5 10x10", "10x10", 6) == "6 10x10")
check("merge-same-or-lower-is-none", d.merge("5 10x10", "10x10", 5) is None and d.merge("5 10x10", "10x10", 4) is None)
check("merge-from-nothing", d.merge(None, "10x10", 0) == "0 10x10")
full = "12 200x50,12 210x55,12 220x60,12 230x62"
new = d.merge(full, "239x63", 12)
check("merge-the-size-just-noted-survives", new and new.startswith("12 239x63,") and len(new.split(",")) == d.KEEP, new)
check("merge-then-nothing-to-do", d.merge(new, "239x63", 12) is None, new)

# 2. What is noted.
s = snap("w1:t1", (239, 63), [ag("w1:p1", "w1:t1", 10), ag("w1:p2", "w1:t1", 4, "4 239x63"),
                              ag("w1:p3", "w1:t2", 12), ag("w1:p4", "w1:t1", 8, "3 239x63,8 250x63")])
r = d.reports(s)
got = {x["pane_id"]: x["tokens"][d.TOKEN] for x in r}
check("reports-focused-tab-only", set(got) == {"w1:p1", "w1:p4"}, got)
check("reports-values", got == {"w1:p1": "10 239x63", "w1:p4": "8 239x63,8 250x63"}, got)
check("reports-source", all(x["source"] == d.SOURCE for x in r) and all(set(x["tokens"]) == {d.TOKEN} for x in r), r)
check("reports-headless-is-not-a-window", d.reports(snap("w1:t1", (120, 40), [ag("w1:p1", "w1:t1", 10)])) == [])
check("reports-no-layout", d.reports({"focused_tab_id": "w1:t1", "agents": [ag("w1:p1", "w1:t1", 3)]}) == [])
check("reports-no-focus", d.reports({"layouts": [], "agents": [ag("w1:p1", "w1:t1", 3)]}) == [])
bad = snap("w1:t1", (80, 24), [None, "x", {"pane_id": 5, "tab_id": "w1:t1", "state_change_seq": 1},
                               {"pane_id": "a", "tab_id": "w1:t1", "state_change_seq": True},
                               {"pane_id": "b", "tab_id": "w1:t1", "state_change_seq": "3"},
                               {"pane_id": "c", "tab_id": "w1:t1", "state_change_seq": -2},
                               {"pane_id": "e", "tab_id": "w1:t1", "state_change_seq": 2, "tokens": "nope"},
                               {"pane_id": "f", "tab_id": "w1:t1", "state_change_seq": 2, "tokens": {d.TOKEN: 7}}])
got = [x["pane_id"] for x in d.reports(bad)]
check("reports-malformed-agents", got == ["e", "f"], got)
left = {"panes": [{"pane_id": "w1:p7", "tokens": {d.TOKEN: "3 9x9"}}, {"pane_id": "w1:p8", "tokens": {"other": "x"}},
                  {"pane_id": "w1:p9"}, "junk"],
        "agents": [{"pane_id": "w1:p6", "tokens": {d.TOKEN: "1 9x9"}}]}
left["panes"].append({"pane_id": "w1:p6", "tokens": {d.TOKEN: "1 9x9"}})
# w1:p7's agent has exited: the token stays on the pane, and it must go too.
check("clears-every-pane-once", [x["pane_id"] for x in d.clears(left)] == ["w1:p7", "w1:p6"]
      and all(x["tokens"] == {d.TOKEN: None} for x in d.clears(left)), d.clears(left))


# 3. The socket, against a server that answers like herdr: one request, then it closes.
class FakeHerdr:
    def __init__(self, path, handler):
        self.path, self.handler, self.requests = path, handler, []
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(path)
        self.sock.listen(16)
        self.alive = True
        threading.Thread(target=self.serve, daemon=True).start()

    def serve(self):
        while self.alive:
            try:
                c, _ = self.sock.accept()
            except OSError:
                return
            with c:
                buf = b""
                while b"\n" not in buf:
                    chunk = c.recv(65536)
                    if not chunk:
                        break
                    buf += chunk
                if not buf:
                    continue
                req = json.loads(buf.split(b"\n")[0])
                self.requests.append(req)
                c.sendall((json.dumps(self.handler(req)) + "\n").encode())

    def close(self):
        self.alive = False
        self.sock.close()


tmp = tempfile.mkdtemp(prefix="drawn-test-", dir="/tmp")
state = os.path.join(tmp, "state")
tokens = {}


def handler(req):
    if req["method"] == "session.snapshot":
        agents = [ag("w1:p1", "w1:t1", 10, tokens.get("w1:p1")), ag("w1:p2", "w1:t1", 6, tokens.get("w1:p2"))]
        return {"id": req["id"], "result": {"type": "session_snapshot", "snapshot": snap("w1:t1", (100, 30), agents)}}
    if req["method"] == "pane.report_metadata":
        tokens[req["params"]["pane_id"]] = req["params"]["tokens"][d.TOKEN]
        return {"id": req["id"], "result": {"type": "ok"}}
    if req["method"] == "plugin.list":
        return {"id": req["id"], "result": {"type": "plugin_list", "plugins": []}}
    return {"id": req["id"], "error": {"code": "invalid_request", "message": "no"}}


sockpath = os.path.join(tmp, "h.sock")
fake = FakeHerdr(sockpath, handler)
env = {"HERDR_SOCKET_PATH": sockpath, "HERDR_PLUGIN_STATE_DIR": state}
d.event(env)
check("event-notes-every-agent-of-the-tab", tokens == {"w1:p1": "10 100x30", "w1:p2": "6 100x30"}, tokens)
check("event-one-connection-per-request", [q["method"] for q in fake.requests]
      == ["session.snapshot", "pane.report_metadata", "pane.report_metadata"], fake.requests)
n = len(fake.requests)
d.event(env)
check("event-nothing-new-writes-nothing", [q["method"] for q in fake.requests[n:]] == ["session.snapshot"], fake.requests[n:])
try:
    d.call(sockpath, "nope", {})
    check("call-error-raises", False)
except ValueError:
    pass

# 4. The locks: one set per herdr server (named sessions share the state directory).
check("locks-per-server", d.server_file("watch", "/a/herdr.sock", "lock") != d.server_file("watch", "/b/herdr.sock", "lock")
      and d.server_file("watch", "/a/herdr.sock", "lock").startswith("watch-"))
fd = d.open_lock(state, d.server_file("drawn", sockpath, "lock"))
fcntl.flock(fd, fcntl.LOCK_EX)
tokens.clear()
n = len(fake.requests)
t0 = time.time()
d.note(sockpath, state, 0.2)
check("note-skips-when-locked", tokens == {} and len(fake.requests) == n and time.time() - t0 < 2, tokens)
os.close(fd)
started = []


def popen(argv, **kw):
    started.append((argv, kw))


check("start-watcher-when-free", d.start_watcher(env, popen) is True and started, started)
argv, kw = started[0]
check("start-watcher-detached", argv[-1] == "--watch" and argv[1] == os.path.abspath(str(TOOL))
      and kw.get("start_new_session") is True and kw.get("stdin") == subprocess.DEVNULL
      and kw.get("stdout") == subprocess.DEVNULL and kw.get("stderr") == subprocess.DEVNULL, (argv, kw))
other = dict(env, HERDR_SOCKET_PATH=os.path.join(tmp, "other.sock"))
open(other["HERDR_SOCKET_PATH"], "w").close()
fd = d.open_lock(state, d.server_file("watch", sockpath, "lock"))
fcntl.flock(fd, fcntl.LOCK_EX)
started.clear()
check("start-watcher-other-server", d.start_watcher(other, popen) is True and started, started)
started.clear()
check("start-watcher-not-twice", d.start_watcher(env, popen) is False and not started, started)
check("watch-exits-when-one-runs", d.watch(dict(env), sleep=lambda s: None) is None)
os.close(fd)
check("start-watcher-needs-the-env", d.start_watcher({}, popen) is False)
check("start-watcher-needs-a-server", d.start_watcher(dict(env, HERDR_SOCKET_PATH=os.path.join(tmp, "none.sock")), popen)
      is False and not started, started)


# 5. The watcher, with a fake herdr, clock and sleep.
class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def run_watch(rpc, env, max_loops=50, me=None):
    clock, loops = Clock(), [0]

    def sleep(s):
        loops[0] += 1
        clock.t += s
        if loops[0] >= max_loops:
            raise KeyboardInterrupt

    try:
        d.watch(env, sleep=sleep, clock=clock, rpc=rpc, me=me)
        return "returned", loops[0]
    except KeyboardInterrupt:
        return "kept going", loops[0]


def rpc_with(plugins, snapshot_ok=True, list_ok=True, calls=None, writes=None):
    def rpc(path, method, params, timeout=3.0):
        if calls is not None:
            calls.append(method)
        if writes is not None and method == "pane.report_metadata":
            writes.append(params)
        if method == "plugin.list":
            if not list_ok:
                raise OSError("refused")
            return {"type": "plugin_list", "plugins": plugins}
        if method == "session.snapshot":
            if not snapshot_ok:
                raise OSError("no socket")
            return {"snapshot": snap("w1:t1", (100, 30), [ag("w1:p1", "w1:t1", 3), ag("w1:p2", "w1:t2", 5, "5 9x9")])}
        return {"type": "ok"}
    return rpc


root = os.path.join(tmp, "root")
os.makedirs(root)
wenv = dict(env, HERDR_PLUGIN_ROOT=root, HERDR_PLUGIN_ID="trustxai.switchboard")
ours = [{"plugin_id": "trustxai.switchboard", "enabled": True, "plugin_root": root}]
calls = []
how, loops = run_watch(rpc_with(ours, calls=calls), wenv, max_loops=40)
check("watch-keeps-going", how == "kept going", (how, loops))
check("watch-notes-every-second", calls.count("session.snapshot") == 40, calls.count("session.snapshot"))
check("watch-checks-every-30-s", 1 < calls.count("plugin.list") <= 3, calls.count("plugin.list"))
for why, plugins in [("removed", []), ("disabled", [dict(ours[0], enabled=False)])]:
    writes = []
    how, loops = run_watch(rpc_with(plugins, writes=writes), wenv)
    check("watch-exits-when-%s" % why, how == "returned", (how, loops))
    check("watch-clears-its-token-when-%s" % why, writes == [{"pane_id": "w1:p2", "source": d.SOURCE,
                                                               "tokens": {d.TOKEN: None}}], writes)
writes = []
check("watch-exits-when-updated", run_watch(rpc_with([dict(ours[0], plugin_root=tmp)], writes=writes), wenv)[0]
      == "returned" and writes == [], writes)
gone = os.path.join(tmp, "gone")
check("watch-exits-when-its-root-is-gone", run_watch(rpc_with([dict(ours[0], plugin_root=gone)]),
                                                     dict(wenv, HERDR_PLUGIN_ROOT=gone))[0] == "returned")
check("watch-exits-when-its-file-is-gone", run_watch(rpc_with(ours), wenv, me=os.path.join(tmp, "no-drawn"))[0] == "returned")
calls = []
how, loops = run_watch(rpc_with(ours, list_ok=False, calls=calls), wenv, max_loops=10)
check("watch-a-failed-check-does-not-stop-it", how == "kept going" and calls.count("session.snapshot") == 10, calls)
err = os.path.join(state, d.server_file("drawn", sockpath, "err"))
check("watch-keeps-the-last-error", os.path.exists(err) and "plugin.list" in open(err).read())
how, loops = run_watch(rpc_with(ours, snapshot_ok=False), wenv, max_loops=500)
check("watch-exits-when-herdr-is-gone", how == "returned" and abs(loops - d.GONE_AFTER / d.INTERVAL) <= 2, (how, loops))
how, loops = run_watch(rpc_with(ours, snapshot_ok=False), dict(wenv, HERDR_SOCKET_PATH=os.path.join(tmp, "gone.sock")))
check("watch-exits-at-once-when-the-socket-is-gone", how == "returned" and loops <= 1, (how, loops))
check("watch-unknown-answer-is-no-reason-to-stop", d.plugin_state("x", wenv, lambda *a, **k: {"weird": 1}) == "ours")

# 6. The manifest.
try:
    import tomllib
except ImportError:
    tomllib = None
manifest = (ROOT / "herdr-plugin.toml").read_text()
if tomllib:
    man = tomllib.loads(manifest)
    events = [e.get("on") for e in man.get("events", [])]
    check("manifest-events", sorted(events) == sorted(["pane.agent_status_changed", "tab.focused",
                                                       "pane.focused", "workspace.focused"]), events)
    check("manifest-never-on-pane-updated", "pane.updated" not in events, events)
    check("manifest-events-run-the-hook", all(e["command"][-1].endswith('/bin/drawn"') for e in man["events"]),
          man["events"])
    starts = man.get("startup", [])
    check("manifest-startup-starts-the-watcher", len(starts) == 1 and starts[0]["command"][-1].endswith("--start"), starts)
check("manifest-pane-updated-absent", '"pane.updated"' not in manifest)

# 7. The program as herdr runs it.
before = set(os.listdir(state))
for name, e in [("no-env", {}), ("dead-socket", {"HERDR_SOCKET_PATH": os.path.join(tmp, "none.sock"),
                                                 "HERDR_PLUGIN_STATE_DIR": state})]:
    for args in ([], ["--start"]):
        r = subprocess.run([sys.executable, str(TOOL)] + args, stdin=subprocess.DEVNULL, capture_output=True,
                           timeout=20, env=dict(e, PATH=os.environ.get("PATH", "/usr/bin:/bin")))
        check("program-%s-%s-silent" % (name, args), r.returncode == 0 and r.stdout == b"" and r.stderr == b"",
              (r.returncode, r.stdout, r.stderr))
time.sleep(0.5)
new_files = set(os.listdir(state)) - before
check("program-leaves-nothing-without-a-server", not new_files, new_files)
fake.close()
subprocess.run(["rm", "-rf", tmp])

if FAILS:
    print("FAIL %d:\n  " % len(FAILS) + "\n  ".join(FAILS))
    sys.exit(1)
print("ok")
