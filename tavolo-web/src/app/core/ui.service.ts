import { Injectable, signal } from '@angular/core';

export interface OpzioniDialogo {
  titolo?: string;
  icona?: string;
  ok?: string;
  annulla?: string;
  pericolo?: boolean;
  soloOk?: boolean;
}

export interface Dialogo extends OpzioniDialogo {
  testo: string;
  risolvi: (ok: boolean) => void;
}

/** Finestre di conferma, avvisi e messaggi brevi (al posto di confirm()/alert()). */
@Injectable({ providedIn: 'root' })
export class UiService {
  readonly dialogo = signal<Dialogo | null>(null);
  readonly toasts = signal<{ id: number; testo: string }[]>([]);
  private n = 0;

  conferma(testo: string, opz: OpzioniDialogo = {}): Promise<boolean> {
    return new Promise((risolvi) => {
      this.dialogo()?.risolvi(false);
      this.dialogo.set({ ...opz, testo, risolvi: (ok) => { this.dialogo.set(null); risolvi(ok); } });
    });
  }

  avviso(testo: string, opz: OpzioniDialogo = {}): Promise<boolean> {
    return this.conferma(testo, { titolo: 'Attenzione', icona: '⚠️', ok: 'Ok', ...opz, soloOk: true });
  }

  toast(testo: string): void {
    const id = ++this.n;
    this.toasts.update((l) => [...l, { id, testo }]);
    setTimeout(() => this.toasts.update((l) => l.filter((t) => t.id !== id)), 3200);
  }
}
