# Regole del tavolo: chi può fare cosa

Da approvare. Sono le regole che il server applica oggi (dopo le correzioni di questa sera) e che il server
nuovo mantiene identiche. Se una regola non ti va bene, dimmi quale e come la vuoi.

## Chi c'è al tavolo

- **Amministratore (admin)**: chi entra con utente e password dell'admin, o un account a cui l'admin ha dato il permesso.
- **Master**: chi l'admin ha nominato Master per la partita. Ce n'è **uno solo** alla volta. L'admin può fare il Master.
- **Giocatore**: chiunque altro sia seduto al tavolo. Chi entra con Discord/Google/GitHub e chi entra come ospite
  hanno **gli stessi poteri**.
- **Proprietario**: il giocatore che gioca un certo personaggio. È il proprietario della sua pedina.

## Entrare

1. All'accensione del server il tavolo è **chiuso**. Entra solo l'admin.
2. L'admin sceglie l'avventura e **apre** il tavolo (sala d'attesa).
3. I giocatori entrano: con un account, oppure come ospiti se l'admin lo permette (anche con una password del tavolo).
4. Nessun giocatore può chiamarsi **admin, amministratore, master, sistema** o con il nome dell'account admin.
5. Un personaggio può averlo **un solo giocatore collegato**. Se esce dal tavolo, il personaggio torna libero.
6. Il Master fa **iniziare** la partita; può metterla in **pausa** (tutti in sala d'attesa); Master o admin la **chiudono**.
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

## Cosa può fare in più l'admin

- Aprire il tavolo e scegliere chi fa il Master.
- Far iniziare e chiudere la partita (anche se non è il Master).
- Impostazioni: nome del tavolo, indirizzo pubblico, ospiti sì/no, password del tavolo, accesso con Discord/Google/GitHub,
  nome e password dell'admin (serve la password attuale).
- Utenti: dare o togliere il permesso di fare il Master o l'admin, eliminare utenti. **Non** può togliersi l'admin
  da solo né eliminare se stesso.
- Partite salvate: vederle, azzerarle; scaricare il backup del database.
- **Novità**: ogni accesso admin e ogni cambio di permessi o impostazioni viene scritto nel **registro di audit**
  (chi, quando, da quale indirizzo). Così si capisce da dove vengono gli account «Admin» che non riconosci.

## Da decidere (proposte, oggi NON attive)

- **Gli account «Admin» che non riconosci quasi certamente sei tu.** Ogni volta che si entra con utente e password
  dell'admin da un browser che non ha le credenziali salvate (altro PC, telefono, finestra anonima, la pagina
  `/admin`), il server crea un nuovo utente chiamato «Admin» con i permessi di admin. Il server Rust fa lo stesso
  (per compatibilità) ma ora scrive ogni accesso nel registro di audit con data e indirizzo IP.
  Proposta: un solo utente «Admin» riusato da tutti i dispositivi. Lo attivo?
  Quelli vecchi si possono eliminare da ⚙️ → Utenti.
- Un admin dovrebbe poter fare le azioni del Master anche senza essere nominato Master? Oggi **no**.
