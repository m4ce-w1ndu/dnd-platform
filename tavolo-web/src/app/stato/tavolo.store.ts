import { Injectable, computed, signal } from '@angular/core';

import type { Avventura, Mappa, Mostro, Personaggio, VoceLog, VoceTiro } from '../api/avventura';
import type { Evento } from '../api/generati/Evento';
import type { Info } from '../api/generati/Info';
import type { Pedina } from '../api/generati/Pedina';
import type { StatoPer } from '../api/generati/StatoPer';
import type { VoceIniziativa } from '../api/generati/VoceIniziativa';
import type { Vantaggio } from '../util/dadi';
import { MAPPA_VUOTA, type Punto, grigliaDi, posPedina } from '../util/geometria';

export type Strumento = 'muovi' | 'righello' | 'ping' | 'nebbia';
export type Scheda = 'dadi' | 'scheda' | 'iniziativa' | 'gruppo' | 'master' | 'impostazioni';
export interface Vista {
  x: number;
  y: number;
  z: number;
}
export interface Righello {
  punti: Punto[];
  colore: string;
}
export interface Ping extends Punto {
  id: number;
  colore: string;
  chi: string;
}

const MAX_LOG = 400;

/**
 * Lo stato del tavolo nel browser. Una sola fonte di verità (`stato`, come arriva da /api/stato) aggiornata
 * dagli eventi SSE; tutto il resto è derivato con `computed`, così i componenti si ridisegnano da soli.
 */
@Injectable({ providedIn: 'root' })
export class TavoloStore {
  // ------------------------------------------------------------------ dal server
  readonly info = signal<Info | null>(null);
  readonly stato = signal<StatoPer | null>(null);
  readonly connessione = signal<'' | 'ok' | 'ko'>('');

  // ------------------------------------------------------------------ solo locale
  readonly vista = signal<Vista>({ x: 0, y: 0, z: 1 });
  readonly strumento = signal<Strumento>('muovi');
  readonly scheda = signal<Scheda>('dadi');
  readonly pannelloAperto = signal(false);
  readonly sel = signal<string | null>(null);
  readonly schedaScelta = signal<string | null>(null);
  readonly vantaggio = signal<Vantaggio>('');
  readonly nebbiaModo = signal<'rivela' | 'copri'>('rivela');
  readonly nebbiaForma = signal<'1' | '3' | '5' | 'rett'>('1');
  readonly anteprimaNebbia = signal<ReadonlySet<string> | null>(null);
  readonly righelli = signal<Record<string, Righello>>({});
  readonly pings = signal<Ping[]>([]);
  readonly lancio = signal<VoceTiro | null>(null);
  readonly avvisoTurno = signal<{ testo: string; mio: boolean; n: number } | null>(null);
  /** Pedina che sto trascinando: il server non la ridisegna sotto il mio dito. */
  readonly trascino = signal<{ id: string; pos: Punto; partenza: Punto } | null>(null);
  readonly nascostiNuovi = signal(false);
  /** Richiesta di centrare la vista su un punto (ping «mostra a tutti», clic sull'iniziativa): la mappa la osserva. */
  readonly centra = signal<{ x: number; y: number; n: number } | null>(null);

  // ------------------------------------------------------------------ derivati
  readonly io = computed(() => this.stato()?.io ?? null);
  readonly master = computed(() => this.io()?.role === 'master');
  /** Amministratore del tavolo: apre il tavolo e sceglie il Master (non l'account di sistema). */
  readonly adminTavolo = computed(() => !!this.io()?.admin && !this.io()?.sistema);
  readonly sistema = computed(() => !!this.io()?.sistema);
  readonly sessione = computed(() => this.stato()?.sessione ?? 'chiusa');
  readonly avv = computed<Avventura>(() => this.stato()?.avv ?? { id: null, titolo: 'Nessuna avventura', mappe: [], personaggi: [], mostri: [], documenti: [] });
  readonly personaggi = computed(() => new Map<string, Personaggio>(this.avv().personaggi.map((p) => [p.id, p])));
  readonly mostri = computed(() => new Map<string, Mostro>(this.avv().mostri.map((m) => [m.id, m])));
  readonly mappa = computed<Mappa>(() => {
    const mappe = this.avv().mappe;
    return mappe.find((m) => m.id === this.stato()?.scena) ?? mappe[0] ?? MAPPA_VUOTA;
  });
  readonly griglia = computed(() => grigliaDi(this.mappa()));
  readonly pedineScena = computed(() => {
    const st = this.stato();
    if (!st) return [];
    return Object.values(st.pedine).filter((p): p is Pedina => !!p && p.scena === st.scena);
  });
  readonly online = computed(() => this.stato()?.online ?? []);
  readonly iniziativa = computed(() => this.stato()?.iniziativa ?? { ordine: [], turno: 0, round: 1 });
  readonly turnoCorrente = computed<VoceIniziativa | undefined>(() => {
    const ini = this.iniziativa();
    return ini.ordine[ini.turno];
  });
  readonly log = computed(() => (this.stato()?.log ?? []) as VoceLog[]);
  readonly nebbia = computed(() => this.stato()?.nebbia[this.stato()?.scena ?? ''] ?? null);
  readonly ilMaster = computed(() => this.online().find((u) => u.role === 'master'));
  /** Il personaggio della scheda mostrata: il proprio per i giocatori, a scelta per il Master. */
  readonly schedaVista = computed<string | null>(() => {
    const pg = this.personaggi();
    if (!this.master()) {
      const c = this.io()?.char;
      return c && pg.has(c) ? c : null;
    }
    const s = this.schedaScelta();
    return s && pg.has(s) ? s : ([...pg.keys()][0] ?? null);
  });

  // ------------------------------------------------------------------ regole lato client (solo per la UI: decide il server)
  puoMuovere(p: Pedina): boolean {
    const io = this.io();
    if (!io) return false;
    return io.role === 'master' || p.proprietario === io.id || (!!p.pg && p.pg === io.char);
  }

  posizione(p: Pedina): Punto {
    const t = this.trascino();
    return t && t.id === p.id ? t.pos : posPedina(p, this.mappa());
  }

  // ------------------------------------------------------------------ aggiornamenti
  imposta(st: StatoPer): void {
    this.stato.set(st);
  }

  private modifica(f: (st: StatoPer) => StatoPer): void {
    const st = this.stato();
    if (st) this.stato.set(f(st));
  }

  /** Applica un evento SSE «di dati». Restituisce l'eventuale voce di iniziativa che è appena diventata di turno. */
  applica(ev: Evento): VoceIniziativa | undefined {
    switch (ev.t) {
      case 'pedina': {
        const io = this.io();
        if (this.trascino()?.id === ev.pedina.id && ev.da === io?.id) return undefined;
        this.modifica((st) => ({ ...st, pedine: { ...st.pedine, [ev.pedina.id]: ev.pedina } }));
        return undefined;
      }
      case 'pedina_via':
        this.modifica((st) => {
          const pedine = { ...st.pedine };
          delete pedine[ev.id];
          return { ...st, pedine };
        });
        if (this.sel() === ev.id) this.sel.set(null);
        return undefined;
      case 'log':
        this.modifica((st) => ({ ...st, log: [...st.log, ev.voce].slice(-MAX_LOG) }));
        return undefined;
      case 'scena':
        this.modifica((st) => ({ ...st, scena: ev.id }));
        this.sel.set(null);
        return undefined;
      case 'nebbia':
        this.modifica((st) => ({ ...st, nebbia: { ...st.nebbia, [ev.scena]: ev.nebbia } }));
        return undefined;
      case 'iniziativa': {
        const prima = this.turnoCorrente()?.id;
        this.modifica((st) => ({ ...st, iniziativa: ev.iniziativa }));
        const ora = this.turnoCorrente();
        return ora && ora.id !== prima ? ora : undefined;
      }
      case 'scheda':
        this.modifica((st) => ({ ...st, schede: { ...st.schede, [ev.id]: ev.scheda } }));
        return undefined;
      case 'online': {
        // l'elenco dice anche qual è il mio personaggio (es. scelto da un'altra scheda)
        const io = this.io();
        const io2 = ev.online.find((u) => u.id === io?.id);
        this.modifica((st) => ({ ...st, online: ev.online, io: io2 ? { ...st.io, char: io2.char, role: io2.role } : st.io }));
        return undefined;
      }
      case 'righello':
        this.righelli.update((r) => {
          const n = { ...r };
          if (ev.punti) n[ev.da] = { punti: ev.punti, colore: ev.colore };
          else delete n[ev.da];
          return n;
        });
        return undefined;
      default:
        return undefined;
    }
  }

  /** Modifica locale ottimistica di una pedina (il server confermerà con un evento). */
  aggiornaPedina(p: Pedina): void {
    this.modifica((st) => ({ ...st, pedine: { ...st.pedine, [p.id]: p } }));
  }

  /** Modifica locale della nebbia (anteprima confermata). */
  aggiornaNebbia(scena: string, celle: string[]): void {
    this.modifica((st) => {
      const nb = st.nebbia[scena];
      return nb ? { ...st, nebbia: { ...st.nebbia, [scena]: { ...nb, celle } } } : st;
    });
  }

  /** Il proprio personaggio è cambiato (il server lo comunica a tutti solo nell'elenco «online»). */
  impostaMioPersonaggio(pg: string | null): void {
    this.modifica((st) => ({ ...st, io: { ...st.io, char: pg } }));
  }

  aggiornaScheda(id: string, scheda: Record<string, unknown>): void {
    this.modifica((st) => ({ ...st, schede: { ...st.schede, [id]: scheda } }));
  }

  private nPing = 0;
  aggiungiPing(p: Omit<Ping, 'id'>): void {
    const id = ++this.nPing;
    this.pings.update((l) => [...l, { ...p, id }]);
    setTimeout(() => this.pings.update((l) => l.filter((x) => x.id !== id)), 2600);
  }
}
