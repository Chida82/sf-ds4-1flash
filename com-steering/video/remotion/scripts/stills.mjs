// Renders PNG stills of chosen slides to out/stills/, in one bundle, to check scenes by eye.
//   npm run stills -- S4.1@0.3 S4.1@0.9 S6.1        (id@fraction of the slide; default 0.85)
// @remotion/bundler, @remotion/renderer and esbuild are transitive deps of @remotion/cli.
import { build } from "esbuild";
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import { mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("..", import.meta.url));
const built = await build({ entryPoints: [`${root}src/timeline.ts`], bundle: true, platform: "node", format: "esm", jsx: "automatic", write: false, logLevel: "error" });
const { segments } = await import(`data:text/javascript;base64,${Buffer.from(built.outputFiles[0].text).toString("base64")}`);

const specs = process.argv.slice(2);
if (specs.length === 0) throw new Error("usage: npm run stills -- <slideId>[@fraction] ...");
const serveUrl = await bundle({ entryPoint: `${root}src/index.ts`, publicDir: `${root}public` });
const composition = await selectComposition({ serveUrl, id: "Candor" });
mkdirSync(`${root}out/stills`, { recursive: true });
for (const spec of specs) {
  const [id, fr = "0.85"] = spec.split("@");
  const s = segments.find((x) => x.id === id);
  if (!s) throw new Error(`no slide ${id}`);
  const frame = s.from + Math.min(s.frames - 1, Math.round(s.frames * Number(fr)));
  const output = `${root}out/stills/${id}@${fr}.png`;
  await renderStill({ composition, serveUrl, output, frame });
  console.log(`still ${id}@${fr} → frame ${frame}`);
}
