import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { CredService } from '../core/cred.service';
import { UiService } from '../core/ui.service';
import type {
  ConfigPubblica,
  PartitaSalvata,
  UtenteImpostazioni,
  VoceAudit,
  VoceTiro,
} from './avventura';
import type { Info } from './generati/Info';
import type { Io } from './generati/Io';
import type { Op } from './generati/Op';
import type { StatoPer } from './generati/StatoPer';

/** Risposta comune: `ok` più, se qualcosa non va, il messaggio per l'utente. */
export interface Esito {
  ok: boolean;
  errore?: string;
  /** Codice HTTP (0 = server non raggiungibile). */
  status: number;
}

/** Campi in più nella risposta di alcuni comandi. */
interface RisposteOp {
  tira: { tiro: VoceTiro };
  pedina_salva: { id: string };
  avventura_nuova: { id: string };
  imp_leggi: { config: ConfigPubblica; utenti: UtenteImpostazioni[] };
  imp_salva: { config: ConfigPubblica };
  imp_partite: { partite: PartitaSalvata[] };
  imp_utenti_elimina: { eliminati: number };
}
export type NomeOp = Op['op'];
export type RispostaOp<K extends NomeOp> = Esito &
  (K extends keyof RisposteOp ? Partial<RisposteOp[K]> : unknown);

export interface Login {
  id: string;
  secret: string;
  nome: string;
}

/** Tutte le chiamate al server, tipizzate con i tipi generati dal codice Rust. */
@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);
  private readonly cred = inject(CredService);
  private readonly ui = inject(UiService);
  /** Chiamato quando il server dice che le credenziali non valgono più. */
  disconnesso: () => void = () => undefined;

  async info(): Promise<Info | null> {
    return this.get<Info>('/api/info');
  }

  async io(): Promise<Io | null> {
    return this.get<Io>(`/api/io?${this.cred.query()}`);
  }

  /** `undefined` = server non raggiungibile (si riprova), `null` = credenziali non valide. */
  async stato(): Promise<StatoPer | null | undefined> {
    try {
      return await firstValueFrom(this.http.get<StatoPer>(`/api/stato?${this.cred.query()}`));
    } catch (e) {
      const s = e instanceof HttpErrorResponse ? e.status : 0;
      return s === 0 || s >= 500 ? undefined : null;
    }
  }

  async login(corpo: Record<string, unknown>): Promise<Esito & Partial<Login>> {
    const c = this.cred.cred();
    return this.post('/api/login', c ? { ...corpo, id: c.id, secret: c.secret } : corpo);
  }

  async entra(dati: {
    ruolo: string;
    personaggio: string | null;
    colore?: string;
    nome?: string;
  }): Promise<Esito & { login?: boolean }> {
    const c = this.cred.cred();
    return this.post('/api/entra', { ...dati, id: c?.id, secret: c?.secret });
  }

  /** Un comando di gioco. Gli errori vengono mostrati all'utente; 401 = si torna all'accesso. */
  async op<K extends NomeOp>(
    o: Extract<Op, { op: K }>,
    opz: { silenzioso?: boolean } = {},
  ): Promise<RispostaOp<K>> {
    const r = await this.post<RispostaOp<K>>('/api/op', o);
    if (!r.ok && r.errore && !opz.silenzioso) void this.ui.avviso(r.errore.replace(/^⚠️\s*/, ''));
    if (r.status === 401) this.disconnesso();
    return r;
  }

  async importa(partita: unknown): Promise<Esito> {
    return this.post('/api/importa', partita);
  }

  /** Caricamento di un file (avventura .zip, mappa, documento). */
  async carica(url: string, file: Blob): Promise<Esito & { id?: string; titolo?: string }> {
    const r = await this.post<Esito & { id?: string; titolo?: string }>(
      `${url}${url.includes('?') ? '&' : '?'}${this.cred.query()}`,
      file,
    );
    if (!r.ok)
      void this.ui.avviso(r.errore || 'Il caricamento non è riuscito.', {
        titolo: 'Caricamento non riuscito',
      });
    return r;
  }

  async audit(): Promise<VoceAudit[]> {
    const r = await this.get<{ ok: boolean; audit: VoceAudit[] }>(
      `/api/audit?${this.cred.query()}`,
    );
    return r?.audit ?? [];
  }

  /** Link di download che usano le credenziali in query. */
  link(path: string): string {
    return `${path}${path.includes('?') ? '&' : '?'}${this.cred.query()}`;
  }

  private async get<T>(url: string): Promise<T | null> {
    try {
      return await firstValueFrom(this.http.get<T>(url));
    } catch {
      return null;
    }
  }

  private async post<T extends Esito>(url: string, corpo: unknown): Promise<T> {
    try {
      const r = await firstValueFrom(this.http.post<T>(url, corpo, { observe: 'response' }));
      return { ...(r.body as T), status: r.status };
    } catch (e) {
      if (e instanceof HttpErrorResponse) {
        const corpo = (e.error && typeof e.error === 'object' ? e.error : {}) as Partial<T>;
        const errore =
          corpo.errore ?? (e.status === 0 ? 'Server non raggiungibile' : `Errore ${e.status}`);
        return { ...corpo, ok: false, errore, status: e.status } as T;
      }
      return { ok: false, errore: 'Errore inatteso', status: 0 } as T;
    }
  }
}
