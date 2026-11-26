//! Password dell'amministratore: Argon2id, con lettura del vecchio PBKDF2 del server Python.
//!
//! Durante la transizione si tiene anche l'hash PBKDF2 aggiornato, così un eventuale ritorno al server
//! Python accetta la stessa password. Le funzioni sono lente di proposito: chiamarle con `spawn_blocking`.

use argon2::password_hash::{PasswordHash, PasswordHasher, PasswordVerifier, SaltString};
use argon2::Argon2;
use rand::rngs::OsRng;
use rand::RngCore;
use sha2::Sha256;

use crate::modello::AdminConf;
use crate::util::uguali;

const ITERAZIONI_PBKDF2: u32 = 200_000;

fn pbkdf2_hex(pw: &str, sale_hex: &str) -> Option<String> {
    let sale = hex::decode(sale_hex).ok()?;
    let mut out = [0u8; 32];
    pbkdf2::pbkdf2_hmac::<Sha256>(pw.as_bytes(), &sale, ITERAZIONI_PBKDF2, &mut out);
    Some(hex::encode(out))
}

/// Esito della verifica: se va bene e manca l'hash Argon2, `aggiorna` contiene quello nuovo da salvare.
pub struct Verifica {
    pub ok: bool,
    pub aggiorna: Option<String>,
}

pub fn verifica(conf: &AdminConf, utente: &str, pw: &str) -> Verifica {
    let no = Verifica { ok: false, aggiorna: None };
    if pw.is_empty() {
        return no;
    }
    let ok_utente = uguali(&utente.trim().to_lowercase(), &conf.utente.to_lowercase());
    if let Some(h) = &conf.argon2 {
        let Ok(parsed) = PasswordHash::new(h) else { return no };
        let ok_pw = Argon2::default().verify_password(pw.as_bytes(), &parsed).is_ok();
        return Verifica {
            ok: ok_utente && ok_pw,
            aggiorna: None,
        };
    }
    if let (Some(sale), Some(hash)) = (&conf.sale, &conf.hash) {
        let ok_pw = pbkdf2_hex(pw, sale).is_some_and(|h| uguali(&h, hash));
        let ok = ok_utente && ok_pw;
        return Verifica {
            ok,
            aggiorna: ok.then(|| argon2(pw)),
        };
    }
    no
}

pub fn argon2(pw: &str) -> String {
    let sale = SaltString::generate(&mut OsRng);
    Argon2::default()
        .hash_password(pw.as_bytes(), &sale)
        .expect("hash argon2")
        .to_string()
}

/// Imposta una nuova password: Argon2id + PBKDF2 compatibile con il server Python.
pub fn imposta(conf: &mut AdminConf, pw: &str) {
    let mut sale = [0u8; 16];
    OsRng.fill_bytes(&mut sale);
    let sale = hex::encode(sale);
    conf.hash = pbkdf2_hex(pw, &sale);
    conf.sale = Some(sale);
    conf.argon2 = Some(argon2(pw));
}

#[cfg(test)]
mod test {
    use super::*;

    #[test]
    fn vecchio_hash_python() {
        // generato con: hashlib.pbkdf2_hmac("sha256", b"segreta", bytes.fromhex("00112233445566778899aabbccddeeff"), 200000).hex()
        let mut c = AdminConf {
            utente: "admin".into(),
            sale: Some("00112233445566778899aabbccddeeff".into()),
            hash: Some("9329637742a6942602a3e2908405db6b4fe9547a4de51cc04dd9332258428091".into()),
            argon2: None,
        };
        let v = verifica(&c, " Admin ", "segreta");
        assert!(v.ok);
        assert!(v.aggiorna.is_some());
        assert!(!verifica(&c, "admin", "sbagliata").ok);
        assert!(!verifica(&c, "altro", "segreta").ok);
        c.argon2 = v.aggiorna;
        let v2 = verifica(&c, "admin", "segreta");
        assert!(v2.ok && v2.aggiorna.is_none());
        assert!(!verifica(&c, "admin", "").ok);
    }

    #[test]
    fn nuova_password() {
        let mut c = AdminConf {
            utente: "capo".into(),
            ..Default::default()
        };
        imposta(&mut c, "password-nuova");
        assert!(verifica(&c, "capo", "password-nuova").ok);
        // l'hash PBKDF2 è aggiornato anche lui (ritorno al server Python)
        c.argon2 = None;
        assert!(verifica(&c, "capo", "password-nuova").ok);
    }
}
