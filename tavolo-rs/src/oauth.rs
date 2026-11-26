//! Accesso con Discord, Google e GitHub (OAuth 2, con PKCE per Google e Discord).

use std::time::Duration;

use base64::Engine;
use serde_json::Value;
use sha2::{Digest, Sha256};

pub struct Provider {
    pub id: &'static str,
    pub nome: &'static str,
    pub auth: &'static str,
    pub token: &'static str,
    pub utente: &'static str,
    pub scope: &'static str,
    pub console: &'static str,
    pub pkce: bool,
}

pub static PROVIDER: &[Provider] = &[
    Provider {
        id: "discord",
        nome: "Discord",
        auth: "https://discord.com/oauth2/authorize",
        token: "https://discord.com/api/oauth2/token",
        utente: "https://discord.com/api/users/@me",
        scope: "identify",
        console: "https://discord.com/developers/applications",
        pkce: true,
    },
    Provider {
        id: "google",
        nome: "Google",
        auth: "https://accounts.google.com/o/oauth2/v2/auth",
        token: "https://oauth2.googleapis.com/token",
        utente: "https://openidconnect.googleapis.com/v1/userinfo",
        scope: "openid email profile",
        console: "https://console.cloud.google.com/apis/credentials",
        pkce: true,
    },
    Provider {
        id: "github",
        nome: "GitHub",
        auth: "https://github.com/login/oauth/authorize",
        token: "https://github.com/login/oauth/access_token",
        utente: "https://api.github.com/user",
        scope: "read:user",
        console: "https://github.com/settings/developers",
        pkce: false,
    },
];

/// Tutto ciò che serve per scambiare il codice (preso dal tavolo, usato fuori dal task).
pub struct Scambio {
    pub provider: &'static Provider,
    pub client_id: String,
    pub client_secret: String,
    pub verifier: String,
    pub redirect: String,
}

fn q(s: &str) -> String {
    urlencoding::encode(s).into_owned()
}

pub fn url_autorizzazione(p: &Provider, client_id: &str, redirect: &str, state: &str, verifier: &str) -> String {
    let mut parti = vec![
        ("response_type", "code".to_string()),
        ("client_id", client_id.to_string()),
        ("redirect_uri", redirect.to_string()),
        ("scope", p.scope.to_string()),
        ("state", state.to_string()),
    ];
    if p.pkce {
        let sfida = base64::engine::general_purpose::URL_SAFE_NO_PAD.encode(Sha256::digest(verifier.as_bytes()));
        parti.push(("code_challenge", sfida));
        parti.push(("code_challenge_method", "S256".into()));
    }
    if p.id == "google" {
        parti.push(("prompt", "select_account".into()));
    }
    let qs: Vec<String> = parti.iter().map(|(k, v)| format!("{k}={}", q(v))).collect();
    format!("{}?{}", p.auth, qs.join("&"))
}

/// Dati dell'utente restituiti dal provider: (uid, nome, avatar).
pub async fn completa(s: &Scambio, codice: &str) -> Result<(String, String, String), String> {
    let p = s.provider;
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(15))
        .user_agent("TavoloVirtuale/3.0")
        .build()
        .map_err(|e| e.to_string())?;
    let mut form = vec![
        ("grant_type", "authorization_code".to_string()),
        ("code", codice.to_string()),
        ("redirect_uri", s.redirect.clone()),
        ("client_id", s.client_id.clone()),
        ("client_secret", s.client_secret.clone()),
    ];
    if p.pkce {
        form.push(("code_verifier", s.verifier.clone()));
    }
    let r = client
        .post(p.token)
        .header("Accept", "application/json")
        .form(&form)
        .send()
        .await
        .map_err(|e| format!("Impossibile contattare {}: {}", p.nome, e.without_url()))?;
    if !r.status().is_success() {
        return Err(format!(
            "{} ha rifiutato il codice (HTTP {}): controlla Client ID, Secret e Redirect URI.",
            p.nome,
            r.status().as_u16()
        ));
    }
    let tok: Value = r.json().await.map_err(|_| "Risposta non valida dal provider.".to_string())?;
    let Some(access) = tok.get("access_token").and_then(Value::as_str) else {
        return Err("Il provider ha rifiutato l'accesso.".into());
    };
    let u: Value = client
        .get(p.utente)
        .header("Accept", "application/json")
        .bearer_auth(access)
        .send()
        .await
        .map_err(|e| format!("Impossibile contattare {}: {}", p.nome, e.without_url()))?
        .json()
        .await
        .map_err(|_| "Risposta non valida dal provider.".to_string())?;
    let s = |k: &str| u.get(k).and_then(crate::util::testo).filter(|v| !v.is_empty());
    let (uid, nome, avatar) = match p.id {
        "discord" => {
            let id = s("id").ok_or("Risposta di Discord senza id.")?;
            let avatar = s("avatar")
                .map(|a| format!("https://cdn.discordapp.com/avatars/{id}/{a}.png?size=64"))
                .unwrap_or_default();
            let nome = s("global_name").or_else(|| s("username")).unwrap_or_default();
            (id, nome, avatar)
        }
        "google" => {
            let id = s("email").or_else(|| s("sub")).ok_or("Risposta di Google senza id.")?;
            (
                id,
                s("given_name").or_else(|| s("name")).unwrap_or_default(),
                s("picture").unwrap_or_default(),
            )
        }
        _ => {
            let id = s("id").ok_or("Risposta di GitHub senza id.")?;
            (
                id,
                s("name").or_else(|| s("login")).unwrap_or_default(),
                s("avatar_url").unwrap_or_default(),
            )
        }
    };
    // l'avatar finisce in un <img src>: solo https
    let avatar = if avatar.starts_with("https://") && avatar.len() < 500 {
        avatar
    } else {
        String::new()
    };
    Ok((uid, nome, avatar))
}

/// Pagina che salva le credenziali nel browser e torna al tavolo (stessa del server Python).
pub fn pagina_accesso(id: &str, secret: &str, nome: &str, account: &str, nonce: &str) -> String {
    let dati = serde_json::json!({"id": id, "secret": secret, "nome": nome, "account": account}).to_string();
    // dentro <script>: niente «<», «>» o «&» letterali (un nome come «</script>» non può chiudere il tag)
    let dati = dati.replace('<', "\\u003c").replace('>', "\\u003e").replace('&', "\\u0026");
    format!(
        "<!doctype html><meta charset=\"utf-8\"><title>Accesso</title><script nonce=\"{nonce}\">\n\
         try{{const v=JSON.parse(localStorage.getItem(\"tv_cred\")||\"{{}}\");localStorage.setItem(\"tv_cred\",JSON.stringify(Object.assign(v,{dati},{{oauth:true}})))}}catch(e){{}}\n\
         location.replace(\"/?accesso=1\");</script>"
    )
}

pub fn pagina_errore(msg: &str) -> String {
    let m: String = crate::util::tronca(msg, 200)
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;");
    format!("<!doctype html><meta charset=\"utf-8\"><p style=\"font:16px sans-serif\">⚠️ {m}</p><p><a href=\"/\">Torna al tavolo</a></p>")
}
