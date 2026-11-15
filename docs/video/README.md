# The demo video

These are the sources of the demo video: 33.6 seconds at 1920×1080 and 30 fps, with narration,
made from `bin/switchboard --demo` over the bundled sample data. Nothing here is needed to use or
test the plugin. CI only byte-compiles and lints the three Python scripts (`make lint`).

The rendered files are not kept in the repository: everything the commands below download or
write is ignored by git (see `.gitignore`).

## The pieces

| File | What it does |
| --- | --- |
| `demo.tape` | [VHS](https://github.com/charmbracelet/vhs) script. It runs `bin/switchboard --demo` from the root of the repository, off camera, waits for the list, then records 25 seconds of keys and pauses into `out/terminal.mp4` at 3600×1760 and 15 fps. The video shows it at half size, so the camera zooms stay sharp. At 30 fps VHS dropped frames, even at 1920×930, and the file came out shorter than the tape's real time. |
| `voice/spec.json` | The narration: one line per beat, plus the intro and the end card, with the ElevenLabs model and voice settings. The voice itself is not in the file (see below). |
| `el.py` | ElevenLabs client, standard library only. `el.py batch` writes one MP3 per line to `remotion/public/voice/`, passing each line its neighbours so the intonation carries across files. |
| `schedule.py` | Measures each line with `ffprobe` and fits the footage to it: every beat is cut out of `out/terminal.mp4` and its last frame is held until the line has had room (`trim`, `tpad`, `concat`). Writes `remotion/src/voice.json`, `remotion/src/schedule.json` and `remotion/public/terminal-timed.mp4`. `--dry-run` prints the schedule and the ffmpeg command and writes nothing. |
| `remotion/` | [Remotion](https://www.remotion.dev) project (`src/Demo.jsx`): the intro, the terminal window, one camera move per beat, the highlight boxes, the captions, the end card and the narration, read from `schedule.json`. |
| `check.py` | The checks on the result (see [Checking the result](#checking-the-result)). |

The last step, ffmpeg's `loudnorm`, has no file of its own: it is one command.

## What you need

The versions are the ones the published video was made with.

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
- **`ELEVENLABS_VOICE_ID` is required.** The published video uses the voice of the person who
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

# 3. The footage fitted to the narration: remotion/src/voice.json, remotion/src/schedule.json
#    and remotion/public/terminal-timed.mp4.
python3 schedule.py

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

`python3 check.py all` runs the four checks below on `out/terminal.mp4` and
`out/switchboard-demo.mp4`, prints what each measured, and exits with 1 when one fails. Each
also takes a file of your choice: `python3 check.py narration other.mp4`. The figures in
brackets are those of the published video.

- **`footage`: the VHS output lasts as long as the tape.** It adds up the visible part of
  `demo.tape` (each `Sleep`, and one typing delay per typed character and per key) and compares
  it with the length of `out/terminal.mp4`, within 0.15 s. [25.16 s against 25.17 s.] A shorter
  file means VHS dropped frames: the same tape at 1920×930 and 30 fps came out at 24.76 s. Every
  beat in `schedule.py` is a time in that file, so lower the frame rate or the size and record
  again before going on.
- **`sheet`: a contact sheet to look at.** `out/sheet.png` holds a frame from the middle of the
  intro, of each beat and of the end card. Check that every caption sits over the action it
  names, that the highlight boxes frame the right rows, and that no zoom cuts a row in half.
- **`narration`: every line starts after its beat and none overlaps the next.** ffmpeg's
  `silencedetect` (-40 dB, 0.1 s) finds the speech; each line must start after its beat begins
  and end before the next line is due, from `schedule.json`. [All eight lines; the closest is
  the first beat's line, which ends 0.75 s before the next one is due.] When a line is longer
  than its beat allows, it runs into the next one and both are reported.
- **`loudness`: -16 LUFS.** ffmpeg's `ebur128`: integrated loudness within 1 LU of -16 LUFS and
  a true peak of -1 dBTP at most. [-16.4 LUFS and -1.5 dBTP; the render before step 5 is at
  -22.5 LUFS.]

## Changing the video

- **What happens on screen:** edit `demo.tape`, then the `BEATS` of `schedule.py` (times in
  `out/terminal.mp4`; the comments in the tape give them) and, in `remotion/src/Demo.jsx`, the
  entries of `SHOTS`, `BOX_DEFS` and `CAPTION_TEXT`, one per beat.
- **What is said:** edit `voice/spec.json` and run steps 2 to 6 again. Each beat stretches to
  fit its line, so nothing else has to change.

## Licences

- **Remotion** is free to use for individuals, non-profit organisations and for-profit companies
  of up to three employees. Anyone else needs a Remotion company licence to render this project:
  see [remotion.dev/license](https://www.remotion.dev/license).
- **ElevenLabs:** what `el.py` generates is subject to the terms of the ElevenLabs plan used to
  generate it. Use a plan whose terms allow what you do with the audio, such as publishing it
  or using it commercially.
