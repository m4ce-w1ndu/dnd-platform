-- Stesso schema del server Python (tavolo/server.py): un database esistente si apre così com'è.
CREATE TABLE IF NOT EXISTS impostazioni (chiave TEXT PRIMARY KEY, valore TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS utenti (id TEXT PRIMARY KEY, nome TEXT, account TEXT, admin INTEGER DEFAULT 0,
                                   master INTEGER DEFAULT 0, visto REAL, dati TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS account (chiave TEXT PRIMARY KEY, utente_id TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS partite (avventura TEXT PRIMARY KEY, stato TEXT NOT NULL, aggiornata REAL);
