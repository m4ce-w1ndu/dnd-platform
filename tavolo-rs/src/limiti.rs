//! Limiti di frequenza (token bucket, crate `governor`): stessi ritmi del server Python.
//!
//! - accessi (`/api/login`, `/api/entra`): 2 al secondo per IP, raffica 10
//! - comandi normali: 5 al secondo per utente, raffica 15
//! - trascinamenti (`pedina_muovi`, `righello`): 20 al secondo per utente, raffica 30
//!
//! In più `web.rs` applica un tetto generale per IP con `tower_governor`.

use std::num::NonZeroU32;
use std::sync::Arc;

use governor::{DefaultKeyedRateLimiter, Quota, RateLimiter};

fn quota(al_secondo: u32, raffica: u32) -> Quota {
    Quota::per_second(NonZeroU32::new(al_secondo).unwrap()).allow_burst(NonZeroU32::new(raffica).unwrap())
}

pub struct Limiti {
    normale: DefaultKeyedRateLimiter<String>,
    veloce: DefaultKeyedRateLimiter<String>,
}

impl Limiti {
    pub fn nuovi() -> Limiti {
        Limiti {
            normale: RateLimiter::keyed(quota(5, 15)),
            veloce: RateLimiter::keyed(quota(20, 30)),
        }
    }

    /// `true` se il comando va rifiutato (troppo frequente).
    pub fn op(&mut self, utente: &str, veloce: bool) -> bool {
        let l = if veloce { &self.veloce } else { &self.normale };
        if l.len() > 5000 {
            l.retain_recent();
        }
        l.check_key(&utente.to_string()).is_err()
    }
}

/// Limite per gli accessi, condiviso tra le richieste HTTP.
#[derive(Clone)]
pub struct LimiteAccessi(Arc<DefaultKeyedRateLimiter<String>>);

impl LimiteAccessi {
    pub fn nuovo() -> LimiteAccessi {
        LimiteAccessi(Arc::new(RateLimiter::keyed(quota(2, 10))))
    }

    pub fn troppi(&self, ip: &str) -> bool {
        if self.0.len() > 5000 {
            self.0.retain_recent();
        }
        self.0.check_key(&ip.to_string()).is_err()
    }
}

#[cfg(test)]
mod test {
    use super::*;

    #[test]
    fn raffica_poi_blocco() {
        let mut l = Limiti::nuovi();
        let passati = (0..30).filter(|_| !l.op("u", false)).count();
        assert!((15..=16).contains(&passati), "{passati}");
        assert!(!l.op("altro", false), "ogni utente ha il suo secchio");
        let veloci = (0..30).filter(|_| !l.op("u", true)).count();
        assert!(veloci >= 30, "{veloci}");
        let a = LimiteAccessi::nuovo();
        assert_eq!((0..20).filter(|_| !a.troppi("1.2.3.4")).count(), 10);
    }
}
