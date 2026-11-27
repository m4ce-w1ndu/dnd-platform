import { ChangeDetectionStrategy, Component, computed, effect, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ApiService } from '../api/api.service';
import type { Mappa } from '../api/avventura';
import { UiService } from '../core/ui.service';
import { AzioniService } from '../stato/azioni.service';
import { TavoloStore } from '../stato/tavolo.store';
import { VistaService } from '../stato/vista.service';

/** Pannello del Master: avventure, mappe, bestiario, griglia, caricamenti, appunti, salvataggi. */
@Component({
  selector: 'app-master',
  imports: [FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <details open>
      <summary>📚 Avventure</summary>
      @for (a of store.stato()?.catalogo ?? []; track a.id) {
        <div class="avv" [class.attiva]="a.id === store.stato()?.attiva">
          <div>
            <b>{{ a.titolo }}</b>
            @if (a.id === store.stato()?.attiva) {
              <span class="chip attivo">in gioco</span>
            }
            <br /><small class="aiuto">{{ a.sottotitolo || '' }} · liv. {{ a.livello || '?' }} · {{ a.mappe }} mappe · {{ a.personaggi }} personaggi</small>
          </div>
          @if (a.id !== store.stato()?.attiva) {
            <div class="gruppo-btn">
              <button class="primario" (click)="gioca(a.id)">▶ Gioca</button><button class="pericolo" title="Elimina dal server" (click)="eliminaAvventura(a.id)">🗑️</button>
            </div>
          }
        </div>
      } @empty {
        <p class="aiuto">Nessuna avventura sul server. Caricane una (.zip) qui sotto.</p>
      }
      <div class="riga"><input #zip type="file" accept=".zip,application/zip" style="flex:1" /><button class="primario" (click)="caricaAvventura(zip)">Carica</button></div>
      <button class="pericolo" style="width:100%;margin:4px 0" (click)="chiudiTavolo()">🔒 Chiudi il tavolo</button>
      <p class="aiuto">Carica un pacchetto avventura (.zip): compare subito nell'elenco. Se ha lo stesso id di una esistente, la aggiorna mantenendo la partita.</p>
    </details>
    <details open>
      <summary>🗺️ Mappe</summary>
      <div id="m-scene">
        @for (g of gruppiMappe(); track g.nome) {
          <div class="gruppo">{{ g.nome }}</div>
          @for (s of g.mappe; track s.id) {
            <button [class.attivo]="s.id === store.stato()?.scena" (click)="scena(s.id)">🗺️ {{ s.titolo }}</button>
          }
        }
      </div>
      <label class="switch"><input type="checkbox" [(ngModel)]="portaGruppo" /> porta le pedine dei personaggi nella nuova mappa</label>
    </details>
    <details open>
      <summary>🐉 Bestiario</summary>
      <label class="switch"><input type="checkbox" [checked]="store.nascostiNuovi()" (change)="store.nascostiNuovi.set(spunta($event))" /> aggiungi nascosti (solo tu li vedi)</label>
      <div class="bestiario">
        @for (m of store.avv().mostri; track m.id) {
          <button (click)="azioni.aggiungiMostro(m, vista.centroVista())">
            <span class="ic">{{ m.icona }}</span><span><b>{{ m.nome }}</b><small>CA {{ m.ca }} · PF {{ m.pf }} · GS {{ m.gs }}</small></span>
          </button>
        } @empty {
          <p class="aiuto">Questa avventura non ha mostri: usa la «pedina libera» qui sotto.</p>
        }
      </div>
      <form class="riga custom" (submit)="pedinaLibera($event)">
        <input [(ngModel)]="libera.nome" name="nome" placeholder="Pedina libera" style="flex:2" />
        <input [(ngModel)]="libera.icona" name="icona" placeholder="🙂" style="width:52px" />
        <input [(ngModel)]="libera.pf" name="pf" type="number" placeholder="PF" style="width:60px" />
        <button>+</button>
      </form>
    </details>
    <details>
      <summary>📐 Griglia della mappa</summary>
      <p class="aiuto">Per le mappe caricate: regola la dimensione del quadretto e lo scostamento finché la griglia combacia.</p>
      <div class="riga"><label>Quadretto px <input type="number" step="0.5" [(ngModel)]="griglia.cella" /></label></div>
      <div class="riga">
        <label>Inizio X <input type="number" step="0.5" [(ngModel)]="griglia.ox" /></label><label>Inizio Y <input type="number" step="0.5" [(ngModel)]="griglia.oy" /></label>
      </div>
      <div class="riga">
        <label class="switch"><input type="checkbox" [(ngModel)]="griglia.mostra" /> disegna la griglia</label><button class="primario" (click)="salvaGriglia()">Salva</button>
      </div>
    </details>
    <details>
      <summary>⬆️ Carica una mappa</summary>
      <input #img type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" />
      <div class="riga"><input [(ngModel)]="nuovaMappa.titolo" placeholder="Titolo della mappa" /><input type="number" title="pixel per quadretto" style="width:80px" [(ngModel)]="nuovaMappa.cella" /></div>
      <button class="primario" (click)="caricaMappa(img)">Carica</button>
      <p class="aiuto">PNG, JPG, WEBP o SVG. Viene aggiunta all'avventura in gioco. Il numero è la dimensione in pixel di un quadretto (0 = senza griglia); puoi correggerla dopo in «Griglia della mappa».</p>
    </details>
    <details>
      <summary>📝 Appunti segreti</summary>
      <textarea id="m-note" rows="8" placeholder="Solo tu vedi questi appunti." [value]="noteMostrate()" (focus)="inizioNote()" (blur)="fineNote()" (input)="note($event)"></textarea>
    </details>
    <details>
      <summary>💾 Salvataggio</summary>
      <div class="gruppo-btn col">
        <a class="btn" [href]="esporta()">Scarica salvataggio</a>
        <label class="btn">Carica salvataggio<input type="file" accept="application/json" hidden (change)="importa($event)" /></label>
        <button (click)="pulisci()">Togli i mostri da questa mappa</button>
        <button (click)="svuotaLog()">Svuota la cronologia</button>
        <button class="pericolo" (click)="reset()">Ricomincia questa avventura</button>
      </div>
    </details>
  `,
})
export class MasterComponent {
  protected readonly store = inject(TavoloStore);
  protected readonly azioni = inject(AzioniService);
  protected readonly vista = inject(VistaService);
  private readonly api = inject(ApiService);
  private readonly ui = inject(UiService);

  protected portaGruppo = true;
  protected libera = { nome: '', icona: '', pf: null as number | null };
  protected griglia = { cella: 0, ox: 0, oy: 0, mostra: false };
  protected nuovaMappa = { titolo: '', cella: 70 };

  protected readonly gruppiMappe = computed(() => {
    const g = new Map<string, Mappa[]>();
    for (const s of this.store.avv().mappe) {
      const k = s.gruppo || 'Mappe';
      g.set(k, [...(g.get(k) ?? []), s]);
    }
    return [...g].map(([nome, mappe]) => ({ nome, mappe }));
  });

  constructor() {
    // il riquadro della griglia mostra i valori della mappa corrente
    effect(() => {
      const g = this.store.griglia();
      this.griglia = { cella: g?.cella ?? 0, ox: g?.ox ?? 0, oy: g?.oy ?? 0, mostra: !!g?.mostra };
    });
  }

  protected spunta(e: Event): boolean {
    return (e.target as HTMLInputElement).checked;
  }

  protected async gioca(id: string): Promise<void> {
    if (await this.ui.conferma('La partita attuale resta salvata e la ritrovi quando ci torni.', { titolo: 'Passare a questa avventura?', icona: '📚', ok: 'Gioca' })) {
      void this.api.op({ op: 'avventura_attiva', id });
    }
  }

  protected async eliminaAvventura(id: string): Promise<void> {
    if (await this.ui.conferma("L'avventura e la sua partita salvata verranno cancellate dal server.", { titolo: "Eliminare l'avventura?", pericolo: true, ok: 'Elimina' })) {
      void this.api.op({ op: 'avventura_elimina', id });
    }
  }

  protected async caricaAvventura(input: HTMLInputElement): Promise<void> {
    const f = input.files?.[0];
    if (!f) {
      void this.ui.avviso("Scegli prima il file .zip dell'avventura con il pulsante accanto.", { titolo: 'Manca il file', icona: '📦' });
      return;
    }
    this.ui.toast('Caricamento in corso…');
    const r = await this.api.carica('/api/carica_avventura', f);
    if (r.ok) {
      this.ui.toast(`📚 «${r.titolo}» è sul server!`);
      input.value = '';
    }
  }

  protected async chiudiTavolo(): Promise<void> {
    if (await this.ui.conferma("La partita resta salvata e i giocatori tornano nella sala d'attesa.", { titolo: 'Chiudere il tavolo?', icona: '🔒', ok: 'Chiudi il tavolo' })) {
      void this.api.op({ op: 'sessione_chiudi' });
    }
  }

  protected scena(id: string): void {
    void this.api.op({ op: 'scena', id, porta_gruppo: this.portaGruppo });
  }

  protected pedinaLibera(e: Event): void {
    e.preventDefault();
    const pf = Math.trunc(+(this.libera.pf ?? 0)) || 0;
    this.azioni.nuovaPedina({ nome: this.libera.nome || 'Pedina', icona: this.libera.icona || '🙂', colore: '#555', pf, pfmax: pf, tipo: 'png' }, this.vista.centroVista());
    this.libera.nome = '';
  }

  protected salvaGriglia(): void {
    const id = this.store.stato()?.scena;
    if (!id) return;
    void this.api.op({ op: 'griglia', id, griglia: { cella: +this.griglia.cella, ox: +this.griglia.ox, oy: +this.griglia.oy, mostra: this.griglia.mostra } });
  }

  protected async caricaMappa(input: HTMLInputElement): Promise<void> {
    const f = input.files?.[0];
    if (!f) {
      void this.ui.avviso("Scegli prima l'immagine della mappa con il pulsante accanto.", { titolo: 'Manca il file', icona: '🗺️' });
      return;
    }
    const titolo = this.nuovaMappa.titolo || f.name.replace(/\.\w+$/, '');
    const cella = +this.nuovaMappa.cella || 0;
    const r = await this.api.carica(`/api/carica_mappa?nome=${encodeURIComponent(f.name)}&titolo=${encodeURIComponent(titolo)}&cella=${cella}`, f);
    if (r.ok) {
      this.ui.toast("🗺️ Mappa aggiunta all'avventura (gruppo «Caricate»)");
      input.value = '';
    }
  }

  // appunti: mentre si scrive, gli aggiornamenti dal server non toccano il campo
  private readonly scrivendo = signal(false);
  private noteAlFocus = '';
  private noteInCorso: string | null = null;
  protected readonly noteMostrate = computed(() => (this.scrivendo() ? this.noteAlFocus : (this.store.stato()?.note_master ?? '')));
  private tNote: ReturnType<typeof setTimeout> | null = null;

  protected inizioNote(): void {
    this.noteAlFocus = this.store.stato()?.note_master ?? '';
    this.scrivendo.set(true);
  }

  protected fineNote(): void {
    if (this.tNote) clearTimeout(this.tNote);
    if (this.noteInCorso !== null) this.salvaNote(this.noteInCorso);
    this.noteInCorso = null;
    this.scrivendo.set(false);
  }

  protected note(e: Event): void {
    const v = (e.target as HTMLTextAreaElement).value;
    this.noteInCorso = v;
    if (this.tNote) clearTimeout(this.tNote);
    this.tNote = setTimeout(() => {
      this.salvaNote(v);
      this.noteInCorso = null;
    }, 700);
  }

  private salvaNote(testo: string): void {
    const st = this.store.stato();
    if (st) this.store.imposta({ ...st, note_master: testo });
    void this.api.op({ op: 'note_master', testo });
  }

  protected esporta(): string {
    return this.api.link('/api/esporta');
  }

  protected async importa(e: Event): Promise<void> {
    const input = e.target as HTMLInputElement;
    const f = input.files?.[0];
    input.value = '';
    if (!f) return;
    if (!(await this.ui.conferma('La partita attuale verrà sostituita da quella del file.', { titolo: 'Caricare il salvataggio?', pericolo: true, ok: 'Carica' }))) return;
    try {
      const r = await this.api.importa(JSON.parse(await f.text()));
      if (!r.ok) void this.ui.avviso(r.errore || 'Il file scelto non è un salvataggio del tavolo.', { titolo: 'File non valido' });
    } catch {
      void this.ui.avviso('Il file scelto non è un salvataggio del tavolo.', { titolo: 'File non valido' });
    }
  }

  protected async pulisci(): Promise<void> {
    if (await this.ui.conferma('Le pedine dei personaggi restano al loro posto.', { titolo: 'Togliere i mostri da questa mappa?', icona: '🧹', ok: 'Togli' })) void this.api.op({ op: 'pulisci_scena' });
  }

  protected async svuotaLog(): Promise<void> {
    if (await this.ui.conferma('Tutti i tiri e i messaggi della chat verranno cancellati per tutti.', { titolo: 'Svuotare la cronologia?', pericolo: true, ok: 'Svuota' })) void this.api.op({ op: 'svuota_log' });
  }

  protected async reset(): Promise<void> {
    if (await this.ui.conferma('Si perdono pedine, nebbia, schede e cronologia di questa partita.', { titolo: 'Ricominciare da zero?', pericolo: true, ok: 'Ricomincia' })) void this.api.op({ op: 'reset_partita' });
  }
}
