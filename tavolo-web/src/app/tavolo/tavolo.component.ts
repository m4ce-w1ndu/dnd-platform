import { ChangeDetectionStrategy, Component, HostListener, computed, inject } from '@angular/core';

import { ApiService } from '../api/api.service';
import { ConnessioneService } from '../core/connessione.service';
import { SuoniService } from '../core/suoni.service';
import { UiService } from '../core/ui.service';
import { LateraleComponent } from '../laterale/laterale.component';
import { type Strumento, TavoloStore } from '../stato/tavolo.store';
import { VistaService } from '../stato/vista.service';
import { aggancia, cellaPx, posPedina } from '../util/geometria';
import { LancioComponent } from './lancio.component';
import { MappaComponent } from './mappa.component';
import { PannelloPedinaComponent } from './pannello-pedina.component';
import { SalaComponent } from './sala.component';
import { SistemaComponent } from './sistema.component';

@Component({
  selector: 'app-tavolo',
  imports: [MappaComponent, LateraleComponent, PannelloPedinaComponent, SalaComponent, LancioComponent, SistemaComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div id="app">
      <header id="barra">
        <div class="titolo-scena">
          <span>{{ store.sistema() ? '⚙️ Amministrazione' : store.mappa().titolo }}</span><span class="conn" [class.ok]="store.connessione() === 'ok'" [class.ko]="store.connessione() === 'ko'" title="connessione"></span>
        </div>
        @if (!store.sistema()) {
          <div class="strumenti">
            @for (t of strumenti(); track t.id) {
              <button [class.attivo]="store.strumento() === t.id" [title]="t.titolo" (click)="strumento(t.id)">{{ t.ic }}<span>{{ t.nome }}</span></button>
            }
            <span class="sep"></span>
            <button title="Rimpicciolisci (-)" (click)="vista.zoom(0.8)">−</button>
            <button title="Adatta la mappa allo schermo (0)" (click)="vista.adatta()">⤢</button>
            <button title="Ingrandisci (+)" (click)="vista.zoom(1.25)">+</button>
          </div>
        } @else {
          <div class="strumenti"></div>
        }
        <div class="destra">
          @if (store.master() && store.sessione() === 'in_corso') {
            <button title="Torna alla sala d'attesa" (click)="pausa()">⏸</button>
          }
          <button title="Suoni on/off" (click)="suoni.alterna()">{{ suoni.attivi() ? '🔊' : '🔇' }}</button>
          <button class="logout" title="Esci da questo account" (click)="esci()">
            @if (store.io()?.avatar; as a) {
              <img [src]="a" alt="" />
            } @else {
              <b>{{ (store.io()?.name || '?').slice(0, 14) }}</b>
            }
            🚪<span class="testo">Esci</span>
          </button>
          <button class="solo-mobile" title="Mostra pannello" (click)="store.pannelloAperto.set(!store.pannelloAperto())">☰</button>
        </div>
      </header>

      <main id="corpo">
        @if (store.sistema()) {
          <app-sistema />
        } @else {
          <app-mappa>
            @if (store.strumento() === 'nebbia' && store.master()) {
              <div id="nebbia-strumenti" class="flottante">
                <b>🌫️ Nebbia</b>
                <label class="switch"><input type="checkbox" [checked]="!!store.nebbia()?.attiva" (change)="nebbiaAttiva($event)" /> attiva su questa mappa</label>
                <div class="gruppo-btn">
                  <button [class.attivo]="store.nebbiaModo() === 'rivela'" (click)="store.nebbiaModo.set('rivela')">Rivela</button><button [class.attivo]="store.nebbiaModo() === 'copri'" (click)="store.nebbiaModo.set('copri')">Copri</button>
                </div>
                <div class="gruppo-btn">
                  @for (f of forme; track f.id) {
                    <button [class.attivo]="store.nebbiaForma() === f.id" (click)="store.nebbiaForma.set(f.id)">{{ f.nome }}</button>
                  }
                </div>
                <div class="gruppo-btn"><button (click)="copriTutto()">Copri tutto</button></div>
              </div>
            }
            <app-pannello-pedina />
            <app-lancio />
            @if (store.avvisoTurno(); as t) {
              <div id="avviso-turno">{{ t.testo }}</div>
            }
            @if (store.sessione() !== 'in_corso') {
              <app-sala />
            }
          </app-mappa>
        }
        @if (!store.sistema()) {
          <app-laterale />
        }
      </main>
    </div>
  `,
})
export class TavoloComponent {
  protected readonly store = inject(TavoloStore);
  protected readonly vista = inject(VistaService);
  protected readonly suoni = inject(SuoniService);
  private readonly api = inject(ApiService);
  private readonly ui = inject(UiService);
  private readonly conn = inject(ConnessioneService);

  protected readonly forme = [
    { id: '1', nome: '● 1' },
    { id: '3', nome: '● 3' },
    { id: '5', nome: '● 5' },
    { id: 'rett', nome: '▭ area' },
  ] as const;

  protected readonly strumenti = computed(() => {
    const l: { id: Strumento; ic: string; nome: string; titolo: string }[] = [
      { id: 'muovi', ic: '✋', nome: 'Muovi', titolo: 'Muovi pedine / sposta la mappa (V)' },
      { id: 'righello', ic: '📏', nome: 'Righello', titolo: 'Misura le distanze (R)' },
      { id: 'ping', ic: '📍', nome: 'Ping', titolo: 'Segnala un punto a tutti (P)' },
    ];
    if (this.store.master()) l.push({ id: 'nebbia', ic: '🌫️', nome: 'Nebbia', titolo: 'Nebbia di guerra (F)' });
    return l;
  });

  protected strumento(t: Strumento): void {
    this.store.strumento.set(t);
    if (t === 'nebbia') this.store.sel.set(null);
  }

  protected nebbiaAttiva(e: Event): void {
    void this.api.op({ op: 'nebbia', attiva: (e.target as HTMLInputElement).checked });
  }

  protected async copriTutto(): Promise<void> {
    if (await this.ui.conferma('Tutte le zone già rivelate torneranno nascoste ai giocatori.', { titolo: 'Coprire tutta la mappa?', icona: '🌫️', ok: 'Copri tutto' })) {
      void this.api.op({ op: 'nebbia', azione: 'copri_tutto' });
    }
  }

  protected async pausa(): Promise<void> {
    if (await this.ui.conferma('La mappa si chiude per tutti finché non riprendi la partita.', { titolo: "Pausa: tutti in sala d'attesa?", icona: '⏸', ok: 'Metti in pausa' })) {
      void this.api.op({ op: 'sessione_pausa' });
    }
  }

  protected async esci(): Promise<void> {
    const nome = this.store.io()?.name;
    if (await this.ui.conferma('Potrai rientrare quando vuoi.', { titolo: `Uscire${nome ? ` da «${nome}»` : ''}?`, icona: '🚪', ok: 'Esci' })) this.conn.esci();
  }

  @HostListener('document:keydown', ['$event'])
  protected tasti(e: KeyboardEvent): void {
    if ((e.target as HTMLElement).closest('input,textarea,select') || this.ui.dialogo() || this.store.sistema()) return;
    const k = e.key.toLowerCase();
    if (k === 'v') this.strumento('muovi');
    else if (k === 'r') this.strumento('righello');
    else if (k === 'p') this.strumento('ping');
    else if (k === 'f' && this.store.master()) this.strumento('nebbia');
    else if (k === '+' || k === '=') this.vista.zoom(1.2);
    else if (k === '-') this.vista.zoom(1 / 1.2);
    else if (k === '0') this.vista.adatta();
    else if (k === 'escape') this.store.sel.set(null);
    else if ((k === 'delete' || k === 'backspace') && this.store.sel() && this.store.master()) {
      void this.api.op({ op: 'pedina_elimina', id: this.store.sel() });
      this.store.sel.set(null);
    } else if (k.startsWith('arrow') && this.store.sel()) {
      const p = this.store.stato()?.pedine[this.store.sel()!];
      if (!p || !this.store.puoMuovere(p)) return;
      e.preventDefault();
      const m = this.store.mappa();
      const c = cellaPx(m);
      const pos = posPedina(p, m);
      const d = ({ arrowup: [0, -1], arrowdown: [0, 1], arrowleft: [-1, 0], arrowright: [1, 0] } as Record<string, [number, number]>)[k];
      if (!d) return;
      const a = aggancia(pos.x + d[0] * c, pos.y + d[1] * c, p.taglia, m);
      this.store.aggiornaPedina({ ...p, x: a.x, y: a.y });
      void this.api.op({ op: 'pedina_muovi', id: p.id, x: a.x, y: a.y, finale: true });
    }
  }
}
