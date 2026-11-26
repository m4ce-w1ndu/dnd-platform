-- Registro di audit: accessi admin, cambi di permessi e impostazioni, azioni distruttive.
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ora REAL NOT NULL,
    utente TEXT,
    nome TEXT,
    ip TEXT,
    azione TEXT NOT NULL,
    dettagli TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS audit_ora ON audit(ora);
