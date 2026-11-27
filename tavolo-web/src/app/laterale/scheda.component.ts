import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';

import { ApiService } from '../api/api.service';
import type { Attacco, Caratteristica, Incantesimo, Personaggio } from '../api/avventura';
import { CredService } from '../core/cred.service';
import { UiService } from '../core/ui.service';
import { AzioniService } from '../stato/azioni.service';
import { TavoloStore } from '../stato/tavolo.store';
import { mod, sg } from '../util/dadi';
import { NOMI_CAR, abilita, percezionePassiva, tsBonus } from '../util/scheda';

/** Scheda del personaggio: PF, caratteristiche, abilità, attacchi, capacità, magia, note. Ogni voce tira i dadi. */
@Component({
  selector: 'app-scheda',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (store.master()) {
      <div class="riga">
        <select style="flex:1" (change)="store.schedaScelta.set(valore($event))">
          @for (x of store.avv().personaggi; track x.id) {
            <option [value]="x.id" [selected]="x.id === store.schedaVista()">{{ x.icona }} {{ x.nome }}</option>
          }
        </select>
      </div>
    }
    @if (p(); as p) {
      <div class="sch">
        <div class="sch-testa">
          <span class="ic">{{ p.icona }}</span>
          <div><h2>{{ p.nome }}</h2><small>{{ p.razza }} · {{ p.classe }} · liv. {{ p.livello }}</small></div>
        </div>
        <div class="gruppo-btn adv" style="margin:8px 0">
          <button [class.attivo]="store.vantaggio() === 'dis'" (click)="store.vantaggio.set('dis')">Svantaggio</button>
          <button [class.attivo]="store.vantaggio() === ''" (click)="store.vantaggio.set('')">Normale</button>
          <button [class.attivo]="store.vantaggio() === 'adv'" (click)="store.vantaggio.set('adv')">Vantaggio</button>
        </div>
        <div class="sch-pf">
          <div class="riga" style="justify-content:space-between;margin:0">
            <b>❤️ Punti Ferita</b><b style="font-size:18px">{{ s().pf }}/{{ p.pf }}{{ s().pft ? ' (+' + s().pft + ')' : '' }}</b>
          </div>
          <div class="barra-pf"><i [style.width.%]="barra(s().pf, p.pf)"></i></div>
          @if (mia()) {
            <div class="riga" style="margin:0">
              <input type="number" min="1" style="width:64px" [value]="qta()" (input)="qta.set(+valore($event) || 0)" />
              <button class="pericolo" (click)="danno(p)">− Danno</button>
              <button (click)="cura(p)">+ Cura</button>
              <button title="Punti ferita temporanei" (click)="temp(p)">+ Temp</button>
              <button title="Riposo lungo: tutto ripristinato" (click)="riposo(p)">🌙</button>
            </div>
          }
        </div>
        <div class="sch-box">
          <div><small>CA</small><b>{{ p.ca }}</b>@if (p.ca_note) {<small>{{ p.ca_note }}</small>}</div>
          <button (click)="iniziativa(p)"><small>Iniziativa</small><b>{{ sg(p.iniz || 0) }}</b></button>
          <div><small>Velocità</small><b style="font-size:15px">{{ p.vel }}</b></div>
          <div><small>Percezione passiva</small><b>{{ passiva(p) }}</b></div>
        </div>
        @if (p.car; as car) {
          <h3>Caratteristiche <small class="aiuto">(clic = prova · riga sotto = tiro salvezza)</small></h3>
          <div class="car6">
            @for (k of caratteristiche; track k) {
              <button [title]="'Prova di ' + nomi[k]" (click)="tira(azioni.d20(mod(car[k])), nome(p) + ' · Prova di ' + nomi[k])"><small>{{ k }}</small><b>{{ sg(mod(car[k])) }}</b><small>{{ car[k] }}</small></button>
            }
          </div>
          <div class="car6" style="margin-top:4px">
            @for (k of caratteristiche; track k) {
              <button [title]="'Tiro salvezza su ' + nomi[k]" (click)="tira(azioni.d20(ts(p, k)), nome(p) + ' · TS ' + nomi[k])"><small>TS</small><em>{{ (p.ts ?? []).includes(k) ? '★' : '' }}{{ sg(ts(p, k)) }}</em></button>
            }
          </div>
        } @else {
          <p class="aiuto">📘 Regole semplificate: per un'abilità che non è nella tua scheda tira il d20 senza aggiungere nulla.</p>
        }
        <h3>Attacchi</h3>
        @for (a of p.attacchi ?? []; track $index) {
          <div class="attacco">
            <button (click)="attacca(p, a)">
              <b>{{ a.nome }}</b>
              @if (a.bonus != null) {
                <b style="color:var(--oro2)"> {{ sg(a.bonus) }}</b>
              }
              · {{ a.danni }} {{ a.tipo }}<small>{{ a.note }}</small>
            </button>
            @if (a.bonus != null) {
              <button title="Solo danni" (click)="tira(a.danni, nome(p) + ' · danni ' + a.nome)">💥</button>
            }
          </div>
        }
        <h3>Abilità</h3>
        <div class="lista-tiri">
          @for (a of abil(); track a.n) {
            <button [class.comp]="a.pro" (click)="tira(azioni.d20(a.b), nome(p) + ' · ' + a.n)"><span>{{ a.n }}</span><b>{{ sg(a.b) }}</b></button>
          }
          @if (!p.car) {
            <button (click)="tira(azioni.d20(0), nome(p) + ' · prova senza bonus')"><span>Altra abilità</span><b>+0</b></button>
          }
        </div>
        @if (p.extra) {
          <p class="aiuto">{{ p.extra }}</p>
        }
        <h3>Capacità</h3>
        @for (c of p.capacita ?? []; track $index; let i = $index) {
          <div class="cap">
            @for (k of conta(c.usi ?? 0); track k) {
              <input type="checkbox" [checked]="(s().usi[i] || 0) > k" [disabled]="!mia()" (change)="uso(p, i, $event)" />
            }
            <b>{{ c.nome }}.</b> {{ c.testo }}
            @if (c.tiro) {
              <button class="link" (click)="tira(c.tiro, nome(p) + ' · ' + c.nome)">tira {{ c.tiro }}</button>
            }
          </div>
        }
        @if (p.sensi) {
          <div class="cap"><b>Sensi.</b> {{ p.sensi }}</div>
        }
        @if (p.magia; as m) {
          <h3>Magia <small class="aiuto">CD {{ m.cd }} · attacco {{ sg(m.att) }}</small></h3>
          <div class="slots">
            @for (lv of livelliSlot(); track lv) {
              <div class="lv">
                {{ lv }}° liv.:
                @for (k of conta(m.slot[lv]); track k) {
                  <input type="checkbox" title="spunta = slot usato" [checked]="(s().slot[lv] || 0) > k" [disabled]="!mia()" (change)="slot(p, lv, $event)" />
                }
              </div>
            }
          </div>
          @if (m.nota) {
            <p class="aiuto">{{ m.nota }}</p>
          }
          @for (x of m.incantesimi; track $index) {
            <details class="incant">
              <summary>
                <span><b>{{ x.nome }}</b> <small>{{ x.liv ? x.liv + '° liv.' : 'trucchetto' }}</small></span>
                @if (mia() && (x.liv || x.tiro)) {
                  <button class="link" (click)="lancia($event, p, x)">{{ x.liv ? 'Lancia' : 'Tira' }}</button>
                }
              </summary>
              <div>{{ x.testo }}</div>
            </details>
          }
        }
        <h3>Equipaggiamento</h3>
        <p class="cap">{{ p.equip }}</p>
        <h3>Note</h3>
        <textarea
          [disabled]="!mia()"
          placeholder="Appunti, tesori, nomi da ricordare…"
          [value]="noteMostrate()"
          (focus)="inizioNote()"
          (blur)="fineNote(p)"
          (input)="note(p, $event)"
        ></textarea>
        @if (p.consiglio) {
          <p class="aiuto">💡 {{ p.consiglio }}</p>
        }
      </div>
    } @else {
      <p class="aiuto">Non hai ancora un personaggio in questa avventura. Scegline uno:</p>
      <div class="pg-griglia">
        @for (x of store.avv().personaggi; track x.id) {
          <button class="pg-card" [class.preso]="presi().has(x.id)" (click)="scegli(x.id)">
            <span class="ic">{{ x.icona }}</span><b>{{ x.nome }}</b><small>{{ x.razza }} · {{ x.classe }}</small>
          </button>
        } @empty {
          <p class="aiuto">Questa avventura non ha personaggi pronti.</p>
        }
      </div>
    }
  `,
})
export class SchedaComponent {
  protected readonly store = inject(TavoloStore);
  protected readonly azioni = inject(AzioniService);
  private readonly api = inject(ApiService);
  private readonly ui = inject(UiService);
  private readonly cred = inject(CredService);

  protected readonly sg = sg;
  protected readonly mod = mod;
  protected readonly nomi = NOMI_CAR;
  protected readonly caratteristiche = Object.keys(NOMI_CAR) as Caratteristica[];
  protected readonly qta = signal(1);

  protected readonly p = computed(() => {
    const id = this.store.schedaVista();
    return id ? (this.store.personaggi().get(id) ?? null) : null;
  });
  protected readonly s = computed(() => {
    const p = this.p();
    this.store.stato(); // si ricalcola quando arrivano nuove schede
    return p ? this.azioni.statoScheda(p) : { pf: 0, pft: 0, slot: {}, usi: {}, note: '' };
  });
  protected readonly mia = computed(() => this.store.master() || this.store.io()?.char === this.p()?.id);
  protected readonly abil = computed(() => {
    const p = this.p();
    return p ? abilita(p) : [];
  });
  protected readonly livelliSlot = computed(() => Object.keys(this.p()?.magia?.slot ?? {}).sort((a, b) => +a - +b));
  protected readonly presi = computed(() => new Set(this.store.online().map((u) => u.char).filter((c): c is string => !!c)));

  protected valore(e: Event): string {
    return (e.target as HTMLInputElement).value;
  }
  protected nome(p: Personaggio): string {
    return p.nome.split(' ')[0];
  }
  protected ts(p: Personaggio, k: Caratteristica): number {
    return tsBonus(p, k);
  }
  protected passiva(p: Personaggio): number {
    return percezionePassiva(p);
  }
  protected barra(pf: number, max: number): number {
    return Math.max(0, Math.min(100, (pf / max) * 100));
  }
  protected conta(n: number): number[] {
    return Array.from({ length: n }, (_, k) => k);
  }

  protected tira(espr: string, etichetta: string, danni?: string): void {
    void this.azioni.tiro(espr, etichetta, { danni });
  }

  protected attacca(p: Personaggio, a: Attacco): void {
    if (a.bonus == null) this.tira(a.danni, `${this.nome(p)} · ${a.nome}`);
    else this.tira(this.azioni.d20(a.bonus), `${this.nome(p)} · ${a.nome}`, a.danni);
  }

  protected iniziativa(p: Personaggio): void {
    const ped = Object.values(this.store.stato()?.pedine ?? {}).find((x) => x?.pg === p.id);
    if (ped) void this.azioni.iniziativaPedina(ped);
    else void this.azioni.iniziativaLibera(p.nome, p.iniz ?? 0, p.colore);
  }

  protected danno(p: Personaggio): void {
    let d = this.qta();
    const st = this.s();
    const assorbiti = Math.min(st.pft, d);
    d -= assorbiti;
    this.azioni.salvaScheda(p, { pf: Math.max(0, st.pf - d), pft: st.pft - assorbiti });
    if (st.pf - d <= 0) {
      void this.ui.avviso(
        'Nel tuo turno tira un d20: con 10 o più è un successo, sotto 10 un fallimento. 3 successi = sei stabile, 3 fallimenti = muori. Un 20 ti rimette in piedi con 1 PF. Qualsiasi cura ti rialza subito.',
        { titolo: 'Sei a terra!', icona: '💀' },
      );
    }
  }

  protected cura(p: Personaggio): void {
    this.azioni.salvaScheda(p, { pf: Math.min(p.pf, this.s().pf + this.qta()) });
  }

  protected temp(p: Personaggio): void {
    this.azioni.salvaScheda(p, { pft: Math.max(this.s().pft, this.qta()) });
  }

  protected async riposo(p: Personaggio): Promise<void> {
    if (await this.ui.conferma('Punti ferita, slot degli incantesimi e capacità tornano al massimo.', { titolo: 'Riposo lungo', icona: '🌙', ok: 'Riposa' })) {
      this.azioni.salvaScheda(p, { pf: p.pf, pft: 0, slot: {}, usi: {} });
    }
  }

  /** Le caselle contano quante sono spuntate (non quale): stesso formato del vecchio client. */
  protected uso(p: Personaggio, i: number, e: Event): void {
    const n = this.contaSpuntate(e);
    this.azioni.salvaScheda(p, { usi: { ...this.s().usi, [i]: n } });
  }

  protected slot(p: Personaggio, lv: string, e: Event): void {
    const n = this.contaSpuntate(e);
    this.azioni.salvaScheda(p, { slot: { ...this.s().slot, [lv]: n } });
  }

  private contaSpuntate(e: Event): number {
    const box = (e.target as HTMLElement).parentElement;
    return box ? box.querySelectorAll('input[type=checkbox]:checked').length : 0;
  }

  protected lancia(e: Event, p: Personaggio, x: Incantesimo): void {
    e.preventDefault();
    e.stopPropagation();
    const m = p.magia;
    if (!m) return;
    const nome = this.nome(p);
    if (x.liv) {
      const st = this.s();
      // si usa lo slot più basso disponibile dal livello dell'incantesimo in su
      const lv = Object.keys(m.slot)
        .map(Number)
        .sort((a, b) => a - b)
        .find((l) => l >= x.liv && (st.slot[l] || 0) < m.slot[l]);
      if (!lv) {
        void this.ui.avviso('Hai usato tutti gli slot di quel livello. Si recuperano con il riposo lungo (🌙 nella scheda).', { titolo: 'Niente più slot', icona: '✨' });
        return;
      }
      this.azioni.salvaScheda(p, { slot: { ...st.slot, [lv]: (st.slot[lv] || 0) + 1 } });
      if (!x.tiro) void this.api.op({ op: 'chat', testo: `✨ ${nome} lancia ${x.nome}! (slot di ${lv}° livello)` });
    }
    if (x.tiro) {
      if (x.attacco) this.tira(this.azioni.d20(m.att), `${nome} · ${x.nome}`, x.tiro);
      else this.tira(x.tiro, `${nome} · ${x.nome}`);
    } else if (!x.liv) void this.api.op({ op: 'chat', testo: `✨ ${nome} usa ${x.nome}.` });
  }

  // Mentre si scrive, gli aggiornamenti dal server non toccano il campo (niente testo perso né cursore che salta).
  private readonly scrivendo = signal(false);
  private noteAlFocus = '';
  private noteInCorso: string | null = null;
  protected readonly noteMostrate = computed(() => (this.scrivendo() ? this.noteAlFocus : this.s().note));
  private tNote: ReturnType<typeof setTimeout> | null = null;

  protected inizioNote(): void {
    this.noteAlFocus = this.s().note;
    this.scrivendo.set(true);
  }

  protected fineNote(p: Personaggio): void {
    if (this.tNote) clearTimeout(this.tNote);
    if (this.noteInCorso !== null) this.azioni.salvaScheda(p, { note: this.noteInCorso });
    this.noteInCorso = null;
    this.scrivendo.set(false);
  }

  protected note(p: Personaggio, e: Event): void {
    const v = (e.target as HTMLTextAreaElement).value;
    this.noteInCorso = v;
    if (this.tNote) clearTimeout(this.tNote);
    this.tNote = setTimeout(() => {
      this.azioni.salvaScheda(p, { note: v });
      this.noteInCorso = null;
    }, 600);
  }

  protected async scegli(pg: string): Promise<void> {
    if (await this.azioni.scegliPersonaggio(pg)) this.cred.aggiorna({ personaggio: pg });
  }
}
