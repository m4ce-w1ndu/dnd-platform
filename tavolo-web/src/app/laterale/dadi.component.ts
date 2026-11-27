import { ChangeDetectionStrategy, Component, ElementRef, computed, effect, inject, signal, viewChild } from '@angular/core';
import { DomSanitizer } from '@angular/platform-browser';
import { FormsModule } from '@angular/forms';

import { ApiService } from '../api/api.service';
import type { ParteTiro, VoceLog } from '../api/avventura';
import { AzioniService } from '../stato/azioni.service';
import { TavoloStore } from '../stato/tavolo.store';
import { comandoTiro, espressionePool, sg } from '../util/dadi';
import { svgDado } from '../util/dado-svg';

/** Vassoio dei dadi, cronologia dei tiri e chat. */
@Component({
  selector: 'app-dadi',
  imports: [FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="vassoio">
      <div class="dadi-bottoni">
        @for (d of dadiBottoni; track d.f) {
          <button [title]="'Aggiungi un d' + d.f + ' (clic destro: tira subito)'" (click)="aggiungi(d.f)" (contextmenu)="subito($event, d.f)"><span [innerHTML]="d.svg"></span>d{{ d.f }}</button>
        }
      </div>
      <div class="pool">
        <div class="pool-espr" [class.vuoto]="!espressione()">{{ espressione() || 'Clicca i dadi · TIRA senza dadi = ' + azioni.d20(mod()) }}</div>
        <div class="pool-mod">
          <button (click)="mod.set(mod() - 1)">−</button><span>{{ sg(mod()) }}</span><button (click)="mod.set(mod() + 1)">+</button>
        </div>
      </div>
      <div class="riga">
        <div class="gruppo-btn adv">
          <button title="Svantaggio: tira 2d20 e tieni il più basso" [class.attivo]="store.vantaggio() === 'dis'" (click)="store.vantaggio.set('dis')">Svantaggio</button>
          <button [class.attivo]="store.vantaggio() === ''" (click)="store.vantaggio.set('')">Normale</button>
          <button title="Vantaggio: tira 2d20 e tieni il più alto" [class.attivo]="store.vantaggio() === 'adv'" (click)="store.vantaggio.set('adv')">Vantaggio</button>
        </div>
      </div>
      <div class="riga">
        <label class="switch"><input type="checkbox" [(ngModel)]="segreto" /> <span>{{ store.master() ? 'tiro nascosto ai giocatori' : 'tiro privato (solo tu e il Master)' }}</span></label>
        <button class="link" (click)="svuota()">svuota</button>
        <button id="pool-tira" class="primario" (click)="tira()">TIRA 🎲</button>
      </div>
    </div>
    <div #log class="log">
      @for (v of voci(); track v.id) {
        @switch (v.tipo) {
          @case ('sistema') {
            <div class="voce sistema">{{ v.testo }}</div>
          }
          @case ('chat') {
            <div class="voce" [class.segreto]="v.segreto" [style.--c]="v.colore">
              <div class="chi">{{ v.chi }}<small>{{ ora(v.ora) }}{{ v.segreto ? ' · 🔒 segreto' : '' }}</small></div>
              <div>{{ v.testo }}</div>
            </div>
          }
          @case ('tiro') {
            <div class="voce" [class.critico]="v.critico" [class.fallimento]="v.fallimento" [class.segreto]="v.segreto" [style.--c]="v.colore">
              <div class="chi">{{ v.chi }}<small>{{ ora(v.ora) }}{{ v.segreto ? ' · 🔒 segreto' : '' }}</small></div>
              <div class="tiro">
                <div class="tot">{{ v.totale }}</div>
                <div>
                  <div class="etich">
                    {{ v.etichetta || v.espr }}
                    @if (v.modo) {
                      <small>({{ v.modo }})</small>
                    }
                    @if (v.critico) {
                      <span class="badge">20 NATURALE!</span>
                    } @else if (v.fallimento) {
                      <span class="badge">1 naturale</span>
                    }
                  </div>
                  <div class="det">{{ v.espr }} → @for (p of v.parti; track $index) { <span class="parte">{{ testoParte(p) }}</span> @if (p.tipo === 'dadi') { @for (x of p.valori; track $index; let i = $index) { <span class="d" [class.x]="!p.tenuti.includes(i)" [class.m]="p.tenuti.includes(i) && x === p.facce" [class.u]="p.tenuti.includes(i) && x === 1">{{ x }}</span> } } }</div>
                </div>
              </div>
              @if (v.danni; as dn) {
                <div class="tiro">
                  <div class="tot" style="font-size:19px">{{ dn.totale }}</div>
                  <div>
                    <div class="etich">💥 Danni{{ v.critico ? ' (critico: dadi doppi!)' : '' }}</div>
                    <div class="det">@for (p of dn.parti; track $index) { <span>{{ testoParte(p) }}</span> @if (p.tipo === 'dadi') { @for (x of p.valori; track $index; let i = $index) { <span class="d" [class.x]="!p.tenuti.includes(i)" [class.m]="x === p.facce" [class.u]="x === 1">{{ x }}</span> } } }</div>
                  </div>
                </div>
              }
            </div>
          }
        }
      }
    </div>
    <form class="chat" (submit)="invia($event)">
      <input [(ngModel)]="testo" name="chat" placeholder="Scrivi… oppure /r 2d6+3" autocomplete="off" />
      <button class="primario">➤</button>
    </form>
  `,
})
export class DadiComponent {
  protected readonly store = inject(TavoloStore);
  protected readonly azioni = inject(AzioniService);
  private readonly api = inject(ApiService);
  private readonly san = inject(DomSanitizer);
  private readonly logEl = viewChild.required<ElementRef<HTMLElement>>('log');

  protected readonly sg = sg;
  protected readonly dadiBottoni = [4, 6, 8, 10, 12, 20, 100].map((f) => ({ f, svg: this.san.bypassSecurityTrustHtml(svgDado(f, '#3a2a1c')) }));
  protected readonly pool = signal<Record<number, number>>({});
  protected readonly mod = signal(0);
  protected readonly espressione = computed(() => espressionePool(this.pool(), this.mod(), this.store.vantaggio()));
  protected readonly voci = computed(() => this.store.log().slice(-150) as VoceLog[]);
  protected segreto = false;
  protected testo = '';

  constructor() {
    // la cronologia resta in fondo, a meno che non si stia leggendo più su
    let n = 0;
    effect(() => {
      const l = this.voci().length;
      const ultima = this.voci()[l - 1];
      const el = this.logEl().nativeElement;
      const vicino = el.scrollHeight - el.scrollTop - el.clientHeight < 80 || n === 0 || ultima?.da === this.store.io()?.id;
      n = l;
      if (vicino) requestAnimationFrame(() => (el.scrollTop = el.scrollHeight));
    });
  }

  protected aggiungi(f: number): void {
    this.pool.update((p) => ({ ...p, [f]: (p[f] ?? 0) + 1 }));
  }

  protected subito(e: Event, f: number): void {
    e.preventDefault();
    const m = this.mod();
    void this.azioni.tiro(f === 20 ? this.azioni.d20(m) : `1d${f}${m ? (m > 0 ? '+' : '') + m : ''}`, `d${f}`);
  }

  protected tira(): void {
    const e = this.espressione() || this.azioni.d20(this.mod());
    void this.azioni.tiro(e, '', { segreto: this.segreto });
    this.svuota();
  }

  protected svuota(): void {
    this.pool.set({});
    this.mod.set(0);
  }

  protected invia(e: Event): void {
    e.preventDefault();
    const t = this.testo.trim();
    if (!t) return;
    const espr = comandoTiro(t);
    if (espr) void this.azioni.tiro(espr, '', { segreto: this.segreto, chiudi: false });
    else void this.api.op({ op: 'chat', testo: t, segreto: this.segreto });
    this.testo = '';
  }

  protected ora(t: number): string {
    return new Date(t * 1000).toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' });
  }

  protected testoParte(p: ParteTiro): string {
    if (p.tipo === 'num') return `${p.valore >= 0 ? '+' : '−'}${Math.abs(p.valore)}`;
    return `${p.segno < 0 ? '−' : ''}${p.n}d${p.facce}`;
  }
}
