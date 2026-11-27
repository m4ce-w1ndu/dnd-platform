import { ChangeDetectionStrategy, Component, OnInit, computed, effect, inject, signal, untracked } from '@angular/core';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { DomSanitizer } from '@angular/platform-browser';

import { ApiService } from '../api/api.service';
import type { ConfigPubblica, PartitaSalvata, UtenteImpostazioni, VoceAudit } from '../api/avventura';
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

/** La pagina dell'account di sistema: configurazione, permessi, dati e registro di audit. Niente mappa. */
@Component({
  selector: 'app-sistema',
  imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div style="flex:1;overflow:auto;padding:16px">
      <div class="card" style="max-width:780px;margin:0 auto">
        <div id="tab-impostazioni" class="tab attivo">
          <p class="aiuto">
            Sei l'<b>account di sistema</b>: qui configuri il tavolo e decidi chi è amministratore. Il tavolo lo aprono e lo conducono gli amministratori, entrando con il
            loro account.
          </p>
          <form [formGroup]="generale">
            <details open>
              <summary>🏰 Generale</summary>
              <label>Nome del tavolo<input formControlName="nome_tavolo" autocomplete="off" /></label>
              <label>Indirizzo pubblico (per l'accesso con account)<input formControlName="public_url" type="url" inputmode="url" autocomplete="url" placeholder="https://dnd.immovilli.trade" /></label>
              <p class="aiuto">Lascia vuoto per usare l'indirizzo con cui apri la pagina. Va impostato se usi l'accesso con account dietro un proxy.</p>
            </details>
            <details open>
              <summary>🚪 Accesso dei giocatori</summary>
              <label class="switch"><input type="checkbox" formControlName="ospiti" /> ammetti ospiti (senza account, solo il nome)</label>
              <label>Password del tavolo (facoltativa)<input formControlName="password_giocatori" autocomplete="off" placeholder="vuota = nessuna password" /></label>
              <p class="aiuto">Se attivi un provider e disattivi gli ospiti, si entra solo con Discord/Google/GitHub.</p>
            </details>
            <details open>
              <summary>🔑 Accesso con account (OAuth)</summary>
              @for (p of provider(); track p.id) {
                <div class="prov" [formGroup]="p.form">
                  <label class="switch"
                    ><input type="checkbox" formControlName="attivo" /> <span class="logo-prov" [class]="p.id" [innerHTML]="logo(p.id)"></span><b>{{ p.conf.nome }}</b>
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
                      [placeholder]="p.conf.secret_impostato ? '•••••• (impostato: scrivi solo per cambiarlo)' : 'incolla qui il secret'"
                  /></label>
                  <span class="aiuto">Redirect URI da registrare su <a [href]="p.conf.console" target="_blank" rel="noopener">{{ p.conf.nome }}</a>:</span>
                  <code>{{ base() }}/auth/{{ p.id }}/callback</code>
                </div>
              }
            </details>
            <button type="button" class="primario grande" (click)="salva()">💾 Salva impostazioni</button>
          </form>

          <details open>
            <summary>👥 Utenti e permessi</summary>
            <p class="aiuto"><b>Admin</b> = amministratore del tavolo: apre il tavolo, sceglie il Master e può fare il Master. <b>Master</b> = può condurre le partite.</p>
            @for (x of utenti(); track x.id) {
              <div class="utente">
                @if (x.avatar) {
                  <img [src]="x.avatar" alt="" />
                } @else {
                  <span class="av">{{ x.sistema ? '⚙️' : '👤' }}</span>
                }
                <div class="n">
                  <b>{{ x.nome }}</b>{{ x.io ? ' (tu)' : '' }} {{ x.online ? '🟢' : '' }}
                  @if (x.sistema) {
                    <span class="chip">sistema</span>
                  }
                  <small>{{ x.provider }}{{ x.account ? ' · ' + x.account : '' }} · visto {{ quando(x.visto) }}</small>
                </div>
                @if (!x.sistema) {
                  <label class="switch" title="Può condurre le partite"><input type="checkbox" [checked]="x.master" [disabled]="x.admin" (change)="permesso(x, 'master', $event)" /> Master</label>
                  <label class="switch" title="Apre il tavolo e sceglie il Master"><input type="checkbox" [checked]="x.admin" (change)="permesso(x, 'admin', $event)" /> Admin</label>
                }
                @if (!x.io) {
                  <button class="link" title="Elimina" (click)="elimina(x)">🗑️</button>
                }
              </div>
            }
          </details>

          <details open>
            <summary>🔐 Account di sistema</summary>
            <form [formGroup]="account">
              <label>Nome utente<input formControlName="utente" autocomplete="off" data-lpignore="true" /></label>
              <label>Nuova password (almeno 8 caratteri)<input formControlName="nuova" type="password" autocomplete="new-password" /></label>
              <label>Ripeti la nuova password<input formControlName="nuova2" type="password" autocomplete="new-password" /></label>
              <label>Password attuale (per confermare)<input formControlName="attuale" type="password" autocomplete="current-password" /></label>
              <button type="button" class="primario" (click)="salvaAccount()">Aggiorna account di sistema</button>
            </form>
          </details>

          <details>
            <summary>💾 Dati e partite salvate</summary>
            <p class="aiuto">Tutto è salvato nel database <code>dati/tavolo.db</code> (SQLite): partite, utenti, impostazioni.</p>
            @for (x of partite(); track x.id) {
              <div class="utente">
                <span class="av">📜</span>
                <div class="n">
                  <b>{{ x.titolo }}</b>
                  @if (x.in_gioco) {
                    <span class="chip attivo">in gioco</span>
                  }
                  <small>salvata {{ quando(x.aggiornata) }} · {{ x.pedine }} pedine · {{ x.tiri }} tiri · round {{ x.round }}</small>
                </div>
                <a class="btn" [href]="link('/api/esporta?id=' + enc(x.id))" title="Scarica">⬇️</a><button class="link" title="Ricomincia da zero" (click)="azzera(x)">♻️</button>
              </div>
            } @empty {
              <p class="aiuto">Nessuna partita salvata.</p>
            }
            <a class="btn" [href]="link('/api/backup')" style="display:block;margin-top:8px">⬇️ Scarica backup del database</a>
          </details>

          <details>
            <summary>📋 Registro di audit</summary>
            <p class="aiuto">Accessi di sistema, permessi, impostazioni e cancellazioni, dal più recente.</p>
            <div class="riga"><button (click)="leggiAudit()">🔄 Aggiorna</button></div>
            @for (a of audit(); track $index) {
              <div class="utente">
                <div class="n">
                  <b>{{ etichetta(a.azione) }}</b>
                  <small>{{ quando(a.ora) }} · {{ a.nome || a.utente || '—' }} · {{ a.ip || '—' }}{{ dettagli(a) }}</small>
                </div>
              </div>
            } @empty {
              <p class="aiuto">Nessuna voce.</p>
            }
          </details>
        </div>
      </div>
    </div>
  `,
})
export class SistemaComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly ui = inject(UiService);
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly san = inject(DomSanitizer);

  protected readonly config = signal<ConfigPubblica | null>(null);
  protected readonly utenti = signal<UtenteImpostazioni[]>([]);
  protected readonly partite = signal<PartitaSalvata[]>([]);
  protected readonly audit = signal<VoceAudit[]>([]);
  protected readonly base = computed(() => this.config()?.public_url || location.origin);

  protected readonly generale = this.fb.group({
    nome_tavolo: ['', Validators.maxLength(200)],
    public_url: [''],
    ospiti: [true],
    password_giocatori: [''],
  });
  protected readonly account = this.fb.group({ utente: ['', Validators.maxLength(40)], nuova: [''], nuova2: [''], attuale: [''] });
  private readonly formProvider = new Map<string, FormProvider>();
  protected readonly provider = computed(() =>
    Object.entries(this.config()?.oauth ?? {}).map(([id, conf]) => ({ id, conf, form: this.formProvider.get(id) ?? this.nuovoProvider(id) })),
  );

  constructor() {
    // quando qualcuno entra o esce, l'elenco degli utenti si aggiorna da solo
    const store = inject(TavoloStore);
    let primo = true;
    effect(() => {
      store.online();
      if (primo) {
        primo = false;
        return;
      }
      untracked(() => void this.leggiUtenti());
    });
  }

  ngOnInit(): void {
    void this.leggi();
    void this.leggiAudit();
  }

  private async leggiUtenti(): Promise<void> {
    const r = await this.api.op({ op: 'imp_leggi' }, { silenzioso: true });
    if (r.ok) this.utenti.set(r.utenti ?? []);
  }

  private nuovoProvider(id: string): FormProvider {
    const f: FormProvider = this.fb.group({ attivo: [false], id: [''], secret: [''] });
    this.formProvider.set(id, f);
    return f;
  }

  private async leggi(): Promise<void> {
    const r = await this.api.op({ op: 'imp_leggi' });
    if (!r.ok || !r.config) return;
    this.applica(r.config);
    this.utenti.set(r.utenti ?? []);
    const p = await this.api.op({ op: 'imp_partite' });
    if (p.ok) this.partite.set(p.partite ?? []);
  }

  private applica(c: ConfigPubblica): void {
    this.generale.reset({ nome_tavolo: c.nome_tavolo, public_url: c.public_url, ospiti: c.ospiti, password_giocatori: c.password_giocatori });
    this.account.reset({ utente: c.admin_utente, nuova: '', nuova2: '', attuale: '' });
    for (const [id, v] of Object.entries(c.oauth)) {
      (this.formProvider.get(id) ?? this.nuovoProvider(id)).reset({ attivo: v.attivo, id: v.id, secret: '' });
    }
    this.config.set(c);
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
    return t ? new Date(t * 1000).toLocaleString('it-IT', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—';
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
    const r = await this.api.op({ op: 'imp_salva', config: { ...g, public_url: g.public_url.trim(), oauth } });
    if (r.ok && r.config) {
      this.ui.toast('💾 Impostazioni salvate');
      this.applica(r.config);
    }
  }

  protected async salvaAccount(): Promise<void> {
    const v = this.account.getRawValue();
    if (v.nuova && v.nuova !== v.nuova2) {
      void this.ui.avviso('Scrivi la stessa nuova password in tutti e due i campi.', { titolo: 'Le password non coincidono', icona: '🔑' });
      return;
    }
    if (!v.attuale) {
      void this.ui.avviso('Per sicurezza, per cambiare utente o password serve la password attuale.', { titolo: 'Manca la password attuale', icona: '🔑' });
      return;
    }
    const r = await this.api.op({ op: 'imp_admin', utente: v.utente, nuova: v.nuova, attuale: v.attuale });
    if (r.ok) {
      this.ui.toast('✅ Account di sistema aggiornato');
      this.account.patchValue({ nuova: '', nuova2: '', attuale: '' });
    }
  }

  protected async permesso(x: UtenteImpostazioni, quale: 'master' | 'admin', e: Event): Promise<void> {
    const v = (e.target as HTMLInputElement).checked;
    await this.api.op({ op: 'imp_utente', id: x.id, [quale]: v });
    await this.leggi();
  }

  protected async elimina(x: UtenteImpostazioni): Promise<void> {
    if (await this.ui.conferma("Dovrà rifare l'accesso da capo.", { titolo: `Eliminare «${x.nome}»?`, pericolo: true, ok: 'Elimina' })) {
      await this.api.op({ op: 'imp_utente', id: x.id, elimina: true });
      await this.leggi();
    }
  }

  protected async azzera(x: PartitaSalvata): Promise<void> {
    if (await this.ui.conferma('Pedine, nebbia, schede e cronologia verranno cancellate.', { titolo: 'Azzerare questa partita?', pericolo: true, ok: 'Azzera' })) {
      await this.api.op({ op: 'imp_partita_azzera', id: x.id });
      await this.leggi();
    }
  }
}
