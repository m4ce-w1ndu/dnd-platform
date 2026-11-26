//! Piccoli strumenti condivisi: numeri JSON, deserializzatori tolleranti, id casuali, validazioni.

use std::sync::LazyLock;
use std::time::{SystemTime, UNIX_EPOCH};

use base64::Engine;
use rand::RngCore;
use regex::Regex;
use serde::de::{self, Deserializer};
use serde::{Deserialize, Serialize, Serializer};
use serde_json::Value;

/// Secondi dall'epoch, come `time.time()` in Python.
pub fn adesso() -> f64 {
    SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs_f64()).unwrap_or(0.0)
}

/// `n` caratteri esadecimali casuali (come `uuid.uuid4().hex[:n]`).
pub fn id_casuale(n: usize) -> String {
    let mut b = vec![0u8; n.div_ceil(2)];
    rand::rngs::OsRng.fill_bytes(&mut b);
    let mut s = hex::encode(b);
    s.truncate(n);
    s
}

/// Segreto URL-safe da `n` byte casuali (come `secrets.token_urlsafe(n)`).
pub fn token(n: usize) -> String {
    let mut b = vec![0u8; n];
    rand::rngs::OsRng.fill_bytes(&mut b);
    base64::engine::general_purpose::URL_SAFE_NO_PAD.encode(b)
}

/// Confronto a tempo costante.
pub fn uguali(a: &str, b: &str) -> bool {
    use subtle::ConstantTimeEq;
    a.len() == b.len() && bool::from(a.as_bytes().ct_eq(b.as_bytes()))
}

/// Tronca a `n` caratteri (non byte), come `s[:n]` in Python.
pub fn tronca(s: &str, n: usize) -> String {
    match s.char_indices().nth(n) {
        Some((i, _)) => s[..i].to_string(),
        None => s.to_string(),
    }
}

/// Numero JSON: si scrive come intero quando non ha parte decimale (20 e non 20.0).
#[derive(Clone, Copy, Debug, PartialEq, PartialOrd, Default)]
pub struct N(pub f64);

impl Serialize for N {
    fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        let v = self.0;
        if !v.is_finite() {
            s.serialize_none()
        } else if v.fract() == 0.0 && v.abs() < 9.0e15 {
            s.serialize_i64(v as i64)
        } else {
            s.serialize_f64(v)
        }
    }
}

impl<'de> Deserialize<'de> for N {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        let v = Value::deserialize(d)?;
        numero(&v).map(N).ok_or_else(|| de::Error::custom("numero non valido"))
    }
}

/// Converte come `float()` di Python: numeri, booleani e stringhe numeriche. Mai NaN/infinito.
pub fn numero(v: &Value) -> Option<f64> {
    let f = match v {
        Value::Number(n) => n.as_f64()?,
        Value::Bool(b) => f64::from(u8::from(*b)),
        Value::String(s) => s.trim().parse::<f64>().ok()?,
        _ => return None,
    };
    f.is_finite().then_some(f)
}

/// Come `bool()` di Python sui valori JSON.
pub fn vero(v: &Value) -> bool {
    match v {
        Value::Null => false,
        Value::Bool(b) => *b,
        Value::Number(n) => n.as_f64().is_some_and(|f| f != 0.0),
        Value::String(s) => !s.is_empty(),
        Value::Array(a) => !a.is_empty(),
        Value::Object(o) => !o.is_empty(),
    }
}

/// Testo da un valore scalare (come `str()`); oggetti e liste sono rifiutati.
pub fn testo(v: &Value) -> Option<String> {
    match v {
        Value::String(s) => Some(s.clone()),
        Value::Number(n) => Some(n.to_string()),
        Value::Bool(b) => Some(if *b { "True".into() } else { "False".into() }),
        _ => None,
    }
}

pub mod lenient {
    //! Deserializzatori tolleranti per i dati salvati e per i campi del client.
    use super::*;

    pub fn bool<'de, D: Deserializer<'de>>(d: D) -> Result<bool, D::Error> {
        Ok(vero(&Value::deserialize(d)?))
    }

    pub fn opt_bool<'de, D: Deserializer<'de>>(d: D) -> Result<Option<bool>, D::Error> {
        Ok(Some(vero(&Value::deserialize(d)?)))
    }

    pub fn string<'de, D: Deserializer<'de>>(d: D) -> Result<String, D::Error> {
        let v = Value::deserialize(d)?;
        match v {
            Value::Null => Ok(String::new()),
            v => testo(&v).ok_or_else(|| de::Error::custom("testo non valido")),
        }
    }

    pub fn opt_string<'de, D: Deserializer<'de>>(d: D) -> Result<Option<String>, D::Error> {
        let v = Value::deserialize(d)?;
        match v {
            Value::Null => Ok(None),
            v => testo(&v).map(Some).ok_or_else(|| de::Error::custom("testo non valido")),
        }
    }

    /// Come `x or None`: stringa vuota → None.
    pub fn opt_nonempty<'de, D: Deserializer<'de>>(d: D) -> Result<Option<String>, D::Error> {
        Ok(opt_string(d)?.filter(|s| !s.is_empty()))
    }

    pub fn i64<'de, D: Deserializer<'de>>(d: D) -> Result<i64, D::Error> {
        let v = Value::deserialize(d)?;
        if v.is_null() {
            return Ok(0);
        }
        let f = numero(&v).ok_or_else(|| de::Error::custom("numero intero non valido"))?;
        if f.abs() > 1e15 {
            return Err(de::Error::custom("numero troppo grande"));
        }
        Ok(f.trunc() as i64)
    }

    pub fn opt_i64<'de, D: Deserializer<'de>>(d: D) -> Result<Option<i64>, D::Error> {
        i64(d).map(Some)
    }

    pub fn f64<'de, D: Deserializer<'de>>(d: D) -> Result<f64, D::Error> {
        let v = Value::deserialize(d)?;
        let f = numero(&v).ok_or_else(|| de::Error::custom("numero non valido"))?;
        if f.abs() > 1e12 {
            return Err(de::Error::custom("numero troppo grande"));
        }
        Ok(f)
    }

    pub fn opt_n<'de, D: Deserializer<'de>>(d: D) -> Result<Option<N>, D::Error> {
        let v = Value::deserialize(d)?;
        Ok(numero(&v).map(N))
    }

    pub fn n_or<'de, D: Deserializer<'de>>(d: D) -> Result<N, D::Error> {
        let v = Value::deserialize(d)?;
        Ok(N(numero(&v).unwrap_or(1.0)))
    }

    /// Lista di testi: gli elementi non scalari vengono scartati.
    pub fn strings<'de, D: Deserializer<'de>>(d: D) -> Result<Vec<String>, D::Error> {
        let v = Value::deserialize(d)?;
        match v {
            Value::Array(a) => Ok(a.iter().filter_map(testo).collect()),
            Value::Null => Ok(vec![]),
            _ => Err(de::Error::custom("lista non valida")),
        }
    }

    /// Campo presente nel JSON (anche se null): `Some(None)`; assente: `None` (con `#[serde(default)]`).
    pub fn presente<'de, D: Deserializer<'de>, T: Deserialize<'de>>(d: D) -> Result<Option<Option<T>>, D::Error> {
        Ok(Some(Option::<T>::deserialize(d)?))
    }

    pub fn presente_n<'de, D: Deserializer<'de>>(d: D) -> Result<Option<Option<N>>, D::Error> {
        let v = Value::deserialize(d)?;
        match v {
            Value::Null => Ok(Some(None)),
            v => numero(&v)
                .map(|f| Some(Some(N(f))))
                .ok_or_else(|| de::Error::custom("numero non valido")),
        }
    }
}

static COLORE_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"^#[0-9a-fA-F]{3,8}$").unwrap());
pub static ID_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"^[a-z0-9][a-z0-9_\-]{0,60}$").unwrap());
static SPAZI_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"\s+").unwrap());

pub fn colore_valido(c: Option<&str>, predefinito: &str) -> String {
    let c = c.unwrap_or("").trim();
    if COLORE_RE.is_match(c) {
        c.to_string()
    } else {
        predefinito.to_string()
    }
}

pub fn id_valido(id: &str) -> bool {
    ID_RE.is_match(id)
}

/// Nomi che un giocatore non può usare (oltre al nome dell'account admin).
pub fn nome_riservato(nome: &str, utente_admin: &str) -> bool {
    let n = SPAZI_RE.replace_all(nome, " ").trim().to_lowercase();
    matches!(n.as_str(), "admin" | "amministratore" | "master" | "sistema") || n == utente_admin.to_lowercase()
}

/// Id leggibile da un titolo: «Àrè Città!» → «are-citta».
pub fn slug(t: &str, max: usize) -> String {
    let t: String = t
        .to_lowercase()
        .chars()
        .map(|c| match c {
            'à' => 'a',
            'è' | 'é' => 'e',
            'ì' => 'i',
            'ò' => 'o',
            'ù' => 'u',
            'ç' => 'c',
            c => c,
        })
        .collect();
    static NON_ALNUM: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"[^a-z0-9]+").unwrap());
    let s = NON_ALNUM.replace_all(&t, "-");
    let s = s.trim_matches('-');
    let s: String = s.chars().take(max).collect();
    let s = s.trim_matches('-').to_string();
    if s.is_empty() {
        "avventura".into()
    } else {
        s
    }
}

#[cfg(test)]
mod test {
    use super::*;

    #[test]
    fn numeri_interi_senza_decimali() {
        assert_eq!(serde_json::to_string(&N(20.0)).unwrap(), "20");
        assert_eq!(serde_json::to_string(&N(2.5)).unwrap(), "2.5");
        assert_eq!(serde_json::to_string(&N(f64::NAN)).unwrap(), "null");
    }

    #[test]
    fn nomi_riservati() {
        for n in ["admin", " Admin ", "MASTER", "sis  tema".replace("  ", "").as_str(), "capo"] {
            assert!(nome_riservato(n, "capo"), "{n}");
        }
        assert!(!nome_riservato("Gimli", "admin"));
        assert!(nome_riservato("ad\tmin".replace('\t', "").as_str(), "admin"));
    }

    #[test]
    fn colori() {
        assert_eq!(colore_valido(Some("#12ab34"), "#000"), "#12ab34");
        assert_eq!(colore_valido(Some("red;}"), "#000"), "#000");
        assert_eq!(colore_valido(None, "#000"), "#000");
    }

    #[test]
    fn slug_italiani() {
        assert_eq!(slug("Àrè Città!", 40), "are-citta");
        assert_eq!(slug("!!!", 40), "avventura");
        assert_eq!(tronca("àèìòù", 2), "àè");
    }
}
