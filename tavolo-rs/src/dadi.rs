//! Tiri di dadi: «2d20kh1+5», «1d8+3+1d6», «d%». Stesse regole e stessi limiti del server Python.

use std::sync::LazyLock;

use rand::Rng;
use regex::Regex;
use serde_json::{json, Value};

static DADI_RE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?i)([+-]?)\s*(?:(\d*)d(\d+|%)(?:(kh|kl)(\d+))?|(\d+))").unwrap());
static DANNI_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"(\d*)d(\d+)").unwrap());

#[derive(Debug, PartialEq)]
pub struct Errore(pub &'static str);

/// Tira un'espressione; restituisce `{espr, parti, totale, critico, fallimento}`.
pub fn tira(espr: &str) -> Result<Value, Errore> {
    tira_con(espr, &mut rand::rngs::OsRng)
}

pub fn tira_con(espr: &str, rng: &mut impl Rng) -> Result<Value, Errore> {
    let s: String = espr.replace(' ', "").to_lowercase();
    if s.is_empty() || s.chars().count() > 120 {
        return Err(Errore("espressione non valida"));
    }
    let (mut pos, mut parti, mut totale, mut dadi_tot) = (0usize, Vec::new(), 0i64, 0u32);
    let (mut nat20, mut nat1) = (false, false);
    for m in DADI_RE.captures_iter(&s) {
        let intero = m.get(0).unwrap();
        if intero.start() != pos {
            return Err(Errore("espressione non valida"));
        }
        pos = intero.end();
        let segno: i64 = if m.get(1).map(|g| g.as_str()) == Some("-") { -1 } else { 1 };
        if let Some(num) = m.get(6) {
            let v: i64 = num.as_str().parse().map_err(|_| Errore("numero troppo grande"))?;
            if v > 1_000_000 {
                return Err(Errore("numero troppo grande"));
            }
            parti.push(json!({"tipo": "num", "valore": v * segno}));
            totale += v * segno;
            continue;
        }
        let n: u32 = match m.get(2).map(|g| g.as_str()).filter(|g| !g.is_empty()) {
            Some(g) => g.parse().map_err(|_| Errore("troppi dadi"))?,
            None => 1,
        };
        let facce: u32 = match m.get(3).unwrap().as_str() {
            "%" => 100,
            f => f.parse().map_err(|_| Errore("troppi dadi"))?,
        };
        if !(1..=100).contains(&n) || !(2..=1000).contains(&facce) {
            return Err(Errore("troppi dadi"));
        }
        dadi_tot += n;
        if dadi_tot > 200 {
            return Err(Errore("troppi dadi"));
        }
        let valori: Vec<i64> = (0..n).map(|_| rng.gen_range(1..=i64::from(facce))).collect();
        let mut tenuti: Vec<usize> = (0..n as usize).collect();
        if let Some(k_tipo) = m.get(4) {
            let k: usize = m.get(5).unwrap().as_str().parse::<usize>().unwrap_or(1).clamp(1, n as usize);
            let mut ordinati: Vec<usize> = (0..n as usize).collect();
            // ordinamento stabile come sorted() di Python
            if k_tipo.as_str() == "kh" {
                ordinati.sort_by(|&a, &b| valori[b].cmp(&valori[a]));
            } else {
                ordinati.sort_by(|&a, &b| valori[a].cmp(&valori[b]));
            }
            tenuti = ordinati[..k].to_vec();
            tenuti.sort_unstable();
        }
        let somma: i64 = tenuti.iter().map(|&i| valori[i]).sum();
        if facce == 20 {
            nat20 = nat20 || tenuti.iter().any(|&i| valori[i] == 20);
            nat1 = nat1 || tenuti.iter().any(|&i| valori[i] == 1);
        }
        parti.push(json!({"tipo": "dadi", "n": n, "facce": facce, "valori": valori, "tenuti": tenuti,
                          "segno": segno, "somma": somma * segno}));
        totale += somma * segno;
    }
    if pos != s.len() || parti.is_empty() {
        return Err(Errore("espressione non valida"));
    }
    Ok(json!({"espr": espr.trim(), "parti": parti, "totale": totale, "critico": nat20, "fallimento": nat1}))
}

/// Colpo critico: si raddoppia il numero di ogni gruppo di dadi dei danni («1d6+2» → «2d6+2»).
pub fn raddoppia_dadi(espr: &str) -> String {
    DANNI_RE
        .replace_all(espr, |c: &regex::Captures| {
            let n: u64 = c.get(1).map(|g| g.as_str()).filter(|g| !g.is_empty()).and_then(|g| g.parse().ok()).unwrap_or(1);
            format!("{}d{}", n.saturating_mul(2), &c[2])
        })
        .into_owned()
}

#[cfg(test)]
mod test {
    use super::*;

    #[test]
    fn valide() {
        for (e, lo, hi) in [("1d20", 1, 20), ("2d6+3", 5, 15), ("d%", 1, 100), ("2d20kh1+5", 6, 25), ("10", 10, 10),
                            ("-1d4", -4, -1), ("1d8 + 3 + 1d6", 5, 17), ("3D6", 3, 18)] {
            for _ in 0..50 {
                let t = tira(e).unwrap();
                let v = t["totale"].as_i64().unwrap();
                assert!((lo..=hi).contains(&v), "{e} → {v}");
            }
        }
    }

    #[test]
    fn tieni_il_migliore() {
        for _ in 0..50 {
            let t = tira("4d20kh1").unwrap();
            let p = &t["parti"][0];
            let max = p["valori"].as_array().unwrap().iter().map(|v| v.as_i64().unwrap()).max().unwrap();
            assert_eq!(t["totale"].as_i64().unwrap(), max);
            assert_eq!(p["tenuti"].as_array().unwrap().len(), 1);
        }
    }

    #[test]
    fn non_valide() {
        for e in ["", "ciao", "1d1", "101d6", "1d1001", "1d20+", "d", "2d6 3d6x", &"x".repeat(121),
                  "50d6+50d6+50d6+51d6", "99999999999999999999", "1d99999999999999999999"] {
            assert!(tira(e).is_err(), "{e}");
        }
    }

    #[test]
    fn critico() {
        assert_eq!(raddoppia_dadi("1d6+2"), "2d6+2");
        assert_eq!(raddoppia_dadi("d8+2d6"), "2d8+4d6");
    }
}
