import { ChangeDetectionStrategy, Component, effect, inject, signal } from '@angular/core';
import { DomSanitizer, type SafeHtml } from '@angular/platform-browser';

import type { VoceTiro } from '../api/avventura';
import { TavoloStore } from '../stato/tavolo.store';
import { svgDado } from '../util/dado-svg';

interface Dado {
  f: number;
  v: number;
  mostrato: number;
  scartato: boolean;
  danno: boolean;
  dx: number;
  r: number;
  svg: SafeHtml;
}

/** L'animazione dei dadi che rotolano al centro della mappa. */
@Component({
  selector: 'app-lancio',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div id="dadi-anim">
      @if (v(); as v) {
        <div class="lancio" [class.critico]="v.critico" [class.fallimento]="v.fallimento">
          <div class="fila">
            @for (d of dadi(); track $index) {
              <div class="dado" [class.scartato]="d.scartato" [class.max]="d.v === d.f" [style.--dx]="d.dx + 'px'" [style.--r]="d.r + 'deg'" [style.animation-delay]="$index * 60 + 'ms'">
                <span class="svg" [innerHTML]="d.svg"></span><span>{{ d.mostrato }}</span>
              </div>
            }
            @if (altri() > 0) {
              <div class="dado"><span>+{{ altri() }}</span></div>
            }
          </div>
          <div class="totale">
            <small>{{ v.chi }} · {{ v.etichetta || v.espr }}</small>
            <b
              >{{ v.totale }}
              @if (v.danni) {
                <span style="font-size:18px;color:#ff9f8a">· 💥 {{ v.danni.totale }}</span>
              }
            </b>
            @if (v.critico) {
              <small>✨ 20 NATURALE! ✨</small>
            } @else if (v.fallimento) {
              <small>💀 che sfortuna…</small>
            }
          </div>
        </div>
      }
    </div>
  `,
})
export class LancioComponent {
  private readonly store = inject(TavoloStore);
  private readonly san = inject(DomSanitizer);
  protected readonly v = signal<VoceTiro | null>(null);
  protected readonly dadi = signal<Dado[]>([]);
  protected readonly altri = signal(0);
  private giro: ReturnType<typeof setInterval> | null = null;
  private via: ReturnType<typeof setTimeout> | null = null;

  constructor() {
    effect(() => {
      const v = this.store.lancio();
      if (v) this.mostra(v);
    });
  }

  private mostra(v: VoceTiro): void {
    const tutti: Omit<Dado, 'svg' | 'dx' | 'r' | 'mostrato'>[] = [];
    v.parti.forEach((p) => p.tipo === 'dadi' && p.valori.forEach((x, i) => tutti.push({ f: p.facce, v: x, scartato: !p.tenuti.includes(i), danno: false })));
    v.danni?.parti.forEach((p) => p.tipo === 'dadi' && p.valori.forEach((x) => tutti.push({ f: p.facce, v: x, scartato: false, danno: true })));
    const colore = v.colore || '#7a2e1c';
    // gli SVG sono generati qui da numeri e da un colore già validato dal server
    const dadi = tutti.slice(0, 10).map((d) => ({
      ...d,
      mostrato: 1,
      dx: (Math.random() - 0.5) * 300,
      r: (Math.random() - 0.5) * 720,
      svg: this.san.bypassSecurityTrustHtml(svgDado(d.f, d.danno ? '#5a1d10' : colore)),
    }));
    this.v.set(v);
    this.altri.set(tutti.length - dadi.length);
    this.dadi.set(dadi);
    if (this.giro) clearInterval(this.giro);
    if (this.via) clearTimeout(this.via);
    let n = 0;
    this.giro = setInterval(() => {
      n++;
      this.dadi.update((l) => l.map((d) => ({ ...d, mostrato: n < 9 ? 1 + Math.floor(Math.random() * d.f) : d.v })));
      if (n >= 9 && this.giro) clearInterval(this.giro);
    }, 70);
    this.via = setTimeout(() => this.v.set(null), 3800);
  }
}
