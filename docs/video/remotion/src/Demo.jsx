import React from "react";
import {
  AbsoluteFill,
  Audio,
  Easing,
  OffthreadVideo,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import SCHEDULE from "./schedule.json";
import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import { loadFont as loadMono } from "@remotion/google-fonts/JetBrainsMono";

const { fontFamily: SANS } = loadInter("normal", { weights: ["400", "600", "800"], subsets: ["latin"] });
const { fontFamily: MONO } = loadMono("normal", { weights: ["400", "600"], subsets: ["latin"] });

export const FPS = 30;

// Timeline, in seconds of the composition. The terminal part is the footage already fitted to
// the narration (schedule.py): every beat lasts at least as long as its line.
const INTRO = SCHEDULE.intro;
const TERMINAL = SCHEDULE.terminal;
const END_START = INTRO + TERMINAL;
const END_LENGTH = SCHEDULE.end;
export const TOTAL_SECONDS = END_START + END_LENGTH;
const B = SCHEDULE.beats; // c0, c1: seconds of the fitted footage

// Tokyo Night palette.
const C = {
  bg: "#1a1b26",
  bg2: "#24283b",
  frame: "#3b4261",
  fg: "#c0caf5",
  dim: "#a9b1d6",
  muted: "#565f89",
  purple: "#bb9af7",
  blue: "#7aa2f7",
  cyan: "#7dcfff",
  red: "#f7768e",
};

// The window that holds the terminal footage (3600x1760 video shown at half size).
const WIN = { x: 60, y: 30, w: 1800, bar: 40 };
const VIEW = { w: WIN.w, h: Math.round((WIN.w * 1760) / 3600) };

// Camera: one shot per beat (fx, fy: the point of the footage, 0..1, to centre), eased in
// over MOVE seconds from the start of the beat.
const MOVE = 0.7;
const SHOTS = [
  { s: 1.0, fx: 0.5, fy: 0.5 },
  { s: 1.25, fx: 0.4, fy: 0.5 },
  { s: 2.0, fx: 0.25, fy: 0.2 },
  { s: 1.8, fx: 0.27, fy: 0.22 },
  { s: 1.45, fx: 0.35, fy: 0.445 },
  { s: 1.0, fx: 0.5, fy: 0.5 },
].map((shot, i) => ({ ...shot, t: B[i].c0 }));

// Boxes drawn over the footage (normalized footage coordinates), per beat, from `from`
// seconds into the beat until just before it ends.
const BOX_DEFS = [
  { beat: 2, from: 1.0, x: 0.024, y: 0.103, w: 0.395, h: 0.044 },
  { beat: 4, from: 0.5, x: 0.022, y: 0.477, w: 0.532, h: 0.044 },
];
const BOXES = BOX_DEFS.map((b) => ({ ...b, t: B[b.beat].c0 + b.from, end: B[b.beat].c1 - 0.2 }));

function Key({ children }) {
  return <span style={{ fontFamily: MONO, color: C.purple, fontWeight: 600 }}>{children}</span>;
}

// Captions, one per beat, shown for the whole beat.
const CAPTION_TEXT = [
  <>Every agent on every machine, in one popup</>,
  <>Blocked first, with a live preview of each pane</>,
  <>It keeps updating while it's open</>,
  <>Type to filter by machine, project or pane</>,
  <><Key>ctrl-y</Key> copies the agent's last reply</>,
  <><Key>enter</Key> jumps to the pane, on any machine</>,
];
const CAPTIONS = CAPTION_TEXT.map((text, i) => ({ text, t: B[i].c0, end: B[i].c1 }));

const ease = Easing.inOut(Easing.cubic);

function camera(t) {
  let prev = SHOTS[0];
  for (let i = 1; i < SHOTS.length; i++) {
    const cur = SHOTS[i];
    if (t < cur.t) break;
    const k = interpolate(t, [cur.t, cur.t + MOVE], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: ease,
    });
    prev = {
      s: prev.s + (cur.s - prev.s) * k,
      fx: prev.fx + (cur.fx - prev.fx) * k,
      fy: prev.fy + (cur.fy - prev.fy) * k,
    };
  }
  const { s, fx, fy } = prev;
  const tx = Math.min(0, Math.max(VIEW.w - VIEW.w * s, VIEW.w / 2 - fx * VIEW.w * s));
  const ty = Math.min(0, Math.max(VIEW.h - VIEW.h * s, VIEW.h / 2 - fy * VIEW.h * s));
  return { s, tx, ty };
}

const Background = () => (
  <AbsoluteFill
    style={{
      background: `radial-gradient(1400px 900px at 30% 20%, ${C.bg2} 0%, ${C.bg} 70%)`,
    }}
  />
);

const Intro = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pop = spring({ frame, fps, config: { damping: 200 } });
  const sub = spring({ frame: frame - 8, fps, config: { damping: 200 } });
  const out = interpolate(frame, [INTRO * fps - 12, INTRO * fps], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", opacity: out }}>
      <div
        style={{
          fontFamily: MONO,
          fontSize: 30,
          color: C.cyan,
          letterSpacing: 2,
          opacity: sub,
          marginBottom: 18,
        }}
      >
        a herdr plugin
      </div>
      <div
        style={{
          fontFamily: SANS,
          fontWeight: 800,
          fontSize: 150,
          color: C.fg,
          letterSpacing: -4,
          transform: `translateY(${(1 - pop) * 30}px)`,
          opacity: pop,
        }}
      >
        Switchboard
      </div>
      <div
        style={{
          fontFamily: SANS,
          fontSize: 44,
          color: C.dim,
          marginTop: 22,
          opacity: sub,
          transform: `translateY(${(1 - sub) * 20}px)`,
        }}
      >
        Every agent and terminal on every machine, in one popup
      </div>
    </AbsoluteFill>
  );
};

const Terminal = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps; // seconds of footage
  const { s, tx, ty } = camera(t);
  const enter = spring({ frame, fps, config: { damping: 200 } });
  const leave = interpolate(t, [TERMINAL - 0.6, TERMINAL], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const winScale = (0.94 + 0.06 * enter) * (0.96 + 0.04 * leave);
  return (
    <AbsoluteFill style={{ opacity: Math.min(enter, leave) }}>
      <div
        style={{
          position: "absolute",
          left: WIN.x,
          top: WIN.y,
          width: WIN.w,
          height: WIN.bar + VIEW.h,
          borderRadius: 16,
          overflow: "hidden",
          background: C.bg,
          boxShadow: "0 30px 80px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.06)",
          transform: `scale(${winScale})`,
        }}
      >
        <div
          style={{
            height: WIN.bar,
            background: "#16161e",
            display: "flex",
            alignItems: "center",
            padding: "0 18px",
            gap: 10,
          }}
        >
          {["#f7768e", "#e0af68", "#9ece6a"].map((c) => (
            <div key={c} style={{ width: 14, height: 14, borderRadius: 7, background: c }} />
          ))}
          <div
            style={{
              flex: 1,
              textAlign: "center",
              fontFamily: SANS,
              fontSize: 19,
              color: C.muted,
              marginRight: 60,
            }}
          >
            switchboard (demo data)
          </div>
        </div>
        <div style={{ position: "relative", width: VIEW.w, height: VIEW.h, overflow: "hidden" }}>
          <div
            style={{
              position: "absolute",
              width: VIEW.w,
              height: VIEW.h,
              transformOrigin: "0 0",
              transform: `translate(${tx}px, ${ty}px) scale(${s})`,
            }}
          >
            <OffthreadVideo
              src={staticFile("terminal-timed.mp4")}
              style={{ width: VIEW.w, height: VIEW.h }}
              muted
            />
            {BOXES.map((b, i) => {
              const o = interpolate(t, [b.t, b.t + 0.25, b.end - 0.25, b.end], [0, 1, 1, 0], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              });
              return (
                <div
                  key={i}
                  style={{
                    position: "absolute",
                    left: b.x * VIEW.w,
                    top: b.y * VIEW.h,
                    width: b.w * VIEW.w,
                    height: b.h * VIEW.h,
                    border: `${3 / s}px solid ${C.purple}`,
                    borderRadius: 6 / s,
                    boxShadow: `0 0 ${18 / s}px rgba(187,154,247,0.45)`,
                    opacity: o,
                  }}
                />
              );
            })}
          </div>
          <EdgeFades s={s} tx={tx} ty={ty} />
        </div>
      </div>
      <Captions t={t} />
    </AbsoluteFill>
  );
};

// While zoomed, a row cut by an edge of the window fades out instead of ending in a hard line.
const EdgeFades = ({ s, tx, ty }) => {
  const SIZE = 50;
  const cut = {
    top: -ty,
    bottom: VIEW.h * s + ty - VIEW.h,
    right: VIEW.w * s + tx - VIEW.w,
    left: -tx,
  };
  const fade = (side) => Math.max(0, Math.min(1, cut[side] / 40));
  const common = { position: "absolute", pointerEvents: "none" };
  return (
    <>
      <div style={{ ...common, left: 0, right: 0, top: 0, height: SIZE, opacity: fade("top"),
        background: `linear-gradient(to bottom, ${C.bg}, rgba(26,27,38,0))` }} />
      <div style={{ ...common, left: 0, right: 0, bottom: 0, height: SIZE, opacity: fade("bottom"),
        background: `linear-gradient(to top, ${C.bg}, rgba(26,27,38,0))` }} />
      <div style={{ ...common, top: 0, bottom: 0, right: 0, width: SIZE, opacity: fade("right"),
        background: `linear-gradient(to left, ${C.bg}, rgba(26,27,38,0))` }} />
      <div style={{ ...common, top: 0, bottom: 0, left: 0, width: SIZE, opacity: fade("left"),
        background: `linear-gradient(to right, ${C.bg}, rgba(26,27,38,0))` }} />
    </>
  );
};

const Captions = ({ t }) => {
  const top = WIN.y + WIN.bar + VIEW.h;
  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        top,
        bottom: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {CAPTIONS.map((c, i) => {
        const o = interpolate(t, [c.t, c.t + 0.3, c.end - 0.25, c.end], [0, 1, 1, 0], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
        if (o <= 0) return null;
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              fontFamily: SANS,
              fontWeight: 600,
              fontSize: 50,
              color: C.fg,
              opacity: o,
              transform: `translateY(${(1 - o) * 14}px)`,
            }}
          >
            {c.text}
          </div>
        );
      })}
    </div>
  );
};

const EndCard = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const a = spring({ frame, fps, config: { damping: 200 } });
  const b = spring({ frame: frame - 8, fps, config: { damping: 200 } });
  const c = spring({ frame: frame - 16, fps, config: { damping: 200 } });
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      <div
        style={{
          fontFamily: SANS,
          fontWeight: 800,
          fontSize: 110,
          color: C.fg,
          letterSpacing: -3,
          opacity: a,
          transform: `translateY(${(1 - a) * 24}px)`,
        }}
      >
        Switchboard
      </div>
      <div
        style={{
          marginTop: 40,
          padding: "26px 44px",
          borderRadius: 16,
          background: "#16161e",
          border: `1px solid ${C.frame}`,
          fontFamily: MONO,
          fontSize: 46,
          color: C.fg,
          opacity: b,
          transform: `translateY(${(1 - b) * 18}px)`,
        }}
      >
        <span style={{ color: C.purple }}>herdr</span> plugin install trustxai/herdr-switchboard
      </div>
      <div
        style={{
          marginTop: 36,
          fontFamily: SANS,
          fontSize: 36,
          color: C.dim,
          opacity: c,
        }}
      >
        github.com/trustxai/herdr-switchboard · Apache-2.0 · Linux and macOS
      </div>
    </AbsoluteFill>
  );
};

export const Demo = () => {
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill>
      <Background />
      <Sequence durationInFrames={Math.round(INTRO * fps)}>
        <Intro />
      </Sequence>
      <Sequence from={Math.round(INTRO * fps)} durationInFrames={Math.round(TERMINAL * fps)}>
        <Terminal />
      </Sequence>
      <Sequence from={Math.round(END_START * fps)}>
        <EndCard />
      </Sequence>
      <Sequence from={Math.round(0.25 * fps)}>
        <Audio src={staticFile("voice/v0-intro.mp3")} />
      </Sequence>
      {B.map((b) => (
        <Sequence key={b.voice} from={Math.round((INTRO + b.c0 + SCHEDULE.lead) * fps)}>
          <Audio src={staticFile(`voice/${b.voice}.mp3`)} />
        </Sequence>
      ))}
      <Sequence from={Math.round((END_START + 0.5) * fps)}>
        <Audio src={staticFile("voice/v7-end.mp3")} />
      </Sequence>
    </AbsoluteFill>
  );
};
