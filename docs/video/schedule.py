#!/usr/bin/env python3
"""Fit the terminal footage to the narration: each beat lasts at least as long as its line.

Measures every line of voice/spec.json with ffprobe (remotion/public/voice/<id>.mp3, from
`el.py batch`) and writes:

  remotion/src/voice.json            the length of each line, in seconds
  remotion/src/schedule.json         the timeline the composition reads (remotion/src/Demo.jsx)
  remotion/public/terminal-timed.mp4 out/terminal.mp4 (from `vhs demo.tape`) cut into beats,
                                     each followed by a hold of its last frame long enough for
                                     its line

Times in the schedule are seconds of the timed footage. ffmpeg and ffprobe come from PATH, or
from FFMPEG and FFPROBE. Relative paths are taken from docs/video, so the script works from any
directory. `--dry-run` measures the lines and prints the schedule and the ffmpeg command
without writing anything.
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
SRC = os.path.join(HERE, "remotion", "src")
FFMPEG = os.environ.get("FFMPEG", "ffmpeg")
FFPROBE = os.environ.get("FFPROBE", "ffprobe")

# A line starts LEAD seconds into its beat, and GAP seconds of silence follow it at least.
LEAD, GAP = 0.15, 0.3

# Beats in seconds of the original footage (the comments in demo.tape), with their line. Each
# ends just before the next key of the tape, so the frame its hold repeats is a still one.
BEATS = [
    (0.0, 3.4, "v1-list"),
    (3.4, 7.4, "v2-preview"),
    (7.4, 11.7, "v3-live"),
    (11.7, 16.4, "v4-filter"),
    (16.4, 19.7, "v5-copy"),
    (19.7, 21.6, "v6-enter"),
]
INTRO_LINE, END_LINE = "v0-intro", "v7-end"


def seconds(path):
    if not os.path.isfile(path):
        sys.exit("schedule.py: %s is missing" % os.path.relpath(path, HERE))
    out = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        sys.exit("schedule.py: ffprobe failed on %s: %s" % (os.path.relpath(path, HERE), out.stderr.strip()))
    return round(float(out.stdout.strip()), 2)


def plan(voice):
    beats, c = [], 0.0
    for f0, f1, vid in BEATS:
        length = f1 - f0
        hold = max(0.0, round(LEAD + voice[vid] + GAP - length, 3))
        beats.append({"f0": f0, "f1": f1, "voice": vid, "c0": round(c, 3), "c1": round(c + length + hold, 3),
                      "hold": hold})
        c += length + hold
    intro = max(2.4, round(0.25 + voice[INTRO_LINE] + 0.25, 2))
    end = max(5.0, round(0.5 + voice[END_LINE] + 1.8, 2))
    return {"lead": LEAD, "intro": intro, "terminal": round(c, 3), "end": end, "beats": beats}


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
    with open(SPEC) as f:
        ids = [line["id"] for line in json.load(f)["lines"]]
    voice = {vid: seconds(os.path.join(VOICE_DIR, vid + ".mp3")) for vid in ids}
    schedule = plan(voice)
    cmd = ffmpeg_command(schedule)
    if dry:
        print(json.dumps({"voice": voice, "schedule": schedule}, indent=1))
        print(" ".join(cmd))
        if not os.path.isfile(FOOTAGE):
            print("schedule.py: %s is missing (vhs demo.tape)" % os.path.relpath(FOOTAGE, HERE))
        return 0
    seconds(FOOTAGE)  # exits with a message when the footage is missing or unreadable
    for name, data in (("voice.json", voice), ("schedule.json", schedule)):
        with open(os.path.join(SRC, name), "w") as f:
            json.dump(data, f, indent=1)
    os.makedirs(os.path.dirname(TIMED), exist_ok=True)
    rc = subprocess.run(cmd, stdin=subprocess.DEVNULL, timeout=600).returncode
    if rc == 0:
        print("schedule.py: %s, %.2f s of footage" % (os.path.relpath(TIMED, HERE), schedule["terminal"]))
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
