import { Injectable, signal } from '@angular/core';

/** Credenziali salvate nel browser (stessa chiave del vecchio client: chi era già entrato resta dentro). */
export interface Credenziali {
  id: string;
  secret: string;
  nome?: string;
  ruolo?: string;
  personaggio?: string | null;
  colore?: string;
  oauth?: boolean;
}

const CHIAVE = 'tv_cred';

@Injectable({ providedIn: 'root' })
export class CredService {
  readonly cred = signal<Credenziali | null>(leggi());

  imposta(c: Credenziali | null): void {
    this.cred.set(c);
    try {
      if (c) localStorage.setItem(CHIAVE, JSON.stringify(c));
      else localStorage.removeItem(CHIAVE);
    } catch {
      /* archiviazione non disponibile (finestra anonima): si resta collegati solo in questa pagina */
    }
  }

  aggiorna(diff: Partial<Credenziali>): void {
    const c = this.cred();
    if (c) this.imposta({ ...c, ...diff });
  }

  /** Parametri `c`/`s` per GET, SSE e download. */
  query(): string {
    const c = this.cred();
    return c ? `c=${encodeURIComponent(c.id)}&s=${encodeURIComponent(c.secret)}` : '';
  }
}

function leggi(): Credenziali | null {
  try {
    const v = JSON.parse(localStorage.getItem(CHIAVE) || 'null') as Credenziali | null;
    return v && typeof v.id === 'string' && typeof v.secret === 'string' ? v : null;
  } catch {
    return null;
  }
}
