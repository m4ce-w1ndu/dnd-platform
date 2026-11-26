//! I comandi di gioco (`/api/op`). Ogni comando passa prima dalla tabella dei permessi.

use serde_json::{json, Map, Value};

use crate::comandi::{Op, PedinaIn};
use crate::modello::{Iniziativa, Pedina, Stato, Voce, VoceIniziativa};
use crate::permessi::{richiesto, Ruolo};
use crate::tavolo::{Risposta, Tavolo};
use crate::util::{colore_valido, id_casuale, numero, tronca, N};

const MAX_CELLE_NEBBIA: usize = 50_000;
const MAX_PEDINE: usize = 2_000;
const MAX_VOCI_INIZIATIVA: usize = 200;
const MAX_CAMPO_SCHEDA: usize = 64 * 1024;

fn n_valido(v: &Value) -> Option<N> {
    numero(v).map(N)
}

impl Tavolo {
    fn puo_muovere(&self, id: &str, p: &Pedina) -> bool {
        let u = &self.utenti[id];
        u.is_master() || p.proprietario.as_deref() == Some(id) || (p.pg.is_some() && p.pg == u.char)
    }

    pub fn crea_pedina_pg(&mut self, id: &str, pg: &str, colore: &str) {
        let Some(info) = self
            .attiva
            .as_ref()
            .and_then(|a| self.catalogo.get(a))
            .and_then(|a| a.personaggio(pg))
            .cloned()
        else {
            return;
        };
        if let Some(p) = self.stato.pedine.values_mut().find(|p| p.pg.as_deref() == Some(pg)) {
            p.proprietario = Some(id.into());
            p.colore = Some(colore.into());
            let ev = json!({"t": "pedina", "pedina": p});
            self.invia(&ev);
            return;
        }
        let pf_info = info.get("pf").and_then(numero).unwrap_or(10.0);
        let sch = self.stato.schede.entry(pg.to_string()).or_insert_with(|| {
            let mut m = Map::new();
            m.insert("pf".into(), json!(N(pf_info)));
            m
        });
        let pf = sch.get("pf").and_then(numero).unwrap_or(pf_info);
        let n = self.stato.pedine.values().filter(|p| p.pg.is_some()).count();
        let pid = id_casuale(10);
        let s = |k: &str, d: &str| {
            info.get(k)
                .and_then(crate::util::testo)
                .filter(|t| !t.is_empty())
                .unwrap_or_else(|| d.into())
        };
        let p = Pedina {
            id: pid.clone(),
            scena: self.stato.scena.clone(),
            x: None,
            y: None,
            nome: s("nome", "Eroe"),
            colore: Some(colore.into()),
            icona: Some(s("icona", "🙂")),
            taglia: N(1.0),
            pf: Some(N(pf)),
            pfmax: Some(N(pf_info)),
            ca: Some(info.get("ca").cloned().unwrap_or(json!(10))),
            nascosta: false,
            condizioni: vec![],
            tipo: Some("pg".into()),
            pg: Some(pg.into()),
            mostro: None,
            proprietario: Some(id.into()),
            slot: Some(N(n as f64)),
            altro: Map::new(),
        };
        let ev = json!({"t": "pedina", "pedina": p});
        self.stato.pedine.insert(pid, p);
        self.invia(&ev);
        self.salva_presto();
    }

    pub async fn op(&mut self, id: &str, op: Op, ip: &str) -> Risposta {
        let (nome_u, colore_u, ruolo) = {
            let u = &self.utenti[id];
            (u.name.clone(), u.color.clone(), Ruolo::di(u))
        };
        let master = ruolo.master;
        let (chi, msg) = richiesto(&op);
        if !chi.ammette(ruolo) {
            return Risposta::no(msg);
        }
        let master_o_no = |ok: bool, msg: &str| if ok { None } else { Some(Risposta::no(msg)) };

        match op {
            Op::Tira {
                espr,
                etichetta,
                segreto,
                modo,
                danni,
            } => {
                let r = match crate::dadi::tira(&espr) {
                    Ok(r) => r,
                    Err(e) => return Risposta::errore(400, e.0),
                };
                let mut resto = Map::new();
                resto.insert("chi".into(), json!(nome_u));
                resto.insert("colore".into(), json!(colore_u));
                resto.insert("etichetta".into(), json!(tronca(&etichetta, 80)));
                let modo = match modo {
                    Some(Value::String(s)) => json!(tronca(&s, 20)),
                    Some(v @ (Value::Bool(_) | Value::Number(_) | Value::Null)) => v,
                    _ => json!(""),
                };
                resto.insert("modo".into(), modo);
                let critico = r["critico"] == true;
                if let Value::Object(o) = r {
                    resto.extend(o);
                }
                if let Some(d) = danni {
                    let espr2 = if critico { crate::dadi::raddoppia_dadi(&d) } else { d };
                    match crate::dadi::tira(&espr2) {
                        Ok(rd) => {
                            resto.insert("danni".into(), rd);
                        }
                        Err(e) => return Risposta::errore(400, e.0),
                    }
                }
                let voce = Voce {
                    id: String::new(),
                    ora: 0.0,
                    tipo: "tiro".into(),
                    da: Some(id.into()),
                    segreto,
                    resto,
                };
                let v = self.aggiungi_log(voce);
                let mut out = v;
                // come Python: il tiro restituito ha anche segreto:false esplicito
                out["segreto"] = json!(segreto);
                Risposta::ok(json!({"ok": true, "tiro": out}))
            }

            Op::Chat { testo, segreto } => {
                let testo = tronca(testo.trim(), 600);
                if testo.is_empty() {
                    return Risposta::no("");
                }
                let mut resto = Map::new();
                resto.insert("chi".into(), json!(nome_u));
                resto.insert("colore".into(), json!(colore_u));
                resto.insert("testo".into(), json!(testo));
                self.aggiungi_log(Voce {
                    id: String::new(),
                    ora: 0.0,
                    tipo: "chat".into(),
                    da: Some(id.into()),
                    segreto,
                    resto,
                });
                Risposta::si()
            }

            Op::Ping { x, y, centra } => {
                self.invia(&json!({"t": "ping", "x": x, "y": y, "colore": colore_u, "chi": nome_u, "centra": centra && master}));
                Risposta::si()
            }

            Op::Righello { punti } => {
                if punti.as_ref().is_some_and(|p| p.len() > 32) {
                    return Risposta::errore(400, "troppi punti");
                }
                let punti = punti.map(|v| v.into_iter().map(|p| json!({"x": p.x, "y": p.y})).collect::<Vec<_>>());
                self.invia(&json!({"t": "righello", "da": id, "colore": colore_u, "punti": punti}));
                Risposta::si()
            }

            Op::ScegliPg { pg } => {
                let avv = self.attiva.as_ref().and_then(|a| self.catalogo.get(a));
                if let Some(p) = &pg {
                    if !avv.is_some_and(|a| a.ha_personaggio(p)) {
                        return Risposta::no("personaggio inesistente");
                    }
                    if !master && self.pg_occupato(p, id) {
                        return Risposta::no("personaggio già scelto da un altro giocatore");
                    }
                }
                self.utenti.get_mut(id).expect("utente").char = pg.clone();
                if let (Some(p), false) = (&pg, master) {
                    self.crea_pedina_pg(id, p, &colore_u);
                }
                let o = self.online();
                self.invia(&json!({"t": "online", "online": o}));
                self.salva_presto();
                Risposta::si()
            }

            Op::PedinaMuovi { id: pid, x, y, finale } => {
                let pid = pid.unwrap_or_default();
                let ok = self.stato.pedine.get(&pid).is_some_and(|p| self.puo_muovere(id, p));
                if !ok {
                    return Risposta::no("non puoi muovere questa pedina");
                }
                let p = self.stato.pedine.get_mut(&pid).expect("pedina");
                p.x = Some(N(x));
                p.y = Some(N(y));
                let ev = json!({"t": "pedina", "pedina": p, "da": id, "trascina": !finale});
                if finale {
                    self.salva_presto();
                }
                self.invia(&ev);
                Risposta::si()
            }

            Op::PedinaSalva { pedina } => self.pedina_salva(id, master, pedina),

            Op::PedinaElimina { id: pid } => {
                let pid = pid.unwrap_or_default();
                let ok = self
                    .stato
                    .pedine
                    .get(&pid)
                    .is_some_and(|p| master || p.proprietario.as_deref() == Some(id));
                if !ok {
                    return Risposta::no("");
                }
                self.stato.pedine.shift_remove(&pid);
                self.stato.iniziativa.ordine.retain(|x| x.pedina.as_deref() != Some(&pid));
                self.invia(&json!({"t": "pedina_via", "id": pid}));
                let ini = json!({"t": "iniziativa", "iniziativa": self.stato.iniziativa});
                self.invia(&ini);
                self.salva_presto();
                Risposta::si()
            }

            Op::Scheda { id: pg, scheda } => {
                if let Some(r) = master_o_no(master || self.utenti[id].char.as_deref() == Some(&pg), "non è la tua scheda") {
                    return r;
                }
                for (k, v) in &scheda {
                    if ["pf", "pft", "slot", "usi", "note", "condizioni"].contains(&k.as_str()) && v.to_string().len() > MAX_CAMPO_SCHEDA {
                        return Risposta::errore(400, "scheda troppo grande");
                    }
                }
                let sch = self.stato.schede.entry(pg.clone()).or_default();
                for k in ["pf", "pft", "slot", "usi", "note", "condizioni"] {
                    if let Some(v) = scheda.get(k) {
                        sch.insert(k.into(), v.clone());
                    }
                }
                if let Some(Value::String(n)) = sch.get("note") {
                    let t = tronca(n, 5000);
                    sch.insert("note".into(), json!(t));
                }
                let pf = sch.get("pf").cloned();
                let sch = Value::Object(sch.clone());
                let mut cambiate = vec![];
                if let Some(pf) = pf {
                    for p in self.stato.pedine.values_mut() {
                        if p.pg.as_deref() == Some(&pg) {
                            p.pf = n_valido(&pf);
                            cambiate.push(json!({"t": "pedina", "pedina": p}));
                        }
                    }
                }
                for ev in cambiate {
                    self.invia(&ev);
                }
                self.invia(&json!({"t": "scheda", "id": pg, "scheda": sch}));
                self.salva_presto();
                Risposta::si()
            }

            Op::Iniziativa {
                azione,
                nome,
                valore,
                pedina,
                colore,
                nascosta,
                id: vid,
            } => {
                let azione = azione.unwrap_or_default();
                let ini = &mut self.stato.iniziativa;
                match azione.as_str() {
                    "aggiungi" => {
                        if !master {
                            let ok = pedina
                                .as_ref()
                                .is_none_or(|pid| self.stato.pedine.get(pid).is_some_and(|p| self.puo_muovere(id, p)));
                            if !ok {
                                return Risposta::no("non è la tua pedina");
                            }
                        }
                        let ini = &mut self.stato.iniziativa;
                        if ini.ordine.len() >= MAX_VOCI_INIZIATIVA {
                            return Risposta::no("troppe voci di iniziativa");
                        }
                        let voce = VoceIniziativa {
                            id: id_casuale(8),
                            nome: tronca(nome.as_deref().unwrap_or("?"), 40),
                            valore: valore.unwrap_or(0),
                            pedina: pedina.clone(),
                            colore: colore_valido(colore.as_deref(), &colore_u),
                            nascosta: nascosta && master,
                            da: (!master).then(|| id.to_string()),
                            altro: Map::new(),
                        };
                        if let Some(p) = &pedina {
                            ini.ordine.retain(|x| x.pedina.as_deref() != Some(p));
                        }
                        ini.ordine.push(voce);
                        ini.ordine.sort_by_key(|x| std::cmp::Reverse(x.valore));
                    }
                    "prossimo" if !ini.ordine.is_empty() => {
                        ini.turno += 1;
                        if ini.turno >= ini.ordine.len() as i64 {
                            ini.turno = 0;
                            ini.round += 1;
                        }
                    }
                    "precedente" if !ini.ordine.is_empty() => {
                        ini.turno -= 1;
                        if ini.turno < 0 {
                            ini.turno = ini.ordine.len() as i64 - 1;
                            ini.round = (ini.round - 1).max(1);
                        }
                    }
                    "rimuovi" => {
                        ini.ordine.retain(|x| Some(&x.id) != vid.as_ref());
                        ini.turno = ini.turno.min((ini.ordine.len() as i64 - 1).max(0));
                    }
                    "valore" => {
                        for x in ini.ordine.iter_mut() {
                            if Some(&x.id) == vid.as_ref() {
                                x.valore = valore.unwrap_or(0);
                            }
                        }
                        ini.ordine.sort_by_key(|x| std::cmp::Reverse(x.valore));
                    }
                    "svuota" => *ini = Iniziativa::default(),
                    _ => {}
                }
                let ini = self.stato.iniziativa.clone();
                self.invia(&json!({"t": "iniziativa", "iniziativa": ini}));
                if azione == "prossimo" {
                    if let Some(cur) = ini.ordine.get(ini.turno.max(0) as usize) {
                        if !cur.nascosta {
                            self.sistema(&format!("🔔 Round {}: tocca a {}!", ini.round, cur.nome));
                        }
                    }
                }
                self.salva_presto();
                Risposta::si()
            }

            // ------------------------------------------------------------ apertura/chiusura del tavolo
            Op::SessioneApri { id: aid } => {
                let aid = aid.or_else(|| self.attiva.clone()).unwrap_or_default();
                if !self.catalogo.contains_key(&aid) {
                    return Risposta::no("scegli un'avventura");
                }
                if Some(&aid) != self.attiva.as_ref() {
                    self.attiva_avventura(Some(aid.clone())).await;
                }
                self.imposta_sessione("lobby");
                self.invia(&json!({"t": "ricarica"}));
                self.db
                    .audit(Some(id), Some(&nome_u), Some(ip), "sessione_apri", &json!({"avventura": aid}))
                    .await;
                Risposta::si()
            }

            Op::NominaMaster { id: uid, master: diventa } => {
                if !self.utenti.contains_key(&uid) {
                    return Risposta::no("utente inesistente");
                }
                if diventa && self.utenti[&uid].sistema {
                    return Risposta::no("l'account di sistema non può fare il Master");
                }
                let mut toccati = vec![];
                if diventa {
                    for (k, v) in self.utenti.iter_mut() {
                        if *k != uid && v.is_master() {
                            v.role = "giocatore".into();
                            if !v.admin {
                                v.master_ok = false;
                            }
                            toccati.push(k.clone());
                        }
                    }
                    let u = self.utenti.get_mut(&uid).expect("utente");
                    u.role = "master".into();
                    u.master_ok = true;
                    u.char = None;
                } else {
                    let u = self.utenti.get_mut(&uid).expect("utente");
                    u.role = "giocatore".into();
                    if !u.admin {
                        u.master_ok = false;
                    }
                }
                toccati.push(uid.clone());
                for k in &toccati {
                    let r = self.utenti[k].role.clone();
                    self.invia_a(&json!({"t": "ruolo", "ruolo": r}), Some(k));
                }
                let o = self.online();
                self.invia(&json!({"t": "online", "online": o}));
                let nome = self.utenti[&uid].name.clone();
                if diventa {
                    self.sistema(&format!("👑 {nome} sarà il Master."));
                }
                self.salva_presto();
                self.db
                    .audit(
                        Some(id),
                        Some(&nome_u),
                        Some(ip),
                        "nomina_master",
                        &json!({"utente": uid, "nome": nome, "master": diventa}),
                    )
                    .await;
                Risposta::si()
            }

            Op::SessioneInizia {} => {
                self.imposta_sessione("in_corso");
                self.sistema("⚔️ La partita ha inizio!");
                Risposta::si()
            }
            Op::SessionePausa {} => {
                self.imposta_sessione("lobby");
                Risposta::si()
            }
            Op::SessioneChiudi {} => {
                self.salva_ora().await;
                self.imposta_sessione("chiusa");
                Risposta::si()
            }

            // ------------------------------------------------------------ impostazioni (solo admin)
            op @ (Op::ImpLeggi {}
            | Op::ImpSalva { .. }
            | Op::ImpAdmin { .. }
            | Op::ImpPartite {}
            | Op::ImpPartitaAzzera { .. }
            | Op::ImpUtente { .. }) => self.impostazioni(id, &nome_u, ip, op).await,

            // ------------------------------------------------------------ solo Master
            Op::Scena { id: sid, porta_gruppo } => {
                if !self
                    .attiva
                    .as_ref()
                    .and_then(|a| self.catalogo.get(a))
                    .is_some_and(|a| a.ha_mappa(&sid))
                {
                    return Risposta::no("mappa inesistente");
                }
                self.stato.scena = Some(sid.clone());
                let mut mossi = vec![];
                if porta_gruppo {
                    for p in self.stato.pedine.values_mut() {
                        if p.pg.is_some() {
                            p.scena = Some(sid.clone());
                            p.x = None;
                            p.y = None;
                            mossi.push(json!({"t": "pedina", "pedina": p}));
                        }
                    }
                }
                self.invia(&json!({"t": "scena", "id": sid}));
                for ev in mossi {
                    self.invia(&ev);
                }
                self.sistema("🗺️ Il Master ha cambiato mappa.");
                self.salva_presto();
                Risposta::si()
            }

            Op::Nebbia {
                scena,
                attiva,
                azione,
                celle,
            } => {
                let Some(sc) = scena.or_else(|| self.stato.scena.clone()) else {
                    return Risposta::no("nessuna mappa");
                };
                if celle.len() > MAX_CELLE_NEBBIA || celle.iter().any(|c| c.len() > 32) {
                    return Risposta::errore(400, "troppe celle");
                }
                let nb = self.stato.nebbia.entry(sc.clone()).or_default();
                if let Some(a) = attiva {
                    nb.attiva = a;
                }
                let mut insieme: std::collections::BTreeSet<String> = nb.celle.iter().cloned().collect();
                match azione.as_deref() {
                    Some("rivela") => insieme.extend(celle),
                    Some("copri") => {
                        for c in &celle {
                            insieme.remove(c);
                        }
                    }
                    Some("copri_tutto") => insieme.clear(),
                    _ => {}
                }
                if insieme.len() > MAX_CELLE_NEBBIA {
                    return Risposta::errore(400, "troppe celle");
                }
                nb.celle = insieme.into_iter().collect();
                let ev = json!({"t": "nebbia", "scena": sc, "nebbia": nb});
                self.invia(&ev);
                self.salva_presto();
                Risposta::si()
            }

            Op::NoteMaster { testo } => {
                self.stato.note_master = tronca(&testo, 20_000);
                self.salva_presto();
                Risposta::si()
            }

            Op::SvuotaLog {} => {
                self.stato.log.clear();
                self.invia(&json!({"t": "ricarica"}));
                self.salva_presto();
                Risposta::si()
            }

            Op::PulisciScena { scena } => {
                let sc = scena.or_else(|| self.stato.scena.clone());
                let via: Vec<String> = self
                    .stato
                    .pedine
                    .iter()
                    .filter(|(_, p)| p.scena == sc && p.pg.is_none())
                    .map(|(k, _)| k.clone())
                    .collect();
                for k in &via {
                    self.stato.pedine.shift_remove(k);
                }
                for k in via {
                    self.invia(&json!({"t": "pedina_via", "id": k}));
                }
                self.salva_presto();
                Risposta::si()
            }

            Op::ResetPartita {} => {
                let prima = self
                    .attiva
                    .as_ref()
                    .and_then(|a| self.catalogo.get(a))
                    .and_then(|a| a.prima_mappa());
                self.stato = Stato::vuoto(self.attiva.as_deref(), prima);
                self.invia(&json!({"t": "ricarica"}));
                self.salva_presto();
                self.db
                    .audit(
                        Some(id),
                        Some(&nome_u),
                        Some(ip),
                        "reset_partita",
                        &json!({"avventura": self.attiva}),
                    )
                    .await;
                Risposta::si()
            }

            Op::AvventuraAttiva { id: aid } => {
                let Some(titolo) = self.catalogo.get(&aid).map(|a| a.titolo()) else {
                    return Risposta::no("avventura inesistente");
                };
                self.attiva_avventura(Some(aid)).await;
                self.invia(&json!({"t": "ricarica"}));
                self.sistema(&format!("📚 Si gioca: {titolo}"));
                Risposta::si()
            }

            op @ (Op::Griglia { .. }
            | Op::AvventuraNuova { .. }
            | Op::AvventuraInfo { .. }
            | Op::MappaMeta { .. }
            | Op::MappaElimina { .. }
            | Op::DocumentoElimina { .. }
            | Op::AvventuraElimina { .. }) => self.op_avventura(id, &nome_u, ip, op).await,
        }
    }

    fn pedina_salva(&mut self, id: &str, master: bool, d: PedinaIn) -> Risposta {
        let pid = d.id.clone().unwrap_or_default();
        let esiste = self.stato.pedine.contains_key(&pid);
        if esiste {
            if !self.puo_muovere(id, &self.stato.pedine[&pid]) {
                return Risposta::no("non è la tua pedina");
            }
        } else {
            // Solo il Master crea pedine nuove: quelle dei giocatori nascono da scegli_pg.
            if !master {
                return Risposta::no("solo il Master può aggiungere pedine");
            }
            if self.stato.pedine.len() >= MAX_PEDINE {
                return Risposta::no("troppe pedine");
            }
        }
        let condizioni = d.condizioni.clone().map(|c| {
            c.unwrap_or_default()
                .iter()
                .filter_map(crate::util::testo)
                .map(|s| tronca(&s, 20))
                .take(12)
                .collect::<Vec<_>>()
        });
        let p = if esiste {
            let p = self.stato.pedine.get_mut(&pid).expect("pedina");
            if let Some(x) = d.x {
                p.x = x;
            }
            if let Some(y) = d.y {
                p.y = y;
            }
            if let Some(c) = condizioni {
                p.condizioni = c;
            }
            if master {
                applica_master(p, &d);
            } else if let Some(pf) = &d.pf {
                // Il giocatore cambia solo posizione, PF e condizioni della sua pedina.
                let pfmax = p.pfmax.map(|n| n.0).unwrap_or(0.0);
                if pfmax > 0.0 {
                    let v = pf.as_ref().and_then(numero).unwrap_or(0.0).trunc();
                    p.pf = Some(N(v.clamp(0.0, pfmax)));
                }
            }
            p.clone()
        } else {
            let mut p = Pedina {
                id: id_casuale(10),
                scena: self.stato.scena.clone(),
                nome: "Pedina".into(),
                taglia: N(1.0),
                ..Default::default()
            };
            if let Some(x) = d.x {
                p.x = x;
            }
            if let Some(y) = d.y {
                p.y = y;
            }
            if let Some(c) = condizioni {
                p.condizioni = c;
            }
            applica_master(&mut p, &d);
            self.stato.pedine.insert(p.id.clone(), p.clone());
            p
        };
        let mut eventi = vec![];
        if let (Some(pg), Some(pf)) = (&p.pg, p.pf) {
            self.stato.schede.entry(pg.clone()).or_default().insert("pf".into(), json!(pf));
        }
        if let Some(pg) = &p.pg {
            if let Some(sch) = self.stato.schede.get(pg) {
                eventi.push(json!({"t": "scheda", "id": pg, "scheda": sch}));
            }
        }
        eventi.push(json!({"t": "pedina", "pedina": p}));
        for ev in eventi {
            self.invia(&ev);
        }
        self.salva_presto();
        Risposta::ok(json!({"ok": true, "id": p.id}))
    }
}

/// Campi che solo il Master può cambiare (con pulizia: nome ≤40, taglia 0.5–6, colore valido…).
fn applica_master(p: &mut Pedina, d: &PedinaIn) {
    if let Some(n) = &d.nome {
        p.nome = tronca(n, 40);
    }
    if let Some(t) = d.taglia {
        let t = t.map(|n| n.0).filter(|v| *v != 0.0).unwrap_or(1.0);
        p.taglia = N(t.clamp(0.5, 6.0));
    }
    if let Some(s) = &d.scena {
        p.scena = s.clone();
    }
    if let Some(c) = &d.colore {
        p.colore = c.as_ref().map(|c| colore_valido(Some(c), "#c0392b"));
    }
    if let Some(i) = &d.icona {
        p.icona = i.as_ref().map(|i| tronca(i, 16));
    }
    if let Some(pf) = &d.pf {
        p.pf = pf.as_ref().and_then(numero).map(N);
    }
    if let Some(m) = d.pfmax {
        p.pfmax = m;
    }
    if let Some(ca) = &d.ca {
        p.ca = ca.as_ref().and_then(|v| match v {
            Value::Number(_) => Some(v.clone()),
            Value::String(s) => Some(json!(tronca(s, 40))),
            _ => None,
        });
    }
    if let Some(n) = d.nascosta {
        p.nascosta = n;
    }
    for (campo, valore) in [
        (&mut p.tipo, &d.tipo),
        (&mut p.pg, &d.pg),
        (&mut p.mostro, &d.mostro),
        (&mut p.proprietario, &d.proprietario),
    ] {
        if let Some(v) = valore {
            *campo = v.as_ref().map(|s| tronca(s, 60));
        }
    }
    if let Some(s) = d.slot {
        p.slot = s;
    }
}
