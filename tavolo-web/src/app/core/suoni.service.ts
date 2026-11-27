import { Injectable, signal } from '@angular/core';

export type Suono = 'dadi' | 'critico' | 'ping' | 'chat' | 'turno';

/** Suoni sintetizzati con WebAudio (nessun file da scaricare). */
@Injectable({ providedIn: 'root' })
export class SuoniService {
  readonly attivi = signal(leggi());
  private ac: AudioContext | null = null;

  alterna(): void {
    this.attivi.update((v) => !v);
    try {
      localStorage.setItem('tv_suono', this.attivi() ? '1' : '0');
    } catch {
      /* niente */
    }
  }

  suona(tipo: Suono, n = 1): void {
    if (!this.attivi()) return;
    try {
      const ac = (this.ac ??= new AudioContext());
      const t0 = ac.currentTime;
      const clic = (t: number, f: number, d = 0.05, vol = 0.18, forma: OscillatorType = 'triangle') => {
        const o = ac.createOscillator();
        const g = ac.createGain();
        o.type = forma;
        o.frequency.setValueAtTime(f, t);
        o.frequency.exponentialRampToValueAtTime(f * 0.5, t + d);
        g.gain.setValueAtTime(vol, t);
        g.gain.exponentialRampToValueAtTime(0.001, t + d);
        o.connect(g).connect(ac.destination);
        o.start(t);
        o.stop(t + d + 0.02);
      };
      if (tipo === 'dadi') for (let i = 0; i < Math.min(6, 3 + n); i++) clic(t0 + i * 0.07 + Math.random() * 0.03, 600 + Math.random() * 900, 0.04, 0.12);
      if (tipo === 'critico') {
        for (let i = 0; i < 4; i++) clic(t0 + i * 0.07, 700, 0.04, 0.1);
        [523, 659, 784, 1047].forEach((f, i) => clic(t0 + 0.35 + i * 0.09, f, 0.35, 0.12, 'sine'));
      }
      if (tipo === 'ping') clic(t0, 1200, 0.25, 0.1, 'sine');
      if (tipo === 'chat') clic(t0, 900, 0.12, 0.06, 'sine');
      if (tipo === 'turno') [440, 660].forEach((f, i) => clic(t0 + i * 0.12, f, 0.3, 0.1, 'sine'));
    } catch {
      /* audio non disponibile */
    }
  }
}

function leggi(): boolean {
  try {
    return localStorage.getItem('tv_suono') !== '0';
  } catch {
    return true;
  }
}
