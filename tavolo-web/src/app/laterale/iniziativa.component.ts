import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ApiService } from '../api/api.service';
import type { VoceIniziativa } from '../api/generati/VoceIniziativa';
import { UiService } from '../core/ui.service';
import { AzioniService } from '../stato/azioni.service';
import { TavoloStore } from '../stato/tavolo.store';
import { posPedina } from '../util/geometria';

/** Ordine di iniziativa e turni. */
@Component({
  selector: 'app-iniziativa',
  imports: [FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="ini-testa">
      <div><b>Round {{ store.iniziativa().round }}</b></div>
      <div class="gruppo-btn"><button class="primario" (click)="tiraIniziativa()">🎲 Tira iniziativa</button></div>
    </div>
    <ol class="ini-lista">
      @for (x of store.iniziativa().ordine; track x.id; let i = $index) {
        <li [class.corrente]="i === store.iniziativa().turno" [class.nasc]="x.nascosta" [style.--c]="x.colore || '#888'" (click)="vai($event, x)">
          @if (store.master()) {
            <input type="number" class="v" style="width:54px" [value]="x.valore" (change)="valore(x, $event)" />
          } @else {
            <span class="v">{{ x.valore }}</span>
          }
          <span class="n">{{ i === store.iniziativa().turno ? '▶ ' : '' }}{{ x.nome }}{{ x.nascosta ? ' 👁️‍🗨️' : '' }}</span>
          @if (store.master()) {
            <button (click)="rimuovi(x)">✕</button>
          }
        </li>
      } @empty {
        <li style="cursor:default;color:var(--muto)">Nessuno scontro in corso. Quando il Master dice «Tirate l'iniziativa!», premi il pulsante qui sopra.</li>
      }
    </ol>
    @if (store.master()) {
      <div class="ini-master">
        <div class="gruppo-btn">
          <button (click)="turno('precedente')">◀ Indietro</button>
          <button class="primario" (click)="turno('prossimo')">Prossimo turno ▶</button>
        </div>
        <div class="gruppo-btn">
          <button (click)="azioni.iniziativaMostri()">+ Mostri sulla mappa</button>
          <button (click)="svuota()">Fine scontro</button>
        </div>
        <form class="riga" (submit)="aggiungi($event)">
          <input [(ngModel)]="nome" name="nome" placeholder="Nome" />
          <input [(ngModel)]="val" name="val" type="number" placeholder="Val." style="width:70px" />
          <button>+</button>
        </form>
      </div>
    }
    <p class="aiuto">Chi ha il valore più alto agisce per primo. Nel tuo turno: <b>movimento</b> + <b>un'azione</b> (+ eventuale azione bonus).</p>
  `,
})
export class IniziativaComponent {
  protected readonly store = inject(TavoloStore);
  protected readonly azioni = inject(AzioniService);
  private readonly api = inject(ApiService);
  private readonly ui = inject(UiService);
  protected nome = '';
  protected val: number | null = null;

  protected tiraIniziativa(): void {
    const io = this.store.io();
    const ped = this.store.pedineScena().find((x) => x.pg && x.pg === io?.char) ?? Object.values(this.store.stato()?.pedine ?? {}).find((x) => x?.pg && x.pg === io?.char);
    if (ped) void this.azioni.iniziativaPedina(ped);
    else if (this.store.master()) void this.azioni.iniziativaMostri();
    else void this.azioni.iniziativaLibera(io?.name ?? '?', 0);
  }

  protected vai(e: Event, x: VoceIniziativa): void {
    if ((e.target as HTMLElement).closest('input,button')) return;
    const p = x.pedina ? this.store.stato()?.pedine[x.pedina] : undefined;
    if (p && p.scena === this.store.stato()?.scena) {
      const pos = posPedina(p, this.store.mappa());
      this.store.centra.set({ ...pos, n: (this.store.centra()?.n ?? 0) + 1 });
      this.store.sel.set(p.id);
    }
  }

  protected valore(x: VoceIniziativa, e: Event): void {
    void this.api.op({ op: 'iniziativa', azione: 'valore', id: x.id, valore: +(e.target as HTMLInputElement).value });
  }

  protected rimuovi(x: VoceIniziativa): void {
    void this.api.op({ op: 'iniziativa', azione: 'rimuovi', id: x.id });
  }

  protected turno(azione: 'prossimo' | 'precedente'): void {
    void this.api.op({ op: 'iniziativa', azione });
  }

  protected async svuota(): Promise<void> {
    if (await this.ui.conferma("L'ordine di iniziativa verrà svuotato.", { titolo: 'Fine dello scontro?', icona: '⚔️', ok: 'Termina' })) {
      void this.api.op({ op: 'iniziativa', azione: 'svuota' });
    }
  }

  protected aggiungi(e: Event): void {
    e.preventDefault();
    if (!this.nome) return;
    void this.api.op({ op: 'iniziativa', azione: 'aggiungi', nome: this.nome, valore: this.val || 0, colore: '#888' });
    this.nome = '';
    this.val = null;
  }
}
