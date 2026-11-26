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
    /// Il Master oppure l'amministratore.
    MasterOAdmin,
    /// Solo l'amministratore.
    Admin,
}

/// Il ruolo di chi manda il comando.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Ruolo {
    pub master: bool,
    pub admin: bool,
}

impl Chi {
    /// `true` se il ruolo supera il controllo di livello (il controllo del proprietario resta al comando).
    pub fn ammette(self, r: Ruolo) -> bool {
        match self {
            Chi::Tutti | Chi::Proprietario => true,
            Chi::Master => r.master,
            Chi::MasterOAdmin => r.master || r.admin,
            Chi::Admin => r.admin,
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
        Op::SessioneApri { .. } => (Admin, "solo l'amministratore apre il tavolo"),
        Op::NominaMaster { .. } => (Admin, "solo l'amministratore sceglie il Master"),
        Op::SessioneInizia {} => (MasterOAdmin, "solo il Master fa iniziare la partita"),
        Op::SessionePausa {} => (Master, "solo il Master mette in pausa"),
        Op::SessioneChiudi {} => (MasterOAdmin, "solo admin o Master chiudono il tavolo"),
        Op::ImpLeggi {}
        | Op::ImpSalva { .. }
        | Op::ImpAdmin { .. }
        | Op::ImpPartite {}
        | Op::ImpPartitaAzzera { .. }
        | Op::ImpUtente { .. } => (Admin, "solo l'amministratore può cambiare le impostazioni"),
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
    pub const BACKUP: Chi = Chi::Admin;
    pub const DOCUMENTO_RISERVATO: Chi = Chi::Master;
}

#[cfg(test)]
mod test {
    use super::*;
    use crate::comandi::{leggi, Lettura, NOMI};
    use serde_json::json;

    const G: Ruolo = Ruolo { master: false, admin: false };
    const M: Ruolo = Ruolo { master: true, admin: false };
    const A: Ruolo = Ruolo { master: false, admin: true };
    const MA: Ruolo = Ruolo { master: true, admin: true };

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

    /// La matrice attesa, scritta a mano da REGOLE.md: (comando, giocatore, Master, admin non-Master).
    /// «P» = passa il controllo di livello ma decide il comando (proprietario).
    const ATTESA: &[(&str, &str, bool, bool)] = &[
        ("tira", "si", true, true),
        ("chat", "si", true, true),
        ("ping", "si", true, true),
        ("righello", "si", true, true),
        ("scegli_pg", "si", true, true),
        ("pedina_muovi", "P", true, true),
        ("pedina_salva", "P", true, true),
        ("pedina_elimina", "P", true, true),
        ("scheda", "P", true, true),
        ("iniziativa", "no", true, false),
        ("sessione_apri", "no", false, true),
        ("nomina_master", "no", false, true),
        ("sessione_inizia", "no", true, true),
        ("sessione_pausa", "no", true, false),
        ("sessione_chiudi", "no", true, true),
        ("imp_leggi", "no", false, true),
        ("imp_salva", "no", false, true),
        ("imp_admin", "no", false, true),
        ("imp_partite", "no", false, true),
        ("imp_partita_azzera", "no", false, true),
        ("imp_utente", "no", false, true),
        ("scena", "no", true, false),
        ("griglia", "no", true, false),
        ("nebbia", "no", true, false),
        ("note_master", "no", true, false),
        ("svuota_log", "no", true, false),
        ("pulisci_scena", "no", true, false),
        ("reset_partita", "no", true, false),
        ("avventura_attiva", "no", true, false),
        ("avventura_nuova", "no", true, false),
        ("avventura_info", "no", true, false),
        ("mappa_meta", "no", true, false),
        ("mappa_elimina", "no", true, false),
        ("documento_elimina", "no", true, false),
        ("avventura_elimina", "no", true, false),
    ];

    #[test]
    fn ogni_comando_per_ogni_ruolo() {
        assert_eq!(ATTESA.len(), NOMI.len(), "ogni comando deve avere una riga nella matrice");
        for &(nome, giocatore, master, admin) in ATTESA {
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
            assert!(chi.ammette(MA), "{nome}: admin+Master può tutto");
            if !g {
                assert!(!msg.is_empty(), "{nome}: manca il messaggio di rifiuto");
            }
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
