#!/usr/bin/env python3
"""The narration of the demo video, from ElevenLabs. Standard library only.

  el.py batch [SPEC] [OUTDIR]   one MP3 per line of SPEC (default voice/spec.json), written to
                                OUTDIR/<id>.mp3 (default remotion/public/voice)
  el.py voices                  the voices the account can use, to pick ELEVENLABS_VOICE_ID
  el.py models                  the models that can do text to speech
  el.py user                    the plan and the characters left this period

The API key is read from ~/.config/elevenlabs/api_key and is never printed. The voice is
ELEVENLABS_VOICE_ID, which `batch` requires: it is not in the spec, because the voice of the
launch video belongs to whoever recorded it. Relative paths are taken from docs/video, so
the script works from any directory.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
API = "https://api.elevenlabs.io"
KEY_FILE = os.path.expanduser("~/.config/elevenlabs/api_key")
VOICE_ENV = "ELEVENLABS_VOICE_ID"


def key():
    try:
        with open(KEY_FILE) as f:
            value = f.read().strip()
    except OSError as e:
        sys.exit("el.py: cannot read the API key from %s (%s)" % (KEY_FILE, e.strerror))
    if not value:
        sys.exit("el.py: %s is empty" % KEY_FILE)
    return value


def call(method, path, body=None, accept="application/json"):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method)
    req.add_header("xi-api-key", key())
    req.add_header("User-Agent", "switchboard-video/1.0")
    req.add_header("Accept", accept)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        sys.exit("el.py: HTTP %d on %s: %s" % (e.code, path, e.read()[:400].decode(errors="replace")))
    except urllib.error.URLError as e:
        sys.exit("el.py: %s: %s" % (path, e.reason))


def here(path):
    return path if os.path.isabs(path) else os.path.join(HERE, path)


def batch(spec_path, outdir):
    voice = os.environ.get(VOICE_ENV, "").strip()
    if not voice:
        sys.exit("el.py: set %s to the id of the voice to use (`el.py voices` lists them)" % VOICE_ENV)
    with open(spec_path) as f:
        spec = json.load(f)
    os.makedirs(outdir, exist_ok=True)
    endpoint = "/v1/text-to-speech/%s?output_format=mp3_44100_128" % urllib.parse.quote(voice, safe="")
    lines = spec["lines"]
    for i, line in enumerate(lines):
        body = {"text": line["text"], "model_id": spec["model"], "voice_settings": spec["settings"]}
        # The neighbouring lines keep the intonation continuous across the separate files.
        if i > 0:
            body["previous_text"] = lines[i - 1]["text"]
        if i + 1 < len(lines):
            body["next_text"] = lines[i + 1]["text"]
        audio = call("POST", endpoint, body, accept="audio/mpeg")
        path = os.path.join(outdir, line["id"] + ".mp3")
        with open(path, "wb") as f:
            f.write(audio)
        print("%s: %d bytes" % (os.path.relpath(path, HERE), len(audio)))


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "batch":
        batch(here(argv[2] if len(argv) > 2 else os.path.join("voice", "spec.json")),
              here(argv[3] if len(argv) > 3 else os.path.join("remotion", "public", "voice")))
    elif cmd == "voices":
        for v in json.loads(call("GET", "/v2/voices?page_size=100")).get("voices", []):
            labels = v.get("labels") or {}
            print("%s  %-28s %-12s %s" % (v["voice_id"], (v.get("name") or "")[:28], v.get("category") or "",
                                         "/".join(str(labels.get(k, "")) for k in ("gender", "age", "accent"))))
    elif cmd == "models":
        for m in json.loads(call("GET", "/v1/models")):
            if m.get("can_do_text_to_speech"):
                print("%-32s %s, %d languages" % (m["model_id"], m.get("name"), len(m.get("languages") or [])))
    elif cmd == "user":
        s = json.loads(call("GET", "/v1/user/subscription"))
        print({k: s.get(k) for k in ("tier", "character_count", "character_limit", "status",
                                     "next_character_count_reset_unix")})
    else:
        sys.exit(__doc__.strip())


if __name__ == "__main__":
    main(sys.argv)
