import { describe, expect, it } from 'vitest';

import type { Personaggio } from '../api/avventura';
import { abilita, iconaCondizione, percezionePassiva, statoSalute, tsBonus } from './scheda';

const base: Personaggio = { id: 'r', nome: 'Rocco', icona: '🛡️', razza: 'Umano', classe: 'Guerriero', ca: 19, pf: 28 };

describe('scheda', () => {
  it('scheda completa: abilità addestrate prima, le altre dalle caratteristiche', () => {
    const p: Personaggio = { ...base, car: { FOR: 16, DES: 14, COS: 15, INT: 9, SAG: 13, CAR: 11 }, comp: 2, ts: ['FOR', 'COS'], abilita: { Atletica: 5 } };
    const a = abilita(p);
    expect(a[0]).toEqual({ n: 'Atletica', c: 'FOR', b: 5, pro: true });
    expect(a.find((x) => x.n === 'Furtività')?.b).toBe(2);
    expect(tsBonus(p, 'FOR')).toBe(5);
    expect(tsBonus(p, 'DES')).toBe(2);
    expect(percezionePassiva(p)).toBe(11);
  });

  it('scheda semplificata (senza caratteristiche)', () => {
    const p: Personaggio = { ...base, abilita: { Percezione: 3 } };
    expect(abilita(p)).toEqual([{ n: 'Percezione', c: 'SAG', b: 3, pro: true }]);
    expect(percezionePassiva(p)).toBe(13);
    expect(percezionePassiva(base)).toBe(10);
  });

  it('salute e condizioni', () => {
    expect(statoSalute(0, 10)).toContain('a terra');
    expect(statoSalute(10, 10)).toContain('illeso');
    expect(iconaCondizione('Prono')).toBe('⬇️');
    expect(iconaCondizione('Boh')).toBe('•');
  });
});
