//! Il tavolo: UN task possiede tutto lo stato (utenti, partita, catalogo, connessioni) e gestisce i
//! comandi uno alla volta da una coda. Niente lock condivisi: le richieste HTTP mandano un `Cmd` e
//! aspettano la risposta su un canale oneshot.

use std::collections::{BTreeMap, HashMap};
use std::path::PathBuf;
use std::sync::Arc;
use std::time::{Duration, Instant};

use futures_util::FutureExt;
use indexmap::IndexMap;
use serde_json::{json, Map, Value};
use tokio::sync::{mpsc, oneshot};

use crate::catalogo::{self, Avventura};
use crate::comandi::Op;
use crate::db::Db;
use crate::limiti::Limiti;
use crate::metriche::Metriche;
use crate::modello::{Config, Stato, Utente, Voce};
use crate::oauth::PROVIDER;
use crate::util::{adesso, colore_valido, id_casuale, nome_riservato, tronca, uguali};

pub const MAX_LOG: usize = 400;
const CODA_CLIENTE: usize = 1024;

#[derive(Clone, Debug)]
pub struct Percorsi {
    pub dati: PathBuf,
    pub avventure: PathBuf,
    pub web: PathBuf,
}

/// Credenziali di una richiesta (header, query o cookie).
#[derive(Clone, Debug, Default)]
pub struct Cred {
    pub id: String,
    pub secret: String,
}

/// Risposta JSON con codice HTTP; `cookie` = credenziali da salvare nel cookie HttpOnly.
#[derive(Debug)]
pub struct Risposta {
    pub status: u16,
    pub corpo: Value,
    pub cookie: Option<Cred>,
}

impl Risposta {
    pub fn ok(corpo: Value) -> Risposta {
        Risposta { status: 200, corpo, cookie: None }
    }
    pub fn si() -> Risposta {
        Risposta::ok(json!({"ok": true}))
    }
    /// Rifiuto applicativo: 200 con ok:false, come il server Python.
    pub fn no(errore: &str) -> Risposta {
        if errore.is_empty() {
            return Risposta::ok(json!({"ok": false}));
        }
        Risposta::ok(json!({"ok": false, "errore": errore}))
    }
    pub fn errore(status: u16, errore: &str) -> Risposta {
        Risposta { status, corpo: json!({"ok": false, "errore": errore}), cookie: None }
    }
}

/// Chi sta facendo la richiesta (dopo l'autenticazione).
#[derive(Clone, Debug)]
pub struct Chi {
    pub id: String,
    pub nome: String,
    pub master: bool,
    pub admin: bool,
}

pub struct Connessione {
    pub conn: u64,
    pub rx: mpsc::Receiver<Arc<str>>,
}

/// I comandi che il task del tavolo sa gestire.
pub enum Cmd {
    Info(oneshot::Sender<Value>),
    Login { corpo: Value, ip: String, admin_ok: Option<(bool, Option<String>)>, reply: oneshot::Sender<Risposta> },
    DatiAdmin(oneshot::Sender<crate::modello::AdminConf>),
    Entra { corpo: Value, ip: String, reply: oneshot::Sender<Risposta> },
    Io { cred: Cred, reply: oneshot::Sender<Option<Value>> },
    Stato { cred: Cred, reply: oneshot::Sender<Option<Value>> },
    Chi { cred: Cred, reply: oneshot::Sender<Option<Chi>> },
    Connetti { cred: Cred, reply: oneshot::Sender<Option<Connessione>> },
    Disconnetti { id: String, conn: u64 },
    Op { cred: Cred, op: Box<Op>, ip: String, reply: oneshot::Sender<Risposta> },
    Contenuto(crate::contenuti::CmdContenuto),
    OAuthInizio { prov: String, base: String, reply: oneshot::Sender<Option<String>> },
    OAuthStato { prov: String, state: String, annullato: bool, reply: oneshot::Sender<Result<crate::oauth::Scambio, String>> },
    OAuthUtente { prov: String, uid: String, nome: String, avatar: String, ip: String, reply: oneshot::Sender<(String, String, String)> },
    DocumentoRiservato { aid: String, file: String, reply: oneshot::Sender<bool> },
    Riscansiona,
    Salute(oneshot::Sender<bool>),
    Chiudi(oneshot::Sender<()>),
}

#[derive(Clone)]
pub struct Handle {
    tx: mpsc::Sender<Cmd>,
}

impl Handle {
    /// Manda un comando e aspetta la risposta. `None` se il tavolo non risponde (in chiusura).
    pub async fn chiedi<T>(&self, f: impl FnOnce(oneshot::Sender<T>) -> Cmd) -> Option<T> {
        let (tx, rx) = oneshot::channel();
        self.tx.send(f(tx)).await.ok()?;
        rx.await.ok()
    }
    pub async fn manda(&self, c: Cmd) {
        let _ = self.tx.send(c).await;
    }
    pub fn prova_manda(&self, c: Cmd) {
        let _ = self.tx.try_send(c);
    }
}

pub struct Cliente {
    pub conn: u64,
    pub tx: mpsc::Sender<Arc<str>>,
}

pub struct StatoOAuth {
    pub prov: String,
    pub scade: f64,
    pub verifier: String,
    pub redirect: String,
}

pub struct Tavolo {
    pub percorsi: Percorsi,
    pub db: Db,
    pub config: Config,
    pub versione: String,
    pub utenti: IndexMap<String, Utente>,
    /// Utenti che non si sono potuti leggere dal DB: non vengono toccati dai salvataggi.
    pub intoccabili: Vec<String>,
    pub account: IndexMap<String, String>,
    pub attiva: Option<String>,
    pub stato: Stato,
    pub catalogo: BTreeMap<String, Avventura>,
    pub sessione: &'static str,
    pub clienti: HashMap<String, Cliente>,
    pub stati_oauth: HashMap<String, StatoOAuth>,
    pub limiti: Limiti,
    pub metriche: Arc<Metriche>,
    salva_entro: Option<Instant>,
    conn_seq: u64,
    online_da_mandare: bool,
}

impl Tavolo {
    pub async fn nuovo(percorsi: Percorsi, db: Db, versione: String, metriche: Arc<Metriche>) -> anyhow::Result<(Tavolo, Option<String>)> {
        let mut t = Tavolo {
            percorsi,
            db,
            config: Config::default(),
            versione,
            utenti: IndexMap::new(),
            intoccabili: vec![],
            account: IndexMap::new(),
            attiva: None,
            stato: Stato::vuoto(None, None),
            catalogo: BTreeMap::new(),
            sessione: "chiusa",
            clienti: HashMap::new(),
            stati_oauth: HashMap::new(),
            limiti: Limiti::nuovi(),
            metriche,
            salva_entro: None,
            conn_seq: 0,
            online_da_mandare: false,
        };
        let pw = t.carica_config().await?;
        t.carica_tutto().await?;
        Ok((t, pw))
    }

    /// Avvia il task del tavolo e restituisce l'handle per parlargli.
    pub fn avvia(self) -> Handle {
        let (tx, rx) = mpsc::channel(4096);
        tokio::spawn(self.ciclo(rx));
        Handle { tx }
    }

    async fn ciclo(mut self, mut rx: mpsc::Receiver<Cmd>) {
        loop {
            let scadenza = self.salva_entro;
            tokio::select! {
                cmd = rx.recv() => {
                    let Some(cmd) = cmd else { break };
                    let inizio = Instant::now();
                    let fine = matches!(cmd, Cmd::Chiudi(_));
                    // Un bug in un comando non deve fermare il tavolo: si registra e si va avanti.
                    // (Chi aspettava la risposta riceve un errore perché il canale oneshot viene chiuso.)
                    let esito = std::panic::AssertUnwindSafe(self.gestisci(cmd)).catch_unwind().await;
                    if let Err(p) = esito {
                        let msg = p.downcast_ref::<&str>().map(|s| s.to_string()).or_else(|| p.downcast_ref::<String>().cloned()).unwrap_or_default();
                        tracing::error!(errore = %msg, "comando andato in panico: il tavolo continua");
                        self.metriche.panico();
                    }
                    if self.online_da_mandare {
                        self.online_da_mandare = false;
                        let o = self.online();
                        self.invia(&json!({"t": "online", "online": o}));
                    }
                    self.metriche.comando(inizio.elapsed());
                    if fine { break; }
                }
                _ = async { tokio::time::sleep_until(scadenza.unwrap().into()).await }, if scadenza.is_some() => {
                    self.salva_ora().await;
                }
            }
        }
        self.salva_ora().await;
    }

    async fn gestisci(&mut self, cmd: Cmd) {
        match cmd {
            Cmd::Info(r) => {
                let _ = r.send(self.info());
            }
            Cmd::DatiAdmin(r) => {
                let _ = r.send(self.config.admin.clone());
            }
            Cmd::Login { corpo, ip, admin_ok, reply } => {
                let r = self.login(corpo, &ip, admin_ok).await;
                let _ = reply.send(r);
            }
            Cmd::Entra { corpo, ip, reply } => {
                let r = self.entra(corpo, &ip);
                let _ = reply.send(r);
            }
            Cmd::Io { cred, reply } => {
                let r = self.autentica(&cred).map(|id| self.io(&id));
                let _ = reply.send(r);
            }
            Cmd::Stato { cred, reply } => {
                let r = self.autentica(&cred).map(|id| self.stato_per(&id));
                let _ = reply.send(r);
            }
            Cmd::Chi { cred, reply } => {
                let r = self.autentica(&cred).map(|id| self.chi(&id));
                let _ = reply.send(r);
            }
            Cmd::Connetti { cred, reply } => {
                let r = self.autentica(&cred).map(|id| self.connetti(&id));
                let _ = reply.send(r);
            }
            Cmd::Disconnetti { id, conn } => {
                if self.clienti.get(&id).is_some_and(|c| c.conn == conn) {
                    self.clienti.remove(&id);
                    self.metriche.clienti(self.clienti.len());
                    self.online_da_mandare = true;
                }
            }
            Cmd::Op { cred, op, ip, reply } => {
                let r = match self.autentica(&cred) {
                    None => Risposta::errore(401, "non autenticato"),
                    Some(id) => {
                        if self.limiti.op(&id, op.veloce()) {
                            self.metriche.limitato();
                            Risposta::errore(429, "Piano! Troppe azioni in poco tempo")
                        } else {
                            self.metriche.op(op.nome());
                            self.op(&id, *op, &ip).await
                        }
                    }
                };
                let _ = reply.send(r);
            }
            Cmd::Contenuto(c) => self.contenuto(c).await,
            Cmd::OAuthInizio { prov, base, reply } => {
                let _ = reply.send(self.oauth_inizio(&prov, &base));
            }
            Cmd::OAuthStato { prov, state, annullato, reply } => {
                let _ = reply.send(self.oauth_stato(&prov, &state, annullato));
            }
            Cmd::OAuthUtente { prov, uid, nome, avatar, ip, reply } => {
                let r = self.oauth_utente(&prov, &uid, &nome, &avatar, &ip).await;
                let _ = reply.send(r);
            }
            Cmd::DocumentoRiservato { aid, file, reply } => {
                let r = self.catalogo.get(&aid).is_some_and(|a| a.doc_solo_master(&file));
                let _ = reply.send(r);
            }
            Cmd::Riscansiona => self.riscansiona_e_avvisa().await,
            Cmd::Salute(r) => {
                let ok = sqlx::query("SELECT 1").execute(&self.db.pool).await.is_ok();
                let _ = r.send(ok);
            }
            Cmd::Chiudi(r) => {
                self.salva_ora().await;
                let _ = r.send(());
            }
        }
    }

    // ------------------------------------------------------------------ configurazione

    /// Carica la configurazione; al primo avvio crea la password admin. Restituisce la password iniziale da mostrare.
    async fn carica_config(&mut self) -> anyhow::Result<Option<String>> {
        let grezza = self.db.get("config").await?.unwrap_or(json!({}));
        self.config = serde_json::from_value(grezza).unwrap_or_else(|e| {
            tracing::error!(errore = %e, "configurazione illeggibile: uso i valori predefiniti");
            Config::default()
        });
        for p in PROVIDER {
            self.config.oauth.entry(p.id.into()).or_default();
        }
        let mut iniziale = None;
        if self.config.admin.argon2.is_none() && self.config.admin.hash.is_none() {
            let pw = std::env::var("MASTER_PASSWORD").ok().filter(|s| !s.is_empty());
            let generata = pw.is_none();
            let pw = pw.unwrap_or_else(|| crate::util::token(9));
            let mut conf = self.config.admin.clone();
            let pw2 = pw.clone();
            conf = tokio::task::spawn_blocking(move || {
                crate::password::imposta(&mut conf, &pw2);
                conf
            })
            .await?;
            self.config.admin = conf;
            if generata {
                iniziale = Some(pw);
            }
        }
        self.salva_config().await;
        Ok(iniziale)
    }

    pub async fn salva_config(&self) {
        match serde_json::to_value(&self.config) {
            Ok(v) => {
                if let Err(e) = self.db.set("config", &v).await {
                    tracing::error!(errore = %e, "salvataggio della configurazione");
                }
            }
            Err(e) => tracing::error!(errore = %e, "serializzazione della configurazione"),
        }
    }

    /// Provider OAuth utilizzabili (attivi e con id e secret).
    pub fn oauth_attivi(&self) -> Vec<&'static crate::oauth::Provider> {
        PROVIDER
            .iter()
            .filter(|p| self.config.oauth.get(p.id).is_some_and(|c| c.attivo && !c.id.is_empty() && !c.secret.is_empty()))
            .collect()
    }

    /// Senza provider gli ospiti sono sempre ammessi (altrimenti nessuno potrebbe entrare).
    pub fn ospiti(&self) -> bool {
        self.config.ospiti || self.oauth_attivi().is_empty()
    }

    // ------------------------------------------------------------------ caricamento e salvataggio

    async fn carica_tutto(&mut self) -> anyhow::Result<()> {
        self.catalogo = catalogo::scansiona(&self.percorsi.avventure);
        let (utenti, account, scartati) = self.db.utenti().await?;
        self.utenti = utenti;
        self.intoccabili = scartati;
        self.account = account.into_iter().collect();
        let attiva = self.db.get("attiva").await?.and_then(|v| v.as_str().map(String::from));
        let attiva = attiva.filter(|a| self.catalogo.contains_key(a));
        // ricordata, ma il tavolo resta chiuso finché l'admin non lo apre
        self.attiva_avventura(attiva).await;
        Ok(())
    }

    pub fn salva_presto(&mut self) {
        if self.salva_entro.is_none() {
            self.salva_entro = Some(Instant::now() + Duration::from_secs(1));
        }
    }

    pub async fn salva_ora(&mut self) {
        self.salva_entro = None;
        let partita = match (&self.attiva, serde_json::to_value(&self.stato)) {
            (Some(a), Ok(v)) => Some((a.clone(), v)),
            (Some(_), Err(e)) => {
                tracing::error!(errore = %e, "serializzazione della partita");
                None
            }
            _ => None,
        };
        let inizio = Instant::now();
        let r = self
            .db
            .salva(self.attiva.as_deref(), &self.utenti, &self.account, partita.as_ref().map(|(a, v)| (a.as_str(), v)), &self.intoccabili)
            .await;
        match r {
            Ok(()) => self.metriche.salvataggio(inizio.elapsed()),
            Err(e) => {
                tracing::error!(errore = %e, "salvataggio non riuscito: riprovo tra poco");
                self.metriche.errore_salvataggio();
                self.salva_entro = Some(Instant::now() + Duration::from_secs(5));
            }
        }
    }

    /// Salva la partita corrente e carica (o crea) quella dell'avventura indicata.
    pub async fn attiva_avventura(&mut self, aid: Option<String>) {
        if self.attiva.is_some() {
            self.salva_ora().await;
        }
        self.attiva = aid.clone();
        let avv = aid.as_ref().and_then(|a| self.catalogo.get(a));
        let prima = avv.and_then(|a| a.prima_mappa());
        let mut st = match &aid {
            Some(a) => match self.db.partita(a).await {
                Ok(Some(v)) => match serde_json::from_value::<Stato>(v) {
                    Ok(s) => s,
                    Err(e) => {
                        tracing::error!(avventura = %a, errore = %e, "partita salvata illeggibile: ne inizio una vuota");
                        Stato::vuoto(Some(a), prima.clone())
                    }
                },
                Ok(None) => Stato::vuoto(Some(a), prima.clone()),
                Err(e) => {
                    tracing::error!(avventura = %a, errore = %e, "lettura della partita");
                    Stato::vuoto(Some(a), prima.clone())
                }
            },
            None => Stato::vuoto(None, None),
        };
        if st.avventura.is_none() {
            st.avventura = aid.clone();
        }
        let scena_ok = st.scena.as_ref().is_some_and(|s| avv.is_some_and(|a| a.ha_mappa(s)));
        if !scena_ok {
            st.scena = prima;
        }
        self.stato = st;
        for u in self.utenti.values_mut() {
            if let Some(c) = &u.char {
                if !avv.is_some_and(|a| a.ha_personaggio(c)) {
                    u.char = None;
                }
            }
        }
        self.salva_presto();
    }

    pub fn riscansiona(&mut self) {
        self.catalogo = catalogo::scansiona(&self.percorsi.avventure);
    }

    /// Chiamato dall'osservatore quando i file delle avventure cambiano.
    async fn riscansiona_e_avvisa(&mut self) {
        self.riscansiona();
        if self.attiva.as_ref().is_some_and(|a| !self.catalogo.contains_key(a)) {
            self.attiva_avventura(None).await;
            self.imposta_sessione("chiusa");
        }
        self.invia(&json!({"t": "catalogo"}));
    }

    // ------------------------------------------------------------------ eventi

    /// Manda un evento a tutti i collegati, filtrato per ruolo.
    pub fn invia(&mut self, ev: &Value) {
        self.invia_a(ev, None);
    }

    pub fn invia_a(&mut self, ev: &Value, solo: Option<&str>) {
        let tutto: Arc<str> = Arc::from(ev.to_string());
        let mut lenti = Vec::new();
        for (id, c) in &self.clienti {
            if solo.is_some_and(|s| s != id) {
                continue;
            }
            let master = self.utenti.get(id).is_some_and(Utente::is_master);
            let msg = if master {
                tutto.clone()
            } else {
                match visibile(ev, id) {
                    Visibile::Uguale => tutto.clone(),
                    Visibile::Altro(v) => Arc::from(v.to_string()),
                    Visibile::No => continue,
                }
            };
            if c.tx.try_send(msg).is_err() {
                lenti.push(id.clone());
            }
        }
        // chi non riesce a stare al passo (o ha chiuso) viene scollegato: il browser si ricollega da solo
        for id in lenti {
            self.clienti.remove(&id);
            self.online_da_mandare = true;
        }
        self.metriche.eventi(1);
    }

    pub fn online(&self) -> Value {
        Value::Array(
            self.clienti
                .keys()
                .filter_map(|id| self.utenti.get(id).map(|u| (id, u)))
                .map(|(id, u)| {
                    json!({"id": id, "name": u.name, "color": u.color, "role": u.role, "char": u.char,
                           "avatar": u.avatar.clone().unwrap_or_default(), "admin": u.admin})
                })
                .collect(),
        )
    }

    pub fn aggiungi_log(&mut self, mut voce: Voce) -> Value {
        if voce.id.is_empty() {
            voce.id = id_casuale(10);
        }
        if voce.ora == 0.0 {
            voce.ora = adesso();
        }
        let v = serde_json::to_value(&voce).unwrap_or(Value::Null);
        self.stato.log.push(voce);
        let n = self.stato.log.len();
        if n > MAX_LOG {
            self.stato.log.drain(..n - MAX_LOG);
        }
        self.invia(&json!({"t": "log", "voce": v}));
        self.salva_presto();
        v
    }

    pub fn sistema(&mut self, testo: &str) {
        let mut resto = Map::new();
        resto.insert("testo".into(), json!(testo));
        self.aggiungi_log(Voce { id: String::new(), ora: 0.0, tipo: "sistema".into(), da: None, segreto: false, resto });
    }

    pub fn online_dopo(&mut self) {
        self.online_da_mandare = true;
    }

    pub fn imposta_sessione(&mut self, s: &'static str) {
        self.sessione = s;
        let ev = json!({"t": "sessione", "sessione": s, "attiva": self.attiva});
        self.invia(&ev);
    }

    // ------------------------------------------------------------------ accesso

    /// Verifica id+secret; aggiorna «visto». Restituisce l'id dell'utente.
    pub fn autentica(&mut self, c: &Cred) -> Option<String> {
        if c.id.is_empty() || c.secret.is_empty() {
            return None;
        }
        let u = self.utenti.get_mut(&c.id)?;
        if !uguali(&u.secret, &c.secret) {
            return None;
        }
        u.seen = adesso();
        Some(c.id.clone())
    }

    fn chi(&self, id: &str) -> Chi {
        let u = &self.utenti[id];
        Chi { id: id.into(), nome: u.name.clone(), master: u.is_master(), admin: u.admin }
    }

    fn connetti(&mut self, id: &str) -> Connessione {
        self.conn_seq += 1;
        let (tx, rx) = mpsc::channel(CODA_CLIENTE);
        // una nuova connessione dello stesso utente sostituisce la vecchia (che così si chiude)
        self.clienti.insert(id.to_string(), Cliente { conn: self.conn_seq, tx });
        self.metriche.clienti(self.clienti.len());
        self.online_da_mandare = true;
        Connessione { conn: self.conn_seq, rx }
    }

    fn info(&self) -> Value {
        let a = if self.sessione != "chiusa" { self.attiva.as_ref().and_then(|a| self.catalogo.get(a)) } else { None };
        let presi: Vec<&String> = self.clienti.keys().filter_map(|c| self.utenti.get(c).and_then(|u| u.char.as_ref())).collect();
        let campo = |k: &str| a.and_then(|a| a.dati.get(k).cloned()).unwrap_or(json!(""));
        let personaggi: Vec<Value> = a
            .map(|a| {
                a.personaggi()
                    .iter()
                    .map(|p| {
                        let mut o = Map::new();
                        for k in ["id", "nome", "icona", "razza", "classe", "colore", "facoltativo"] {
                            o.insert(k.into(), p.get(k).cloned().unwrap_or(Value::Null));
                        }
                        Value::Object(o)
                    })
                    .collect()
            })
            .unwrap_or_default();
        json!({
            "avventura": {"id": campo("id"), "titolo": campo("titolo"), "sottotitolo": campo("sottotitolo"), "descrizione": campo("descrizione")},
            "personaggi": personaggi, "presi": presi, "password_giocatori": !self.config.password_giocatori.is_empty(),
            "login": self.oauth_attivi().iter().map(|p| json!({"id": p.id, "nome": p.nome})).collect::<Vec<_>>(),
            "ospiti": self.ospiti(), "versione": self.versione, "nome_tavolo": self.config.nome_tavolo, "sessione": self.sessione,
        })
    }

    fn io(&self, id: &str) -> Value {
        let u = &self.utenti[id];
        json!({"ok": true, "nome": u.name, "admin": u.admin, "master": u.master_ok || u.admin,
               "provider": u.provider.clone().unwrap_or_default(), "avatar": u.avatar.clone().unwrap_or_default(),
               "char": u.char, "colore": u.color, "ruolo": u.role})
    }

    pub fn avventura_per(&self, master: bool) -> Value {
        match self.attiva.as_ref().and_then(|a| self.catalogo.get(a)) {
            Some(a) => a.per_ruolo(master),
            None => catalogo::vuota(),
        }
    }

    fn stato_per(&self, id: &str) -> Value {
        let u = &self.utenti[id];
        let master = u.is_master();
        let mut s = serde_json::to_value(&self.stato).unwrap_or(json!({}));
        if !master {
            if let Some(Value::Object(p)) = s.get_mut("pedine") {
                p.retain(|_, v| v.get("nascosta") != Some(&Value::Bool(true)));
            }
            if let Some(Value::Array(l)) = s.get_mut("log") {
                l.retain(|e| e.get("segreto") != Some(&Value::Bool(true)) || e.get("da").and_then(Value::as_str) == Some(id));
            }
            s["note_master"] = json!("");
        }
        s["online"] = self.online();
        s["io"] = json!({"id": id, "name": u.name, "color": u.color, "role": u.role, "char": u.char,
                         "avatar": u.avatar, "provider": u.provider, "admin": u.admin});
        s["avv"] = self.avventura_per(master);
        s["sessione"] = json!(self.sessione);
        if master || u.admin {
            s["catalogo"] = Value::Array(self.catalogo.values().map(Avventura::breve).collect());
            s["attiva"] = json!(self.attiva);
        }
        s
    }

    /// Primo passo: chi sei? (ospite o amministratore). `admin_ok` è la verifica della password fatta fuori dal task.
    async fn login(&mut self, corpo: Value, ip: &str, admin_ok: Option<(bool, Option<String>)>) -> Risposta {
        let s = |k: &str| corpo.get(k).and_then(crate::util::testo).unwrap_or_default();
        let cred = Cred { id: s("id"), secret: s("secret") };
        let conosciuto = !cred.id.is_empty()
            && self.utenti.get(&cred.id).is_some_and(|u| uguali(&u.secret, &cred.secret));
        let mut id = cred.id.clone();
        match corpo.get("tipo").and_then(Value::as_str) {
            Some("admin") => {
                let (ok, aggiorna) = admin_ok.unwrap_or((false, None));
                if !ok {
                    self.metriche.accesso_fallito();
                    self.db.audit(None, Some(&s("utente")), Some(ip), "login_admin_fallito", &json!({})).await;
                    return Risposta::errore(403, "Utente o password dell'amministratore sbagliati");
                }
                if let Some(h) = aggiorna {
                    self.config.admin.argon2 = Some(h);
                    self.salva_config().await;
                    self.db.audit(None, None, Some(ip), "password_admin_convertita_argon2", &json!({})).await;
                }
                let nuovo = !conosciuto;
                if nuovo {
                    id = id_casuale(12);
                    let nome = capitalizza(&self.config.admin.utente);
                    self.utenti.insert(id.clone(), Utente::nuovo(&nome, "#e0b04a", "master"));
                }
                let u = self.utenti.get_mut(&id).expect("utente");
                u.admin = true;
                u.master_ok = true;
                u.seen = adesso();
                let nome = u.name.clone();
                self.db.audit(Some(&id), Some(&nome), Some(ip), "login_admin", &json!({"nuovo_utente": nuovo})).await;
            }
            Some("ospite") => {
                if !self.ospiti() {
                    return Risposta::errore(403, "Gli ospiti non sono ammessi: accedi con un account");
                }
                let pwg = &self.config.password_giocatori;
                if !pwg.is_empty() && !uguali(&s("password"), pwg) {
                    self.metriche.accesso_fallito();
                    return Risposta::errore(403, "Password del tavolo sbagliata (chiedila al Master)");
                }
                let nome = tronca(s("nome").trim(), 30);
                if nome.is_empty() {
                    return Risposta::errore(400, "Scrivi il tuo nome");
                }
                if nome_riservato(&nome, &self.config.admin.utente) {
                    return Risposta::errore(400, "Questo nome è riservato: scegline un altro");
                }
                if !conosciuto {
                    id = id_casuale(12);
                    self.utenti.insert(id.clone(), Utente::nuovo("", "#c0392b", "giocatore"));
                }
                let u = self.utenti.get_mut(&id).expect("utente");
                u.name = nome;
                u.seen = adesso();
            }
            _ => return Risposta::errore(400, "tipo di accesso non valido"),
        }
        self.salva_presto();
        let u = &self.utenti[&id];
        let mut r = Risposta::ok(json!({"ok": true, "id": id, "secret": u.secret, "nome": u.name}));
        r.cookie = Some(Cred { id: id.clone(), secret: u.secret.clone() });
        r
    }

    /// Il personaggio è già in mano a un altro giocatore collegato?
    pub fn pg_occupato(&self, pg: &str, id: &str) -> bool {
        self.clienti.keys().any(|k| k != id && self.utenti.get(k).is_some_and(|u| u.char.as_deref() == Some(pg)))
    }

    /// Secondo passo: ci si siede al tavolo con un ruolo (e magari un personaggio).
    fn entra(&mut self, corpo: Value, _ip: &str) -> Risposta {
        let s = |k: &str| corpo.get(k).and_then(crate::util::testo).unwrap_or_default();
        let cred = Cred { id: s("id"), secret: s("secret") };
        let Some(id) = self.autentica(&cred) else {
            return Risposta { status: 401, corpo: json!({"ok": false, "errore": "Devi prima accedere", "login": true}), cookie: None };
        };
        let u = &self.utenti[&id];
        // Master: l'admin (se lo chiede) oppure chi è stato nominato Master dall'admin. Tutti gli altri sono giocatori.
        let mut ruolo = if s("ruolo") == "master" && (u.master_ok || u.admin) { "master" } else { "giocatore" };
        if u.is_master() && u.master_ok && !u.admin {
            ruolo = "master";
        }
        let avv = self.attiva.as_ref().and_then(|a| self.catalogo.get(a));
        let pg = Some(s("personaggio")).filter(|p| !p.is_empty()).filter(|p| avv.is_some_and(|a| a.ha_personaggio(p)));
        let nome = tronca(s("nome").trim(), 30);
        if !nome.is_empty() && nome_riservato(&nome, &self.config.admin.utente) && !u.admin {
            return Risposta::errore(400, "Questo nome è riservato: scegline un altro");
        }
        if let Some(p) = &pg {
            if ruolo == "giocatore" && self.pg_occupato(p, &id) {
                return Risposta::errore(409, "Personaggio già scelto da un altro giocatore");
            }
        }
        let colore = colore_valido(corpo.get("colore").and_then(Value::as_str), &colore_valido(Some(&u.color), "#c0392b"));
        let u = self.utenti.get_mut(&id).expect("utente");
        if !nome.is_empty() {
            u.name = nome;
        }
        u.color = colore.clone();
        u.role = ruolo.into();
        u.char = if ruolo == "giocatore" { pg.clone() } else { None };
        u.seen = adesso();
        let (nome, secret) = (u.name.clone(), u.secret.clone());
        if let (Some(p), "giocatore") = (&pg, ruolo) {
            self.crea_pedina_pg(&id, p, &colore);
        }
        self.salva_presto();
        if self.sessione != "chiusa" {
            let come = if ruolo == "master" { " come Master" } else { "" };
            self.sistema(&format!("👋 {nome} si è seduto al tavolo{come}."));
        }
        self.online_da_mandare = true;
        let mut r = Risposta::ok(json!({"ok": true, "id": id, "secret": secret}));
        r.cookie = Some(Cred { id, secret });
        r
    }

    // ------------------------------------------------------------------ OAuth

    fn oauth_inizio(&mut self, prov: &str, base: &str) -> Option<String> {
        let p = self.oauth_attivi().into_iter().find(|p| p.id == prov)?;
        let conf = self.config.oauth.get(prov)?.clone();
        let ora = adesso();
        self.stati_oauth.retain(|_, s| s.scade >= ora);
        if self.stati_oauth.len() > 10_000 {
            return None;
        }
        let state = crate::util::token(24);
        let verifier = crate::util::token(48);
        let base = if self.config.public_url.is_empty() { base } else { self.config.public_url.as_str() };
        let redirect = format!("{}/auth/{}/callback", base.trim_end_matches('/'), prov);
        let url = crate::oauth::url_autorizzazione(p, &conf.id, &redirect, &state, &verifier);
        self.stati_oauth.insert(state, StatoOAuth { prov: prov.into(), scade: ora + 600.0, verifier, redirect });
        Some(url)
    }

    /// `Err("")` = provider non attivo (404); altri errori diventano una pagina con il messaggio.
    fn oauth_stato(&mut self, prov: &str, state: &str, annullato: bool) -> Result<crate::oauth::Scambio, String> {
        if !self.oauth_attivi().iter().any(|p| p.id == prov) {
            return Err(String::new());
        }
        if annullato {
            return Err("Accesso annullato.".into());
        }
        let st = self.stati_oauth.remove(state);
        let Some(st) = st.filter(|s| s.prov == prov && s.scade >= adesso()) else {
            return Err("Accesso scaduto o non valido: riprova.".into());
        };
        let p = PROVIDER.iter().find(|p| p.id == prov).ok_or("provider sconosciuto")?;
        let conf = self.config.oauth.get(prov).cloned().unwrap_or_default();
        Ok(crate::oauth::Scambio { provider: p, client_id: conf.id, client_secret: conf.secret, verifier: st.verifier, redirect: st.redirect })
    }

    async fn oauth_utente(&mut self, prov: &str, uid: &str, nome: &str, avatar: &str, ip: &str) -> (String, String, String) {
        let chiave = format!("{prov}:{uid}");
        let mut nuovo = false;
        let id = match self.account.get(&chiave).filter(|c| self.utenti.contains_key(*c)) {
            Some(c) => c.clone(),
            None => {
                let id = id_casuale(12);
                let n = if nome.is_empty() { "Avventuriero".to_string() } else { tronca(nome, 30) };
                self.utenti.insert(id.clone(), Utente::nuovo(&n, "#c0392b", "giocatore"));
                self.account.insert(chiave.clone(), id.clone());
                nuovo = true;
                id
            }
        };
        let nome_prov = PROVIDER.iter().find(|p| p.id == prov).map(|p| p.nome).unwrap_or(prov);
        let u = self.utenti.get_mut(&id).expect("utente");
        u.account = Some(chiave.clone());
        u.avatar = Some(avatar.to_string());
        u.provider = Some(nome_prov.to_string());
        u.seen = adesso();
        let r = (id.clone(), u.secret.clone(), u.name.clone());
        let admin = u.admin;
        self.salva_presto();
        self.db
            .audit(Some(&id), Some(&r.2), Some(ip), if admin { "login_admin_oauth" } else { "login_oauth" }, &json!({"account": chiave, "nuovo_utente": nuovo}))
            .await;
        r
    }
}

pub fn capitalizza(s: &str) -> String {
    let mut c = s.chars();
    match c.next() {
        Some(p) => p.to_uppercase().collect::<String>() + &c.as_str().to_lowercase(),
        None => String::new(),
    }
}

pub enum Visibile {
    Uguale,
    Altro(Value),
    No,
}

/// Cosa vede di un evento chi non è Master.
pub fn visibile(ev: &Value, id: &str) -> Visibile {
    match ev.get("t").and_then(Value::as_str) {
        Some("pedina") if ev["pedina"].get("nascosta") == Some(&Value::Bool(true)) => {
            Visibile::Altro(json!({"t": "pedina_via", "id": ev["pedina"]["id"]}))
        }
        Some("log") => {
            let v = &ev["voce"];
            if v.get("segreto") == Some(&Value::Bool(true)) && v.get("da").and_then(Value::as_str) != Some(id) {
                Visibile::No
            } else {
                Visibile::Uguale
            }
        }
        _ => Visibile::Uguale,
    }
}
