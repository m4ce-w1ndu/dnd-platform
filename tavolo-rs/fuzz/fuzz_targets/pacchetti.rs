//! Qualsiasi file caricato come pacchetto avventura: niente panico, niente file fuori dalla cartella.
#![no_main]
use libfuzzer_sys::fuzz_target;

fuzz_target!(|dati: &[u8]| {
    let dir = std::env::temp_dir().join("tavolo-fuzz-pacchetti");
    let _ = std::fs::create_dir_all(&dir);
    if let Ok((_, tmp)) = tavolo::pacchetti::estrai(dati, &dir) {
        assert!(tmp.starts_with(&dir));
        let _ = std::fs::remove_dir_all(tmp);
    }
});
