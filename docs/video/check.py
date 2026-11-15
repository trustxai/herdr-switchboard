#!/usr/bin/env python3
"""Checks on the rendered demo video. Each prints what it measured and OK or FAIL; the exit
status is 1 when one fails.

  check.py footage [MP4]   out/terminal.mp4 lasts as long as the visible part of demo.tape
  check.py sheet [MP4]     out/sheet.png: a frame from the middle of the intro, of every beat
                           and of the end card, to look at (default MP4: out/switchboard-demo.mp4)
  check.py narration [MP4] every line starts after its beat begins and ends before the next
                           line is due (silencedetect)
  check.py loudness [MP4]  integrated loudness -16 LUFS (within 1 LU), true peak at most -1 dBTP
  check.py all             the four, on the default files

They read remotion/src/schedule.json, which schedule.py writes. ffmpeg and ffprobe come from
PATH, or from FFMPEG and FFPROBE. Relative paths are taken from docs/video.
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
# The composition starts the intro line 0.25 s in and the end line 0.5 s into the end card
# (remotion/src/Demo.jsx).
INTRO_AT, END_AT = 0.25, 0.5
# Speech is what is louder than SILENCE; a quieter stretch of PAUSE or more ends it. Short, so
# that the 0.29 s of silence before the intro line counts. The pauses inside a line (a comma)
# then split it into several stretches, which count for the line they fall in.
SILENCE, PAUSE = "-40dB", 0.1
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


def tape_seconds(path):
    """How long the visible part of a VHS tape lasts: its sleeps, plus one typing delay per
    typed character and per key, from each Show to the next Hide."""
    shown, total, typing = True, 0.0, 0.05
    with open(path) as f:
        for raw in f:
            words = shlex.split(raw, comments=True)
            if not words:
                continue
            cmd, args = words[0], words[1:]
            if cmd == "Set" and args[:1] == ["TypingSpeed"]:
                typing = to_seconds(args[1])
            elif cmd in ("Show", "Hide"):
                shown = cmd == "Show"
            elif not shown or cmd in ("Output", "Require", "Set", "Source", "Env"):
                continue
            elif cmd == "Sleep":
                total += to_seconds(args[0])
            elif cmd.split("@")[0] == "Type":
                speed = to_seconds(cmd.split("@")[1]) if "@" in cmd else typing
                total += speed * sum(len(a) for a in args)
            elif cmd.split("@")[0] in KEYS or re.fullmatch(r"(Ctrl|Alt|Shift)\+.+", cmd):
                speed = to_seconds(cmd.split("@")[1]) if "@" in cmd and "+" not in cmd else typing
                total += speed * (int(args[0]) if args else 1)
            else:
                sys.exit("check.py: cannot time %r while the tape is shown" % raw.strip())
    return round(total, 2)


def check_footage(path):
    want, got = tape_seconds(TAPE), duration(path)
    return report("footage", abs(got - want) <= FOOTAGE_TOLERANCE,
                  "%s lasts %.2f s, the tape shows %.2f s (tolerance %.2f s)"
                  % (os.path.relpath(path, HERE), got, want, FOOTAGE_TOLERANCE))


def schedule():
    with open(need(SCHEDULE)) as f:
        return json.load(f)


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


def check_narration(path):
    s = schedule()
    intro, end_start = s["intro"], s["intro"] + s["terminal"]
    # (line, when its beat begins, when the composition starts the line)
    lines = [("v0-intro", 0.0, INTRO_AT)]
    lines += [(b["voice"], intro + b["c0"], intro + b["c0"] + s["lead"]) for b in s["beats"]]
    lines += [("v7-end", end_start, end_start + END_AT)]
    spans = speech(path)
    ok = True
    for i, (name, beat, due) in enumerate(lines):
        nxt = lines[i + 1][2] if i + 1 < len(lines) else float("inf")
        # The speech of a line is what starts between its own start and the next line's.
        mine = [sp for sp in spans if due - 0.05 <= sp[0] < nxt - 0.05]
        if not mine:
            ok = report("narration", False, "%s: no speech between %.2f and %.2f s" % (name, due, nxt)) and ok
            continue
        start, end = mine[0][0], mine[-1][1]
        good = start >= beat and end < nxt
        ok = report("narration", good, "%s: beat %.2f s, speech %.2f to %.2f s, next line at %s" % (
            name, beat, start, end, "%.2f s" % nxt if nxt != float("inf") else "-")) and ok
    stray = [sp for sp in spans if sp[0] < lines[0][2] - 0.05]
    if stray:
        ok = report("narration", False, "speech before the first line: %s" % stray) and ok
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
    checks = {"footage": (check_footage, FOOTAGE), "sheet": (check_sheet, FINAL),
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
