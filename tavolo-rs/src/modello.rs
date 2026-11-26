//! Dati del tavolo: partita, pedine, cronologia, iniziativa, utenti, configurazione.
//!
//! Stesso formato JSON del server Python (le partite e gli utenti sono salvati come JSON in SQLite).
//! La lettura è tollerante (tipi «sbagliati» nei vecchi salvataggi non fanno fallire il caricamento)
//! e i campi sconosciuti vengono conservati (`altro`).

use std::collections::BTreeMap;

use indexmap::IndexMap;
use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};

use crate::util::{lenient, N};

fn uno() -> N {
    N(1.0)
}
fn falso(b: &bool) -> bool {
    !*b
}

#[derive(Clone, Debug, Default, Serialize, Deserialize, PartialEq)]
pub struct Pedina {
    #[serde(deserialize_with = "lenient::string")]
    pub id: String,
    #[serde(default, deserialize_with = "lenient::opt_string", skip_serializing_if = "Option::is_none")]
    pub scena: Option<String>,
    #[serde(default, deserialize_with = "lenient::opt_n")]
    pub x: Option<N>,
    #[serde(default, deserialize_with = "lenient::opt_n")]
    pub y: Option<N>,
    #[serde(default, deserialize_with = "lenient::string")]
    pub nome: String,
    #[serde(default, deserialize_with = "lenient::opt_string", skip_serializing_if = "Option::is_none")]
    pub colore: Option<String>,
    #[serde(default, deserialize_with = "lenient::opt_string", skip_serializing_if = "Option::is_none")]
    pub icona: Option<String>,
    #[serde(default = "uno", deserialize_with = "lenient::n_or")]
    pub taglia: N,
    #[serde(default, deserialize_with = "lenient::opt_n", skip_serializing_if = "Option::is_none")]
    pub pf: Option<N>,
    #[serde(default, deserialize_with = "lenient::opt_n", skip_serializing_if = "Option::is_none")]
    pub pfmax: Option<N>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub ca: Option<Value>,
    #[serde(default, deserialize_with = "lenient::bool", skip_serializing_if = "falso")]
    pub nascosta: bool,
    #[serde(default, deserialize_with = "lenient::strings")]
    pub condizioni: Vec<String>,
    #[serde(default, deserialize_with = "lenient::opt_string", skip_serializing_if = "Option::is_none")]
    pub tipo: Option<String>,
    #[serde(default, deserialize_with = "lenient::opt_string", skip_serializing_if = "Option::is_none")]
    pub pg: Option<String>,
    #[serde(default, deserialize_with = "lenient::opt_string", skip_serializing_if = "Option::is_none")]
    pub mostro: Option<String>,
    #[serde(default, deserialize_with = "lenient::opt_string", skip_serializing_if = "Option::is_none")]
    pub proprietario: Option<String>,
    #[serde(default, deserialize_with = "lenient::opt_n", skip_serializing_if = "Option::is_none")]
    pub slot: Option<N>,
    #[serde(flatten)]
    pub altro: Map<String, Value>,
}

/// Una voce della cronologia (tiro, chat, messaggio di sistema). I campi specifici restano in `resto`.
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Voce {
    #[serde(default, deserialize_with = "lenient::string")]
    pub id: String,
    #[serde(default, deserialize_with = "lenient::f64")]
    pub ora: f64,
    #[serde(default, deserialize_with = "lenient::string")]
    pub tipo: String,
    #[serde(default, deserialize_with = "lenient::opt_string", skip_serializing_if = "Option::is_none")]
    pub da: Option<String>,
    #[serde(default, deserialize_with = "lenient::bool", skip_serializing_if = "falso")]
    pub segreto: bool,
    #[serde(flatten)]
    pub resto: Map<String, Value>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct VoceIniziativa {
    #[serde(deserialize_with = "lenient::string")]
    pub id: String,
    #[serde(default, deserialize_with = "lenient::string")]
    pub nome: String,
    #[serde(default, deserialize_with = "lenient::i64")]
    pub valore: i64,
    #[serde(default, deserialize_with = "lenient::opt_string")]
    pub pedina: Option<String>,
    #[serde(default, deserialize_with = "lenient::string")]
    pub colore: String,
    #[serde(default, deserialize_with = "lenient::bool")]
    pub nascosta: bool,
    #[serde(default, deserialize_with = "lenient::opt_string", skip_serializing_if = "Option::is_none")]
    pub da: Option<String>,
    #[serde(flatten)]
    pub altro: Map<String, Value>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Iniziativa {
    #[serde(default)]
    pub ordine: Vec<VoceIniziativa>,
    #[serde(default, deserialize_with = "lenient::i64")]
    pub turno: i64,
    #[serde(default = "round1", deserialize_with = "lenient::i64")]
    pub round: i64,
}

fn round1() -> i64 {
    1
}

impl Default for Iniziativa {
    fn default() -> Self {
        Iniziativa { ordine: vec![], turno: 0, round: 1 }
    }
}

#[derive(Clone, Debug, Default, Serialize, Deserialize, PartialEq)]
pub struct Nebbia {
    #[serde(default, deserialize_with = "lenient::bool")]
    pub attiva: bool,
    #[serde(default, deserialize_with = "lenient::strings")]
    pub celle: Vec<String>,
}

/// La partita di un'avventura (riga di `partite`).
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Stato {
    #[serde(default = "due")]
    pub versione: Value,
    #[serde(default, deserialize_with = "lenient::opt_string")]
    pub avventura: Option<String>,
    #[serde(default, deserialize_with = "lenient::opt_string")]
    pub scena: Option<String>,
    #[serde(default)]
    pub nebbia: IndexMap<String, Nebbia>,
    #[serde(default)]
    pub pedine: IndexMap<String, Pedina>,
    #[serde(default)]
    pub log: Vec<Voce>,
    #[serde(default)]
    pub iniziativa: Iniziativa,
    #[serde(default)]
    pub schede: IndexMap<String, Map<String, Value>>,
    #[serde(default, deserialize_with = "lenient::string")]
    pub note_master: String,
    #[serde(flatten)]
    pub altro: Map<String, Value>,
}

fn due() -> Value {
    Value::from(2)
}

/// Chiavi della partita che `/api/importa` può sostituire.
pub const CHIAVI_STATO: &[&str] =
    &["versione", "avventura", "scena", "nebbia", "pedine", "log", "iniziativa", "schede", "note_master"];

impl Stato {
    pub fn vuoto(aid: Option<&str>, prima_mappa: Option<String>) -> Stato {
        Stato {
            versione: due(),
            avventura: aid.map(String::from),
            scena: prima_mappa,
            nebbia: IndexMap::new(),
            pedine: IndexMap::new(),
            log: vec![],
            iniziativa: Iniziativa::default(),
            schede: IndexMap::new(),
            note_master: String::new(),
            altro: Map::new(),
        }
    }
}

/// Un utente (riga di `utenti`, colonna `dati`).
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Utente {
    #[serde(default, deserialize_with = "lenient::string")]
    pub secret: String,
    #[serde(default, deserialize_with = "lenient::string")]
    pub name: String,
    #[serde(default = "rosso", deserialize_with = "lenient::string")]
    pub color: String,
    #[serde(default = "giocatore", deserialize_with = "lenient::string")]
    pub role: String,
    #[serde(default, deserialize_with = "lenient::opt_string")]
    pub char: Option<String>,
    #[serde(default, deserialize_with = "lenient::bool", skip_serializing_if = "falso")]
    pub admin: bool,
    #[serde(default, deserialize_with = "lenient::bool", skip_serializing_if = "falso")]
    pub master_ok: bool,
    #[serde(default, deserialize_with = "lenient::f64")]
    pub seen: f64,
    #[serde(default, deserialize_with = "lenient::opt_string", skip_serializing_if = "Option::is_none")]
    pub account: Option<String>,
    #[serde(default, deserialize_with = "lenient::opt_string", skip_serializing_if = "Option::is_none")]
    pub avatar: Option<String>,
    #[serde(default, deserialize_with = "lenient::opt_string", skip_serializing_if = "Option::is_none")]
    pub provider: Option<String>,
    #[serde(flatten)]
    pub altro: Map<String, Value>,
}

fn rosso() -> String {
    "#c0392b".into()
}
fn giocatore() -> String {
    "giocatore".into()
}

impl Utente {
    pub fn nuovo(name: &str, color: &str, role: &str) -> Utente {
        Utente {
            secret: crate::util::token(18),
            name: name.into(),
            color: color.into(),
            role: role.into(),
            char: None,
            admin: false,
            master_ok: false,
            seen: crate::util::adesso(),
            account: None,
            avatar: None,
            provider: None,
            altro: Map::new(),
        }
    }
    pub fn is_master(&self) -> bool {
        self.role == "master"
    }
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct OAuthConf {
    #[serde(default, deserialize_with = "lenient::bool")]
    pub attivo: bool,
    #[serde(default, deserialize_with = "lenient::string")]
    pub id: String,
    #[serde(default, deserialize_with = "lenient::string")]
    pub secret: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AdminConf {
    #[serde(default = "admin", deserialize_with = "lenient::string")]
    pub utente: String,
    /// Vecchio hash PBKDF2-SHA256 (200 000 iterazioni) del server Python: tenuto finché serve un ritorno al Python.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub sale: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub hash: Option<String>,
    /// Hash Argon2id (formato PHC). Se presente è quello che conta.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub argon2: Option<String>,
}

fn admin() -> String {
    "admin".into()
}

impl Default for AdminConf {
    fn default() -> Self {
        AdminConf { utente: admin(), sale: None, hash: None, argon2: None }
    }
}
fn vero_() -> bool {
    true
}
fn nome_tavolo() -> String {
    "Tavolo Virtuale".into()
}

/// Impostazioni modificabili dal browser (chiave `config` in `impostazioni`).
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Config {
    #[serde(default = "nome_tavolo", deserialize_with = "lenient::string")]
    pub nome_tavolo: String,
    #[serde(default, deserialize_with = "lenient::string")]
    pub public_url: String,
    #[serde(default = "vero_", deserialize_with = "lenient::bool")]
    pub ospiti: bool,
    #[serde(default, deserialize_with = "lenient::string")]
    pub password_giocatori: String,
    #[serde(default)]
    pub oauth: BTreeMap<String, OAuthConf>,
    #[serde(default)]
    pub admin: AdminConf,
    #[serde(flatten)]
    pub altro: Map<String, Value>,
}

impl Default for Config {
    fn default() -> Self {
        serde_json::from_value(Value::Object(Map::new())).expect("config predefinita")
    }
}

#[cfg(test)]
mod test {
    use super::*;
    use serde_json::json;

    #[test]
    fn stato_tollerante_e_campi_sconosciuti() {
        let v = json!({"versione": 2, "avventura": "x", "scena": 5, "pedine": {"a": {"id": "a", "x": "12", "y": null,
            "pf": "boh", "taglia": null, "condizioni": ["Prono", 3, {"x": 1}], "nuovo_campo": [1]}},
            "log": [{"id": "l", "ora": 1.5, "tipo": "tiro", "totale": 7, "segreto": 1}], "extra": true,
            "iniziativa": {"ordine": [{"id": "i", "nome": "A", "valore": "12"}]}});
        let s: Stato = serde_json::from_value(v).unwrap();
        let p = &s.pedine["a"];
        assert_eq!(p.x, Some(N(12.0)));
        assert_eq!(p.pf, None);
        assert_eq!(p.condizioni, vec!["Prono", "3"]);
        assert_eq!(p.altro["nuovo_campo"], json!([1]));
        assert!(s.log[0].segreto);
        assert_eq!(s.iniziativa.ordine[0].valore, 12);
        assert_eq!(s.iniziativa.round, 1);
        assert_eq!(s.scena.as_deref(), Some("5"));
        let out = serde_json::to_value(&s).unwrap();
        assert_eq!(out["extra"], json!(true));
        assert_eq!(out["log"][0]["totale"], json!(7));
    }

    #[test]
    fn utente_python() {
        let u: Utente = serde_json::from_value(json!({"secret": "s", "name": "Admin", "color": "#e0b04a", "role": "master",
            "char": null, "admin": true, "master_ok": true, "seen": 1.7e9, "account": "discord:1"})).unwrap();
        assert!(u.admin && u.master_ok && u.is_master());
        let c: Config = serde_json::from_value(json!({"admin": {"utente": "admin", "sale": "ab", "hash": "cd"}})).unwrap();
        assert!(c.ospiti);
        assert_eq!(c.nome_tavolo, "Tavolo Virtuale");
    }
}
