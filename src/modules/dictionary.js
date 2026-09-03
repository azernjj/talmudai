import { state } from '../state.js'
import { cleanText, escapeHtml } from './utils.js'

import { initializeApp, getApps } from "https://www.gstatic.com/firebasejs/10.12.4/firebase-app.js"
import {
  getFirestore,
  collection,
  getDocs
} from "https://www.gstatic.com/firebasejs/10.12.4/firebase-firestore.js"


/* =========================================================
   FIREBASE
   Même configuration que public/dictionary/dictionary.js
   ========================================================= */

const firebaseFrConfig = {
  apiKey: "AIzaSyBTQEl7BVMYcpD4XLjL7hsNUo74MSGaaUI",
  authDomain: "dico-fr-arameen.firebaseio.com",
  projectId: "test"
}

const firebaseEnConfig = {
  apiKey: "AIzaSyBTQEl7BVMYcpD4XLjL7hsNUo74MSGaaUI",
  authDomain: "dico-fr-arameen.firebaseio.com",
  projectId: "English"
}


function getOrCreateApp(config, name) {
  const existing = getApps().find(app => app.name === name)

  if (existing) {
    return existing
  }

  return initializeApp(config, name)
}


const appFr = getOrCreateApp(firebaseFrConfig, "talmud-fr")
const appEn = getOrCreateApp(firebaseEnConfig, "talmud-en")

const dbFr = getFirestore(appFr)
const dbEn = getFirestore(appEn)


/* =========================================================
   OUVERTURE DU DICTIONNAIRE
   ========================================================= */

export function openDictionary(initialSearch = '') {

  document
    .querySelector('#dictionaryPanel')
    ?.classList.remove('hidden')

  document
    .querySelector('#dictOverlay')
    ?.classList.remove('hidden')

  const input = document.querySelector('#dictSearch')

  if (input) {
    input.value = initialSearch || ''
    input.focus()
    input.select()
  }

  /*
   * IMPORTANT :
   * on recharge Firebase à chaque ouverture.
   *
   * Donc un mot ajouté dans Firebase après le déploiement
   * apparaîtra sans modifier GitHub ni Vercel.
   */
  loadDictionary()
}


export function closeDictionary() {

  document
    .querySelector('#dictionaryPanel')
    ?.classList.add('hidden')

  document
    .querySelector('#dictOverlay')
    ?.classList.add('hidden')
}


/* =========================================================
   UTILITAIRE FIREBASE
   ========================================================= */

function getValue(data, keys) {

  for (const key of keys) {

    if (
      data[key] !== undefined &&
      data[key] !== null &&
      data[key] !== ''
    ) {
      return data[key]
    }
  }

  return ''
}


/* =========================================================
   CHARGEMENT FIREBASE
   ========================================================= */

export async function loadDictionary() {

  const status = document.querySelector('#dictStatus')

  if (status) {
    status.textContent = 'Chargement du dictionnaire Firebase...'
  }

  try {

    const all = []


    /* -----------------------------------------------------
       FRANÇAIS
       ----------------------------------------------------- */

    const frSnap = await getDocs(
      collection(dbFr, "test")
    )

    frSnap.forEach(doc => {

      const d = doc.data() || {}

      all.push({

        id: "fr-" + doc.id,

        term:
          getValue(
            d,
            [
              "term",
              "ar",
              "he",
              "aramic",
              "arameen"
            ]
          ) || doc.id,

        aramic:
          getValue(
            d,
            [
              "aramic",
              "arameen",
              "hebrew",
              "he",
              "term"
            ]
          ) || doc.id,

        fr:
          getValue(
            d,
            [
              "fr",
              "french",
              "translation",
              "traduction"
            ]
          ),

        en: "",

        category: "Firebase Français"
      })
    })


    /* -----------------------------------------------------
       ANGLAIS
       ----------------------------------------------------- */

    const enSnap = await getDocs(
      collection(dbEn, "English")
    )

    enSnap.forEach(doc => {

      const d = doc.data() || {}

      all.push({

        id: "en-" + doc.id,

        term:
          getValue(
            d,
            [
              "term",
              "ar",
              "he",
              "aramic",
              "arameen"
            ]
          ) || doc.id,

        aramic:
          getValue(
            d,
            [
              "aramic",
              "arameen",
              "hebrew",
              "he",
              "term"
            ]
          ) || doc.id,

        fr: "",

        en:
          getValue(
            d,
            [
              "en",
              "english",
              "translation"
            ]
          ),

        category: "Firebase English"
      })
    })


    /* -----------------------------------------------------
       FUSION FR / EN
       ----------------------------------------------------- */

    state.dictionaryItems =
      mergeDictionaryItems(all)

    state.dictionaryLoaded = true


    if (status) {
      status.textContent =
        `${state.dictionaryItems.length} entrées Firebase chargées.`
    }


    renderDictionaryResults()

  } catch (error) {

    console.error(
      "Erreur Firebase dictionnaire TALMUD AI :",
      error
    )

    if (status) {
      status.textContent =
        "Firebase indisponible. Chargement du dictionnaire local..."
    }

    /*
     * En cas de problème Firebase,
     * TALMUD AI continue à fonctionner avec le JSON.
     */
    await loadLocalDictionary()
  }
}


/* =========================================================
   DICTIONNAIRE LOCAL DE SECOURS
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

      const res = await fetch(
        url,
        {
          cache: 'no-store'
        }
      )


      if (!res.ok) {

        lastError =
          `${url} : ${res.status}`

        continue
      }


      const raw =
        await res.json()


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

      lastError =
        `${url} : ${error.message}`
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

      if (
        value &&
        typeof value === 'object'
      ) {

        const term =
          value.term ||
          value.aramic ||
          value.he ||
          value.hebrew ||
          value.word ||
          ''


        items.push({

          term:
            cleanText(term),

          aramic:
            cleanText(
              value.aramic ||
              value.hebrew ||
              value.he ||
              term
            ),

          fr:
            cleanText(
              value.fr ||
              value.french ||
              value.traduction ||
              ''
            ),

          en:
            cleanText(
              value.en ||
              value.english ||
              ''
            ),

          category:
            value.category ||
            'Dictionnaire'
        })
      }
    })


    return mergeDictionaryItems(items)
  }


  for (
    const [category, entries]
    of Object.entries(raw || {})
  ) {

    if (
      !entries ||
      typeof entries !== 'object'
    ) {
      continue
    }


    for (
      const [term, value]
      of Object.entries(entries)
    ) {

      const parsed =
        parseDictionaryValue(
          value,
          category
        )


      items.push({

        term:
          cleanText(term),

        aramic:
          cleanText(
            parsed.aramic ||
            term
          ),

        fr:
          cleanText(parsed.fr),

        en:
          cleanText(parsed.en),

        category
      })
    }
  }


  return mergeDictionaryItems(items)
}


function isEnglishCategory(category = '') {

  const c =
    String(category)
      .toLowerCase()

  return (
    c === 'english' ||
    c.includes('eng')
  )
}


function parseDictionaryValue(
  value,
  category = ''
) {

  const english =
    isEnglishCategory(category)


  if (Array.isArray(value)) {

    return {

      aramic:
        value[0] || '',

      fr:
        english
          ? ''
          : (
            value[2] ||
            value[1] ||
            ''
          ),

      en:
        english
          ? (
            value[2] ||
            value[1] ||
            ''
          )
          : (
            value[1] ||
            ''
          )
    }
  }


  if (
    value &&
    typeof value === 'object'
  ) {

    return {

      aramic:
        value.aramic ||
        value.hebrew ||
        value.he ||
        value.term ||
        '',

      fr:
        english
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

    const s =
      value.trim()


    try {

      const parsed =
        JSON.parse(s)


      if (Array.isArray(parsed)) {

        return {

          aramic:
            parsed[0] || '',

          fr:
            english
              ? ''
              : (
                parsed[2] ||
                parsed[1] ||
                ''
              ),

          en:
            english
              ? (
                parsed[2] ||
                parsed[1] ||
                ''
              )
              : (
                parsed[1] ||
                ''
              )
        }
      }

    } catch {
      /*
       * Ce n'est pas du JSON.
       * On conserve la chaîne telle quelle.
       */
    }


    return {

      aramic: '',

      fr:
        english
          ? ''
          : s,

      en:
        english
          ? s
          : ''
    }
  }


  return {
    aramic: '',
    fr: '',
    en: ''
  }
}


/* =========================================================
   FUSION FRANÇAIS / ANGLAIS
   ========================================================= */

function mergeDictionaryItems(items) {

  const map =
    new Map()


  for (const item of items) {

    const key =
      cleanText(
        item.term ||
        item.aramic
      )


    if (!key) {
      continue
    }


    if (!map.has(key)) {

      map.set(
        key,
        {
          ...item
        }
      )

    } else {

      const old =
        map.get(key)


      map.set(
        key,
        {

          ...old,

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
            old.category ||
            item.category
        }
      )
    }
  }


  return Array.from(
    map.values()
  )
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


  if (
    !input ||
    !box
  ) {
    return
  }


  const q =
    cleanText(input.value)
      .toLowerCase()


  box.innerHTML = ''


  if (!q) {

    if (
      status &&
      state.dictionaryLoaded
    ) {

      status.textContent =
        `${state.dictionaryItems.length} entrées chargées. Écris un mot.`
    }

    return
  }


  const exact = []
  const starts = []
  const contains = []


  for (
    const item
    of state.dictionaryItems || []
  ) {

    const term =
      cleanText(
        item.term
      ).toLowerCase()

    const aramic =
      cleanText(
        item.aramic
      ).toLowerCase()

    const fr =
      cleanText(
        item.fr
      ).toLowerCase()

    const en =
      cleanText(
        item.en
      ).toLowerCase()


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
      : [
          ...starts,
          ...contains
        ].slice(0, 80)


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
    results
      .map(
        item => `
          <div class="dictCard">

            <div class="dictTerm">
              ${escapeHtml(
                item.aramic ||
                item.term
              )}
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
              state.dictLang !== 'en' &&
              item.fr
                ? `
                  <div>
                    <b>Français :</b>
                    ${escapeHtml(item.fr)}
                  </div>
                `
                : ''
            }

            ${
              state.dictLang !== 'fr' &&
              item.en
                ? `
                  <div>
                    <b>English :</b>
                    ${escapeHtml(item.en)}
                  </div>
                `
                : ''
            }

            <small>
              ${escapeHtml(
                item.category ||
                'Firebase'
              )}
            </small>

          </div>
        `
      )
      .join('')
}


/* =========================================================
   CHOIX FR / EN
   ========================================================= */

function setDictLang(lang) {

  state.dictLang = lang


  document
    .querySelectorAll(
      '.dictLangButtons button'
    )
    .forEach(
      btn =>
        btn.classList.remove('active')
    )


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
   DOUBLE CLIC SUR TEXTE HÉBREU / ARAMÉEN
   ========================================================= */

export function installHebrewWordClick() {

  document
    .querySelectorAll('.clickableHe')
    .forEach(el => {

      el.addEventListener(
        'dblclick',
        () => {

          const selection =
            window
              .getSelection()
              .toString()
              .trim()


          if (selection) {

            openDictionary(
              selection
            )
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
