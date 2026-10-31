import React from "react";
import { Composition } from "remotion";
import { Video } from "./Video";
import { FPS, totalFrames } from "./timeline";

export const Root: React.FC = () => (
  <Composition id="Candor" component={Video} durationInFrames={totalFrames} fps={FPS} width={1920} height={1080} />
);
