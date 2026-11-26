//! Il protocollo verso il browser, tipizzato: eventi SSE e risposte principali.
//!
//! Da questi tipi (e da quelli di `modello` e `comandi`) `ts-rs` genera i tipi TypeScript del client
//! (`cargo test esporta_tipi_typescript` → `tavolo-web/src/app/api/generati/`). Se il server cambia un campo,
//! il client smette di compilare: niente più disallineamenti silenziosi.

use serde::Serialize;
use serde_json::{Map, Value};
use ts_rs::TS;

use crate::comandi::Punto;
use crate::modello::{Iniziativa, Nebbia, Pedina, Stato, Voce};

/// Un evento mandato sullo stream `/api/eventi` (`data: {"t": ...}`).
/// (Vive un istante: viene subito serializzato, quindi la dimensione delle varianti non conta.)
#[allow(clippy::large_enum_variant)]
#[derive(Debug, Clone, Serialize, TS)]
#[serde(tag = "t", rename_all = "snake_case")]
pub enum Evento {
    /// Una pedina nuova o cambiata (ai non-Master una pedina nascosta arriva come `pedina_via`).
    Pedina {
        pedina: Pedina,
        #[serde(skip_serializing_if = "Option::is_none")]
        #[ts(optional)]
        da: Option<String>,
        /// `true` durante un trascinamento (non ancora salvato).
        #[serde(skip_serializing_if = "Option::is_none")]
        #[ts(optional)]
        trascina: Option<bool>,
    },
    PedinaVia {
        id: String,
    },
    /// Una voce della cronologia (le voci segrete arrivano solo all'autore e al Master).
    Log {
        voce: Voce,
    },
    Scena {
        id: Option<String>,
    },
    Nebbia {
        scena: String,
        nebbia: Nebbia,
    },
    Iniziativa {
        iniziativa: Iniziativa,
    },
    Scheda {
        id: String,
        #[ts(type = "Record<string, unknown>")]
        scheda: Map<String, Value>,
    },
    Online {
        online: Vec<Online>,
    },
    /// Il catalogo delle avventure è cambiato: ricaricare lo stato.
    Catalogo,
    Ping {
        x: f64,
        y: f64,
        colore: String,
        chi: String,
        centra: bool,
    },
    Righello {
        da: String,
        colore: String,
        punti: Option<Vec<Punto>>,
    },
    /// Ricaricare lo stato da `/api/stato`.
    Ricarica,
    Sessione {
        sessione: String,
        attiva: Option<String>,
    },
    /// Il proprio ruolo è cambiato (`master` o `giocatore`).
    Ruolo {
        ruolo: String,
    },
    /// Le impostazioni pubbliche sono cambiate: rileggere `/api/info`.
    Info,
    /// L'utente è stato eliminato: tornare alla schermata di accesso.
    Esci,
}

/// Un utente collegato allo stream.
#[derive(Debug, Clone, Serialize, TS)]
pub struct Online {
    pub id: String,
    pub name: String,
    pub color: String,
    pub role: String,
    pub char: Option<String>,
    pub avatar: String,
    pub admin: bool,
    pub sistema: bool,
}

/// `GET /api/info` (pubblico).
#[derive(Debug, Clone, Serialize, TS)]
pub struct Info {
    pub avventura: InfoAvventura,
    pub personaggi: Vec<PersonaggioBreve>,
    /// Personaggi già in mano a qualcuno di collegato.
    pub presi: Vec<String>,
    /// Gli ospiti devono dare la password del tavolo.
    pub password_giocatori: bool,
    /// Provider OAuth attivi.
    pub login: Vec<Provider>,
    pub ospiti: bool,
    /// Impronta dei file web: se cambia, il browser si ricarica.
    pub versione: String,
    pub nome_tavolo: String,
    pub sessione: String,
}

#[derive(Debug, Clone, Serialize, TS)]
pub struct InfoAvventura {
    pub id: String,
    pub titolo: String,
    pub sottotitolo: String,
    pub descrizione: String,
}

#[derive(Debug, Clone, Serialize, TS)]
pub struct PersonaggioBreve {
    pub id: String,
    pub nome: String,
    pub icona: Option<String>,
    pub razza: Option<String>,
    pub classe: Option<String>,
    pub colore: Option<String>,
    pub facoltativo: bool,
}

#[derive(Debug, Clone, Serialize, TS)]
pub struct Provider {
    pub id: String,
    pub nome: String,
}

/// `GET /api/io`.
#[derive(Debug, Clone, Serialize, TS)]
pub struct Io {
    pub ok: bool,
    pub nome: String,
    /// Amministratore (del tavolo o di sistema).
    pub admin: bool,
    /// Account di sistema: solo impostazioni e permessi.
    pub sistema: bool,
    /// Può fare il Master.
    pub master: bool,
    pub provider: String,
    pub avatar: String,
    pub char: Option<String>,
    pub colore: String,
    pub ruolo: String,
}

/// `io` dentro lo stato.
#[derive(Debug, Clone, Serialize, TS)]
pub struct IoStato {
    pub id: String,
    pub name: String,
    pub color: String,
    pub role: String,
    pub char: Option<String>,
    pub avatar: Option<String>,
    pub provider: Option<String>,
    pub admin: bool,
    pub sistema: bool,
}

/// `GET /api/stato`: la partita filtrata per chi la chiede, più chi c'è e l'avventura.
#[derive(Debug, Clone, Serialize, TS)]
pub struct StatoPer {
    #[serde(flatten)]
    pub stato: Stato,
    pub online: Vec<Online>,
    pub io: IoStato,
    /// L'avventura attiva (formato in tavolo/FORMATO_AVVENTURE.md), già filtrata per ruolo.
    #[ts(type = "import(\"../avventura\").Avventura")]
    pub avv: Value,
    pub sessione: String,
    /// Solo per Master e amministratori.
    #[serde(skip_serializing_if = "Option::is_none")]
    #[ts(optional, type = "Array<import(\"../avventura\").AvventuraBreve>")]
    pub catalogo: Option<Vec<Value>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    #[ts(optional)]
    pub attiva: Option<Option<String>>,
}

#[cfg(test)]
mod test {
    /// Scrive i tipi TypeScript in tavolo-web/src/app/api/generati/ (interi come `number`, non `bigint`).
    #[test]
    fn esporta_tipi_typescript() {
        use ts_rs::TS;
        let dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../tavolo-web/src/app/api/generati");
        let cfg = ts_rs::Config::new().with_large_int("number").with_out_dir(dir);
        super::Evento::export_all(&cfg).unwrap();
        super::StatoPer::export_all(&cfg).unwrap();
        super::Info::export_all(&cfg).unwrap();
        super::Io::export_all(&cfg).unwrap();
        crate::comandi::Op::export_all(&cfg).unwrap();
    }
}
