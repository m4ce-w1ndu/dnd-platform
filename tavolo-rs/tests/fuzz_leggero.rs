//! «Fuzzing» su Rust stabile: migliaia di input casuali (ma riproducibili, seme fisso) contro
//! la lettura dei comandi, i dadi, i salvataggi, i pacchetti zip e la logica di gioco vera.
//! Nessun input deve far andare in panico il server; alcune regole devono restare sempre vere.
//! (Il fuzzing guidato dalla copertura, con cargo-fuzz e Rust nightly, è in `fuzz/`.)

use std::path::Path;
use std::sync::Arc;

use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};
use serde_json::{json, Map, Value};
use tavolo::comandi::{leggi, Lettura, NOMI};
use tavolo::modello::{Stato, Utente};
use tavolo::tavolo::{Percorsi, Tavolo};

const CAMPI: &[&str] = &[
    "op", "id", "x", "y", "espr", "testo", "segreto", "danni", "pg", "pedina", "scheda", "azione", "valore", "nome",
    "colore", "nascosta", "celle", "scena", "attiva", "griglia", "titolo", "ordine", "file", "punti", "finale",
    "porta_gruppo", "master", "admin", "elimina", "config", "attuale", "nuova", "utente", "centra", "etichetta", "modo",
];

fn valore(r: &mut StdRng, profondita: u32) -> Value {
    match r.gen_range(0..if profondita > 3 { 6 } else { 9 }) {
        0 => Value::Null,
        1 => json!(r.gen_bool(0.5)),
        2 => json!(r.gen_range(-1_000_000i64..1_000_000)),
        3 => json!(r.gen::<f64>() * 10f64.powi(r.gen_range(-5..300))),
        4 => json!(["1d20", "2d6+3", "d%", "4d20kh1", "100d1000", "", "1d", "<script>", "#fff", "rocco", "01_piazza"][r.gen_range(0..11)]),
        5 => {
            let n = r.gen_range(0..40);
            json!((0..n).map(|_| char::from_u32(r.gen_range(0..0x2FFFF)).unwrap_or('x')).collect::<String>())
        }
        6 => Value::Array((0..r.gen_range(0..6)).map(|_| valore(r, profondita + 1)).collect()),
        _ => {
            let mut m = Map::new();
            for _ in 0..r.gen_range(0..6) {
                m.insert(CAMPI[r.gen_range(0..CAMPI.len())].into(), valore(r, profondita + 1));
            }
            Value::Object(m)
        }
    }
}

fn comando(r: &mut StdRng) -> Value {
    let mut m = Map::new();
    m.insert("op".into(), json!(NOMI[r.gen_range(0..NOMI.len())]));
    for _ in 0..r.gen_range(0..8) {
        m.insert(CAMPI[r.gen_range(1..CAMPI.len())].into(), valore(r, 0));
    }
    Value::Object(m)
}

#[test]
fn lettura_comandi_e_salvataggi() {
    let mut r = StdRng::seed_from_u64(42);
    for _ in 0..100_000 {
        let v = if r.gen_bool(0.8) { comando(&mut r) } else { valore(&mut r, 0) };
        let _ = leggi(v.clone());
        let _ = serde_json::from_value::<Stato>(v.clone());
        let _ = serde_json::from_value::<Utente>(v);
    }
}

#[test]
fn dadi() {
    let mut r = StdRng::seed_from_u64(7);
    let pezzi = ["d", "1", "2", "0", "20", "%", "kh", "kl", "+", "-", " ", "9999999999", "x", "D"];
    for _ in 0..200_000 {
        let s: String = (0..r.gen_range(0..20)).map(|_| pezzi[r.gen_range(0..pezzi.len())]).collect();
        if let Ok(t) = tavolo::dadi::tira(&s) {
            assert!(t["totale"].is_i64(), "{s}");
        }
        let _ = tavolo::dadi::raddoppia_dadi(&s);
    }
}

#[test]
fn pacchetti_zip_rovinati() {
    use std::io::Write;
    let dir = tempfile::tempdir().unwrap();
    let mut buf = std::io::Cursor::new(Vec::new());
    {
        let mut z = zip::ZipWriter::new(&mut buf);
        let o = zip::write::SimpleFileOptions::default();
        z.start_file("p/avventura.json", o).unwrap();
        z.write_all(br#"{"id":"buono","titolo":"T"}"#).unwrap();
        z.start_file("p/mappe/a.svg", o).unwrap();
        z.write_all(&[b'x'; 5000]).unwrap();
        z.finish().unwrap();
    }
    let buono = buf.into_inner();
    let mut r = StdRng::seed_from_u64(3);
    for _ in 0..3000 {
        let mut d = buono.clone();
        for _ in 0..r.gen_range(1..10) {
            let i = r.gen_range(0..d.len());
            d[i] = r.gen();
        }
        if r.gen_bool(0.2) {
            d.truncate(r.gen_range(0..d.len()));
        }
        if let Ok((_, tmp)) = tavolo::pacchetti::estrai(&d, dir.path()) {
            assert!(tmp.starts_with(dir.path()));
            std::fs::remove_dir_all(tmp).unwrap();
        }
    }
    // niente è uscito dalla cartella
    for e in std::fs::read_dir(dir.path()).unwrap() {
        assert!(!e.unwrap().file_name().to_string_lossy().starts_with(".tmp-"));
    }
}

/// Logica di gioco vera: un tavolo con l'avventura di prova, quattro ruoli, comandi casuali.
#[tokio::test(flavor = "multi_thread")]
async fn logica_di_gioco() {
    let dir = tempfile::tempdir().unwrap();
    let avv = dir.path().join("avventure");
    copia(Path::new(env!("CARGO_MANIFEST_DIR")).join("e2e/fixture/avventure").as_path(), &avv);
    let percorsi = Percorsi { dati: dir.path().join("dati"), avventure: avv, web: dir.path().into() };
    std::env::set_var("MASTER_PASSWORD", "fuzz-password");
    let db = tavolo::db::Db::apri(&percorsi.dati.join("tavolo.db")).await.unwrap();
    let (mut t, _) = Tavolo::nuovo(percorsi, db, "v".into(), Arc::new(Default::default())).await.unwrap();
    let mut ruoli = vec![];
    for (i, (master, admin)) in [(false, false), (false, false), (true, false), (false, true)].into_iter().enumerate() {
        let mut u = Utente::nuovo(&format!("U{i}"), "#123456", if master { "master" } else { "giocatore" });
        u.admin = admin;
        u.master_ok = master || admin;
        u.char = (i == 0).then(|| "rocco".into());
        let id = format!("utente{i}");
        t.utenti.insert(id.clone(), u);
        ruoli.push(id);
    }
    t.attiva_avventura(Some("prova".into())).await;
    t.crea_pedina_pg("utente0", "rocco", "#123456");

    let mut r = StdRng::seed_from_u64(1234);
    let mut eseguiti = 0;
    for _ in 0..20_000 {
        let mut c = comando(&mut r);
        // comandi che cancellano dati del disco: con id casuali sono innocui, ma niente reset continui
        if c["op"] == "avventura_elimina" || c["op"] == "imp_partita_azzera" {
            c["id"] = json!("non-esiste");
        }
        if c["op"] == "imp_utente" && c.get("elimina").is_some() {
            c["elimina"] = json!(false);
        }
        let Lettura::Ok(op) = leggi(c) else { continue };
        let chi = ruoli[r.gen_range(0..ruoli.len())].clone();
        let pedine_prima: Vec<_> = t.stato.pedine.keys().cloned().collect();
        let nascoste_prima = t.stato.pedine.values().filter(|p| p.nascosta).count();
        let master = t.utenti[&chi].is_master();
        let risposta = t.op(&chi, *op.clone(), "127.0.0.1").await;
        eseguiti += 1;
        assert!(matches!(risposta.status, 200 | 400), "{} → {}", op.nome(), risposta.status);
        // regole che devono restare vere
        assert!(t.stato.log.len() <= tavolo::tavolo::MAX_LOG);
        for p in t.stato.pedine.values() {
            assert!((0.5..=6.0).contains(&p.taglia.0), "taglia {}", p.taglia.0);
            assert!(p.nome.chars().count() <= 40);
            assert!(p.condizioni.len() <= 12);
            if let Some(c) = &p.colore {
                assert!(c.starts_with('#') && c.len() <= 9, "colore {c}");
            }
        }
        if !master {
            // l'unica pedina che un giocatore può far nascere è quella del suo personaggio (scegli_pg)
            for (k, p) in t.stato.pedine.iter().filter(|(k, _)| !pedine_prima.contains(k)) {
                assert!(op.nome() == "scegli_pg" && p.pg.is_some() && p.proprietario.as_deref() == Some(chi.as_str()),
                        "un giocatore ha creato la pedina {k} con {}", op.nome());
            }
            assert!(t.stato.pedine.values().filter(|p| p.nascosta).count() <= nascoste_prima, "un giocatore ha nascosto una pedina");
        }
        // i ruoli devono restare quelli del test (un admin può nominare altri Master: si rimette a posto)
        for (i, id) in ruoli.iter().enumerate() {
            if let Some(u) = t.utenti.get_mut(id) {
                u.role = if i == 2 { "master".into() } else { "giocatore".into() };
                u.admin = i == 3;
                u.master_ok = i >= 2;
            }
        }
    }
    assert!(eseguiti > 5000, "troppi pochi comandi validi: {eseguiti}");
}

fn copia(da: &Path, a: &Path) {
    std::fs::create_dir_all(a).unwrap();
    for e in std::fs::read_dir(da).unwrap() {
        let e = e.unwrap();
        if e.path().is_dir() {
            copia(&e.path(), &a.join(e.file_name()));
        } else {
            std::fs::copy(e.path(), a.join(e.file_name())).unwrap();
        }
    }
}
