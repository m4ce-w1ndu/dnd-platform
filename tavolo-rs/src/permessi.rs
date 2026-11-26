//! Chi può fare cosa: UNA tabella per tutti i comandi (vedi REGOLE.md).
//!
//! La logica di gioco consulta `richiesto()` prima di eseguire qualsiasi comando. Per le operazioni
//! sulle pedine il livello `Proprietario` delega il controllo fine (di chi è la pedina) al comando.

use crate::comandi::Op;

/// Livello richiesto per un comando.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Chi {
    /// Chiunque sia seduto al tavolo (ospiti e account hanno gli stessi poteri).
    Tutti,
    /// Il proprietario della pedina/scheda in questione, oppure il Master.
    Proprietario,
    /// Solo il Master della partita.
    Master,
    /// Il Master oppure un amministratore del tavolo.
    MasterOAdmin,
    /// Un amministratore del tavolo (possono essere tanti; uno di loro può anche fare il Master).
    Admin,
    /// Solo l'account di sistema «Admin»: impostazioni, permessi, backup. Non gioca e non apre il tavolo.
    Sistema,
}

/// Il ruolo di chi manda il comando.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct Ruolo {
    /// È il Master della partita.
    pub master: bool,
    /// È un amministratore del tavolo (mai vero per l'account di sistema).
    pub admin: bool,
    /// È l'account di sistema (utente e password dell'admin).
    pub sistema: bool,
}

impl Ruolo {
    pub fn di(u: &crate::modello::Utente) -> Ruolo {
        Ruolo {
            master: u.is_master() && !u.sistema,
            admin: u.admin && !u.sistema,
            sistema: u.sistema,
        }
    }
}

impl Chi {
    /// `true` se il ruolo supera il controllo di livello (il controllo del proprietario resta al comando).
    pub fn ammette(self, r: Ruolo) -> bool {
        match self {
            // l'account di sistema non gioca: niente dadi, chat, pedine
            Chi::Tutti | Chi::Proprietario => !r.sistema,
            Chi::Master => r.master,
            Chi::MasterOAdmin => r.master || r.admin,
            Chi::Admin => r.admin,
            Chi::Sistema => r.sistema,
        }
    }
}

/// La tabella: livello richiesto e messaggio di rifiuto per ogni comando.
pub fn richiesto(op: &Op) -> (Chi, &'static str) {
    use Chi::*;
    match op {
        Op::Tira { .. } | Op::Chat { .. } | Op::Ping { .. } | Op::Righello { .. } | Op::ScegliPg { .. } => (Tutti, ""),
        Op::PedinaMuovi { .. } => (Proprietario, "non puoi muovere questa pedina"),
        Op::PedinaSalva { .. } => (Proprietario, "non è la tua pedina"),
        Op::PedinaElimina { .. } => (Proprietario, "non è la tua pedina"),
        Op::Scheda { .. } => (Proprietario, "non è la tua scheda"),
        Op::Iniziativa { azione, .. } if azione.as_deref() == Some("aggiungi") => (Proprietario, "non è la tua pedina"),
        Op::Iniziativa { .. } => (Master, "solo il Master gestisce i turni"),
        Op::SessioneApri { .. } => (Admin, "il tavolo lo apre un amministratore del tavolo (non l'account di sistema)"),
        Op::NominaMaster { .. } => (
            Admin,
            "il Master lo sceglie un amministratore del tavolo (non l'account di sistema)",
        ),
        Op::SessioneInizia {} => (MasterOAdmin, "solo il Master fa iniziare la partita"),
        Op::SessionePausa {} => (Master, "solo il Master mette in pausa"),
        Op::SessioneChiudi {} => (MasterOAdmin, "solo un amministratore o il Master chiudono il tavolo"),
        Op::ImpLeggi {}
        | Op::ImpSalva { .. }
        | Op::ImpAdmin { .. }
        | Op::ImpPartite {}
        | Op::ImpPartitaAzzera { .. }
        | Op::ImpUtente { .. } => (Sistema, "impostazioni e permessi si cambiano solo dall'account di sistema «Admin»"),
        Op::Scena { .. }
        | Op::Griglia { .. }
        | Op::Nebbia { .. }
        | Op::NoteMaster { .. }
        | Op::SvuotaLog {}
        | Op::PulisciScena { .. }
        | Op::ResetPartita {}
        | Op::AvventuraAttiva { .. }
        | Op::AvventuraNuova { .. }
        | Op::AvventuraInfo { .. }
        | Op::MappaMeta { .. }
        | Op::MappaElimina { .. }
        | Op::DocumentoElimina { .. }
        | Op::AvventuraElimina { .. } => (Master, "solo il Master può farlo"),
    }
}

/// Endpoint HTTP fuori da `/api/op`.
pub mod endpoint {
    use super::Chi;
    pub const CARICA: Chi = Chi::Master; // carica_avventura, carica_mappa, carica_documento
    pub const SCARICA_AVVENTURA: Chi = Chi::Master;
    pub const ESPORTA: Chi = Chi::Master;
    pub const IMPORTA: Chi = Chi::Master;
    pub const BACKUP: Chi = Chi::Sistema;
    pub const AUDIT: Chi = Chi::Sistema;
    pub const DOCUMENTO_RISERVATO: Chi = Chi::Master;
}

#[cfg(test)]
mod test {
    use super::*;
    use crate::comandi::{leggi, Lettura, NOMI};
    use serde_json::json;

    const G: Ruolo = Ruolo {
        master: false,
        admin: false,
        sistema: false,
    };
    const M: Ruolo = Ruolo {
        master: true,
        admin: false,
        sistema: false,
    };
    const A: Ruolo = Ruolo {
        master: false,
        admin: true,
        sistema: false,
    };
    const MA: Ruolo = Ruolo {
        master: true,
        admin: true,
        sistema: false,
    };
    const S: Ruolo = Ruolo {
        master: false,
        admin: false,
        sistema: true,
    };

    fn op(nome: &str, extra: serde_json::Value) -> Op {
        let mut v = json!({"op": nome, "x": 0, "y": 0, "id": "x"});
        for (k, val) in extra.as_object().unwrap() {
            v[k] = val.clone();
        }
        match leggi(v) {
            Lettura::Ok(o) => *o,
            _ => panic!("{nome}"),
        }
    }

    /// La matrice attesa, scritta a mano da REGOLE.md:
    /// (comando, giocatore, Master, admin del tavolo non-Master, account di sistema).
    /// «P» = passa il controllo di livello ma decide il comando (proprietario).
    const ATTESA: &[(&str, &str, bool, bool, bool)] = &[
        ("tira", "si", true, true, false),
        ("chat", "si", true, true, false),
        ("ping", "si", true, true, false),
        ("righello", "si", true, true, false),
        ("scegli_pg", "si", true, true, false),
        ("pedina_muovi", "P", true, true, false),
        ("pedina_salva", "P", true, true, false),
        ("pedina_elimina", "P", true, true, false),
        ("scheda", "P", true, true, false),
        ("iniziativa", "no", true, false, false),
        ("sessione_apri", "no", false, true, false),
        ("nomina_master", "no", false, true, false),
        ("sessione_inizia", "no", true, true, false),
        ("sessione_pausa", "no", true, false, false),
        ("sessione_chiudi", "no", true, true, false),
        ("imp_leggi", "no", false, false, true),
        ("imp_salva", "no", false, false, true),
        ("imp_admin", "no", false, false, true),
        ("imp_partite", "no", false, false, true),
        ("imp_partita_azzera", "no", false, false, true),
        ("imp_utente", "no", false, false, true),
        ("scena", "no", true, false, false),
        ("griglia", "no", true, false, false),
        ("nebbia", "no", true, false, false),
        ("note_master", "no", true, false, false),
        ("svuota_log", "no", true, false, false),
        ("pulisci_scena", "no", true, false, false),
        ("reset_partita", "no", true, false, false),
        ("avventura_attiva", "no", true, false, false),
        ("avventura_nuova", "no", true, false, false),
        ("avventura_info", "no", true, false, false),
        ("mappa_meta", "no", true, false, false),
        ("mappa_elimina", "no", true, false, false),
        ("documento_elimina", "no", true, false, false),
        ("avventura_elimina", "no", true, false, false),
    ];

    #[test]
    fn ogni_comando_per_ogni_ruolo() {
        assert_eq!(ATTESA.len(), NOMI.len(), "ogni comando deve avere una riga nella matrice");
        for &(nome, giocatore, master, admin, sistema) in ATTESA {
            assert!(NOMI.contains(&nome), "{nome}");
            let (chi, msg) = richiesto(&op(nome, json!({})));
            let g = chi.ammette(G);
            match giocatore {
                "si" => assert!(g && chi == Chi::Tutti, "{nome}: il giocatore dovrebbe potere"),
                "P" => assert!(g && chi == Chi::Proprietario, "{nome}: serve il controllo del proprietario"),
                _ => assert!(!g, "{nome}: il giocatore NON dovrebbe potere"),
            }
            assert_eq!(chi.ammette(M), master, "{nome} Master");
            assert_eq!(chi.ammette(A), admin, "{nome} admin");
            assert_eq!(chi.ammette(S), sistema, "{nome} account di sistema");
            if !nome.starts_with("imp_") {
                assert!(chi.ammette(MA), "{nome}: admin+Master può tutto il gioco");
            }
            if !g {
                assert!(!msg.is_empty(), "{nome}: manca il messaggio di rifiuto");
            }
        }
    }

    #[test]
    fn sistema_non_gioca_e_non_apre() {
        for nome in [
            "sessione_apri",
            "nomina_master",
            "sessione_inizia",
            "sessione_chiudi",
            "scena",
            "iniziativa",
            "reset_partita",
        ] {
            assert!(!richiesto(&op(nome, json!({}))).0.ammette(S), "{nome}");
        }
        for nome in [
            "imp_leggi",
            "imp_salva",
            "imp_utente",
            "imp_admin",
            "imp_partite",
            "imp_partita_azzera",
        ] {
            assert!(!richiesto(&op(nome, json!({}))).0.ammette(MA), "{nome}: solo il sistema");
        }
    }

    #[test]
    fn iniziativa_aggiungi_e_turni() {
        assert_eq!(richiesto(&op("iniziativa", json!({"azione": "aggiungi"}))).0, Chi::Proprietario);
        for a in ["prossimo", "precedente", "rimuovi", "valore", "svuota", "boh"] {
            assert_eq!(richiesto(&op("iniziativa", json!({"azione": a}))).0, Chi::Master, "{a}");
        }
    }
}
