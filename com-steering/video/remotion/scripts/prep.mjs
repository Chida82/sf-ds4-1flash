// Turns ../NARRATION.md into src/narration.generated.json: per scene, one chunk per
// `###` slide section. Chunk length drives slide duration; a chunk containing [STOP]
// is a presenter stop. Lines starting with `#` or `>` (slide names, on-slide text and
// its translation) are for the presenter and are not counted. Editing the narration
// re-times the video.
import { readFileSync, writeFileSync } from "node:fs";

const WPM = 150;
const md = readFileSync(new URL("../../NARRATION.md", import.meta.url), "utf8");
const body = md.split(/^## Controlli prima di registrare/m)[0];
const heads = [...body.matchAll(/^## (S\d+)\. (.*?)\s*$/gm)];

const scenes = heads.map((h, i) => {
  const start = h.index + h[0].length;
  const end = i + 1 < heads.length ? heads[i + 1].index : body.length;
  const parts = body.slice(start, end).split(/^### /m).slice(1);
  const chunks = parts.map((p) => {
    const [first, ...rest] = p.split("\n");
    const raw = rest.filter((l) => !/^\s*[>#]/.test(l) && !/^---\s*$/.test(l)).join("\n");
    const text = raw.replace("[STOP]", "").replace(/\*\*/g, "").replace(/\s+/g, " ").trim();
    return { slide: first.split(" ")[0], name: first.replace(/^\S+ · /, ""), text, words: text.split(" ").filter(Boolean).length, stop: raw.includes("[STOP]") };
  });
  return { id: h[1], title: h[2], chunks };
});

if (scenes.length === 0) throw new Error("no scenes parsed from NARRATION.md");
writeFileSync(new URL("../src/narration.generated.json", import.meta.url), JSON.stringify({ scenes }, null, 1));

let words = 0;
for (const s of scenes) {
  const w = s.chunks.reduce((n, c) => n + c.words, 0);
  words += w;
  console.log(`${s.id.padEnd(4)} ${String(w).padStart(4)} words  ~${(w / WPM).toFixed(1)} min  ${s.title}`);
}
console.log(`prep: ${scenes.length} scenes, ${scenes.reduce((n, s) => n + s.chunks.length, 0)} slides, ${words} words, ~${(words / WPM).toFixed(1)} min at ${WPM} wpm`);
