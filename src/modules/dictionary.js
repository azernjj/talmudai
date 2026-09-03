import { state } from '../state.js'
import { cleanText, escapeHtml } from './utils.js'

import { initializeApp, getApps } from 'https://www.gstatic.com/firebasejs/10.12.4/firebase-app.js'
import {
  getFirestore,
  collection,
  onSnapshot
} from 'https://www.gstatic.com/firebasejs/10.12.4/firebase-firestore.js'


/* =========================================================
   FIREBASE
   ========================================================= */

/* Base française */
const firebaseFrConfig = {
  apiKey: 'AIzaSyBTQEl7BVMYcpD4XLjL7hsNUo74MSGaaUI',
  authDomain: 'dico-fr-arameen.firebaseio.com',
  projectId: 'test'
}

/* Base anglaise */
const firebaseEnConfig = {
  apiKey: 'AIzaSyBTQEl7BVMYcpD4XLjL7hsNUo74MSGaaUI',
  authDomain: 'dico-fr-arameen.firebaseio.com',
  projectId: 'English'
}

let firebaseInitialized = false
let dbFr = null
let dbEn = null

let unsubscribeFr = null
let unsubscribeEn = null

let firebaseFrItems = []
let firebaseEnItems = []


function initFirebase() {
  if (firebaseInitialized) return

  const existingApps = getApps()

  let appFr = existingApps.find(app => app.name === 'talmud-dict-fr')
  let appEn = existingApps.find(app => app.name === 'talmud-dict-en')

  if (!appFr) {
    appFr = initializeApp(firebaseFrConfig, 'talmud-dict-fr')
  }

  if (!appEn) {
    appEn = initializeApp(firebaseEnConfig, 'talmud-dict-en')
  }

  dbFr = getFirestore(appFr)
  dbEn = getFirestore(appEn)

  firebaseInitialized = true
}


/* =========================================================
   OUVERTURE / FERMETURE
   ========================================================= */

export function openDictionary(initialSearch = '') {
  document.querySelector('#dictionaryPanel')?.classList.remove('hidden')
  document.querySelector('#dictOverlay')?.classList.remove('hidden')

  const input = document.querySelector('#dictSearch')

  if (input) {
    input.value = initialSearch || ''
    input.focus()
    input.select()
  }

  if (!state.dictionaryLoaded) {
    loadDictionary()
  } else {
    renderDictionaryResults()
  }
}


export function closeDictionary() {
  document.querySelector('#dictionaryPanel')?.classList.add('hidden')
  document.querySelector('#dictOverlay')?.classList.add('hidden')
}


/* =========================================================
   UTILITAIRES FIREBASE
   ========================================================= */

function getValue(data, keys) {
  for (const key of keys) {
    if (
      Object.prototype.hasOwnProperty.call(data, key) &&
      data[key] !== null &&
      data[key] !== undefined &&
      data[key] !== ''
    ) {
      return data[key]
    }
  }

  return ''
}


function firestoreDocToItem(doc, language) {
  const data = doc.data() || {}

  const term =
    getValue(data, [
      'term',
      'ar',
      'he',
      'aramic',
      'arameen',
      'hebrew',
      'word'
    ]) || doc.id

  const aramic =
    getValue(data, [
      'aramic',
      'arameen',
      'hebrew',
      'he',
      'term',
      'ar',
      'word'
    ]) || term

  if (language === 'fr') {
    return {
      term: cleanText(term),
      aramic: cleanText(aramic),
      fr: cleanText(
        getValue(data, [
          'fr',
          'french',
          'translation',
          'traduction'
        ])
      ),
      en: '',
      category: 'Firebase Français'
    }
  }

  return {
    term: cleanText(term),
    aramic: cleanText(aramic),
    fr: '',
    en: cleanText(
      getValue(data, [
        'en',
        'english',
        'translation',
        'traduction'
      ])
    ),
    category: 'Firebase English'
  }
}


/* =========================================================
   SYNCHRONISATION FIREBASE TEMPS RÉEL
   ========================================================= */

function refreshFirebaseDictionary() {
  const merged = mergeDictionaryItems([
    ...firebaseFrItems,
    ...firebaseEnItems
  ])

  state.dictionaryItems = merged
  state.dictionaryLoaded = true

  const status = document.querySelector('#dictStatus')

  if (status) {
    status.textContent =
      `${state.dictionaryItems.length} entrées Firebase chargées.`
  }

  renderDictionaryResults()
}


function startFirebaseListeners() {
  initFirebase()

  /*
   * On évite de créer plusieurs écouteurs si le dictionnaire
   * est ouvert plusieurs fois.
   */
  if (!unsubscribeFr) {
    unsubscribeFr = onSnapshot(
      collection(dbFr, 'test'),

      snapshot => {
        firebaseFrItems = []

        snapshot.forEach(doc => {
          firebaseFrItems.push(
            firestoreDocToItem(doc, 'fr')
          )
        })

        refreshFirebaseDictionary()
      },

      error => {
        console.error(
          'Erreur Firebase dictionnaire français :',
          error
        )
      }
    )
  }


  if (!unsubscribeEn) {
    unsubscribeEn = onSnapshot(
      collection(dbEn, 'English'),

      snapshot => {
        firebaseEnItems = []

        snapshot.forEach(doc => {
          firebaseEnItems.push(
            firestoreDocToItem(doc, 'en')
          )
        })

        refreshFirebaseDictionary()
      },

      error => {
        console.error(
          'Erreur Firebase dictionnaire anglais :',
          error
        )
      }
    )
  }
}


/* =========================================================
   CHARGEMENT PRINCIPAL
   ========================================================= */

export async function loadDictionary() {
  const status = document.querySelector('#dictStatus')

  if (status) {
    status.textContent =
      'Connexion au dictionnaire Firebase...'
  }

  try {
    startFirebaseListeners()

    /*
     * onSnapshot est asynchrone.
     * Le premier snapshot remplira automatiquement
     * state.dictionaryItems.
     */
    return

  } catch (error) {

    console.error(
      'Firebase indisponible, utilisation du dictionnaire local :',
      error
    )

    if (status) {
      status.textContent =
        'Firebase indisponible. Chargement du dictionnaire local...'
    }

    await loadLocalDictionary()
  }
}


/* =========================================================
   FALLBACK : DICTIONNAIRE JSON LOCAL
   ========================================================= */

async function loadLocalDictionary() {
  const status = document.querySelector('#dictStatus')

  const paths = [
    '/data/dictionary/dictionary.json',
    '/dictionary/dictionary.json',
    '/data/dictionnaire/dictionary.json',
    '/data/dictionary.json',
    '/dictionary.json'
  ]

  let lastError = ''

  for (const url of paths) {
    try {
      const response = await fetch(url, {
        cache: 'no-store'
      })

      if (!response.ok) {
        lastError = `${url} : ${response.status}`
        continue
      }

      const raw = await response.json()

      state.dictionaryItems =
        normalizeDictionaryJson(raw)

      state.dictionaryLoaded = true

      if (status) {
        status.textContent =
          `${state.dictionaryItems.length} entrées locales chargées.`
      }

      renderDictionaryResults()

      return

    } catch (error) {
      lastError = `${url} : ${error.message}`
    }
  }

  if (status) {
    status.textContent =
      'Dictionnaire introuvable. Dernier essai : ' +
      lastError
  }
}


/* =========================================================
   NORMALISATION DU JSON LOCAL
   ========================================================= */

function normalizeDictionaryJson(raw) {
  const items = []

  if (Array.isArray(raw)) {

    raw.forEach(value => {
      if (!value || typeof value !== 'object') return

      const term =
        value.term ||
        value.aramic ||
        value.he ||
        value.hebrew ||
        value.word ||
        ''

      items.push({
        term: cleanText(term),

        aramic: cleanText(
          value.aramic ||
          value.hebrew ||
          value.he ||
          term
        ),

        fr: cleanText(
          value.fr ||
          value.french ||
          value.traduction ||
          ''
        ),

        en: cleanText(
          value.en ||
          value.english ||
          ''
        ),

        category:
          value.category ||
          'Dictionnaire'
      })
    })

    return mergeDictionaryItems(items)
  }


  for (const [category, entries] of Object.entries(raw || {})) {

    if (!entries || typeof entries !== 'object') {
      continue
    }

    for (const [term, value] of Object.entries(entries)) {

      const parsed =
        parseDictionaryValue(value, category)

      items.push({
        term: cleanText(term),

        aramic: cleanText(
          parsed.aramic || term
        ),

        fr: cleanText(parsed.fr),

        en: cleanText(parsed.en),

        category
      })
    }
  }

  return mergeDictionaryItems(items)
}


function isEnglishCategory(category = '') {
  const value =
    String(category).toLowerCase()

  return (
    value === 'english' ||
    value.includes('eng')
  )
}


function parseDictionaryValue(value, category = '') {
  const english =
    isEnglishCategory(category)

  if (Array.isArray(value)) {
    return {
      aramic: value[0] || '',

      fr: english
        ? ''
        : (value[2] || value[1] || ''),

      en: english
        ? (value[2] || value[1] || '')
        : (value[1] || '')
    }
  }


  if (value && typeof value === 'object') {
    return {
      aramic:
        value.aramic ||
        value.hebrew ||
        value.he ||
        value.term ||
        '',

      fr: english
        ? ''
        : (
          value.fr ||
          value.french ||
          value.traduction ||
          value.translation ||
          ''
        ),

      en:
        value.en ||
        value.english ||
        (
          english
            ? value.translation || ''
            : ''
        )
    }
  }


  if (typeof value === 'string') {

    const text = value.trim()

    try {
      const parsed = JSON.parse(text)

      if (Array.isArray(parsed)) {
        return {
          aramic: parsed[0] || '',

          fr: english
            ? ''
            : (parsed[2] || parsed[1] || ''),

          en: english
            ? (parsed[2] || parsed[1] || '')
            : (parsed[1] || '')
        }
      }

    } catch {
      /* Ce n'est simplement pas du JSON */
    }

    return {
      aramic: '',
      fr: english ? '' : text,
      en: english ? text : ''
    }
  }


  return {
    aramic: '',
    fr: '',
    en: ''
  }
}


/* =========================================================
   FUSION FR + EN
   ========================================================= */

function mergeDictionaryItems(items) {
  const map = new Map()

  for (const item of items) {

    const key =
      cleanText(item.term || item.aramic)

    if (!key) continue

    /*
     * On utilise également la forme araméenne nettoyée
     * afin de rapprocher les entrées FR et EN.
     */
    const normalizedKey =
      key.toLowerCase()

    if (!map.has(normalizedKey)) {

      map.set(normalizedKey, {
        ...item
      })

    } else {

      const old =
        map.get(normalizedKey)

      map.set(normalizedKey, {
        ...old,

        term:
          old.term ||
          item.term,

        aramic:
          old.aramic ||
          item.aramic,

        fr:
          old.fr ||
          item.fr,

        en:
          old.en ||
          item.en,

        category:
          old.category === item.category
            ? old.category
            : 'Firebase FR + EN'
      })
    }
  }

  return Array.from(map.values())
}


/* =========================================================
   RECHERCHE
   ========================================================= */

export function renderDictionaryResults() {
  const input =
    document.querySelector('#dictSearch')

  const box =
    document.querySelector('#dictResults')

  const status =
    document.querySelector('#dictStatus')

  if (!input || !box) return

  const q =
    cleanText(input.value)
      .toLowerCase()

  box.innerHTML = ''


  if (!q) {

    if (status && state.dictionaryLoaded) {
      status.textContent =
        `${state.dictionaryItems.length} entrées chargées. Écris un mot.`
    }

    return
  }


  const exact = []
  const starts = []
  const contains = []


  for (const item of state.dictionaryItems || []) {

    const term =
      cleanText(item.term)
        .toLowerCase()

    const aramic =
      cleanText(item.aramic)
        .toLowerCase()

    const fr =
      cleanText(item.fr)
        .toLowerCase()

    const en =
      cleanText(item.en)
        .toLowerCase()


    if (
      term === q ||
      aramic === q
    ) {

      exact.push(item)

    } else if (
      term.startsWith(q) ||
      aramic.startsWith(q)
    ) {

      starts.push(item)

    } else if (
      term.includes(q) ||
      aramic.includes(q) ||
      fr.includes(q) ||
      en.includes(q)
    ) {

      contains.push(item)
    }
  }


  const results =
    exact.length
      ? exact
      : [...starts, ...contains].slice(0, 80)


  if (status) {
    status.textContent =
      `${results.length} résultat(s).`
  }


  if (!results.length) {

    box.innerHTML =
      '<div class="dictEmpty">Aucune traduction trouvée.</div>'

    return
  }


  box.innerHTML =
    results.map(item => {

      const showFrench =
        state.dictLang !== 'en' &&
        item.fr

      const showEnglish =
        state.dictLang !== 'fr' &&
        item.en


      return `
        <div class="dictCard">

          <div class="dictTerm">
            ${escapeHtml(item.aramic || item.term)}
          </div>

          ${
            item.term &&
            item.term !== item.aramic
              ? `
                <div>
                  <b>Entrée :</b>
                  ${escapeHtml(item.term)}
                </div>
              `
              : ''
          }

          ${
            showFrench
              ? `
                <div>
                  <b>Français :</b>
                  ${escapeHtml(item.fr)}
                </div>
              `
              : ''
          }

          ${
            showEnglish
              ? `
                <div>
                  <b>English :</b>
                  ${escapeHtml(item.en)}
                </div>
              `
              : ''
          }

          <small>
            ${escapeHtml(item.category || 'Dictionnaire')}
          </small>

        </div>
      `
    }).join('')
}


/* =========================================================
   LANGUES
   ========================================================= */

function setDictLang(lang) {
  state.dictLang = lang

  document
    .querySelectorAll('.dictLangButtons button')
    .forEach(button => {
      button.classList.remove('active')
    })


  if (lang === 'both') {
    document
      .querySelector('#dictBothBtn')
      ?.classList.add('active')
  }

  if (lang === 'fr') {
    document
      .querySelector('#dictFrBtn')
      ?.classList.add('active')
  }

  if (lang === 'en') {
    document
      .querySelector('#dictEnBtn')
      ?.classList.add('active')
  }

  renderDictionaryResults()
}


/* =========================================================
   DOUBLE-CLIC MOT HÉBREU
   ========================================================= */

export function installHebrewWordClick() {

  document
    .querySelectorAll('.clickableHe')
    .forEach(element => {

      element.addEventListener(
        'dblclick',
        () => {

          const selection =
            window
              .getSelection()
              .toString()
              .trim()

          if (selection) {
            openDictionary(selection)
          }
        }
      )
    })
}


/* =========================================================
   ÉVÉNEMENTS
   ========================================================= */

export function initDictionaryEvents() {

  document
    .querySelector('#dictBtn')
    ?.addEventListener(
      'click',
      () => openDictionary()
    )


  document
    .querySelector('#closeDictBtn')
    ?.addEventListener(
      'click',
      closeDictionary
    )


  document
    .querySelector('#dictOverlay')
    ?.addEventListener(
      'click',
      closeDictionary
    )


  document
    .querySelector('#dictSearch')
    ?.addEventListener(
      'input',
      renderDictionaryResults
    )


  document
    .querySelector('#dictBothBtn')
    ?.addEventListener(
      'click',
      () => setDictLang('both')
    )


  document
    .querySelector('#dictFrBtn')
    ?.addEventListener(
      'click',
      () => setDictLang('fr')
    )


  document
    .querySelector('#dictEnBtn')
    ?.addEventListener(
      'click',
      () => setDictLang('en')
    )
}
