import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';

import { ApiService } from '../api/api.service';
import type { Documento } from '../api/avventura';
import type { Pedina } from '../api/generati/Pedina';
import { ConnessioneService } from '../core/connessione.service';
import { UiService } from '../core/ui.service';
import { TavoloStore } from '../stato/tavolo.store';

/** Documenti dell'avventura, chi c'è al tavolo, salute del gruppo, guida rapida. */
@Component({
  selector: 'app-gruppo',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h3>📖 Avventura</h3>
    <div class="documenti">
      <p style="margin:0 0 6px"><b>{{ store.avv().titolo }}</b><br /><span class="aiuto">{{ store.avv().descrizione || '' }}</span></p>
      @for (d of store.avv().documenti; track d.file) {
        <a class="btn doc" target="_blank" rel="noopener" [href]="url(d)">{{ d.solo_master ? '🔒' : '📖' }} {{ d.titolo }}</a>
      } @empty {
        <p class="aiuto">Nessun documento.</p>
      }
    </div>
    <div class="riga">
      <span class="aiuto" style="flex:1">
        @if (store.io()?.avatar; as a) {
          <img [src]="a" style="width:18px;height:18px;border-radius:50%;vertical-align:middle" />
        }
        {{ store.io()?.name }} · {{ store.io()?.provider || 'ospite' }}{{ store.adminTavolo() ? ' · admin' : '' }}
      </span>
      <button class="link" (click)="esci()">Esci / cambia account</button>
    </div>
    <h3>Al tavolo</h3>
    <ul class="online">
      @for (u of persone(); track u.id) {
        <li [style.--c]="u.color">
          @if (u.avatar) {
            <img [src]="u.avatar" alt="" />
          } @else {
            <span class="pallino"></span>
          }
          <b>{{ u.name }}</b> <span class="aiuto">{{ u.role === 'master' ? '👑 Master' : pg(u.char) || 'spettatore' }}</span>
        </li>
      }
    </ul>
    <h3>Il gruppo</h3>
    @for (p of gruppo(); track p.id) {
      <div class="party-pg">
        <div class="riga" style="margin:0;justify-content:space-between">
          <span>{{ p.icona }} <b>{{ p.nome }}</b></span><span>{{ p.pf }}/{{ p.pfmax }} · CA {{ p.ca }}</span>
        </div>
        <div class="barra-pf"><i [style.width.%]="salute(p) * 100"></i></div>
        @if (p.condizioni.length) {
          <small class="aiuto">{{ p.condizioni.join(', ') }}</small>
        }
      </div>
    } @empty {
      <p class="aiuto">Nessun personaggio al tavolo.</p>
    }
    <h3>Guida rapida</h3>
    <div class="aiuto">
      <p><b>Muovere la mappa:</b> trascina lo sfondo · rotellina o due dita per lo zoom.</p>
      <p><b>Muovere la tua pedina:</b> trascinala; si aggancia alla griglia e vedi quanti metri hai fatto (velocità tipica 9 m = 6 quadretti).</p>
      <p><b>Tirare i dadi:</b> nella scheda clicca su qualsiasi abilità, attacco o incantesimo, oppure usa il vassoio dei dadi.</p>
      <p><b>Scorciatoie:</b> V muovi · R righello · P ping · frecce per spostare la pedina selezionata.</p>
    </div>
  `,
})
export class GruppoComponent {
  protected readonly store = inject(TavoloStore);
  private readonly api = inject(ApiService);
  private readonly ui = inject(UiService);
  private readonly conn = inject(ConnessioneService);

  protected readonly persone = computed(() => this.store.online().filter((u) => !u.sistema));
  protected readonly gruppo = computed(() => Object.values(this.store.stato()?.pedine ?? {}).filter((p): p is Pedina => !!p?.pg));

  protected pg(id: string | null): string {
    const p = id ? this.store.personaggi().get(id) : undefined;
    return p ? `${p.icona} ${p.nome}` : '';
  }

  protected salute(p: Pedina): number {
    return Math.max(0, Math.min(1, (p.pf ?? p.pfmax ?? 0) / (p.pfmax || 1)));
  }

  protected url(d: Documento): string {
    const base = `/avventure/${this.store.avv().id}/documenti/${encodeURIComponent(d.file)}`;
    return d.solo_master ? this.api.link(base) : base;
  }

  protected async esci(): Promise<void> {
    if (await this.ui.conferma('Potrai rientrare quando vuoi.', { titolo: 'Uscire dal tavolo?', icona: '🚪', ok: 'Esci' })) this.conn.esci();
  }
}
