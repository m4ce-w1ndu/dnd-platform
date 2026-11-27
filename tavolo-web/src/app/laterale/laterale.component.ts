import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';

import { type Scheda, TavoloStore } from '../stato/tavolo.store';
import { DadiComponent } from './dadi.component';
import { GruppoComponent } from './gruppo.component';
import { IniziativaComponent } from './iniziativa.component';
import { MasterComponent } from './master.component';
import { SchedaComponent } from './scheda.component';

/** Il pannello laterale con le schede: dadi, personaggio, turni, gruppo, Master. */
@Component({
  selector: 'app-laterale',
  imports: [DadiComponent, SchedaComponent, IniziativaComponent, GruppoComponent, MasterComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <aside id="laterale" [class.aperto]="store.pannelloAperto()">
      <nav id="schede-nav" (dblclick)="chiudiSuTelefono()">
        @for (s of schede(); track s.id) {
          <button [class.attivo]="attiva() === s.id" (click)="apri(s.id)">{{ s.ic }}<span>{{ s.nome }}</span></button>
        }
      </nav>
      <div class="tab" id="tab-dadi" [class.attivo]="attiva() === 'dadi'"><app-dadi /></div>
      <div class="tab" id="tab-scheda" [class.attivo]="attiva() === 'scheda'">
        @if (attiva() === 'scheda') {
          <app-scheda />
        }
      </div>
      <div class="tab" id="tab-iniziativa" [class.attivo]="attiva() === 'iniziativa'"><app-iniziativa /></div>
      <div class="tab" id="tab-gruppo" [class.attivo]="attiva() === 'gruppo'">
        @if (attiva() === 'gruppo') {
          <app-gruppo />
        }
      </div>
      @if (store.master()) {
        <div class="tab" id="tab-master" [class.attivo]="attiva() === 'master'"><app-master /></div>
      }
    </aside>
  `,
})
export class LateraleComponent {
  protected readonly store = inject(TavoloStore);
  protected readonly schede = computed(() => {
    const l: { id: Scheda; ic: string; nome: string }[] = [
      { id: 'dadi', ic: '🎲', nome: 'Dadi' },
      { id: 'scheda', ic: '📜', nome: 'Scheda' },
      { id: 'iniziativa', ic: '⚔️', nome: 'Turni' },
      { id: 'gruppo', ic: '👥', nome: 'Gruppo' },
    ];
    if (this.store.master()) l.push({ id: 'master', ic: '👑', nome: 'Master' });
    return l;
  });
  /** Se il Master torna giocatore mentre era sulla scheda Master, si torna ai dadi. */
  protected readonly attiva = computed<Scheda>(() => (this.store.scheda() === 'master' && !this.store.master() ? 'dadi' : this.store.scheda()));

  protected apri(s: Scheda): void {
    this.store.scheda.set(s);
    if (innerWidth < 860) this.store.pannelloAperto.set(true);
  }

  protected chiudiSuTelefono(): void {
    if (innerWidth < 860) this.store.pannelloAperto.set(false);
  }
}
