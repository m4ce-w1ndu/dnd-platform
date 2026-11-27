import { ChangeDetectionStrategy, Component, HostListener, OnInit, inject } from '@angular/core';

import { ConnessioneService } from './core/connessione.service';
import { UiService } from './core/ui.service';
import { IngressoComponent } from './ingresso/ingresso.component';
import { TavoloComponent } from './tavolo/tavolo.component';

@Component({
  selector: 'app-root',
  imports: [IngressoComponent, TavoloComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (conn.schermata() === 'ingresso') {
      <app-ingresso />
    } @else {
      <app-tavolo />
    }
    @if (ui.dialogo(); as d) {
      <div class="dialogo" (click)="$event.target === $event.currentTarget && d.risolvi(false)">
        <div class="dialogo-card" [class.pericolo]="d.pericolo" role="dialog" aria-modal="true">
          <div class="dialogo-ic">{{ d.icona || (d.pericolo ? '⚠️' : '❓') }}</div>
          <h3>{{ d.titolo || 'Sei sicuro?' }}</h3>
          <p>{{ d.testo }}</p>
          <div class="dialogo-btn">
            @if (!d.soloOk) {
              <button class="annulla" (click)="d.risolvi(false)">{{ d.annulla || 'Annulla' }}</button>
            }
            <button class="ok" [class.rosso]="d.pericolo" [class.primario]="!d.pericolo" (click)="d.risolvi(true)" autofocus>{{ d.ok || 'Conferma' }}</button>
          </div>
        </div>
      </div>
    }
    <div id="toast">
      @for (t of ui.toasts(); track t.id) {
        <div>{{ t.testo }}</div>
      }
    </div>
  `,
})
export class App implements OnInit {
  protected readonly conn = inject(ConnessioneService);
  protected readonly ui = inject(UiService);

  ngOnInit(): void {
    void this.conn.avvio();
  }

  @HostListener('document:keydown', ['$event'])
  tasti(e: KeyboardEvent): void {
    const d = this.ui.dialogo();
    if (!d) return;
    if (e.key === 'Escape') {
      e.preventDefault();
      d.risolvi(false);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      d.risolvi(true);
    }
  }
}
