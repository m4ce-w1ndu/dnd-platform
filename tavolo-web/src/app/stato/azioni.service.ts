import { Injectable, inject } from '@angular/core';

import { ApiService } from '../api/api.service';
import type { Mostro, Personaggio } from '../api/avventura';
import type { Pedina } from '../api/generati/Pedina';
import type { PedinaIn } from '../api/generati/PedinaIn';
import { UiService } from '../core/ui.service';
import { d20, modoDi } from '../util/dadi';
import { type Punto, cellaPx, postoLibero, posPedina } from '../util/geometria';
import { TavoloStore } from './tavolo.store';

/** Stato della scheda di un personaggio (salvato dal server in `schede`). */
export interface StatoScheda {
  pf: number;
  pft: number;
  slot: Record<string, number>;
  usi: Record<string, number>;
  note: string;
}

/** Azioni di gioco usate da più pannelli (dadi, iniziativa, pedine, schede). */
@Injectable({ providedIn: 'root' })
export class AzioniService {
  private readonly api = inject(ApiService);
  private readonly store = inject(TavoloStore);
  private readonly ui = inject(UiService);
  private pendenti: (Punto & { r: number; t: number })[] = [];

  /** Tira un'espressione; su telefono chiude il pannello laterale per mostrare i dadi. */
  async tiro(espr: string, etichetta = '', opz: { segreto?: boolean; danni?: string | null; chiudi?: boolean } = {}) {
    const r = await this.api.op({ op: 'tira', espr, etichetta, segreto: !!opz.segreto, danni: opz.danni ?? null, modo: modoDi(espr) });
    if (innerWidth < 860 && opz.chiudi !== false) this.store.pannelloAperto.set(false);
    return r;
  }

  d20(bonus: number): string {
    return d20(bonus, this.store.vantaggio());
  }

  async iniziativaPedina(p: Pedina): Promise<void> {
    let bonus = 0;
    if (p.pg) bonus = this.store.personaggi().get(p.pg)?.iniz ?? 0;
    else if (p.mostro) bonus = this.store.mostri().get(p.mostro)?.des ?? 0;
    const segreto = this.store.master() && !!p.nascosta;
    const r = await this.tiro(this.d20(bonus), `${p.nome} · Iniziativa`, { segreto });
    if (r.ok && r.tiro) {
      await this.api.op({ op: 'iniziativa', azione: 'aggiungi', nome: p.nome, valore: r.tiro.totale, pedina: p.id, colore: p.colore ?? null, nascosta: !!p.nascosta });
    }
  }

  async iniziativaLibera(nome: string, bonus: number, colore?: string): Promise<void> {
    const r = await this.tiro(this.d20(bonus), `${nome} · Iniziativa`);
    if (r.ok && r.tiro) await this.api.op({ op: 'iniziativa', azione: 'aggiungi', nome, valore: r.tiro.totale, colore: colore ?? null });
  }

  /** Il Master aggiunge tutti i mostri della mappa che non sono già in iniziativa. */
  async iniziativaMostri(): Promise<void> {
    const gia = new Set(this.store.iniziativa().ordine.map((x) => x.pedina));
    for (const p of this.store.pedineScena().filter((p) => !p.pg && !gia.has(p.id))) await this.iniziativaPedina(p);
  }

  /** Nuova pedina vicino al centro della vista, in un posto libero. */
  nuovaPedina(d: PedinaIn, centro: Punto): void {
    const m = this.store.mappa();
    const cel = cellaPx(m);
    const t = d.taglia ?? 1;
    const ora = performance.now();
    this.pendenti = this.pendenti.filter((q) => ora - q.t < 3000);
    const occupate = [...this.store.pedineScena().map((p) => ({ ...posPedina(p, m), r: ((p.taglia || 1) * cel) / 2 })), ...this.pendenti];
    const pos = postoLibero(centro, t, occupate, m);
    this.pendenti.push({ ...pos, r: (t * cel) / 2, t: ora });
    void this.api.op({
      op: 'pedina_salva',
      pedina: { taglia: 1, condizioni: [], scena: this.store.stato()?.scena ?? null, nascosta: this.store.nascostiNuovi(), ...d, x: pos.x, y: pos.y },
    });
  }

  aggiungiMostro(m: Mostro, centro: Punto): void {
    const stessi = this.store.pedineScena().filter((p) => p.mostro === m.id).length;
    this.nuovaPedina(
      {
        nome: stessi ? `${m.nome} ${stessi + 1}` : m.nome,
        icona: m.icona ?? null,
        colore: m.colore ?? null,
        pf: m.pf,
        pfmax: m.pf,
        ca: m.ca,
        taglia: m.taglia || 1,
        tipo: m.alleato ? 'alleato' : 'mostro',
        mostro: m.id,
      },
      centro,
    );
  }

  salvaPedina(p: Pedina, diff: Partial<Pedina>): void {
    const nuova = { ...p, ...diff };
    this.store.aggiornaPedina(nuova);
    void this.api.op({ op: 'pedina_salva', pedina: nuova as PedinaIn });
  }

  statoScheda(p: Personaggio): StatoScheda {
    const s = (this.store.stato()?.schede[p.id] ?? {}) as Partial<StatoScheda>;
    return { pf: typeof s.pf === 'number' ? s.pf : p.pf, pft: s.pft || 0, slot: s.slot || {}, usi: s.usi || {}, note: s.note || '' };
  }

  salvaScheda(p: Personaggio, diff: Partial<StatoScheda>): void {
    const s = { ...this.statoScheda(p), ...diff };
    this.store.aggiornaScheda(p.id, s as unknown as Record<string, unknown>);
    void this.api.op({ op: 'scheda', id: p.id, scheda: s as unknown as Record<string, never> });
  }

  async scegliPersonaggio(pg: string): Promise<boolean> {
    const r = await this.api.op({ op: 'scegli_pg', pg });
    if (r.ok) {
      this.store.impostaMioPersonaggio(pg);
      this.ui.toast(`✅ Giocherai con ${this.store.personaggi().get(pg)?.nome ?? pg}!`);
    }
    return r.ok;
  }
}
