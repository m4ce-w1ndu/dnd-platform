//! Contenuti delle avventure: caricamenti, gestione di mappe/documenti/avventure, esporta/importa/backup.

use std::path::PathBuf;
use std::sync::LazyLock;

use crate::api::Evento;
use bytes::Bytes;
use regex::Regex;
use serde_json::{json, Map, Value};
use tokio::sync::oneshot;

use crate::catalogo::{dividi_ext, leggi_json, scrivi_json, DOC_EXT, IMG_EXT};
use crate::comandi::Op;
use crate::modello::{Stato, CHIAVI_STATO};
use crate::tavolo::{Cred, Risposta, Tavolo};
use crate::util::{id_casuale, id_valido, slug, tronca};

static NON_STEM: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"[^a-z0-9_\-]").unwrap());
static NON_DOC: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"[^\w\-.]").unwrap());

pub enum CmdContenuto {
    CaricaMappa {
        cred: Cred,
        nome: String,
        titolo: String,
        cella: f64,
        dati: Bytes,
        reply: oneshot::Sender<Risposta>,
    },
    CaricaDocumento {
        cred: Cred,
        nome: String,
        titolo: String,
        solo_master: bool,
        dati: Bytes,
        reply: oneshot::Sender<Risposta>,
    },
    InstallaPacchetto {
        cred: Cred,
        tmp: PathBuf,
        aid: String,
        ip: String,
        reply: oneshot::Sender<Risposta>,
    },
    /// Autorizzazione + cartella delle avventure, per estrarre un pacchetto fuori dal task.
    PermessoCarica {
        cred: Cred,
        reply: oneshot::Sender<Option<PathBuf>>,
    },
    CartellaAvventura {
        cred: Cred,
        aid: String,
        reply: oneshot::Sender<Option<PathBuf>>,
    },
    Esporta {
        cred: Cred,
        aid: Option<String>,
        reply: oneshot::Sender<Option<(String, Vec<u8>)>>,
    },
    Importa {
        cred: Cred,
        corpo: Value,
        ip: String,
        reply: oneshot::Sender<Risposta>,
    },
    Backup {
        cred: Cred,
        ip: String,
        reply: oneshot::Sender<Option<PathBuf>>,
    },
    Audit {
        cred: Cred,
        reply: oneshot::Sender<Option<Value>>,
    },
}

impl Tavolo {
    /// L'utente è (ancora) il Master? Si ricontrolla dentro il task, al momento dell'operazione.
    fn master_da(&mut self, cred: &Cred) -> Option<String> {
        let id = self.autentica(cred)?;
        self.utenti[&id].is_master().then_some(id)
    }

    fn cartella_attiva(&self) -> Option<PathBuf> {
        self.attiva.as_ref().map(|a| self.percorsi.avventure.join(a))
    }

    pub async fn contenuto(&mut self, c: CmdContenuto) {
        match c {
            CmdContenuto::CaricaMappa {
                cred,
                nome,
                titolo,
                cella,
                dati,
                reply,
            } => {
                let r = match self.master_da(&cred) {
                    None => Risposta::errore(403, "solo il Master può caricare"),
                    Some(_) => self.carica_mappa(&nome, &titolo, cella, &dati).await,
                };
                let _ = reply.send(r);
            }
            CmdContenuto::CaricaDocumento {
                cred,
                nome,
                titolo,
                solo_master,
                dati,
                reply,
            } => {
                let r = match self.master_da(&cred) {
                    None => Risposta::errore(403, "solo il Master può caricare"),
                    Some(_) => self.carica_documento(&nome, &titolo, solo_master, &dati).await,
                };
                let _ = reply.send(r);
            }
            CmdContenuto::PermessoCarica { cred, reply } => {
                let r = self.master_da(&cred).map(|_| self.percorsi.avventure.clone());
                let _ = reply.send(r);
            }
            CmdContenuto::InstallaPacchetto { cred, tmp, aid, ip, reply } => {
                let Some(id) = self.master_da(&cred) else {
                    let _ = std::fs::remove_dir_all(&tmp);
                    let _ = reply.send(Risposta::errore(403, "solo il Master può caricare"));
                    return;
                };
                let avv = self.percorsi.avventure.clone();
                let a2 = aid.clone();
                let esito = tokio::task::spawn_blocking(move || crate::pacchetti::installa(&tmp, &avv, &a2)).await;
                let r = match esito {
                    Ok(Ok(())) => {
                        self.riscansiona();
                        self.invia(Evento::Catalogo);
                        if Some(&aid) == self.attiva.as_ref() {
                            self.attiva_avventura(Some(aid.clone())).await;
                            self.invia(Evento::Ricarica);
                        }
                        let nome = self.utenti.get(&id).map(|u| u.name.clone());
                        self.db
                            .audit(
                                Some(&id),
                                nome.as_deref(),
                                Some(&ip),
                                "carica_avventura",
                                &json!({"avventura": aid}),
                            )
                            .await;
                        let titolo = self.catalogo.get(&aid).map(|a| a.titolo()).unwrap_or(aid.clone());
                        Risposta::ok(json!({"ok": true, "id": aid, "titolo": titolo}))
                    }
                    _ => Risposta::errore(500, "installazione non riuscita"),
                };
                let _ = reply.send(r);
            }
            CmdContenuto::CartellaAvventura { cred, aid, reply } => {
                let ok = self.master_da(&cred).is_some() && self.catalogo.contains_key(&aid);
                let _ = reply.send(ok.then(|| self.percorsi.avventure.join(&aid)));
            }
            CmdContenuto::Esporta { cred, aid, reply } => {
                let r = if self.master_da(&cred).is_some() {
                    self.salva_ora().await;
                    let aid = aid.or_else(|| self.attiva.clone()).unwrap_or_default();
                    let st = self.db.partita(&aid).await.ok().flatten().unwrap_or(json!({}));
                    Some((aid, serde_json::to_vec_pretty(&st).unwrap_or_default()))
                } else {
                    None
                };
                let _ = reply.send(r);
            }
            CmdContenuto::Importa { cred, corpo, ip, reply } => {
                let r = match self.master_da(&cred) {
                    None => Risposta::errore(404, ""),
                    Some(id) => self.importa(&id, corpo, &ip).await,
                };
                let _ = reply.send(r);
            }
            CmdContenuto::Backup { cred, ip, reply } => {
                let Some(id) = self.autentica(&cred).filter(|id| self.utenti[id].sistema) else {
                    let _ = reply.send(None);
                    return;
                };
                self.salva_ora().await;
                let dest = self.percorsi.dati.join(format!("tavolo.db.backup-{}", id_casuale(8)));
                let r = match self.db.copia_in(&dest).await {
                    Ok(()) => Some(dest),
                    Err(e) => {
                        tracing::error!(errore = %e, "backup del database");
                        None
                    }
                };
                let nome = self.utenti[&id].name.clone();
                self.db.audit(Some(&id), Some(&nome), Some(&ip), "backup", &json!({})).await;
                let _ = reply.send(r);
            }
            CmdContenuto::Audit { cred, reply } => {
                let ok = self.autentica(&cred).is_some_and(|id| self.utenti[&id].sistema);
                let r = if ok {
                    self.db.leggi_audit(1000).await.ok().map(Value::from)
                } else {
                    None
                };
                let _ = reply.send(r);
            }
        }
    }

    async fn importa(&mut self, id: &str, corpo: Value, ip: &str) -> Risposta {
        let Value::Object(corpo) = corpo else {
            return Risposta::errore(400, "salvataggio non valido");
        };
        let prima = self
            .attiva
            .as_ref()
            .and_then(|a| self.catalogo.get(a))
            .and_then(|a| a.prima_mappa());
        let mut base = serde_json::to_value(Stato::vuoto(self.attiva.as_deref(), prima)).unwrap_or(json!({}));
        for k in CHIAVI_STATO {
            if let Some(v) = corpo.get(*k) {
                base[*k] = v.clone();
            }
        }
        match serde_json::from_value::<Stato>(base) {
            Ok(st) => {
                self.stato = st;
                self.invia(Evento::Ricarica);
                self.salva_presto();
                let nome = self.utenti[id].name.clone();
                self.db
                    .audit(
                        Some(id),
                        Some(&nome),
                        Some(ip),
                        "importa_partita",
                        &json!({"avventura": self.attiva}),
                    )
                    .await;
                Risposta::si()
            }
            Err(e) => Risposta::errore(400, &format!("salvataggio non valido ({e})")),
        }
    }

    async fn carica_mappa(&mut self, nome_file: &str, titolo: &str, cella: f64, dati: &[u8]) -> Risposta {
        let Some(base) = self.cartella_attiva() else {
            return Risposta::errore(400, "nessuna avventura attiva");
        };
        let (stem, ext) = dividi_ext(nome_file).unwrap_or((nome_file, ""));
        let ext = ext.to_lowercase();
        if !IMG_EXT.contains(&ext.as_str()) {
            return Risposta::errore(400, "formato immagine non supportato (svg, png, jpg, webp)");
        }
        let mut stem: String = NON_STEM.replace_all(&stem.to_lowercase(), "_").chars().take(40).collect();
        if stem.is_empty() {
            stem = "mappa".into();
        }
        let cart = base.join("mappe");
        if tokio::fs::create_dir_all(&cart).await.is_err() {
            return Risposta::errore(500, "impossibile creare la cartella delle mappe");
        }
        if cart.join(format!("{stem}.{ext}")).exists() {
            stem = format!("{stem}_{}", id_casuale(4));
        }
        if let Err(e) = tokio::fs::write(cart.join(format!("{stem}.{ext}")), dati).await {
            tracing::error!(errore = %e, "scrittura della mappa");
            return Risposta::errore(500, "scrittura non riuscita");
        }
        let mut meta =
            json!({"titolo": if titolo.is_empty() { stem.clone() } else { tronca(titolo, 200) }, "gruppo": "Caricate", "ordine": 500});
        if cella > 0.0 && cella.is_finite() {
            meta["griglia"] = json!({"cella": cella, "ox": 0, "oy": 0, "mostra": true});
        }
        if scrivi_json(&cart.join(format!("{stem}.json")), &meta).is_err() {
            return Risposta::errore(500, "scrittura non riuscita");
        }
        self.riscansiona();
        self.invia(Evento::Catalogo);
        Risposta::ok(json!({"ok": true, "id": stem}))
    }

    async fn carica_documento(&mut self, nome_file: &str, titolo: &str, solo_master: bool, dati: &[u8]) -> Risposta {
        let Some(base) = self.cartella_attiva() else {
            return Risposta::errore(400, "nessuna avventura attiva");
        };
        let base_nome = nome_file.rsplit(['/', '\\']).next().unwrap_or("");
        let (stem, ext) = dividi_ext(base_nome).unwrap_or((base_nome, ""));
        let ext = ext.to_lowercase();
        if !DOC_EXT.contains(&ext.as_str()) {
            return Risposta::errore(400, "formato non supportato (html, pdf, md, txt o immagini)");
        }
        let stem: String = NON_DOC.replace_all(stem, "_").chars().take(60).collect();
        let stem = if stem.is_empty() || stem.chars().all(|c| c == '.') {
            "documento".to_string()
        } else {
            stem
        };
        let nome = format!("{stem}.{ext}");
        let docs = base.join("documenti");
        if tokio::fs::create_dir_all(&docs).await.is_err() || tokio::fs::write(docs.join(&nome), dati).await.is_err() {
            return Risposta::errore(500, "scrittura non riuscita");
        }
        let man_p = base.join("avventura.json");
        let mut man = leggi_json(&man_p).and_then(|v| v.as_object().cloned()).unwrap_or_default();
        let mut lista: Vec<Value> = man
            .get("documenti")
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default()
            .into_iter()
            .filter(|d| d.get("file").and_then(Value::as_str) != Some(nome.as_str()))
            .collect();
        let titolo = if titolo.is_empty() { stem.clone() } else { tronca(titolo, 200) };
        lista.push(json!({"file": nome, "titolo": titolo, "solo_master": solo_master}));
        man.insert("documenti".into(), Value::Array(lista));
        if scrivi_json(&man_p, &Value::Object(man)).is_err() {
            return Risposta::errore(500, "scrittura non riuscita");
        }
        self.riscansiona();
        self.invia(Evento::Catalogo);
        Risposta::si()
    }

    fn scrivi_meta_mappa(&self, scena: &str, aggiorna: Map<String, Value>) -> Result<(), Risposta> {
        let a = self.attiva.as_ref().and_then(|a| self.catalogo.get(a));
        if !a.is_some_and(|a| a.ha_mappa(scena)) {
            return Err(Risposta::errore(400, "mappa inesistente"));
        }
        let path = self.cartella_attiva().expect("attiva").join("mappe").join(format!("{scena}.json"));
        let mut meta = leggi_json(&path).and_then(|v| v.as_object().cloned()).unwrap_or_default();
        meta.extend(aggiorna);
        scrivi_json(&path, &Value::Object(meta)).map_err(|_| Risposta::errore(500, "scrittura non riuscita"))
    }

    pub async fn op_avventura(&mut self, id: &str, nome_u: &str, ip: &str, op: Op) -> Risposta {
        match op {
            Op::Griglia { id: sid, griglia } => {
                let g = griglia.unwrap_or_default();
                let mut agg = Map::new();
                agg.insert(
                    "griglia".into(),
                    json!({"cella": g.cella, "ox": g.ox, "oy": g.oy, "mostra": g.mostra}),
                );
                if let Err(r) = self.scrivi_meta_mappa(&sid, agg) {
                    return r;
                }
            }
            Op::MappaMeta {
                id: sid,
                titolo,
                ordine,
                note_master,
                gruppo,
            } => {
                let mut agg = Map::new();
                for (k, v) in [("titolo", titolo), ("note_master", note_master), ("gruppo", gruppo)] {
                    if let Some(v) = v {
                        let v = v.unwrap_or(Value::Null);
                        let v = match v {
                            Value::String(s) => json!(tronca(&s, 5000)),
                            Value::Null | Value::Number(_) | Value::Bool(_) => v,
                            _ => return Risposta::errore(400, "dati non validi"),
                        };
                        agg.insert(k.into(), v);
                    }
                }
                if let Some(o) = ordine {
                    agg.insert("ordine".into(), json!(o));
                }
                if let Err(r) = self.scrivi_meta_mappa(&sid, agg) {
                    return r;
                }
            }
            Op::AvventuraNuova { titolo } => {
                let titolo = titolo.trim().to_string();
                if titolo.is_empty() {
                    return Risposta::no("serve un titolo");
                }
                let mut aid = slug(&titolo, 40);
                while self.percorsi.avventure.join(&aid).exists() {
                    aid = format!("{}-{}", slug(&titolo, 34), id_casuale(4));
                }
                let base = self.percorsi.avventure.join(&aid);
                let ok = std::fs::create_dir_all(base.join("mappe")).is_ok()
                    && std::fs::create_dir_all(base.join("documenti")).is_ok()
                    && scrivi_json(
                        &base.join("avventura.json"),
                        &json!({"id": aid, "titolo": tronca(&titolo, 80), "formato": 1, "documenti": []}),
                    )
                    .is_ok()
                    && scrivi_json(&base.join("personaggi.json"), &json!([])).is_ok()
                    && scrivi_json(&base.join("mostri.json"), &json!([])).is_ok();
                if !ok {
                    return Risposta::errore(500, "impossibile creare l'avventura");
                }
                self.riscansiona();
                self.invia(Evento::Catalogo);
                return Risposta::ok(json!({"ok": true, "id": aid}));
            }
            Op::AvventuraInfo { campi } => {
                let Some(base) = self.cartella_attiva() else {
                    return Risposta::errore(400, "nessuna avventura attiva");
                };
                let man_p = base.join("avventura.json");
                let mut man = leggi_json(&man_p).and_then(|v| v.as_object().cloned()).unwrap_or_default();
                for k in ["titolo", "sottotitolo", "descrizione", "livello", "giocatori", "durata"] {
                    if let Some(v) = campi.get(k) {
                        let Some(t) = crate::util::testo(v).or_else(|| v.is_null().then(String::new)) else {
                            return Risposta::errore(400, "dati non validi");
                        };
                        man.insert(k.into(), json!(tronca(&t, 2000)));
                    }
                }
                if scrivi_json(&man_p, &Value::Object(man)).is_err() {
                    return Risposta::errore(500, "scrittura non riuscita");
                }
            }
            Op::MappaElimina { id: mid } => {
                let Some(a) = self.attiva.as_ref().and_then(|a| self.catalogo.get(a)) else {
                    return Risposta::no("mappa inesistente");
                };
                if !a.ha_mappa(&mid) {
                    return Risposta::no("mappa inesistente");
                }
                if a.mappe().len() <= 1 {
                    return Risposta::no("l'avventura deve avere almeno una mappa");
                }
                let cart = self.cartella_attiva().expect("attiva").join("mappe");
                if let Ok(rd) = std::fs::read_dir(&cart) {
                    for e in rd.filter_map(|e| e.ok()) {
                        let n = e.file_name().to_string_lossy().to_string();
                        let stem = dividi_ext(&n).map(|(s, _)| s).unwrap_or(&n);
                        if stem == mid && e.path().is_file() {
                            let _ = std::fs::remove_file(e.path());
                        }
                    }
                }
                self.riscansiona();
                if self.stato.scena.as_deref() == Some(&mid) {
                    self.stato.scena = self
                        .attiva
                        .as_ref()
                        .and_then(|a| self.catalogo.get(a))
                        .and_then(|a| a.prima_mappa());
                    self.invia(Evento::Scena {
                        id: self.stato.scena.clone(),
                    });
                }
                self.salva_presto();
                self.db
                    .audit(
                        Some(id),
                        Some(nome_u),
                        Some(ip),
                        "mappa_elimina",
                        &json!({"avventura": self.attiva, "mappa": mid}),
                    )
                    .await;
            }
            Op::DocumentoElimina { file } => {
                let Some(base) = self.cartella_attiva() else {
                    return Risposta::errore(400, "nessuna avventura attiva");
                };
                let nome = file.rsplit(['/', '\\']).next().unwrap_or("").to_string();
                let man_p = base.join("avventura.json");
                let mut man = leggi_json(&man_p).and_then(|v| v.as_object().cloned()).unwrap_or_default();
                let lista: Vec<Value> = man
                    .get("documenti")
                    .and_then(Value::as_array)
                    .cloned()
                    .unwrap_or_default()
                    .into_iter()
                    .filter(|d| d.get("file").and_then(Value::as_str) != Some(nome.as_str()))
                    .collect();
                man.insert("documenti".into(), Value::Array(lista));
                if scrivi_json(&man_p, &Value::Object(man)).is_err() {
                    return Risposta::errore(500, "scrittura non riuscita");
                }
                if !nome.is_empty() && nome != "." && nome != ".." {
                    let _ = std::fs::remove_file(base.join("documenti").join(&nome));
                }
            }
            Op::AvventuraElimina { id: aid } => {
                if Some(&aid) == self.attiva.as_ref() {
                    return Risposta::no("non puoi eliminare l'avventura in corso");
                }
                if !id_valido(&aid) || !self.catalogo.contains_key(&aid) {
                    return Risposta::no("avventura inesistente");
                }
                let dir = self.percorsi.avventure.join(&aid);
                let _ = tokio::task::spawn_blocking(move || std::fs::remove_dir_all(dir)).await;
                let _ = self.db.elimina_partita(&aid).await;
                self.db
                    .audit(Some(id), Some(nome_u), Some(ip), "avventura_elimina", &json!({"avventura": aid}))
                    .await;
            }
            _ => return Risposta::no("operazione sconosciuta"),
        }
        self.riscansiona();
        self.invia(Evento::Catalogo);
        Risposta::si()
    }
}
