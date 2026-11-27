/**
 * Contenuto delle avventure (file JSON dei pacchetti, vedi tavolo/FORMATO_AVVENTURE.md).
 * Il server li passa così come sono: questi tipi descrivono il formato, i campi facoltativi sono «?».
 */
import type { Voce } from './generati/Voce';

export interface Griglia {
  cella: number;
  ox: number;
  oy: number;
  mostra?: boolean;
}

export interface Mappa {
  id: string;
  titolo: string;
  gruppo: string;
  ordine: number;
  /** Percorso relativo, es. `avventure/<id>/mappe/<file>`. */
  file: string;
  larghezza: number;
  altezza: number;
  griglia?: Griglia;
  /** `[colonna, riga]` dove compaiono le pedine dei personaggi. */
  inizio?: [number, number];
  note_master?: string;
  descrizione?: string;
}

export interface Documento {
  file: string;
  titolo: string;
  solo_master: boolean;
}

export type Caratteristica = 'FOR' | 'DES' | 'COS' | 'INT' | 'SAG' | 'CAR';

export interface Attacco {
  nome: string;
  /** `null` = tira solo i danni (es. Attacco furtivo). */
  bonus: number | null;
  danni: string;
  tipo?: string;
  note?: string;
}

export interface Capacita {
  nome: string;
  testo: string;
  tiro?: string;
  usi?: number;
}

export interface Incantesimo {
  nome: string;
  liv: number;
  testo: string;
  tiro?: string;
  attacco?: boolean;
}

export interface Magia {
  cd: number;
  att: number;
  slot: Record<string, number>;
  nota?: string;
  incantesimi: Incantesimo[];
}

export interface Personaggio {
  id: string;
  nome: string;
  icona: string;
  colore?: string;
  razza: string;
  classe: string;
  background?: string;
  livello?: number;
  facoltativo?: boolean;
  sottotitolo?: string;
  chi?: string;
  personalita?: string;
  perche?: string;
  legame?: string;
  consiglio?: string;
  equip?: string;
  ca: number;
  ca_note?: string;
  pf: number;
  vel?: string;
  iniz?: number;
  dadivita?: string;
  comp?: number;
  /** Assente nelle schede «semplificate». */
  car?: Record<Caratteristica, number>;
  ts?: Caratteristica[];
  abilita?: Record<string, number>;
  factotum?: number;
  sensi?: string;
  extra?: string;
  attacchi?: Attacco[];
  capacita?: Capacita[];
  magia?: Magia;
}

export interface Mostro {
  id: string;
  nome: string;
  tipo?: string;
  icona?: string;
  colore?: string;
  ca: number | string;
  pf: number;
  vel?: string;
  gs?: string;
  des?: number;
  taglia?: number;
  alleato?: boolean;
  attacchi?: Attacco[];
  tratti?: Capacita[];
}

export interface Avventura {
  id: string | null;
  titolo: string;
  sottotitolo?: string;
  descrizione?: string;
  livello?: string;
  giocatori?: string;
  durata?: string;
  copertina?: string;
  mappe: Mappa[];
  personaggi: Personaggio[];
  mostri: Mostro[];
  documenti: Documento[];
}

/** Voce del catalogo (solo Master e amministratori). */
export interface AvventuraBreve {
  id: string;
  titolo: string;
  sottotitolo: string;
  descrizione: string;
  livello: string;
  giocatori: string;
  durata: string;
  mappe: number;
  personaggi: number;
  documenti: Documento[];
}

/** Un gruppo di dadi o un numero dentro un tiro. */
export type ParteTiro =
  | { tipo: 'num'; valore: number }
  | { tipo: 'dadi'; n: number; facce: number; valori: number[]; tenuti: number[]; segno: number; somma: number };

export interface RisultatoTiro {
  espr: string;
  parti: ParteTiro[];
  totale: number;
  critico: boolean;
  fallimento: boolean;
}

/** Le voci della cronologia con i loro campi specifici (il tipo generato ha solo quelli comuni). */
export type VoceTiro = Voce & RisultatoTiro & {
  tipo: 'tiro';
  chi: string;
  colore: string;
  etichetta: string;
  modo: string;
  danni?: RisultatoTiro;
};
export type VoceChat = Voce & { tipo: 'chat'; chi: string; colore: string; testo: string };
export type VoceSistema = Voce & { tipo: 'sistema'; testo: string };
export type VoceLog = VoceTiro | VoceChat | VoceSistema;

/** Una voce di `imp_leggi.utenti`. */
export interface UtenteImpostazioni {
  id: string;
  nome: string;
  account: string;
  provider: string;
  avatar: string;
  master: boolean;
  admin: boolean;
  sistema: boolean;
  online: boolean;
  visto: number;
  io: boolean;
}

export interface ProviderConfig {
  attivo: boolean;
  id: string;
  secret_impostato: boolean;
  nome: string;
  console: string;
}

export interface ConfigPubblica {
  nome_tavolo: string;
  public_url: string;
  ospiti: boolean;
  password_giocatori: string;
  admin_utente: string;
  oauth: Record<string, ProviderConfig>;
}

export interface PartitaSalvata {
  id: string;
  titolo: string;
  aggiornata: number | null;
  pedine: number;
  tiri: number;
  round: number;
  in_gioco: boolean;
}

export interface VoceAudit {
  ora: number;
  utente: string | null;
  nome: string | null;
  ip: string | null;
  azione: string;
  dettagli: unknown;
}
