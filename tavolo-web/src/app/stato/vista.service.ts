import { Injectable, inject } from '@angular/core';

import type { Punto } from '../util/geometria';
import { posPedina } from '../util/geometria';
import { TavoloStore } from './tavolo.store';

const MOBILE = 860;

/** Vista della mappa: zoom, spostamento, conversione da coordinate dello schermo a coordinate della mappa. */
@Injectable({ providedIn: 'root' })
export class VistaService {
  private readonly store = inject(TavoloStore);
  /** Il riquadro della mappa (lo imposta il componente della mappa). */
  viewport: HTMLElement | null = null;

  private rect(): DOMRect | null {
    return this.viewport?.getBoundingClientRect() ?? null;
  }

  aMondo(clientX: number, clientY: number): Punto {
    const vp = this.rect();
    const v = this.store.vista();
    return { x: (clientX - (vp?.left ?? 0) - v.x) / v.z, y: (clientY - (vp?.top ?? 0) - v.y) / v.z };
  }

  centroVista(): Punto {
    const vp = this.rect();
    if (!vp) return { x: 0, y: 0 };
    return this.aMondo(vp.left + vp.width / 2, vp.top + vp.height / 2 - (innerWidth < MOBILE ? 25 : 0));
  }

  zoom(f: number, cx?: number, cy?: number): void {
    const vp = this.rect();
    if (!vp) return;
    const x = cx ?? vp.width / 2;
    const y = cy ?? vp.height / 2;
    const v = this.store.vista();
    const z = Math.min(6, Math.max(0.08, v.z * f));
    this.store.vista.set({ x: x - (x - v.x) * (z / v.z), y: y - (y - v.y) * (z / v.z), z });
  }

  centraSu(p: Punto): void {
    const vp = this.rect();
    if (!vp) return;
    const z = this.store.vista().z;
    this.store.vista.set({ x: vp.width / 2 - p.x * z, y: vp.height / 2 - p.y * z, z });
  }

  /** Adatta la mappa allo schermo; su telefono ingrandisce e centra sulla propria pedina (o sul gruppo). */
  adatta(): void {
    const vp = this.rect();
    if (!vp || vp.width < 10 || vp.height < 10) return;
    const m = this.store.mappa();
    const mobile = innerWidth < MOBILE;
    const alto = vp.height - (mobile ? 50 : 0);
    let z = Math.max(0.1, Math.min(vp.width / m.larghezza, alto / m.altezza) * 0.96);
    let x = (vp.width - m.larghezza * z) / 2;
    let y = (alto - m.altezza * z) / 2;
    if (mobile) {
      z = Math.max(z, Math.min(1, (alto / m.altezza) * 0.95));
      const io = this.store.io();
      const mia = this.store.pedineScena().find((p) => p.pg && (p.pg === io?.char || this.store.master()));
      const c = mia ? posPedina(mia, m) : { x: m.larghezza / 2, y: m.altezza / 2 };
      x = vp.width / 2 - c.x * z;
      y = alto / 2 - c.y * z;
    }
    this.store.vista.set({ x, y, z });
  }
}
