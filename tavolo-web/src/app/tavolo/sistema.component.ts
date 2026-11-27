import { NgTemplateOutlet } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnInit,
  computed,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { DomSanitizer } from '@angular/platform-browser';

import { ApiService } from '../api/api.service';
import type {
  ConfigPubblica,
  PartitaSalvata,
  UtenteImpostazioni,
  VoceAudit,
} from '../api/avventura';
import { UiService } from '../core/ui.service';
import { LOGHI } from '../ingresso/loghi';
import { TavoloStore } from '../stato/tavolo.store';

type FormProvider = FormGroup<{
  attivo: import('@angular/forms').FormControl<boolean>;
  id: import('@angular/forms').FormControl<string>;
  secret: import('@angular/forms').FormControl<string>;
}>;

const AZIONI: Record<string, string> = {
  login_admin: '🔑 accesso di sistema',
  login_admin_fallito: '⛔ password di sistema sbagliata',
  login_oauth: '👤 accesso con account',
  login_admin_oauth: '👤 accesso di un amministratore',
  password_admin_convertita_argon2: '🔒 password convertita ad Argon2',
  imp_salva: '⚙️ impostazioni salvate',
  imp_admin: '🔑 account di sistema cambiato',
  imp_admin_password_errata: '⛔ password attuale sbagliata',
  utente_permessi: '👥 permessi cambiati',
  utente_eliminato: '🗑️ utente eliminato',
  utenti_eliminati: '🧹 pulizia degli utenti',
  sessione_apri: '🚪 tavolo aperto',
  nomina_master: '👑 Master scelto',
  reset_partita: '♻️ partita ricominciata',
  imp_partita_azzera: '♻️ partita azzerata',
  importa_partita: '📥 partita importata',
  carica_avventura: '📦 avventura caricata',
  avventura_elimina: '🗑️ avventura eliminata',
  mappa_elimina: '🗑️ mappa eliminata',
  backup: '💾 backup scaricato',
};

type Sezione = 'generale' | 'oauth' | 'utenti' | 'dati' | 'audit' | 'account';
type Filtro = 'tutti' | 'admin' | 'account' | 'ospiti';
const CHIAVE_SEZIONE = 'tv_sistema_sezione';
const GIORNO = 86400;

/** La pagina dell'account di sistema: configurazione, permessi, dati e registro di audit. Niente mappa. */
@Component({
  selector: 'app-sistema',
  imports: [ReactiveFormsModule, NgTemplateOutlet],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="sis">
      <nav class="sis-nav" aria-label="Sezioni">
        @for (x of sezioni; track x.id) {
          <button [class.attivo]="sezione() === x.id" (click)="vai(x.id)">
            <span class="ic">{{ x.ic }}</span><span class="t">{{ x.nome }}</span>
            @if (x.id === 'utenti' && daPulire().length) {
              <span class="bolla" title="utenti da pulire">{{ daPulire().length }}</span>
            }
          </button>
        }
      </nav>

      <div class="sis-corpo">
        <div class="sis-pagina" id="tab-impostazioni">
          @switch (sezione()) {
            @case ('generale') {
              <h2>🏰 Generale</h2>
              <p class="aiuto">
                Sei l'<b>account di sistema</b>: configuri il tavolo e decidi chi è amministratore.
                Il tavolo lo aprono e lo conducono gli amministratori, entrando con il loro account.
              </p>
              <form [formGroup]="generale" class="blocco">
                <label
                  >Nome del tavolo<input formControlName="nome_tavolo" autocomplete="off"
                /></label>
                <label
                  >Indirizzo pubblico (per l'accesso con account)<input
                    formControlName="public_url"
                    type="url"
                    inputmode="url"
                    autocomplete="url"
                    placeholder="https://dnd.immovilli.trade"
                /></label>
                <p class="aiuto">
                  Lascia vuoto per usare l'indirizzo con cui apri la pagina. Va impostato se usi
                  l'accesso con account dietro un proxy.
                </p>
              </form>
              <h3>🚪 Accesso dei giocatori</h3>
              <form [formGroup]="generale" class="blocco">
                <label class="switch"
                  ><input type="checkbox" formControlName="ospiti" /> ammetti ospiti (senza account,
                  solo il nome)</label
                >
                <label
                  >Password del tavolo (facoltativa)<input
                    formControlName="password_giocatori"
                    autocomplete="off"
                    placeholder="vuota = nessuna password"
                /></label>
                <p class="aiuto">
                  Se attivi un provider e disattivi gli ospiti, si entra solo con
                  Discord/Google/GitHub.
                </p>
              </form>
              <ng-container *ngTemplateOutlet="salvaBarra" />
            }

            @case ('oauth') {
              <h2>🔑 Accesso con account</h2>
              <p class="aiuto">
                Discord, Google e GitHub: attiva quelli che vuoi e incolla le credenziali dell'app
                registrata sulla loro console.
              </p>
              @for (p of provider(); track p.id) {
                <div class="prov" [formGroup]="p.form">
                  <label class="switch"
                    ><input type="checkbox" formControlName="attivo" />
                    <span class="logo-prov" [class]="p.id" [innerHTML]="logo(p.id)"></span
                    ><b>{{ p.conf.nome }}</b>
                    @if (p.conf.attivo && p.conf.id && p.conf.secret_impostato) {
                      <span class="chip attivo">attivo</span>
                    }
                  </label>
                  <label>Client ID<input formControlName="id" autocomplete="off" /></label>
                  <label
                    >Client Secret<input
                      formControlName="secret"
                      type="text"
                      class="segreto"
                      autocomplete="off"
                      spellcheck="false"
                      [placeholder]="
                        p.conf.secret_impostato
                          ? '•••••• (impostato: scrivi solo per cambiarlo)'
                          : 'incolla qui il secret'
                      "
                  /></label>
                  <span class="aiuto"
                    >Redirect URI da registrare su
                    <a [href]="p.conf.console" target="_blank" rel="noopener">{{
                      p.conf.nome
                    }}</a>:</span
                  >
                  <code>{{ base() }}/auth/{{ p.id }}/callback</code>
                </div>
              }
              <ng-container *ngTemplateOutlet="salvaBarra" />
            }

            @case ('utenti') {
              <h2>👥 Utenti e permessi</h2>
              <p class="aiuto">
                <b>Admin</b> = amministratore del tavolo: apre il tavolo, sceglie il Master e può
                fare il Master. <b>Master</b> = può condurre le partite.
              </p>

              @if (doppioni().length || ospitiVecchi().length) {
                <div class="pulizia">
                  <div>
                    <b>🧹 Pulizia</b>
                    <small>
                      @if (doppioni().length) {
                        {{ doppioni().length }}
                        {{ doppioni().length === 1 ? 'vecchia copia' : 'vecchie copie' }}
                        dell'account di sistema
                      }
                      @if (doppioni().length && ospitiVecchi().length) {
                        ·
                      }
                      @if (ospitiVecchi().length) {
                        {{ ospitiVecchi().length }}
                        {{ ospitiVecchi().length === 1 ? 'ospite' : 'ospiti' }} non
                        {{ ospitiVecchi().length === 1 ? 'visto' : 'visti' }} da più di
                      }
                      <select
                        [value]="giorni()"
                        (change)="giorni.set(+$any($event.target).value)"
                        aria-label="giorni"
                      >
                        @for (g of [1, 7, 30, 90]; track g) {
                          <option [value]="g" [selected]="g === giorni()">
                            {{ g === 1 ? '1 giorno' : g + ' giorni' }}
                          </option>
                        }
                      </select>
                    </small>
                  </div>
                  <button class="primario" [disabled]="!daPulire().length" (click)="pulisci()">
                    Elimina {{ daPulire().length }}
                  </button>
                </div>
              } @else {
                <div class="pulizia ok">
                  <small
                    >✨ Niente da pulire: nessuna copia dell'account di sistema e nessun ospite
                    fermo da più di</small
                  >
                  <select
                    [value]="giorni()"
                    (change)="giorni.set(+$any($event.target).value)"
                    aria-label="giorni"
                  >
                    @for (g of [1, 7, 30, 90]; track g) {
                      <option [value]="g" [selected]="g === giorni()">
                        {{ g === 1 ? '1 giorno' : g + ' giorni' }}
                      </option>
                    }
                  </select>
                </div>
              }

              <div class="riga filtri">
                <input
                  type="search"
                  placeholder="🔎 Cerca per nome o account"
                  [value]="cerca()"
                  (input)="cerca.set($any($event.target).value)"
                />
                <div class="gruppo-btn">
                  @for (f of filtri; track f.id) {
                    <button [class.attivo]="filtro() === f.id" (click)="filtro.set(f.id)">
                      {{ f.nome }} <small>{{ conta()[f.id] }}</small>
                    </button>
                  }
                </div>
              </div>

              @for (x of utentiVisti(); track x.id) {
                <div class="utente" [class.da-pulire]="daPulireIds().has(x.id)">
                  @if (x.avatar) {
                    <img [src]="x.avatar" alt="" />
                  } @else {
                    <span class="av">{{ x.sistema ? '⚙️' : '👤' }}</span>
                  }
                  <div class="n">
                    <b>{{ x.nome }}</b>{{ x.io ? ' (tu)' : '' }} {{ x.online ? '🟢' : '' }}
                    @if (x.sistema) {
                      <span class="chip">{{ x.io ? 'sistema' : 'copia vecchia' }}</span>
                    } @else if (x.admin) {
                      <span class="chip attivo">admin</span>
                    }
                    <small
                      >{{ x.sistema ? 'account di sistema' : x.provider
                      }}{{ x.account ? ' · ' + x.account : '' }} · visto
                      {{ quando(x.visto) }}</small
                    >
                  </div>
                  @if (!x.sistema) {
                    <label class="switch" title="Può condurre le partite"
                      ><input
                        type="checkbox"
                        [checked]="x.master"
                        [disabled]="x.admin"
                        (change)="permesso(x, 'master', $event)"
                      />
                      Master</label
                    >
                    <label class="switch" title="Apre il tavolo e sceglie il Master"
                      ><input
                        type="checkbox"
                        [checked]="x.admin"
                        (change)="permesso(x, 'admin', $event)"
                      />
                      Admin</label
                    >
                  }
                  @if (!x.io) {
                    <button class="link" title="Elimina" (click)="elimina(x)">🗑️</button>
                  }
                </div>
              } @empty {
                <p class="aiuto">Nessun utente.</p>
              }
            }

            @case ('dati') {
              <h2>💾 Partite e backup</h2>
              <p class="aiuto">
                Tutto è salvato nel database <code>dati/tavolo.db</code> (SQLite): partite, utenti,
                impostazioni.
              </p>
              <a
                class="btn primario"
                [href]="link('/api/backup')"
                style="display:block;margin:8px 0 14px"
                >⬇️ Scarica backup del database</a
              >
              @for (x of partite(); track x.id) {
                <div class="utente">
                  <span class="av">📜</span>
                  <div class="n">
                    <b>{{ x.titolo }}</b>
                    @if (x.in_gioco) {
                      <span class="chip attivo">in gioco</span>
                    }
                    <small
                      >salvata {{ quando(x.aggiornata) }} · {{ x.pedine }} pedine ·
                      {{ x.tiri }} tiri · round {{ x.round }}</small
                    >
                  </div>
                  <a class="btn" [href]="link('/api/esporta?id=' + enc(x.id))" title="Scarica">⬇️</a
                  ><button class="link" title="Ricomincia da zero" (click)="azzera(x)">♻️</button>
                </div>
              } @empty {
                <p class="aiuto">Nessuna partita salvata.</p>
              }
            }

            @case ('audit') {
              <h2>📋 Registro di audit</h2>
              <div class="riga">
                <span class="aiuto" style="flex:1"
                  >Accessi di sistema, permessi, impostazioni e cancellazioni, dal più
                  recente.</span
                >
                <button (click)="leggiAudit()">🔄 Aggiorna</button>
              </div>
              @for (a of audit(); track $index) {
                <div class="utente">
                  <div class="n">
                    <b>{{ etichetta(a.azione) }}</b>
                    <small
                      >{{ quando(a.ora) }} · {{ a.nome || a.utente || '—' }} · {{ a.ip || '—'
                      }}{{ dettagli(a) }}</small
                    >
                  </div>
                </div>
              } @empty {
                <p class="aiuto">Nessuna voce.</p>
              }
            }

            @case ('account') {
              <h2>🔐 Account di sistema</h2>
              <p class="aiuto">
                Nome utente e password con cui entri qui. Per cambiarli serve la password attuale.
              </p>
              <form [formGroup]="account" class="blocco">
                <label
                  >Nome utente<input
                    formControlName="utente"
                    autocomplete="off"
                    data-lpignore="true"
                /></label>
                <label
                  >Nuova password (almeno 8 caratteri)<input
                    formControlName="nuova"
                    type="password"
                    autocomplete="new-password"
                /></label>
                <label
                  >Ripeti la nuova password<input
                    formControlName="nuova2"
                    type="password"
                    autocomplete="new-password"
                /></label>
                <label
                  >Password attuale (per confermare)<input
                    formControlName="attuale"
                    type="password"
                    autocomplete="current-password"
                /></label>
                <button type="button" class="primario" (click)="salvaAccount()">
                  Aggiorna account di sistema
                </button>
              </form>
            }
          }
        </div>
      </div>
    </div>

    <ng-template #salvaBarra>
      <div class="salva-barra" [class.sporco]="modificato()">
        <span class="aiuto">{{
          modificato() ? 'Ci sono modifiche non salvate.' : 'Tutto salvato.'
        }}</span>
        <button type="button" class="primario" [disabled]="!modificato()" (click)="salva()">
          💾 Salva
        </button>
      </div>
    </ng-template>
  `,
  styles: `
    :host {
      flex: 1;
      display: flex;
      min-height: 0;
      min-width: 0;
    }
    .sis {
      flex: 1;
      display: flex;
      min-height: 0;
      min-width: 0;
    }
    .sis-nav {
      width: 210px;
      flex: none;
      display: flex;
      flex-direction: column;
      gap: 2px;
      padding: 12px 8px;
      background: var(--pan);
      border-right: 1px solid var(--linea);
      overflow: auto;
    }
    .sis-nav button {
      display: flex;
      align-items: center;
      gap: 10px;
      text-align: left;
      border: 1px solid transparent;
      background: none;
      padding: 9px 10px;
      color: var(--muto);
    }
    .sis-nav button:hover {
      background: var(--pan2);
      color: var(--testo);
    }
    .sis-nav button.attivo {
      background: #3a2f1e;
      border-color: var(--oro);
      color: var(--oro2);
    }
    .sis-nav .ic {
      font-size: 17px;
      width: 22px;
      text-align: center;
    }
    .sis-nav .t {
      flex: 1;
    }
    .bolla {
      background: var(--rosso);
      color: #fff;
      border-radius: 10px;
      font-size: 11px;
      padding: 1px 7px;
      font-weight: 700;
    }
    .sis-corpo {
      flex: 1;
      overflow: auto;
      padding: 20px 16px 40px;
      min-width: 0;
    }
    .sis-pagina {
      max-width: 760px;
      margin: 0 auto;
    }
    h2 {
      font-family: var(--serif);
      color: var(--oro2);
      margin: 0 0 6px;
      font-size: 22px;
    }
    .blocco {
      display: flex;
      flex-direction: column;
      gap: 4px;
      background: var(--pan);
      border: 1px solid var(--linea);
      border-radius: 12px;
      padding: 10px 14px;
      margin: 10px 0;
    }
    .salva-barra {
      position: sticky;
      bottom: -40px;
      margin-top: 14px;
      display: flex;
      align-items: center;
      gap: 10px;
      justify-content: space-between;
      padding: 10px 14px;
      border-radius: 12px;
      background: var(--pan);
      border: 1px solid var(--linea);
    }
    .salva-barra.sporco {
      border-color: var(--oro);
      box-shadow: 0 -6px 20px rgba(0, 0, 0, 0.5);
    }
    .salva-barra button:disabled {
      opacity: 0.45;
      cursor: default;
    }
    .pulizia {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 10px 14px;
      margin: 10px 0;
      border-radius: 12px;
      border: 1px solid var(--oro);
      background: #2a2216;
    }
    .pulizia > div {
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 2px;
    }
    .pulizia small {
      color: var(--muto);
    }
    .pulizia.ok {
      border-color: var(--linea);
      background: var(--pan);
      flex-wrap: wrap;
      gap: 6px;
    }
    .pulizia select {
      padding: 2px 6px;
      margin-left: 4px;
    }
    .filtri {
      margin: 12px 0 4px;
    }
    .filtri input {
      flex: 1 1 200px;
    }
    .filtri small {
      color: var(--muto);
      margin-left: 2px;
    }
    .utente.da-pulire {
      opacity: 0.55;
    }
    .utente .chip {
      border: 1px solid var(--linea);
      margin-left: 4px;
      font-size: 11px;
      padding: 1px 7px;
    }
    @media (max-width: 760px) {
      .sis {
        flex-direction: column;
      }
      .sis-nav {
        width: auto;
        flex-direction: row;
        border-right: none;
        border-bottom: 1px solid var(--linea);
        padding: 6px;
        gap: 4px;
        overflow-x: auto;
      }
      .sis-nav button {
        flex-direction: column;
        gap: 2px;
        padding: 6px 8px;
        font-size: 11px;
        position: relative;
        flex: none;
      }
      .sis-nav .t {
        flex: none;
        white-space: nowrap;
      }
      .bolla {
        position: absolute;
        top: 0;
        right: 0;
      }
      .sis-corpo {
        padding: 14px 12px 40px;
      }
      .utente {
        flex-wrap: wrap;
      }
      .utente .n {
        flex-basis: calc(100% - 40px);
      }
    }
  `,
})
export class SistemaComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly ui = inject(UiService);
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly san = inject(DomSanitizer);
  private readonly distrutto = inject(DestroyRef);

  protected readonly sezioni: { id: Sezione; ic: string; nome: string }[] = [
    { id: 'generale', ic: '🏰', nome: 'Generale' },
    { id: 'oauth', ic: '🔑', nome: 'Accesso con account' },
    { id: 'utenti', ic: '👥', nome: 'Utenti e permessi' },
    { id: 'dati', ic: '💾', nome: 'Partite e backup' },
    { id: 'audit', ic: '📋', nome: 'Registro' },
    { id: 'account', ic: '🔐', nome: 'Account di sistema' },
  ];
  protected readonly sezione = signal<Sezione>(this.sezioneSalvata());

  protected readonly filtri: { id: Filtro; nome: string }[] = [
    { id: 'tutti', nome: 'Tutti' },
    { id: 'admin', nome: 'Admin' },
    { id: 'account', nome: 'Con account' },
    { id: 'ospiti', nome: 'Ospiti' },
  ];
  protected readonly filtro = signal<Filtro>('tutti');
  protected readonly cerca = signal('');
  protected readonly giorni = signal(30);
  protected readonly modificato = signal(false);

  protected readonly config = signal<ConfigPubblica | null>(null);
  protected readonly utenti = signal<UtenteImpostazioni[]>([]);
  protected readonly partite = signal<PartitaSalvata[]>([]);
  protected readonly audit = signal<VoceAudit[]>([]);
  protected readonly base = computed(() => this.config()?.public_url || location.origin);

  /** Copie dell'account di sistema nate col server Python (una per browser): quella in uso resta. */
  protected readonly doppioni = computed(() =>
    this.utenti().filter((x) => x.sistema && !x.io && !x.online),
  );
  /** Ospiti senza permessi, scollegati e non visti da più di `giorni`. */
  protected readonly ospitiVecchi = computed(() => {
    const limite = Date.now() / 1000 - this.giorni() * GIORNO;
    return this.utenti().filter(
      (x) =>
        !x.sistema &&
        !x.account &&
        !x.admin &&
        !x.master &&
        !x.online &&
        !x.io &&
        (x.visto || 0) < limite,
    );
  });
  protected readonly daPulire = computed(() => [...this.doppioni(), ...this.ospitiVecchi()]);
  protected readonly daPulireIds = computed(() => new Set(this.daPulire().map((x) => x.id)));

  private readonly ordinati = computed(() =>
    [...this.utenti()].sort(
      (a, b) =>
        +b.io - +a.io ||
        +b.admin - +a.admin ||
        +!!b.account - +!!a.account ||
        +b.online - +a.online ||
        (b.visto || 0) - (a.visto || 0),
    ),
  );
  private passa(x: UtenteImpostazioni, f: Filtro): boolean {
    switch (f) {
      case 'admin':
        return x.admin && !x.sistema;
      case 'account':
        return !!x.account && !x.sistema;
      case 'ospiti':
        return !x.account && !x.sistema;
      default:
        return true;
    }
  }
  protected readonly conta = computed(() => {
    const c: Record<Filtro, number> = { tutti: 0, admin: 0, account: 0, ospiti: 0 };
    for (const x of this.utenti()) for (const f of this.filtri) if (this.passa(x, f.id)) c[f.id]++;
    return c;
  });
  protected readonly utentiVisti = computed(() => {
    const q = this.cerca().trim().toLowerCase();
    const f = this.filtro();
    return this.ordinati().filter(
      (x) =>
        this.passa(x, f) &&
        (!q || x.nome.toLowerCase().includes(q) || x.account.toLowerCase().includes(q)),
    );
  });

  protected readonly generale = this.fb.group({
    nome_tavolo: ['', Validators.maxLength(200)],
    public_url: [''],
    ospiti: [true],
    password_giocatori: [''],
  });
  protected readonly account = this.fb.group({
    utente: ['', Validators.maxLength(40)],
    nuova: [''],
    nuova2: [''],
    attuale: [''],
  });
  private readonly formProvider = new Map<string, FormProvider>();
  protected readonly provider = computed(() =>
    Object.entries(this.config()?.oauth ?? {}).map(([id, conf]) => ({
      id,
      conf,
      form: this.formProvider.get(id) ?? this.nuovoProvider(id),
    })),
  );

  constructor() {
    this.generale.valueChanges
      .pipe(takeUntilDestroyed())
      .subscribe(() => this.aggiornaModificato());
    // quando qualcuno entra o esce, l'elenco degli utenti si aggiorna da solo
    const store = inject(TavoloStore);
    let primo = true;
    effect(() => {
      store.online();
      if (primo) {
        primo = false;
        return;
      }
      // chi entra ed esce a raffica (o il proprio collegamento appena aperta la pagina) vale una lettura sola
      clearTimeout(this.timerUtenti);
      this.timerUtenti = setTimeout(() => untracked(() => void this.leggiUtenti()), 1000);
    });
    inject(DestroyRef).onDestroy(() => clearTimeout(this.timerUtenti));
  }

  private timerUtenti: ReturnType<typeof setTimeout> | undefined;
  private lettoAlle = 0;

  ngOnInit(): void {
    void this.leggi();
    void this.leggiAudit();
  }

  private async leggiUtenti(): Promise<void> {
    if (Date.now() - this.lettoAlle < 1500) return; // appena letti da leggi()
    const r = await this.api.op({ op: 'imp_leggi' }, { silenzioso: true });
    if (r.ok) this.utenti.set(r.utenti ?? []);
  }

  private nuovoProvider(id: string): FormProvider {
    const f: FormProvider = this.fb.group({ attivo: [false], id: [''], secret: [''] });
    f.valueChanges
      .pipe(takeUntilDestroyed(this.distrutto))
      .subscribe(() => this.aggiornaModificato());
    this.formProvider.set(id, f);
    return f;
  }

  private async leggi(): Promise<void> {
    this.lettoAlle = Date.now();
    const r = await this.api.op({ op: 'imp_leggi' });
    if (!r.ok || !r.config) return;
    this.applica(r.config);
    this.utenti.set(r.utenti ?? []);
    const p = await this.api.op({ op: 'imp_partite' });
    if (p.ok) this.partite.set(p.partite ?? []);
  }

  private applica(c: ConfigPubblica): void {
    this.generale.reset({
      nome_tavolo: c.nome_tavolo,
      public_url: c.public_url,
      ospiti: c.ospiti,
      password_giocatori: c.password_giocatori,
    });
    this.account.reset({ utente: c.admin_utente, nuova: '', nuova2: '', attuale: '' });
    for (const [id, v] of Object.entries(c.oauth)) {
      (this.formProvider.get(id) ?? this.nuovoProvider(id)).reset({
        attivo: v.attivo,
        id: v.id,
        secret: '',
      });
    }
    this.config.set(c);
    this.modificato.set(false);
  }

  private aggiornaModificato(): void {
    this.modificato.set(
      this.generale.dirty || [...this.formProvider.values()].some((f) => f.dirty),
    );
  }

  private sezioneSalvata(): Sezione {
    try {
      const v = localStorage.getItem(CHIAVE_SEZIONE) as Sezione | null;
      if (v && this.sezioni.some((x) => x.id === v)) return v;
    } catch {
      /* niente storage: si parte da Generale */
    }
    return 'generale';
  }

  protected vai(s: Sezione): void {
    this.sezione.set(s);
    try {
      localStorage.setItem(CHIAVE_SEZIONE, s);
    } catch {
      /* pazienza */
    }
    if (s === 'audit') void this.leggiAudit();
  }

  protected async pulisci(): Promise<void> {
    const via = this.daPulire();
    if (!via.length) return;
    const nomi =
      via
        .slice(0, 8)
        .map((x) => x.nome)
        .join(', ') + (via.length > 8 ? ` e altri ${via.length - 8}` : '');
    const ok = await this.ui.conferma(`${nomi}. Chi rientra dovrà rifare l'accesso da capo.`, {
      titolo: `Eliminare ${via.length} ${via.length === 1 ? 'utente' : 'utenti'}?`,
      icona: '🧹',
      pericolo: true,
      ok: 'Elimina',
    });
    if (!ok) return;
    const r = await this.api.op({ op: 'imp_utenti_elimina', ids: via.map((x) => x.id) });
    if (r.ok) this.ui.toast(`🧹 ${r.eliminati ?? via.length} utenti eliminati`);
    await this.leggi();
  }

  async leggiAudit(): Promise<void> {
    this.audit.set(await this.api.audit());
  }

  protected logo(id: string) {
    return this.san.bypassSecurityTrustHtml(LOGHI[id] ?? '');
  }

  protected link(path: string): string {
    return this.api.link(path);
  }

  protected enc(s: string): string {
    return encodeURIComponent(s);
  }

  protected quando(t: number | null): string {
    return t
      ? new Date(t * 1000).toLocaleString('it-IT', {
          day: '2-digit',
          month: '2-digit',
          year: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
        })
      : '—';
  }

  protected etichetta(a: string): string {
    return AZIONI[a] ?? a;
  }

  protected dettagli(a: VoceAudit): string {
    const d = a.dettagli as Record<string, unknown> | null;
    if (!d || typeof d !== 'object') return '';
    const parti = Object.entries(d)
      .filter(([, v]) => v !== null && v !== false && !(Array.isArray(v) && !v.length))
      .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : String(v)}`);
    return parti.length ? ` · ${parti.join(' · ')}` : '';
  }

  protected async salva(): Promise<void> {
    const oauth: Record<string, { attivo: boolean; id: string; secret: string }> = {};
    for (const [id, f] of this.formProvider) {
      const v = f.getRawValue();
      oauth[id] = { attivo: v.attivo, id: v.id.trim(), secret: v.secret.trim() };
    }
    const g = this.generale.getRawValue();
    const r = await this.api.op({
      op: 'imp_salva',
      config: { ...g, public_url: g.public_url.trim(), oauth },
    });
    if (r.ok && r.config) {
      this.ui.toast('💾 Impostazioni salvate');
      this.applica(r.config);
    }
  }

  protected async salvaAccount(): Promise<void> {
    const v = this.account.getRawValue();
    if (v.nuova && v.nuova !== v.nuova2) {
      void this.ui.avviso('Scrivi la stessa nuova password in tutti e due i campi.', {
        titolo: 'Le password non coincidono',
        icona: '🔑',
      });
      return;
    }
    if (!v.attuale) {
      void this.ui.avviso(
        'Per sicurezza, per cambiare utente o password serve la password attuale.',
        { titolo: 'Manca la password attuale', icona: '🔑' },
      );
      return;
    }
    const r = await this.api.op({
      op: 'imp_admin',
      utente: v.utente,
      nuova: v.nuova,
      attuale: v.attuale,
    });
    if (r.ok) {
      this.ui.toast('✅ Account di sistema aggiornato');
      this.account.patchValue({ nuova: '', nuova2: '', attuale: '' });
    }
  }

  protected async permesso(
    x: UtenteImpostazioni,
    quale: 'master' | 'admin',
    e: Event,
  ): Promise<void> {
    const v = (e.target as HTMLInputElement).checked;
    await this.api.op({ op: 'imp_utente', id: x.id, [quale]: v });
    await this.leggi();
  }

  protected async elimina(x: UtenteImpostazioni): Promise<void> {
    if (
      await this.ui.conferma("Dovrà rifare l'accesso da capo.", {
        titolo: `Eliminare «${x.nome}»?`,
        pericolo: true,
        ok: 'Elimina',
      })
    ) {
      await this.api.op({ op: 'imp_utente', id: x.id, elimina: true });
      await this.leggi();
    }
  }

  protected async azzera(x: PartitaSalvata): Promise<void> {
    if (
      await this.ui.conferma('Pedine, nebbia, schede e cronologia verranno cancellate.', {
        titolo: 'Azzerare questa partita?',
        pericolo: true,
        ok: 'Azzera',
      })
    ) {
      await this.api.op({ op: 'imp_partita_azzera', id: x.id });
      await this.leggi();
    }
  }
}
