//! Qualsiasi corpo di /api/op: la lettura non deve mai andare in panico.
#![no_main]
use libfuzzer_sys::fuzz_target;

fuzz_target!(|dati: &[u8]| {
    if let Ok(v) = serde_json::from_slice::<serde_json::Value>(dati) {
        let _ = tavolo::comandi::leggi(v.clone());
        let _ = serde_json::from_value::<tavolo::modello::Stato>(v);
    }
});
