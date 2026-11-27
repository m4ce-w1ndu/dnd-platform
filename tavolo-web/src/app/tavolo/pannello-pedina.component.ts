import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';

import { ApiService } from '../api/api.service';
import type { Pedina } from '../api/generati/Pedina';
import { AzioniService } from '../stato/azioni.service';
import { TavoloStore } from '../stato/tavolo.store';
import { posPedina } from '../util/geometria';
import { CONDIZIONI, statoSalute } from '../util/scheda';
import { sg } from '../util/dadi';

/** Il riquadro della pedina selezionata: PF, condizioni, attacchi dei mostri, opzioni del Master. */
@Component({
  selector: 'app-pannello-pedina',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (p(); as p) {
      <div id="pannello-pedina" class="flottante">
        <div class="pp-testa">
          <span class="ic">{{ p.icona || '●' }}</span>
          @if (master()) {
            <input class="nome" [value]="p.nome" (change)="salva(p, { nome: valore($event) })" />
          } @else {
            <b style="flex:1;font-size:15px">{{ p.nome }}</b>
          }
          @if (p.ca) {
            <span class="chip" title="Classe Armatura">🛡️ CA {{ p.ca }}</span>
          }
          <button title="Chiudi" (click)="store.sel.set(null)">✕</button>
        </div>
        @if (p.pfmax) {
          @if (vedePf()) {
            <div class="pp-pf">
              <span class="num">{{ p.pf ?? p.pfmax }}/{{ p.pfmax }}</span>
              @if (mia()) {
                <input type="number" min="1" [value]="qta()" (input)="qta.set(+valore($event) || 0)" />
                <button class="pericolo" (click)="salva(p, { pf: max0((p.pf ?? p.pfmax) - qta()) })">− Danno</button>
                <button (click)="salva(p, { pf: min(p.pfmax, (p.pf ?? p.pfmax) + qta()) })">+ Cura</button>
              }
            </div>
          } @else {
            <div class="pp-pf"><span class="aiuto">Salute: {{ salute(p) }}</span></div>
          }
        }
        @if (mia()) {
          <div class="chips">
            @for (c of condizioni; track c[0]) {
              <button class="chip" [class.attivo]="p.condizioni.includes(c[0])" (click)="alternaCondizione(p, c[0])">{{ c[1] }} {{ c[0] }}</button>
            }
          </div>
        } @else if (p.condizioni.length) {
          <div class="chips">
            @for (c of p.condizioni; track c) {
              <span class="chip attivo">{{ c }}</span>
            }
          </div>
        }
        @if (mostro(); as m) {
          @if (master()) {
            <div class="stat-mini">
              @for (a of m.attacchi ?? []; track $index) {
                <button (click)="attacca(p, a.nome, a.bonus, a.danni)">
                  <b>{{ a.nome }}</b> {{ a.bonus != null ? sg(a.bonus) : '' }} · {{ a.danni }}<br /><small>{{ a.note || '' }}</small>
                </button>
              }
            </div>
            @for (t of m.tratti ?? []; track $index) {
              <div class="tratto">
                <b>{{ t.nome }}.</b> {{ t.testo }}
                @if (t.tiro) {
                  <button class="link" (click)="azioni.tiro(t.tiro, p.nome + ' · ' + t.nome)">tira {{ t.tiro }}</button>
                }
              </div>
            }
          }
        }
        <div class="riga" style="margin-top:8px">
          @if (mia()) {
            <button (click)="azioni.iniziativaPedina(p)">⚔️ Iniziativa</button>
          }
          @if (master()) {
            <label class="switch"><input type="checkbox" [checked]="!!p.nascosta" (change)="salva(p, { nascosta: spunta($event) })" /> nascosta</label>
            <select (change)="salva(p, { taglia: +valore($event) })">
              @for (t of taglie; track t[0]) {
                <option [value]="t[0]" [selected]="p.taglia === t[0]">{{ t[1] }}</option>
              }
            </select>
            <button (click)="mostra(p)">📍 Mostra a tutti</button>
          }
          @if ((master() || p.proprietario === store.io()?.id) && !p.pg) {
            <button class="pericolo" (click)="elimina(p)">🗑️</button>
          }
        </div>
      </div>
    }
  `,
})
export class PannelloPedinaComponent {
  protected readonly store = inject(TavoloStore);
  protected readonly azioni = inject(AzioniService);
  private readonly api = inject(ApiService);
  protected readonly condizioni = CONDIZIONI;
  protected readonly taglie: [number, string][] = [[0.5, 'Minuscola'], [1, 'Media/Piccola'], [2, 'Grande'], [3, 'Enorme'], [4, 'Mastodontica']];
  protected readonly sg = sg;
  protected readonly qta = signal(1);

  protected readonly p = computed(() => {
    const id = this.store.sel();
    return id ? (this.store.stato()?.pedine[id] ?? null) : null;
  });
  protected readonly master = this.store.master;
  protected readonly mia = computed(() => {
    const p = this.p();
    return !!p && this.store.puoMuovere(p);
  });
  protected readonly vedePf = computed(() => this.master() || this.mia() || this.p()?.tipo === 'pg');
  protected readonly mostro = computed(() => {
    const m = this.p()?.mostro;
    return m ? (this.store.mostri().get(m) ?? null) : null;
  });

  protected valore(e: Event): string {
    return (e.target as HTMLInputElement).value;
  }
  protected spunta(e: Event): boolean {
    return (e.target as HTMLInputElement).checked;
  }
  protected max0(n: number): number {
    return Math.max(0, n);
  }
  protected min(a: number, b: number): number {
    return Math.min(a, b);
  }
  protected salute(p: Pedina): string {
    return statoSalute(p.pf ?? p.pfmax ?? 0, p.pfmax ?? 1);
  }

  protected salva(p: Pedina, diff: Partial<Pedina>): void {
    this.azioni.salvaPedina(p, diff);
  }

  protected alternaCondizione(p: Pedina, c: string): void {
    const l = new Set(p.condizioni);
    if (l.has(c)) l.delete(c);
    else l.add(c);
    this.salva(p, { condizioni: [...l] });
  }

  protected attacca(p: Pedina, nome: string, bonus: number | null, danni: string): void {
    if (bonus == null) void this.azioni.tiro(danni, `${p.nome} · ${nome}`);
    else void this.azioni.tiro(`1d20${bonus >= 0 ? '+' : ''}${bonus}`, `${p.nome} · ${nome}`, { danni });
  }

  protected mostra(p: Pedina): void {
    const pos = posPedina(p, this.store.mappa());
    void this.api.op({ op: 'ping', x: pos.x, y: pos.y, centra: true });
  }

  protected elimina(p: Pedina): void {
    void this.api.op({ op: 'pedina_elimina', id: p.id });
    this.store.sel.set(null);
  }
}
