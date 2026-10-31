import React, { useEffect, useRef } from "react";
import { createRoot } from "react-dom/client";
import { Player, PlayerRef } from "@remotion/player";
import { Video } from "../src/Video";
import { FPS, segments, stopFrames, totalFrames } from "../src/timeline";

// Presenter: plays the same timeline, pauses on every [STOP] frame. Space = play/pause
// (Player default); Right / Left arrow = next slide / restart this slide, then the previous one.
const App: React.FC = () => {
  const ref = useRef<PlayerRef>(null);
  useEffect(() => {
    const p = ref.current;
    if (!p) return;
    let next = stopFrames[0] ?? Infinity;
    const arm = () => (next = stopFrames.find((s) => s > p.getCurrentFrame()) ?? Infinity);
    const onFrame = (e: { detail: { frame: number } }) => {
      if (e.detail.frame >= next) { p.pause(); p.seekTo(next); }
    };
    p.addEventListener("play", arm);
    p.addEventListener("seeked", arm);
    p.addEventListener("frameupdate", onFrame);
    const key = (e: KeyboardEvent) => {
      const f = p.getCurrentFrame();
      if (e.key === "ArrowRight") p.seekTo(segments.find((s) => s.from > f)?.from ?? totalFrames - 1);
      // Left: restart the slide you are in; within its first second, go to the previous one.
      if (e.key === "ArrowLeft") {
        const i = segments.filter((s) => s.from <= f).length - 1;
        p.seekTo(f - segments[i].from > 30 || i === 0 ? segments[i].from : segments[i - 1].from);
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);
  return (
    <div style={{ background: "#000", height: "100vh", display: "grid", placeItems: "center" }}>
      <Player ref={ref} component={Video} durationInFrames={totalFrames} fps={FPS} compositionWidth={1920} compositionHeight={1080}
        controls clickToPlay style={{ width: "100%", maxWidth: "calc(100vh * 16 / 9)" }} />
    </div>
  );
};

createRoot(document.getElementById("root")!).render(<App />);
