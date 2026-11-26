//! Pacchetti avventura (.zip): estrazione protetta da path traversal e zip bomb, ed esportazione.

use std::fs;
use std::io::{self, Read, Write};
use std::path::{Component, Path, PathBuf};
use std::sync::LazyLock;

use regex::Regex;
use serde_json::Value;

use crate::util::{id_casuale, id_valido};

pub const MAX_ESTRATTO: u64 = 300 * 1024 * 1024;
const MAX_FILE: usize = 20_000;

static NON_ID: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"[^a-z0-9_\-]").unwrap());

/// Percorso relativo sicuro (solo componenti normali, niente assoluti, `..`, backslash o NUL).
fn relativo_sicuro(rel: &str) -> Option<PathBuf> {
    if rel.is_empty() || rel.contains('\\') || rel.contains('\0') {
        return None;
    }
    let p = Path::new(rel);
    let mut out = PathBuf::new();
    for c in p.components() {
        match c {
            Component::Normal(s) => out.push(s),
            _ => return None,
        }
    }
    (!out.as_os_str().is_empty()).then_some(out)
}

/// Estrae il pacchetto in una cartella temporanea dentro `avv_dir`. Restituisce (id, cartella temporanea).
pub fn estrai(dati: &[u8], avv_dir: &Path) -> Result<(String, PathBuf), String> {
    let mut z = zip::ZipArchive::new(io::Cursor::new(dati)).map_err(|_| "il file non è uno zip valido".to_string())?;
    if z.len() > MAX_FILE {
        return Err("troppi file nel pacchetto".into());
    }
    let mut nomi = Vec::new();
    let mut totale: u64 = 0;
    for i in 0..z.len() {
        let f = z.by_index_raw(i).map_err(|_| "il file non è uno zip valido".to_string())?;
        if f.is_dir() || f.name().ends_with('/') {
            continue;
        }
        totale = totale.saturating_add(f.size());
        nomi.push((i, f.name().to_string()));
    }
    if totale > MAX_ESTRATTO {
        return Err("pacchetto troppo grande una volta estratto".into());
    }
    let radice = nomi
        .iter()
        .filter(|(_, n)| n.rsplit('/').next() == Some("avventura.json"))
        .map(|(_, n)| n.as_str())
        .min_by_key(|n| n.len())
        .ok_or("manca avventura.json nel pacchetto")?;
    let radice = radice[..radice.len() - "avventura.json".len()].to_string();
    let manifest: Value = {
        let mut f = z.by_name(&format!("{radice}avventura.json")).map_err(|_| "avventura.json illeggibile".to_string())?;
        let mut buf = Vec::new();
        f.by_ref().take(2 * 1024 * 1024).read_to_end(&mut buf).map_err(|_| "avventura.json illeggibile".to_string())?;
        serde_json::from_slice(&buf).map_err(|_| "avventura.json non è un JSON valido".to_string())?
    };
    let dal_manifest = manifest.get("id").and_then(crate::util::testo).filter(|s| !s.is_empty());
    let dalla_cartella = radice.trim_matches('/').rsplit('/').next().filter(|s| !s.is_empty()).map(String::from);
    let aid = dal_manifest.or(dalla_cartella).unwrap_or_else(|| "avventura".into()).to_lowercase();
    let aid: String = NON_ID.replace_all(&aid, "-").chars().take(60).collect();
    let aid = aid.trim_matches('-').to_string();
    let aid = if aid.is_empty() { "avventura".to_string() } else { aid };
    if !id_valido(&aid) {
        return Err("id dell'avventura non valido".into());
    }
    let tmp = avv_dir.join(format!(".tmp-{aid}-{}", id_casuale(6)));
    fs::create_dir_all(&tmp).map_err(|e| format!("impossibile creare la cartella: {e}"))?;
    let esito = (|| -> Result<(), String> {
        let mut scritti: u64 = 0;
        for (i, nome) in &nomi {
            let Some(rel) = nome.strip_prefix(&radice) else { continue };
            let rel = relativo_sicuro(rel).ok_or("percorso non valido nel pacchetto")?;
            let mut f = z.by_index(*i).map_err(|_| "file illeggibile nel pacchetto".to_string())?;
            if f.enclosed_name().is_none() {
                return Err("percorso non valido nel pacchetto".into());
            }
            let dest = tmp.join(&rel);
            if let Some(d) = dest.parent() {
                fs::create_dir_all(d).map_err(|e| e.to_string())?;
            }
            let mut out = fs::File::create(&dest).map_err(|e| e.to_string())?;
            // si legge al massimo quanto resta del limite: uno zip che mente sulle dimensioni non passa
            let resta = MAX_ESTRATTO - scritti;
            let n = io::copy(&mut f.by_ref().take(resta + 1), &mut out).map_err(|_| "file danneggiato nel pacchetto".to_string())?;
            scritti += n;
            if scritti > MAX_ESTRATTO {
                return Err("pacchetto troppo grande una volta estratto".into());
            }
            out.flush().map_err(|e| e.to_string())?;
        }
        Ok(())
    })();
    match esito {
        Ok(()) => Ok((aid, tmp)),
        Err(e) => {
            let _ = fs::remove_dir_all(&tmp);
            Err(e)
        }
    }
}

/// Sostituisce (o crea) `avv_dir/<aid>` con la cartella estratta.
pub fn installa(tmp: &Path, avv_dir: &Path, aid: &str) -> io::Result<()> {
    let finale = avv_dir.join(aid);
    let mut vecchio = None;
    if finale.exists() {
        let v = avv_dir.join(format!(".old-{aid}-{}", id_casuale(6)));
        fs::rename(&finale, &v)?;
        vecchio = Some(v);
    }
    if let Err(e) = fs::rename(tmp, &finale) {
        if let Some(v) = &vecchio {
            let _ = fs::rename(v, &finale);
        }
        let _ = fs::remove_dir_all(tmp);
        return Err(e);
    }
    if let Some(v) = vecchio {
        let _ = fs::remove_dir_all(v);
    }
    Ok(())
}

/// Zip della cartella di un'avventura (`<aid>/...`). I link simbolici non vengono seguiti.
pub fn zip_avventura(base: &Path, aid: &str) -> io::Result<Vec<u8>> {
    let mut buf = io::Cursor::new(Vec::new());
    {
        let mut z = zip::ZipWriter::new(&mut buf);
        let opz = zip::write::SimpleFileOptions::default().compression_method(zip::CompressionMethod::Deflated).large_file(true);
        let mut pila = vec![base.to_path_buf()];
        let mut files = Vec::new();
        while let Some(d) = pila.pop() {
            for e in fs::read_dir(&d)?.filter_map(|e| e.ok()) {
                let ft = e.file_type()?;
                if ft.is_dir() {
                    pila.push(e.path());
                } else if ft.is_file() {
                    files.push(e.path());
                }
            }
        }
        files.sort();
        for f in files {
            let rel = f.strip_prefix(base).map_err(io::Error::other)?;
            let nome = format!("{aid}/{}", rel.to_string_lossy().replace('\\', "/"));
            z.start_file(nome, opz).map_err(io::Error::other)?;
            io::copy(&mut fs::File::open(&f)?, &mut z)?;
        }
        z.finish().map_err(io::Error::other)?;
    }
    Ok(buf.into_inner())
}

#[cfg(test)]
mod test {
    use super::*;
    use zip::write::SimpleFileOptions;

    fn zip_di(files: &[(&str, &[u8])]) -> Vec<u8> {
        let mut buf = io::Cursor::new(Vec::new());
        let mut z = zip::ZipWriter::new(&mut buf);
        for (n, d) in files {
            z.start_file(*n, SimpleFileOptions::default()).unwrap();
            z.write_all(d).unwrap();
        }
        z.finish().unwrap();
        buf.into_inner()
    }

    #[test]
    fn traversal_rifiutato() {
        let dir = tempfile::tempdir().unwrap();
        let z = zip_di(&[("p/avventura.json", b"{\"id\":\"x\"}"), ("p/../../evil.txt", b"pwn")]);
        assert!(estrai(&z, dir.path()).is_err());
        let z = zip_di(&[("p/avventura.json", b"{\"id\":\"x\"}"), ("p//etc/passwd", b"pwn")]);
        let r = estrai(&z, dir.path());
        if let Ok((_, tmp)) = r {
            assert!(tmp.join("etc/passwd").starts_with(&tmp));
        }
        assert_eq!(fs::read_dir(dir.path()).unwrap().filter(|e| e.as_ref().unwrap().file_name().to_string_lossy().contains("evil")).count(), 0);
    }

    #[test]
    fn id_ripulito() {
        let dir = tempfile::tempdir().unwrap();
        let z = zip_di(&[("a/avventura.json", br#"{"id": "../../Strano ID!"}"#), ("a/mappe/m.svg", b"<svg/>")]);
        let (aid, tmp) = estrai(&z, dir.path()).unwrap();
        assert_eq!(aid, "strano-id");
        assert!(tmp.join("mappe/m.svg").is_file());
        installa(&tmp, dir.path(), &aid).unwrap();
        assert!(dir.path().join("strano-id/avventura.json").is_file());
        let zz = zip_avventura(&dir.path().join("strano-id"), "strano-id").unwrap();
        let mut a = zip::ZipArchive::new(io::Cursor::new(zz)).unwrap();
        assert!(a.by_name("strano-id/mappe/m.svg").is_ok());
    }

    #[test]
    fn non_zip_e_senza_manifest() {
        let dir = tempfile::tempdir().unwrap();
        assert!(estrai(b"ciao", dir.path()).is_err());
        assert!(estrai(&zip_di(&[("x/readme.txt", b"x")]), dir.path()).is_err());
    }
}
