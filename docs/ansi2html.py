"""Turn one `tmux capture-pane -e` frame into an HTML page that looks like a terminal window.

    python3 docs/ansi2html.py FRAME.ansi --cols 144 --rows 44 --title TEXT > frame.html

Used by docs/render.sh. Standard library only (Python 3.9+). It understands the SGR codes
fzf and the demo emit: reset, bold, dim, italic, underline, reverse, the 16 palette colours
in both their 30-37/90-97 and 38;5 forms, 256 colours and truecolor. Every other escape
sequence is dropped. The palette is fixed so the images look the same wherever they are
rendered; the font is DejaVu Sans Mono (Noto Sans Mono as a fallback), and nothing in the
demo needs an emoji font.
"""
import argparse
import html
import re

# A dark palette: black, red, green, yellow, blue, magenta, cyan, white, then the bright ones.
PALETTE = ["#45475a", "#f38ba8", "#a6e3a1", "#f9e2af", "#89b4fa", "#cba6f7", "#94e2d5", "#bac2de",
           "#6c7086", "#f38ba8", "#a6e3a1", "#f9e2af", "#89b4fa", "#cba6f7", "#94e2d5", "#cdd6f4"]
FG, BG = "#cdd6f4", "#1e1e2e"
PAGE, BAR, TITLE = "#3b4261", "#181825", "#a6adc8"

SGR = re.compile(r"\x1b\[([0-9;:]*)m")
OTHER_ESCAPES = re.compile(r"\x1b\[[0-9;:?<=>]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b.")


def color256(n):
    if n < 16:
        return PALETTE[n]
    if n < 232:
        n -= 16
        steps = [0, 95, 135, 175, 215, 255]
        return "#%02x%02x%02x" % (steps[n // 36], steps[n // 6 % 6], steps[n % 6])
    g = 8 + (n - 232) * 10
    return "#%02x%02x%02x" % (g, g, g)


def mix(a, b, t):
    """a moved toward b by t (0..1): how dim text is drawn."""
    pa = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    pb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(pa, pb))


def apply_sgr(state, params):
    ps = [int(p) if p.isdigit() else 0 for p in re.split(r"[;:]", params)] if params else [0]
    i = 0
    while i < len(ps):
        p = ps[i]
        if p == 0:
            state.clear()
        elif p in (1, 2, 3, 4, 7):
            state[{1: "bold", 2: "dim", 3: "italic", 4: "underline", 7: "reverse"}[p]] = True
        elif p == 22:
            state.pop("bold", None)
            state.pop("dim", None)
        elif p in (23, 24, 27):
            state.pop({23: "italic", 24: "underline", 27: "reverse"}[p], None)
        elif 30 <= p <= 37 or 90 <= p <= 97:
            state["fg"] = PALETTE[p - 30 if p < 90 else p - 82]
        elif 40 <= p <= 47 or 100 <= p <= 107:
            state["bg"] = PALETTE[p - 40 if p < 100 else p - 92]
        elif p == 39:
            state.pop("fg", None)
        elif p == 49:
            state.pop("bg", None)
        elif p in (38, 48) and i + 1 < len(ps):
            key = "fg" if p == 38 else "bg"
            if ps[i + 1] == 5 and i + 2 < len(ps):
                state[key] = color256(ps[i + 2])
                i += 2
            elif ps[i + 1] == 2 and i + 4 < len(ps):
                state[key] = "#%02x%02x%02x" % tuple(min(255, v) for v in ps[i + 2:i + 5])
                i += 4
        i += 1


def style(state):
    fg, bg = state.get("fg", FG), state.get("bg")
    if state.get("reverse"):
        fg, bg = (bg or BG), fg
    if state.get("dim"):
        fg = mix(fg, bg or BG, 0.45)
    css = ["color:" + fg]
    if bg:
        css.append("background:" + bg)
    if state.get("bold"):
        css.append("font-weight:700")
    if state.get("italic"):
        css.append("font-style:italic")
    if state.get("underline"):
        css.append("text-decoration:underline")
    return ";".join(css)


def convert(text, rows=0):
    """The frame as one <div> per line, each run of equal attributes a <span>, padded with
    empty lines to `rows` so every frame of a GIF has the same height."""
    state, lines = {}, []
    raw_lines = text[:-1].split("\n") if text.endswith("\n") else text.split("\n")
    raw_lines += [""] * (rows - len(raw_lines))
    for raw in raw_lines:
        out, pos = [], 0
        for m in SGR.finditer(raw):
            chunk = OTHER_ESCAPES.sub("", raw[pos:m.start()])
            if chunk:
                out.append('<span style="%s">%s</span>' % (style(state), html.escape(chunk)))
            apply_sgr(state, m.group(1))
            pos = m.end()
        chunk = OTHER_ESCAPES.sub("", raw[pos:])
        if chunk:
            out.append('<span style="%s">%s</span>' % (style(state), html.escape(chunk)))
        lines.append('<div class="l">%s</div>' % "".join(out))
    return "\n".join(lines)


def page(body, title, cols):
    return """<!doctype html>
<meta charset="utf-8">
<style>
html, body { margin: 0; background: %(page)s; }
.win { display: inline-block; margin: 40px; border-radius: 12px; overflow: hidden;
       background: %(bg)s; box-shadow: 0 14px 40px rgba(0, 0, 0, .45); }
.bar { position: relative; height: 34px; background: %(bar)s; display: flex;
       align-items: center; justify-content: center; }
.bar i { position: absolute; top: 11px; width: 12px; height: 12px; border-radius: 50%%; }
.bar b { color: %(title)s; font: 13px/1 "DejaVu Sans", "Noto Sans", sans-serif; }
.term { padding: 12px 16px 14px; width: %(cols)dch;
        font: 15px "DejaVu Sans Mono", "Noto Sans Mono", monospace; color: %(fg)s; }
.l { height: 20px; line-height: 20px; white-space: pre; overflow: hidden; }
.l > span { display: inline-block; height: 20px; vertical-align: top; }
</style>
<div class="win"><div class="bar"><i style="left:14px;background:#f38ba8"></i><i style="left:34px;background:#f9e2af"></i><i style="left:54px;background:#a6e3a1"></i><b>%(name)s</b></div>
<div class="term">
%(body)s
</div></div>
""" % {"page": PAGE, "bg": BG, "bar": BAR, "title": TITLE, "fg": FG, "cols": cols,
       "name": html.escape(title), "body": body}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("frame")
    ap.add_argument("--title", default="")
    ap.add_argument("--cols", type=int, default=144)
    ap.add_argument("--rows", type=int, default=0, help="pad the frame to this many lines")
    args = ap.parse_args()
    with open(args.frame, encoding="utf-8", errors="replace") as f:
        print(page(convert(f.read(), args.rows), args.title, args.cols))


if __name__ == "__main__":
    main()
