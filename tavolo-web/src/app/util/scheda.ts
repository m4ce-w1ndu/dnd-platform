/** Calcoli della scheda del personaggio (D&D 5e). */
import type { Caratteristica, Personaggio } from '../api/avventura';
import { mod } from './dadi';

export const NOMI_CAR: Record<Caratteristica, string> = { FOR: 'Forza', DES: 'Destrezza', COS: 'Costituzione', INT: 'Intelligenza', SAG: 'Saggezza', CAR: 'Carisma' };

export const ABILITA: Record<string, Caratteristica> = {
  Acrobazia: 'DES', 'Addestrare Animali': 'SAG', Arcano: 'INT', Atletica: 'FOR', Furtività: 'DES', Indagare: 'INT', Inganno: 'CAR',
  Intimidire: 'CAR', Intrattenere: 'CAR', Intuizione: 'SAG', Medicina: 'SAG', Natura: 'INT', Percezione: 'SAG', Persuasione: 'CAR',
  'Rapidità di Mano': 'DES', Religione: 'INT', Storia: 'INT', Sopravvivenza: 'SAG',
};

export const CONDIZIONI: [string, string][] = [
  ['Prono', '⬇️'], ['Spaventato', '😱'], ['Afferrato', '✊'], ['Trattenuto', '🕸️'], ['Accecato', '🙈'], ['Avvelenato', '🤢'],
  ['Stordito', '💫'], ['Privo di sensi', '💤'], ['Concentrazione', '🧠'], ['Benedetto', '✨'], ['Marchiato', '🎯'], ['Invisibile', '👻'],
];

export function iconaCondizione(c: string): string {
  return CONDIZIONI.find((x) => x[0] === c)?.[1] ?? '•';
}

export interface Abilita {
  n: string;
  c: Caratteristica | '';
  b: number;
  pro: boolean;
}

/** Schede «semplificate» (avventure introduttive): niente punteggi di caratteristica. */
export const semplice = (p: Personaggio): boolean => !p.car;

export function tsBonus(p: Personaggio, k: Caratteristica): number {
  return mod(p.car?.[k] ?? 10) + ((p.ts ?? []).includes(k) ? (p.comp ?? 0) : 0);
}

export function abilita(p: Personaggio): Abilita[] {
  const addestrate = p.abilita ?? {};
  if (!p.car) return Object.entries(addestrate).map(([n, b]) => ({ n, c: ABILITA[n] ?? '', b, pro: true }));
  const car = p.car;
  return Object.entries(ABILITA)
    .map(([n, c]) => {
      const pro = n in addestrate;
      return { n, c, b: pro ? addestrate[n] : mod(car[c]) + (p.factotum ?? 0), pro };
    })
    .sort((a, b) => Number(b.pro) - Number(a.pro) || a.n.localeCompare(b.n));
}

export function percezionePassiva(p: Personaggio): number {
  return 10 + (p.abilita?.['Percezione'] ?? (p.car ? mod(p.car.SAG) : 0));
}

export function statoSalute(pf: number, pfmax: number): string {
  const r = pf / pfmax;
  if (r <= 0) return '💀 a terra';
  if (r <= 0.25) return '🩸 gravemente ferito';
  if (r <= 0.5) return '🤕 ferito';
  if (r < 1) return '😤 graffiato';
  return '💪 illeso';
}
