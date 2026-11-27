import { ChangeDetectionStrategy, Component, ElementRef, OnDestroy, OnInit, computed, effect, inject, signal, untracked, viewChild } from '@angular/core';

import { ApiService } from '../api/api.service';
import type { Pedina } from '../api/generati/Pedina';
import { UiService } from '../core/ui.service';
import { TavoloStore } from '../stato/tavolo.store';
import { VistaService } from '../stato/vista.service';
import { type Punto, aggancia, cellaDi, cellaPx, celleDaPennello, celleDaRett, dimNebbia, distanzaQ, fmtDist, posPedina } from '../util/geometria';
import { iconaCondizione } from '../util/scheda';

interface VistaPedina {
  p: Pedina;
  x: number;
  y: number;
  s: number;
  r: number;
  visibile: boolean;
  mia: boolean;
  turno: boolean;
  trascinata: boolean;
  cond: string;
}

/** La mappa: immagine, griglia, nebbia, pedine, righelli e ping, con pan/zoom e trascinamento. */
@Component({
  selector: 'app-mappa',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section
      #vp
      id="viewport"
      [class]="'tool-' + store.strumento()"
      [class.trascina]="spostando()"
      (pointerdown)="giu($event)"
      (pointermove)="muovi($event)"
      (pointerup)="su($event)"
      (pointercancel)="su($event)"
      (contextmenu)="$event.preventDefault()"
      (dblclick)="doppio($event)"
    >
      <div id="mondo" [style.transform]="trasformazione()">
        <img id="mappa" alt="" draggable="false" [hidden]="!mappa().file" [src]="src()" [style.width.px]="mappa().larghezza" [style.height.px]="mappa().altezza" (error)="erroreImmagine()" />
        <canvas #griglia id="griglia-cv"></canvas>
        <canvas #nebbia id="nebbia-cv" [class.giocatore]="!store.master()"></canvas>
        <div id="pedine">
          @for (v of pedine(); track v.p.id) {
            <div
              class="pedina"
              [id]="'p_' + v.p.id"
              [hidden]="!v.visibile"
              [class.trascinata]="v.trascinata"
              [class.nascosta]="!!v.p.nascosta"
              [class.selezionata]="store.sel() === v.p.id"
              [class.mia]="v.mia"
              [class.a-terra]="!!v.p.pfmax && (v.p.pf ?? 1) <= 0"
              [class.turno]="v.turno"
              [style.width.px]="v.s"
              [style.height.px]="v.s"
              [style.left.px]="v.x - v.s / 2"
              [style.top.px]="v.y - v.s / 2"
              [style.z-index]="v.p.tipo === 'pg' ? 3 : 2"
              [style.--s]="v.s + 'px'"
              [style.--c]="v.p.colore || '#555'"
              [title]="v.p.nome + (v.p.pfmax ? ' · PF ' + v.p.pf + '/' + v.p.pfmax : '')"
              (pointerdown)="inizioTrascina($event, v.p)"
            >
              <div class="pf" [hidden]="!v.p.pfmax" [class.basso]="v.r <= 0.25" [class.medio]="v.r > 0.25 && v.r <= 0.5"><i [style.width.%]="v.r * 100"></i></div>
              <div class="disco"><span class="ico">{{ v.p.icona || (v.p.nome || '?').slice(0, 2) }}</span></div>
              <div class="nome">{{ v.p.nome }}</div>
              <div class="cond">{{ v.cond }}</div>
            </div>
          }
        </div>
        <svg id="sovra" xmlns="http://www.w3.org/2000/svg" [attr.width]="mappa().larghezza" [attr.height]="mappa().altezza" [style.width.px]="mappa().larghezza" [style.height.px]="mappa().altezza">
          @if (traccia(); as t) {
            <g>
              <line [attr.x1]="t.a.x" [attr.y1]="t.a.y" [attr.x2]="t.b.x" [attr.y2]="t.b.y" stroke="#f6d27a" [attr.stroke-width]="4 * k()" [attr.stroke-dasharray]="10 * k() + ' ' + 6 * k()" stroke-linecap="round" />
              <circle [attr.cx]="t.b.x" [attr.cy]="t.b.y" [attr.r]="6 * k()" fill="#f6d27a" />
              <g [attr.transform]="'translate(' + t.b.x + ' ' + (t.b.y - 30 * k()) + ') scale(' + k() + ')'">
                <rect x="-58" y="-16" width="116" height="26" rx="13" fill="#1b130a" stroke="#e0b04a" />
                <text y="3" text-anchor="middle" fill="#f6d27a" font-size="14" font-weight="800" font-family="system-ui">{{ t.testo }}</text>
              </g>
            </g>
          }
          @for (r of righelli(); track r.chi) {
            <g>
              <line [attr.x1]="r.a.x" [attr.y1]="r.a.y" [attr.x2]="r.b.x" [attr.y2]="r.b.y" [attr.stroke]="r.colore" [attr.stroke-width]="5 * k()" stroke-linecap="round" opacity=".9" />
              <circle [attr.cx]="r.a.x" [attr.cy]="r.a.y" [attr.r]="6 * k()" [attr.fill]="r.colore" />
              <circle [attr.cx]="r.b.x" [attr.cy]="r.b.y" [attr.r]="6 * k()" [attr.fill]="r.colore" />
              <g [attr.transform]="'translate(' + r.b.x + ' ' + (r.b.y - 28 * k()) + ') scale(' + k() + ')'">
                <rect x="-60" y="-16" width="120" height="26" rx="13" fill="#1b130a" [attr.stroke]="r.colore" stroke-width="2" />
                <text y="3" text-anchor="middle" fill="#fff" font-size="14" font-weight="800" font-family="system-ui">📏 {{ r.testo }}</text>
              </g>
            </g>
          }
          @for (p of store.pings(); track p.id) {
            <g class="ping">
              <circle [attr.cx]="p.x" [attr.cy]="p.y" [attr.r]="10 * k()" [attr.fill]="p.colore">
                <animate attributeName="r" [attr.from]="8 * k()" [attr.to]="60 * k()" dur="1.2s" repeatCount="2" />
                <animate attributeName="opacity" from="1" to="0" dur="1.2s" repeatCount="2" />
              </circle>
              <circle [attr.cx]="p.x" [attr.cy]="p.y" [attr.r]="7 * k()" [attr.fill]="p.colore" stroke="#fff" [attr.stroke-width]="2 * k()" />
              <text [attr.x]="p.x" [attr.y]="p.y - 16 * k()" [attr.font-size]="13 * k()" text-anchor="middle" fill="#fff" stroke="#000" [attr.stroke-width]="3 * k()" paint-order="stroke" font-weight="800" font-family="system-ui">{{ p.chi }}</text>
            </g>
          }
        </svg>
      </div>
      <ng-content />
    </section>
  `,
})
export class MappaComponent implements OnInit, OnDestroy {
  protected readonly store = inject(TavoloStore);
  private readonly vista = inject(VistaService);
  private readonly api = inject(ApiService);
  private readonly ui = inject(UiService);

  private readonly vp = viewChild.required<ElementRef<HTMLElement>>('vp');
  private readonly cvGriglia = viewChild.required<ElementRef<HTMLCanvasElement>>('griglia');
  private readonly cvNebbia = viewChild.required<ElementRef<HTMLCanvasElement>>('nebbia');

  protected readonly mappa = this.store.mappa;
  protected readonly k = computed(() => 1 / this.store.vista().z);
  protected readonly trasformazione = computed(() => {
    const v = this.store.vista();
    return `translate(${v.x}px,${v.y}px) scale(${v.z})`;
  });
  protected readonly spostando = signal(false);
  private readonly tentativi = signal(0);
  protected readonly src = computed(() => {
    const file = this.mappa().file;
    if (!file) return '';
    // percorso assoluto: il client può essere servito anche da /beta/
    const f = file.startsWith('/') || file.startsWith('http') ? file : `/${file}`;
    const n = this.tentativi();
    return n ? `${f}${f.includes('?') ? '&' : '?'}r=${n}` : f;
  });

  protected readonly pedine = computed<VistaPedina[]>(() => {
    const m = this.mappa();
    const cel = cellaPx(m);
    const cur = this.store.turnoCorrente();
    const n = this.store.iniziativa().ordine.length;
    const master = this.store.master();
    const t = this.store.trascino();
    return this.store.pedineScena().map((p) => {
      const pos = this.store.posizione(p);
      const r = p.pfmax ? Math.max(0, Math.min(1, (p.pf ?? p.pfmax) / p.pfmax)) : 1;
      return {
        p,
        x: pos.x,
        y: pos.y,
        s: (p.taglia || 1) * cel,
        r,
        visibile: this.visibileNebbia(p),
        mia: this.store.puoMuovere(p) && !master,
        turno: !!cur && cur.pedina === p.id && n > 1,
        trascinata: t?.id === p.id,
        cond: (p.condizioni ?? []).map(iconaCondizione).join(''),
      };
    });
  });

  protected readonly traccia = computed(() => {
    const t = this.store.trascino();
    if (!t) return null;
    const p = this.store.stato()?.pedine[t.id];
    const m = this.mappa();
    const b = aggancia(t.pos.x, t.pos.y, p?.taglia ?? 1, m);
    return { a: t.partenza, b, testo: fmtDist(distanzaQ(t.partenza, b, m)) };
  });

  private readonly mioRighello = signal<Punto[] | null>(null);
  protected readonly righelli = computed(() => {
    const m = this.mappa();
    const io = this.store.io();
    const altri = Object.entries(this.store.righelli()).filter(([chi]) => chi !== io?.id);
    const mio = this.mioRighello();
    const tutti: [string, Punto[], string][] = altri.map(([chi, r]) => [chi, r.punti, r.colore]);
    if (mio && io) tutti.push([io.id, mio, io.color]);
    return tutti.filter(([, punti]) => punti.length >= 2).map(([chi, [a, b], colore]) => ({ chi, a, b, colore, testo: fmtDist(distanzaQ(a, b, m)) }));
  });

  private readonly ridimensiona = () => this.vista.adatta();
  private readonly rotella = (e: WheelEvent) => {
    e.preventDefault();
    const r = this.vp().nativeElement.getBoundingClientRect();
    this.vista.zoom(Math.exp(-e.deltaY * 0.0015), e.clientX - r.left, e.clientY - r.top);
  };

  constructor() {
    // griglia disegnata solo per le mappe che la chiedono
    effect(() => {
      const cv = this.cvGriglia().nativeElement;
      const m = this.mappa();
      const g = this.store.griglia();
      if (!g || !g.mostra) {
        cv.width = cv.height = 0;
        return;
      }
      cv.width = m.larghezza;
      cv.height = m.altezza;
      cv.style.width = `${m.larghezza}px`;
      cv.style.height = `${m.altezza}px`;
      const c = cv.getContext('2d');
      if (!c) return;
      c.strokeStyle = 'rgba(0,0,0,.45)';
      c.lineWidth = 1;
      c.beginPath();
      for (let x = g.ox; x <= m.larghezza; x += g.cella) {
        c.moveTo(x, 0);
        c.lineTo(x, m.altezza);
      }
      for (let y = g.oy; y <= m.altezza; y += g.cella) {
        c.moveTo(0, y);
        c.lineTo(m.larghezza, y);
      }
      c.stroke();
    });
    // nebbia: un pixel per quadretto, ingrandito (e sfocato per i giocatori)
    effect(() => this.disegnaNebbia());
    // nuova mappa → si adatta la vista
    let scenaPrima: string | null | undefined;
    effect(() => {
      const sc = this.store.stato()?.scena;
      if (sc !== scenaPrima) {
        scenaPrima = sc;
        this.tentativi.set(0);
        requestAnimationFrame(() => this.vista.adatta());
      }
    });
    effect(() => {
      const c = this.store.centra();
      if (c) untracked(() => this.vista.centraSu(c));
    });
  }

  ngOnInit(): void {
    const el = this.vp().nativeElement;
    this.vista.viewport = el;
    el.addEventListener('wheel', this.rotella, { passive: false });
    addEventListener('resize', this.ridimensiona);
  }

  ngOnDestroy(): void {
    this.vp().nativeElement.removeEventListener('wheel', this.rotella);
    removeEventListener('resize', this.ridimensiona);
    this.vista.viewport = null;
  }

  protected erroreImmagine(): void {
    const n = this.tentativi() + 1;
    if (n <= 3) setTimeout(() => this.tentativi.set(n), 800 * n);
    else void this.ui.avviso("Non riesco a caricare l'immagine della mappa. Prova a ricaricare la pagina.", { titolo: 'Mappa non disponibile', icona: '🗺️' });
  }

  private visibileNebbia(p: Pedina): boolean {
    if (this.store.master() || p.pg || this.store.puoMuovere(p)) return true;
    const nb = this.store.nebbia();
    const d = dimNebbia(this.mappa());
    if (!nb || !nb.attiva || !d) return true;
    return nb.celle.includes(cellaDi(posPedina(p, this.mappa()), d));
  }

  private disegnaNebbia(): void {
    const cv = this.cvNebbia().nativeElement;
    const nb = this.store.nebbia();
    const m = this.mappa();
    const d = dimNebbia(m);
    const anteprima = this.store.anteprimaNebbia();
    const modo = this.store.nebbiaModo();
    const master = this.store.master();
    const pedine = this.store.pedineScena();
    if (!d || !nb || !nb.attiva) {
      cv.width = cv.height = 0;
      return;
    }
    cv.width = d.col;
    cv.height = d.rig;
    cv.style.left = `${d.g.ox}px`;
    cv.style.top = `${d.g.oy}px`;
    cv.style.width = `${d.col * d.g.cella}px`;
    cv.style.height = `${d.rig * d.g.cella}px`;
    const c = cv.getContext('2d');
    if (!c) return;
    c.fillStyle = master ? 'rgba(10,8,20,.55)' : '#07060a';
    c.fillRect(0, 0, d.col, d.rig);
    const viste = new Set(nb.celle);
    anteprima?.forEach((k) => (modo === 'rivela' ? viste.add(k) : viste.delete(k)));
    viste.forEach((k) => {
      const [x, y] = k.split(',').map(Number);
      c.clearRect(x, y, 1, 1);
    });
    if (!master) {
      // ogni personaggio vede un quadretto intorno a sé (effetto «torcia»)
      for (const p of pedine) {
        if (!p.pg) continue;
        const pos = this.store.posizione(p);
        const cx = Math.floor((pos.x - d.g.ox) / d.g.cella);
        const cy = Math.floor((pos.y - d.g.oy) / d.g.cella);
        c.clearRect(cx - 1, cy - 1, 3, 3);
      }
    }
  }

  // ------------------------------------------------------------------ input sulla mappa
  private readonly punti = new Map<number, Punto>();
  private pan: { x: number; y: number; vx: number; vy: number; mosso: boolean } | null = null;
  private pinch: { d: number; z: number } | null = null;
  private azione: { tipo: 'righello'; a: Punto; ultimo: number } | { tipo: 'pennello' } | { tipo: 'rett'; a: Punto } | null = null;

  protected giu(e: PointerEvent): void {
    if ((e.target as HTMLElement).closest('.flottante, #sala')) return;
    const vp = this.vp().nativeElement;
    vp.setPointerCapture(e.pointerId);
    this.punti.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (this.punti.size === 2) {
      const [a, b] = [...this.punti.values()];
      this.pinch = { d: Math.hypot(a.x - b.x, a.y - b.y), z: this.store.vista().z };
      this.pan = null;
      this.azione = null;
      return;
    }
    const w = this.vista.aMondo(e.clientX, e.clientY);
    const tool = this.store.strumento();
    if (e.button === 1 || e.button === 2 || tool === 'muovi') {
      const v = this.store.vista();
      this.pan = { x: e.clientX, y: e.clientY, vx: v.x, vy: v.y, mosso: false };
      this.spostando.set(true);
      return;
    }
    if (tool === 'righello') this.azione = { tipo: 'righello', a: aggancia(w.x, w.y, 1, this.mappa()), ultimo: 0 };
    if (tool === 'ping') void this.api.op({ op: 'ping', x: w.x, y: w.y, centra: e.shiftKey });
    if (tool === 'nebbia' && this.store.master()) {
      if (!this.store.nebbia()?.attiva) {
        void this.ui.avviso('Spunta «attiva su questa mappa» nel riquadro della nebbia, poi potrai rivelare o coprire le zone.', { titolo: 'La nebbia è spenta', icona: '🌫️' });
        return;
      }
      const d = dimNebbia(this.mappa());
      if (!d) return;
      if (this.store.nebbiaForma() === 'rett') this.azione = { tipo: 'rett', a: w };
      else {
        this.azione = { tipo: 'pennello' };
        this.store.anteprimaNebbia.set(new Set(celleDaPennello(w, +this.store.nebbiaForma(), d)));
      }
    }
  }

  protected muovi(e: PointerEvent): void {
    if (this.trascinamento) {
      this.trascinamento.muovi(e);
      return;
    }
    if (!this.punti.has(e.pointerId)) return;
    this.punti.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (this.pinch && this.punti.size === 2) {
      const [a, b] = [...this.punti.values()];
      const d = Math.hypot(a.x - b.x, a.y - b.y);
      const r = this.vp().nativeElement.getBoundingClientRect();
      this.vista.zoom((this.pinch.z * d) / this.pinch.d / this.store.vista().z, (a.x + b.x) / 2 - r.left, (a.y + b.y) / 2 - r.top);
      return;
    }
    if (this.pan) {
      const dx = e.clientX - this.pan.x;
      const dy = e.clientY - this.pan.y;
      if (Math.abs(dx) + Math.abs(dy) > 3) this.pan.mosso = true;
      this.store.vista.update((v) => ({ ...v, x: this.pan!.vx + dx, y: this.pan!.vy + dy }));
      return;
    }
    const a = this.azione;
    if (!a) return;
    const w = this.vista.aMondo(e.clientX, e.clientY);
    const m = this.mappa();
    const d = dimNebbia(m);
    if (a.tipo === 'righello') {
      const b = aggancia(w.x, w.y, 1, m);
      this.mioRighello.set([a.a, b]);
      const ora = performance.now();
      if (ora - a.ultimo > 100) {
        a.ultimo = ora;
        void this.api.op({ op: 'righello', punti: [a.a, b] }, { silenzioso: true });
      }
    } else if (a.tipo === 'pennello' && d) {
      const s = new Set(this.store.anteprimaNebbia() ?? []);
      celleDaPennello(w, +this.store.nebbiaForma(), d).forEach((k) => s.add(k));
      this.store.anteprimaNebbia.set(s);
    } else if (a.tipo === 'rett' && d) {
      this.store.anteprimaNebbia.set(new Set(celleDaRett(a.a, w, d)));
    }
  }

  protected su(e: PointerEvent): void {
    if (this.trascinamento) {
      this.trascinamento.fine(e);
      return;
    }
    this.punti.delete(e.pointerId);
    if (this.punti.size < 2) this.pinch = null;
    this.spostando.set(false);
    if (this.pan) {
      if (!this.pan.mosso && !(e.target as HTMLElement).closest?.('.pedina')) this.store.sel.set(null);
      this.pan = null;
    }
    const a = this.azione;
    if (a?.tipo === 'righello') {
      void this.api.op({ op: 'righello', punti: null }, { silenzioso: true });
      setTimeout(() => this.mioRighello.set(null), 1500);
    }
    const ant = this.store.anteprimaNebbia();
    if ((a?.tipo === 'pennello' || a?.tipo === 'rett') && ant) {
      const modo = this.store.nebbiaModo();
      void this.api.op({ op: 'nebbia', azione: modo, celle: [...ant] });
      const sc = this.store.stato()?.scena;
      const nb = this.store.nebbia();
      if (sc && nb) {
        const s = new Set(nb.celle);
        ant.forEach((k) => (modo === 'rivela' ? s.add(k) : s.delete(k)));
        this.store.aggiornaNebbia(sc, [...s]);
      }
      this.store.anteprimaNebbia.set(null);
    }
    this.azione = null;
  }

  protected doppio(e: MouseEvent): void {
    if ((e.target as HTMLElement).closest('.pedina,.flottante,#sala')) return;
    const w = this.vista.aMondo(e.clientX, e.clientY);
    void this.api.op({ op: 'ping', x: w.x, y: w.y });
  }

  // ------------------------------------------------------------------ trascinamento delle pedine
  private trascinamento: { muovi: (e: PointerEvent) => void; fine: (e: PointerEvent) => void } | null = null;

  protected inizioTrascina(e: PointerEvent, p: Pedina): void {
    if (this.store.strumento() !== 'muovi') return;
    e.stopPropagation();
    this.store.sel.set(p.id);
    if (!this.store.puoMuovere(p) || e.button !== 0) return;
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    const m = this.mappa();
    const partenza = posPedina(p, m);
    const w0 = this.vista.aMondo(e.clientX, e.clientY);
    const dx = w0.x - partenza.x;
    const dy = w0.y - partenza.y;
    let ultimo = 0;
    let mosso = false;
    const qui = (ev: PointerEvent): Punto => {
      const w = this.vista.aMondo(ev.clientX, ev.clientY);
      return { x: w.x - dx, y: w.y - dy };
    };
    this.store.trascino.set({ id: p.id, pos: partenza, partenza });
    this.trascinamento = {
      muovi: (ev) => {
        const pos = qui(ev);
        mosso = true;
        this.store.trascino.set({ id: p.id, pos, partenza });
        const ora = performance.now();
        if (ora - ultimo > 80) {
          ultimo = ora;
          const a = aggancia(pos.x, pos.y, p.taglia, m);
          void this.api.op({ op: 'pedina_muovi', id: p.id, x: a.x, y: a.y }, { silenzioso: true });
        }
      },
      fine: (ev) => {
        this.trascinamento = null;
        this.store.trascino.set(null);
        if (!mosso) return;
        const pos = qui(ev);
        const a = aggancia(pos.x, pos.y, p.taglia, m);
        const attuale = this.store.stato()?.pedine[p.id] ?? p;
        this.store.aggiornaPedina({ ...attuale, x: a.x, y: a.y });
        void this.api.op({ op: 'pedina_muovi', id: p.id, x: a.x, y: a.y, finale: true });
      },
    };
  }
}
