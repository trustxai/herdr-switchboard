# The demo video

These are the sources of the demo video: about 34 seconds at 1920×1080 and 30 fps, with
narration, made from `bin/switchboard --demo` over the bundled sample data. Nothing here is needed
to use or test the plugin. CI byte-compiles and lints the Python scripts, and `make test` runs
`test_video.py`, which needs neither ffmpeg nor the network.

The rendered files are not kept in the repository: everything the commands below download or
write is ignored by git (see `.gitignore`).

## The pieces

| File | What it does |
| --- | --- |
| `demo.tape` | [VHS](https://github.com/charmbracelet/vhs) script. It runs `bin/switchboard --demo` from the root of the repository, off camera, waits for the list, then records 25 seconds of keys and pauses into `out/terminal.mp4` at 3600×1760. VHS captures 15 frames per second and writes them as a 25 fps file (629 frames for 25.16 s), repeating frames. The video shows it at half size, so the camera zooms stay sharp. At a capture rate of 30, VHS dropped frames, even at 1920×930, and the file came out shorter than the tape's real time. |
| `voice/spec.json` | The narration: one line per beat, plus the intro and the end card, with the ElevenLabs model and voice settings. The voice itself is not in the file (see below). |
| `el.py` | ElevenLabs client, standard library only. `el.py batch` writes one MP3 per line to `remotion/public/voice/`, passing each line its neighbours so the intonation carries across files. |
| `schedule.py` | Measures each line with `ffprobe` and fits the footage to it: every beat (`BEATS`) is cut out of `out/terminal.mp4` and its last frame is held until the line has had room (`trim`, `tpad`, `concat`). Writes `remotion/public/terminal-timed.mp4`, then `remotion/src/schedule.json`: the beats, and when each line starts and how long it lasts. It refuses footage shorter than the beats, and writes the schedule only once the fitted footage lasts as long as the schedule says. `--dry-run` prints the schedule and the ffmpeg command and writes nothing. |
| `remotion/` | [Remotion](https://www.remotion.dev) project (`src/Demo.jsx`): the intro, the terminal window, one camera move per beat, the highlight boxes, the captions, the end card and the narration, all timed by `schedule.json`. The camera moves, boxes and captions go with the beats by position; a schedule with another number of beats stops the render with a message. |
| `check.py` | The checks on the result (see [Checking the result](#checking-the-result)). |
| `test_video.py` | Tests for the three scripts: standard library only, with a fake ElevenLabs API on 127.0.0.1. |

The last step, ffmpeg's `loudnorm`, has no file of its own: it is one command.

## What you need

The versions are the ones the launch video was made with.

| Tool | Version | For |
| --- | --- | --- |
| [VHS](https://github.com/charmbracelet/vhs) | 0.12.1 | the terminal footage |
| [ttyd](https://github.com/tsl0922/ttyd) | 1.7.7 | VHS runs the shell in it |
| Google Chrome or Chromium | any recent | VHS drives it |
| [ffmpeg and ffprobe](https://ffmpeg.org) | 8.1 | VHS, `schedule.py`, `check.py` and the loudness step |
| Python | 3.9 or newer | the demo and the scripts |
| [fzf](https://github.com/junegunn/fzf) | 0.71 or newer | the demo |
| DejaVu Sans Mono | | the terminal font |
| Node.js and npm | 22 (22.14.0) | Remotion |
| Remotion | 4.0.543 | the composition; pinned by `remotion/package-lock.json` |
| ElevenLabs API | model `eleven_v4` | the narration |

Remotion downloads its own headless Chrome the first time it renders, and the composition loads
Inter and JetBrains Mono from Google Fonts, so a render needs the network.

## Before you start

- **The ElevenLabs API key** goes in `~/.config/elevenlabs/api_key`, alone on one line, readable
  only by you (`chmod 600`). It never goes in the repository, and `el.py` never prints it.
- **`ELEVENLABS_VOICE_ID` is required.** The launch video uses the voice of the person who
  recorded it, and that voice is not part of this repository. Set it to any voice your account
  can use; `python3 el.py voices` lists them.
- **One batch uses about 335 characters** of the plan (the eight lines). `python3 el.py user`
  shows what is left.

## Commands, in order

From `docs/video`:

```sh
cd docs/video

# 1. The terminal footage, out/terminal.mp4. An empty environment with a throwaway HOME, so no
#    Switchboard config.toml or shell configuration changes what the demo shows.
env -i HOME="$(mktemp -d)" PATH="$PATH" LANG=C.UTF-8 TERM=xterm-256color vhs demo.tape
python3 check.py footage

# 2. The narration, remotion/public/voice/<id>.mp3.
export ELEVENLABS_VOICE_ID=...
python3 el.py batch

# 3. The footage fitted to the narration: remotion/public/terminal-timed.mp4, then
#    remotion/src/schedule.json.
python3 schedule.py
python3 check.py live

# 4. The composition, out/raw.mp4 (h264 and 320 kb/s AAC, Remotion's defaults).
cd remotion
npm ci
npx remotion render src/index.jsx Demo ../out/raw.mp4
cd ..

# 5. The loudness: -16 LUFS integrated, out/switchboard-demo.mp4.
ffmpeg -i out/raw.mp4 -c:v copy -af loudnorm=I=-16:TP=-1.5:LRA=11 -ar 48000 \
  -c:a aac -b:a 160k -movflags +faststart out/switchboard-demo.mp4

# 6. The checks.
python3 check.py all
```

`npx remotion studio src/index.jsx`, from `remotion/`, opens the composition in a browser to
look at it frame by frame; it needs steps 1 to 3 first, as the render does.

`schedule.py` and `check.py` take `ffmpeg` and `ffprobe` from `PATH`, or from the `FFMPEG` and
`FFPROBE` variables. All three scripts resolve their paths from `docs/video`, so they work from
any directory.

## Checking the result

`python3 check.py all` runs the five checks below on `out/terminal.mp4` and
`out/switchboard-demo.mp4`, prints what each measured, and exits with 1 when one fails. Each
also takes a file of your choice: `python3 check.py narration other.mp4`. The figures in
brackets are those of a render of these files with the launch narration.

- **`footage`: the VHS output lasts as long as the tape.** It adds up the visible part of
  `demo.tape` (each `Sleep`, and one typing delay per typed character and per key) and compares
  it with the length of `out/terminal.mp4`, within 0.15 s. [25.16 s against 25.17 s.] A shorter
  file means VHS dropped frames: the same keys at 1920×930 and 30 fps came out at 24.76 s. Every
  beat in `schedule.py` is a time in that file, so lower the frame rate or the size and record
  again before going on.
- **`live`: the live update happens inside its beat.** It finds every change of the screen in
  `out/terminal.mp4` and prints them with the key each comes from: these are the times to cut
  `BEATS` at. A key shows about 0.1 s before the sum of the tape's sleeps and delays. The first
  change no key causes is the demo's live update (a working agent turns done, 8 s after the demo
  starts); it must show at least 0.5 s after the `v3-live` beat begins and 1 s before it ends.
  [At 7.27 s, inside 5.60 to 10.00 s. It came between 7.27 and 7.40 s in four recordings: it
  counts from the demo's start, and the footage starts once the list has loaded.]
- **`sheet`: a contact sheet to look at.** `out/sheet.png` holds a frame from the middle of the
  intro, of each beat and of the end card. Check that every caption sits over the action it
  names, that the highlight boxes frame the right rows, and that no zoom cuts a row in half.
- **`narration`: every line in its own slot.** ffmpeg's `silencedetect` (-40 dB, 0.1 s) finds
  the stretches of speech. `schedule.json` gives each line a slot, from where it starts to where
  its file ends, and a stretch belongs to the line whose slot holds its start. Each line must
  start once its beat has begun and keep all its speech inside its slot. Speech outside every
  slot counts against the line it comes before: a line that starts early fails even when a
  pause after its first word makes its first stretch look like the end of the line before.
  [All eight lines; each starts within 0.04 s of the start of its slot.]
- **`loudness`: -16 LUFS.** ffmpeg's `ebur128`: integrated loudness within 1 LU of -16 LUFS and
  a true peak of -1 dBTP at most. [-16.4 LUFS and -1.5 dBTP; the render before step 5 is at
  -22.5 LUFS.]

## Changing the video

- **What happens on screen:** edit `demo.tape`, record it, and cut the `BEATS` of
  `schedule.py` at the times `python3 check.py live` prints (the tape's comments give no times).
  In `remotion/src/Demo.jsx`, `SHOT_DEFS` and `CAPTION_TEXT` need one entry per beat, and the
  `beat` of each `BOX_DEFS` entry must be one of them.
- **What is said:** edit the text of a line in `voice/spec.json` (and its caption in
  `CAPTION_TEXT`, if they should match), then run steps 2 to 6 again. Each beat stretches to fit
  its line, so the timing needs no change.
- **The tests:** `test_video.py` checks the tape's length, the keys it types and the moments the
  list updates live, with those values written into the test. A change to `demo.tape` or to the
  `BEATS` needs the same change there.

## Licences

- **Remotion** is free to use for individuals, non-profit organisations and for-profit companies
  of up to three employees. Anyone else needs a Remotion company licence to render this project:
  see [remotion.dev/license](https://www.remotion.dev/license).
- **ElevenLabs:** what `el.py` generates is subject to the terms of the ElevenLabs plan used to
  generate it. Use a plan whose terms allow what you do with the audio, such as publishing it
  or using it commercially.
