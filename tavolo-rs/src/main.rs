//! Tavolo Virtuale · server di gioco per D&D.
//!
//!     tavolo                       # porta 8000 (o $PORT); al primo avvio crea l'account admin
//!     tavolo --porta 8080 --host 127.0.0.1
//!     tavolo verifica-db <tavolo.db>   # controlla un database esistente (su una copia)
//!     tavolo --healthcheck         # per HEALTHCHECK del container
//!
//! Cartelle: $DATI_DIR (database), $AVVENTURE_DIR (avventure), $WEB_DIR (client); predefinite accanto al binario.

use std::net::SocketAddr;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::Duration;

use anyhow::{Context, Result};
use sha2::{Digest, Sha256};
use tavolo::tavolo::{Cmd, Percorsi, Tavolo};
use tavolo::web::{router, App};

fn cartella(var: &str, predefinita: &str) -> PathBuf {
    if let Ok(v) = std::env::var(var) {
        if !v.is_empty() {
            return PathBuf::from(v);
        }
    }
    let base = std::env::current_exe().ok().and_then(|e| e.parent().map(Path::to_path_buf)).unwrap_or_else(|| PathBuf::from("."));
    base.join(predefinita)
}

/// Impronta dei file web: se cambia, i browser aperti si ricaricano.
fn calcola_versione(web: &Path) -> String {
    let mut h = Sha256::new();
    let mut pila = vec![web.to_path_buf()];
    let mut files = vec![];
    while let Some(d) = pila.pop() {
        let Ok(rd) = std::fs::read_dir(&d) else { continue };
        for e in rd.filter_map(|e| e.ok()) {
            if e.path().is_dir() {
                pila.push(e.path());
            } else {
                files.push(e.path());
            }
        }
    }
    files.sort();
    for f in files {
        h.update(f.file_name().map(|n| n.to_string_lossy().to_string()).unwrap_or_default().as_bytes());
        h.update(std::fs::read(&f).unwrap_or_default());
    }
    hex::encode(h.finalize())[..12].to_string()
}

fn healthcheck(porta: u16) -> ! {
    use std::io::{Read, Write};
    let ok = (|| -> std::io::Result<bool> {
        let mut s = std::net::TcpStream::connect_timeout(&SocketAddr::from(([127, 0, 0, 1], porta)), Duration::from_secs(3))?;
        s.set_read_timeout(Some(Duration::from_secs(5)))?;
        s.write_all(b"GET /healthz HTTP/1.0\r\nHost: localhost\r\n\r\n")?;
        let mut r = String::new();
        s.read_to_string(&mut r)?;
        Ok(r.starts_with("HTTP/1.0 200") || r.starts_with("HTTP/1.1 200"))
    })()
    .unwrap_or(false);
    std::process::exit(if ok { 0 } else { 1 })
}

#[tokio::main]
async fn main() -> Result<()> {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let mut porta: u16 = std::env::var("PORT").ok().and_then(|p| p.parse().ok()).unwrap_or(8000);
    let mut host = std::env::var("HOST").unwrap_or_else(|_| "0.0.0.0".into());
    let mut i = 0;
    let mut salute = false;
    while i < args.len() {
        match args[i].as_str() {
            "--porta" | "--port" => {
                porta = args.get(i + 1).and_then(|p| p.parse().ok()).context("--porta vuole un numero")?;
                i += 1;
            }
            "--host" => {
                host = args.get(i + 1).cloned().context("--host vuole un indirizzo")?;
                i += 1;
            }
            "--healthcheck" => salute = true,
            "verifica-db" => {
                let f = args.get(i + 1).context("uso: tavolo verifica-db <file.db>")?;
                tracing_subscriber::fmt().with_env_filter("warn").init();
                let ok = tavolo::verifica::verifica_db(Path::new(f)).await?;
                std::process::exit(if ok { 0 } else { 2 });
            }
            "-h" | "--help" => {
                println!("uso: tavolo [--porta N] [--host IP] | verifica-db <file.db> | --healthcheck");
                return Ok(());
            }
            a => anyhow::bail!("opzione sconosciuta: {a}"),
        }
        i += 1;
    }
    if salute {
        healthcheck(porta);
    }

    let filtro = tracing_subscriber::EnvFilter::try_from_env("RUST_LOG").unwrap_or_else(|_| "info".into());
    if std::env::var("LOG_FORMAT").as_deref() == Ok("json") {
        tracing_subscriber::fmt().with_env_filter(filtro).json().init();
    } else {
        tracing_subscriber::fmt().with_env_filter(filtro).init();
    }

    let percorsi = Percorsi { dati: cartella("DATI_DIR", "dati"), avventure: cartella("AVVENTURE_DIR", "avventure"), web: cartella("WEB_DIR", "web") };
    std::fs::create_dir_all(&percorsi.dati).context("cartella dati")?;
    std::fs::create_dir_all(&percorsi.avventure).context("cartella avventure")?;
    let web_reale = std::fs::canonicalize(&percorsi.web).with_context(|| format!("cartella web {}", percorsi.web.display()))?;
    let avv_reale = std::fs::canonicalize(&percorsi.avventure)?;
    let versione = calcola_versione(&web_reale);
    let db_file = percorsi.dati.join("tavolo.db");
    let db = tavolo::db::Db::apri(&db_file).await?;
    let metriche = Arc::new(tavolo::metriche::Metriche::default());
    let (t, pw_iniziale) = Tavolo::nuovo(percorsi.clone(), db.clone(), versione.clone(), metriche.clone()).await?;
    let (utente_admin, n_avv, attiva) = (t.config.admin.utente.clone(), t.catalogo.len(), t.attiva.clone());
    let provider: Vec<&str> = t.oauth_attivi().iter().map(|p| p.nome).collect();
    let ospiti = t.ospiti();
    let handle = t.avvia();

    // osservatore: nuove avventure o mappe copiate sul server compaiono senza riavvii
    {
        let (h, dir) = (handle.clone(), percorsi.avventure.clone());
        tokio::spawn(async move {
            let d2 = dir.clone();
            let mut ultima = tokio::task::spawn_blocking(move || tavolo::catalogo::firma(&d2)).await.unwrap_or_default();
            loop {
                tokio::time::sleep(Duration::from_secs(4)).await;
                let d2 = dir.clone();
                let f = tokio::task::spawn_blocking(move || tavolo::catalogo::firma(&d2)).await.unwrap_or_default();
                if f != ultima {
                    ultima = f;
                    h.manda(Cmd::Riscansiona).await;
                }
            }
        });
    }

    let app = App {
        tavolo: handle.clone(),
        accessi: tavolo::limiti::LimiteAccessi::nuovo(),
        percorsi: Arc::new(percorsi.clone()),
        web_reale: Arc::new(web_reale),
        avv_reale: Arc::new(avv_reale),
        versione: Arc::new(versione),
        metriche,
        token_metriche: std::env::var("METRICS_TOKEN").ok().filter(|t| t.len() >= 16).map(Arc::new),
    };
    let indirizzo: SocketAddr = format!("{host}:{porta}").parse().context("indirizzo di ascolto")?;
    let listener = tokio::net::TcpListener::bind(indirizzo).await.with_context(|| format!("porta {porta} occupata?"))?;

    println!("{}", "=".repeat(60));
    println!("  🐉  TAVOLO VIRTUALE  ·  pronto!  (server Rust {})", env!("CARGO_PKG_VERSION"));
    println!("{}", "=".repeat(60));
    println!("  Su questo PC:          http://localhost:{porta}");
    println!("  Database:              {}", db_file.display());
    match &pw_iniziale {
        Some(pw) => println!("  Account admin:         {utente_admin}  ·  password iniziale: {pw}"),
        None => println!("  Account admin:         {utente_admin}  (password cifrata nel database)"),
    }
    println!("  Accesso con account:   {}", if provider.is_empty() { "(nessuno: si configura in ⚙️ Impostazioni)".into() } else { provider.join(", ") });
    println!("  Ospiti:                {}", if ospiti { "ammessi" } else { "non ammessi" });
    println!("  Avventure:             {n_avv}");
    println!("  In gioco:              {}", attiva.as_deref().unwrap_or("None"));
    println!("{}", "=".repeat(60));

    // SIGTERM/SIGINT: si salva e si esce (gli stream SSE aperti non devono bloccare la chiusura)
    {
        let h = handle.clone();
        tokio::spawn(async move {
            let mut term = tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate()).expect("segnale");
            tokio::select! {
                _ = term.recv() => {}
                _ = tokio::signal::ctrl_c() => {}
            }
            println!("Salvo e chiudo…");
            let _ = tokio::time::timeout(Duration::from_secs(8), h.chiedi(Cmd::Chiudi)).await;
            db.chiudi().await;
            std::process::exit(0);
        });
    }

    axum::serve(listener, router(app).into_make_service_with_connect_info::<SocketAddr>()).await?;
    Ok(())
}
