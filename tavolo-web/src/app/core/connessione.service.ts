import { DOCUMENT } from '@angular/common';
import { Injectable, effect, inject, signal } from '@angular/core';

import { ApiService } from '../api/api.service';
import type { VoceLog, VoceTiro } from '../api/avventura';
import type { Evento } from '../api/generati/Evento';
import type { Io } from '../api/generati/Io';
import type { VoceIniziativa } from '../api/generati/VoceIniziativa';
import { TavoloStore } from '../stato/tavolo.store';
import { CredService } from './cred.service';
import { SuoniService } from './suoni.service';
import { UiService } from './ui.service';

export const COLORI = ['#c0392b', '#e67e22', '#f1c40f', '#27ae60', '#16a085', '#2980b9', '#8e44ad', '#d35400', '#e84393', '#7f8c8d'];

/**
 * Accesso, connessione e riconnessione: carica lo stato, apre lo stream SSE, applica gli eventi.
 * Se il server viene riavviato con una versione nuova del client, la pagina si ricarica da sola.
 */
@Injectable({ providedIn: 'root' })
export class ConnessioneService {
  private readonly api = inject(ApiService);
  private readonly cred = inject(CredService);
  private readonly store = inject(TavoloStore);
  private readonly ui = inject(UiService);
  private readonly suoni = inject(SuoniService);
  private readonly doc = inject(DOCUMENT);

  /** `ingresso` finché non si è seduti al tavolo. */
  readonly schermata = signal<'ingresso' | 'tavolo'>('ingresso');
  readonly passo = signal<'login' | 'attesa'>('login');
  readonly errore = signal('');
  readonly loginAdmin = signal(false);
  readonly io = signal<Io | null>(null);

  private es: EventSource | null = null;
  private versione = '';
  private riprovaTimer: ReturnType<typeof setTimeout> | null = null;
  private riprovaAttesa = 2000;
  private tTurno: ReturnType<typeof setTimeout> | null = null;

  constructor() {
    this.api.disconnesso = () => this.esci();
    // classi sul body usate dal foglio di stile (es. il pannello della sala per i non-Master)
    effect(() => {
      const b = this.doc.body.classList;
      b.toggle('master', this.store.master());
      b.toggle('admin', this.store.adminTavolo() || this.store.sistema());
    });
    effect(() => {
      this.doc.title = `${this.store.avv().titolo || 'Tavolo'} · Tavolo Virtuale`;
    });
    setInterval(() => {
      if (this.cred.cred() && this.doc.visibilityState === 'visible') void this.controllaVersione();
    }, 60000);
  }

  async avvio(): Promise<void> {
    const info = await this.api.info();
    if (info) {
      this.store.info.set(info);
      this.versione = info.versione;
    }
    const u = new URLSearchParams(location.search);
    if (/\/admin\/?$/.test(location.pathname) || u.has('admin')) {
      // ingresso di riserva per l'amministratore: sempre disponibile
      history.replaceState(null, '', location.pathname.replace(/admin\/?$/, ''));
      this.loginAdmin.set(true);
      return;
    }
    if (u.get('accesso')) history.replaceState(null, '', location.pathname);
    const c = this.cred.cred();
    if (!c) return;
    const io = await this.api.io();
    if (!io) {
      this.cred.imposta(null);
      return;
    }
    this.io.set(io);
    const sessione = this.store.info()?.sessione;
    if (c.ruolo && !u.get('accesso') && (sessione !== 'chiusa' || io.admin)) {
      if (await this.entra({ ruolo: c.ruolo, personaggio: c.personaggio ?? null, colore: c.colore ?? io.colore }, true)) return;
    }
    await this.siediti();
  }

  async login(corpo: Record<string, unknown>): Promise<boolean> {
    this.errore.set('');
    const r = await this.api.login(corpo);
    if (!r.ok || !r.id || !r.secret) {
      this.errore.set(r.errore || 'Errore');
      void this.ui.avviso(r.errore || 'Accesso non riuscito.', { titolo: 'Accesso non riuscito', icona: '🔐' });
      return false;
    }
    this.cred.imposta({ id: r.id, secret: r.secret, nome: r.nome });
    this.io.set(await this.api.io());
    await this.siediti();
    return true;
  }

  /** Dopo l'accesso si entra nella sala d'attesa; il ruolo lo decide poi chi amministra il tavolo. */
  async siediti(): Promise<void> {
    const io = this.io();
    this.passo.set('attesa');
    await this.entra({
      ruolo: io?.master ? 'master' : 'giocatore',
      personaggio: io?.char ?? null,
      colore: io?.colore || COLORI[Math.floor(Math.random() * COLORI.length)],
    });
  }

  async entra(dati: { ruolo: string; personaggio: string | null; colore?: string }, silenzioso = false): Promise<boolean> {
    this.errore.set('');
    const r = await this.api.entra(dati);
    if (!r.ok) {
      if (r.login) {
        this.esci();
        return false;
      }
      if (!silenzioso) {
        this.errore.set(r.errore || 'Errore');
        void this.ui.avviso(r.errore || 'Non riesco a entrare.', { titolo: 'Non riesco a entrare', icona: '🚪' });
      }
      return false;
    }
    this.cred.aggiorna({ ruolo: dati.ruolo, personaggio: dati.personaggio, colore: dati.colore });
    await this.connetti();
    return true;
  }

  async connetti(): Promise<void> {
    const st = await this.api.stato();
    if (st === undefined) {
      this.riprova(); // server giù (riavvio, proxy 502…): si riprova più tardi
      return;
    }
    if (st === null) {
      this.schermata.set('ingresso');
      this.passo.set('login');
      return;
    }
    this.store.imposta(st);
    this.schermata.set('tavolo');
    this.es?.close();
    const es = new EventSource(`/api/eventi?${this.cred.query()}`);
    this.es = es;
    es.onmessage = (m: MessageEvent<string>) => {
      try {
        this.evento(JSON.parse(m.data) as Evento);
      } catch (e) {
        console.error(e);
      }
    };
    es.onopen = async () => {
      this.store.connessione.set('ok');
      await this.controllaVersione();
      await this.ricarica();
    };
    es.onerror = () => {
      this.store.connessione.set('ko');
      // se il proxy risponde con un errore (es. 502 durante un riavvio) EventSource smette di riprovare da solo
      if (es.readyState === EventSource.CLOSED) this.riprova();
    };
  }

  async ricarica(): Promise<void> {
    const st = await this.api.stato();
    if (st) this.store.imposta(st);
  }

  private riprova(): void {
    if (this.riprovaTimer) return;
    this.riprovaTimer = setTimeout(async () => {
      this.riprovaTimer = null;
      const i = await this.api.info();
      if (!i) {
        this.riprovaAttesa = Math.min(this.riprovaAttesa * 1.5, 15000);
        this.riprova();
        return;
      }
      this.riprovaAttesa = 2000;
      if (this.versione && i.versione !== this.versione) {
        location.reload();
        return;
      }
      await this.connetti();
    }, this.riprovaAttesa);
  }

  private async controllaVersione(): Promise<void> {
    const i = await this.api.info();
    if (!i) return;
    if (this.versione && i.versione && i.versione !== this.versione) {
      this.ui.toast('🔄 Il tavolo è stato aggiornato: ricarico…');
      setTimeout(() => location.reload(), 800);
    }
    this.store.info.set(i);
  }

  esci(): void {
    this.es?.close();
    this.es = null;
    this.cred.imposta(null);
    void fetch('/api/esci', { method: 'POST' }).catch(() => undefined);
    location.href = location.pathname;
  }

  private evento(ev: Evento): void {
    const turno = this.store.applica(ev);
    if (turno) this.annunciaTurno(turno);
    switch (ev.t) {
      case 'log': {
        const v = ev.voce as VoceLog;
        if (v.tipo === 'tiro') this.lancia(v);
        else if (v.tipo === 'chat' && v.da !== this.store.io()?.id) this.suoni.suona('chat');
        break;
      }
      case 'ping':
        this.store.aggiungiPing({ x: ev.x, y: ev.y, colore: ev.colore, chi: ev.chi });
        this.suoni.suona('ping');
        if (ev.centra) this.store.centra.set({ x: ev.x, y: ev.y, n: (this.store.centra()?.n ?? 0) + 1 });
        break;
      case 'catalogo':
      case 'ricarica':
      case 'sessione':
        void this.ricarica();
        break;
      case 'ruolo':
        this.cred.aggiorna({ ruolo: ev.ruolo });
        if (ev.ruolo === 'master') {
          void this.ui.avviso('Ora hai il pannello 👑 Master: mappe, mostri, nebbia di guerra e turni. Quando tutti hanno scelto il personaggio, premi «▶ Inizia la partita».', {
            titolo: 'Sei il Master!',
            icona: '👑',
            ok: 'Andiamo!',
          });
        } else this.ui.toast('Ora sei un giocatore.');
        void this.ricarica();
        break;
      case 'info':
        void this.controllaVersione();
        break;
      case 'esci':
        this.esci();
        break;
      default:
        break;
    }
  }

  private lancia(v: VoceTiro): void {
    this.store.lancio.set(v);
    const dadi = v.parti.reduce((n, p) => n + (p.tipo === 'dadi' ? p.valori.length : 0), 0);
    this.suoni.suona(v.critico ? 'critico' : 'dadi', dadi);
  }

  private annunciaTurno(x: VoceIniziativa): void {
    const io = this.store.io();
    const ped = x.pedina ? this.store.stato()?.pedine[x.pedina] : undefined;
    const mio = (!!ped && this.store.puoMuovere(ped) && !this.store.master()) || x.da === io?.id;
    if (x.nascosta && !this.store.master()) return;
    const n = (this.store.avvisoTurno()?.n ?? 0) + 1;
    this.store.avvisoTurno.set({ testo: mio ? `⚔️ Tocca a te, ${x.nome}!` : `Turno di ${x.nome}`, mio, n });
    if (this.tTurno) clearTimeout(this.tTurno);
    this.tTurno = setTimeout(() => this.store.avvisoTurno.set(null), mio ? 5000 : 2500);
    if (mio) this.suoni.suona('turno');
  }
}
