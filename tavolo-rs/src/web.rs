//! HTTP (axum): stessa API del server Python, più /healthz, /metrics, /api/audit, /api/esci.

use std::collections::HashMap;
use std::convert::Infallible;
use std::net::SocketAddr;
use std::path::{Component, Path, PathBuf};
use std::sync::Arc;
use std::time::Duration;

use axum::body::{Body, Bytes};
use axum::extract::{ConnectInfo, Path as PathParam, Query, Request, State};
use axum::http::{header, HeaderMap, HeaderName, HeaderValue, Method, StatusCode, Uri};
use axum::middleware::{self, Next};
use axum::response::sse::{Event, KeepAlive, Sse};
use axum::response::{IntoResponse, Response};
use axum::routing::{get, post};
use axum::Router;
use serde_json::{json, Value};
use tower_governor::governor::GovernorConfigBuilder;
use tower_governor::key_extractor::KeyExtractor;
use tower_governor::{GovernorError, GovernorLayer};

use crate::comandi::{leggi, Lettura};
use crate::contenuti::CmdContenuto;
use crate::limiti::LimiteAccessi;
use crate::metriche::Metriche;
use crate::tavolo::{Cmd, Cred, Handle, Percorsi, Risposta};
use crate::util::id_valido;

pub const MAX_CORPO: usize = 80 * 1024 * 1024;
const MAX_JSON: usize = 4 * 1024 * 1024;

pub const CSP: &str = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https:; \
media-src 'self' data: blob:; connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'none'; \
form-action 'self'; frame-ancestors 'self'";
const CSP_SANDBOX: &str = "sandbox allow-popups allow-popups-to-escape-sandbox allow-modals";
const COOKIE: &str = "tv_sess";

#[derive(Clone)]
pub struct App {
    pub tavolo: Handle,
    pub accessi: LimiteAccessi,
    pub percorsi: Arc<Percorsi>,
    pub web_reale: Arc<PathBuf>,
    /// Client nuovo (Angular), se configurato (WEB_BETA_DIR): è la pagina principale e il vecchio va su /vecchio/.
    pub web_beta: Option<Arc<PathBuf>>,
    pub avv_reale: Arc<PathBuf>,
    pub versione: Arc<String>,
    pub metriche: Arc<Metriche>,
    pub token_metriche: Option<Arc<String>>,
}

// ---------------------------------------------------------------------- utilità

/// IP del client: l'ultimo valore di X-Forwarded-For (lo aggiunge il proxy), altrimenti l'IP della connessione.
fn ip_da(headers: &HeaderMap, peer: Option<SocketAddr>) -> String {
    let xff = headers.get("x-forwarded-for").and_then(|v| v.to_str().ok()).unwrap_or("");
    let ultimo = xff.rsplit(',').next().unwrap_or("").trim();
    if !ultimo.is_empty() {
        return crate::util::tronca(ultimo, 64);
    }
    peer.map(|p| p.ip().to_string()).unwrap_or_default()
}

#[derive(Clone)]
struct UltimoXff;

impl KeyExtractor for UltimoXff {
    type Key = String;
    fn extract<T>(&self, req: &axum::http::Request<T>) -> Result<Self::Key, GovernorError> {
        let peer = req.extensions().get::<ConnectInfo<SocketAddr>>().map(|c| c.0);
        Ok(ip_da(req.headers(), peer))
    }
}

fn header(h: &HeaderMap, k: &str) -> String {
    h.get(k).and_then(|v| v.to_str().ok()).unwrap_or("").to_string()
}

/// Credenziali: header X-Client/X-Secret, poi query c/s, poi cookie HttpOnly.
fn cred(h: &HeaderMap, q: &HashMap<String, String>) -> Cred {
    let (id, secret) = (header(h, "x-client"), header(h, "x-secret"));
    if !id.is_empty() {
        return Cred { id, secret };
    }
    let (id, secret) = (q.get("c").cloned().unwrap_or_default(), q.get("s").cloned().unwrap_or_default());
    if !id.is_empty() {
        return Cred { id, secret };
    }
    for c in h.get_all(header::COOKIE).iter().filter_map(|v| v.to_str().ok()) {
        for parte in c.split(';') {
            if let Some(v) = parte.trim().strip_prefix(&format!("{COOKIE}=")) {
                if let Some((id, secret)) = v.split_once('.') {
                    return Cred {
                        id: id.into(),
                        secret: secret.into(),
                    };
                }
            }
        }
    }
    Cred::default()
}

fn https(h: &HeaderMap) -> bool {
    header(h, "x-forwarded-proto")
        .split(',')
        .next()
        .unwrap_or("")
        .trim()
        .eq_ignore_ascii_case("https")
}

fn json_risposta(r: Risposta, h: &HeaderMap) -> Response {
    let mut res = (StatusCode::from_u16(r.status).unwrap_or(StatusCode::OK), r.corpo.to_string()).into_response();
    let hh = res.headers_mut();
    hh.insert(header::CONTENT_TYPE, HeaderValue::from_static("application/json; charset=utf-8"));
    hh.insert(header::CACHE_CONTROL, HeaderValue::from_static("no-store"));
    if let Some(c) = r.cookie {
        let secure = if https(h) { "; Secure" } else { "" };
        let v = format!(
            "{COOKIE}={}.{}; Path=/; HttpOnly; SameSite=Strict; Max-Age=31536000{secure}",
            c.id, c.secret
        );
        if let Ok(v) = HeaderValue::from_str(&v) {
            hh.insert(header::SET_COOKIE, v);
        }
    }
    res
}

fn json_stato(status: u16, v: Value) -> Response {
    json_risposta(
        Risposta {
            status,
            corpo: v,
            cookie: None,
        },
        &HeaderMap::new(),
    )
}

fn non_trovato() -> Response {
    let mut r = (StatusCode::NOT_FOUND, "Non trovato").into_response();
    r.headers_mut()
        .insert(header::CONTENT_TYPE, HeaderValue::from_static("text/plain; charset=utf-8"));
    r
}

fn occupato() -> Response {
    json_stato(503, json!({"ok": false, "errore": "server in chiusura"}))
}

/// Legge il corpo con un limite; oltre → 413 come il server Python.
async fn leggi_corpo(h: &HeaderMap, body: Body, max: usize) -> Result<Bytes, Response> {
    let troppo = || {
        json_stato(
            413,
            json!({"ok": false, "errore": format!("file troppo grande (max {} MB)", max / 1024 / 1024)}),
        )
    };
    if header(h, "content-length").parse::<usize>().is_ok_and(|n| n > max) {
        return Err(troppo());
    }
    axum::body::to_bytes(body, max).await.map_err(|_| troppo())
}

fn leggi_json_corpo(raw: &[u8]) -> Result<Value, Response> {
    if raw.iter().all(u8::is_ascii_whitespace) {
        return Ok(json!({}));
    }
    serde_json::from_slice(raw).map_err(|_| json_stato(400, json!({"ok": false, "errore": "JSON non valido"})))
}

fn allegato(dati: Vec<u8>, tipo: &'static str, nome: &str) -> Response {
    let mut r = Response::new(Body::from(dati));
    let h = r.headers_mut();
    h.insert(header::CONTENT_TYPE, HeaderValue::from_static(tipo));
    if let Ok(v) = HeaderValue::from_str(&format!("attachment; filename=\"{nome}\"")) {
        h.insert(header::CONTENT_DISPOSITION, v);
    }
    h.insert(header::CACHE_CONTROL, HeaderValue::from_static("no-store"));
    r
}

/// Percorso URL decodificato → percorso relativo sicuro (niente `..`, assoluti, NUL, backslash).
fn relativo(path: &str) -> Option<PathBuf> {
    let dec = urlencoding::decode(path).ok()?;
    if dec.contains('\0') || dec.contains('\\') {
        return None;
    }
    let mut out = PathBuf::new();
    for c in Path::new(dec.trim_start_matches('/')).components() {
        match c {
            Component::Normal(s) => out.push(s),
            Component::CurDir => {}
            _ => return None,
        }
    }
    Some(out)
}

fn tipo_file(p: &Path) -> String {
    let ext = p.extension().and_then(|e| e.to_str()).unwrap_or("").to_lowercase();
    let t = match ext.as_str() {
        "svg" => "image/svg+xml".to_string(),
        "js" | "mjs" => "application/javascript".to_string(),
        "md" => "text/markdown".to_string(),
        "webp" => "image/webp".to_string(),
        _ => mime_guess::from_ext(&ext)
            .first()
            .map(|m| m.essence_str().to_string())
            .unwrap_or_else(|| "application/octet-stream".into()),
    };
    if t.starts_with("text/") || t == "application/javascript" || t == "application/json" || t == "image/svg+xml" {
        format!("{t}; charset=utf-8")
    } else {
        t
    }
}

/// Serve un file (in streaming) con ETag: i browser non riscaricano mappe che non sono cambiate.
async fn servi_file(full: &Path, h: &HeaderMap, sandbox: bool) -> Response {
    let Ok(f) = tokio::fs::File::open(full).await else {
        return non_trovato();
    };
    let Ok(md) = f.metadata().await else { return non_trovato() };
    if !md.is_file() {
        return non_trovato();
    }
    let mtime = md
        .modified()
        .ok()
        .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    let etag = format!("\"{:x}-{:x}\"", md.len(), mtime);
    let mut r = if header(h, "if-none-match") == etag {
        StatusCode::NOT_MODIFIED.into_response()
    } else {
        let mut r = Response::new(Body::from_stream(tokio_util::io::ReaderStream::with_capacity(f, 64 * 1024)));
        r.headers_mut().insert(header::CONTENT_LENGTH, HeaderValue::from(md.len()));
        r
    };
    let hh = r.headers_mut();
    if let Ok(v) = HeaderValue::from_str(&tipo_file(full)) {
        hh.insert(header::CONTENT_TYPE, v);
    }
    hh.insert(header::CACHE_CONTROL, HeaderValue::from_static("no-cache"));
    if let Ok(v) = HeaderValue::from_str(&etag) {
        hh.insert(header::ETAG, v);
    }
    if sandbox {
        hh.insert(header::CONTENT_SECURITY_POLICY, HeaderValue::from_static(CSP_SANDBOX));
    }
    r
}

/// Il percorso reale sta dentro `base` ed è un file?
async fn dentro(base: &Path, rel: &Path) -> Option<PathBuf> {
    let full = tokio::fs::canonicalize(base.join(rel)).await.ok()?;
    (full.starts_with(base) && full != base && tokio::fs::metadata(&full).await.ok()?.is_file()).then_some(full)
}

// ---------------------------------------------------------------------- router

pub fn router(app: App) -> Router {
    let governor = Arc::new(
        GovernorConfigBuilder::default()
            .per_millisecond(10) // 100 richieste al secondo per IP…
            .burst_size(400) // …con raffiche fino a 400: ferma solo gli abusi
            .key_extractor(UltimoXff)
            .finish()
            .expect("configurazione del limite"),
    );
    let limiter = governor.limiter().clone();
    tokio::spawn(async move {
        loop {
            tokio::time::sleep(Duration::from_secs(60)).await;
            limiter.retain_recent();
        }
    });

    Router::new()
        .route("/api/info", get(info))
        .route("/api/io", get(io))
        .route("/api/stato", get(stato))
        .route("/api/eventi", get(eventi))
        .route("/api/esporta", get(esporta))
        .route("/api/backup", get(backup))
        .route("/api/audit", get(audit))
        .route("/api/scarica_avventura", get(scarica_avventura))
        .route("/api/login", post(login))
        .route("/api/entra", post(entra))
        .route("/api/esci", post(esci))
        .route("/api/op", post(op))
        .route("/api/importa", post(importa))
        .route("/api/carica_avventura", post(carica_avventura))
        .route("/api/carica_mappa", post(carica_mappa))
        .route("/api/carica_documento", post(carica_documento))
        .route("/auth/{prov}/{fase}", get(oauth))
        .route("/avventure/{*resto}", get(file_avventura))
        .route("/beta", get(beta))
        .route("/beta/", get(beta))
        .route("/beta/{*resto}", get(beta))
        .route("/vecchio", get(|| async { axum::response::Redirect::permanent("/vecchio/") }))
        .route("/vecchio/", get(vecchio))
        .route("/vecchio/{*resto}", get(vecchio))
        .route("/healthz", get(salute))
        .route("/metrics", get(metriche))
        .fallback(statico)
        .layer(middleware::from_fn_with_state(app.clone(), intestazioni))
        .layer(GovernorLayer { config: governor })
        .layer(tower_http::catch_panic::CatchPanicLayer::new())
        .with_state(app)
}

/// Intestazioni di sicurezza su ogni risposta (la CSP predefinita solo se la risposta non ne ha già una).
async fn intestazioni(State(app): State<App>, req: Request, next: Next) -> Response {
    let mut r = next.run(req).await;
    let h = r.headers_mut();
    if !h.contains_key(header::CONTENT_SECURITY_POLICY) {
        h.insert(header::CONTENT_SECURITY_POLICY, HeaderValue::from_static(CSP));
    }
    h.insert(header::X_CONTENT_TYPE_OPTIONS, HeaderValue::from_static("nosniff"));
    h.insert(header::REFERRER_POLICY, HeaderValue::from_static("same-origin"));
    h.insert(
        HeaderName::from_static("permissions-policy"),
        HeaderValue::from_static("camera=(), microphone=(), geolocation=()"),
    );
    app.metriche.risposta(r.status().as_u16());
    r
}

// ---------------------------------------------------------------------- endpoint

async fn info(State(app): State<App>) -> Response {
    match app.tavolo.chiedi(Cmd::Info).await {
        Some(v) => json_stato(200, v),
        None => occupato(),
    }
}

async fn io(State(app): State<App>, h: HeaderMap, Query(q): Query<HashMap<String, String>>) -> Response {
    let cred = cred(&h, &q);
    match app.tavolo.chiedi(|reply| Cmd::Io { cred, reply }).await {
        Some(Some(v)) => json_stato(200, v),
        Some(None) => json_stato(401, json!({"ok": false})),
        None => occupato(),
    }
}

async fn stato(State(app): State<App>, h: HeaderMap, Query(q): Query<HashMap<String, String>>) -> Response {
    let cred = cred(&h, &q);
    match app.tavolo.chiedi(|reply| Cmd::Stato { cred, reply }).await {
        Some(Some(v)) => json_stato(200, v),
        Some(None) => json_stato(401, json!({"ok": false, "errore": "non autenticato"})),
        None => occupato(),
    }
}

/// Avvisa il tavolo quando lo stream si chiude (il browser se n'è andato o è stato sostituito).
struct Guardia {
    tavolo: Handle,
    id: String,
    conn: u64,
}

impl Drop for Guardia {
    fn drop(&mut self) {
        let (t, id, conn) = (self.tavolo.clone(), std::mem::take(&mut self.id), self.conn);
        if let Ok(rt) = tokio::runtime::Handle::try_current() {
            rt.spawn(async move { t.manda(Cmd::Disconnetti { id, conn }).await });
        }
    }
}

async fn eventi(State(app): State<App>, h: HeaderMap, Query(q): Query<HashMap<String, String>>) -> Response {
    let cred = cred(&h, &q);
    let id = cred.id.clone();
    let conn = match app.tavolo.chiedi(|reply| Cmd::Connetti { cred, reply }).await {
        Some(Some(c)) => c,
        Some(None) => return json_stato(401, json!({"ok": false})),
        None => return occupato(),
    };
    let guardia = Guardia {
        tavolo: app.tavolo.clone(),
        id,
        conn: conn.conn,
    };
    let mut rx = conn.rx;
    let flusso = async_stream::stream! {
        let _g = guardia;
        yield Ok::<Event, Infallible>(Event::default().retry(Duration::from_millis(2000)));
        while let Some(msg) = rx.recv().await {
            yield Ok(Event::default().data(&*msg));
        }
    };
    let mut r = Sse::new(flusso)
        .keep_alive(KeepAlive::new().interval(Duration::from_secs(15)).text("ping"))
        .into_response();
    r.headers_mut()
        .insert(HeaderName::from_static("x-accel-buffering"), HeaderValue::from_static("no"));
    r.headers_mut().insert(header::CACHE_CONTROL, HeaderValue::from_static("no-cache"));
    r
}

async fn login(State(app): State<App>, ConnectInfo(peer): ConnectInfo<SocketAddr>, h: HeaderMap, body: Body) -> Response {
    let ip = ip_da(&h, Some(peer));
    let raw = match leggi_corpo(&h, body, MAX_JSON).await {
        Ok(b) => b,
        Err(r) => return r,
    };
    let corpo = match leggi_json_corpo(&raw) {
        Ok(v) => v,
        Err(r) => return r,
    };
    if app.accessi.troppi(&ip) {
        app.metriche.limitato();
        return json_stato(429, json!({"ok": false, "errore": "Troppi tentativi: aspetta qualche secondo"}));
    }
    // la password dell'admin si verifica fuori dal task del tavolo (Argon2/PBKDF2 sono lenti di proposito)
    let mut admin_ok = None;
    if corpo.get("tipo").and_then(Value::as_str) == Some("admin") {
        let Some(conf) = app.tavolo.chiedi(Cmd::DatiAdmin).await else {
            return occupato();
        };
        let utente = corpo.get("utente").and_then(crate::util::testo).unwrap_or_default();
        let pw = corpo.get("password").and_then(crate::util::testo).unwrap_or_default();
        let v = tokio::task::spawn_blocking(move || crate::password::verifica(&conf, &utente, &pw)).await;
        admin_ok = Some(v.map(|v| (v.ok, v.aggiorna)).unwrap_or((false, None)));
    }
    match app
        .tavolo
        .chiedi(|reply| Cmd::Login {
            corpo,
            ip,
            admin_ok,
            reply,
        })
        .await
    {
        Some(r) => json_risposta(r, &h),
        None => occupato(),
    }
}

async fn entra(State(app): State<App>, ConnectInfo(peer): ConnectInfo<SocketAddr>, h: HeaderMap, body: Body) -> Response {
    let ip = ip_da(&h, Some(peer));
    let raw = match leggi_corpo(&h, body, MAX_JSON).await {
        Ok(b) => b,
        Err(r) => return r,
    };
    let corpo = match leggi_json_corpo(&raw) {
        Ok(v) => v,
        Err(r) => return r,
    };
    if app.accessi.troppi(&ip) {
        app.metriche.limitato();
        return json_stato(429, json!({"ok": false, "errore": "Troppi tentativi: aspetta qualche secondo"}));
    }
    match app.tavolo.chiedi(|reply| Cmd::Entra { corpo, ip, reply }).await {
        Some(r) => json_risposta(r, &h),
        None => occupato(),
    }
}

async fn esci(h: HeaderMap) -> Response {
    let mut r = json_stato(200, json!({"ok": true}));
    let secure = if https(&h) { "; Secure" } else { "" };
    if let Ok(v) = HeaderValue::from_str(&format!("{COOKIE}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0{secure}")) {
        r.headers_mut().insert(header::SET_COOKIE, v);
    }
    r
}

async fn op(State(app): State<App>, ConnectInfo(peer): ConnectInfo<SocketAddr>, h: HeaderMap, body: Body) -> Response {
    let ip = ip_da(&h, Some(peer));
    let raw = match leggi_corpo(&h, body, MAX_JSON).await {
        Ok(b) => b,
        Err(r) => return r,
    };
    let corpo = match leggi_json_corpo(&raw) {
        Ok(v) => v,
        Err(r) => return r,
    };
    let cred = cred(&h, &HashMap::new());
    match leggi(corpo) {
        Lettura::Ok(op) => match app.tavolo.chiedi(|reply| Cmd::Op { cred, op, ip, reply }).await {
            Some(r) => json_risposta(r, &h),
            None => occupato(),
        },
        altro => {
            // prima chi sei (401), poi cosa chiedi
            match app.tavolo.chiedi(|reply| Cmd::Chi { cred, reply }).await {
                Some(None) => json_stato(401, json!({"ok": false, "errore": "non autenticato"})),
                None => occupato(),
                Some(Some(_)) => match altro {
                    Lettura::NonValida(e) => json_stato(400, json!({"ok": false, "errore": e})),
                    _ => json_stato(200, json!({"ok": false, "errore": "operazione sconosciuta"})),
                },
            }
        }
    }
}

async fn importa(State(app): State<App>, ConnectInfo(peer): ConnectInfo<SocketAddr>, h: HeaderMap, body: Body) -> Response {
    let ip = ip_da(&h, Some(peer));
    let raw = match leggi_corpo(&h, body, MAX_CORPO).await {
        Ok(b) => b,
        Err(r) => return r,
    };
    let corpo = match leggi_json_corpo(&raw) {
        Ok(v) => v,
        Err(r) => return r,
    };
    let cred = cred(&h, &HashMap::new());
    let Some(id_ok) = app.tavolo.chiedi(|reply| Cmd::Chi { cred: cred.clone(), reply }).await else {
        return occupato();
    };
    if id_ok.is_none() {
        return json_stato(401, json!({"ok": false, "errore": "non autenticato"}));
    }
    match app
        .tavolo
        .chiedi(|reply| Cmd::Contenuto(CmdContenuto::Importa { cred, corpo, ip, reply }))
        .await
    {
        Some(r) if r.status == 404 => json_stato(404, json!({"ok": false})),
        Some(r) => json_risposta(r, &h),
        None => occupato(),
    }
}

/// Controllo comune ai caricamenti: dimensione, poi Master, poi lettura del corpo.
async fn prepara_caricamento(app: &App, h: &HeaderMap, q: &HashMap<String, String>, body: Body) -> Result<(Cred, Bytes), Response> {
    if header(h, "content-length").parse::<usize>().is_ok_and(|n| n > MAX_CORPO) {
        return Err(json_stato(413, json!({"ok": false, "errore": "file troppo grande (max 80 MB)"})));
    }
    let cred = cred(h, q);
    match app.tavolo.chiedi(|reply| Cmd::Chi { cred: cred.clone(), reply }).await {
        Some(Some(c)) if c.master => {}
        Some(_) => return Err(json_stato(403, json!({"ok": false, "errore": "solo il Master può caricare"}))),
        None => return Err(occupato()),
    }
    let dati = leggi_corpo(h, body, MAX_CORPO).await?;
    Ok((cred, dati))
}

async fn carica_mappa(State(app): State<App>, h: HeaderMap, Query(q): Query<HashMap<String, String>>, body: Body) -> Response {
    let (cred, dati) = match prepara_caricamento(&app, &h, &q, body).await {
        Ok(x) => x,
        Err(r) => return r,
    };
    let nome = q.get("nome").cloned().unwrap_or_else(|| "mappa.png".into());
    let titolo = q.get("titolo").cloned().unwrap_or_default();
    let cella = q
        .get("cella")
        .and_then(|c| c.parse::<f64>().ok())
        .filter(|c| c.is_finite())
        .unwrap_or(0.0);
    match app
        .tavolo
        .chiedi(|reply| {
            Cmd::Contenuto(CmdContenuto::CaricaMappa {
                cred,
                nome,
                titolo,
                cella,
                dati,
                reply,
            })
        })
        .await
    {
        Some(r) => json_risposta(r, &h),
        None => occupato(),
    }
}

async fn carica_documento(State(app): State<App>, h: HeaderMap, Query(q): Query<HashMap<String, String>>, body: Body) -> Response {
    let (cred, dati) = match prepara_caricamento(&app, &h, &q, body).await {
        Ok(x) => x,
        Err(r) => return r,
    };
    let nome = q.get("nome").cloned().unwrap_or_else(|| "documento.html".into());
    let titolo = q.get("titolo").cloned().unwrap_or_default();
    let solo_master = q.get("solo_master").map(String::as_str) == Some("1");
    match app
        .tavolo
        .chiedi(|reply| {
            Cmd::Contenuto(CmdContenuto::CaricaDocumento {
                cred,
                nome,
                titolo,
                solo_master,
                dati,
                reply,
            })
        })
        .await
    {
        Some(r) => json_risposta(r, &h),
        None => occupato(),
    }
}

async fn carica_avventura(
    State(app): State<App>,
    ConnectInfo(peer): ConnectInfo<SocketAddr>,
    h: HeaderMap,
    Query(q): Query<HashMap<String, String>>,
    body: Body,
) -> Response {
    let ip = ip_da(&h, Some(peer));
    let (cred, dati) = match prepara_caricamento(&app, &h, &q, body).await {
        Ok(x) => x,
        Err(r) => return r,
    };
    let Some(Some(avv)) = app
        .tavolo
        .chiedi(|reply| Cmd::Contenuto(CmdContenuto::PermessoCarica { cred: cred.clone(), reply }))
        .await
    else {
        return json_stato(403, json!({"ok": false, "errore": "solo il Master può caricare"}));
    };
    let estratto = tokio::task::spawn_blocking(move || crate::pacchetti::estrai(&dati, &avv)).await;
    let (aid, tmp) = match estratto {
        Ok(Ok(x)) => x,
        Ok(Err(e)) => return json_stato(400, json!({"ok": false, "errore": e})),
        Err(_) => return json_stato(500, json!({"ok": false, "errore": "estrazione non riuscita"})),
    };
    match app
        .tavolo
        .chiedi(|reply| Cmd::Contenuto(CmdContenuto::InstallaPacchetto { cred, tmp, aid, ip, reply }))
        .await
    {
        Some(r) => json_risposta(r, &h),
        None => occupato(),
    }
}

async fn scarica_avventura(State(app): State<App>, h: HeaderMap, Query(q): Query<HashMap<String, String>>) -> Response {
    let cred = cred(&h, &q);
    let aid = q.get("id").cloned().unwrap_or_default();
    if !id_valido(&aid) {
        return json_stato(403, json!({"ok": false}));
    }
    let a2 = aid.clone();
    let Some(Some(dir)) = app
        .tavolo
        .chiedi(|reply| Cmd::Contenuto(CmdContenuto::CartellaAvventura { cred, aid: a2, reply }))
        .await
    else {
        return json_stato(403, json!({"ok": false}));
    };
    let a3 = aid.clone();
    match tokio::task::spawn_blocking(move || crate::pacchetti::zip_avventura(&dir, &a3)).await {
        Ok(Ok(dati)) => allegato(dati, "application/zip", &format!("{aid}.zip")),
        _ => json_stato(500, json!({"ok": false, "errore": "impossibile creare lo zip"})),
    }
}

async fn esporta(State(app): State<App>, h: HeaderMap, Query(q): Query<HashMap<String, String>>) -> Response {
    let cred = cred(&h, &q);
    let aid = q.get("id").cloned().filter(|a| !a.is_empty());
    match app
        .tavolo
        .chiedi(|reply| Cmd::Contenuto(CmdContenuto::Esporta { cred, aid, reply }))
        .await
    {
        Some(Some((aid, dati))) => {
            let nome: String = aid
                .chars()
                .filter(|c| c.is_ascii_alphanumeric() || *c == '-' || *c == '_')
                .take(60)
                .collect();
            allegato(dati, "application/json; charset=utf-8", &format!("partita_{nome}.json"))
        }
        Some(None) => json_stato(403, json!({"ok": false})),
        None => occupato(),
    }
}

async fn backup(
    State(app): State<App>,
    ConnectInfo(peer): ConnectInfo<SocketAddr>,
    h: HeaderMap,
    Query(q): Query<HashMap<String, String>>,
) -> Response {
    let ip = ip_da(&h, Some(peer));
    let cred = cred(&h, &q);
    match app
        .tavolo
        .chiedi(|reply| Cmd::Contenuto(CmdContenuto::Backup { cred, ip, reply }))
        .await
    {
        Some(Some(file)) => {
            let dati = tokio::fs::read(&file).await;
            let _ = tokio::fs::remove_file(&file).await;
            match dati {
                Ok(d) => {
                    let ora = time::OffsetDateTime::now_local().unwrap_or_else(|_| time::OffsetDateTime::now_utc());
                    let fmt = time::macros::format_description!("[year][month][day]-[hour][minute]");
                    let quando = ora.format(&fmt).unwrap_or_default();
                    allegato(d, "application/vnd.sqlite3", &format!("tavolo-{quando}.db"))
                }
                Err(_) => json_stato(500, json!({"ok": false})),
            }
        }
        Some(None) => json_stato(403, json!({"ok": false})),
        None => occupato(),
    }
}

async fn audit(State(app): State<App>, h: HeaderMap, Query(q): Query<HashMap<String, String>>) -> Response {
    let cred = cred(&h, &q);
    match app.tavolo.chiedi(|reply| Cmd::Contenuto(CmdContenuto::Audit { cred, reply })).await {
        Some(Some(v)) => json_stato(200, json!({"ok": true, "audit": v})),
        Some(None) => json_stato(403, json!({"ok": false})),
        None => occupato(),
    }
}

fn base_url(h: &HeaderMap) -> String {
    let proto = header(h, "x-forwarded-proto");
    let proto = proto
        .split(',')
        .next()
        .map(str::trim)
        .filter(|p| *p == "https" || *p == "http")
        .unwrap_or("http");
    let host = Some(header(h, "x-forwarded-host"))
        .filter(|x| !x.is_empty())
        .unwrap_or_else(|| header(h, "host"));
    let host = host.split(',').next().unwrap_or("").trim().to_string();
    let host_ok = !host.is_empty() && host.chars().all(|c| c.is_ascii_alphanumeric() || ".-:[]".contains(c));
    format!("{proto}://{}", if host_ok { host.as_str() } else { "localhost" })
}

async fn oauth(
    State(app): State<App>,
    ConnectInfo(peer): ConnectInfo<SocketAddr>,
    PathParam((prov, fase)): PathParam<(String, String)>,
    h: HeaderMap,
    Query(q): Query<HashMap<String, String>>,
) -> Response {
    let ip = ip_da(&h, Some(peer));
    match fase.as_str() {
        "start" => {
            let base = base_url(&h);
            match app.tavolo.chiedi(|reply| Cmd::OAuthInizio { prov, base, reply }).await {
                Some(Some(url)) => {
                    let mut r = StatusCode::FOUND.into_response();
                    if let Ok(v) = HeaderValue::from_str(&url) {
                        r.headers_mut().insert(header::LOCATION, v);
                    }
                    r
                }
                Some(None) => non_trovato(),
                None => occupato(),
            }
        }
        "callback" => {
            let annullato = q.contains_key("error");
            let state = q.get("state").cloned().unwrap_or_default();
            let p2 = prov.clone();
            let esito = match app
                .tavolo
                .chiedi(|reply| Cmd::OAuthStato {
                    prov: p2,
                    state,
                    annullato,
                    reply,
                })
                .await
            {
                None => return occupato(),
                Some(Err(e)) if e.is_empty() => return non_trovato(),
                Some(e) => e,
            };
            let pagina = |corpo: String, csp: Option<String>, cookie: Option<Cred>| {
                let mut r = Risposta::ok(Value::Null);
                r.cookie = cookie;
                let mut res = (StatusCode::OK, corpo).into_response();
                let hh = res.headers_mut();
                hh.insert(header::CONTENT_TYPE, HeaderValue::from_static("text/html; charset=utf-8"));
                hh.insert(header::CACHE_CONTROL, HeaderValue::from_static("no-store"));
                if let Some(c) = csp.and_then(|c| HeaderValue::from_str(&c).ok()) {
                    hh.insert(header::CONTENT_SECURITY_POLICY, c);
                }
                if let Some(c) = r.cookie {
                    let secure = if https(&h) { "; Secure" } else { "" };
                    if let Ok(v) = HeaderValue::from_str(&format!(
                        "{COOKIE}={}.{}; Path=/; HttpOnly; SameSite=Lax; Max-Age=31536000{secure}",
                        c.id, c.secret
                    )) {
                        hh.insert(header::SET_COOKIE, v);
                    }
                }
                res
            };
            let scambio = match esito {
                Ok(s) => s,
                Err(e) => return pagina(crate::oauth::pagina_errore(&e), None, None),
            };
            let codice = q.get("code").cloned().unwrap_or_default();
            let nome_prov = scambio.provider.nome;
            let (uid, nome, avatar) = match crate::oauth::completa(&scambio, &codice).await {
                Ok(x) => x,
                Err(e) => return pagina(crate::oauth::pagina_errore(&e), None, None),
            };
            let Some((id, secret, nome)) = app
                .tavolo
                .chiedi(|reply| Cmd::OAuthUtente {
                    prov: prov.clone(),
                    uid,
                    nome,
                    avatar,
                    ip,
                    reply,
                })
                .await
            else {
                return occupato();
            };
            let nonce = crate::util::token(16);
            let csp = format!("default-src 'none'; script-src 'nonce-{nonce}'; base-uri 'none'; frame-ancestors 'none'");
            let corpo = crate::oauth::pagina_accesso(&id, &secret, &nome, nome_prov, &nonce);
            pagina(corpo, Some(csp), Some(Cred { id, secret }))
        }
        _ => non_trovato(),
    }
}

async fn file_avventura(State(app): State<App>, uri: Uri, h: HeaderMap, Query(q): Query<HashMap<String, String>>) -> Response {
    let Ok(path) = urlencoding::decode(uri.path()) else {
        return non_trovato();
    };
    let parti: Vec<&str> = path.split('/').collect(); // ['', 'avventure', id, 'mappe'|'documenti'|'immagini', file...]
    if parti.len() < 5 || !["mappe", "documenti", "immagini"].contains(&parti[3]) || !id_valido(parti[2]) {
        return non_trovato();
    }
    let Some(rel) = relativo(&parti[2..].join("/")) else {
        return non_trovato();
    };
    let Some(full) = dentro(&app.avv_reale, &rel).await else {
        return non_trovato();
    };
    let aid_dir = app.avv_reale.join(parti[2]);
    if !full.starts_with(&aid_dir) {
        return non_trovato();
    }
    let pdf = full.extension().is_some_and(|e| e.eq_ignore_ascii_case("pdf"));
    if parti[3] == "documenti" {
        let file = parti[4..].join("/");
        let aid = parti[2].to_string();
        let riservato = app
            .tavolo
            .chiedi(|reply| Cmd::DocumentoRiservato { aid, file, reply })
            .await
            .unwrap_or(true);
        if riservato {
            let cred = cred(&h, &q);
            let master = matches!(app.tavolo.chiedi(|reply| Cmd::Chi { cred, reply }).await, Some(Some(c)) if c.master);
            if !master {
                let mut r = (StatusCode::FORBIDDEN, "Solo per il Master").into_response();
                r.headers_mut()
                    .insert(header::CONTENT_TYPE, HeaderValue::from_static("text/plain; charset=utf-8"));
                return r;
            }
        }
    }
    // tutto ciò che viene dalle avventure è in sandbox (anche gli SVG), tranne i PDF che altrimenti non si aprono
    servi_file(&full, &h, !pdf).await
}

async fn statico(State(app): State<App>, method: Method, uri: Uri, h: HeaderMap) -> Response {
    if method == Method::POST {
        // come il server Python: chi non è autenticato riceve 401, gli altri 404
        let c = cred(&h, &HashMap::new());
        return match app.tavolo.chiedi(|reply| Cmd::Chi { cred: c, reply }).await {
            Some(Some(_)) => json_stato(404, json!({"ok": false})),
            _ => json_stato(401, json!({"ok": false, "errore": "non autenticato"})),
        };
    }
    if method != Method::GET && method != Method::HEAD {
        return StatusCode::METHOD_NOT_ALLOWED.into_response();
    }
    match app.web_beta.clone() {
        // con il client nuovo configurato, è lui la pagina principale (il vecchio resta su /vecchio/)
        Some(base) => client_nuovo(&base, &uri, &h).await,
        None => client_vecchio(&app, uri.path(), &h).await,
    }
}

/// Il client vecchio (WEB_DIR): `p` è il percorso relativo alla sua radice.
async fn client_vecchio(app: &App, p: &str, h: &HeaderMap) -> Response {
    let p = if matches!(p, "" | "/" | "/admin" | "/admin/") {
        "/index.html"
    } else {
        p
    };
    let Some(rel) = relativo(p) else { return non_trovato() };
    if rel.as_os_str().is_empty() {
        return non_trovato();
    }
    let Some(full) = dentro(&app.web_reale, &rel).await else {
        return non_trovato();
    };
    if full.file_name().is_some_and(|n| n == "index.html") {
        let Ok(testo) = tokio::fs::read_to_string(&full).await else {
            return non_trovato();
        };
        let mut r = testo.replace("__VERSIONE__", &app.versione).into_response();
        r.headers_mut()
            .insert(header::CONTENT_TYPE, HeaderValue::from_static("text/html; charset=utf-8"));
        r.headers_mut().insert(header::CACHE_CONTROL, HeaderValue::from_static("no-cache"));
        return r;
    }
    servi_file(&full, h, false).await
}

/// Il client nuovo (WEB_BETA_DIR): i file se esistono, altrimenti index.html (applicazione a pagina singola).
/// Un percorso con estensione che non esiste è un 404 vero, non la pagina.
async fn client_nuovo(base: &std::path::Path, uri: &Uri, h: &HeaderMap) -> Response {
    let p = uri.path();
    // /admin/ → /admin: i file della build sono relativi alla pagina e la CSP vieta <base>
    if p.len() > 1 && p.ends_with('/') {
        let q = uri.query().map(|q| format!("?{q}")).unwrap_or_default();
        return axum::response::Redirect::permanent(&format!("{}{q}", p.trim_end_matches('/'))).into_response();
    }
    let rel = relativo(p);
    if let Some(r) = rel.as_ref().filter(|r| !r.as_os_str().is_empty()) {
        if let Some(full) = dentro(base, r).await {
            if full.file_name().is_none_or(|n| n != "index.html") {
                return servi_file(&full, h, false).await;
            }
        } else if r.extension().is_some() {
            return non_trovato();
        }
    }
    let Ok(testo) = tokio::fs::read_to_string(base.join("index.html")).await else {
        return non_trovato();
    };
    let mut r = testo.into_response();
    r.headers_mut()
        .insert(header::CONTENT_TYPE, HeaderValue::from_static("text/html; charset=utf-8"));
    r.headers_mut().insert(header::CACHE_CONTROL, HeaderValue::from_static("no-cache"));
    r
}

/// Il client vecchio sotto /vecchio/ (quando il nuovo è la pagina principale), per chi preferisce ancora quello.
async fn vecchio(State(app): State<App>, uri: Uri, h: HeaderMap) -> Response {
    if app.web_beta.is_none() {
        return axum::response::Redirect::permanent("/").into_response();
    }
    let p = uri.path().strip_prefix("/vecchio").unwrap_or("/");
    client_vecchio(&app, p, &h).await
}

/// /beta/ era l'indirizzo provvisorio del client nuovo: ora è la pagina principale.
async fn beta(uri: Uri) -> Response {
    let q = uri.query().map(|q| format!("?{q}")).unwrap_or_default();
    axum::response::Redirect::permanent(&format!("/{q}")).into_response()
}

async fn salute(State(app): State<App>) -> Response {
    let ok = tokio::time::timeout(Duration::from_secs(3), app.tavolo.chiedi(Cmd::Salute)).await;
    match ok {
        Ok(Some(true)) => (StatusCode::OK, "ok").into_response(),
        _ => (StatusCode::SERVICE_UNAVAILABLE, "non pronto").into_response(),
    }
}

async fn metriche(State(app): State<App>, ConnectInfo(peer): ConnectInfo<SocketAddr>, h: HeaderMap) -> Response {
    let locale = peer.ip().is_loopback() && h.get("x-forwarded-for").is_none();
    let token_ok = app
        .token_metriche
        .as_ref()
        .is_some_and(|t| crate::util::uguali(&header(&h, "authorization"), &format!("Bearer {t}")));
    if !locale && !token_ok {
        return non_trovato();
    }
    let mut r = app.metriche.testo().into_response();
    r.headers_mut().insert(
        header::CONTENT_TYPE,
        HeaderValue::from_static("text/plain; version=0.0.4; charset=utf-8"),
    );
    r
}

#[cfg(test)]
mod test {
    use super::*;

    #[test]
    fn percorsi_relativi() {
        assert_eq!(relativo("/app.js"), Some(PathBuf::from("app.js")));
        assert_eq!(relativo("/%2e%2e/server.py"), None);
        assert_eq!(relativo("/..%2fserver.py"), None);
        assert_eq!(relativo("/a/../b"), None);
        assert_eq!(relativo("/a%00b"), None);
        assert_eq!(relativo("/a\\b"), None);
    }

    #[test]
    fn ip_dal_proxy() {
        let mut h = HeaderMap::new();
        h.insert("x-forwarded-for", HeaderValue::from_static("1.1.1.1, 2.2.2.2"));
        assert_eq!(ip_da(&h, None), "2.2.2.2");
    }

    #[test]
    fn credenziali_da_cookie() {
        let mut h = HeaderMap::new();
        h.insert(header::COOKIE, HeaderValue::from_static("a=b; tv_sess=abc.s3cr3t-_x"));
        let c = cred(&h, &HashMap::new());
        assert_eq!((c.id.as_str(), c.secret.as_str()), ("abc", "s3cr3t-_x"));
        h.insert("x-client", HeaderValue::from_static("hdr"));
        h.insert("x-secret", HeaderValue::from_static("x"));
        assert_eq!(cred(&h, &HashMap::new()).id, "hdr");
    }
}
