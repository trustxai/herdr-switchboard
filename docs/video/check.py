#!/usr/bin/env python3
"""Checks on the demo video. Each prints what it measured and OK or FAIL; the exit status is 1
when one fails.

  check.py footage [MP4]   out/terminal.mp4 lasts as long as the visible part of demo.tape
  check.py live [MP4]      when the screen changes in out/terminal.mp4 (what BEATS in schedule.py
                           are cut at), and whether the demo's live update, the change no key
                           causes, happens inside the beat whose line talks about it
  check.py sheet [MP4]     out/sheet.png: a frame from the middle of the intro, of every beat and
                           of the end card, to look at (default MP4: out/switchboard-demo.mp4)
  check.py narration [MP4] every line starts once its beat has begun, and all its speech falls
                           inside its own slot of the schedule (silencedetect)
  check.py loudness [MP4]  integrated loudness -16 LUFS (within 1 LU), true peak at most -1 dBTP
  check.py all             the five, on the default files

live, sheet and narration read remotion/src/schedule.json, which schedule.py writes. ffmpeg and
ffprobe come from PATH, or from FFMPEG and FFPROBE. Relative paths are taken from docs/video.
"""
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FFMPEG = os.environ.get("FFMPEG", "ffmpeg")
FFPROBE = os.environ.get("FFPROBE", "ffprobe")
TAPE = os.path.join(HERE, "demo.tape")
FOOTAGE = os.path.join(HERE, "out", "terminal.mp4")
FINAL = os.path.join(HERE, "out", "switchboard-demo.mp4")
SCHEDULE = os.path.join(HERE, "remotion", "src", "schedule.json")

FOOTAGE_TOLERANCE = 0.15  # s: at 15 fps it came out 0.01 s off; at 30 fps (1920x930), 0.41 s short
# A change of the screen: more than CHANGE_PX pixels of a 900x440 grey copy moved by more than 40
# levels from one frame to the next, at the 15 fps VHS captures at. A typed character changes 260
# or more, the live update about 6600. A change that starts from KEY_BEFORE seconds before a key
# lands (in the footage keys show about 0.1 s before the tape's own sums) to KEY_AFTER seconds
# after it (ctrl-y's message shows 0.39 s after the key) is that key's.
CHANGE_PX, KEY_BEFORE, KEY_AFTER = 200, 0.3, 0.8
# The beat that shows the live update, and how far inside it the update must happen: after the
# camera has moved in, and with time left to see it.
LIVE_LINE, LIVE_AFTER_START, LIVE_BEFORE_END = "v3-live", 0.5, 1.0
# Speech is what is louder than SILENCE; a quieter stretch of PAUSE or more ends it. Short, so
# that the 0.29 s of silence before the intro line counts. The pauses inside a line (a comma)
# then split it into several stretches, which count for the line whose slot they fall in.
SILENCE, PAUSE, EDGE = "-40dB", 0.1, 0.05
LOUDNESS, LOUDNESS_TOLERANCE, TRUE_PEAK = -16.0, 1.0, -1.0
KEYS = {"Backspace", "Delete", "Down", "End", "Enter", "Escape", "Home", "Insert", "Left", "PageDown", "PageUp",
        "Right", "Space", "Tab", "Up"}


def run(cmd):
    return subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=600)


def here(path):
    return path if os.path.isabs(path) else os.path.join(HERE, path)


def need(path):
    if not os.path.isfile(path):
        sys.exit("check.py: %s is missing" % os.path.relpath(path, HERE))
    return path


def duration(path):
    out = run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", need(path)])
    return float(out.stdout.strip())


def report(name, ok, text):
    print("%-9s %s  %s" % (name, "OK  " if ok else "FAIL", text))
    return ok


def to_seconds(value, default_unit="s"):
    m = re.fullmatch(r"([0-9.]+)(ms|s|m)?", value)
    if not m:
        raise ValueError(value)
    n, unit = float(m.group(1)), m.group(2) or default_unit
    return n / 1000 if unit == "ms" else n * 60 if unit == "m" else n


def tape(path):
    """The visible part of a VHS tape, from each Show to the next Hide: how long it lasts (its
    sleeps, plus one typing delay per typed character and per key) and, as (seconds, key), when
    each key lands in it. VHS presses a key, then waits the typing delay."""
    shown, total, typing, keys = True, 0.0, 0.05, []
    with open(path) as f:
        for raw in f:
            words = shlex.split(raw, comments=True)
            if not words:
                continue
            cmd, args = words[0], words[1:]
            name, _, speed = cmd.partition("@")
            if cmd == "Set" and args[:1] == ["TypingSpeed"]:
                typing = to_seconds(args[1])
            elif cmd in ("Show", "Hide"):
                shown = cmd == "Show"
            elif not shown or cmd in ("Output", "Require", "Set", "Source", "Env"):
                continue
            elif cmd == "Sleep":
                total += to_seconds(args[0])
            elif name == "Type" or name in KEYS or re.fullmatch(r"(Ctrl|Alt|Shift)\+.+", cmd):
                delay = to_seconds(speed) if speed and "+" not in cmd else typing
                presses = len("".join(args)) if name == "Type" else int(args[0]) if args else 1
                for _ in range(presses):
                    keys.append((round(total, 3), name))
                    total += delay
            else:
                sys.exit("check.py: cannot time %r while the tape is shown" % raw.strip())
    return round(total, 2), keys


def check_footage(path):
    want, got = tape(TAPE)[0], duration(path)
    return report("footage", abs(got - want) <= FOOTAGE_TOLERANCE,
                  "%s lasts %.2f s, the tape shows %.2f s (tolerance %.2f s)"
                  % (os.path.relpath(path, HERE), got, want, FOOTAGE_TOLERANCE))


def schedule():
    with open(need(SCHEDULE)) as f:
        return json.load(f)


def screen_changes(path):
    """When the screen changes, as (seconds, pixels): one entry per run of changed frames."""
    vf = ("fps=15,scale=900:440,format=gray,tblend=all_mode=difference,lut=c0='if(gt(val,40),255,0)',"
          "signalstats,metadata=mode=print:key=lavfi.signalstats.YAVG:file=-")
    out = run([FFMPEG, "-v", "error", "-i", need(path), "-vf", vf, "-f", "null", "-"])
    frames, t = [], None
    for line in out.stdout.splitlines():
        m = re.search(r"pts_time:([0-9.]+)", line)
        if m:
            t = float(m.group(1))
            continue
        m = re.search(r"YAVG=([0-9.]+)", line)
        if m and t is not None:
            px = float(m.group(1)) / 255 * 900 * 440
            if px > CHANGE_PX:
                frames.append((t, px))
    runs = []
    for t, px in frames:
        if runs and t - runs[-1][2] < 0.1:
            runs[-1][1], runs[-1][2] = max(runs[-1][1], px), t
        else:
            runs.append([t, px, t])
    return [(round(t, 2), int(px)) for t, px, _ in runs]


def cause(t, keys):
    """The key a change at t seconds comes from, or None for a change no key causes."""
    for at, name in keys:
        if at - KEY_BEFORE <= t <= at + KEY_AFTER:
            return name
    return None


def judge_live(changes, keys, beat):
    """(ok, text) for the first change no key causes, against the beat that shows it."""
    unprompted = [t for t, _ in changes if cause(t, keys) is None]
    if not unprompted:
        return False, "no change without a key: the demo's live update is not in the footage"
    t, lo, hi = unprompted[0], beat["f0"] + LIVE_AFTER_START, beat["f1"] - LIVE_BEFORE_END
    where = "inside" if lo <= t <= hi else "outside"
    return lo <= t <= hi, ("the live update shows at %.2f s, %s %s's beat (%.2f to %.2f s; it must show"
                           " between %.2f and %.2f s)" % (t, where, beat["voice"], beat["f0"], beat["f1"], lo, hi))


def check_live(path):
    keys = tape(TAPE)[1]
    beat = next((b for b in schedule()["beats"] if b["voice"] == LIVE_LINE), None)
    changes = screen_changes(path)
    print("changes   %s: %s" % (os.path.relpath(path, HERE), ", ".join(
        "%.2f %s" % (t, cause(t, keys) or "(no key)") for t, _ in changes)))
    if beat is None:
        return report("live", False, "schedule.json has no beat for %s" % LIVE_LINE)
    ok, text = judge_live(changes, keys, beat)
    return report("live", ok, text)


def check_sheet(path):
    s = schedule()
    intro, end_start = s["intro"], s["intro"] + s["terminal"]
    times = [intro / 2] + [intro + (b["c0"] + b["c1"]) / 2 for b in s["beats"]] + [end_start + s["end"] / 2]
    sheet = os.path.join(HERE, "out", "sheet.png")
    with tempfile.TemporaryDirectory() as d:
        for i, t in enumerate(times):
            out = run([FFMPEG, "-v", "error", "-y", "-ss", "%.2f" % t, "-i", need(path), "-frames:v", "1",
                       "-vf", "scale=640:-1", os.path.join(d, "%02d.png" % i)])
            if out.returncode != 0:
                return report("sheet", False, "no frame at %.2f s: %s" % (t, out.stderr.strip()))
        out = run([FFMPEG, "-v", "error", "-y", "-i", os.path.join(d, "%02d.png"), "-vf",
                   "tile=4x%d:padding=8:margin=8" % ((len(times) + 3) // 4), "-frames:v", "1", sheet])
    return report("sheet", out.returncode == 0, "%s: frames at %s s" % (
        os.path.relpath(sheet, HERE), ", ".join("%.1f" % t for t in times)))


def speech(path):
    """The stretches of sound between silences, as (start, end) in seconds."""
    err = run([FFMPEG, "-hide_banner", "-nostats", "-i", need(path), "-vn", "-af",
               "silencedetect=noise=%s:d=%s" % (SILENCE, PAUSE), "-f", "null", "-"]).stderr
    edges = [(m.group(1), float(m.group(2))) for m in re.finditer(r"silence_(start|end): ([0-9.]+)", err)]
    spans, start = [], 0.0
    for kind, t in edges:
        if kind == "start":
            if t > start:
                spans.append((start, t))
            start = None
        else:
            start = t
    if start is not None and duration(path) - start > 0.01:
        spans.append((start, duration(path)))
    return spans


def judge_narration(lines, spans):
    """One (voice, ok, text) per line of the schedule's narration. Each line has a slot, from
    when it starts to when its file ends (at to at + length), and a stretch of speech belongs to
    the line whose slot holds its start. Speech outside every slot comes from a line that started
    too early, or ran on: it counts against the line it comes before, or the last one."""
    slots = [(n, n["at"] - EDGE, n["at"] + n["length"] + EDGE) for n in lines]
    mine = {n["voice"]: [] for n in lines}
    stray = {n["voice"]: [] for n in lines}
    for start, end in spans:
        owner = next((n for n, lo, hi in slots if lo <= start < hi), None)
        if owner is not None:
            mine[owner["voice"]].append((start, end))
        else:
            after = next((n for n, lo, _ in slots if lo > start), lines[-1])
            stray[after["voice"]].append((start, end))
    results = []
    for n, lo, hi in slots:
        faults = ["speech at %.2f to %.2f s, outside every line's slot" % sp for sp in stray[n["voice"]]]
        got = mine[n["voice"]]
        if not got:
            faults.append("no speech in its slot")
        else:
            if got[0][0] < n["beat"]:
                faults.append("starts before its beat")
            if got[-1][1] > hi:
                faults.append("runs past the end of its slot")
        heard = "speech %.2f to %.2f s" % (got[0][0], got[-1][1]) if got else "no speech"
        results.append((n["voice"], not faults, "%s: beat %.2f s, slot %.2f to %.2f s, %s%s" % (
            n["voice"], n["beat"], n["at"], n["at"] + n["length"], heard, "; " + "; ".join(faults) if faults else "")))
    return results


def check_narration(path):
    ok = True
    for _, good, text in judge_narration(schedule()["narration"], speech(path)):
        ok = report("narration", good, text) and ok
    return ok


def check_loudness(path):
    err = run([FFMPEG, "-hide_banner", "-nostats", "-i", need(path), "-vn", "-af", "ebur128=peak=true", "-f", "null",
               "-"]).stderr
    summary = err[err.rfind("Summary:"):]
    i = re.search(r"I:\s+(-?[0-9.]+) LUFS", summary)
    peak = re.search(r"True peak:\s+Peak:\s+(-?[0-9.inf]+) dBFS", summary)
    if not (i and peak):
        return report("loudness", False, "no ebur128 summary for %s" % os.path.relpath(path, HERE))
    loud, tp = float(i.group(1)), float(peak.group(1))
    return report("loudness", abs(loud - LOUDNESS) <= LOUDNESS_TOLERANCE and tp <= TRUE_PEAK,
                  "integrated %.1f LUFS (target %.0f within %.0f), true peak %.1f dBTP (at most %.0f)"
                  % (loud, LOUDNESS, LOUDNESS_TOLERANCE, tp, TRUE_PEAK))


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ""
    path = here(argv[2]) if len(argv) > 2 else None
    checks = {"footage": (check_footage, FOOTAGE), "live": (check_live, FOOTAGE), "sheet": (check_sheet, FINAL),
              "narration": (check_narration, FINAL), "loudness": (check_loudness, FINAL)}
    if cmd == "all":
        results = [fn(default) for fn, default in checks.values()]
    elif cmd in checks:
        fn, default = checks[cmd]
        results = [fn(path or default)]
    else:
        sys.exit(__doc__.strip())
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
