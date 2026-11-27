# Regole del tavolo: chi può fare cosa

Approvate il 27/11/2026, con la modifica sugli amministratori.

## Chi c'è al tavolo

- **Account di sistema «Admin»**: si entra con utente e password dell'admin. È **uno solo** (lo stesso da qualsiasi
  dispositivo) e serve **solo** a configurare il sistema e assegnare i permessi. Non gioca, non apre il tavolo,
  non fa il Master.
- **Amministratori del tavolo**: possono essere **tanti**; sono gli account (Discord/Google/GitHub o ospiti) a cui
  l'account di sistema dà il permesso di admin. Aprono il tavolo, scelgono il Master e **possono fare il Master**.
- **Master**: chi è stato nominato Master per la partita. Ce n'è **uno solo** alla volta.
- **Giocatore**: chiunque altro sia seduto al tavolo. Chi entra con Discord/Google/GitHub e chi entra come ospite
  hanno **gli stessi poteri**.
- **Proprietario**: il giocatore che gioca un certo personaggio. È il proprietario della sua pedina.

## Entrare

1. All'accensione del server il tavolo è **chiuso**.
2. Un amministratore del tavolo sceglie l'avventura e **apre** il tavolo (sala d'attesa), poi sceglie il Master
   (anche se stesso).
3. I giocatori entrano: con un account, oppure come ospiti se l'admin lo permette (anche con una password del tavolo).
4. Nessun giocatore può chiamarsi **admin, amministratore, master, sistema** o con il nome dell'account admin.
5. Un personaggio può averlo **un solo giocatore collegato**. Se esce dal tavolo, il personaggio torna libero.
6. Il Master (o un amministratore del tavolo) fa **iniziare** la partita; il Master può metterla in **pausa**
   (tutti in sala d'attesa); Master o un amministratore del tavolo la **chiudono**.
7. Troppi tentativi di accesso dallo stesso indirizzo vengono bloccati per qualche secondo.

## Cosa può fare ogni giocatore

- Tirare i dadi (anche **tiri segreti**: li vedono solo lui e il Master), scrivere in chat (anche messaggi segreti).
- Fare un **ping** sulla mappa e usare il **righello**.
- Scegliere un personaggio libero.
- Mettersi in **iniziativa** (con un nome o con la propria pedina).
- Sulla **propria** pedina: spostarla, cambiare PF (tra 0 e il massimo) e condizioni, eliminarla.
  **Non** può cambiarne nome, icona, taglia, colore, né renderla nascosta.
- Sulla **propria** scheda: PF, PF temporanei, slot, usi, note, condizioni.
- **Non** può: creare pedine, muovere o toccare pedine altrui, mettere in iniziativa pedine altrui, gestire i turni,
  vedere pedine nascoste, documenti e note del Master, mostri non alleati.
- Se manda troppe azioni in poco tempo, il server lo frena per qualche secondo (i trascinamenti hanno un margine più ampio).

## Cosa può fare in più il Master

- Creare, modificare, nascondere ed eliminare **qualsiasi** pedina.
- Gestire **tutti i turni** di iniziativa (avanti, indietro, valori, rimuovere, svuotare); voci di iniziativa nascoste.
- Cambiare mappa (portandosi dietro il gruppo), griglia, nebbia, note del Master.
- Modificare qualsiasi scheda.
- Svuotare la cronologia, togliere i mostri da una mappa, ricominciare la partita da zero.
- Gestire le avventure: cambiarla, crearne una, modificarne i dati, caricare pacchetti, mappe e documenti,
  eliminare mappe, documenti e avventure (non quella in gioco), scaricarle; esportare/importare la partita.
- Leggere i documenti «solo Master».

## Cosa può fare in più un amministratore del tavolo

- Aprire il tavolo e scegliere chi fa il Master (anche se stesso).
- Far iniziare e chiudere la partita (anche se non è il Master).
- Fare il Master.
- **Non** può cambiare impostazioni o permessi: quelli sono dell'account di sistema.

## Cosa può fare l'account di sistema «Admin» (e solo lui)

- Impostazioni: nome del tavolo, indirizzo pubblico, ospiti sì/no, password del tavolo, accesso con Discord/Google/GitHub,
  nome e password dell'admin (serve la password attuale).
- Utenti: dare o togliere il permesso di fare il Master o l'amministratore del tavolo, eliminare utenti.
  Non può togliersi i permessi da solo né eliminare se stesso.
- Partite salvate: vederle, azzerarle; scaricare il backup del database; leggere il registro di audit.
- Ogni accesso con la password dell'admin e ogni cambio di permessi o impostazioni viene scritto nel
  **registro di audit** (chi, quando, da quale indirizzo).
- I vecchi utenti «Admin» creati dal server Python (uno per ogni browser) vengono riconosciuti come account di
  sistema: non possono più aprire il tavolo. Da ⚙️ → Utenti e permessi → 🧹 Pulizia si eliminano in un colpo solo,
  insieme agli ospiti senza permessi non visti da più di N giorni (scelti lì: 1, 7, 30 o 90).
