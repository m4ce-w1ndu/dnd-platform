/** Geometria della mappa: posizioni delle pedine, aggancio alla griglia, distanze, celle della nebbia. */
import type { Griglia, Mappa } from '../api/avventura';
import type { Pedina } from '../api/generati/Pedina';

export interface Punto {
  x: number;
  y: number;
}

export const MAPPA_VUOTA: Mappa = { id: 'vuota', titolo: 'Nessuna mappa', gruppo: '', ordine: 0, file: '', larghezza: 1000, altezza: 800 };

/** La griglia della mappa, se ha un quadretto valido. */
export function grigliaDi(m: Mappa): Required<Griglia> | null {
  const g = m.griglia;
  if (g && +g.cella > 0) return { cella: +g.cella, ox: +g.ox || 0, oy: +g.oy || 0, mostra: !!g.mostra };
  return null;
}

export function cellaPx(m: Mappa): number {
  return grigliaDi(m)?.cella ?? 50;
}

/** Posizione di una pedina; le pedine dei personaggi senza posizione stanno nel punto di partenza della mappa. */
export function posPedina(p: Pedina, m: Mappa): Punto {
  if (p.x != null && p.y != null) return { x: p.x, y: p.y };
  const g = grigliaDi(m);
  const cel = cellaPx(m);
  const k = p.slot ?? 0;
  let bx: number;
  let by: number;
  if (m.inizio && g) {
    bx = g.ox + (m.inizio[0] + 0.5) * g.cella;
    by = g.oy + (m.inizio[1] + 0.5) * g.cella;
  } else {
    bx = m.larghezza / 2 - cel;
    by = m.altezza / 2;
  }
  return { x: bx + (k % 3) * cel, y: by + Math.floor(k / 3) * cel };
}

/** Aggancio alla griglia: centro del quadretto per taglie dispari, incrocio per taglie pari. */
export function aggancia(x: number, y: number, taglia: number, m: Mappa): Punto {
  const g = grigliaDi(m);
  if (!g) return { x, y };
  const dispari = Math.round(taglia || 1) % 2 === 1;
  const fx = (x - g.ox) / g.cella;
  const fy = (y - g.oy) / g.cella;
  if (dispari) return { x: g.ox + (Math.floor(fx) + 0.5) * g.cella, y: g.oy + (Math.floor(fy) + 0.5) * g.cella };
  return { x: g.ox + Math.round(fx) * g.cella, y: g.oy + Math.round(fy) * g.cella };
}

/** Distanza in quadretti (regola D&D 5e: le diagonali contano 1). */
export function distanzaQ(a: Punto, b: Punto, m: Mappa): number {
  return Math.max(Math.abs(a.x - b.x), Math.abs(a.y - b.y)) / cellaPx(m);
}

export function fmtDist(q: number): string {
  return `${Math.round(q)} q · ${(Math.round(q) * 1.5).toLocaleString('it-IT')} m`;
}

export interface DimNebbia {
  g: Required<Griglia>;
  col: number;
  rig: number;
}

export function dimNebbia(m: Mappa): DimNebbia | null {
  const g = grigliaDi(m);
  if (!g) return null;
  return { g, col: Math.ceil((m.larghezza - g.ox) / g.cella), rig: Math.ceil((m.altezza - g.oy) / g.cella) };
}

export function cellaDi(p: Punto, d: DimNebbia): string {
  return `${Math.floor((p.x - d.g.ox) / d.g.cella)},${Math.floor((p.y - d.g.oy) / d.g.cella)}`;
}

/** Celle sotto un pennello rotondo di diametro `forma` quadretti. */
export function celleDaPennello(p: Punto, forma: number, d: DimNebbia): string[] {
  const cx = Math.floor((p.x - d.g.ox) / d.g.cella);
  const cy = Math.floor((p.y - d.g.oy) / d.g.cella);
  const r = Math.floor((forma || 1) / 2);
  const out: string[] = [];
  for (let i = -r; i <= r; i++) {
    for (let j = -r; j <= r; j++) {
      if (r > 0 && i * i + j * j > r * r + r) continue;
      const a = cx + i;
      const b = cy + j;
      if (a >= 0 && b >= 0 && a < d.col && b < d.rig) out.push(`${a},${b}`);
    }
  }
  return out;
}

export function celleDaRett(p1: Punto, p2: Punto, d: DimNebbia): string[] {
  const a = Math.floor((Math.min(p1.x, p2.x) - d.g.ox) / d.g.cella);
  const b = Math.floor((Math.min(p1.y, p2.y) - d.g.oy) / d.g.cella);
  const c = Math.floor((Math.max(p1.x, p2.x) - d.g.ox) / d.g.cella);
  const e = Math.floor((Math.max(p1.y, p2.y) - d.g.oy) / d.g.cella);
  const out: string[] = [];
  for (let i = Math.max(0, a); i <= Math.min(d.col - 1, c); i++) for (let j = Math.max(0, b); j <= Math.min(d.rig - 1, e); j++) out.push(`${i},${j}`);
  return out;
}

/** Primo posto libero vicino a `c` per una nuova pedina (a spirale), evitando quelle già presenti. */
export function postoLibero(c: Punto, taglia: number, occupate: (Punto & { r: number })[], m: Mappa): Punto {
  const cel = cellaPx(m);
  for (let r = 0; r < 12; r++) {
    for (let i = -r; i <= r; i++) {
      for (let j = -r; j <= r; j++) {
        if (Math.max(Math.abs(i), Math.abs(j)) !== r) continue;
        const q = aggancia(c.x + i * cel, c.y + j * cel, taglia, m);
        if (occupate.every((o) => Math.max(Math.abs(o.x - q.x), Math.abs(o.y - q.y)) >= o.r + (taglia * cel) / 2 - 1)) return q;
      }
    }
  }
  return aggancia(c.x, c.y, taglia, m);
}
