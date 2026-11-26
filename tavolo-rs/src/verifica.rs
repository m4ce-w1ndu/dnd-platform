//! `tavolo verifica-db <file>`: controlla che un database del server Python si carichi senza perdite.
//!
//! Lavora su una COPIA (il file indicato non viene mai toccato): applica le migrazioni, legge configurazione,
//! utenti e partite con i tipi del server Rust, li riserializza e confronta il risultato con l'originale.

use std::path::Path;

use anyhow::{Context, Result};
use serde_json::Value;

use crate::db::Db;
use crate::modello::{Config, Stato};

/// Uguaglianza tra JSON ignorando 2 vs 2.0 e i campi falsi/nulli omessi in uscita.
fn equivalenti(a: &Value, b: &Value) -> bool {
    match (a, b) {
        (Value::Number(x), Value::Number(y)) => x.as_f64() == y.as_f64(),
        (Value::Object(x), Value::Object(y)) => {
            let chiavi: std::collections::BTreeSet<&String> = x.keys().chain(y.keys()).collect();
            chiavi.into_iter().all(|k| {
                let (va, vb) = (x.get(k).unwrap_or(&Value::Null), y.get(k).unwrap_or(&Value::Null));
                equivalenti(va, vb) || (vuoto(va) && vuoto(vb))
            })
        }
        (Value::Array(x), Value::Array(y)) => x.len() == y.len() && x.iter().zip(y).all(|(a, b)| equivalenti(a, b)),
        _ => a == b,
    }
}

fn vuoto(v: &Value) -> bool {
    matches!(v, Value::Null | Value::Bool(false))
}

/// Differenze (percorso) tra originale e riletto, al massimo `max`.
fn differenze(a: &Value, b: &Value, percorso: &str, out: &mut Vec<String>, max: usize) {
    if out.len() >= max || equivalenti(a, b) {
        return;
    }
    match (a, b) {
        (Value::Object(x), Value::Object(y)) => {
            for k in x.keys().chain(y.keys()) {
                let (va, vb) = (x.get(k).unwrap_or(&Value::Null), y.get(k).unwrap_or(&Value::Null));
                if !(vuoto(va) && vuoto(vb)) {
                    differenze(va, vb, &format!("{percorso}.{k}"), out, max);
                }
            }
        }
        (Value::Array(x), Value::Array(y)) if x.len() == y.len() => {
            for (i, (va, vb)) in x.iter().zip(y).enumerate() {
                differenze(va, vb, &format!("{percorso}[{i}]"), out, max);
            }
        }
        _ => out.push(format!("{percorso}: {} → {}", crate::util::tronca(&a.to_string(), 80), crate::util::tronca(&b.to_string(), 80))),
    }
}

pub async fn verifica_db(originale: &Path) -> Result<bool> {
    let tmp = tempfile_dir()?;
    let copia = tmp.join("tavolo.db");
    std::fs::copy(originale, &copia).with_context(|| format!("copia di {}", originale.display()))?;
    for ext in ["-wal", "-shm"] {
        let f = originale.with_file_name(format!("{}{ext}", originale.file_name().unwrap().to_string_lossy()));
        if f.exists() {
            std::fs::copy(&f, tmp.join(format!("tavolo.db{ext}")))?;
        }
    }
    let db = Db::apri(&copia).await?;
    let mut ok = true;
    println!("Verifica di {} (su una copia in {})", originale.display(), tmp.display());

    let grezza = db.get("config").await?.unwrap_or(Value::Null);
    match serde_json::from_value::<Config>(grezza.clone()) {
        Ok(c) => {
            let riletta = serde_json::to_value(&c)?;
            let mut d = vec![];
            differenze(&grezza, &riletta, "config", &mut d, 20);
            println!("✓ configurazione: utente admin «{}», hash {}, ospiti {}, provider attivi: {}",
                c.admin.utente,
                if c.admin.argon2.is_some() { "Argon2" } else if c.admin.hash.is_some() { "PBKDF2 (verrà convertito al primo accesso)" } else { "ASSENTE" },
                c.ospiti,
                c.oauth.iter().filter(|(_, o)| o.attivo).map(|(k, _)| k.as_str()).collect::<Vec<_>>().join(", "));
            for x in &d {
                println!("  ✗ differenza: {x}");
                ok = false;
            }
        }
        Err(e) => {
            println!("✗ configurazione illeggibile: {e}");
            ok = false;
        }
    }

    let (utenti, account, scartati) = db.utenti().await?;
    let grezzi: Vec<(String, String)> = sqlx::query_as("SELECT id, dati FROM utenti").fetch_all(&db.pool).await?;
    let mut diff_utenti = 0;
    for (id, dati) in &grezzi {
        let Some(u) = utenti.get(id) else { continue };
        let orig: Value = serde_json::from_str(dati)?;
        let mut d = vec![];
        differenze(&orig, &serde_json::to_value(u)?, &format!("utente {id}"), &mut d, 5);
        for x in &d {
            println!("  ✗ differenza: {x}");
        }
        diff_utenti += d.len();
    }
    println!("✓ utenti: {} letti, {} illeggibili, {} account collegati, {} differenze", utenti.len(), scartati.len(), account.len(), diff_utenti);
    ok &= scartati.is_empty() && diff_utenti == 0;
    let admin: Vec<_> = utenti.iter().filter(|(_, u)| u.admin).collect();
    println!("  amministratori ({}):", admin.len());
    for (id, u) in admin {
        let visto = time::OffsetDateTime::from_unix_timestamp(u.seen as i64).map(|t| t.date().to_string()).unwrap_or_default();
        println!("    - {id} «{}» account={} provider={} ultimo accesso={visto}", u.name, u.account.as_deref().unwrap_or("-"), u.provider.as_deref().unwrap_or("-"));
    }

    let attiva = db.get("attiva").await?;
    println!("✓ avventura ricordata: {}", attiva.unwrap_or(Value::Null));
    for p in db.partite().await? {
        match serde_json::from_value::<Stato>(p.stato.clone()) {
            Ok(s) => {
                let mut d = vec![];
                differenze(&p.stato, &serde_json::to_value(&s)?, &format!("partita {}", p.avventura), &mut d, 10);
                println!("✓ partita «{}»: {} pedine, {} voci di cronologia, {} schede, {} differenze",
                    p.avventura, s.pedine.len(), s.log.len(), s.schede.len(), d.len());
                for x in &d {
                    println!("  ✗ differenza: {x}");
                }
                ok &= d.is_empty();
            }
            Err(e) => {
                println!("✗ partita «{}» illeggibile: {e}", p.avventura);
                ok = false;
            }
        }
    }
    // salvataggio di prova: deve riuscire e rileggere gli stessi utenti
    db.salva(None, &utenti, &account.into_iter().collect(), None, &scartati).await?;
    let (riletti, _, _) = db.utenti().await?;
    println!("✓ salvataggio di prova sulla copia: {} utenti riletti", riletti.len());
    ok &= riletti.len() == utenti.len();
    db.chiudi().await;
    let _ = std::fs::remove_dir_all(&tmp);
    println!("{}", if ok { "RISULTATO: tutto leggibile, nessuna perdita." } else { "RISULTATO: ci sono problemi (vedi sopra)." });
    Ok(ok)
}

fn tempfile_dir() -> Result<std::path::PathBuf> {
    let d = std::env::temp_dir().join(format!("tavolo-verifica-{}", crate::util::id_casuale(8)));
    std::fs::create_dir_all(&d)?;
    Ok(d)
}
