//! I comandi di `/api/op`: un enum `serde` per comando, validato all'ingresso.
//!
//! Un JSON che non rispetta i tipi viene rifiutato con 400 prima di arrivare alla logica di gioco.

use serde::Deserialize;
use serde_json::{Map, Value};

use ts_rs::TS;

use crate::util::{lenient, N};

#[derive(Debug, Clone, Deserialize, serde::Serialize, TS)]
pub struct Punto {
    #[serde(deserialize_with = "lenient::f64")]
    pub x: f64,
    #[serde(deserialize_with = "lenient::f64")]
    pub y: f64,
}

/// Dati di una pedina mandati dal client: ogni campo può mancare (`None`) o essere presente (anche null).
#[derive(Debug, Clone, Default, Deserialize, TS)]
pub struct PedinaIn {
    #[serde(default, deserialize_with = "lenient::opt_string")]
    #[ts(optional = nullable)]
    pub id: Option<String>,
    #[serde(default, deserialize_with = "lenient::presente")]
    #[ts(optional, type = "string | null")]
    pub scena: Option<Option<String>>,
    #[serde(default, deserialize_with = "lenient::presente_n")]
    #[ts(optional, type = "number | null")]
    pub x: Option<Option<N>>,
    #[serde(default, deserialize_with = "lenient::presente_n")]
    #[ts(optional, type = "number | null")]
    pub y: Option<Option<N>>,
    #[serde(default, deserialize_with = "lenient::opt_string")]
    #[ts(optional = nullable)]
    pub nome: Option<String>,
    #[serde(default, deserialize_with = "lenient::presente")]
    #[ts(optional, type = "string | null")]
    pub colore: Option<Option<String>>,
    #[serde(default, deserialize_with = "lenient::presente")]
    #[ts(optional, type = "string | null")]
    pub icona: Option<Option<String>>,
    #[serde(default, deserialize_with = "lenient::presente_n")]
    #[ts(optional, type = "number | null")]
    pub taglia: Option<Option<N>>,
    #[serde(default, deserialize_with = "lenient::presente")]
    #[ts(optional, type = "unknown")]
    pub pf: Option<Option<Value>>,
    #[serde(default, deserialize_with = "lenient::presente_n")]
    #[ts(optional, type = "number | null")]
    pub pfmax: Option<Option<N>>,
    #[serde(default, deserialize_with = "lenient::presente")]
    #[ts(optional, type = "unknown")]
    pub ca: Option<Option<Value>>,
    #[serde(default, deserialize_with = "lenient::opt_bool")]
    #[ts(optional = nullable)]
    pub nascosta: Option<bool>,
    #[serde(default, deserialize_with = "lenient::presente")]
    #[ts(optional, type = "Array<string> | null")]
    pub condizioni: Option<Option<Vec<Value>>>,
    #[serde(default, deserialize_with = "lenient::presente")]
    #[ts(optional, type = "string | null")]
    pub tipo: Option<Option<String>>,
    #[serde(default, deserialize_with = "lenient::presente")]
    #[ts(optional, type = "string | null")]
    pub pg: Option<Option<String>>,
    #[serde(default, deserialize_with = "lenient::presente")]
    #[ts(optional, type = "string | null")]
    pub mostro: Option<Option<String>>,
    #[serde(default, deserialize_with = "lenient::presente")]
    #[ts(optional, type = "string | null")]
    pub proprietario: Option<Option<String>>,
    #[serde(default, deserialize_with = "lenient::presente_n")]
    #[ts(optional, type = "number | null")]
    pub slot: Option<Option<N>>,
}

#[derive(Debug, Clone, Default, Deserialize, TS)]
pub struct GrigliaIn {
    #[serde(default, deserialize_with = "lenient::f64")]
    pub cella: f64,
    #[serde(default, deserialize_with = "lenient::f64")]
    pub ox: f64,
    #[serde(default, deserialize_with = "lenient::f64")]
    pub oy: f64,
    #[ts(as = "Option<bool>", optional = nullable)]
    #[serde(default, deserialize_with = "lenient::bool")]
    pub mostra: bool,
}

#[derive(Debug, Clone, Default, Deserialize, TS)]
pub struct OAuthIn {
    #[serde(default, deserialize_with = "lenient::opt_bool")]
    #[ts(optional = nullable)]
    pub attivo: Option<bool>,
    #[serde(default, deserialize_with = "lenient::opt_string")]
    #[ts(optional = nullable)]
    pub id: Option<String>,
    #[serde(default, deserialize_with = "lenient::opt_string")]
    #[ts(optional = nullable)]
    pub secret: Option<String>,
    #[ts(as = "Option<bool>", optional = nullable)]
    #[serde(default, deserialize_with = "lenient::bool")]
    pub rimuovi_secret: bool,
}

#[derive(Debug, Clone, Default, Deserialize, TS)]
pub struct ConfigIn {
    #[serde(default, deserialize_with = "lenient::opt_string")]
    #[ts(optional = nullable)]
    pub nome_tavolo: Option<String>,
    #[serde(default, deserialize_with = "lenient::opt_string")]
    #[ts(optional = nullable)]
    pub password_giocatori: Option<String>,
    #[serde(default, deserialize_with = "lenient::opt_string")]
    #[ts(optional = nullable)]
    pub public_url: Option<String>,
    #[serde(default, deserialize_with = "lenient::opt_bool")]
    #[ts(optional = nullable)]
    pub ospiti: Option<bool>,
    #[serde(default)]
    #[ts(optional = nullable)]
    pub oauth: Option<std::collections::BTreeMap<String, OAuthIn>>,
}

fn sempre() -> bool {
    true
}

/// Un comando di gioco. Il nome JSON è il campo `op`. (Viaggia sempre in un `Box`.)
#[allow(clippy::large_enum_variant)]
#[derive(Debug, Clone, Deserialize, TS)]
#[serde(tag = "op", rename_all = "snake_case")]
pub enum Op {
    Tira {
        #[ts(as = "Option<String>", optional = nullable)]
        #[serde(default, deserialize_with = "lenient::string")]
        espr: String,
        #[ts(as = "Option<String>", optional = nullable)]
        #[serde(default, deserialize_with = "lenient::string")]
        etichetta: String,
        #[ts(as = "Option<bool>", optional = nullable)]
        #[serde(default, deserialize_with = "lenient::bool")]
        segreto: bool,
        #[serde(default)]
        #[ts(optional = nullable)]
        modo: Option<Value>,
        #[serde(default, deserialize_with = "lenient::opt_nonempty")]
        #[ts(optional = nullable)]
        danni: Option<String>,
    },
    Chat {
        #[ts(as = "Option<String>", optional = nullable)]
        #[serde(default, deserialize_with = "lenient::string")]
        testo: String,
        #[ts(as = "Option<bool>", optional = nullable)]
        #[serde(default, deserialize_with = "lenient::bool")]
        segreto: bool,
    },
    Ping {
        #[serde(deserialize_with = "lenient::f64")]
        x: f64,
        #[serde(deserialize_with = "lenient::f64")]
        y: f64,
        #[ts(as = "Option<bool>", optional = nullable)]
        #[serde(default, deserialize_with = "lenient::bool")]
        centra: bool,
    },
    Righello {
        #[serde(default)]
        #[ts(optional = nullable)]
        punti: Option<Vec<Punto>>,
    },
    ScegliPg {
        #[serde(default, deserialize_with = "lenient::opt_nonempty")]
        #[ts(optional = nullable)]
        pg: Option<String>,
    },
    PedinaMuovi {
        #[serde(default, deserialize_with = "lenient::opt_string")]
        #[ts(optional = nullable)]
        id: Option<String>,
        #[serde(deserialize_with = "lenient::f64")]
        x: f64,
        #[serde(deserialize_with = "lenient::f64")]
        y: f64,
        #[ts(as = "Option<bool>", optional = nullable)]
        #[serde(default, deserialize_with = "lenient::bool")]
        finale: bool,
    },
    PedinaSalva {
        #[ts(as = "Option<PedinaIn>", optional = nullable)]
        #[serde(default)]
        pedina: PedinaIn,
    },
    PedinaElimina {
        #[serde(default, deserialize_with = "lenient::opt_string")]
        #[ts(optional = nullable)]
        id: Option<String>,
    },
    Scheda {
        #[ts(as = "Option<String>", optional = nullable)]
        #[serde(default, deserialize_with = "lenient::string")]
        id: String,
        #[ts(as = "Option<Map<String, Value>>", optional = nullable)]
        #[serde(default)]
        scheda: Map<String, Value>,
    },
    Iniziativa {
        #[serde(default, deserialize_with = "lenient::opt_string")]
        #[ts(optional = nullable)]
        azione: Option<String>,
        #[serde(default, deserialize_with = "lenient::opt_string")]
        #[ts(optional = nullable)]
        nome: Option<String>,
        #[serde(default, deserialize_with = "lenient::opt_i64")]
        #[ts(optional = nullable)]
        valore: Option<i64>,
        #[serde(default, deserialize_with = "lenient::opt_nonempty")]
        #[ts(optional = nullable)]
        pedina: Option<String>,
        #[serde(default, deserialize_with = "lenient::opt_string")]
        #[ts(optional = nullable)]
        colore: Option<String>,
        #[ts(as = "Option<bool>", optional = nullable)]
        #[serde(default, deserialize_with = "lenient::bool")]
        nascosta: bool,
        #[serde(default, deserialize_with = "lenient::opt_string")]
        #[ts(optional = nullable)]
        id: Option<String>,
    },
    SessioneApri {
        #[serde(default, deserialize_with = "lenient::opt_nonempty")]
        #[ts(optional = nullable)]
        id: Option<String>,
    },
    NominaMaster {
        #[ts(as = "Option<String>", optional = nullable)]
        #[serde(default, deserialize_with = "lenient::string")]
        id: String,
        #[ts(as = "Option<bool>", optional = nullable)]
        #[serde(default = "sempre", deserialize_with = "lenient::bool")]
        master: bool,
    },
    SessioneInizia {},
    SessionePausa {},
    SessioneChiudi {},
    ImpLeggi {},
    ImpSalva {
        #[ts(as = "Option<ConfigIn>", optional = nullable)]
        #[serde(default)]
        config: ConfigIn,
    },
    ImpAdmin {
        #[ts(as = "Option<String>", optional = nullable)]
        #[serde(default, deserialize_with = "lenient::string")]
        attuale: String,
        #[ts(as = "Option<String>", optional = nullable)]
        #[serde(default, deserialize_with = "lenient::string")]
        utente: String,
        #[ts(as = "Option<String>", optional = nullable)]
        #[serde(default, deserialize_with = "lenient::string")]
        nuova: String,
    },
    ImpPartite {},
    ImpPartitaAzzera {
        #[ts(as = "Option<String>", optional = nullable)]
        #[serde(default, deserialize_with = "lenient::string")]
        id: String,
    },
    ImpUtente {
        #[ts(as = "Option<String>", optional = nullable)]
        #[serde(default, deserialize_with = "lenient::string")]
        id: String,
        #[ts(as = "Option<bool>", optional = nullable)]
        #[serde(default, deserialize_with = "lenient::bool")]
        elimina: bool,
        #[serde(default, deserialize_with = "lenient::opt_bool")]
        #[ts(optional = nullable)]
        master: Option<bool>,
        #[serde(default, deserialize_with = "lenient::opt_bool")]
        #[ts(optional = nullable)]
        admin: Option<bool>,
    },
    /// Elimina più utenti in una volta (pulizia dei vecchi ospiti e dei doppioni dell'account di sistema).
    ImpUtentiElimina {
        #[ts(as = "Option<Vec<String>>", optional = nullable)]
        #[serde(default, deserialize_with = "lenient::strings")]
        ids: Vec<String>,
    },
    Scena {
        #[ts(as = "Option<String>", optional = nullable)]
        #[serde(default, deserialize_with = "lenient::string")]
        id: String,
        #[ts(as = "Option<bool>", optional = nullable)]
        #[serde(default = "sempre", deserialize_with = "lenient::bool")]
        porta_gruppo: bool,
    },
    Griglia {
        #[serde(deserialize_with = "lenient::string")]
        id: String,
        #[serde(default)]
        #[ts(optional = nullable)]
        griglia: Option<GrigliaIn>,
    },
    Nebbia {
        #[serde(default, deserialize_with = "lenient::opt_string")]
        #[ts(optional = nullable)]
        scena: Option<String>,
        #[serde(default, deserialize_with = "lenient::opt_bool")]
        #[ts(optional = nullable)]
        attiva: Option<bool>,
        #[serde(default, deserialize_with = "lenient::opt_string")]
        #[ts(optional = nullable)]
        azione: Option<String>,
        #[ts(as = "Option<Vec<String>>", optional = nullable)]
        #[serde(default, deserialize_with = "lenient::strings")]
        celle: Vec<String>,
    },
    NoteMaster {
        #[ts(as = "Option<String>", optional = nullable)]
        #[serde(default, deserialize_with = "lenient::string")]
        testo: String,
    },
    SvuotaLog {},
    PulisciScena {
        #[serde(default, deserialize_with = "lenient::opt_string")]
        #[ts(optional = nullable)]
        scena: Option<String>,
    },
    ResetPartita {},
    AvventuraAttiva {
        #[ts(as = "Option<String>", optional = nullable)]
        #[serde(default, deserialize_with = "lenient::string")]
        id: String,
    },
    AvventuraNuova {
        #[ts(as = "Option<String>", optional = nullable)]
        #[serde(default, deserialize_with = "lenient::string")]
        titolo: String,
    },
    AvventuraInfo {
        #[serde(flatten)]
        #[ts(skip)]
        campi: Map<String, Value>,
    },
    MappaMeta {
        #[serde(deserialize_with = "lenient::string")]
        id: String,
        #[serde(default, deserialize_with = "lenient::presente")]
        #[ts(optional, type = "unknown")]
        titolo: Option<Option<Value>>,
        #[serde(default, deserialize_with = "lenient::opt_i64")]
        #[ts(optional = nullable)]
        ordine: Option<i64>,
        #[serde(default, deserialize_with = "lenient::presente")]
        #[ts(optional, type = "unknown")]
        note_master: Option<Option<Value>>,
        #[serde(default, deserialize_with = "lenient::presente")]
        #[ts(optional, type = "unknown")]
        gruppo: Option<Option<Value>>,
    },
    MappaElimina {
        #[ts(as = "Option<String>", optional = nullable)]
        #[serde(default, deserialize_with = "lenient::string")]
        id: String,
    },
    DocumentoElimina {
        #[ts(as = "Option<String>", optional = nullable)]
        #[serde(default, deserialize_with = "lenient::string")]
        file: String,
    },
    AvventuraElimina {
        #[ts(as = "Option<String>", optional = nullable)]
        #[serde(default, deserialize_with = "lenient::string")]
        id: String,
    },
}

/// Tutti i nomi di comando conosciuti (stesso ordine della matrice dei permessi).
pub const NOMI: &[&str] = &[
    "tira",
    "chat",
    "ping",
    "righello",
    "scegli_pg",
    "pedina_muovi",
    "pedina_salva",
    "pedina_elimina",
    "scheda",
    "iniziativa",
    "sessione_apri",
    "nomina_master",
    "sessione_inizia",
    "sessione_pausa",
    "sessione_chiudi",
    "imp_leggi",
    "imp_salva",
    "imp_admin",
    "imp_partite",
    "imp_partita_azzera",
    "imp_utente",
    "imp_utenti_elimina",
    "scena",
    "griglia",
    "nebbia",
    "note_master",
    "svuota_log",
    "pulisci_scena",
    "reset_partita",
    "avventura_attiva",
    "avventura_nuova",
    "avventura_info",
    "mappa_meta",
    "mappa_elimina",
    "documento_elimina",
    "avventura_elimina",
];

/// Esito della lettura di un corpo `/api/op`.
pub enum Lettura {
    Ok(Box<Op>),
    /// `op` mancante o sconosciuto: risposta 200 `ok:false` come il server Python.
    Sconosciuta,
    /// Dati con tipi sbagliati: 400.
    NonValida(String),
}

pub fn leggi(corpo: Value) -> Lettura {
    let Value::Object(m) = corpo else {
        return Lettura::NonValida("il comando deve essere un oggetto JSON".into());
    };
    match m.get("op") {
        Some(Value::String(s)) if NOMI.contains(&s.as_str()) => {}
        Some(Value::String(_)) | Some(Value::Null) | None => return Lettura::Sconosciuta,
        Some(_) => return Lettura::NonValida("op non valido".into()),
    }
    match serde_json::from_value::<Op>(Value::Object(m)) {
        Ok(op) => Lettura::Ok(Box::new(op)),
        Err(e) => Lettura::NonValida(format!("dati non validi ({e})")),
    }
}

impl Op {
    pub fn nome(&self) -> &'static str {
        match self {
            Op::Tira { .. } => "tira",
            Op::Chat { .. } => "chat",
            Op::Ping { .. } => "ping",
            Op::Righello { .. } => "righello",
            Op::ScegliPg { .. } => "scegli_pg",
            Op::PedinaMuovi { .. } => "pedina_muovi",
            Op::PedinaSalva { .. } => "pedina_salva",
            Op::PedinaElimina { .. } => "pedina_elimina",
            Op::Scheda { .. } => "scheda",
            Op::Iniziativa { .. } => "iniziativa",
            Op::SessioneApri { .. } => "sessione_apri",
            Op::NominaMaster { .. } => "nomina_master",
            Op::SessioneInizia {} => "sessione_inizia",
            Op::SessionePausa {} => "sessione_pausa",
            Op::SessioneChiudi {} => "sessione_chiudi",
            Op::ImpLeggi {} => "imp_leggi",
            Op::ImpSalva { .. } => "imp_salva",
            Op::ImpAdmin { .. } => "imp_admin",
            Op::ImpPartite {} => "imp_partite",
            Op::ImpPartitaAzzera { .. } => "imp_partita_azzera",
            Op::ImpUtente { .. } => "imp_utente",
            Op::ImpUtentiElimina { .. } => "imp_utenti_elimina",
            Op::Scena { .. } => "scena",
            Op::Griglia { .. } => "griglia",
            Op::Nebbia { .. } => "nebbia",
            Op::NoteMaster { .. } => "note_master",
            Op::SvuotaLog {} => "svuota_log",
            Op::PulisciScena { .. } => "pulisci_scena",
            Op::ResetPartita {} => "reset_partita",
            Op::AvventuraAttiva { .. } => "avventura_attiva",
            Op::AvventuraNuova { .. } => "avventura_nuova",
            Op::AvventuraInfo { .. } => "avventura_info",
            Op::MappaMeta { .. } => "mappa_meta",
            Op::MappaElimina { .. } => "mappa_elimina",
            Op::DocumentoElimina { .. } => "documento_elimina",
            Op::AvventuraElimina { .. } => "avventura_elimina",
        }
    }

    /// Trascinamenti: hanno un limite di frequenza più largo.
    pub fn veloce(&self) -> bool {
        matches!(self, Op::PedinaMuovi { .. } | Op::Righello { .. })
    }
}

#[cfg(test)]
mod test {
    use super::*;
    use serde_json::json;

    #[test]
    fn ogni_nome_si_legge() {
        for n in NOMI {
            let mut corpo = json!({"op": n, "x": 1, "y": 2, "id": "a"});
            if *n == "pedina_muovi" {
                corpo["id"] = json!("p");
            }
            match leggi(corpo) {
                Lettura::Ok(op) => assert_eq!(op.nome(), *n),
                Lettura::NonValida(e) => panic!("{n}: {e}"),
                Lettura::Sconosciuta => panic!("{n} sconosciuta"),
            }
        }
    }

    #[test]
    fn corpi_strani() {
        assert!(matches!(leggi(json!({"op": "boh"})), Lettura::Sconosciuta));
        assert!(matches!(leggi(json!({})), Lettura::Sconosciuta));
        assert!(matches!(leggi(json!({"op": 5})), Lettura::NonValida(_)));
        assert!(matches!(leggi(json!([1])), Lettura::NonValida(_)));
        assert!(matches!(leggi(json!({"op": "ping", "x": "abc", "y": 1})), Lettura::NonValida(_)));
        assert!(matches!(leggi(json!({"op": "chat", "testo": {"a": 1}})), Lettura::NonValida(_)));
        assert!(matches!(
            leggi(json!({"op": "pedina_muovi", "id": [1], "x": 1, "y": 1})),
            Lettura::NonValida(_)
        ));
        assert!(matches!(leggi(json!({"op": "ping", "x": 1e300, "y": 1})), Lettura::NonValida(_)));
    }
}
