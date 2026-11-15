#!/usr/bin/env python3
"""Tests for the scripts behind the demo video: el.py, schedule.py and check.py. Standard library
only, no ffmpeg and no network (the ElevenLabs API is a server on 127.0.0.1). Prints "ok" or the
failures; `make test` runs it.

1. el.py never shows the API key: a key file with more than one line or a space is refused with
   a message that leaves the value out; an error reply that echoes the key has it taken out
   before it is cut; a redirect does not carry the key to the next address.
2. schedule.py refuses footage shorter than its beats, checks the length of what ffmpeg wrote,
   and writes schedule.json only once both are right, with every line of the narration placed.
3. check.py: the tape's length and keys; the narration check puts each stretch of speech in the
   slot of the line it belongs to, so a line that starts early fails, also with a pause inside;
   the live update has to show inside the beat that talks about it, with margin.

A section that crashes is a failure that names the exception type and the line, never its
message, which could hold the key.
"""
import sys

sys.dont_write_bytecode = True  # importing the scripts must leave no __pycache__ in docs/video

import contextlib  # noqa: E402
import http.server  # noqa: E402
import importlib.util  # noqa: E402
import io  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import secrets  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402
import threading  # noqa: E402
import traceback  # noqa: E402
import types  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FAILURES = []
# The lengths of the lines in the launch video, in seconds.
LINES = {"v0-intro": 2.56, "v1-list": 3.6, "v2-preview": 3.92, "v3-live": 2.48, "v4-filter": 3.44,
         "v5-copy": 3.6, "v6-enter": 3.6, "v7-end": 2.72}


def check(name, cond, detail=""):
    if not cond:
        FAILURES.append("%s %s" % (name, detail))


def load(name):
    spec = importlib.util.spec_from_file_location("video_" + name, os.path.join(HERE, name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(fn, *args):
    """(what fn printed, its exit message or None, the text of any other exception or None)."""
    out = io.StringIO()
    exit_text = error = None
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            fn(*args)
    except SystemExit as e:
        exit_text = str(e.code)
    except Exception:
        error = traceback.format_exc()
    return out.getvalue(), exit_text, error


# --- 1. el.py ------------------------------------------------------------------------------

def serve(reply):
    """A server on 127.0.0.1 that answers every GET with reply(request headers) -> (status,
    headers, body). Returns it, the headers of each request it saw, and its thread."""
    seen = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            headers = {k.lower(): v for k, v in self.headers.items()}
            seen.append(headers)
            status, extra, body = reply(headers)
            self.send_response(status)
            for k, v in extra:
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    return server, seen, thread


def stop(server, thread):
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def test_el():
    for name in list(os.environ):  # the fake API is on 127.0.0.1: no proxy in between
        if name.lower() in ("http_proxy", "https_proxy", "all_proxy"):
            del os.environ[name]
    os.environ["no_proxy"] = "*"
    el = load("el")
    key = "fake-" + secrets.token_hex(16)  # made here, so no key-like text is in the repository
    with tempfile.TemporaryDirectory() as d:
        el.KEY_FILE = os.path.join(d, "api_key")
        el.API = "http://127.0.0.1:9"  # nothing may be sent in the first cases

        for name, content in (("two-lines", key + "\n" + key[::-1] + "\n"),
                              ("inner-space", key[:10] + " " + key[10:]), ("tab", key + "\t" + key[::-1])):
            with open(el.KEY_FILE, "w") as f:
                f.write(content)
            printed, exit_text, error = run(el.main, ["el.py", "user"])
            shown = printed + (exit_text or "") + (error or "")
            check("el-refuses-a-key-with-%s" % name, exit_text is not None and error is None,
                  "(it raised instead)" if error else "")
            check("el-never-shows-a-key-with-%s" % name, key[:8] not in shown and key[::-1][:8] not in shown)

        with open(el.KEY_FILE, "w") as f:
            f.write(key + "\n")

        # A reply that echoes the key, with the key across the 400 characters that are shown.
        server, seen, thread = serve(lambda h: (401, [], b"x" * 380 + h.get("xi-api-key", "").encode() + b" invalid"))
        el.API = "http://127.0.0.1:%d" % server.server_port
        printed, exit_text, error = run(el.main, ["el.py", "user"])
        stop(server, thread)
        shown = printed + (exit_text or "") + (error or "")
        check("el-the-api-got-the-key", bool(seen) and seen[0].get("xi-api-key") == key)
        check("el-error-reply-without-the-key", exit_text is not None and "HTTP 401" in exit_text
              and key[:8] not in shown and "<api key>" in exit_text, "(the key or a piece of it was shown)")

        # A redirect to another address does not take the key with it.
        target, seen_target, thread_target = serve(lambda h: (200, [], b'{"tier": "test"}'))
        location = "http://127.0.0.1:%d/v1/user/subscription" % target.server_port
        source, seen_source, thread_source = serve(lambda h: (302, [("Location", location)], b""))
        el.API = "http://127.0.0.1:%d" % source.server_port
        printed, exit_text, error = run(el.main, ["el.py", "user"])
        stop(source, thread_source)
        stop(target, thread_target)
        check("el-redirect-followed", exit_text is None and error is None and "test" in printed
              and len(seen_target) == 1)
        check("el-key-sent-to-the-api", bool(seen_source) and seen_source[0].get("xi-api-key") == key)
        check("el-key-not-sent-after-a-redirect", bool(seen_target) and "xi-api-key" not in seen_target[0])

        # batch needs the voice, and says so without a request.
        os.environ.pop(el.VOICE_ENV, None)
        printed, exit_text, error = run(el.main, ["el.py", "batch", os.path.join(HERE, "voice", "spec.json"), d])
        check("el-batch-needs-the-voice", exit_text is not None and el.VOICE_ENV in exit_text and error is None)


# --- 2. schedule.py ------------------------------------------------------------------------

def run_schedule(schedule, footage, timed_short=0.0, ffmpeg_rc=0):
    """schedule.main on fake files: (exit text, exception text, ffmpeg runs, the schedule it wrote
    or None, whether the fitted footage is left)."""
    with tempfile.TemporaryDirectory() as d:
        schedule.SPEC = os.path.join(d, "spec.json")
        with open(schedule.SPEC, "w") as f:
            json.dump({"lines": [{"id": k, "text": k} for k in LINES]}, f)
        schedule.VOICE_DIR = d
        schedule.FOOTAGE = os.path.join(d, "terminal.mp4")
        schedule.TIMED = os.path.join(d, "public", "terminal-timed.mp4")
        schedule.SCHEDULE = os.path.join(d, "schedule.json")
        schedule.SRC = d  # where the first version wrote its files
        runs = []

        def seconds(path):
            name = os.path.basename(path)
            if name == "terminal.mp4":
                return footage
            if name == "terminal-timed.mp4":
                return round(schedule.plan(LINES)["terminal"] - timed_short, 2)
            return LINES[name[:-4]]

        def fake_run(cmd, **kwargs):
            runs.append(cmd)
            with open(cmd[-1], "wb") as f:
                f.write(b"fitted footage")
            return subprocess.CompletedProcess(cmd, ffmpeg_rc)

        schedule.seconds = seconds
        schedule.subprocess = types.SimpleNamespace(run=fake_run, DEVNULL=subprocess.DEVNULL)
        printed, exit_text, error = run(lambda: sys.exit(schedule.main(["schedule.py"])))
        data = None
        if os.path.isfile(schedule.SCHEDULE):
            with open(schedule.SCHEDULE) as f:
                data = json.load(f)
        return exit_text, error, len(runs), data, os.path.isfile(schedule.TIMED)


def test_schedule():
    schedule = load("schedule")
    exit_text, error, runs, data, timed = run_schedule(schedule, footage=12.0)
    check("schedule-refuses-short-footage", error is None and exit_text not in (None, "0") and "12.00" in exit_text
          and runs == 0 and data is None, (exit_text, runs))
    exit_text, error, runs, data, timed = run_schedule(schedule, footage=25.16, timed_short=2.0)
    check("schedule-checks-what-ffmpeg-wrote", error is None and exit_text not in (None, "0") and runs == 1
          and data is None and not timed, (exit_text, runs, timed))
    exit_text, error, runs, data, timed = run_schedule(schedule, footage=25.16, ffmpeg_rc=1)
    check("schedule-nothing-written-when-ffmpeg-fails", error is None and exit_text == "1" and data is None,
          exit_text)
    exit_text, error, runs, data, timed = run_schedule(schedule, footage=25.16)
    check("schedule-writes-after-success", error is None and exit_text == "0" and data is not None and timed,
          exit_text)
    if not data:
        return
    narration, intro, beats = data["narration"], data["intro"], data["beats"]
    check("schedule-places-every-line", [n["voice"] for n in narration] == list(LINES)
          and all(n["length"] == LINES[n["voice"]] for n in narration))
    check("schedule-line-after-its-beat", narration[0]["at"] == schedule.INTRO_AT
          and all(abs(n["at"] - (intro + b["c0"] + data["lead"])) < 1e-6 and n["beat"] == round(intro + b["c0"], 3)
                  for n, b in zip(narration[1:-1], beats))
          and abs(narration[-1]["at"] - (intro + data["terminal"] + schedule.END_AT)) < 1e-6)
    check("schedule-each-line-fits-its-beat", all(b["c1"] - b["c0"] >= data["lead"] + LINES[b["voice"]]
                                                  + schedule.GAP - 1e-6 for b in beats))


# --- 3. check.py ---------------------------------------------------------------------------

def said(n, early=0.0, pause_after=0.3):
    """The stretches of speech of a line placed `early` seconds before its slot."""
    start = n["at"] - early + 0.03
    end = n["at"] - early + n["length"] - 0.3
    return [(round(start, 3), round(start + pause_after, 3)), (round(start + pause_after + 0.25, 3), round(end, 3))]


def test_check():
    check_py, schedule = load("check"), load("schedule")
    total, keys = check_py.tape(os.path.join(HERE, "demo.tape"))
    check("tape-length", total == 25.17, total)
    check("tape-keys", len(keys) == 22 and keys[0] == (3.5, "Down") and keys[-1][1] == "Ctrl+Y",
          (len(keys), keys[:1]))

    plan = schedule.plan(LINES)
    lines = plan["narration"]

    def verdicts(spans):
        return {voice: ok for voice, ok, _ in check_py.judge_narration(lines, sorted(spans))}

    good = [sp for n in lines for sp in said(n)]
    check("narration-all-in-place", all(verdicts(good).values()), verdicts(good))
    # The case that used to pass: a line that starts 0.2 s before its beat (0.35 s before its
    # slot), with a pause of 0.25 s after its first word.
    early = [sp for n in lines for sp in (said(n, early=0.35) if n["voice"] == "v3-live" else said(n))]
    v = verdicts(early)
    check("narration-early-line-fails-on-its-line", v["v3-live"] is False
          and all(ok for k, ok in v.items() if k != "v3-live"), v)
    # A line that goes on past its slot, without a pause.
    v2 = next(n for n in lines if n["voice"] == "v2-preview")
    first, second = said(v2)
    long_line = [sp for n in lines if n is not v2 for sp in said(n)]
    long_line += [first, (second[0], round(v2["at"] + v2["length"] + 0.4, 3))]
    v = verdicts(long_line)
    check("narration-overrun-fails-on-its-line", v["v2-preview"] is False
          and all(ok for k, ok in v.items() if k != "v2-preview"), v)
    v = verdicts([sp for n in lines if n["voice"] != "v4-filter" for sp in said(n)])
    check("narration-missing-line-fails", v["v4-filter"] is False and v["v5-copy"] is True, v)

    # The live update: the screen changes of the launch footage, where it came at 7.40 s, with it
    # at the 7.27 and 7.33 s of two later recordings.
    live_beat = next(b for b in plan["beats"] if b["voice"] == check_py.LIVE_LINE)
    old_beat = {"voice": "v3-live", "f0": 7.4, "f1": 11.7}
    for at in (7.27, 7.33, 7.40):
        changes = [(3.4, 25564), (4.8, 25526), (at, 6655), (11.87, 8884), (14.33, 342), (16.8, 1260)]
        ok, text = check_py.judge_live(changes, keys, live_beat)
        check("live-update-inside-its-beat-at-%.2f" % at, ok, text)
        ok, text = check_py.judge_live(changes, keys, old_beat)
        check("live-update-before-the-old-beat-fails-at-%.2f" % at, not ok, text)
    ok, text = check_py.judge_live([(3.4, 25564), (4.8, 25526), (11.87, 8884)], keys, live_beat)
    check("live-update-missing-fails", not ok, text)
    check("key-changes-are-the-keys", check_py.cause(3.4, keys) == "Down" and check_py.cause(16.8, keys) == "Ctrl+Y"
          and check_py.cause(7.3, keys) is None)


for section in (test_el, test_schedule, test_check):
    try:
        section()
    except Exception as e:
        where = traceback.extract_tb(e.__traceback__)[-1]
        FAILURES.append("%s crashed: %s at %s:%d" % (section.__name__, type(e).__name__,
                                                     os.path.basename(where.filename), where.lineno))

if FAILURES:
    print("FAIL %d:" % len(FAILURES))
    for failure in FAILURES:
        print("  " + failure)
    sys.exit(1)
print("ok")
