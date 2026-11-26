//! Metriche in formato Prometheus (`/metrics`), senza dipendenze esterne.

use std::collections::BTreeMap;
use std::sync::atomic::{AtomicU64, Ordering::Relaxed};
use std::sync::Mutex;
use std::time::{Duration, Instant};

pub struct Metriche {
    avvio: Instant,
    richieste: Mutex<BTreeMap<u16, u64>>,
    ops: Mutex<BTreeMap<&'static str, u64>>,
    comandi: AtomicU64,
    comandi_us: AtomicU64,
    comando_max_us: AtomicU64,
    eventi: AtomicU64,
    clienti: AtomicU64,
    limitati: AtomicU64,
    accessi_falliti: AtomicU64,
    salvataggi: AtomicU64,
    salvataggi_us: AtomicU64,
    errori_salvataggio: AtomicU64,
}

impl Default for Metriche {
    fn default() -> Self {
        Metriche {
            avvio: Instant::now(),
            richieste: Mutex::default(),
            ops: Mutex::default(),
            comandi: AtomicU64::new(0),
            comandi_us: AtomicU64::new(0),
            comando_max_us: AtomicU64::new(0),
            eventi: AtomicU64::new(0),
            clienti: AtomicU64::new(0),
            limitati: AtomicU64::new(0),
            accessi_falliti: AtomicU64::new(0),
            salvataggi: AtomicU64::new(0),
            salvataggi_us: AtomicU64::new(0),
            errori_salvataggio: AtomicU64::new(0),
        }
    }
}

impl Metriche {
    pub fn risposta(&self, status: u16) {
        if let Ok(mut m) = self.richieste.lock() {
            *m.entry(status).or_default() += 1;
        }
    }
    pub fn op(&self, nome: &'static str) {
        if let Ok(mut m) = self.ops.lock() {
            *m.entry(nome).or_default() += 1;
        }
    }
    pub fn comando(&self, d: Duration) {
        let us = d.as_micros() as u64;
        self.comandi.fetch_add(1, Relaxed);
        self.comandi_us.fetch_add(us, Relaxed);
        self.comando_max_us.fetch_max(us, Relaxed);
    }
    pub fn eventi(&self, n: u64) {
        self.eventi.fetch_add(n, Relaxed);
    }
    pub fn clienti(&self, n: usize) {
        self.clienti.store(n as u64, Relaxed);
    }
    pub fn limitato(&self) {
        self.limitati.fetch_add(1, Relaxed);
    }
    pub fn accesso_fallito(&self) {
        self.accessi_falliti.fetch_add(1, Relaxed);
    }
    pub fn salvataggio(&self, d: Duration) {
        self.salvataggi.fetch_add(1, Relaxed);
        self.salvataggi_us.fetch_add(d.as_micros() as u64, Relaxed);
    }
    pub fn errore_salvataggio(&self) {
        self.errori_salvataggio.fetch_add(1, Relaxed);
    }

    pub fn testo(&self) -> String {
        let mut s = String::new();
        let mut riga = |nome: &str, tipo: &str, aiuto: &str, valori: Vec<(String, f64)>| {
            s += &format!("# HELP {nome} {aiuto}\n# TYPE {nome} {tipo}\n");
            for (etichette, v) in valori {
                s += &format!("{nome}{etichette} {v}\n");
            }
        };
        let g = |a: &AtomicU64| a.load(Relaxed) as f64;
        riga("tavolo_uptime_secondi", "gauge", "Secondi dall'avvio", vec![(String::new(), self.avvio.elapsed().as_secs_f64())]);
        let r = self.richieste.lock().map(|m| m.clone()).unwrap_or_default();
        riga("tavolo_risposte_http_totale", "counter", "Risposte HTTP per codice", r.iter().map(|(k, v)| (format!("{{codice=\"{k}\"}}"), *v as f64)).collect());
        let o = self.ops.lock().map(|m| m.clone()).unwrap_or_default();
        riga("tavolo_comandi_op_totale", "counter", "Comandi /api/op eseguiti", o.iter().map(|(k, v)| (format!("{{op=\"{k}\"}}"), *v as f64)).collect());
        riga("tavolo_comandi_tavolo_totale", "counter", "Comandi gestiti dal task del tavolo", vec![(String::new(), g(&self.comandi))]);
        riga("tavolo_comandi_tavolo_secondi_totale", "counter", "Tempo speso nei comandi", vec![(String::new(), g(&self.comandi_us) / 1e6)]);
        riga("tavolo_comando_piu_lento_secondi", "gauge", "Comando più lento dall'avvio", vec![(String::new(), g(&self.comando_max_us) / 1e6)]);
        riga("tavolo_eventi_totale", "counter", "Eventi inviati ai browser", vec![(String::new(), g(&self.eventi))]);
        riga("tavolo_clienti_collegati", "gauge", "Browser collegati allo stream", vec![(String::new(), g(&self.clienti))]);
        riga("tavolo_limitati_totale", "counter", "Richieste rifiutate dai limiti di frequenza", vec![(String::new(), g(&self.limitati))]);
        riga("tavolo_accessi_falliti_totale", "counter", "Password sbagliate", vec![(String::new(), g(&self.accessi_falliti))]);
        riga("tavolo_salvataggi_totale", "counter", "Salvataggi nel database", vec![(String::new(), g(&self.salvataggi))]);
        riga("tavolo_salvataggi_secondi_totale", "counter", "Tempo speso a salvare", vec![(String::new(), g(&self.salvataggi_us) / 1e6)]);
        riga("tavolo_errori_salvataggio_totale", "counter", "Salvataggi non riusciti", vec![(String::new(), g(&self.errori_salvataggio))]);
        s
    }
}
