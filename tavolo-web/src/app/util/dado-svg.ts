/** Il disegno di un dado (poligono della forma giusta) come SVG. */
const FORME: Record<number, string> = {
  4: '50,6 95,88 5,88',
  6: '12,12 88,12 88,88 12,88',
  8: '50,3 94,50 50,97 6,50',
  10: '50,4 92,40 50,96 8,40',
  12: '50,4 95,36 78,92 22,92 5,36',
  20: '50,3 93,27 93,73 50,97 7,73 7,27',
  100: '50,4 92,40 50,96 8,40',
};

const COLORE_OK = /^#[0-9a-fA-F]{3,8}$/;

export function svgDado(f: number, colore = '#7a2e1c'): string {
  const c = COLORE_OK.test(colore) ? colore : '#7a2e1c';
  const venti = f === 20 ? '<polyline points="50,3 30,62 70,62 50,3" fill="none" stroke="#f6d27a55" stroke-width="3"/>' : '';
  return `<svg viewBox="0 0 100 100"><polygon points="${FORME[f] ?? FORME[6]}" fill="${c}" stroke="#f6d27a" stroke-width="5" stroke-linejoin="round"/>${venti}</svg>`;
}
