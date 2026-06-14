import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.4/firebase-app.js";
import {
  getFirestore,
  collection,
  getDocs
} from "https://www.gstatic.com/firebasejs/10.12.4/firebase-firestore.js";

/* Projet Firebase FR */
const firebaseFrConfig = {
  apiKey: " AIzaSyBTQEl7BVMYcpD4XLjL7hsNUo74MSGaaUI",
  authDomain: "https://dico-fr-arameen.firebaseio.com/",
  projectId: "test"
};

/* Projet Firebase EN */
const firebaseEnConfig = {
  apiKey: "AIzaSyBTQEl7BVMYcpD4XLjL7hsNUo74MSGaaUI",
  authDomain: "https://dico-fr-arameen.firebaseio.com/",
  projectId: "English"
};

const appFr = initializeApp(firebaseFrConfig, "fr");
const appEn = initializeApp(firebaseEnConfig, "en");

const dbFr = getFirestore(appFr);
const dbEn = getFirestore(appEn);

const input = document.getElementById("searchInput");
const resultsEl = document.getElementById("results");
const statusEl = document.getElementById("status");
const buttons = document.querySelectorAll(".filters button");

let dictionary = [];
let currentLang = "both";

function getValue(data, keys) {
  for (const k of keys) {
    if (data[k]) return data[k];
  }
  return "";
}

async function loadDictionary() {
  const all = [];

  const frSnap = await getDocs(collection(dbFr, "test"));
  frSnap.forEach((doc) => {
    const d = doc.data();
    all.push({
      id: "fr-" + doc.id,
      term: getValue(d, ["term", "ar", "he", "aramic", "arameen"]) || doc.id,
      aramic: getValue(d, ["aramic", "arameen", "hebrew", "he", "term"]) || doc.id,
      fr: getValue(d, ["fr", "french", "translation", "traduction"]),
      en: "",
      source: "Français"
    });
  });

  const enSnap = await getDocs(collection(dbEn, "English"));
  enSnap.forEach((doc) => {
    const d = doc.data();
    all.push({
      id: "en-" + doc.id,
      term: getValue(d, ["term", "ar", "he", "aramic", "arameen"]) || doc.id,
      aramic: getValue(d, ["aramic", "arameen", "hebrew", "he", "term"]) || doc.id,
      fr: "",
      en: getValue(d, ["en", "english", "translation"]),
      source: "English"
    });
  });

  dictionary = mergeEntries(all);
  statusEl.textContent = `${dictionary.length} entrées chargées`;
}

function mergeEntries(items) {
  const map = new Map();

  for (const item of items) {
    const key = item.term || item.aramic;
    if (!map.has(key)) {
      map.set(key, { ...item });
    } else {
      const old = map.get(key);
      map.set(key, {
        ...old,
        fr: old.fr || item.fr,
        en: old.en || item.en
      });
    }
  }

  return Array.from(map.values());
}

function render() {
  const q = input.value.trim().toLowerCase();
  resultsEl.innerHTML = "";

  if (!q) return;

  const results = dictionary
    .filter((item) =>
      `${item.term} ${item.aramic} ${item.fr} ${item.en}`
        .toLowerCase()
        .includes(q)
    )
    .slice(0, 80);

  statusEl.textContent = `${results.length} résultat(s)`;

  if (results.length === 0) {
    resultsEl.innerHTML = `<div class="card">Aucune traduction trouvée.</div>`;
    return;
  }

  for (const item of results) {
    const card = document.createElement("div");
    card.className = "card";

    card.innerHTML = `
      <div class="term">${escapeHtml(item.aramic || item.term)}</div>
      ${(currentLang === "fr" || currentLang === "both") && item.fr
        ? `<div class="line"><b>Français :</b> ${escapeHtml(item.fr)}</div>`
        : ""}
      ${(currentLang === "en" || currentLang === "both") && item.en
        ? `<div class="line"><b>English :</b> ${escapeHtml(item.en)}</div>`
        : ""}
      <span class="tag">${escapeHtml(item.source || "Firebase")}</span>
    `;

    resultsEl.appendChild(card);
  }
}

function escapeHtml(str) {
  return String(str || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

buttons.forEach((btn) => {
  btn.addEventListener("click", () => {
    buttons.forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    currentLang = btn.dataset.lang;
    render();
  });
});

input.addEventListener("input", render);

loadDictionary().catch((err) => {
  console.error(err);
  statusEl.textContent = "Erreur Firebase. Vérifie la configuration.";
});
