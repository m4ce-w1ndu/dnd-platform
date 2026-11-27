import { describe, expect, it } from 'vitest';

import type { Mappa } from '../api/avventura';
import type { Pedina } from '../api/generati/Pedina';
import { aggancia, celleDaPennello, celleDaRett, dimNebbia, distanzaQ, fmtDist, posPedina, postoLibero } from './geometria';

const mappa: Mappa = { id: 'm', titolo: 'M', gruppo: '', ordine: 1, file: '', larghezza: 640, altezza: 480, griglia: { cella: 32, ox: 0, oy: 0 }, inizio: [2, 3] };
const pedina = (p: Partial<Pedina>): Pedina => ({ id: 'p', x: null, y: null, nome: 'P', taglia: 1, condizioni: [], ...p });

describe('geometria', () => {
  it('aggancia al centro del quadretto (taglia dispari) o all incrocio (pari)', () => {
    expect(aggancia(40, 70, 1, mappa)).toEqual({ x: 48, y: 80 });
    expect(aggancia(40, 70, 2, mappa)).toEqual({ x: 32, y: 64 });
    expect(aggancia(40, 70, 1, { ...mappa, griglia: undefined })).toEqual({ x: 40, y: 70 });
  });

  it('pedine dei personaggi senza posizione al punto di partenza, in fila per slot', () => {
    expect(posPedina(pedina({ x: 5, y: 6 }), mappa)).toEqual({ x: 5, y: 6 });
    expect(posPedina(pedina({ slot: 0 }), mappa)).toEqual({ x: 80, y: 112 });
    expect(posPedina(pedina({ slot: 4 }), mappa)).toEqual({ x: 112, y: 144 });
  });

  it('distanze alla D&D (diagonali = 1)', () => {
    expect(distanzaQ({ x: 0, y: 0 }, { x: 96, y: 64 }, mappa)).toBe(3);
    expect(fmtDist(6)).toBe('6 q · 9 m');
  });

  it('celle della nebbia', () => {
    const d = dimNebbia(mappa)!;
    expect(d.col).toBe(20);
    expect(d.rig).toBe(15);
    expect(celleDaPennello({ x: 40, y: 40 }, 1, d)).toEqual(['1,1']);
    expect(celleDaPennello({ x: 40, y: 40 }, 3, d)).toHaveLength(9);
    expect(celleDaPennello({ x: 1, y: 1 }, 3, d)).toHaveLength(4); // tagliato al bordo
    expect(celleDaRett({ x: 70, y: 70 }, { x: 0, y: 0 }, d)).toHaveLength(9);
  });

  it('posto libero per una pedina nuova', () => {
    const c = { x: 48, y: 48 };
    expect(postoLibero(c, 1, [], mappa)).toEqual({ x: 48, y: 48 });
    const occupato = [{ x: 48, y: 48, r: 16 }];
    const p = postoLibero(c, 1, occupato, mappa);
    expect(p).not.toEqual({ x: 48, y: 48 });
    expect(Math.max(Math.abs(p.x - 48), Math.abs(p.y - 48))).toBe(32);
  });
});
