//! Tavolo Virtuale per D&D: server di gioco (riscrittura in Rust di `tavolo/server.py`).
//!
//! Architettura: un solo task (`tavolo::Tavolo`) possiede tutto lo stato e gestisce i comandi in
//! ordine da una coda; lo strato HTTP (`web`) traduce le richieste in comandi. Vedi CONTRATTO.md.

// Le risposte HTTP di errore viaggiano per valore come in tutto l'ecosistema axum: non sono un collo di bottiglia.
#![allow(clippy::result_large_err)]

pub mod api;
pub mod catalogo;
pub mod comandi;
pub mod contenuti;
pub mod dadi;
pub mod db;
pub mod gioco;
pub mod impostazioni;
pub mod limiti;
pub mod metriche;
pub mod modello;
pub mod oauth;
pub mod pacchetti;
pub mod password;
pub mod permessi;
pub mod tavolo;
pub mod util;
pub mod verifica;
pub mod web;
