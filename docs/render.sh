#!/bin/sh
# Regenerate the README images from the demo mode:
#
#   docs/render.sh                 writes docs/assets/hero.png and docs/assets/demo.gif
#   docs/render.sh --frames DIR    also copies every intermediate frame to DIR, to look at
#
# How: `bin/switchboard --demo`, the real interface over the sample data in
# demo/fixtures.json, runs in a tmux server of its own. Keys go in with `tmux send-keys`;
# each screen is captured with its colours (`tmux capture-pane -e`) once it has stopped
# changing; docs/ansi2html.py draws it as a terminal window in HTML; headless Chrome takes
# the screenshot; ImageMagick trims it and assembles the GIF.
#
# Needs python3 (3.9+), fzf 0.71+, tmux, Google Chrome or Chromium (or CHROME=/path), and
# ImageMagick (`convert`). It does not need herdr, ssh or the network: Chrome's resolver
# is pointed at nothing. It leaves nothing behind: the tmux server and its socket, the demo's
# run and state directories, Chrome's profile and every intermediate file live in one
# temporary directory, removed on exit whatever happens, and the demo is closed with Esc and
# waited for, so it removes its own files.
#
# Every child runs with an empty environment plus PATH, a throwaway HOME and a UTF-8
# locale, so no personal configuration (a Switchboard config.toml, a tmux.conf, a Chrome
# profile) can change what the images show. The saved machines are read only once, and a
# session that runs into the sample timeline's change on this machine is redone, so the list
# cannot change between two frames; each frame is otherwise exactly what the popup draws, and
# the script checks the counts in its header.
set -eu

ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/docs/assets"
COLS=144       # wide enough for the whole header line
HERO_ROWS=44   # every status and a terminal row above, a preview that fills the half below
GIF_ROWS=34    # the animation's previews are shorter: no empty half screen in every frame
FRAMES_TO=""
if [ "${1:-}" = "--frames" ]; then
  [ -n "${2:-}" ] || { echo "usage: docs/render.sh [--frames DIR]" >&2; exit 2; }
  FRAMES_TO=$2
fi

die() { echo "render: $*" >&2; exit 1; }

for tool in tmux python3 convert fzf; do
  command -v "$tool" >/dev/null 2>&1 || die "$tool is not installed"
done
fzf_version=$(fzf --version | sed -n 's/^\([0-9][0-9]*\)\.\([0-9][0-9]*\).*/\1 \2/p')
[ -n "$fzf_version" ] || die "cannot read the fzf version"
# shellcheck disable=SC2086
set -- $fzf_version
{ [ "$1" -gt 0 ] || [ "$2" -ge 71 ]; } || die "fzf $1.$2 is too old: 0.71 or newer is needed"
CHROME=${CHROME:-}
if [ -z "$CHROME" ]; then
  for c in google-chrome google-chrome-stable chromium chromium-browser \
           "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"; do
    if command -v "$c" >/dev/null 2>&1; then CHROME=$c; break; fi
  done
fi
[ -n "$CHROME" ] || die "Chrome or Chromium not found (set CHROME=/path/to/chrome)"
case $(uname -s) in Darwin) LOCALE=en_US.UTF-8 ;; *) LOCALE=C.UTF-8 ;; esac

# /tmp, not $TMPDIR: the tmux socket path must stay under the 104-byte limit of macOS.
WORK=$(mktemp -d /tmp/switchboard-render.XXXXXX)
SOCK="$WORK/tmux.sock"
mkdir "$WORK/home" "$WORK/frames" "$WORK/run"

clean() {
  env -i PATH="$PATH" HOME="$WORK/home" TMPDIR="$WORK" TERM=xterm-256color \
    LANG="$LOCALE" LC_ALL="$LOCALE" "$@"
}
tm() { clean tmux -S "$SOCK" "$@"; }

cleanup() {
  status=$?
  trap - EXIT
  if [ -S "$SOCK" ]; then
    # Esc first, so a demo still open closes its popup and removes its run directory.
    tm send-keys -t sb Escape >/dev/null 2>&1 || true
    demo_gone >/dev/null 2>&1 || true
    tm kill-server >/dev/null 2>&1 || true
  fi
  pkill -f -- "--user-data-dir=$WORK/chrome" 2>/dev/null || true
  rm -rf "$WORK"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT TERM

screen() { tm capture-pane -p -t sb; }

# Wait until the screen matches $1 (grep -E) and is the same in two captures in a row.
settle() {
  last=""
  i=0
  while [ $i -lt 100 ]; do
    now=$(screen)
    if [ "$now" = "$last" ] && printf '%s\n' "$now" | grep -E -q -- "$1"; then
      return 0
    fi
    last=$now
    i=$((i + 1))
    sleep 0.2
  done
  printf '%s\n' "$now" >&2
  die "the screen never showed /$1/"
}

# The selected row: the only one fzf paints with a background (SGR 4x).
ESC=$(printf '\033')
selected() { tm capture-pane -p -e -t sb | grep -E "$ESC\\[(4[0-7]|48;)" | head -n 1; }

# The sample data before its timeline moves: what every frame of the list must show.
COUNTS='18 agents · 3 blocked · 3 done · 5 working'

grab() {   # grab NAME [--list]; with --list, fails when the counts above are not on screen
  tm capture-pane -p -e -N -t sb > "$WORK/frames/$1.ansi"
  [ "${2:-}" != "--list" ] || grep -q -- "$COUNTS" "$WORK/frames/$1.ansi"
}

# Move the cursor down until the selected row contains $1.
select_row() {
  n=0
  until selected | grep -q -- "$1"; do
    n=$((n + 1))
    [ $n -le 30 ] || die "could not select the row with $1"
    tm send-keys -t sb Down
    sleep 0.2
  done
}

cat > "$WORK/tmux.conf" <<'EOF'
set -g status off
set -g default-terminal "screen-256color"
set -g remain-on-exit on
EOF

# A prompt line, then the demo, then nothing: the pane stays up for the last frame. The saved
# machines are read once (the sample timeline changes one of them after 8 s); this machine
# keeps its default 1 s refresh, and its own change comes after 16 s: a session that takes
# longer is retried (see attempt). The popup's run directory goes inside $WORK too.
DEMO_CMD="printf '\$ bin/switchboard --demo\\n'; \
SWITCHBOARD_REMOTE_EVERY=3600 SWITCHBOARD_RUN_ROOT='$WORK/run' python3 '$ROOT/bin/switchboard' --demo; \
sleep 3600"

# start_demo ROWS: a fresh demo in a terminal of COLS x ROWS.
ROWS=""
start_demo() {
  if [ -S "$SOCK" ] && [ "$ROWS" = "$1" ]; then
    tm respawn-pane -k -t sb "$DEMO_CMD"
  else
    if [ -S "$SOCK" ]; then
      # The pane only holds `sleep` by now (the demo has exited). tmux does not remove a -S
      # socket when it stops, so wait for the server and then remove the file.
      tm kill-server
      i=0
      while tm has-session -t sb 2>/dev/null; do
        i=$((i + 1))
        [ $i -le 50 ] || die "the tmux server did not stop"
        sleep 0.1
      done
      rm -f "$SOCK"
    fi
    ROWS=$1
    tm -f "$WORK/tmux.conf" new-session -d -s sb -x $COLS -y "$ROWS" "$DEMO_CMD"
  fi
  # Complete once every machine has answered: the header no longer says "loading".
  settle "$COUNTS .*esc close"
}

# Wait until the demo process has exited and the pane is back to its `sleep`. The screen
# clears as soon as fzf exits, but the demo still has to remove its run directory: killing it
# before then would leave that directory behind.
demo_gone() {
  i=0
  while [ "$(tm display-message -p -t sb '#{pane_current_command}')" != "sleep" ]; do
    i=$((i + 1))
    [ $i -le 100 ] || return 1
    sleep 0.1
  done
}

# Esc closes the popup, and the demo removes its own run directory on the way out.
close_demo() {
  tm send-keys -t sb Escape
  demo_gone || die "the demo did not exit after Esc"
}

# Run a capture session; if the list changed under it, close the demo and run it again.
attempt() {
  for n in 1 2 3; do
    if "$1"; then return 0; fi
    echo "render: the sample timeline moved during $1, trying again" >&2
    close_demo
  done
  die "$1 failed three times"
}

# The hero: the whole list, with a blocked agent selected; its preview (an agent asking to
# run a command) fills the lower half.
hero() {
  start_demo $HERO_ROWS
  select_row 'flaky-checkout-test'
  settle 'Do you want to proceed\?'
  grab hero --list || return 1
  close_demo
}

# The animation: open, filter by machine, move so the preview changes, copy, Enter.
animation() {
  start_demo $GIF_ROWS
  settle 'I reviewed the rate limiter'
  grab 1-open --list || return 1
  tm send-keys -t sb -l 'workstation'
  settle '❯ workstation .* 8/23'
  grab 2-filter --list || return 1
  select_row 'landing-page-copy'
  settle 'tighter hero section'
  grab 3-move --list || return 1
  tm send-keys -t sb C-y
  settle 'copied: the last reply'
  grab 4-copy --list || return 1
  tm send-keys -t sb Enter
  settle 'demo: the demo never jumps'
  grab 5-enter
  demo_gone || die "the demo did not exit after Enter"
}

attempt hero
attempt animation

# Every character on screen must exist in the font the pages use, or Chrome draws a box.
if command -v fc-list >/dev/null 2>&1; then
  missing=$(python3 -I - "$WORK"/frames/*.ansi <<'EOF'
import re, subprocess, sys
chars = set()
for path in sys.argv[1:]:
    with open(path, encoding="utf-8") as f:
        chars |= {c for c in re.sub(r"\x1b\[[0-9;:]*[A-Za-z]", "", f.read()) if ord(c) > 126}
for c in sorted(chars):
    fams = subprocess.run(["fc-list", ":charset=%x" % ord(c), "family"],
                          capture_output=True, universal_newlines=True).stdout
    if "DejaVu Sans Mono" not in fams and "Noto Sans Mono" not in fams:
        print("U+%04X" % ord(c))
EOF
)
  [ -z "$missing" ] || die "the font has no glyph for: $missing"
fi

# --- frames to pictures ---------------------------------------------------------------------

shoot() {   # shoot NAME SCALE MARGIN ROWS
  python3 -I "$ROOT/docs/ansi2html.py" "$WORK/frames/$1.ansi" --cols $COLS --rows "$4" \
    --title 'switchboard (demo data)' > "$WORK/frames/$1.html"
  clean "$CHROME" --headless=new --disable-gpu --hide-scrollbars --no-first-run \
    --no-default-browser-check --disable-extensions --disable-sync --disable-component-update \
    --disable-background-networking --disable-default-apps --disable-crash-reporter \
    --host-resolver-rules='MAP * ~NOTFOUND' --user-data-dir="$WORK/chrome" \
    --force-device-scale-factor="$2" --window-size=1500,1150 \
    --screenshot="$WORK/frames/$1.raw.png" "file://$WORK/frames/$1.html" >/dev/null 2>&1 || true
  [ -s "$WORK/frames/$1.raw.png" ] || die "Chrome wrote no screenshot for $1"
  # Down to the window, then an even margin of the page colour around it.
  convert "$WORK/frames/$1.raw.png" -trim +repage -bordercolor '#3b4261' \
    -border "$3" -strip "$WORK/frames/$1.png"
}

shoot hero 2 40 $HERO_ROWS
convert "$WORK/frames/hero.png" -dither None -colors 256 -define png:compression-level=9 \
  -strip PNG8:"$WORK/frames/hero.small.png"
# The GIF at 1.5x: sharper than 1x once GitHub scales it down, and still well under 1 MB.
for f in 1-open 2-filter 3-move 4-copy 5-enter; do shoot "$f" 1.5 30 $GIF_ROWS; done
sizes=$(cd "$WORK/frames" && identify -format '%wx%h\n' 1-open.png 2-filter.png 3-move.png \
  4-copy.png 5-enter.png | sort -u | wc -l)
[ "$sizes" -eq 1 ] || die "the GIF frames do not all have the same size"
convert -dither None -loop 0 \
  -delay 250 "$WORK/frames/1-open.png" \
  -delay 220 "$WORK/frames/2-filter.png" \
  -delay 220 "$WORK/frames/3-move.png" \
  -delay 220 "$WORK/frames/4-copy.png" \
  -delay 400 "$WORK/frames/5-enter.png" \
  -layers Optimize -strip "$WORK/frames/demo.gif"

mkdir -p "$OUT"
cp "$WORK/frames/hero.small.png" "$OUT/hero.png"
cp "$WORK/frames/demo.gif" "$OUT/demo.gif"
if [ -n "$FRAMES_TO" ]; then
  mkdir -p "$FRAMES_TO"
  cp "$WORK"/frames/* "$FRAMES_TO"/
fi
for f in "$OUT/hero.png" "$OUT/demo.gif"; do
  echo "render: ${f#"$ROOT"/} $(wc -c < "$f" | tr -d ' ') bytes"
done
