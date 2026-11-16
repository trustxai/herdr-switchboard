#!/usr/bin/env python3
"""Fit the terminal footage to the narration: each beat lasts at least as long as its line.

Measures every line of voice/spec.json with ffprobe (remotion/public/voice/<id>.mp3, from
`el.py batch`), cuts out/terminal.mp4 (from `vhs demo.tape`) into beats, and holds the last frame
of each beat until its line has had room. It writes:

  remotion/public/terminal-timed.mp4 the fitted footage
  remotion/src/schedule.json         the timeline that remotion/src/Demo.jsx renders and
                                     check.py checks: the beats, and when each line starts and
                                     how long it lasts

It refuses footage shorter than the beats, checks that the fitted footage lasts as long as the
schedule says, and writes schedule.json only after that, so a failed run never leaves a schedule
that does not match the footage. Times in the schedule are seconds of the composition, except
f0 and f1 (seconds of out/terminal.mp4) and c0 and c1 (seconds of the fitted footage).

ffmpeg and ffprobe come from PATH, or from FFMPEG and FFPROBE. Relative paths are taken from
docs/video, so the script works from any directory. `--dry-run` measures the lines and prints
the schedule and the ffmpeg command without writing anything.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = os.path.join(HERE, "voice", "spec.json")
VOICE_DIR = os.path.join(HERE, "remotion", "public", "voice")
FOOTAGE = os.path.join(HERE, "out", "terminal.mp4")
TIMED = os.path.join(HERE, "remotion", "public", "terminal-timed.mp4")
SCHEDULE = os.path.join(HERE, "remotion", "src", "schedule.json")
FFMPEG = os.environ.get("FFMPEG", "ffmpeg")
FFPROBE = os.environ.get("FFPROBE", "ffprobe")

# A beat's line starts LEAD seconds into the beat, and GAP seconds of silence follow it at least.
LEAD, GAP = 0.15, 0.3
# The intro line starts INTRO_AT seconds into the intro, the end line END_AT into the end card.
INTRO_LINE, INTRO_AT = "v0-intro", 0.25
END_LINE, END_AT = "v7-end", 0.5
# How far the fitted footage may be from the length the schedule gives it (one frame is 0.033 s).
TOLERANCE = 0.1

# Beats in seconds of out/terminal.mp4, with their line; `python3 check.py live` prints when the
# screen changes in that file. Each beat ends before a change it does not show, so the frame its
# hold repeats is a still one. Beats need not touch: nothing moves between 10.0 and 11.7 s, and
# that stretch is left out. The third beat starts at 5.6 s, 0.7 s after the second Down shows and
# well before the demo's live update (7.27 to 7.40 s in four recordings), so the update happens
# on screen while its line is said, with more than a second to spare on either side.
BEATS = [
    (0.0, 3.4, "v1-list"),
    (3.4, 5.6, "v2-preview"),
    (5.6, 10.0, "v3-live"),
    (11.7, 16.4, "v4-filter"),
    (16.4, 19.7, "v5-copy"),
    (19.7, 21.6, "v6-enter"),
]


def rel(path):
    return os.path.relpath(path, HERE)


def seconds(path):
    if not os.path.isfile(path):
        sys.exit("schedule.py: %s is missing" % rel(path))
    out = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        sys.exit("schedule.py: ffprobe failed on %s: %s" % (rel(path), out.stderr.strip()))
    return round(float(out.stdout.strip()), 2)


def check_beats():
    end = 0.0
    for f0, f1, vid in BEATS:
        if not end <= f0 < f1:
            sys.exit("schedule.py: the beat of %s (%s to %s s) must start after the one before ends"
                     " and end after it starts" % (vid, f0, f1))
        end = f1


def plan(voice):
    beats, c = [], 0.0
    for f0, f1, vid in BEATS:
        length = f1 - f0
        hold = max(0.0, round(LEAD + voice[vid] + GAP - length, 3))
        beats.append({"f0": f0, "f1": f1, "voice": vid, "c0": round(c, 3), "c1": round(c + length + hold, 3),
                      "hold": hold})
        c += length + hold
    intro = max(2.4, round(INTRO_AT + voice[INTRO_LINE] + 0.25, 2))
    end = max(5.0, round(END_AT + voice[END_LINE] + 1.8, 2))
    terminal = round(c, 3)
    end_start = intro + terminal
    # Every line of the narration: when its beat begins, when the line starts, how long it lasts.
    narration = [{"voice": INTRO_LINE, "beat": 0.0, "at": INTRO_AT, "length": voice[INTRO_LINE]}]
    narration += [{"voice": b["voice"], "beat": round(intro + b["c0"], 3), "at": round(intro + b["c0"] + LEAD, 3),
                   "length": voice[b["voice"]]} for b in beats]
    narration.append({"voice": END_LINE, "beat": round(end_start, 3), "at": round(end_start + END_AT, 3),
                      "length": voice[END_LINE]})
    return {"lead": LEAD, "intro": intro, "terminal": terminal, "end": end, "beats": beats,
            "narration": narration}


def ffmpeg_command(schedule):
    parts, labels = [], []
    for i, b in enumerate(schedule["beats"]):
        parts.append("[0:v]trim=start=%s:end=%s,setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration=%s[v%d]"
                     % (b["f0"], b["f1"], b["hold"], i))
        labels.append("[v%d]" % i)
    graph = ";".join(parts) + ";" + "".join(labels) + "concat=n=%d:v=1:a=0[out]" % len(labels)
    return [FFMPEG, "-v", "error", "-y", "-i", FOOTAGE, "-filter_complex", graph, "-map", "[out]", "-r", "30",
            "-c:v", "libx264", "-crf", "14", "-preset", "fast", "-pix_fmt", "yuv420p", TIMED]


def main(argv):
    dry = "--dry-run" in argv[1:]
    check_beats()
    with open(SPEC) as f:
        ids = [line["id"] for line in json.load(f)["lines"]]
    missing = sorted(({vid for _, _, vid in BEATS} | {INTRO_LINE, END_LINE}) - set(ids))
    if missing:
        sys.exit("schedule.py: voice/spec.json has no line %s" % ", ".join(missing))
    voice = {vid: seconds(os.path.join(VOICE_DIR, vid + ".mp3")) for vid in ids}
    schedule = plan(voice)
    cmd = ffmpeg_command(schedule)
    if dry:
        print(json.dumps(schedule, indent=1))
        print(" ".join(cmd))
        if not os.path.isfile(FOOTAGE):
            print("schedule.py: %s is missing (vhs demo.tape)" % rel(FOOTAGE))
        return 0
    footage, needed = seconds(FOOTAGE), BEATS[-1][1]
    if footage < needed:
        sys.exit("schedule.py: %s lasts %.2f s, and the beats run to %.2f s; record it again (vhs demo.tape)"
                 % (rel(FOOTAGE), footage, needed))
    os.makedirs(os.path.dirname(TIMED), exist_ok=True)
    rc = subprocess.run(cmd, stdin=subprocess.DEVNULL, timeout=600).returncode
    if rc != 0:
        # A partial file next to the old schedule.json would pair new footage with old timings.
        if os.path.exists(TIMED):
            os.remove(TIMED)
        print("schedule.py: ffmpeg failed (exit status %d); %s was removed and %s was not written"
              % (rc, rel(TIMED), rel(SCHEDULE)), file=sys.stderr)
        return rc
    got = seconds(TIMED)
    if abs(got - schedule["terminal"]) > TOLERANCE:
        os.remove(TIMED)
        sys.exit("schedule.py: the fitted footage lasted %.2f s instead of %.2f s; it was removed, and %s was"
                 " not written" % (got, schedule["terminal"], rel(SCHEDULE)))
    with open(SCHEDULE + ".tmp", "w") as f:
        json.dump(schedule, f, indent=1)
        f.write("\n")
    os.replace(SCHEDULE + ".tmp", SCHEDULE)
    print("schedule.py: %s (%.2f s) and %s" % (rel(TIMED), got, rel(SCHEDULE)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
