//! Database SQLite (sqlx): stesso schema del server Python, più il registro di audit.

use std::path::Path;
use std::str::FromStr;

use anyhow::{Context, Result};
use indexmap::IndexMap;
use serde_json::Value;
use sqlx::sqlite::{SqliteConnectOptions, SqliteJournalMode, SqlitePoolOptions, SqliteSynchronous};
use sqlx::{Row, SqlitePool};

use crate::modello::Utente;

#[derive(Clone)]
pub struct Db {
    pub pool: SqlitePool,
}

/// Una partita salvata: id dell'avventura, JSON, ultimo salvataggio.
pub struct Partita {
    pub avventura: String,
    pub stato: Value,
    pub aggiornata: Option<f64>,
}

impl Db {
    pub async fn apri(file: &Path) -> Result<Db> {
        if let Some(d) = file.parent() {
            std::fs::create_dir_all(d)?;
        }
        let opz = SqliteConnectOptions::from_str(&format!("sqlite://{}", file.display()))?
            .create_if_missing(true)
            .journal_mode(SqliteJournalMode::Wal)
            .synchronous(SqliteSynchronous::Normal)
            .busy_timeout(std::time::Duration::from_secs(10))
            .foreign_keys(true);
        let pool = SqlitePoolOptions::new().max_connections(4).connect_with(opz).await.context("apertura del database")?;
        sqlx::migrate!("./migrations").run(&pool).await.context("migrazioni del database")?;
        Ok(Db { pool })
    }

    pub async fn get(&self, chiave: &str) -> Result<Option<Value>> {
        let r = sqlx::query("SELECT valore FROM impostazioni WHERE chiave=?").bind(chiave).fetch_optional(&self.pool).await?;
        Ok(match r {
            Some(r) => Some(serde_json::from_str(&r.get::<String, _>(0))?),
            None => None,
        })
    }

    pub async fn set(&self, chiave: &str, valore: &Value) -> Result<()> {
        sqlx::query("INSERT INTO impostazioni(chiave, valore) VALUES(?,?) ON CONFLICT(chiave) DO UPDATE SET valore=excluded.valore")
            .bind(chiave)
            .bind(serde_json::to_string(valore)?)
            .execute(&self.pool)
            .await?;
        Ok(())
    }

    pub async fn partita(&self, aid: &str) -> Result<Option<Value>> {
        let r = sqlx::query("SELECT stato FROM partite WHERE avventura=?").bind(aid).fetch_optional(&self.pool).await?;
        Ok(match r {
            Some(r) => serde_json::from_str(&r.get::<String, _>(0)).ok(),
            None => None,
        })
    }

    pub async fn partite(&self) -> Result<Vec<Partita>> {
        let righe = sqlx::query("SELECT avventura, stato, aggiornata FROM partite ORDER BY aggiornata DESC").fetch_all(&self.pool).await?;
        Ok(righe
            .into_iter()
            .map(|r| Partita {
                avventura: r.get(0),
                stato: serde_json::from_str(&r.get::<String, _>(1)).unwrap_or(Value::Null),
                aggiornata: r.try_get(2).ok(),
            })
            .collect())
    }

    pub async fn elimina_partita(&self, aid: &str) -> Result<()> {
        sqlx::query("DELETE FROM partite WHERE avventura=?").bind(aid).execute(&self.pool).await?;
        Ok(())
    }

    /// Utenti e account. Le righe con JSON illeggibile vengono segnalate e saltate (mai perse: restano nel DB
    /// finché non si salva, e il salvataggio riscrive solo gli utenti caricati — vedi `salva`).
    pub async fn utenti(&self) -> Result<(IndexMap<String, Utente>, Vec<(String, String)>, Vec<String>)> {
        let mut utenti = IndexMap::new();
        let mut scartati = Vec::new();
        for r in sqlx::query("SELECT id, dati FROM utenti").fetch_all(&self.pool).await? {
            let id: String = r.get(0);
            let dati: String = r.get(1);
            match serde_json::from_str::<Utente>(&dati) {
                Ok(u) => {
                    utenti.insert(id, u);
                }
                Err(e) => {
                    tracing::error!(utente = %id, errore = %e, "utente illeggibile nel database");
                    scartati.push(id);
                }
            }
        }
        let account = sqlx::query("SELECT chiave, utente_id FROM account")
            .fetch_all(&self.pool)
            .await?
            .into_iter()
            .map(|r| (r.get(0), r.get(1)))
            .collect();
        Ok((utenti, account, scartati))
    }

    /// Salvataggio completo in una transazione, come `_salva()` del server Python.
    pub async fn salva(
        &self,
        attiva: Option<&str>,
        utenti: &IndexMap<String, Utente>,
        account: &IndexMap<String, String>,
        partita: Option<(&str, &Value)>,
        intoccabili: &[String],
    ) -> Result<()> {
        let mut tx = self.pool.begin().await?;
        sqlx::query("INSERT INTO impostazioni(chiave, valore) VALUES('attiva', ?) ON CONFLICT(chiave) DO UPDATE SET valore=excluded.valore")
            .bind(serde_json::to_string(&attiva)?)
            .execute(&mut *tx)
            .await?;
        // si cancellano tutti gli utenti tranne quelli che non si sono potuti leggere (li si lascia com'erano)
        let mut q = sqlx::QueryBuilder::<sqlx::Sqlite>::new("DELETE FROM utenti");
        if !intoccabili.is_empty() {
            q.push(" WHERE id NOT IN (");
            let mut sep = q.separated(",");
            for id in intoccabili {
                sep.push_bind(id);
            }
            q.push(")");
        }
        q.build().execute(&mut *tx).await?;
        for (id, u) in utenti {
            sqlx::query("INSERT OR REPLACE INTO utenti(id,nome,account,admin,master,visto,dati) VALUES(?,?,?,?,?,?,?)")
                .bind(id)
                .bind(&u.name)
                .bind(&u.account)
                .bind(i64::from(u.admin))
                .bind(i64::from(u.master_ok || u.admin))
                .bind(u.seen)
                .bind(serde_json::to_string(u)?)
                .execute(&mut *tx)
                .await?;
        }
        sqlx::query("DELETE FROM account").execute(&mut *tx).await?;
        for (k, v) in account {
            sqlx::query("INSERT INTO account VALUES(?,?)").bind(k).bind(v).execute(&mut *tx).await?;
        }
        if let Some((aid, st)) = partita {
            sqlx::query("INSERT INTO partite VALUES(?,?,?) ON CONFLICT(avventura) DO UPDATE SET stato=excluded.stato, aggiornata=excluded.aggiornata")
                .bind(aid)
                .bind(serde_json::to_string(st)?)
                .bind(crate::util::adesso())
                .execute(&mut *tx)
                .await?;
        }
        tx.commit().await?;
        Ok(())
    }

    pub async fn audit(&self, utente: Option<&str>, nome: Option<&str>, ip: Option<&str>, azione: &str, dettagli: &Value) {
        let r = sqlx::query("INSERT INTO audit(ora, utente, nome, ip, azione, dettagli) VALUES(?,?,?,?,?,?)")
            .bind(crate::util::adesso())
            .bind(utente)
            .bind(nome)
            .bind(ip)
            .bind(azione)
            .bind(dettagli.to_string())
            .execute(&self.pool)
            .await;
        if let Err(e) = r {
            tracing::error!(errore = %e, "scrittura del registro di audit");
        }
        tracing::info!(target: "audit", utente, nome, ip, azione, dettagli = %dettagli);
    }

    pub async fn leggi_audit(&self, quanti: i64) -> Result<Vec<Value>> {
        let righe = sqlx::query("SELECT ora, utente, nome, ip, azione, dettagli FROM audit ORDER BY id DESC LIMIT ?")
            .bind(quanti)
            .fetch_all(&self.pool)
            .await?;
        Ok(righe
            .into_iter()
            .map(|r| {
                serde_json::json!({"ora": r.get::<f64, _>(0), "utente": r.get::<Option<String>, _>(1),
                    "nome": r.get::<Option<String>, _>(2), "ip": r.get::<Option<String>, _>(3), "azione": r.get::<String, _>(4),
                    "dettagli": serde_json::from_str::<Value>(&r.get::<String, _>(5)).unwrap_or(Value::Null)})
            })
            .collect())
    }

    /// Copia coerente del database in un file (VACUUM INTO), per il backup.
    pub async fn copia_in(&self, dest: &Path) -> Result<()> {
        let _ = std::fs::remove_file(dest);
        sqlx::query("VACUUM INTO ?").bind(dest.to_string_lossy().to_string()).execute(&self.pool).await?;
        Ok(())
    }

    pub async fn chiudi(&self) {
        self.pool.close().await;
    }
}
