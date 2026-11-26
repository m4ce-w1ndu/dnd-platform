//! Qualsiasi espressione di dadi.
#![no_main]
use libfuzzer_sys::fuzz_target;

fuzz_target!(|s: &str| {
    let _ = tavolo::dadi::tira(s);
    let _ = tavolo::dadi::raddoppia_dadi(s);
});
