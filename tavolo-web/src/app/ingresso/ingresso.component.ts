import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DomSanitizer } from '@angular/platform-browser';

import { ConnessioneService } from '../core/connessione.service';
import { TavoloStore } from '../stato/tavolo.store';
import { LOGHI } from './loghi';

/** Primo passo: chi sei? (account Discord/Google/GitHub, ospite o amministratore). */
@Component({
  selector: 'app-ingresso',
  imports: [FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div id="ingresso" class="modale aperta">
      <div class="card ingresso-card">
        <div class="logo">🐉</div>
        <h1>{{ titolo() }}</h1>
        <p class="sotto">{{ sotto() }}</p>

        @if (conn.passo() === 'login') {
          <div>
            @if (provider().length) {
              <div class="oauth">
                @for (l of provider(); track l.id) {
                  <a [class]="l.id" [href]="'/auth/' + l.id + '/start'"><span [innerHTML]="logo(l.id)"></span><span>Accedi con {{ l.nome }}</span></a>
                }
              </div>
            }
            @if (info()?.ospiti) {
              <div id="in-ospite">
                @if (provider().length) {
                  <div class="oppure"><span>oppure entra come ospite</span></div>
                }
                <label>Il tuo nome<input [(ngModel)]="nome" maxlength="30" placeholder="es. Giulia" autocomplete="nickname" (keydown.enter)="ospite()" /></label>
                @if (info()?.password_giocatori) {
                  <label>Password del tavolo<input [(ngModel)]="pwTavolo" type="password" placeholder="chiedila al Master" (keydown.enter)="ospite()" /></label>
                }
                <button class="primario grande" (click)="ospite()">Entra come ospite</button>
              </div>
            }
            <details class="admin-box" [open]="adminAperto()">
              <summary>🔑 Amministrazione del sistema</summary>
              <label>Utente <small class="aiuto">(di solito: admin)</small><input [(ngModel)]="utente" autocomplete="username" autocapitalize="none" spellcheck="false" /></label>
              <label
                >Password
                <span class="pw-riga"
                  ><input [(ngModel)]="pw" [type]="vediPw() ? 'text' : 'password'" autocomplete="current-password" autocapitalize="none" spellcheck="false" (keydown.enter)="admin()" /><button
                    type="button"
                    title="Mostra la password"
                    (click)="vediPw.set(!vediPw())"
                  >
                    {{ vediPw() ? '🙈' : '👁' }}
                  </button></span
                >
              </label>
              <p class="aiuto" style="margin:0">Questo accesso serve solo a configurare il sistema e assegnare i permessi. Per giocare o aprire il tavolo entra con il tuo account.</p>
              <button class="primario" (click)="admin()">Accedi</button>
            </details>
          </div>
        } @else {
          <div class="chiuso-box">Entro nella sala d'attesa…</div>
        }
        <div class="errore">{{ conn.errore() }}</div>
      </div>
    </div>
  `,
})
export class IngressoComponent {
  protected readonly conn = inject(ConnessioneService);
  private readonly store = inject(TavoloStore);
  private readonly san = inject(DomSanitizer);

  protected readonly info = this.store.info;
  protected readonly provider = computed(() => this.info()?.login ?? []);
  protected readonly titolo = computed(() => {
    const i = this.info();
    if (!i) return 'Tavolo Virtuale';
    return i.sessione === 'chiusa' ? i.nome_tavolo || 'Tavolo Virtuale' : i.avventura.titolo || i.nome_tavolo || 'Tavolo Virtuale';
  });
  protected readonly sotto = computed(() => {
    const i = this.info();
    if (!i || i.sessione === 'chiusa') return 'Accedi per entrare. Il tavolo si aprirà quando un amministratore avvia una partita.';
    return i.avventura.sottotitolo || 'Accedi per sederti al tavolo.';
  });
  protected readonly adminAperto = computed(() => this.conn.loginAdmin() || (!this.provider().length && !this.info()?.ospiti));
  protected readonly vediPw = signal(false);

  protected nome = '';
  protected pwTavolo = '';
  protected utente = 'admin';
  protected pw = '';

  /** I loghi sono SVG costanti scritti qui (non dati esterni): si possono inserire così come sono. */
  protected logo(id: string) {
    return this.san.bypassSecurityTrustHtml(LOGHI[id] ?? '');
  }

  protected ospite(): void {
    void this.conn.login({ tipo: 'ospite', nome: this.nome, password: this.pwTavolo });
  }

  protected admin(): void {
    void this.conn.login({ tipo: 'admin', utente: this.utente, password: this.pw });
  }
}
