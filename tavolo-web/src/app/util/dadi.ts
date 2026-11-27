/** Composizione delle espressioni di dadi dal vassoio (il tiro vero lo fa il server). */
export type Vantaggio = '' | 'adv' | 'dis';

export const sg = (n: number): string => (n >= 0 ? `+${n}` : `−${-n}`);
export const mod = (v: number): number => Math.floor((v - 10) / 2);
const bonus = (b: number): string => (b ? (b > 0 ? `+${b}` : `${b}`) : '');

export function d20(b: number, adv: Vantaggio): string {
  const base = adv === 'adv' ? '2d20kh1' : adv === 'dis' ? '2d20kl1' : '1d20';
  return base + bonus(b);
}

/** «2d6+1d20+3» dal vassoio; un solo d20 con vantaggio diventa 2d20kh1. */
export function espressionePool(pool: Record<number, number>, modificatore: number, adv: Vantaggio): string {
  const parti = Object.entries(pool)
    .filter(([, n]) => n > 0)
    .map(([f, n]) => (+f === 20 && n === 1 && adv ? (adv === 'adv' ? '2d20kh1' : '2d20kl1') : `${n}d${f}`));
  return parti.length ? parti.join('+') + bonus(modificatore) : '';
}

export function modoDi(espr: string): string {
  return espr.includes('kh') ? 'vantaggio' : espr.includes('kl') ? 'svantaggio' : '';
}

/** Comando di chat «/r 2d6+3» (anche /roll, /tira). */
export function comandoTiro(testo: string): string | null {
  const m = testo.match(/^\/(r|roll|tira)\s+(.+)$/i);
  return m ? m[2] : null;
}
