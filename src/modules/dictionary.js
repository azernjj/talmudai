import { state } from '../state.js'
import { cleanText, escapeHtml } from './utils.js'
import { initializeApp, getApps } from 'firebase/app'
import { getDatabase, ref, get } from 'firebase/database'

const firebaseConfig = {
  apiKey: 'AIzaSyBTQEl7BVMYcpD4XLjL7hsNUo74MSGaaUI',
  databaseURL: 'https://dico-fr-arameen.firebaseio.com/',
  projectId: 'dico-fr-arameen'
}

const app = getApps().find(a => a.name === 'talmud-dictionary') ||
  initializeApp(firebaseConfig, 'talmud-dictionary')

const database = getDatabase(app)

let searchTimer = null
let searchSequence = 0

export function openDictionary(initialSearch = '') {
  document.querySelector('#dictionaryPanel').classList.remove('hidden')
  document.querySelector('#dictOverlay').classList.remove('hidden')

  const input = document.querySelector('#dictSearch')
  input.value = initialSearch || ''
  input.focus()
  input.select()

  if (!state.dictionaryLoaded) {
    loadDictionary().then(() => {
      if (cleanText(input.value)) searchDictionary()
    })
  } else {
    searchDictionary()
  }
}

export function closeDictionary() {
  document.querySelector('#dictionaryPanel').classList.add('hidden')
  document.querySelector('#dictOverlay').classList.add('hidden')
}

export async function loadDictionary() {
  const status = document.querySelector('#dictStatus')

  status.textContent = 'Chargement du dictionnaire local...'

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
      const res = await fetch(url, {
        cache: 'no-store'
      })

      if (!res.ok) {
        lastError = `${url} : ${res.status}`
        continue
      }

      const raw = await res.json()

      state.dictionaryItems = normalizeDictionaryJson(raw)
      state.dictionaryLoaded = true

      status.textContent =
        `${state.dictionaryItems.length} entrées locales chargées.`

      return

    } catch (e) {
      lastError = `${url} : ${e.message}`
    }
  }

  /*
   * Même si le fichier JSON local n'est pas disponible,
   * le dictionnaire Firebase reste utilisable.
   */

  state.dictionaryItems = []
  state.dictionaryLoaded = true

  status.textContent =
    'Dictionnaire local indisponible. Recherche Firebase active.' +
    (lastError ? ` (${lastError})` : '')
}

function normalizeDictionaryJson(raw) {
  const items = []

  if (Array.isArray(raw)) {

    raw.forEach(value => {

      if (value && typeof value === 'object') {

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
            'Dictionnaire local'
        })
      }
    })

    return mergeDictionaryItems(items)
  }

  for (const [category, entries] of Object.entries(raw || {})) {

    if (!entries || typeof entries !== 'object') continue

    for (const [term, value] of Object.entries(entries)) {

      const parsed =
        parseDictionaryValue(value, category)

      items.push({
        term: cleanText(term),

        aramic: cleanText(
          parsed.aramic ||
          term
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
  const c =
    String(category).toLowerCase()

  return (
    c === 'english' ||
    c.includes('eng')
  )
}

function parseDictionaryValue(value, category = '') {

  const english =
    isEnglishCategory(category)

  if (Array.isArray(value)) {

    return {
      aramic:
        value[0] || '',

      fr:
        english
          ? ''
          : (value[2] || value[1] || ''),

      en:
        english
          ? (value[2] || value[1] || '')
          : (value[1] || '')
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

    const s = value.trim()

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

    } catch {}

    return {
      aramic: '',
      fr: english ? '' : s,
      en: english ? s : ''
    }
  }

  return {
    aramic: '',
    fr: '',
    en: ''
  }
}

function mergeDictionaryItems(items) {

  const map =
    new Map()

  for (const item of items) {

    const key =
      cleanText(
        item.term ||
        item.aramic
      )

    if (!key) continue

    if (!map.has(key)) {

      map.set(
        key,
        item
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

function isAramaicHebrew(text) {

  return /[\u0590-\u05FF]/.test(text)
}

function cleanFirebaseValue(value) {

  if (typeof value === 'string') {

    return cleanText(
      value.replace(
        /^"(.+)"$/,
        '$1'
      )
    )
  }

  if (
    value &&
    typeof value === 'object'
  ) {

    return cleanText(
      value.translation ||
      value.traduction ||
      value.fr ||
      value.french ||
      value.en ||
      value.english ||
      value.value ||
      ''
    )
  }

  return cleanText(
    value == null
      ? ''
      : String(value)
  )
}

async function firebaseGet(path) {

  const timeout =
    new Promise(
      (_, reject) => {

        setTimeout(
          () =>
            reject(
              new Error(
                'Timeout Firebase'
              )
            ),
          10000
        )
      }
    )

  const snapshot =
    await Promise.race([
      get(
        ref(
          database,
          path
        )
      ),
      timeout
    ])

  return snapshot
}


/*
 * ======================================================
 * RECHERCHE FIREBASE
 * ======================================================
 *
 * Même fonctionnement que :
 *
 * aramean-lingua-scribe-main
 *
 * Français :
 *
 * test/<mot araméen>
 *
 * Anglais :
 *
 * English/<mot araméen>
 *
 * Exemple :
 *
 * test/שנכפה
 *
 * ======================================================
 */

async function getFirebaseByAramaic(aramaicWord) {

  const word =
    cleanText(aramaicWord)

  if (!word)
    return null

  const [
    frResult,
    enResult
  ] =
    await Promise.allSettled([

      firebaseGet(
        `test/${word}`
      ),

      firebaseGet(
        `English/${word}`
      )
    ])

  const frSnapshot =
    frResult.status === 'fulfilled'
      ? frResult.value
      : null

  const enSnapshot =
    enResult.status === 'fulfilled'
      ? enResult.value
      : null

  const fr =
    frSnapshot?.exists()
      ? cleanFirebaseValue(
          frSnapshot.val()
        )
      : ''

  const en =
    enSnapshot?.exists()
      ? cleanFirebaseValue(
          enSnapshot.val()
        )
      : ''

  if (!fr && !en)
    return null

  return {
    term: word,

    aramic: word,

    fr,

    en,

    category:
      'Firebase'
  }
}


/*
 * Recherche inverse.
 *
 * Exemple :
 *
 * utilisateur tape :
 *
 * contraint
 *
 * On recherche la traduction
 * dans le dossier "test".
 */

async function findFirebaseByTranslation(
  sourceWord,
  language
) {

  const searched =
    cleanText(sourceWord)
      .toLowerCase()

  if (!searched)
    return null

  const bucket =
    language === 'en'
      ? 'English'
      : 'test'

  const snapshot =
    await firebaseGet(bucket)

  if (!snapshot?.exists())
    return null

  const data =
    snapshot.val()

  if (
    !data ||
    typeof data !== 'object'
  )
    return null

  for (
    const [
      aramaicKey,
      translationValue
    ]
    of Object.entries(data)
  ) {

    const translated =
      cleanFirebaseValue(
        translationValue
      )

    if (
      translated &&
      translated.toLowerCase() === searched
    ) {

      return cleanText(
        aramaicKey
      )
    }
  }

  return null
}

async function searchFirebase(query) {

  const q =
    cleanText(query)

  if (!q)
    return []

  try {

    /*
     * Si le texte contient
     * de l'hébreu/araméen,
     * recherche directe.
     */

    if (isAramaicHebrew(q)) {

      const item =
        await getFirebaseByAramaic(q)

      return item
        ? [item]
        : []
    }

    /*
     * Recherche FR / EN.
     */

    const languages =
      state.dictLang === 'fr'
        ? ['fr']

        : state.dictLang === 'en'
          ? ['en']

          : ['fr', 'en']

    const matches =
      await Promise.allSettled(

        languages.map(
          lang =>
            findFirebaseByTranslation(
              q,
              lang
            )
        )
      )

    const aramaicWords =
      [
        ...new Set(

          matches

            .filter(
              r =>
                r.status ===
                  'fulfilled' &&
                r.value
            )

            .map(
              r =>
                r.value
            )
        )
      ]

    const items =
      await Promise.all(

        aramaicWords.map(
          word =>
            getFirebaseByAramaic(
              word
            )
        )
      )

    return items.filter(Boolean)

  } catch (error) {

    console.error(
      'Erreur de recherche Firebase du dictionnaire :',
      error
    )

    return []
  }
}


/*
 * ======================================================
 * RECHERCHE DANS LE JSON LOCAL
 * ======================================================
 */

function getLocalResults(query) {

  const q =
    cleanText(query)
      .toLowerCase()

  if (!q)
    return []

  const exact = []
  const starts = []
  const contains = []

  for (
    const item
    of state.dictionaryItems || []
  ) {

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
      fr.includes(q) ||
      en.includes(q)
    ) {

      contains.push(item)
    }
  }

  return exact.length
    ? exact
    : [
        ...starts,
        ...contains
      ].slice(0, 80)
}


/*
 * Firebase est volontairement placé
 * AVANT le dictionnaire local.
 *
 * Une correction Firebase doit donc
 * avoir priorité sur une ancienne
 * valeur du JSON.
 */

function combineSearchResults(
  firebaseItems,
  localItems
) {

  return mergeDictionaryItems([
    ...(firebaseItems || []),
    ...(localItems || [])
  ])
}

function renderResultCards(results) {

  const box =
    document.querySelector(
      '#dictResults'
    )

  if (!results.length) {

    box.innerHTML =
      '<div class="dictEmpty">Aucune traduction trouvée.</div>'

    return
  }

  box.innerHTML =
    results.map(
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
            'Dictionnaire'
          )}
        </small>

      </div>

    `
    ).join('')
}


/*
 * ======================================================
 * RECHERCHE PRINCIPALE
 * ======================================================
 */

export async function searchDictionary() {

  const input =
    document.querySelector(
      '#dictSearch'
    )

  const status =
    document.querySelector(
      '#dictStatus'
    )

  const box =
    document.querySelector(
      '#dictResults'
    )

  const query =
    cleanText(
      input?.value ||
      ''
    )

  const sequence =
    ++searchSequence

  box.innerHTML = ''

  if (!query) {

    status.textContent =
      state.dictionaryLoaded

        ? `${
            (
              state.dictionaryItems ||
              []
            ).length
          } entrées locales chargées. Écris un mot.`

        : 'Chargement du dictionnaire...'

    return
  }


  /*
   * On affiche immédiatement
   * le résultat local.
   */

  const localResults =
    getLocalResults(query)

  renderResultCards(
    localResults
  )

  status.textContent =
    localResults.length

      ? `${localResults.length} résultat(s) local(aux). Vérification Firebase...`

      : 'Recherche dans Firebase...'


  /*
   * Puis interrogation Firebase.
   */

  const firebaseResults =
    await searchFirebase(query)

  /*
   * Si l'utilisateur a déjà
   * tapé autre chose entre temps,
   * on ignore l'ancienne réponse.
   */

  if (
    sequence !==
    searchSequence
  )
    return

  const results =
    combineSearchResults(
      firebaseResults,
      localResults
    )

  renderResultCards(
    results
  )

  if (firebaseResults.length) {

    status.textContent =
      `${results.length} résultat(s) — Firebase à jour.`

  } else {

    status.textContent =
      `${results.length} résultat(s).`
  }
}


/*
 * Appelé pendant la frappe.
 *
 * Délai de 250 ms afin de ne pas
 * interroger Firebase à chaque touche.
 */

export function renderDictionaryResults() {

  clearTimeout(
    searchTimer
  )

  searchTimer =
    setTimeout(
      () => {
        searchDictionary()
      },
      250
    )
}

function setDictLang(lang) {

  state.dictLang = lang

  document
    .querySelectorAll(
      '.dictLangButtons button'
    )
    .forEach(
      btn =>
        btn.classList.remove(
          'active'
        )
    )

  if (lang === 'both')
    document
      .querySelector(
        '#dictBothBtn'
      )
      .classList.add(
        'active'
      )

  if (lang === 'fr')
    document
      .querySelector(
        '#dictFrBtn'
      )
      .classList.add(
        'active'
      )

  if (lang === 'en')
    document
      .querySelector(
        '#dictEnBtn'
      )
      .classList.add(
        'active'
      )

  searchDictionary()
}


/*
 * Double clic sur un mot
 * hébreu/araméen du Talmud.
 */

export function installHebrewWordClick() {

  document
    .querySelectorAll(
      '.clickableHe'
    )
    .forEach(
      el => {

        el.addEventListener(
          'dblclick',
          () => {

            const selection =
              window
                .getSelection()
                .toString()
                .trim()

            if (selection)
              openDictionary(
                selection
              )
          }
        )
      }
    )
}


/*
 * ======================================================
 * ÉVÉNEMENTS
 * ======================================================
 */

export function initDictionaryEvents() {

  document
    .querySelector(
      '#dictBtn'
    )
    ?.addEventListener(
      'click',
      () =>
        openDictionary()
    )

  document
    .querySelector(
      '#closeDictBtn'
    )
    ?.addEventListener(
      'click',
      closeDictionary
    )

  document
    .querySelector(
      '#dictOverlay'
    )
    ?.addEventListener(
      'click',
      closeDictionary
    )

  document
    .querySelector(
      '#dictSearch'
    )
    ?.addEventListener(
      'input',
      renderDictionaryResults
    )

  document
    .querySelector(
      '#dictBothBtn'
    )
    ?.addEventListener(
      'click',
      () =>
        setDictLang(
          'both'
        )
    )

  document
    .querySelector(
      '#dictFrBtn'
    )
    ?.addEventListener(
      'click',
      () =>
        setDictLang(
          'fr'
        )
    )

  document
    .querySelector(
      '#dictEnBtn'
    )
    ?.addEventListener(
      'click',
      () =>
        setDictLang(
          'en'
        )
    )
}
