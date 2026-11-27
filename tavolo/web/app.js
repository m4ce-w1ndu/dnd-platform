/* Tavolo Virtuale · client
 * Nessuna dipendenza esterna. Parla con server.py via fetch (POST /api/op) e Server-Sent Events (/api/eventi).
 */
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const sg = (n) => (n >= 0 ? "+" + n : "−" + -n);
const mod = (v) => Math.floor((v - 10) / 2);
const NOMI_CAR = { FOR: "Forza", DES: "Destrezza", COS: "Costituzione", INT: "Intelligenza", SAG: "Saggezza", CAR: "Carisma" };
const ABILITA = { "Acrobazia": "DES", "Addestrare Animali": "SAG", "Arcano": "INT", "Atletica": "FOR", "Furtività": "DES", "Indagare": "INT", "Inganno": "CAR", "Intimidire": "CAR", "Intrattenere": "CAR", "Intuizione": "SAG", "Medicina": "SAG", "Natura": "INT", "Percezione": "SAG", "Persuasione": "CAR", "Rapidità di Mano": "DES", "Religione": "INT", "Storia": "INT", "Sopravvivenza": "SAG" };
const CONDIZIONI = [["Prono", "⬇️"], ["Spaventato", "😱"], ["Afferrato", "✊"], ["Trattenuto", "🕸️"], ["Accecato", "🙈"], ["Avvelenato", "🤢"], ["Stordito", "💫"], ["Privo di sensi", "💤"], ["Concentrazione", "🧠"], ["Benedetto", "✨"], ["Marchiato", "🎯"], ["Invisibile", "👻"]];
const LOGHI = {
  discord: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M20.317 4.3698a19.7913 19.7913 0 00-4.8851-1.5152.0741.0741 0 00-.0785.0371c-.211.3753-.4447.8648-.6083 1.2495-1.8447-.2762-3.68-.2762-5.4868 0-.1636-.3933-.4058-.8742-.6177-1.2495a.077.077 0 00-.0785-.037 19.7363 19.7363 0 00-4.8852 1.515.0699.0699 0 00-.0321.0277C.5334 9.0458-.319 13.5799.0992 18.0578a.0824.0824 0 00.0312.0561c2.0528 1.5076 4.0413 2.4228 5.9929 3.0294a.0777.0777 0 00.0842-.0276c.4616-.6304.8731-1.2952 1.226-1.9942a.076.076 0 00-.0416-.1057c-.6528-.2476-1.2743-.5495-1.8722-.8923a.077.077 0 01-.0076-.1277c.1258-.0943.2517-.1923.3718-.2914a.0743.0743 0 01.0776-.0105c3.9278 1.7933 8.18 1.7933 12.0614 0a.0739.0739 0 01.0785.0095c.1202.099.246.1981.3728.2924a.077.077 0 01-.0066.1276 12.2986 12.2986 0 01-1.873.8914.0766.0766 0 00-.0407.1067c.3604.698.7719 1.3628 1.225 1.9932a.076.076 0 00.0842.0286c1.961-.6067 3.9495-1.5219 6.0023-3.0294a.077.077 0 00.0313-.0552c.5004-5.177-.8382-9.6739-3.5485-13.6604a.061.061 0 00-.0312-.0286zM8.02 15.3312c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9555-2.4189 2.157-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.9555 2.4189-2.1569 2.4189zm7.9748 0c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9554-2.4189 2.1569-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.946 2.4189-2.1568 2.4189Z"/></svg>',
  google: '<svg viewBox="0 0 48 48" aria-hidden="true"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/><path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/></svg>',
  github: '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/></svg>',
};
const COLORI = ["#c0392b", "#e67e22", "#f1c40f", "#27ae60", "#16a085", "#2980b9", "#8e44ad", "#d35400", "#e84393", "#7f8c8d"];

const S = {
  me: null, cred: null, st: null, scene: [], pg: {}, mostri: {},
  view: { x: 0, y: 0, z: 1 }, tool: "muovi", sel: null, adv: "", pool: {}, mod: 0,
  suono: true, nb: { modo: "rivela", forma: "1" }, schedaVista: null, es: null,
};

/* ============================================================ rete */
async function api(path, body) {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Client": S.cred?.id || "", "X-Secret": S.cred?.secret || "" },
    body: JSON.stringify(body || {}),
  });
  let j = {};
  try { j = await r.json(); } catch (e) { /* vuoto */ }
  if (!j.ok && j.errore) avviso(j.errore.replace(/^⚠️\s*/, ""));
  if (r.status === 401 && path !== "/api/entra" && path !== "/api/login") { esci(); }
  return j;
}
const op = (o) => api("/api/op", o);

function toast(t) {
  const d = document.createElement("div");
  d.textContent = t;
  $("#toast").appendChild(d);
  setTimeout(() => d.remove(), 3200);
}

/* ============================================================ avvio */
async function avvio() {
  S.info = await fetch("/api/info").then((r) => r.json()).catch(() => ({ avventura: {}, personaggi: [], presi: [], login: [] }));
  S.versione = S.info.versione;
  S.info.personaggi.forEach((p) => (S.pg[p.id] = p));
  try { S.suono = localStorage.getItem("tv_suono") !== "0"; } catch (e) { /* */ }
  $("#btn-suono").textContent = S.suono ? "🔊" : "🔇";
  preparaUI();
  preparaIngresso();

  const u = new URLSearchParams(location.search);
  let cred = null;
  try { cred = JSON.parse(localStorage.getItem("tv_cred") || "null"); } catch (e) { /* */ }
  if (location.pathname.replace(/\/$/, "") === "/admin" || u.has("admin")) {
    // ingresso di riserva per l'amministratore: sempre disponibile, qualunque cosa sia salvata nel browser
    history.replaceState(null, "", "/");
    mostraLoginAdmin();
    return;
  }
  if (u.get("accesso")) history.replaceState(null, "", location.pathname);
  // collegamento rapido (usato anche dai test): ?nome=…&ruolo=master&pw=…&pg=…
  if (u.get("nome")) {
    const master = u.get("ruolo") === "master";
    const r = await login(master ? { tipo: "admin", utente: u.get("utente") || "admin", password: u.get("pw") || "" } : { tipo: "ospite", nome: u.get("nome") });
    if (r) await entra({ ruolo: master ? "master" : "giocatore", personaggio: u.get("pg") || null, colore: u.get("colore") || COLORI[Math.floor(Math.random() * COLORI.length)] });
    return;
  }
  if (cred?.id) {
    S.cred = cred;
    const io = await fetch(`/api/io?c=${encodeURIComponent(cred.id)}&s=${encodeURIComponent(cred.secret)}`).then((r) => (r.ok ? r.json() : null)).catch(() => null);
    if (!io) { try { localStorage.removeItem("tv_cred"); } catch (e) { /* */ } S.cred = null; return; }
    S.io = io;
    // si era già seduti: si rientra direttamente
    if (cred.ruolo && !u.get("accesso") && (S.info.sessione !== "chiusa" || io.admin)) {
      const ok = await entra({ ruolo: cred.ruolo, personaggio: cred.personaggio || null, colore: cred.colore || io.colore }, true);
      if (ok) return;
    }
    mostraScelta();
  }
}

function salvaCred() { try { localStorage.setItem("tv_cred", JSON.stringify(S.cred)); } catch (e) { /* */ } }

function esci() {
  try { localStorage.removeItem("tv_cred"); } catch (e) { /* */ }
  location.href = location.pathname;
}

/* ============================================================ finestre di conferma (al posto di confirm()) */
function avviso(testo, opz = {}) {
  // come conferma(), ma con un solo pulsante: per errori e messaggi importanti
  return conferma(testo, { titolo: opz.titolo || "Attenzione", icona: opz.icona || "⚠️", ok: opz.ok || "Ok", soloOk: true, pericolo: opz.pericolo });
}

function conferma(testo, opz = {}) {
  return new Promise((risolvi) => {
    const sfondo = document.createElement("div");
    sfondo.className = "dialogo";
    sfondo.innerHTML = `<div class="dialogo-card ${opz.pericolo ? "pericolo" : ""}" role="dialog" aria-modal="true">
      <div class="dialogo-ic">${opz.icona || (opz.pericolo ? "⚠️" : "❓")}</div>
      <h3>${esc(opz.titolo || "Sei sicuro?")}</h3>
      <p>${esc(testo)}</p>
      <div class="dialogo-btn">
        ${opz.soloOk ? "" : `<button class="annulla">${esc(opz.annulla || "Annulla")}</button>`}
        <button class="ok ${opz.pericolo ? "rosso" : "primario"}">${esc(opz.ok || "Conferma")}</button>
      </div></div>`;
    const chiudi = (v) => { document.removeEventListener("keydown", tasti, true); sfondo.classList.add("via"); setTimeout(() => sfondo.remove(), 150); risolvi(v); };
    const tasti = (e) => { if (e.key === "Escape") { e.preventDefault(); chiudi(false); } if (e.key === "Enter") { e.preventDefault(); chiudi(true); } };
    sfondo.addEventListener("click", (e) => { if (e.target === sfondo) chiudi(false); });
    if (!opz.soloOk) sfondo.querySelector(".annulla").onclick = () => chiudi(false);
    sfondo.querySelector(".ok").onclick = () => chiudi(true);
    document.addEventListener("keydown", tasti, true);
    document.body.appendChild(sfondo);
    setTimeout(() => sfondo.querySelector(opz.pericolo && !opz.soloOk ? ".annulla" : ".ok").focus(), 30);
  });
}

/* ============================================================ ingresso: 1) accesso  2) ruolo e personaggio */
async function login(dati) {
  $("#in-errore").textContent = "";
  const corpo = { ...dati };
  if (S.cred?.id) { corpo.id = S.cred.id; corpo.secret = S.cred.secret; }
  const r = await fetch("/api/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) }).then((x) => x.json()).catch(() => ({ ok: false, errore: "Server non raggiungibile" }));
  if (!r.ok) { $("#in-errore").textContent = r.errore || "Errore"; avviso(r.errore || "Accesso non riuscito.", { titolo: "Accesso non riuscito", icona: "🔐" }); return false; }
  S.cred = { id: r.id, secret: r.secret, nome: r.nome };
  salvaCred();
  S.io = await fetch(`/api/io?c=${encodeURIComponent(r.id)}&s=${encodeURIComponent(r.secret)}`).then((x) => x.json()).catch(() => ({ nome: r.nome }));
  return true;
}

function preparaIngresso() {
  const i = S.info;
  $("#in-titolo").textContent = i.sessione === "chiusa" ? (i.nome_tavolo || "Tavolo Virtuale") : (i.avventura?.titolo || i.nome_tavolo || "Tavolo Virtuale");
  $("#in-sotto").textContent = i.sessione === "chiusa" ? "Accedi per entrare. Il tavolo si aprirà quando l'amministratore avvia una partita." : (i.avventura?.sottotitolo || "Accedi per sederti al tavolo.");
  const prov = i.login || [];
  $("#in-oauth").innerHTML = prov.map((l) => `<a class="${l.id}" href="/auth/${l.id}/start">${LOGHI[l.id] || ""}<span>Accedi con ${esc(l.nome)}</span></a>`).join("");
  $("#in-oauth").hidden = !prov.length;
  $("#in-ospite").hidden = !i.ospiti;
  $("#in-oppure").hidden = !prov.length;
  $("#in-pw-gioc").hidden = !i.password_giocatori;
  if (!prov.length && !i.ospiti) $("#in-admin").open = true;
  const ospite = async () => { if (await login({ tipo: "ospite", nome: $("#in-nome").value, password: $("#in-pwg").value })) mostraScelta(); };
  const admin = async () => { if (await login({ tipo: "admin", utente: $("#in-utente").value, password: $("#in-pw").value })) mostraScelta(); };
  $("#in-ospite-btn").onclick = ospite;
  $("#in-admin-btn").onclick = admin;
  $("#in-pw-vedi").onclick = () => { const f = $("#in-pw"); f.type = f.type === "password" ? "text" : "password"; $("#in-pw-vedi").textContent = f.type === "password" ? "👁" : "🙈"; };
  ["#in-nome", "#in-pwg"].forEach((q) => $(q).addEventListener("keydown", (e) => e.key === "Enter" && ospite()));
  $("#in-pw").addEventListener("keydown", (e) => e.key === "Enter" && admin());
}

function mostraLoginAdmin() {
  $("#passo-scelta").hidden = true;
  $("#passo-login").hidden = false;
  $("#in-admin").hidden = false;
  $("#in-admin").open = true;
  setTimeout(() => $("#in-pw").focus(), 50);
}

function mostraScelta() {
  // Il ruolo non si sceglie più all'ingresso: si entra nella sala d'attesa,
  // dove l'admin nomina il Master e i giocatori scelgono il personaggio.
  const io = S.io || {};
  $("#passo-login").hidden = true;
  $("#passo-scelta").hidden = false;
  $("#in-scelta").hidden = true;
  $("#in-chiuso").hidden = false;
  $("#in-chiuso").textContent = "Entro nella sala d'attesa…";
  entra({ ruolo: io.admin || io.master ? "master" : "giocatore", personaggio: io.char || null, colore: io.colore || COLORI[Math.floor(Math.random() * COLORI.length)] });
}

async function entra(dati, silenzioso) {
  $("#in-errore").textContent = "";
  const r = await fetch("/api/entra", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...dati, id: S.cred.id, secret: S.cred.secret }) })
    .then((x) => x.json()).catch(() => ({ ok: false, errore: "Server non raggiungibile" }));
  if (!r.ok) {
    if (r.login) { esci(); return false; }
    if (!silenzioso) { $("#in-errore").textContent = r.errore || "Errore"; avviso(r.errore || "Non riesco a entrare.", { titolo: "Non riesco a entrare", icona: "🚪" }); }
    return false;
  }
  S.cred = { ...S.cred, ruolo: dati.ruolo, personaggio: dati.personaggio, colore: dati.colore };
  salvaCred();
  await connetti();
  return true;
}

/* ============================================================ connessione e stato */
async function connetti() {
  const q = `c=${encodeURIComponent(S.cred.id)}&s=${encodeURIComponent(S.cred.secret)}`;
  const r = await fetch("/api/stato?" + q).catch(() => null);
  if (!r || r.status >= 500) { riprova(); return; }          // server giù (riavvio, proxy 502…): si riprova più tardi
  const st = r.ok ? await r.json().catch(() => null) : null;
  if (!st) { $("#ingresso").classList.add("aperta"); return; }
  $("#ingresso").classList.remove("aperta");
  $("#app").hidden = false;
  applicaStato(st);
  requestAnimationFrame(() => adattaVista());
  if (S.es) S.es.close();
  const es = new EventSource("/api/eventi?" + q);
  S.es = es;
  es.onmessage = (m) => { try { evento(JSON.parse(m.data)); } catch (e) { console.error(e); } };
  es.onopen = async () => {
    $("#stato-conn").className = "conn ok";
    await controllaVersione();
    const st2 = await fetch("/api/stato?" + q).then((r) => (r.ok ? r.json() : null)).catch(() => null);
    if (st2) applicaStato(st2, true);
  };
  es.onerror = () => {
    $("#stato-conn").className = "conn ko";
    // Se il proxy risponde con un errore (es. 502 durante un riavvio) EventSource smette di riprovare da solo.
    if (es.readyState === EventSource.CLOSED) riprova();
  };
}

// Riconnessione dopo un riavvio del server: se nel frattempo il codice è cambiato, la pagina si ricarica.
let riprovaTimer = null, riprovaAttesa = 2000;
function riprova() {
  if (riprovaTimer) return;
  riprovaTimer = setTimeout(async () => {
    riprovaTimer = null;
    const i = await fetch("/api/info").then((r) => (r.ok ? r.json() : null)).catch(() => null);
    if (!i) { riprovaAttesa = Math.min(riprovaAttesa * 1.5, 15000); riprova(); return; }
    riprovaAttesa = 2000;
    if (S.versione && i.versione && i.versione !== S.versione) { location.reload(); return; }
    connetti();
  }, riprovaAttesa);
}
setInterval(() => { if (S.cred && document.visibilityState === "visible") controllaVersione(); }, 60000);

async function controllaVersione() {
  const i = await fetch("/api/info").then((r) => r.json()).catch(() => null);
  if (i && S.versione && i.versione && i.versione !== S.versione) { toast("🔄 Il tavolo è stato aggiornato: ricarico…"); setTimeout(() => location.reload(), 800); }
  if (i) S.info = i;
}
async function ricaricaStato(mantieni = true) {
  const q = `c=${encodeURIComponent(S.cred.id)}&s=${encodeURIComponent(S.cred.secret)}`;
  const st = await fetch("/api/stato?" + q).then((r) => (r.ok ? r.json() : null)).catch(() => null);
  if (st) applicaStato(st, mantieni);
}
function applicaStato(st, mantieniVista) {
  const scenaPrima = S.st?.scena;
  S.st = st;
  S.me = st.io;
  document.body.classList.toggle("master", S.me.role === "master");
  // L'account di sistema configura e basta: niente sala, niente mappa, solo ⚙️ Impostazioni.
  const sistema = !!S.me.sistema;
  document.body.classList.toggle("admin", !!S.me.admin && !sistema);
  document.body.classList.toggle("sistema", sistema);
  $("#btn-logout-nome").innerHTML = S.me.avatar ? `<img src="${esc(S.me.avatar)}" alt="">` : `<b>${esc((S.me.name || "?").slice(0, 14))}</b>`;
  $("#io-chi").innerHTML = `${S.me.avatar ? `<img src="${esc(S.me.avatar)}" style="width:18px;height:18px;border-radius:50%;vertical-align:middle"> ` : ""}${esc(S.me.name)}${S.me.provider ? ` · ${esc(S.me.provider)}` : " · ospite"}${sistema ? " · sistema" : S.me.admin ? " · admin" : ""}`;
  $("#segreto-lbl").textContent = S.me.role === "master" ? "tiro nascosto ai giocatori" : "tiro privato (solo tu e il Master)";
  S.avv = st.avv;
  S.pg = {}; S.mostri = {};
  (st.avv.personaggi || []).forEach((p) => (S.pg[p.id] = p));
  (st.avv.mostri || []).forEach((m) => (S.mostri[m.id] = m));
  S.scene = st.avv.mappe || [];
  document.title = (st.avv.titolo || "Tavolo") + " · Tavolo Virtuale";
  if (S.schedaVista && !S.pg[S.schedaVista]) S.schedaVista = null;
  if (S.me.role !== "master") S.schedaVista = S.me.char && S.pg[S.me.char] ? S.me.char : null;
  else if (!S.schedaVista) S.schedaVista = Object.keys(S.pg)[0] || null;
  disegnaBestiario();
  disegnaDocumenti();
  disegnaSala();
  $("#m-note").value = st.note_master || "";
  caricaScena(!(mantieniVista && scenaPrima === st.scena));
  disegnaLog(true);
  disegnaIniziativa();
  disegnaScheda();
  disegnaGruppo();
  disegnaMaster();
}

function evento(ev) {
  const st = S.st;
  switch (ev.t) {
    case "pedina": {
      if (S.drag && S.drag.id === ev.pedina.id && ev.da === S.me.id) return;
      st.pedine[ev.pedina.id] = ev.pedina;
      disegnaPedina(ev.pedina, ev.trascina);
      if (S.sel === ev.pedina.id) disegnaPannelloPedina();
      disegnaGruppo();
      break;
    }
    case "pedina_via":
      delete st.pedine[ev.id];
      $(`#p_${ev.id}`)?.remove();
      if (S.sel === ev.id) seleziona(null);
      disegnaGruppo();
      break;
    case "log":
      st.log.push(ev.voce);
      if (st.log.length > 400) st.log.shift();
      aggiungiVoce(ev.voce, true);
      if (ev.voce.tipo === "tiro") animaDadi(ev.voce);
      break;
    case "scena":
      st.scena = ev.id;
      seleziona(null);
      caricaScena(true);
      break;
    case "nebbia":
      st.nebbia[ev.scena] = ev.nebbia;
      if (ev.scena === st.scena) disegnaNebbia();
      break;
    case "iniziativa": {
      const prima = st.iniziativa.ordine[st.iniziativa.turno]?.id;
      st.iniziativa = ev.iniziativa;
      disegnaIniziativa();
      const ora = st.iniziativa.ordine[st.iniziativa.turno];
      if (ora && ora.id !== prima) annunciaTurno(ora);
      break;
    }
    case "scheda":
      st.schede[ev.id] = ev.scheda;
      if (ev.id === S.schedaVista && !document.activeElement?.closest?.("#scheda")) disegnaScheda();
      else if (ev.id === S.schedaVista) aggiornaPfScheda();
      disegnaGruppo();
      break;
    case "online":
      st.online = ev.online;
      disegnaGruppo();
      if (st.sessione !== "in_corso") disegnaSala();
      break;
    case "catalogo":
      ricaricaStato();
      break;
    case "ping":
      mostraPing(ev.x, ev.y, ev.colore, ev.chi);
      if (ev.centra) centraSu(ev.x, ev.y);
      break;
    case "righello":
      if (ev.da !== S.me.id) disegnaRighello(ev.da, ev.punti, ev.colore);
      break;
    case "ricarica":
      ricaricaStato(false);
      break;
    case "sessione":
      S.st.sessione = ev.sessione;
      ricaricaStato(false);
      break;
    case "ruolo":
      S.cred.ruolo = ev.ruolo;
      salvaCred();
      if (ev.ruolo === "master") avviso("Ora hai il pannello 👑 Master: mappe, mostri, nebbia di guerra e turni. Quando tutti hanno scelto il personaggio, premi «▶ Inizia la partita».", { titolo: "Sei il Master!", icona: "👑", ok: "Andiamo!" });
      else toast("Ora sei un giocatore.");
      ricaricaStato(false);
      break;
    case "info":
      controllaVersione();
      break;
    case "esci":
      esci();
      break;
  }
}

/* ============================================================ scena e vista */
function scenaCorrente() {
  return S.scene.find((s) => s.id === S.st.scena) || S.scene[0] || { id: "vuota", titolo: "Nessuna mappa", file: "", larghezza: 1000, altezza: 800 };
}
function griglia() {
  const sc = scenaCorrente();
  const g = sc.griglia;
  if (g && g.cella > 0) return { cella: +g.cella, ox: +g.ox || 0, oy: +g.oy || 0, mostra: !!g.mostra };
  return null;
}
function cellaPx() { return griglia()?.cella || 50; }

function caricaScena(adatta) {
  const sc = scenaCorrente();
  $("#nome-scena").textContent = S.me?.sistema ? "⚙️ Amministrazione" : sc.titolo;
  const img = $("#mappa");
  const W = sc.larghezza, H = sc.altezza;
  img.hidden = !sc.file;
  if (sc.file && img.dataset.src !== sc.file) {
    img.dataset.src = sc.file;
    img.dataset.tentativi = "0";
    img.onerror = () => {
      const n = +img.dataset.tentativi + 1;
      img.dataset.tentativi = n;
      if (n <= 3) setTimeout(() => (img.src = sc.file + (sc.file.includes("?") ? "&" : "?") + "r=" + Date.now()), 800 * n);
      else avviso("Non riesco a caricare l'immagine della mappa. Prova a ricaricare la pagina.", { titolo: "Mappa non disponibile", icona: "🗺️" });
    };
    img.src = sc.file;
  }
  img.style.width = W + "px";
  img.style.height = H + "px";
  const sv = $("#sovra");
  sv.setAttribute("width", W); sv.setAttribute("height", H);
  sv.style.width = W + "px"; sv.style.height = H + "px";
  $("#pedine").innerHTML = "";
  Object.values(S.st.pedine).forEach((p) => disegnaPedina(p));
  disegnaGriglia();
  disegnaNebbia();
  disegnaIniziativa();
  if (adatta) adattaVista();
  disegnaMaster();
}

function applicaVista() {
  const v = S.view;
  $("#mondo").style.transform = `translate(${v.x}px,${v.y}px) scale(${v.z})`;
}
function adattaVista() {
  const sc = scenaCorrente();
  const vp = $("#viewport").getBoundingClientRect();
  if (vp.width < 10 || vp.height < 10) return;
  const z = Math.min(vp.width / sc.larghezza, (vp.height - (innerWidth < 860 ? 50 : 0)) / sc.altezza) * 0.96;
  S.view.z = Math.max(0.1, z);
  S.view.x = (vp.width - sc.larghezza * S.view.z) / 2;
  S.view.y = ((vp.height - (innerWidth < 860 ? 50 : 0)) - sc.altezza * S.view.z) / 2;
  if (innerWidth < 860) {
    // su telefono la mappa intera è troppo piccola: si ingrandisce e si centra sulla propria pedina (o sul gruppo)
    S.view.z = Math.max(S.view.z, Math.min(1, (vp.height - 50) / sc.altezza * 0.95));
    const mia = Object.values(S.st.pedine || {}).find((p) => p.scena === S.st.scena && p.pg && (p.pg === S.me.char || S.me.role === "master"));
    const c = mia ? posPedina(mia) : { x: sc.larghezza / 2, y: sc.altezza / 2 };
    S.view.x = vp.width / 2 - c.x * S.view.z;
    S.view.y = (vp.height - 50) / 2 - c.y * S.view.z;
  }
  applicaVista();
}
function zoom(f, cx, cy) {
  const vp = $("#viewport").getBoundingClientRect();
  if (cx === undefined) { cx = vp.width / 2; cy = vp.height / 2; }
  const z2 = Math.min(6, Math.max(0.08, S.view.z * f));
  S.view.x = cx - (cx - S.view.x) * (z2 / S.view.z);
  S.view.y = cy - (cy - S.view.y) * (z2 / S.view.z);
  S.view.z = z2;
  applicaVista();
}
function centraSu(x, y) {
  const vp = $("#viewport").getBoundingClientRect();
  S.view.x = vp.width / 2 - x * S.view.z;
  S.view.y = vp.height / 2 - y * S.view.z;
  applicaVista();
}
function aMondo(clientX, clientY) {
  const vp = $("#viewport").getBoundingClientRect();
  return { x: (clientX - vp.left - S.view.x) / S.view.z, y: (clientY - vp.top - S.view.y) / S.view.z };
}

function disegnaGriglia() {
  const cv = $("#griglia-cv");
  const sc = scenaCorrente();
  const g = griglia();
  if (!g || !g.mostra) { cv.width = cv.height = 0; return; }
  cv.width = sc.larghezza; cv.height = sc.altezza;
  cv.style.width = sc.larghezza + "px"; cv.style.height = sc.altezza + "px";
  const c = cv.getContext("2d");
  c.strokeStyle = "rgba(0,0,0,.45)";
  c.lineWidth = 1;
  c.beginPath();
  for (let x = g.ox; x <= sc.larghezza; x += g.cella) { c.moveTo(x, 0); c.lineTo(x, sc.altezza); }
  for (let y = g.oy; y <= sc.altezza; y += g.cella) { c.moveTo(0, y); c.lineTo(sc.larghezza, y); }
  c.stroke();
}

/* ============================================================ nebbia */
function dimNebbia() {
  const g = griglia();
  if (!g) return null;
  const sc = scenaCorrente();
  return { g, col: Math.ceil((sc.larghezza - g.ox) / g.cella), rig: Math.ceil((sc.altezza - g.oy) / g.cella) };
}
function disegnaNebbia() {
  const cv = $("#nebbia-cv");
  const nb = S.st.nebbia?.[S.st.scena];
  const d = dimNebbia();
  if (!d || !nb || !nb.attiva) {
    cv.width = cv.height = 0;
    $$(".pedina[hidden]").forEach((el) => (el.hidden = false));
    return;
  }
  cv.width = d.col; cv.height = d.rig;
  cv.style.left = d.g.ox + "px"; cv.style.top = d.g.oy + "px";
  cv.style.width = d.col * d.g.cella + "px"; cv.style.height = d.rig * d.g.cella + "px";
  const master = S.me.role === "master";
  cv.classList.toggle("giocatore", !master);
  const c = cv.getContext("2d");
  c.fillStyle = master ? "rgba(10,8,20,.55)" : "#07060a";
  c.fillRect(0, 0, d.col, d.rig);
  const viste = new Set(nb.celle);
  if (S.nbAnteprima) S.nbAnteprima.forEach((k) => (S.nb.modo === "rivela" ? viste.add(k) : viste.delete(k)));
  viste.forEach((k) => { const [x, y] = k.split(",").map(Number); c.clearRect(x, y, 1, 1); });
  if (!master) Object.values(S.st.pedine).forEach((p) => { const el = $(`#p_${p.id}`); if (el) el.hidden = !visibileNebbia(p); });
  // le pedine vedono un quadretto intorno a sé (solo per i giocatori, effetto «torcia»)
  if (!master) {
    Object.values(S.st.pedine).forEach((p) => {
      if (p.scena !== S.st.scena || !p.pg) return;
      const pos = posPedina(p);
      const cx = Math.floor((pos.x - d.g.ox) / d.g.cella), cy = Math.floor((pos.y - d.g.oy) / d.g.cella);
      c.clearRect(cx - 1, cy - 1, 3, 3);
    });
  }
}
function celleDaPennello(x, y) {
  const d = dimNebbia();
  if (!d) return [];
  const cx = Math.floor((x - d.g.ox) / d.g.cella), cy = Math.floor((y - d.g.oy) / d.g.cella);
  const r = Math.floor((+S.nb.forma || 1) / 2);
  const out = [];
  for (let i = -r; i <= r; i++) for (let j = -r; j <= r; j++) {
    if (r > 0 && i * i + j * j > r * r + r) continue;
    const a = cx + i, b = cy + j;
    if (a >= 0 && b >= 0 && a < d.col && b < d.rig) out.push(a + "," + b);
  }
  return out;
}
function celleDaRett(p1, p2) {
  const d = dimNebbia();
  if (!d) return [];
  const a = Math.floor((Math.min(p1.x, p2.x) - d.g.ox) / d.g.cella), b = Math.floor((Math.min(p1.y, p2.y) - d.g.oy) / d.g.cella);
  const c = Math.floor((Math.max(p1.x, p2.x) - d.g.ox) / d.g.cella), e = Math.floor((Math.max(p1.y, p2.y) - d.g.oy) / d.g.cella);
  const out = [];
  for (let i = Math.max(0, a); i <= Math.min(d.col - 1, c); i++) for (let j = Math.max(0, b); j <= Math.min(d.rig - 1, e); j++) out.push(i + "," + j);
  return out;
}

/* ============================================================ pedine */
function posPedina(p) {
  if (p.x != null && p.y != null) return { x: p.x, y: p.y };
  const sc = scenaCorrente();
  const g = griglia();
  const cel = cellaPx();
  const k = p.slot || 0;
  let bx, by;
  if (sc.inizio && g) { bx = g.ox + (sc.inizio[0] + 0.5) * g.cella; by = g.oy + (sc.inizio[1] + 0.5) * g.cella; }
  else { bx = sc.larghezza / 2 - cel; by = sc.altezza / 2; }
  return { x: bx + (k % 3) * cel, y: by + Math.floor(k / 3) * cel };
}
function puoMuovere(p) {
  return S.me.role === "master" || p.proprietario === S.me.id || (p.pg && p.pg === S.me.char);
}
function disegnaPedina(p, rapida) {
  let el = $(`#p_${p.id}`);
  if (p.scena !== S.st.scena) { el?.remove(); return; }
  if (!el) {
    el = document.createElement("div");
    el.id = "p_" + p.id;
    el.className = "pedina";
    el.innerHTML = `<div class="pf"><i></i></div><div class="disco"><span class="ico"></span></div><div class="nome"></div><div class="cond"></div>`;
    el.addEventListener("pointerdown", (e) => inizioTrascina(e, p.id));
    $("#pedine").appendChild(el);
  }
  const cel = cellaPx();
  const s = (p.taglia || 1) * cel;
  const pos = posPedina(p);
  el.style.width = el.style.height = s + "px";
  el.style.setProperty("--s", s + "px");
  el.style.setProperty("--c", p.colore || "#555");
  el.classList.toggle("trascinata", !!rapida);
  if (!(S.drag && S.drag.id === p.id)) { el.style.left = pos.x - s / 2 + "px"; el.style.top = pos.y - s / 2 + "px"; }
  $(".ico", el).textContent = p.icona || (p.nome || "?").slice(0, 2);
  $(".nome", el).textContent = p.nome;
  const pf = $(".pf", el);
  if (p.pfmax) {
    const r = Math.max(0, Math.min(1, (p.pf ?? p.pfmax) / p.pfmax));
    pf.hidden = false;
    $("i", pf).style.width = r * 100 + "%";
    pf.className = "pf" + (r <= 0.25 ? " basso" : r <= 0.5 ? " medio" : "");
  } else pf.hidden = true;
  $(".cond", el).textContent = (p.condizioni || []).map((c) => (CONDIZIONI.find((x) => x[0] === c) || [0, "•"])[1]).join("");
  el.classList.toggle("nascosta", !!p.nascosta);
  el.hidden = !visibileNebbia(p);
  el.classList.toggle("selezionata", S.sel === p.id);
  el.classList.toggle("mia", puoMuovere(p) && S.me.role !== "master");
  el.classList.toggle("a-terra", p.pfmax > 0 && (p.pf ?? 1) <= 0);
  const ini = S.st.iniziativa;
  const cur = ini.ordine[ini.turno];
  el.classList.toggle("turno", !!(cur && cur.pedina === p.id && ini.ordine.length > 1));
  el.style.zIndex = p.tipo === "pg" ? 3 : 2;
  el.title = p.nome + (p.pfmax ? ` · PF ${p.pf}/${p.pfmax}` : "");
}
function visibileNebbia(p) {
  if (S.me.role === "master" || p.pg || puoMuovere(p)) return true;
  const nb = S.st.nebbia?.[S.st.scena];
  const d = dimNebbia();
  if (!nb || !nb.attiva || !d) return true;
  const pos = posPedina(p);
  const k = Math.floor((pos.x - d.g.ox) / d.g.cella) + "," + Math.floor((pos.y - d.g.oy) / d.g.cella);
  return nb.celle.includes(k);
}
function aggancia(x, y, taglia) {
  const g = griglia();
  if (!g) return { x, y };
  const dispari = Math.round(taglia || 1) % 2 === 1;
  const fx = (x - g.ox) / g.cella, fy = (y - g.oy) / g.cella;
  if (dispari) return { x: g.ox + (Math.floor(fx) + 0.5) * g.cella, y: g.oy + (Math.floor(fy) + 0.5) * g.cella };
  return { x: g.ox + Math.round(fx) * g.cella, y: g.oy + Math.round(fy) * g.cella };
}
function distanzaQ(a, b) {
  const c = cellaPx();
  return Math.max(Math.abs(a.x - b.x), Math.abs(a.y - b.y)) / c;
}
const fmtDist = (q) => `${Math.round(q)} q · ${(Math.round(q) * 1.5).toLocaleString("it-IT")} m`;

function inizioTrascina(e, id) {
  if (S.tool !== "muovi") return;
  const p = S.st.pedine[id];
  if (!p) return;
  e.stopPropagation();
  seleziona(id);
  if (!puoMuovere(p) || e.button !== 0) return;
  const el = $(`#p_${id}`);
  el.setPointerCapture(e.pointerId);
  const start = posPedina(p);
  const m = aMondo(e.clientX, e.clientY);
  S.drag = { id, start, dx: m.x - start.x, dy: m.y - start.y, ultimo: 0, mosso: false };
  el.classList.add("trascinata");
  const muovi = (ev) => {
    const w = aMondo(ev.clientX, ev.clientY);
    const x = w.x - S.drag.dx, y = w.y - S.drag.dy;
    const s = (p.taglia || 1) * cellaPx();
    el.style.left = x - s / 2 + "px"; el.style.top = y - s / 2 + "px";
    S.drag.mosso = true;
    const a = aggancia(x, y, p.taglia);
    disegnaTraccia(start, a);
    const ora = performance.now();
    if (ora - S.drag.ultimo > 80) { S.drag.ultimo = ora; op({ op: "pedina_muovi", id, x: a.x, y: a.y }); }
  };
  const fine = (ev) => {
    el.removeEventListener("pointermove", muovi);
    el.removeEventListener("pointerup", fine);
    el.removeEventListener("pointercancel", fine);
    const w = aMondo(ev.clientX, ev.clientY);
    const a = aggancia(w.x - S.drag.dx, w.y - S.drag.dy, p.taglia);
    const mosso = S.drag.mosso;
    S.drag = null;
    el.classList.remove("trascinata");
    $("#traccia")?.remove();
    if (!mosso) { disegnaPedina(p); return; }
    p.x = a.x; p.y = a.y;
    disegnaPedina(p);
    op({ op: "pedina_muovi", id, x: a.x, y: a.y, finale: true });
    if (S.st.nebbia?.[S.st.scena]?.attiva && S.me.role !== "master") disegnaNebbia();
  };
  el.addEventListener("pointermove", muovi);
  el.addEventListener("pointerup", fine);
  el.addEventListener("pointercancel", fine);
}
function disegnaTraccia(a, b) {
  let g = $("#traccia");
  if (!g) { g = document.createElementNS("http://www.w3.org/2000/svg", "g"); g.id = "traccia"; $("#sovra").appendChild(g); }
  const q = distanzaQ(a, b);
  const z = 1 / S.view.z;
  g.innerHTML = `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke="#f6d27a" stroke-width="${4 * z}" stroke-dasharray="${10 * z} ${6 * z}" stroke-linecap="round"/>
    <circle cx="${b.x}" cy="${b.y}" r="${6 * z}" fill="#f6d27a"/>
    <g transform="translate(${b.x} ${b.y - 30 * z}) scale(${z})"><rect x="-58" y="-16" width="116" height="26" rx="13" fill="#1b130a" stroke="#e0b04a"/><text y="3" text-anchor="middle" fill="#f6d27a" font-size="14" font-weight="800" font-family="system-ui">${fmtDist(q)}</text></g>`;
}

function seleziona(id) {
  const prima = S.sel;
  S.sel = id;
  if (prima) { const p = S.st.pedine[prima]; if (p) disegnaPedina(p); }
  if (id) { const p = S.st.pedine[id]; if (p) disegnaPedina(p); }
  disegnaPannelloPedina();
}

function disegnaPannelloPedina() {
  const box = $("#pannello-pedina");
  const p = S.st.pedine[S.sel];
  if (!p) { box.hidden = true; return; }
  const master = S.me.role === "master";
  const mia = puoMuovere(p);
  const m = p.mostro ? S.mostri[p.mostro] : null;
  const vedePf = master || mia || p.tipo === "pg";
  box.hidden = false;
  box.innerHTML = `
    <div class="pp-testa"><span class="ic">${esc(p.icona || "●")}</span>
      ${master ? `<input class="nome" value="${esc(p.nome)}" id="pp-nome">` : `<b style="flex:1;font-size:15px">${esc(p.nome)}</b>`}
      ${p.ca ? `<span class="chip" title="Classe Armatura">🛡️ CA ${p.ca}</span>` : ""}
      <button id="pp-chiudi" title="Chiudi">✕</button></div>
    ${p.pfmax ? (vedePf ? `<div class="pp-pf"><span class="num">${p.pf ?? p.pfmax}/${p.pfmax}</span>
      ${mia ? `<input id="pp-qta" type="number" min="1" value="1"><button id="pp-danno" class="pericolo">− Danno</button><button id="pp-cura">+ Cura</button>` : ""}</div>`
      : `<div class="pp-pf"><span class="aiuto">Salute: ${statoSalute(p)}</span></div>`) : ""}
    ${mia ? `<div class="chips" id="pp-cond">${CONDIZIONI.map(([c, ic]) => `<button class="chip ${p.condizioni?.includes(c) ? "attivo" : ""}" data-c="${esc(c)}">${ic} ${c}</button>`).join("")}</div>` :
      (p.condizioni?.length ? `<div class="chips">${p.condizioni.map((c) => `<span class="chip attivo">${esc(c)}</span>`).join("")}</div>` : "")}
    ${m && master ? `<div class="stat-mini">${m.attacchi.map((a, i) => `<button data-att="${i}"><b>${esc(a.nome)}</b> ${a.bonus != null ? sg(a.bonus) : ""} · ${esc(a.danni)}<br><small>${esc(a.note || "")}</small></button>`).join("")}</div>
      ${m.tratti.map((t, i) => `<div class="tratto"><b>${esc(t.nome)}.</b> ${esc(t.testo)} ${t.tiro ? `<button class="link" data-tr="${i}">tira ${esc(t.tiro)}</button>` : ""}</div>`).join("")}` : ""}
    <div class="riga" style="margin-top:8px">
      ${mia ? `<button id="pp-ini">⚔️ Iniziativa</button>` : ""}
      ${master ? `<label class="switch"><input type="checkbox" id="pp-nasc" ${p.nascosta ? "checked" : ""}> nascosta</label>
        <select id="pp-taglia">${[[0.5, "Minuscola"], [1, "Media/Piccola"], [2, "Grande"], [3, "Enorme"], [4, "Mastodontica"]].map(([v, n]) => `<option value="${v}" ${p.taglia == v ? "selected" : ""}>${n}</option>`).join("")}</select>
        <button id="pp-centra">📍 Mostra a tutti</button>` : ""}
      ${(master || p.proprietario === S.me.id) && !p.pg ? `<button id="pp-elimina" class="pericolo">🗑️</button>` : ""}
    </div>`;
  $("#pp-chiudi").onclick = () => seleziona(null);
  const salva = (diff) => { Object.assign(p, diff); disegnaPedina(p); op({ op: "pedina_salva", pedina: { ...p } }); disegnaPannelloPedina(); };
  $("#pp-nome")?.addEventListener("change", (e) => salva({ nome: e.target.value }));
  const qta = () => Math.max(0, parseInt($("#pp-qta").value) || 0);
  $("#pp-danno")?.addEventListener("click", () => salva({ pf: Math.max(0, (p.pf ?? p.pfmax) - qta()) }));
  $("#pp-cura")?.addEventListener("click", () => salva({ pf: Math.min(p.pfmax, (p.pf ?? p.pfmax) + qta()) }));
  $$("#pp-cond button").forEach((b) => (b.onclick = () => {
    const c = b.dataset.c, l = new Set(p.condizioni || []);
    l.has(c) ? l.delete(c) : l.add(c);
    salva({ condizioni: [...l] });
  }));
  $("#pp-nasc")?.addEventListener("change", (e) => salva({ nascosta: e.target.checked }));
  $("#pp-taglia")?.addEventListener("change", (e) => salva({ taglia: +e.target.value }));
  $("#pp-elimina")?.addEventListener("click", () => { op({ op: "pedina_elimina", id: p.id }); seleziona(null); });
  $("#pp-centra")?.addEventListener("click", () => { const pos = posPedina(p); op({ op: "ping", x: pos.x, y: pos.y, centra: true }); });
  $("#pp-ini")?.addEventListener("click", () => tiraIniziativaPedina(p));
  $$("[data-att]", box).forEach((b) => (b.onclick = () => {
    const a = m.attacchi[+b.dataset.att];
    tiro(`1d20${a.bonus >= 0 ? "+" : ""}${a.bonus}`, `${p.nome} · ${a.nome}`, { danni: a.danni, segreto: $("#m-nascosto")?.checked && false });
  }));
  $$("[data-tr]", box).forEach((b) => (b.onclick = () => { const t = m.tratti[+b.dataset.tr]; tiro(t.tiro, `${p.nome} · ${t.nome}`); }));
}
function statoSalute(p) {
  const r = (p.pf ?? p.pfmax) / p.pfmax;
  if (r <= 0) return "💀 a terra";
  if (r <= 0.25) return "🩸 gravemente ferito";
  if (r <= 0.5) return "🤕 ferito";
  if (r < 1) return "😤 graffiato";
  return "💪 illeso";
}
function tiraIniziativaPedina(p) {
  let bonus = 0;
  if (p.pg && S.pg[p.pg]) bonus = S.pg[p.pg].iniz;
  else if (p.mostro && S.mostri[p.mostro]) bonus = S.mostri[p.mostro].des || 0;
  const seg = S.me.role === "master" && p.nascosta;
  tiro(`1d20${bonus >= 0 ? "+" : ""}${bonus}`, `${p.nome} · Iniziativa`, { segreto: seg }).then((r) => {
    if (r?.ok) op({ op: "iniziativa", azione: "aggiungi", nome: p.nome, valore: r.tiro.totale, pedina: p.id, colore: p.colore, nascosta: !!p.nascosta });
  });
}

/* ============================================================ input sulla mappa */
function preparaMappa() {
  const vp = $("#viewport");
  const punt = new Map();
  let pan = null, pinch = null, azione = null;

  vp.addEventListener("pointerdown", (e) => {
    if (e.target.closest(".flottante, #sala")) return;
    vp.setPointerCapture(e.pointerId);
    punt.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (punt.size === 2) {
      const [a, b] = [...punt.values()];
      pinch = { d: Math.hypot(a.x - b.x, a.y - b.y), z: S.view.z };
      pan = null; azione = null;
      return;
    }
    const w = aMondo(e.clientX, e.clientY);
    if (e.button === 1 || e.button === 2 || S.tool === "muovi") {
      pan = { x: e.clientX, y: e.clientY, vx: S.view.x, vy: S.view.y, mosso: false };
      vp.classList.add("trascina");
      return;
    }
    if (S.tool === "righello") azione = { tipo: "righello", a: aggancia(w.x, w.y, 1), ultimo: 0 };
    if (S.tool === "ping") { op({ op: "ping", x: w.x, y: w.y, centra: e.shiftKey }); }
    if (S.tool === "nebbia" && S.me.role === "master") {
      if (!S.st.nebbia?.[S.st.scena]?.attiva) { avviso("Spunta «attiva su questa mappa» nel riquadro della nebbia, poi potrai rivelare o coprire le zone.", { titolo: "La nebbia è spenta", icona: "🌫️" }); return; }
      if (S.nb.forma === "rett") azione = { tipo: "rett", a: w };
      else { azione = { tipo: "pennello" }; S.nbAnteprima = new Set(celleDaPennello(w.x, w.y)); disegnaNebbia(); }
    }
  });
  vp.addEventListener("pointermove", (e) => {
    if (!punt.has(e.pointerId)) return;
    punt.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pinch && punt.size === 2) {
      const [a, b] = [...punt.values()];
      const d = Math.hypot(a.x - b.x, a.y - b.y);
      const r = vp.getBoundingClientRect();
      zoom((pinch.z * d / pinch.d) / S.view.z, (a.x + b.x) / 2 - r.left, (a.y + b.y) / 2 - r.top);
      return;
    }
    if (pan) {
      const dx = e.clientX - pan.x, dy = e.clientY - pan.y;
      if (Math.abs(dx) + Math.abs(dy) > 3) pan.mosso = true;
      S.view.x = pan.vx + dx; S.view.y = pan.vy + dy;
      applicaVista();
      return;
    }
    if (!azione) return;
    const w = aMondo(e.clientX, e.clientY);
    if (azione.tipo === "righello") {
      azione.b = aggancia(w.x, w.y, 1);
      disegnaRighello(S.me.id, [azione.a, azione.b], S.me.color);
      const ora = performance.now();
      if (ora - azione.ultimo > 100) { azione.ultimo = ora; op({ op: "righello", punti: [azione.a, azione.b] }); }
    } else if (azione.tipo === "pennello") {
      celleDaPennello(w.x, w.y).forEach((k) => S.nbAnteprima.add(k));
      disegnaNebbia();
    } else if (azione.tipo === "rett") {
      S.nbAnteprima = new Set(celleDaRett(azione.a, w));
      disegnaNebbia();
    }
  });
  const fine = (e) => {
    punt.delete(e.pointerId);
    if (punt.size < 2) pinch = null;
    vp.classList.remove("trascina");
    if (pan) { if (!pan.mosso && e.target.closest && !e.target.closest(".pedina")) seleziona(null); pan = null; }
    if (azione?.tipo === "righello") {
      op({ op: "righello", punti: null });
      setTimeout(() => disegnaRighello(S.me.id, null), 1500);
    }
    if ((azione?.tipo === "pennello" || azione?.tipo === "rett") && S.nbAnteprima) {
      op({ op: "nebbia", azione: S.nb.modo, celle: [...S.nbAnteprima] });
      const nb = S.st.nebbia[S.st.scena];
      const s = new Set(nb.celle);
      S.nbAnteprima.forEach((k) => (S.nb.modo === "rivela" ? s.add(k) : s.delete(k)));
      nb.celle = [...s];
      S.nbAnteprima = null;
      disegnaNebbia();
    }
    azione = null;
  };
  vp.addEventListener("pointerup", fine);
  vp.addEventListener("pointercancel", fine);
  vp.addEventListener("contextmenu", (e) => e.preventDefault());
  vp.addEventListener("wheel", (e) => {
    e.preventDefault();
    const r = vp.getBoundingClientRect();
    zoom(Math.exp(-e.deltaY * 0.0015), e.clientX - r.left, e.clientY - r.top);
  }, { passive: false });
  vp.addEventListener("dblclick", (e) => {
    if (e.target.closest(".pedina,.flottante")) return;
    const w = aMondo(e.clientX, e.clientY);
    op({ op: "ping", x: w.x, y: w.y });
  });
  window.addEventListener("resize", () => adattaVista());
}

function disegnaRighello(chi, punti, colore) {
  const id = "rg_" + chi;
  let g = document.getElementById(id);
  if (!punti) { g?.remove(); return; }
  if (!g) { g = document.createElementNS("http://www.w3.org/2000/svg", "g"); g.id = id; $("#sovra").appendChild(g); }
  const [a, b] = punti;
  const z = 1 / S.view.z;
  g.innerHTML = `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke="${esc(colore)}" stroke-width="${5 * z}" stroke-linecap="round" opacity=".9"/>
    <circle cx="${a.x}" cy="${a.y}" r="${6 * z}" fill="${colore}"/><circle cx="${b.x}" cy="${b.y}" r="${6 * z}" fill="${colore}"/>
    <g transform="translate(${b.x} ${b.y - 28 * z}) scale(${z})"><rect x="-60" y="-16" width="120" height="26" rx="13" fill="#1b130a" stroke="${colore}" stroke-width="2"/><text y="3" text-anchor="middle" fill="#fff" font-size="14" font-weight="800" font-family="system-ui">📏 ${fmtDist(distanzaQ(a, b))}</text></g>`;
}
function mostraPing(x, y, colore, chi) {
  const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
  const z = 1 / S.view.z;
  g.setAttribute("class", "ping");
  g.innerHTML = `<circle cx="${x}" cy="${y}" r="${10 * z}" fill="${esc(colore)}"><animate attributeName="r" from="${8 * z}" to="${60 * z}" dur="1.2s" repeatCount="2"/><animate attributeName="opacity" from="1" to="0" dur="1.2s" repeatCount="2"/></circle>
    <circle cx="${x}" cy="${y}" r="${7 * z}" fill="${colore}" stroke="#fff" stroke-width="${2 * z}"/>
    <text x="${x}" y="${y - 16 * z}" font-size="${13 * z}" text-anchor="middle" fill="#fff" stroke="#000" stroke-width="${3 * z}" paint-order="stroke" font-weight="800" font-family="system-ui">${esc(chi)}</text>`;
  $("#sovra").appendChild(g);
  suona("ping");
  setTimeout(() => g.remove(), 2600);
}

/* ============================================================ dadi */
const FORME = {
  4: "50,6 95,88 5,88", 6: "12,12 88,12 88,88 12,88", 8: "50,3 94,50 50,97 6,50", 10: "50,4 92,40 50,96 8,40",
  12: "50,4 95,36 78,92 22,92 5,36", 20: "50,3 93,27 93,73 50,97 7,73 7,27", 100: "50,4 92,40 50,96 8,40",
};
const svgDado = (f, colore = "#7a2e1c", testo = "") => `<svg viewBox="0 0 100 100"><polygon points="${FORME[f] || FORME[6]}" fill="${esc(colore)}" stroke="#f6d27a" stroke-width="5" stroke-linejoin="round"/>${f === 20 ? '<polyline points="50,3 30,62 70,62 50,3" fill="none" stroke="#f6d27a55" stroke-width="3"/>' : ""}${testo ? `<text x="50" y="62" text-anchor="middle" font-size="30" font-weight="900" fill="#f6d27a">${testo}</text>` : ""}</svg>`;

function preparaDadi() {
  const box = $("#dadi-bottoni");
  [4, 6, 8, 10, 12, 20, 100].forEach((f) => {
    const b = document.createElement("button");
    b.innerHTML = svgDado(f, "#3a2a1c") + `d${f}`;
    b.title = `Aggiungi un d${f} (clic destro: tira subito)`;
    b.onclick = () => { S.pool[f] = (S.pool[f] || 0) + 1; disegnaPool(); };
    b.oncontextmenu = (e) => { e.preventDefault(); tiro(f === 20 ? d20(S.mod) : `1d${f}${S.mod ? (S.mod > 0 ? "+" : "") + S.mod : ""}`, `d${f}`); };
    box.appendChild(b);
  });
  $("#mod-piu").onclick = () => { S.mod++; disegnaPool(); };
  $("#mod-meno").onclick = () => { S.mod--; disegnaPool(); };
  $("#pool-svuota").onclick = () => { S.pool = {}; S.mod = 0; disegnaPool(); };
  $("#pool-tira").onclick = () => {
    let e = espressionePool();
    if (!e) e = d20(S.mod);
    tiro(e, "", { segreto: $("#tiro-segreto").checked });
    S.pool = {}; S.mod = 0; disegnaPool();
  };
  $$("#adv button").forEach((b) => (b.onclick = () => { S.adv = b.dataset.adv; $$("#adv button").forEach((x) => x.classList.toggle("attivo", x === b)); disegnaPool(); }));
  disegnaPool();
}
function espressionePool() {
  const parti = Object.entries(S.pool).filter(([, n]) => n > 0).map(([f, n]) => {
    if (+f === 20 && n === 1 && S.adv) return S.adv === "adv" ? "2d20kh1" : "2d20kl1";
    return `${n}d${f}`;
  });
  if (!parti.length) return "";
  return parti.join("+") + (S.mod ? (S.mod > 0 ? "+" : "") + S.mod : "");
}
function disegnaPool() {
  const e = espressionePool();
  const el = $("#pool-espr");
  el.classList.toggle("vuoto", !e);
  el.textContent = e || `Clicca i dadi · TIRA senza dadi = ${d20(S.mod)}`;
  $("#mod-val").textContent = sg(S.mod);
}
function d20(bonus) {
  const base = S.adv === "adv" ? "2d20kh1" : S.adv === "dis" ? "2d20kl1" : "1d20";
  return base + (bonus ? (bonus > 0 ? "+" : "") + bonus : "");
}
async function tiro(espr, etichetta, opz = {}) {
  const r = await op({ op: "tira", espr, etichetta, segreto: !!opz.segreto, danni: opz.danni || null, modo: espr.includes("kh") ? "vantaggio" : espr.includes("kl") ? "svantaggio" : "" });
  if (innerWidth < 860 && opz.chiudi !== false) $("#laterale").classList.remove("aperto");
  return r;
}

function dettagli(r) {
  return r.parti.map((p) => {
    if (p.tipo === "num") return `<span>${p.valore >= 0 ? "+" : "−"}${Math.abs(p.valore)}</span>`;
    const dd = p.valori.map((v, i) => {
      const t = p.tenuti.includes(i);
      return `<span class="d ${!t ? "x" : ""} ${t && v === p.facce ? "m" : ""} ${t && v === 1 ? "u" : ""}">${v}</span>`;
    }).join("");
    return `<span>${p.segno < 0 ? "−" : ""}${p.n}d${p.facce}${p.valori.length > 1 && p.tenuti.length < p.valori.length ? (p.tenuti.length === 1 ? "" : "") : ""}</span> ${dd}`;
  }).join(" ");
}
function htmlVoce(v) {
  const ora = new Date(v.ora * 1000).toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" });
  if (v.tipo === "sistema") return `<div class="voce sistema">${esc(v.testo)}</div>`;
  const testa = `<div class="chi">${esc(v.chi)}<small>${ora}${v.segreto ? " · 🔒 segreto" : ""}</small></div>`;
  if (v.tipo === "chat") return `<div class="voce ${v.segreto ? "segreto" : ""}" style="--c:${esc(v.colore)}">${testa}<div>${esc(v.testo)}</div></div>`;
  const cls = v.critico ? "critico" : v.fallimento ? "fallimento" : "";
  const badge = v.critico ? `<span class="badge">20 NATURALE!</span>` : v.fallimento ? `<span class="badge">1 naturale</span>` : "";
  const dan = v.danni ? `<div class="tiro"><div class="tot" style="font-size:19px">${v.danni.totale}</div><div><div class="etich">💥 Danni${v.critico ? " (critico: dadi doppi!)" : ""}</div><div class="det">${dettagli(v.danni)}</div></div></div>` : "";
  return `<div class="voce ${cls} ${v.segreto ? "segreto" : ""}" style="--c:${esc(v.colore)}">${testa}
    <div class="tiro"><div class="tot">${v.totale}</div><div><div class="etich">${esc(v.etichetta || v.espr)}${v.modo ? ` <small>(${v.modo})</small>` : ""}${badge}</div><div class="det">${esc(v.espr)} → ${dettagli(v)}</div></div></div>${dan}</div>`;
}
function disegnaLog() {
  const log = $("#log");
  log.innerHTML = S.st.log.slice(-150).map(htmlVoce).join("");
  log.scrollTop = log.scrollHeight;
}
function aggiungiVoce(v) {
  const log = $("#log");
  const vicino = log.scrollHeight - log.scrollTop - log.clientHeight < 80;
  log.insertAdjacentHTML("beforeend", htmlVoce(v));
  while (log.children.length > 200) log.firstChild.remove();
  if (vicino) log.scrollTop = log.scrollHeight;
  if (v.tipo === "chat" && v.da !== S.me.id) suona("chat");
}

function animaDadi(v) {
  const dadi = [];
  v.parti.forEach((p) => p.tipo === "dadi" && p.valori.forEach((x, i) => dadi.push({ f: p.facce, v: x, scartato: !p.tenuti.includes(i) })));
  if (v.danni) v.danni.parti.forEach((p) => p.tipo === "dadi" && p.valori.forEach((x) => dadi.push({ f: p.facce, v: x, danno: true })));
  const box = document.createElement("div");
  box.className = "lancio " + (v.critico ? "critico" : v.fallimento ? "fallimento" : "");
  const mostra = dadi.slice(0, 10);
  box.innerHTML = `<div class="fila">${mostra.map((d, i) => `<div class="dado ${d.scartato ? "scartato" : ""} ${d.v === d.f ? "max" : ""}" style="--dx:${(Math.random() - 0.5) * 300}px;--r:${(Math.random() - 0.5) * 720}deg;animation-delay:${i * 60}ms">${svgDado(d.f, d.danno ? "#5a1d10" : (v.colore || "#7a2e1c"))}<span>${d.v}</span></div>`).join("")}${dadi.length > 10 ? `<div class="dado"><span>+${dadi.length - 10}</span></div>` : ""}</div>
    <div class="totale"><small>${esc(v.chi)} · ${esc(v.etichetta || v.espr)}</small><b>${v.totale}${v.danni ? ` <span style="font-size:18px;color:#ff9f8a">· 💥 ${v.danni.totale}</span>` : ""}</b>${v.critico ? "<small>✨ 20 NATURALE! ✨</small>" : v.fallimento ? "<small>💀 che sfortuna…</small>" : ""}</div>`;
  // numeri che scorrono durante il rotolamento
  const spans = $$(".dado span", box);
  let n = 0;
  const giro = setInterval(() => {
    n++;
    spans.forEach((s, i) => { if (mostra[i]) s.textContent = n < 9 ? 1 + Math.floor(Math.random() * mostra[i].f) : mostra[i].v; });
    if (n >= 9) clearInterval(giro);
  }, 70);
  $$(".lancio", $("#dadi-anim")).forEach((x) => x.remove());
  $("#dadi-anim").appendChild(box);
  setTimeout(() => box.remove(), 3800);
  suona(v.critico ? "critico" : "dadi", dadi.length);
}

/* ============================================================ suoni (WebAudio, nessun file) */
let AC = null;
function suona(tipo, n = 1) {
  if (!S.suono) return;
  try {
    AC = AC || new (window.AudioContext || window.webkitAudioContext)();
    const t0 = AC.currentTime;
    const clic = (t, f, d = 0.05, vol = 0.18, forma = "triangle") => {
      const o = AC.createOscillator(), g = AC.createGain();
      o.type = forma; o.frequency.setValueAtTime(f, t);
      o.frequency.exponentialRampToValueAtTime(f * 0.5, t + d);
      g.gain.setValueAtTime(vol, t); g.gain.exponentialRampToValueAtTime(0.001, t + d);
      o.connect(g).connect(AC.destination); o.start(t); o.stop(t + d + 0.02);
    };
    if (tipo === "dadi") for (let i = 0; i < Math.min(6, 3 + n); i++) clic(t0 + i * 0.07 + Math.random() * 0.03, 600 + Math.random() * 900, 0.04, 0.12);
    if (tipo === "critico") { for (let i = 0; i < 4; i++) clic(t0 + i * 0.07, 700, 0.04, 0.1); [523, 659, 784, 1047].forEach((f, i) => clic(t0 + 0.35 + i * 0.09, f, 0.35, 0.12, "sine")); }
    if (tipo === "ping") clic(t0, 1200, 0.25, 0.1, "sine");
    if (tipo === "chat") clic(t0, 900, 0.12, 0.06, "sine");
    if (tipo === "turno") [440, 660].forEach((f, i) => clic(t0 + i * 0.12, f, 0.3, 0.1, "sine"));
  } catch (e) { /* audio non disponibile */ }
}

/* ============================================================ scheda personaggio */
function schedaStato(id) {
  const p = S.pg[id];
  const s = S.st.schede[id] || {};
  return { pf: s.pf ?? p.pf, pft: s.pft || 0, slot: s.slot || {}, usi: s.usi || {}, note: s.note || "" };
}
function salvaScheda(id, diff) {
  const s = { ...schedaStato(id), ...diff };
  S.st.schede[id] = s;
  op({ op: "scheda", id, scheda: s });
}
function aggiornaPfScheda() {
  const id = S.schedaVista, p = S.pg[id];
  if (!p) return;
  const s = schedaStato(id);
  const n = $("#sch-pf-num"), b = $("#sch-pf-barra");
  if (n) n.textContent = `${s.pf}/${p.pf}${s.pft ? ` (+${s.pft})` : ""}`;
  if (b) b.style.width = Math.max(0, Math.min(100, (s.pf / p.pf) * 100)) + "%";
}
function disegnaScheda() {
  const box = $("#scheda");
  const sc = $("#scheda-scelta");
  if (S.me.role === "master") {
    sc.innerHTML = `<select id="sch-sel" style="flex:1">${Object.values(S.pg).map((p) => `<option value="${p.id}" ${p.id === S.schedaVista ? "selected" : ""}>${p.icona} ${esc(p.nome)}</option>`).join("")}</select>`;
    $("#sch-sel").onchange = (e) => { S.schedaVista = e.target.value; disegnaScheda(); };
  }
  const id = S.schedaVista, p = S.pg[id];
  if (!p) {
    const presi = new Set((S.st.online || []).map((u) => u.char).filter(Boolean));
    box.innerHTML = `<p class="aiuto">Non hai ancora un personaggio in questa avventura. Scegline uno:</p><div class="pg-griglia">${Object.values(S.pg).map((x) => `<button class="pg-card ${presi.has(x.id) ? "preso" : ""}" data-scegli="${x.id}"><span class="ic">${x.icona}</span><b>${esc(x.nome)}</b><small>${esc(x.razza)} · ${esc(x.classe)}</small></button>`).join("") || '<p class="aiuto">Questa avventura non ha personaggi pronti.</p>'}</div>`;
    $$("[data-scegli]", box).forEach((b) => (b.onclick = async () => {
      const r = await op({ op: "scegli_pg", pg: b.dataset.scegli });
      if (r.ok) { S.me.char = b.dataset.scegli; S.cred.personaggio = b.dataset.scegli; salvaCred(); S.schedaVista = b.dataset.scegli; disegnaScheda(); }
    }));
    return;
  }
  const s = schedaStato(id);
  const mia = S.me.role === "master" || S.me.char === id;
  const semplice = !p.car;   // schede «semplificate» (es. avventure introduttive): niente punteggi di caratteristica
  const comp = (k) => (p.ts || []).includes(k);
  const tsBonus = (k) => mod(p.car[k]) + (comp(k) ? p.comp : 0);
  const abil = semplice
    ? Object.entries(p.abilita || {}).map(([n, b]) => ({ n, c: ABILITA[n] || "", b, pro: true }))
    : Object.entries(ABILITA).map(([n, c]) => {
      const pro = n in p.abilita;
      const b = pro ? p.abilita[n] : mod(p.car[c]) + (p.factotum || 0);
      return { n, c, b, pro };
    }).sort((a, b) => (b.pro - a.pro) || a.n.localeCompare(b.n));
  const m = p.magia;
  box.innerHTML = `<div class="sch">
    <div class="sch-testa"><span class="ic">${p.icona}</span><div><h2>${esc(p.nome)}</h2><small>${esc(p.razza)} · ${esc(p.classe)} · liv. ${p.livello}</small></div></div>
    <div class="gruppo-btn adv" style="margin:8px 0" id="sch-adv">
      <button data-adv="dis" class="${S.adv === "dis" ? "attivo" : ""}">Svantaggio</button><button data-adv="" class="${!S.adv ? "attivo" : ""}">Normale</button><button data-adv="adv" class="${S.adv === "adv" ? "attivo" : ""}">Vantaggio</button>
    </div>
    <div class="sch-pf">
      <div class="riga" style="justify-content:space-between;margin:0"><b>❤️ Punti Ferita</b><b id="sch-pf-num" style="font-size:18px">${s.pf}/${p.pf}${s.pft ? ` (+${s.pft})` : ""}</b></div>
      <div class="barra-pf"><i id="sch-pf-barra" style="width:${Math.max(0, Math.min(100, (s.pf / p.pf) * 100))}%"></i></div>
      ${mia ? `<div class="riga" style="margin:0"><input id="sch-qta" type="number" value="1" min="1" style="width:64px"><button id="sch-danno" class="pericolo">− Danno</button><button id="sch-cura">+ Cura</button><button id="sch-tmp" title="Punti ferita temporanei">+ Temp</button><button id="sch-riposo" title="Riposo lungo: tutto ripristinato">🌙</button></div>` : ""}
    </div>
    <div class="sch-box">
      <div><small>CA</small><b>${p.ca}</b>${p.ca_note ? `<small>${esc(p.ca_note)}</small>` : ""}</div>
      <button id="sch-ini"><small>Iniziativa</small><b>${sg(p.iniz || 0)}</b></button>
      <div><small>Velocità</small><b style="font-size:15px">${esc(p.vel)}</b></div>
      <div><small>Percezione passiva</small><b>${10 + (p.abilita.Percezione ?? (semplice ? 0 : mod(p.car.SAG)))}</b></div>
    </div>
    ${semplice ? `<p class="aiuto">📘 Regole semplificate: per un'abilità che non è nella tua scheda tira il d20 senza aggiungere nulla.</p>` : `<h3>Caratteristiche <small class="aiuto">(clic = prova · riga sotto = tiro salvezza)</small></h3>
    <div class="car6">${Object.entries(p.car).map(([k, v]) => `<button data-prova="${k}" title="Prova di ${NOMI_CAR[k]}"><small>${k}</small><b>${sg(mod(v))}</b><small>${v}</small></button>`).join("")}</div>
    <div class="car6" style="margin-top:4px">${Object.keys(p.car).map((k) => `<button data-ts="${k}" title="Tiro salvezza su ${NOMI_CAR[k]}"><small>TS</small><em>${comp(k) ? "★" : ""}${sg(tsBonus(k))}</em></button>`).join("")}</div>`}
    <h3>Attacchi</h3>
    ${p.attacchi.map((a, i) => `<div class="attacco"><button data-att="${i}"><b>${esc(a.nome)}</b> ${a.bonus != null ? `<b style="color:var(--oro2)">${sg(a.bonus)}</b>` : ""} · ${esc(a.danni)} ${esc(a.tipo)}<small>${esc(a.note)}</small></button>${a.bonus != null ? `<button data-dan="${i}" title="Solo danni">💥</button>` : ""}</div>`).join("")}
    <h3>Abilità</h3>
    <div class="lista-tiri">${abil.map((a) => `<button data-abil="${esc(a.n)}" class="${a.pro ? "comp" : ""}"><span>${esc(a.n)}</span><b>${sg(a.b)}</b></button>`).join("")}${semplice ? `<button data-abil-altra="1"><span>Altra abilità</span><b>+0</b></button>` : ""}</div>
    ${p.extra ? `<p class="aiuto">${esc(p.extra)}</p>` : ""}
    <h3>Capacità</h3>
    ${p.capacita.map((c, i) => `<div class="cap">${c.usi ? Array.from({ length: c.usi }, (_, k) => `<input type="checkbox" data-uso="${i}" data-k="${k}" ${(s.usi[i] || 0) > k ? "checked" : ""} ${mia ? "" : "disabled"}>`).join("") : ""} <b>${esc(c.nome)}.</b> ${esc(c.testo)} ${c.tiro ? `<button class="link" data-cap="${i}">tira ${esc(c.tiro)}</button>` : ""}</div>`).join("")}
    ${p.sensi ? `<div class="cap"><b>Sensi.</b> ${esc(p.sensi)}</div>` : ""}
    ${m ? `<h3>Magia <small class="aiuto">CD ${m.cd} · attacco ${sg(m.att)}</small></h3>
      <div class="slots">${Object.entries(m.slot).map(([lv, n]) => `<div class="lv">${lv}° liv.: ${Array.from({ length: n }, (_, k) => `<input type="checkbox" data-slot="${lv}" data-k="${k}" ${(s.slot[lv] || 0) > k ? "checked" : ""} ${mia ? "" : "disabled"} title="spunta = slot usato">`).join("")}</div>`).join("")}</div>
      ${m.nota ? `<p class="aiuto">${esc(m.nota)}</p>` : ""}
      ${m.incantesimi.map((x, i) => `<details class="incant"><summary><span><b>${esc(x.nome)}</b> <small>${x.liv ? x.liv + "° liv." : "trucchetto"}</small></span>${mia ? `<button class="link" data-lancia="${i}">${x.liv ? "Lancia" : (x.tiro ? "Tira" : "")}</button>` : ""}</summary><div>${esc(x.testo)}</div></details>`).join("")}` : ""}
    <h3>Equipaggiamento</h3><p class="cap">${esc(p.equip)}</p>
    <h3>Note</h3><textarea id="sch-note" ${mia ? "" : "disabled"} placeholder="Appunti, tesori, nomi da ricordare…">${esc(s.note)}</textarea>
    <p class="aiuto">💡 ${esc(p.consiglio)}</p>
  </div>`;

  const nome = p.nome.split(" ")[0];
  $$("#sch-adv button").forEach((b) => (b.onclick = () => { S.adv = b.dataset.adv; $$("#adv button").forEach((x) => x.classList.toggle("attivo", x.dataset.adv === S.adv)); disegnaScheda(); disegnaPool(); }));
  $$("[data-prova]", box).forEach((b) => (b.onclick = () => tiro(d20(mod(p.car[b.dataset.prova])), `${nome} · Prova di ${NOMI_CAR[b.dataset.prova]}`)));
  $$("[data-ts]", box).forEach((b) => (b.onclick = () => tiro(d20(tsBonus(b.dataset.ts)), `${nome} · TS ${NOMI_CAR[b.dataset.ts]}`)));
  $$("[data-abil]", box).forEach((b) => (b.onclick = () => { const a = abil.find((x) => x.n === b.dataset.abil); tiro(d20(a.b), `${nome} · ${a.n}`); }));
  $("[data-abil-altra]", box)?.addEventListener("click", () => tiro(d20(0), `${nome} · prova senza bonus`));
  $$("[data-att]", box).forEach((b) => (b.onclick = () => {
    const a = p.attacchi[+b.dataset.att];
    if (a.bonus == null) tiro(a.danni, `${nome} · ${a.nome}`);
    else tiro(d20(a.bonus), `${nome} · ${a.nome}`, { danni: a.danni });
  }));
  $$("[data-dan]", box).forEach((b) => (b.onclick = () => { const a = p.attacchi[+b.dataset.dan]; tiro(a.danni, `${nome} · danni ${a.nome}`); }));
  $$("[data-cap]", box).forEach((b) => (b.onclick = () => { const c = p.capacita[+b.dataset.cap]; tiro(c.tiro, `${nome} · ${c.nome}`); }));
  $("#sch-ini").onclick = () => {
    const ped = Object.values(S.st.pedine).find((x) => x.pg === id);
    if (ped) tiraIniziativaPedina(ped);
    else tiro(d20(p.iniz), `${nome} · Iniziativa`).then((r) => r?.ok && op({ op: "iniziativa", azione: "aggiungi", nome: p.nome, valore: r.tiro.totale, colore: p.colore }));
  };
  if (!mia) return;
  const qta = () => Math.max(0, parseInt($("#sch-qta").value) || 0);
  $("#sch-danno").onclick = () => {
    let d = qta(), st = schedaStato(id), tmp = st.pft;
    const assorbiti = Math.min(tmp, d); tmp -= assorbiti; d -= assorbiti;
    salvaScheda(id, { pf: Math.max(0, st.pf - d), pft: tmp }); aggiornaPfScheda();
    if (st.pf - d <= 0) avviso("Nel tuo turno tira un d20: con 10 o più è un successo, sotto 10 un fallimento. 3 successi = sei stabile, 3 fallimenti = muori. Un 20 ti rimette in piedi con 1 PF. Qualsiasi cura ti rialza subito.", { titolo: "Sei a terra!", icona: "💀" });
  };
  $("#sch-cura").onclick = () => { const st = schedaStato(id); salvaScheda(id, { pf: Math.min(p.pf, st.pf + qta()) }); aggiornaPfScheda(); };
  $("#sch-tmp").onclick = () => { salvaScheda(id, { pft: Math.max(schedaStato(id).pft, qta()) }); aggiornaPfScheda(); };
  $("#sch-riposo").onclick = async () => { if (await conferma("Punti ferita, slot degli incantesimi e capacità tornano al massimo.", { titolo: "Riposo lungo", icona: "🌙", ok: "Riposa" })) { salvaScheda(id, { pf: p.pf, pft: 0, slot: {}, usi: {} }); disegnaScheda(); } };
  $$("[data-slot]", box).forEach((c) => (c.onchange = () => {
    const lv = c.dataset.slot;
    const n = $$(`[data-slot="${lv}"]`, box).filter((x) => x.checked).length;
    salvaScheda(id, { slot: { ...schedaStato(id).slot, [lv]: n } });
  }));
  $$("[data-uso]", box).forEach((c) => (c.onchange = () => {
    const i = c.dataset.uso;
    const n = $$(`[data-uso="${i}"]`, box).filter((x) => x.checked).length;
    salvaScheda(id, { usi: { ...schedaStato(id).usi, [i]: n } });
  }));
  $$("[data-lancia]", box).forEach((b) => (b.onclick = (e) => {
    e.preventDefault(); e.stopPropagation();
    const x = m.incantesimi[+b.dataset.lancia];
    if (x.liv) {
      const st = schedaStato(id);
      // usa lo slot più basso disponibile dal livello dell'incantesimo in su
      const lv = Object.keys(m.slot).map(Number).sort().find((l) => l >= x.liv && (st.slot[l] || 0) < m.slot[l]);
      if (!lv) { avviso("Hai usato tutti gli slot di quel livello. Si recuperano con il riposo lungo (🌙 nella scheda).", { titolo: "Niente più slot", icona: "✨" }); return; }
      salvaScheda(id, { slot: { ...st.slot, [lv]: (st.slot[lv] || 0) + 1 } });
      disegnaScheda();
      if (!x.tiro) op({ op: "chat", testo: `✨ ${nome} lancia ${x.nome}! (slot di ${lv}° livello)` });
    }
    if (x.tiro) {
      if (x.attacco) tiro(d20(m.att), `${nome} · ${x.nome}`, { danni: x.tiro });
      else tiro(x.tiro, `${nome} · ${x.nome}`);
    } else if (!x.liv) op({ op: "chat", testo: `✨ ${nome} usa ${x.nome}.` });
  }));
  let tNote;
  $("#sch-note").oninput = (e) => { clearTimeout(tNote); tNote = setTimeout(() => salvaScheda(id, { note: e.target.value }), 600); };
}

/* ============================================================ iniziativa */
function disegnaIniziativa() {
  const ini = S.st.iniziativa;
  $("#ini-round").textContent = ini.round;
  const master = S.me.role === "master";
  $("#ini-lista").innerHTML = ini.ordine.length ? ini.ordine.map((x, i) => `<li class="${i === ini.turno ? "corrente" : ""} ${x.nascosta ? "nasc" : ""}" data-id="${x.id}" style="--c:${esc(x.colore || "#888")}">
    ${master ? `<input type="number" class="v" value="${x.valore}" data-val="${x.id}" style="width:54px">` : `<span class="v">${x.valore}</span>`}
    <span class="n">${i === ini.turno ? "▶ " : ""}${esc(x.nome)}${x.nascosta ? " 👁️‍🗨️" : ""}</span>
    ${master ? `<button data-rm="${x.id}">✕</button>` : ""}</li>`).join("") : `<li style="cursor:default;color:var(--muto)">Nessuno scontro in corso. Quando il Master dice «Tirate l'iniziativa!», premi il pulsante qui sopra.</li>`;
  $$("#ini-lista li[data-id]").forEach((li) => (li.onclick = (e) => {
    if (e.target.closest("input,button")) return;
    const x = ini.ordine.find((o) => o.id === li.dataset.id);
    const p = x?.pedina && S.st.pedine[x.pedina];
    if (p && p.scena === S.st.scena) { const pos = posPedina(p); centraSu(pos.x, pos.y); seleziona(p.id); }
  }));
  $$("[data-rm]").forEach((b) => (b.onclick = () => op({ op: "iniziativa", azione: "rimuovi", id: b.dataset.rm })));
  $$("[data-val]").forEach((inp) => (inp.onchange = () => op({ op: "iniziativa", azione: "valore", id: inp.dataset.val, valore: +inp.value })));
  Object.values(S.st.pedine).forEach((p) => p.scena === S.st.scena && $(`#p_${p.id}`) && disegnaPedina(p));
}
function annunciaTurno(x) {
  const box = $("#avviso-turno");
  const mio = (x.pedina && S.st.pedine[x.pedina] && puoMuovere(S.st.pedine[x.pedina]) && S.me.role !== "master") || x.da === S.me.id;
  if (x.nascosta && S.me.role !== "master") return;
  box.hidden = false;
  box.textContent = mio ? `⚔️ Tocca a te, ${x.nome}!` : `Turno di ${x.nome}`;
  box.style.animation = "none"; box.offsetHeight; box.style.animation = "";
  clearTimeout(S.tTurno);
  S.tTurno = setTimeout(() => (box.hidden = true), mio ? 5000 : 2500);
  if (mio) suona("turno");
}

/* ============================================================ gruppo */
function disegnaGruppo() {
  $("#online").innerHTML = (S.st.online || []).map((u) => `<li style="--c:${esc(u.color)}">${u.avatar ? `<img src="${esc(u.avatar)}" alt="">` : '<span class="pallino"></span>'}<b>${esc(u.name)}</b> <span class="aiuto">${u.role === "master" ? "👑 Master" : u.char && S.pg[u.char] ? S.pg[u.char].icona + " " + esc(S.pg[u.char].nome) : "spettatore"}</span></li>`).join("");
  const pgs = Object.values(S.st.pedine).filter((p) => p.pg);
  $("#party").innerHTML = pgs.length ? pgs.map((p) => {
    const r = Math.max(0, Math.min(1, (p.pf ?? p.pfmax) / (p.pfmax || 1)));
    return `<div class="party-pg"><div class="riga" style="margin:0;justify-content:space-between"><span>${p.icona} <b>${esc(p.nome)}</b></span><span>${p.pf}/${p.pfmax} · CA ${p.ca}</span></div><div class="barra-pf"><i style="width:${r * 100}%"></i></div>${p.condizioni?.length ? `<small class="aiuto">${p.condizioni.join(", ")}</small>` : ""}</div>`;
  }).join("") : `<p class="aiuto">Nessun personaggio al tavolo.</p>`;
}

/* ============================================================ pannello Master */
function disegnaMaster() {
  if (S.me?.role !== "master") return;
  const box = $("#m-scene");
  const gruppi = {};
  S.scene.forEach((s) => (gruppi[s.gruppo || "Mappe"] = gruppi[s.gruppo || "Mappe"] || []).push(s));
  box.innerHTML = Object.entries(gruppi).map(([g, l]) => `<div class="gruppo">${esc(g)}</div>${l.map((s) => `<button data-sc="${s.id}" class="${s.id === S.st.scena ? "attivo" : ""}">🗺️ ${esc(s.titolo)}</button>`).join("")}`).join("");
  $$("[data-sc]", box).forEach((b) => (b.onclick = () => op({ op: "scena", id: b.dataset.sc, porta_gruppo: $("#m-porta").checked })));
  const g = griglia() || { cella: 0, ox: 0, oy: 0 };
  $("#g-cella").value = g.cella; $("#g-ox").value = g.ox; $("#g-oy").value = g.oy;
  $("#g-mostra").checked = !!g.mostra;
  disegnaCatalogo();
  $("#nb-attiva").checked = !!S.st.nebbia?.[S.st.scena]?.attiva;
}
function disegnaBestiario() {
  const best = $("#m-bestiario");
  const l = Object.values(S.mostri);
  best.innerHTML = l.length ? l.map((m) => `<button data-mo="${m.id}"><span class="ic">${m.icona}</span><span><b>${esc(m.nome)}</b><small>CA ${m.ca} · PF ${m.pf} · GS ${m.gs}</small></span></button>`).join("") : `<p class="aiuto">Questa avventura non ha mostri: usa la «pedina libera» qui sotto.</p>`;
  $$("[data-mo]", best).forEach((b) => (b.onclick = () => aggiungiMostro(S.mostri[b.dataset.mo])));
}
function urlDoc(d) {
  const q = d.solo_master ? `?c=${encodeURIComponent(S.cred.id)}&s=${encodeURIComponent(S.cred.secret)}` : "";
  return `avventure/${S.avv.id}/documenti/${encodeURIComponent(d.file)}${q}`;
}
function disegnaDocumenti() {
  const box = $("#documenti");
  const l = S.avv?.documenti || [];
  box.innerHTML = `<p style="margin:0 0 6px"><b>${esc(S.avv?.titolo || "")}</b><br><span class="aiuto">${esc(S.avv?.descrizione || "")}</span></p>` +
    (l.length ? l.map((d) => `<a class="btn doc" target="_blank" rel="noopener" href="${urlDoc(d)}">${d.solo_master ? "🔒" : "📖"} ${esc(d.titolo)}</a>`).join("") : `<p class="aiuto">Nessun documento.</p>`);
}
function disegnaCatalogo() {
  const box = $("#m-avventure");
  if (!box || !S.st.catalogo) return;
  box.innerHTML = S.st.catalogo.map((a) => `<div class="avv ${a.id === S.st.attiva ? "attiva" : ""}">
    <div><b>${esc(a.titolo)}</b> ${a.id === S.st.attiva ? '<span class="chip attivo">in gioco</span>' : ""}<br>
    <small class="aiuto">${esc(a.sottotitolo || "")} · liv. ${esc(a.livello || "?")} · ${a.mappe} mappe · ${a.personaggi} personaggi</small></div>
    <div class="gruppo-btn">${a.id === S.st.attiva ? "" : `<button data-gioca="${a.id}" class="primario">▶ Gioca</button><button data-elimina="${a.id}" class="pericolo" title="Elimina dal server">🗑️</button>`}</div></div>`).join("") || `<p class="aiuto">Nessuna avventura sul server. Caricane una (.zip) qui sotto.</p>`;
  $$("[data-gioca]", box).forEach((b) => (b.onclick = () => conferma("La partita attuale resta salvata e la ritrovi quando ci torni.", { titolo: "Passare a questa avventura?", icona: "📚", ok: "Gioca" }).then((ok) => ok && op({ op: "avventura_attiva", id: b.dataset.gioca }))));
  $$("[data-elimina]", box).forEach((b) => (b.onclick = () => conferma("L'avventura e la sua partita salvata verranno cancellate dal server.", { titolo: "Eliminare l'avventura?", pericolo: true, ok: "Elimina" }).then((ok) => ok && op({ op: "avventura_elimina", id: b.dataset.elimina }))));
}
async function caricaBinario(url, file) {
  const q = `c=${encodeURIComponent(S.cred.id)}&s=${encodeURIComponent(S.cred.secret)}`;
  const r = await fetch(url + (url.includes("?") ? "&" : "?") + q, { method: "POST", body: file }).then((x) => x.json()).catch(() => ({ ok: false, errore: "caricamento non riuscito" }));
  if (!r.ok) avviso(r.errore || "Il caricamento non è riuscito.", { titolo: "Caricamento non riuscito" });
  return r;
}
function preparaMaster() {
  $("#av-carica").onclick = async () => {
    const f = $("#av-file").files[0];
    if (!f) { avviso("Scegli prima il file .zip dell'avventura con il pulsante accanto.", { titolo: "Manca il file", icona: "📦" }); return; }
    toast("Caricamento in corso…");
    const r = await caricaBinario("/api/carica_avventura", f);
    if (r.ok) { toast(`📚 «${r.titolo}» è sul server!`); $("#av-file").value = ""; }
  };

  $("#m-custom").onsubmit = (e) => {
    e.preventDefault();
    const pf = parseInt($("#mc-pf").value) || 0;
    nuovaPedina({ nome: $("#mc-nome").value || "Pedina", icona: $("#mc-icona").value || "🙂", colore: "#555", pf, pfmax: pf, tipo: "png" });
    $("#mc-nome").value = "";
  };
  $("#g-salva").onclick = () => op({ op: "griglia", id: S.st.scena, griglia: { cella: +$("#g-cella").value, ox: +$("#g-ox").value, oy: +$("#g-oy").value, mostra: $("#g-mostra").checked } });
  $("#up-invia").onclick = caricaMappa;
  let tN;
  $("#m-note").oninput = (e) => { clearTimeout(tN); tN = setTimeout(() => op({ op: "note_master", testo: e.target.value }), 700); };
  $("#m-esporta").onclick = (e) => { e.preventDefault(); location.href = `/api/esporta?c=${encodeURIComponent(S.cred.id)}&s=${encodeURIComponent(S.cred.secret)}`; };
  $("#m-importa").onchange = async (e) => {
    const f = e.target.files[0]; if (!f) return;
    if (!(await conferma("La partita attuale verrà sostituita da quella del file.", { titolo: "Caricare il salvataggio?", pericolo: true, ok: "Carica" }))) return;
    try { await api("/api/importa", JSON.parse(await f.text())); } catch (err) { avviso("Il file scelto non è un salvataggio del tavolo.", { titolo: "File non valido" }); }
  };
  $("#m-pulisci").onclick = () => conferma("Le pedine dei personaggi restano al loro posto.", { titolo: "Togliere i mostri da questa mappa?", icona: "🧹", ok: "Togli" }).then((ok) => ok && op({ op: "pulisci_scena" }));
  $("#m-svuota-log").onclick = () => conferma("Tutti i tiri e i messaggi della chat verranno cancellati per tutti.", { titolo: "Svuotare la cronologia?", pericolo: true, ok: "Svuota" }).then((ok) => ok && op({ op: "svuota_log" }));
  $("#m-reset").onclick = () => conferma("Si perdono pedine, nebbia, schede e cronologia di questa partita.", { titolo: "Ricominciare da zero?", pericolo: true, ok: "Ricomincia" }).then((ok) => ok && op({ op: "reset_partita" }));
  // nebbia
  $("#nb-attiva").onchange = (e) => op({ op: "nebbia", attiva: e.target.checked });
  $$("#nb-modo button").forEach((b) => (b.onclick = () => { S.nb.modo = b.dataset.m; $$("#nb-modo button").forEach((x) => x.classList.toggle("attivo", x === b)); }));
  $$("#nb-forma button").forEach((b) => (b.onclick = () => { S.nb.forma = b.dataset.f; $$("#nb-forma button").forEach((x) => x.classList.toggle("attivo", x === b)); }));
  $("#nb-copri-tutto").onclick = () => conferma("Tutte le zone già rivelate torneranno nascoste ai giocatori.", { titolo: "Coprire tutta la mappa?", icona: "🌫️", ok: "Copri tutto" }).then((ok) => ok && op({ op: "nebbia", azione: "copri_tutto" }));
  // iniziativa
  $("#ini-pross").onclick = () => op({ op: "iniziativa", azione: "prossimo" });
  $("#ini-prec").onclick = () => op({ op: "iniziativa", azione: "precedente" });
  $("#ini-svuota").onclick = () => conferma("L'ordine di iniziativa verrà svuotato.", { titolo: "Fine dello scontro?", icona: "⚔️", ok: "Termina" }).then((ok) => ok && op({ op: "iniziativa", azione: "svuota" }));
  $("#ini-mostri").onclick = () => {
    const gia = new Set(S.st.iniziativa.ordine.map((x) => x.pedina));
    Object.values(S.st.pedine).filter((p) => p.scena === S.st.scena && !p.pg && !gia.has(p.id)).forEach((p) => tiraIniziativaPedina(p));
  };
  $("#ini-form").onsubmit = (e) => {
    e.preventDefault();
    if (!$("#ini-nome").value) return;
    op({ op: "iniziativa", azione: "aggiungi", nome: $("#ini-nome").value, valore: +$("#ini-val").value || 0, colore: "#888" });
    $("#ini-nome").value = ""; $("#ini-val").value = "";
  };
}
function centroVista() {
  const vp = $("#viewport").getBoundingClientRect();
  return aMondo(vp.left + vp.width / 2, vp.top + vp.height / 2 - (innerWidth < 860 ? 25 : 0));
}
function nuovaPedina(d) {
  const c = centroVista();
  const cel = cellaPx();
  const t = d.taglia || 1;
  S.pendenti = (S.pendenti || []).filter((q) => performance.now() - q.t < 3000);
  const occupate = Object.values(S.st.pedine).filter((p) => p.scena === S.st.scena).map((p) => ({ ...posPedina(p), r: (p.taglia || 1) * cel / 2 })).concat(S.pendenti);
  let pos = aggancia(c.x, c.y, t);
  cerca: for (let r = 0; r < 12; r++) {
    for (let i = -r; i <= r; i++) for (let j = -r; j <= r; j++) {
      if (Math.max(Math.abs(i), Math.abs(j)) !== r) continue;
      const q = aggancia(c.x + i * cel, c.y + j * cel, t);
      if (occupate.every((o) => Math.max(Math.abs(o.x - q.x), Math.abs(o.y - q.y)) >= o.r + t * cel / 2 - 1)) { pos = q; break cerca; }
    }
  }
  S.pendenti.push({ x: pos.x, y: pos.y, r: t * cel / 2, t: performance.now() });
  op({ op: "pedina_salva", pedina: { taglia: 1, condizioni: [], scena: S.st.scena, nascosta: $("#m-nascosto").checked, ...d, x: pos.x, y: pos.y } });
}
function aggiungiMostro(m) {
  const stessi = Object.values(S.st.pedine).filter((p) => p.mostro === m.id).length;
  nuovaPedina({ nome: stessi ? `${m.nome} ${stessi + 1}` : m.nome, icona: m.icona, colore: m.colore, pf: m.pf, pfmax: m.pf, ca: m.ca, taglia: m.taglia || 1, tipo: m.alleato ? "alleato" : "mostro", mostro: m.id });
}
async function caricaMappa() {
  const f = $("#up-file").files[0];
  if (!f) { avviso("Scegli prima l'immagine della mappa con il pulsante accanto.", { titolo: "Manca il file", icona: "🗺️" }); return; }
  const titolo = $("#up-titolo").value || f.name.replace(/\.\w+$/, "");
  const cella = +$("#up-cella").value || 0;
  const r = await caricaBinario(`/api/carica_mappa?nome=${encodeURIComponent(f.name)}&titolo=${encodeURIComponent(titolo)}&cella=${cella}`, f);
  if (r.ok) { toast("🗺️ Mappa aggiunta all'avventura (gruppo «Caricate»)"); $("#up-file").value = ""; }
}

/* ============================================================ sala d'attesa / tavolo chiuso */
function disegnaSala() {
  const box = $("#sala");
  const st = S.st.sessione || "chiusa";
  const master = S.me.role === "master";
  const admin = !!S.me.admin && !S.me.sistema;
  if (S.me.sistema) {
    box.hidden = true;
    $("#btn-pausa").hidden = true;
    $("#nome-scena").textContent = "⚙️ Amministrazione";
    const tab = $('#schede-nav [data-tab="impostazioni"]');
    if (!tab.classList.contains("attivo")) tab.click();
    return;
  }
  if (st === "in_corso") { box.hidden = true; $("#btn-pausa").hidden = !master; return; }
  box.hidden = false;
  $("#btn-pausa").hidden = true;
  const online = (S.st.online || []).filter((u) => !u.sistema); // l'account di sistema non gioca
  const ilMaster = online.find((u) => u.role === "master");
  const persone = online.map((u) => {
    const pg = u.char && S.pg[u.char] ? `${S.pg[u.char].icona} ${esc(S.pg[u.char].nome)}` : u.admin ? "🔑 admin" : (st === "chiusa" ? "in attesa" : "sceglie il personaggio…");
    const io = u.id === S.me.id ? " <small>(tu)</small>" : "";
    const ruolo = u.role === "master" ? '<span class="chip attivo">👑 Master</span>' : `<span class="aiuto">${pg}</span>`;
    const azione = admin ? (u.role === "master"
      ? `<button class="link" data-nomina="${u.id}" data-togli="1" title="Togli il ruolo di Master">togli</button>`
      : `<button data-nomina="${u.id}" title="Fai condurre la partita a questa persona">👑 Rendi Master</button>`) : "";
    return `<li class="persona" style="--c:${esc(u.color)}">${u.avatar ? `<img src="${esc(u.avatar)}" alt="">` : '<span class="pallino"></span>'}<span class="nome"><b>${esc(u.name)}</b>${io}<br>${ruolo}</span>${azione}</li>`;
  }).join("");
  let h = "";
  if (admin) {
    const cat = S.st.catalogo || [];
    const titolo = st === "chiusa" ? "🛋️ Sala d'attesa" : esc(S.avv?.titolo || "");
    h = `<h2>${titolo}</h2>
      <div class="sala-passi">
        <section><h3>1 · Avventura</h3>${st === "chiusa"
          ? `<div class="sala-avv">${cat.map((a) => `<button data-apri="${a.id}" class="${a.id === S.st.attiva ? "attivo" : ""}"><b>${esc(a.titolo)}</b><small>${esc(a.sottotitolo || "")} · liv. ${esc(a.livello || "?")} · ${a.personaggi} personaggi</small></button>`).join("") || "<p>Nessuna avventura: caricane una dal pannello 👑 Master.</p>"}</div>`
          : `<p>✅ <b>${esc(S.avv?.titolo || "")}</b> · i giocatori stanno scegliendo il personaggio. <button class="link" id="sala-chiudi">chiudi e cambia</button></p>`}</section>
        <section><h3>2 · Chi fa il Master?</h3><ul class="online persone">${persone || "<li class='aiuto'>Nessuno collegato.</li>"}</ul>
          <p class="aiuto">${ilMaster ? `Master: <b>${esc(ilMaster.name)}</b>` : "Premi «👑 Rendi Master» accanto alla persona che condurrà la partita (anche te stesso)."}</p></section>
        <section><h3>3 · Si parte</h3>
          <button id="sala-inizia" class="primario grande" ${st === "chiusa" || !ilMaster ? "disabled" : ""}>▶ Inizia la partita</button>
          <p class="aiuto">${st === "chiusa" ? "Prima scegli l'avventura." : !ilMaster ? "Prima scegli il Master." : "Quando tutti hanno scelto il personaggio."}</p></section>
      </div>`;
  } else if (st === "chiusa") {
    h = `${passiSala(1)}<h2>🛋️ Sala d'attesa</h2>
      <div class="sala-msg">⏳ <b>Sei dentro!</b><br>L'amministratore sta preparando la partita.<br>Appena sceglie l'avventura, <b>qui</b> potrai scegliere il tuo personaggio.</div>
      <h3>Chi c'è</h3><ul class="online persone">${persone}</ul>`;
  } else if (master) {
    h = `<h2>${esc(S.avv?.titolo || "")}</h2><p>👑 <b>Sei il Master!</b> Quando tutti hanno scelto il personaggio, fai iniziare la partita.</p><ul class="online persone">${persone}</ul>
      <button id="sala-inizia" class="primario grande">▶ Inizia la partita</button>`;
  } else {
    h = salaGiocatore(online, ilMaster, persone);
  }
  box.innerHTML = `<div class="card sala-card">${h}</div>`;
  $$("[data-apri]", box).forEach((b) => (b.onclick = () => op({ op: "sessione_apri", id: b.dataset.apri })));
  $$("[data-nomina]", box).forEach((b) => (b.onclick = () => op({ op: "nomina_master", id: b.dataset.nomina, master: !b.dataset.togli })));
  $$("[data-anteprima]", box).forEach((b) => (b.onclick = () => { S.anteprima = b.dataset.anteprima; disegnaSala(); $("#sala-anteprima")?.scrollIntoView({ behavior: "smooth", block: "nearest" }); }));
  $("#sala-annulla")?.addEventListener("click", () => { S.anteprima = null; disegnaSala(); });
  $("#sala-cambia")?.addEventListener("click", () => { S.cambiaPg = true; S.anteprima = null; disegnaSala(); });
  $("#sala-conferma")?.addEventListener("click", async (e) => {
    const pg = e.currentTarget.dataset.pg;
    const r = await op({ op: "scegli_pg", pg });
    if (r.ok) {
      S.me.char = pg; S.cred.personaggio = pg; salvaCred(); S.schedaVista = pg;
      S.anteprima = null; S.cambiaPg = false;
      disegnaScheda(); disegnaSala();
      toast(`✅ Giocherai con ${S.pg[pg].nome}!`);
    }
  });
  $("#sala-inizia")?.addEventListener("click", () => op({ op: "sessione_inizia" }));
  $("#sala-chiudi")?.addEventListener("click", () => conferma("La partita resta salvata: potrai riaprirla quando vuoi.", { titolo: "Chiudere e cambiare avventura?", icona: "🔒", ok: "Chiudi il tavolo" }).then((ok) => ok && op({ op: "sessione_chiudi" })));
}

function passiSala(n) {
  const passi = ["Accesso", "Personaggio", "Inizio partita"];
  return `<ol class="passi">${passi.map((t, k) => `<li class="${k < n ? "fatto" : k === n ? "ora" : ""}"><span>${k < n ? "✓" : k + 1}</span>${t}</li>`).join("")}</ol>`;
}

function cartaPg(p, opz = {}) {
  return `<button class="carta-pg ${opz.attiva ? "attiva" : ""} ${opz.presa ? "presa" : ""}" ${opz.presa ? "disabled" : `data-anteprima="${p.id}"`} style="--c:${esc(p.colore || "#888")}">
    <span class="ic">${p.icona}</span>
    <span class="testo"><b>${esc(p.nome)}</b><small>${esc(p.razza)} · ${esc(p.classe)}</small>
      ${p.sottotitolo ? `<em>${esc(p.sottotitolo)}</em>` : ""}
      <span class="stat">🛡️ CA ${p.ca} · ❤️ PF ${p.pf}</span></span>
    ${opz.presa ? `<span class="badge">preso da ${esc(opz.presa)}</span>` : ""}</button>`;
}

function salaGiocatore(online, ilMaster, persone) {
  const presi = {};
  online.forEach((u) => { if (u.char && u.id !== S.me.id) presi[u.char] = u.name; });
  const pgs = Object.values(S.pg);
  const masterTxt = ilMaster ? `👑 Il Master è <b>${esc(ilMaster.name)}</b>.` : "👑 Il Master non è ancora stato scelto.";
  // già scelto: si aspetta
  if (S.me.char && S.pg[S.me.char] && !S.cambiaPg) {
    const p = S.pg[S.me.char];
    return `${passiSala(2)}<h2>✅ Sei pronto!</h2>
      <p>Giocherai con:</p>
      <div class="pg-scelto" style="--c:${esc(p.colore || "#888")}"><span class="ic">${p.icona}</span><div><b>${esc(p.nome)}</b><small>${esc(p.razza)} · ${esc(p.classe)}</small></div></div>
      <div class="sala-msg">⏳ Aspetta che il Master faccia iniziare la partita.<br>${masterTxt}<br><small>Quando la partita inizia, la tua scheda completa è nella scheda 📜 in basso: lì tocchi abilità e attacchi per tirare i dadi.</small></div>
      <button class="link" id="sala-cambia">↩ cambia personaggio</button>
      <h3>Al tavolo</h3><ul class="online persone">${persone}</ul>`;
  }
  if (!pgs.length) {
    return `${passiSala(2)}<h2>${esc(S.avv?.titolo || "")}</h2><div class="sala-msg">Questa avventura non ha personaggi pronti: giocherai come spettatore.<br>${masterTxt}</div><ul class="online persone">${persone}</ul>`;
  }
  const a = S.anteprima && S.pg[S.anteprima];
  const dettaglio = a ? `<div id="sala-anteprima" class="anteprima" style="--c:${esc(a.colore || "#888")}">
      <div class="testa"><span class="ic">${a.icona}</span><div><b>${esc(a.nome)}</b><small>${esc(a.razza)} · ${esc(a.classe)}</small></div></div>
      <p>${esc(a.chi || "")}</p>
      ${a.personalita ? `<p><b>Carattere:</b> ${esc(a.personalita)}</p>` : ""}
      ${a.consiglio ? `<p class="aiuto">💡 ${esc(a.consiglio)}</p>` : ""}
      <div class="gruppo-btn"><button id="sala-conferma" class="primario grande" data-pg="${a.id}">✓ Gioco con ${esc(a.nome.split(" ")[0])}</button><button class="link" id="sala-annulla">guarda gli altri</button></div>
    </div>` : "";
  return `${passiSala(1)}<h2>🎭 Scegli il tuo personaggio</h2>
    <p class="aiuto">${esc(S.avv?.titolo || "")} · ${masterTxt}<br><b>Tocca una carta</b> per leggere chi è, poi conferma.</p>
    ${dettaglio}
    <div class="carte-pg">${pgs.map((p) => cartaPg(p, { attiva: S.anteprima === p.id, presa: presi[p.id] })).join("")}</div>
    <h3>Al tavolo</h3><ul class="online persone">${persone}</ul>`;
}

/* ============================================================ impostazioni (admin) */
async function disegnaImpostazioni() {
  if (!S.me?.sistema) return;
  const r = await op({ op: "imp_leggi" });
  if (!r.ok) return;
  const c = r.config;
  S.imp = c;
  $("#i-nome").value = c.nome_tavolo; $("#i-url").value = c.public_url; $("#i-ospiti").checked = c.ospiti; $("#i-pwg").value = c.password_giocatori;
  $("#i-adm-utente").value = c.admin_utente;
  const base = c.public_url || location.origin;
  $("#i-oauth").innerHTML = Object.entries(c.oauth).map(([k, v]) => `<div class="prov" data-prov="${k}">
    <label class="switch"><input type="checkbox" data-k="attivo" ${v.attivo ? "checked" : ""}> <span class="logo-prov ${k}">${LOGHI[k] || ""}</span><b>${esc(v.nome)}</b> ${v.attivo && v.id && v.secret_impostato ? '<span class="chip attivo">attivo</span>' : ""}</label>
    <label>Client ID<input data-k="id" name="oauth-id-${k}" value="${esc(v.id)}" autocomplete="off"></label>
    <label>Client Secret<input data-k="secret" name="oauth-secret-${k}" type="text" class="segreto" placeholder="${v.secret_impostato ? "•••••• (impostato: scrivi solo per cambiarlo)" : "incolla qui il secret"}" autocomplete="off" spellcheck="false"></label>
    <span class="aiuto">Redirect URI da registrare su <a href="${esc(v.console)}" target="_blank" rel="noopener">${esc(v.nome)}</a>:</span>
    <code>${esc(base)}/auth/${k}/callback</code></div>`).join("");
  const quando = (t) => (t ? new Date(t * 1000).toLocaleString("it-IT", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "—");
  $("#i-utenti").innerHTML = r.utenti.map((x) => `<div class="utente">${x.avatar ? `<img src="${esc(x.avatar)}" alt="">` : '<span class="av">👤</span>'}
    <div class="n"><b>${esc(x.nome)}</b>${x.io ? " (tu)" : ""} ${x.online ? "🟢" : ""}<small>${esc(x.provider)}${x.account ? " · " + esc(x.account) : ""} · visto ${quando(x.visto)}</small></div>
    <label class="switch" title="Può entrare come Master"><input type="checkbox" data-master="${x.id}" ${x.master ? "checked" : ""} ${x.admin ? "disabled" : ""}> Master</label>
    ${x.io ? "" : `<label class="switch" title="Può cambiare le impostazioni"><input type="checkbox" data-admin="${x.id}" ${x.admin ? "checked" : ""}> Admin</label><button class="link" data-del="${x.id}" title="Elimina">🗑️</button>`}</div>`).join("");
  $$("[data-master]").forEach((cb) => (cb.onchange = () => op({ op: "imp_utente", id: cb.dataset.master, master: cb.checked })));
  $$("[data-admin]").forEach((cb) => (cb.onchange = async () => { await op({ op: "imp_utente", id: cb.dataset.admin, admin: cb.checked }); disegnaImpostazioni(); }));
  const rp = await op({ op: "imp_partite" });
  if (rp.ok) {
    const q = `c=${encodeURIComponent(S.cred.id)}&s=${encodeURIComponent(S.cred.secret)}`;
    $("#i-partite").innerHTML = rp.partite.length ? rp.partite.map((x) => `<div class="utente"><span class="av">📜</span><div class="n"><b>${esc(x.titolo)}</b>${x.in_gioco ? ' <span class="chip attivo">in gioco</span>' : ""}<small>salvata ${quando(x.aggiornata)} · ${x.pedine} pedine · ${x.tiri} tiri · round ${x.round}</small></div>
      <a class="btn" href="/api/esporta?id=${encodeURIComponent(x.id)}&${q}" title="Scarica">⬇️</a><button class="link" data-azzera="${esc(x.id)}" title="Ricomincia da zero">♻️</button></div>`).join("") : '<p class="aiuto">Nessuna partita salvata.</p>';
    $$("[data-azzera]").forEach((b) => (b.onclick = async () => { if (await conferma("Pedine, nebbia, schede e cronologia verranno cancellate.", { titolo: "Azzerare questa partita?", pericolo: true, ok: "Azzera" })) { await op({ op: "imp_partita_azzera", id: b.dataset.azzera }); disegnaImpostazioni(); } }));
    $("#i-backup").href = `/api/backup?${q}`;
  }
  $$("[data-del]").forEach((b) => (b.onclick = async () => { if (await conferma("Dovrà rifare l'accesso da capo.", { titolo: "Eliminare questo utente?", pericolo: true, ok: "Elimina" })) { await op({ op: "imp_utente", id: b.dataset.del, elimina: true }); disegnaImpostazioni(); } }));
}
function preparaImpostazioni() {
  $("#i-salva").onclick = async () => {
    const oauth = {};
    $$("#i-oauth .prov").forEach((d) => {
      oauth[d.dataset.prov] = { attivo: $('[data-k="attivo"]', d).checked, id: $('[data-k="id"]', d).value.trim(), secret: $('[data-k="secret"]', d).value.trim() };
    });
    const r = await op({ op: "imp_salva", config: { nome_tavolo: $("#i-nome").value, public_url: $("#i-url").value.trim(), ospiti: $("#i-ospiti").checked, password_giocatori: $("#i-pwg").value, oauth } });
    if (r.ok) { toast("💾 Impostazioni salvate"); disegnaImpostazioni(); }
  };
  $("#i-adm-salva").onclick = async () => {
    const nuova = $("#i-adm-nuova").value;
    if (nuova && nuova !== $("#i-adm-nuova2").value) { avviso("Scrivi la stessa nuova password in tutti e due i campi.", { titolo: "Le password non coincidono", icona: "🔑" }); return; }
    if (!$("#i-adm-attuale").value) { avviso("Per sicurezza, per cambiare utente o password serve la password attuale.", { titolo: "Manca la password attuale", icona: "🔑" }); return; }
    const r = await op({ op: "imp_admin", utente: $("#i-adm-utente").value, nuova, attuale: $("#i-adm-attuale").value });
    if (r.ok) { toast("✅ Account admin aggiornato"); ["#i-adm-nuova", "#i-adm-nuova2", "#i-adm-attuale"].forEach((q) => ($(q).value = "")); }
  };
}

/* ============================================================ UI generale */
function preparaUI() {
  $$("#schede-nav button").forEach((b) => (b.onclick = () => {
    $$("#schede-nav button").forEach((x) => x.classList.toggle("attivo", x === b));
    $$(".tab").forEach((t) => t.classList.toggle("attivo", t.id === "tab-" + b.dataset.tab));
    if (innerWidth < 860) $("#laterale").classList.add("aperto");
    if (b.dataset.tab === "impostazioni") disegnaImpostazioni();
  }));
  $("#btn-esci").onclick = () => conferma("Potrai rientrare quando vuoi.", { titolo: "Uscire dal tavolo?", icona: "🚪", ok: "Esci" }).then((ok) => ok && esci());
  $("#btn-logout").onclick = () => conferma("Potrai rientrare quando vuoi.", { titolo: `Uscire${S.me?.name ? " da «" + S.me.name + "»" : ""}?`, icona: "🚪", ok: "Esci" }).then((ok) => ok && esci());
  $("#btn-pausa").onclick = () => conferma("La mappa si chiude per tutti finché non riprendi la partita.", { titolo: "Pausa: tutti in sala d'attesa?", icona: "⏸", ok: "Metti in pausa" }).then((ok) => ok && op({ op: "sessione_pausa" }));
  $("#m-chiudi").onclick = () => conferma("La partita resta salvata e i giocatori tornano nella sala d'attesa.", { titolo: "Chiudere il tavolo?", icona: "🔒", ok: "Chiudi il tavolo" }).then((ok) => ok && op({ op: "sessione_chiudi" }));
  preparaImpostazioni();
  $$("#strumenti [data-tool]").forEach((b) => (b.onclick = () => strumento(b.dataset.tool)));
  $("#zoom-piu").onclick = () => zoom(1.25);
  $("#zoom-meno").onclick = () => zoom(0.8);
  $("#zoom-adatta").onclick = adattaVista;
  $("#btn-suono").onclick = () => { S.suono = !S.suono; $("#btn-suono").textContent = S.suono ? "🔊" : "🔇"; try { localStorage.setItem("tv_suono", S.suono ? "1" : "0"); } catch (e) { /* */ } };
  $("#btn-pannello").onclick = () => $("#laterale").classList.toggle("aperto");
  $("#schede-nav").addEventListener("dblclick", () => innerWidth < 860 && $("#laterale").classList.remove("aperto"));
  $("#chat-form").onsubmit = (e) => {
    e.preventDefault();
    const t = $("#chat-in").value.trim();
    if (!t) return;
    const m = t.match(/^\/(r|roll|tira)\s+(.+)$/i);
    if (m) tiro(m[2], "", { segreto: $("#tiro-segreto").checked, chiudi: false });
    else op({ op: "chat", testo: t, segreto: $("#tiro-segreto").checked });
    $("#chat-in").value = "";
  };
  $("#ini-tira").onclick = () => {
    const ped = Object.values(S.st.pedine).find((x) => x.pg && x.pg === S.me.char);
    if (ped) tiraIniziativaPedina(ped);
    else if (S.me.role === "master") $("#ini-mostri").click();
    else tiro(d20(0), "Iniziativa").then((r) => r?.ok && op({ op: "iniziativa", azione: "aggiungi", nome: S.me.name, valore: r.tiro.totale }));
  };
  document.addEventListener("keydown", (e) => {
    if (e.target.closest("input,textarea,select")) return;
    const k = e.key.toLowerCase();
    if (k === "v") strumento("muovi");
    else if (k === "r") strumento("righello");
    else if (k === "p") strumento("ping");
    else if (k === "f" && S.me?.role === "master") strumento("nebbia");
    else if (k === "+" || k === "=") zoom(1.2);
    else if (k === "-") zoom(1 / 1.2);
    else if (k === "0") adattaVista();
    else if (k === "escape") seleziona(null);
    else if ((k === "delete" || k === "backspace") && S.sel && S.me.role === "master") { op({ op: "pedina_elimina", id: S.sel }); seleziona(null); }
    else if (k.startsWith("arrow") && S.sel) {
      const p = S.st.pedine[S.sel];
      if (!p || !puoMuovere(p)) return;
      e.preventDefault();
      const c = cellaPx(), pos = posPedina(p);
      const d = { arrowup: [0, -1], arrowdown: [0, 1], arrowleft: [-1, 0], arrowright: [1, 0] }[k];
      const a = aggancia(pos.x + d[0] * c, pos.y + d[1] * c, p.taglia);
      p.x = a.x; p.y = a.y; disegnaPedina(p);
      op({ op: "pedina_muovi", id: p.id, x: a.x, y: a.y, finale: true });
    }
  });
  preparaMappa();
  preparaDadi();
  preparaMaster();
}
function strumento(t) {
  S.tool = t;
  $$("#strumenti [data-tool]").forEach((b) => b.classList.toggle("attivo", b.dataset.tool === t));
  $("#viewport").className = "tool-" + t;
  $("#nebbia-strumenti").hidden = !(t === "nebbia" && S.me?.role === "master");
  if (t === "nebbia") seleziona(null);
}

avvio();
