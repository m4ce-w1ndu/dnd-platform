//! Catalogo delle avventure: cartelle in AVVENTURE_DIR con avventura.json, mappe, personaggi, mostri, documenti.

use std::collections::BTreeMap;
use std::fs;
use std::io::{Read, Seek, SeekFrom};
use std::path::{Path, PathBuf};
use std::sync::LazyLock;

use regex::Regex;
use serde_json::{json, Map, Value};

use crate::util::id_valido;

pub const IMG_EXT: &[&str] = &["svg", "png", "jpg", "jpeg", "webp"];
pub const DOC_EXT: &[&str] = &["html", "htm", "pdf", "md", "txt", "png", "jpg", "jpeg", "webp", "svg"];

/// Un'avventura così come la vede il client (`avv` nello stato, `catalogo` per il Master).
#[derive(Clone, Debug)]
pub struct Avventura {
    pub id: String,
    pub dati: Map<String, Value>,
}

impl Avventura {
    pub fn titolo(&self) -> String {
        self.dati.get("titolo").and_then(Value::as_str).unwrap_or(&self.id).to_string()
    }
    pub fn mappe(&self) -> &[Value] {
        self.dati.get("mappe").and_then(Value::as_array).map(Vec::as_slice).unwrap_or(&[])
    }
    pub fn personaggi(&self) -> &[Value] {
        self.dati
            .get("personaggi")
            .and_then(Value::as_array)
            .map(Vec::as_slice)
            .unwrap_or(&[])
    }
    pub fn documenti(&self) -> &[Value] {
        self.dati
            .get("documenti")
            .and_then(Value::as_array)
            .map(Vec::as_slice)
            .unwrap_or(&[])
    }
    pub fn ha_mappa(&self, id: &str) -> bool {
        self.mappe().iter().any(|m| m["id"] == id)
    }
    pub fn ha_personaggio(&self, id: &str) -> bool {
        self.personaggi().iter().any(|p| p.get("id").and_then(Value::as_str) == Some(id))
    }
    pub fn personaggio(&self, id: &str) -> Option<&Value> {
        self.personaggi().iter().find(|p| p.get("id").and_then(Value::as_str) == Some(id))
    }
    pub fn prima_mappa(&self) -> Option<String> {
        self.mappe().first().and_then(|m| m["id"].as_str()).map(String::from)
    }
    /// Documento dichiarato nel manifest e solo per il Master?
    pub fn doc_solo_master(&self, file: &str) -> bool {
        self.documenti().iter().any(|d| d["file"] == file && d["solo_master"] == true)
    }

    /// Versione per un ruolo: ai non-Master niente mostri nemici, documenti riservati, note del Master.
    pub fn per_ruolo(&self, master: bool) -> Value {
        let mut a = self.dati.clone();
        if !master {
            let filtra = |k: &str, a: &mut Map<String, Value>, f: &dyn Fn(&Value) -> bool| {
                if let Some(Value::Array(v)) = a.get_mut(k) {
                    v.retain(|x| f(x));
                }
            };
            filtra("mostri", &mut a, &|m| crate::util::vero(m.get("alleato").unwrap_or(&Value::Null)));
            filtra("documenti", &mut a, &|d| d["solo_master"] != true);
            if let Some(Value::Array(mappe)) = a.get_mut("mappe") {
                for m in mappe {
                    if let Some(o) = m.as_object_mut() {
                        o.remove("note_master");
                    }
                }
            }
        }
        Value::Object(a)
    }

    pub fn breve(&self) -> Value {
        let mut o = Map::new();
        for k in ["id", "titolo", "sottotitolo", "descrizione", "livello", "giocatori", "durata"] {
            o.insert(k.into(), self.dati.get(k).cloned().unwrap_or(Value::Null));
        }
        o.insert("mappe".into(), json!(self.mappe().len()));
        o.insert("personaggi".into(), json!(self.personaggi().len()));
        o.insert("documenti".into(), json!(self.documenti()));
        Value::Object(o)
    }
}

pub fn vuota() -> Value {
    json!({"id": null, "titolo": "Nessuna avventura", "mappe": [], "personaggi": [], "mostri": [], "documenti": []})
}

pub fn leggi_json(path: &Path) -> Option<Value> {
    let f = fs::read(path).ok()?;
    if f.len() > 20 * 1024 * 1024 {
        return None;
    }
    serde_json::from_slice(&f).ok()
}

/// Scrittura atomica (file temporaneo + rename).
pub fn scrivi_json(path: &Path, v: &Value) -> std::io::Result<()> {
    if let Some(d) = path.parent() {
        fs::create_dir_all(d)?;
    }
    let tmp = path.with_extension(format!("tmp-{}", crate::util::id_casuale(6)));
    fs::write(&tmp, serde_json::to_vec(v)?)?;
    fs::rename(&tmp, path)
}

fn stringa(m: &Map<String, Value>, k: &str) -> Value {
    m.get(k).cloned().unwrap_or_else(|| Value::String(String::new()))
}

pub fn carica_avventura(base: &Path, aid: &str) -> Option<Avventura> {
    let man = leggi_json(&base.join("avventura.json"))?;
    let man = man.as_object()?;
    let mut mappe = Vec::new();
    let cart = base.join("mappe");
    if let Ok(rd) = fs::read_dir(&cart) {
        let mut nomi: Vec<String> = rd.filter_map(|e| e.ok()).filter_map(|e| e.file_name().into_string().ok()).collect();
        nomi.sort();
        for nome in nomi {
            let Some((stem, ext)) = dividi_ext(&nome) else { continue };
            if !IMG_EXT.contains(&ext.to_lowercase().as_str()) || !cart.join(&nome).is_file() {
                continue;
            }
            let meta = leggi_json(&cart.join(format!("{stem}.json")))
                .and_then(|v| v.as_object().cloned())
                .unwrap_or_default();
            let (w, h) = dimensioni_immagine(&cart.join(&nome)).unwrap_or((1000, 1000));
            let titolo = match meta.get("titolo") {
                Some(t) if crate::util::vero(t) => t.clone(),
                _ => Value::String(capitalizza(&stem.replace('_', " "))),
            };
            let mut sc = Map::new();
            sc.insert("id".into(), json!(stem));
            sc.insert("titolo".into(), titolo);
            sc.insert("gruppo".into(), stringa(&meta, "gruppo"));
            sc.insert("ordine".into(), meta.get("ordine").cloned().unwrap_or(json!(999)));
            sc.insert("file".into(), json!(format!("avventure/{aid}/mappe/{nome}")));
            sc.insert("larghezza".into(), meta.get("larghezza").cloned().unwrap_or(json!(w)));
            sc.insert("altezza".into(), meta.get("altezza").cloned().unwrap_or(json!(h)));
            for k in ["griglia", "inizio", "note_master", "descrizione"] {
                if let Some(v) = meta.get(k).filter(|v| !v.is_null()) {
                    sc.insert(k.into(), v.clone());
                }
            }
            let griglia_ok = sc.get("griglia").map(|g| g.get("cella").is_some_and(crate::util::vero));
            if griglia_ok == Some(false) {
                sc.remove("griglia");
            }
            mappe.push(Value::Object(sc));
        }
    }
    let ordine = |m: &Value| crate::util::numero(&m["ordine"]).unwrap_or(999.0);
    mappe.sort_by(|a, b| {
        ordine(a)
            .partial_cmp(&ordine(b))
            .unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| a["id"].as_str().cmp(&b["id"].as_str()))
    });
    let mut documenti = Vec::new();
    if let Some(Value::Array(docs)) = man.get("documenti") {
        for d in docs {
            let Some(file) = d.get("file").and_then(Value::as_str) else {
                continue;
            };
            if file.is_empty() || file.contains("..") || !base.join("documenti").join(file).is_file() {
                continue;
            }
            documenti.push(json!({"file": file, "titolo": d.get("titolo").cloned().unwrap_or(json!(file)),
                                  "solo_master": crate::util::vero(d.get("solo_master").unwrap_or(&Value::Null))}));
        }
    }
    let lista = |f: &str| match leggi_json(&base.join(f)) {
        Some(Value::Array(v)) => Value::Array(v),
        _ => json!([]),
    };
    let mut dati = Map::new();
    dati.insert("id".into(), json!(aid));
    dati.insert("titolo".into(), man.get("titolo").cloned().unwrap_or(json!(aid)));
    for k in ["sottotitolo", "descrizione", "livello", "giocatori", "durata", "copertina"] {
        dati.insert(k.into(), stringa(man, k));
    }
    dati.insert("mappe".into(), Value::Array(mappe));
    dati.insert("personaggi".into(), lista("personaggi.json"));
    dati.insert("mostri".into(), lista("mostri.json"));
    dati.insert("documenti".into(), Value::Array(documenti));
    Some(Avventura { id: aid.to_string(), dati })
}

pub fn scansiona(dir: &Path) -> BTreeMap<String, Avventura> {
    let mut out = BTreeMap::new();
    let Ok(rd) = fs::read_dir(dir) else { return out };
    for e in rd.filter_map(|e| e.ok()) {
        let Ok(aid) = e.file_name().into_string() else { continue };
        if id_valido(&aid) && e.path().is_dir() {
            if let Some(a) = carica_avventura(&e.path(), &aid) {
                out.insert(aid, a);
            }
        }
    }
    out
}

/// Impronta della cartella avventure (percorso, dimensione, data): se cambia si riscansiona.
pub fn firma(dir: &Path) -> Vec<(PathBuf, u64, i128)> {
    let mut out = Vec::new();
    let mut pila = vec![dir.to_path_buf()];
    while let Some(d) = pila.pop() {
        let Ok(rd) = fs::read_dir(&d) else { continue };
        for e in rd.filter_map(|e| e.ok()) {
            let Ok(md) = e.metadata() else { continue };
            if md.is_dir() {
                pila.push(e.path());
            } else {
                let t = md
                    .modified()
                    .ok()
                    .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
                    .map(|d| d.as_nanos() as i128)
                    .unwrap_or(0);
                out.push((e.path(), md.len(), t));
            }
        }
    }
    out.sort();
    out
}

pub fn dividi_ext(nome: &str) -> Option<(&str, &str)> {
    let i = nome.rfind('.')?;
    if i == 0 {
        return None;
    }
    Some((&nome[..i], &nome[i + 1..]))
}

fn capitalizza(s: &str) -> String {
    let s = s.trim();
    let mut c = s.chars();
    match c.next() {
        Some(p) => p.to_uppercase().collect::<String>() + &c.as_str().to_lowercase(),
        None => String::new(),
    }
}

static SVG_TAG: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"(?s)<svg[^>]*>").unwrap());
static SVG_W: LazyLock<Regex> = LazyLock::new(|| Regex::new(r#"\swidth="([\d.]+)"#).unwrap());
static SVG_H: LazyLock<Regex> = LazyLock::new(|| Regex::new(r#"\sheight="([\d.]+)"#).unwrap());
static SVG_VB: LazyLock<Regex> = LazyLock::new(|| Regex::new(r#"viewBox="[\d.\-]+[ ,]+[\d.\-]+[ ,]+([\d.]+)[ ,]+([\d.]+)""#).unwrap());

/// (larghezza, altezza) di SVG/PNG/JPEG/WEBP leggendo solo l'intestazione.
pub fn dimensioni_immagine(path: &Path) -> Option<(u32, u32)> {
    let mut f = fs::File::open(path).ok()?;
    let mut head = vec![0u8; 4096];
    let n = f.read(&mut head).ok()?;
    head.truncate(n);
    let nome = path.to_string_lossy().to_lowercase();
    let num = |s: &str| {
        s.parse::<f64>()
            .ok()
            .filter(|v| v.is_finite() && *v >= 0.0 && *v < 1e7)
            .map(|v| v as u32)
    };
    if nome.ends_with(".svg") {
        let txt = String::from_utf8_lossy(&head);
        let tag = SVG_TAG
            .find(&txt)
            .map(|m| m.as_str().to_string())
            .unwrap_or_else(|| txt.to_string());
        if let (Some(w), Some(h)) = (SVG_W.captures(&tag), SVG_H.captures(&tag)) {
            if let (Some(w), Some(h)) = (num(&w[1]), num(&h[1])) {
                return Some((w, h));
            }
        }
        if let Some(vb) = SVG_VB.captures(&tag) {
            if let (Some(w), Some(h)) = (num(&vb[1]), num(&vb[2])) {
                return Some((w, h));
            }
        }
        return Some((1000, 1000));
    }
    let be32 = |b: &[u8]| u32::from_be_bytes([b[0], b[1], b[2], b[3]]);
    if head.len() >= 24 && head.starts_with(b"\x89PNG\r\n\x1a\n") {
        return Some((be32(&head[16..20]), be32(&head[20..24])));
    }
    if head.len() >= 30 && &head[..4] == b"RIFF" && &head[8..12] == b"WEBP" {
        let le24 = |b: &[u8]| u32::from(b[0]) | u32::from(b[1]) << 8 | u32::from(b[2]) << 16;
        match &head[12..16] {
            b"VP8X" => return Some((1 + le24(&head[24..27]), 1 + le24(&head[27..30]))),
            b"VP8 " => {
                let w = u16::from_le_bytes([head[26], head[27]]) & 0x3FFF;
                let h = u16::from_le_bytes([head[28], head[29]]) & 0x3FFF;
                return Some((u32::from(w), u32::from(h)));
            }
            b"VP8L" => {
                let b = u32::from_le_bytes([head[21], head[22], head[23], head[24]]);
                return Some(((b & 0x3FFF) + 1, ((b >> 14) & 0x3FFF) + 1));
            }
            _ => {}
        }
    }
    if head.starts_with(b"\xff\xd8") {
        f.seek(SeekFrom::Start(2)).ok()?;
        for _ in 0..10_000 {
            let mut m = [0u8; 2];
            f.read_exact(&mut m).ok()?;
            if m[0] != 0xFF {
                break;
            }
            if matches!(m[1], 0xC0..=0xC3 | 0xC5..=0xC7 | 0xC9..=0xCB | 0xCD..=0xCF) {
                let mut b = [0u8; 7];
                f.read_exact(&mut b).ok()?;
                let h = u16::from_be_bytes([b[3], b[4]]);
                let w = u16::from_be_bytes([b[5], b[6]]);
                return Some((u32::from(w), u32::from(h)));
            }
            let mut l = [0u8; 2];
            f.read_exact(&mut l).ok()?;
            let seg = i64::from(u16::from_be_bytes(l));
            if seg < 2 {
                break;
            }
            f.seek(SeekFrom::Current(seg - 2)).ok()?;
        }
    }
    Some((1000, 1000))
}
