import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';

import { ApiService } from '../api/api.service';
import type { Personaggio } from '../api/avventura';
import type { Online } from '../api/generati/Online';
import { CredService } from '../core/cred.service';
import { UiService } from '../core/ui.service';
import { AzioniService } from '../stato/azioni.service';
import { TavoloStore } from '../stato/tavolo.store';

/** Sala d'attesa: l'amministratore apre il tavolo e sceglie il Master, i giocatori scelgono il personaggio. */
@Component({
  selector: 'app-sala',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div id="sala">
      <div class="card sala-card">
        @if (admin()) {
          <h2>{{ chiusa() ? "🛋️ Sala d'attesa" : store.avv().titolo }}</h2>
          <div class="sala-passi">
            <section>
              <h3>1 · Avventura</h3>
              @if (chiusa()) {
                <div class="sala-avv">
                  @for (a of store.stato()?.catalogo ?? []; track a.id) {
                    <button [class.attivo]="a.id === store.stato()?.attiva" (click)="apri(a.id)">
                      <b>{{ a.titolo }}</b><small>{{ a.sottotitolo || '' }} · liv. {{ a.livello || '?' }} · {{ a.personaggi }} personaggi</small>
                    </button>
                  } @empty {
                    <p>Nessuna avventura: caricane una dal pannello 👑 Master.</p>
                  }
                </div>
              } @else {
                <p>✅ <b>{{ store.avv().titolo }}</b> · i giocatori stanno scegliendo il personaggio. <button class="link" (click)="chiudi()">chiudi e cambia</button></p>
              }
            </section>
            <section>
              <h3>2 · Chi fa il Master?</h3>
              <ul class="online persone">
                @for (u of persone(); track u.id) {
                  <li class="persona" [style.--c]="u.color">
                    @if (u.avatar) {
                      <img [src]="u.avatar" alt="" />
                    } @else {
                      <span class="pallino"></span>
                    }
                    <span class="nome"
                      ><b>{{ u.name }}</b>
                      @if (u.id === store.io()?.id) {
                        <small>(tu)</small>
                      }
                      <br />
                      @if (u.role === 'master') {
                        <span class="chip attivo">👑 Master</span>
                      } @else {
                        <span class="aiuto">{{ descrizione(u) }}</span>
                      }
                    </span>
                    @if (u.role === 'master') {
                      <button class="link" title="Togli il ruolo di Master" (click)="nomina(u.id, false)">togli</button>
                    } @else {
                      <button title="Fai condurre la partita a questa persona" (click)="nomina(u.id, true)">👑 Rendi Master</button>
                    }
                  </li>
                } @empty {
                  <li class="aiuto">Nessuno collegato.</li>
                }
              </ul>
              <p class="aiuto">
                @if (store.ilMaster(); as m) {
                  Master: <b>{{ m.name }}</b>
                } @else {
                  Premi «👑 Rendi Master» accanto alla persona che condurrà la partita (anche te stesso).
                }
              </p>
            </section>
            <section>
              <h3>3 · Si parte</h3>
              <button id="sala-inizia" class="primario grande" [disabled]="chiusa() || !store.ilMaster()" (click)="inizia()">▶ Inizia la partita</button>
              <p class="aiuto">{{ chiusa() ? "Prima scegli l'avventura." : !store.ilMaster() ? 'Prima scegli il Master.' : 'Quando tutti hanno scelto il personaggio.' }}</p>
            </section>
          </div>
        } @else if (chiusa()) {
          <ol class="passi">
            @for (t of passi; track t; let k = $index) {
              <li [class.fatto]="k < 1" [class.ora]="k === 1"><span>{{ k < 1 ? '✓' : k + 1 }}</span>{{ t }}</li>
            }
          </ol>
          <h2>🛋️ Sala d'attesa</h2>
          <div class="sala-msg">⏳ <b>Sei dentro!</b><br />Un amministratore sta preparando la partita.<br />Appena sceglie l'avventura, <b>qui</b> potrai scegliere il tuo personaggio.</div>
          <h3>Chi c'è</h3>
          <ul class="online persone">
            @for (u of persone(); track u.id) {
              <li class="persona" [style.--c]="u.color"><span class="pallino"></span><span class="nome"><b>{{ u.name }}</b><br /><span class="aiuto">{{ descrizione(u) }}</span></span></li>
            }
          </ul>
        } @else if (store.master()) {
          <h2>{{ store.avv().titolo }}</h2>
          <p>👑 <b>Sei il Master!</b> Quando tutti hanno scelto il personaggio, fai iniziare la partita.</p>
          <ul class="online persone">
            @for (u of persone(); track u.id) {
              <li class="persona" [style.--c]="u.color"><span class="pallino"></span><span class="nome"><b>{{ u.name }}</b><br /><span class="aiuto">{{ descrizione(u) }}</span></span></li>
            }
          </ul>
          <button id="sala-inizia" class="primario grande" (click)="inizia()">▶ Inizia la partita</button>
        } @else {
          <ol class="passi">
            @for (t of passi; track t; let k = $index) {
              <li [class.fatto]="k < passo()" [class.ora]="k === passo()"><span>{{ k < passo() ? '✓' : k + 1 }}</span>{{ t }}</li>
            }
          </ol>
          @if (mio(); as p) {
            <h2>✅ Sei pronto!</h2>
            <p>Giocherai con:</p>
            <div class="pg-scelto" [style.--c]="p.colore || '#888'">
              <span class="ic">{{ p.icona }}</span>
              <div><b>{{ p.nome }}</b><small>{{ p.razza }} · {{ p.classe }}</small></div>
            </div>
            <div class="sala-msg">
              ⏳ Aspetta che il Master faccia iniziare la partita.<br />{{ testoMaster() }}<br /><small
                >Quando la partita inizia, la tua scheda completa è nella scheda 📜: lì tocchi abilità e attacchi per tirare i dadi.</small
              >
            </div>
            <button class="link" (click)="cambia.set(true)">↩ cambia personaggio</button>
          } @else if (!store.avv().personaggi.length) {
            <h2>{{ store.avv().titolo }}</h2>
            <div class="sala-msg">Questa avventura non ha personaggi pronti: giocherai come spettatore.<br />{{ testoMaster() }}</div>
          } @else {
            <h2>🎭 Scegli il tuo personaggio</h2>
            <p class="aiuto">{{ store.avv().titolo }} · {{ testoMaster() }}<br /><b>Tocca una carta</b> per leggere chi è, poi conferma.</p>
            @if (anteprimaPg(); as a) {
              <div id="sala-anteprima" class="anteprima" [style.--c]="a.colore || '#888'">
                <div class="testa"><span class="ic">{{ a.icona }}</span><div><b>{{ a.nome }}</b><small>{{ a.razza }} · {{ a.classe }}</small></div></div>
                <p>{{ a.chi || '' }}</p>
                @if (a.personalita) {
                  <p><b>Carattere:</b> {{ a.personalita }}</p>
                }
                @if (a.consiglio) {
                  <p class="aiuto">💡 {{ a.consiglio }}</p>
                }
                <div class="gruppo-btn">
                  <button class="primario grande" (click)="scegli(a.id)">✓ Gioco con {{ a.nome.split(' ')[0] }}</button>
                  <button class="link" (click)="anteprima.set(null)">guarda gli altri</button>
                </div>
              </div>
            }
            <div class="carte-pg">
              @for (p of store.avv().personaggi; track p.id) {
                <button
                  class="carta-pg"
                  [class.attiva]="anteprima() === p.id"
                  [class.presa]="!!presi()[p.id]"
                  [disabled]="!!presi()[p.id]"
                  [style.--c]="p.colore || '#888'"
                  (click)="anteprima.set(p.id)"
                >
                  <span class="ic">{{ p.icona }}</span>
                  <span class="testo"
                    ><b>{{ p.nome }}</b><small>{{ p.razza }} · {{ p.classe }}</small>
                    @if (p.sottotitolo) {
                      <em>{{ p.sottotitolo }}</em>
                    }
                    <span class="stat">🛡️ CA {{ p.ca }} · ❤️ PF {{ p.pf }}</span></span
                  >
                  @if (presi()[p.id]; as chi) {
                    <span class="badge">preso da {{ chi }}</span>
                  }
                </button>
              }
            </div>
          }
          <h3>Al tavolo</h3>
          <ul class="online persone">
            @for (u of persone(); track u.id) {
              <li class="persona" [style.--c]="u.color"><span class="pallino"></span><span class="nome"><b>{{ u.name }}</b><br /><span class="aiuto">{{ descrizione(u) }}</span></span></li>
            }
          </ul>
        }
      </div>
    </div>
  `,
})
export class SalaComponent {
  protected readonly store = inject(TavoloStore);
  private readonly api = inject(ApiService);
  private readonly ui = inject(UiService);
  private readonly azioni = inject(AzioniService);
  private readonly cred = inject(CredService);

  protected readonly passi = ['Accesso', 'Personaggio', 'Inizio partita'];
  protected readonly anteprima = signal<string | null>(null);
  protected readonly cambia = signal(false);
  protected readonly chiusa = computed(() => this.store.sessione() === 'chiusa');
  protected readonly admin = this.store.adminTavolo;
  /** L'account di sistema non compare nella sala: non gioca. */
  protected readonly persone = computed(() => this.store.online().filter((u) => !u.sistema));
  protected readonly presi = computed(() => {
    const io = this.store.io()?.id;
    const r: Record<string, string> = {};
    for (const u of this.store.online()) if (u.char && u.id !== io) r[u.char] = u.name;
    return r;
  });
  protected readonly mio = computed<Personaggio | null>(() => {
    const c = this.store.io()?.char;
    return c && !this.cambia() ? (this.store.personaggi().get(c) ?? null) : null;
  });
  protected readonly passo = computed(() => (this.mio() ? 2 : 1));
  protected readonly anteprimaPg = computed(() => {
    const a = this.anteprima();
    return a ? (this.store.personaggi().get(a) ?? null) : null;
  });
  protected readonly testoMaster = computed(() => {
    const m = this.store.ilMaster();
    return m ? `👑 Il Master è ${m.name}.` : '👑 Il Master non è ancora stato scelto.';
  });

  protected descrizione(u: Online): string {
    const pg = u.char ? this.store.personaggi().get(u.char) : undefined;
    if (pg) return `${pg.icona} ${pg.nome}`;
    if (u.admin) return '🔑 admin';
    return this.chiusa() ? 'in attesa' : 'sceglie il personaggio…';
  }

  protected apri(id: string): void {
    void this.api.op({ op: 'sessione_apri', id });
  }

  protected nomina(id: string, master: boolean): void {
    void this.api.op({ op: 'nomina_master', id, master });
  }

  protected inizia(): void {
    void this.api.op({ op: 'sessione_inizia' });
  }

  protected async chiudi(): Promise<void> {
    if (await this.ui.conferma('La partita resta salvata: potrai riaprirla quando vuoi.', { titolo: 'Chiudere e cambiare avventura?', icona: '🔒', ok: 'Chiudi il tavolo' })) {
      void this.api.op({ op: 'sessione_chiudi' });
    }
  }

  protected async scegli(pg: string): Promise<void> {
    if (await this.azioni.scegliPersonaggio(pg)) {
      this.cred.aggiorna({ personaggio: pg });
      this.anteprima.set(null);
      this.cambia.set(false);
    }
  }
}
