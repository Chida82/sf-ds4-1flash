export type Rect = { x: number; y: number; w: number; h: number };

/** Squarified treemap: `items` sized by `v`, laid out to fill a W×H box. */
export const treemap = (items: { id: string; v: number }[], W: number, H: number): Record<string, Rect> => {
  const out: Record<string, Rect> = {};
  const total = items.reduce((n, i) => n + i.v, 0);
  let rest = [...items].sort((a, b) => b.v - a.v).map((i) => ({ id: i.id, a: (i.v * W * H) / total }));
  let r: Rect = { x: 0, y: 0, w: W, h: H };
  const sum = (row: { a: number }[]) => row.reduce((n, i) => n + i.a, 0);
  const worst = (row: { a: number }[], side: number) => {
    const s = sum(row);
    const mx = Math.max(...row.map((i) => i.a)), mn = Math.min(...row.map((i) => i.a));
    return Math.max((side * side * mx) / (s * s), (s * s) / (side * side * mn));
  };
  while (rest.length) {
    const side = Math.min(r.w, r.h);
    const row = [rest[0]];
    let k = 1;
    while (k < rest.length && worst([...row, rest[k]], side) <= worst(row, side)) row.push(rest[k++]);
    rest = rest.slice(row.length);
    const s = sum(row);
    if (r.w >= r.h) {
      const cw = s / r.h;
      let y = r.y;
      for (const i of row) { const h = i.a / cw; out[i.id] = { x: r.x, y, w: cw, h }; y += h; }
      r = { x: r.x + cw, y: r.y, w: r.w - cw, h: r.h };
    } else {
      const rh = s / r.w;
      let x = r.x;
      for (const i of row) { const w = i.a / rh; out[i.id] = { x, y: r.y, w, h: rh }; x += w; }
      r = { x: r.x, y: r.y + rh, w: r.w, h: r.h - rh };
    }
  }
  return out;
};
