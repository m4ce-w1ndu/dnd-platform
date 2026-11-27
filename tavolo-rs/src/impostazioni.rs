//! Impostazioni (`imp_*`, solo admin): configurazione, password admin, utenti, partite salvate.

use std::sync::LazyLock;

use crate::api::Evento;
use regex::Regex;
use serde_json::{json, Value};

use crate::catalogo::Avventura;
use crate::comandi::Op;
use crate::modello::Stato;
use crate::oauth::PROVIDER;
use crate::tavolo::{Risposta, Tavolo};
use crate::util::tronca;

static SPAZI: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"\s+").unwrap());
static HA_SCHEMA: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"(?i)^https?://").unwrap());
static SOLO_ORIGINE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"(?i)^(https?://[^/\s]+).*$").unwrap());
static URL_OK: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"^https?://[a-z0-9.\-]+(:\d+)?$").unwrap());

fn formato_id(prov: &str) -> &'static Regex {
    static DISCORD: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"^\d{15,25}$").unwrap());
    static GOOGLE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"^[\w\-]+\.apps\.googleusercontent\.com$").unwrap());
    static GITHUB: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"^[A-Za-z0-9._\-]{10,60}$").unwrap());
    match prov {
        "discord" => &DISCORD,
        "google" => &GOOGLE,
        _ => &GITHUB,
    }
}

/// Normalizza l'indirizzo pubblico: «dnd.esempio.it/x» → «https://dnd.esempio.it». `None` se non valido.
pub fn normalizza_url(url: &str) -> Option<String> {
    let mut url = url.trim().to_string();
    if url.is_empty() {
        return Some(url);
    }
    if !HA_SCHEMA.is_match(&url) {
        url = format!("https://{url}");
    }
    let url = SOLO_ORIGINE.replace(&url, "$1").to_lowercase();
    if !URL_OK.is_match(&url) || (!url.contains('.') && !url.contains("localhost")) {
        return None;
    }
    Some(url)
}

impl Tavolo {
    pub fn config_pubblica(&self) -> Value {
        let c = &self.config;
        let oauth: serde_json::Map<String, Value> = PROVIDER
            .iter()
            .map(|p| {
                let o = c.oauth.get(p.id).cloned().unwrap_or_default();
                (
                    p.id.to_string(),
                    json!({"attivo": o.attivo, "id": o.id, "secret_impostato": !o.secret.is_empty(), "nome": p.nome, "console": p.console}),
                )
            })
            .collect();
        json!({"nome_tavolo": c.nome_tavolo, "public_url": c.public_url, "ospiti": c.ospiti,
               "password_giocatori": c.password_giocatori, "admin_utente": c.admin.utente, "oauth": oauth})
    }

    pub async fn impostazioni(&mut self, id: &str, nome_u: &str, ip: &str, op: Op) -> Risposta {
        match op {
            Op::ImpLeggi {} => {
                let mut utenti: Vec<Value> = self
                    .utenti
                    .iter()
                    .map(|(k, v)| {
                        json!({"id": k, "nome": v.name, "account": v.account.clone().unwrap_or_default(),
                               "provider": v.provider.clone().unwrap_or_else(|| "ospite".into()), "avatar": v.avatar.clone().unwrap_or_default(),
                               "master": (v.master_ok || v.admin) && !v.sistema, "admin": v.admin, "sistema": v.sistema, "online": self.clienti.contains_key(k),
                               "visto": v.seen, "io": k == id})
                    })
                    .collect();
                utenti.sort_by(|a, b| b["visto"].as_f64().unwrap_or(0.0).total_cmp(&a["visto"].as_f64().unwrap_or(0.0)));
                let audit = self.db.leggi_audit(200).await.unwrap_or_default();
                Risposta::ok(json!({"ok": true, "config": self.config_pubblica(), "utenti": utenti, "audit": audit}))
            }

            Op::ImpSalva { config: c } => {
                let mut nuovo = self.config.clone(); // si lavora su una copia: se qualcosa non va, la config resta com'era
                let mut cambiati = vec![];
                if let Some(v) = &c.nome_tavolo {
                    nuovo.nome_tavolo = tronca(v.trim(), 200);
                    cambiati.push("nome_tavolo");
                }
                if let Some(v) = &c.password_giocatori {
                    nuovo.password_giocatori = tronca(v.trim(), 200);
                    cambiati.push("password_giocatori");
                }
                if let Some(v) = &c.public_url {
                    match normalizza_url(v) {
                        Some(u) => nuovo.public_url = u,
                        None => return Risposta::no("L'indirizzo pubblico deve essere tipo https://dnd.esempio.it"),
                    }
                    cambiati.push("public_url");
                }
                if let Some(v) = c.ospiti {
                    nuovo.ospiti = v;
                    cambiati.push("ospiti");
                }
                for (prov, conf) in c.oauth.unwrap_or_default() {
                    let Some(p) = PROVIDER.iter().find(|p| p.id == prov) else {
                        continue;
                    };
                    let dest = nuovo.oauth.entry(prov.clone()).or_default();
                    if let Some(a) = conf.attivo {
                        dest.attivo = a;
                    }
                    if let Some(cid) = &conf.id {
                        let mut nuovo_id = tronca(&SPAZI.replace_all(cid, ""), 300);
                        let attivo = conf.attivo.unwrap_or(dest.attivo);
                        if !nuovo_id.is_empty() && !formato_id(&prov).is_match(&nuovo_id) {
                            if attivo {
                                let esempio = match prov.as_str() {
                                    "discord" => "deve contenere solo numeri, es. 1570503076421439708",
                                    "google" => "deve finire con .apps.googleusercontent.com",
                                    _ => "deve essere un codice di lettere e numeri, senza spazi",
                                };
                                return Risposta::no(&format!(
                                    "{}: il Client ID non sembra giusto ({esempio}). Controlla anche che il browser non l'abbia compilato da solo.",
                                    p.nome
                                ));
                            }
                            nuovo_id = dest.id.clone(); // provider spento con un valore strano: si lascia quello di prima
                        }
                        dest.id = nuovo_id;
                    }
                    if let Some(s) = conf.secret.as_ref().filter(|s| !s.is_empty()) {
                        dest.secret = tronca(s.trim(), 300);
                    }
                    if conf.rimuovi_secret {
                        dest.secret.clear();
                    }
                    cambiati.push("oauth");
                }
                self.config = nuovo;
                self.salva_config().await;
                self.invia(Evento::Info);
                self.db
                    .audit(Some(id), Some(nome_u), Some(ip), "imp_salva", &json!({"campi": cambiati}))
                    .await;
                Risposta::ok(json!({"ok": true, "config": self.config_pubblica()}))
            }

            Op::ImpAdmin { attuale, utente, nuova } => {
                let conf = self.config.admin.clone();
                let utente_conf = conf.utente.clone();
                let ok = tokio::task::spawn_blocking(move || crate::password::verifica(&conf, &utente_conf, &attuale).ok)
                    .await
                    .unwrap_or(false);
                if !ok {
                    self.db
                        .audit(Some(id), Some(nome_u), Some(ip), "imp_admin_password_errata", &json!({}))
                        .await;
                    return Risposta::no("la password attuale non è corretta");
                }
                if !nuova.is_empty() && nuova.chars().count() < 8 {
                    return Risposta::no("la nuova password deve avere almeno 8 caratteri");
                }
                let nuovo_utente = tronca(utente.trim(), 40);
                if !nuovo_utente.is_empty() {
                    self.config.admin.utente = nuovo_utente;
                }
                if !nuova.is_empty() {
                    let mut conf = self.config.admin.clone();
                    conf = tokio::task::spawn_blocking(move || {
                        crate::password::imposta(&mut conf, &nuova);
                        conf
                    })
                    .await
                    .unwrap_or(conf_vuota());
                    if conf.argon2.is_some() {
                        self.config.admin = conf;
                    }
                }
                self.salva_config().await;
                self.db
                    .audit(
                        Some(id),
                        Some(nome_u),
                        Some(ip),
                        "imp_admin",
                        &json!({"utente": self.config.admin.utente}),
                    )
                    .await;
                Risposta::si()
            }

            Op::ImpPartite {} => {
                self.salva_ora().await;
                let righe = self.db.partite().await.unwrap_or_default();
                let partite: Vec<Value> = righe
                    .into_iter()
                    .map(|p| {
                        let st = &p.stato;
                        let titolo = self.catalogo.get(&p.avventura).map(Avventura::titolo).unwrap_or(format!("{} (avventura rimossa)", p.avventura));
                        json!({"id": p.avventura, "titolo": titolo, "aggiornata": p.aggiornata,
                               "pedine": st.get("pedine").and_then(Value::as_object).map(|o| o.len()).unwrap_or(0),
                               "tiri": st.get("log").and_then(Value::as_array).map(|l| l.iter().filter(|v| v["tipo"] == "tiro").count()).unwrap_or(0),
                               "round": st.get("iniziativa").and_then(|i| i.get("round")).cloned().unwrap_or(json!(1)),
                               "in_gioco": Some(&p.avventura) == self.attiva.as_ref()})
                    })
                    .collect();
                Risposta::ok(json!({"ok": true, "partite": partite}))
            }

            Op::ImpPartitaAzzera { id: aid } => {
                let attiva = Some(&aid) == self.attiva.as_ref();
                if attiva {
                    let prima = self.catalogo.get(&aid).and_then(|a| a.prima_mappa());
                    self.stato = Stato::vuoto(Some(&aid), prima);
                }
                if let Err(e) = self.db.elimina_partita(&aid).await {
                    tracing::error!(errore = %e, "eliminazione della partita");
                }
                if attiva {
                    self.invia(Evento::Ricarica);
                    self.salva_presto();
                }
                self.db
                    .audit(Some(id), Some(nome_u), Some(ip), "imp_partita_azzera", &json!({"avventura": aid}))
                    .await;
                Risposta::si()
            }

            Op::ImpUtente {
                id: uid,
                elimina,
                master,
                admin,
            } => {
                if !self.utenti.contains_key(&uid) {
                    return Risposta::no("utente inesistente");
                }
                let nome = self.utenti[&uid].name.clone();
                if elimina {
                    if uid == id {
                        return Risposta::no("non puoi eliminare te stesso");
                    }
                    self.account.retain(|_, v| *v != uid);
                    self.utenti.shift_remove(&uid);
                    self.invia_a(Evento::Esci, Some(&uid));
                    self.clienti.remove(&uid); // il browser riceve «esci» e poi lo stream si chiude
                    self.db
                        .audit(
                            Some(id),
                            Some(nome_u),
                            Some(ip),
                            "utente_eliminato",
                            &json!({"utente": uid, "nome": nome}),
                        )
                        .await;
                } else {
                    if let Some(m) = master.filter(|_| !self.utenti[&uid].sistema) {
                        let u = self.utenti.get_mut(&uid).expect("utente");
                        u.master_ok = m;
                        if !m && u.is_master() {
                            u.role = "giocatore".into();
                            self.invia_a(Evento::Ricarica, Some(&uid));
                        }
                    }
                    if let Some(a) = admin {
                        // l'account di sistema resta sempre amministratore (e non si toglie i permessi da solo)
                        if uid != id && !self.utenti[&uid].sistema {
                            let u = self.utenti.get_mut(&uid).expect("utente");
                            u.admin = a;
                            if a {
                                u.master_ok = true;
                            }
                        }
                    }
                    // chi ha appena ricevuto (o perso) un permesso vede subito i pulsanti giusti
                    self.invia_a(Evento::Ricarica, Some(&uid));
                    self.db
                        .audit(
                            Some(id),
                            Some(nome_u),
                            Some(ip),
                            "utente_permessi",
                            &json!({"utente": uid, "nome": nome, "master": master, "admin": admin}),
                        )
                        .await;
                }
                self.online_dopo();
                self.salva_presto();
                Risposta::si()
            }

            _ => Risposta::no("impostazione sconosciuta"),
        }
    }
}

fn conf_vuota() -> crate::modello::AdminConf {
    crate::modello::AdminConf::default()
}

#[cfg(test)]
mod test {
    use super::normalizza_url;

    #[test]
    fn url_pubblico() {
        assert_eq!(
            normalizza_url("Dnd.Esempio.it/percorso/").as_deref(),
            Some("https://dnd.esempio.it")
        );
        assert_eq!(normalizza_url("http://localhost:8000").as_deref(), Some("http://localhost:8000"));
        assert_eq!(normalizza_url("").as_deref(), Some(""));
        assert_eq!(normalizza_url("https://senza punto"), None);
        assert_eq!(normalizza_url("javascript:alert(1)"), None);
    }
}
