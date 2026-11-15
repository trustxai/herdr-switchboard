import React from "react";
import { Composition } from "remotion";
import { Demo, FPS, TOTAL_SECONDS } from "./Demo";

export const Root = () => (
  <Composition
    id="Demo"
    component={Demo}
    durationInFrames={Math.round(TOTAL_SECONDS * FPS)}
    fps={FPS}
    width={1920}
    height={1080}
  />
);
