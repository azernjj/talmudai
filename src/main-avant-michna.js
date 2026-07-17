import './style.css'

const app = document.querySelector('#app')

const sedarim = [
  { name: 'Zeraïm', masechtot: [{ name: 'Berakhot', file: 'berakhot.json' }] },
  { name: 'Moed', masechtot: [
    { name: 'Shabbat', file: 'shabbat.json' },
    { name: 'Erouvin', file: 'eruvin.json' },
    { name: 'Pessa’him', file: 'pesachim.json' },
    { name: 'Yoma', file: 'yoma.json' },
    { name: 'Soukka', file: 'sukkah.json' },
    { name: 'Beitsa', file: 'beitzah.json' },
    { name: 'Roch Hachana', file: 'rosh-hashanah.json' },
    { name: 'Taanit', file: 'taanit.json' },
    { name: 'Meguila', file: 'megillah.json' },
    { name: 'Moed Katan', file: 'moed-katan.json' },
    { name: 'Haguiga', file: 'chagigah.json' }
  ]},
  { name: 'Nachim', masechtot: [
    { name: 'Yevamot', file: 'yevamot.json' },
    { name: 'Ketoubot', file: 'ketubot.json' },
    { name: 'Nedarim', file: 'nedarim.json' },
    { name: 'Nazir', file: 'nazir.json' },
    { name: 'Sota', file: 'sotah.json' },
    { name: 'Gittin', file: 'gittin.json' },
    { name: 'Kiddouchin', file: 'kiddushin.json' }
  ]},
  { name: 'Nezikin', masechtot: [
    { name: 'Bava Kama', file: 'bava-kamma.json' },
    { name: 'Bava Metsia', file: 'bava-metzia.json' },
    { name: 'Bava Batra', file: 'bava-batra.json' },
    { name: 'Sanhédrin', file: 'sanhedrin.json' },
    { name: 'Makot', file: 'makkot.json' },
    { name: 'Chevouot', file: 'shevuot.json' },
    { name: 'Avoda Zara', file: 'avodah-zarah.json' },
    { name: 'Horayot', file: 'horayot.json' }
  ]},
  { name: 'Kodachim', masechtot: [
    { name: 'Zevahim', file: 'zevachim.json' },
    { name: 'Menahot', file: 'menachot.json' },
    { name: 'Houlin', file: 'chullin.json' },
    { name: 'Bekhorot', file: 'bekhorot.json' },
    { name: 'Arakhin', file: 'arakhin.json' },
    { name: 'Temoura', file: 'temurah.json' },
    { name: 'Keritot', file: 'keritot.json' },
    { name: 'Meila', file: 'meilah.json' },
    { name: 'Tamid', file: 'tamid.json' },
    { name: 'Midot', file: 'middot.json' },
    { name: 'Kinim', file: 'kinnim.json' }
  ]},
  { name: 'Taharot', masechtot: [{ name: 'Nidda', file: 'niddah.json' }] }
]

let currentLang = localStorage.getItem('talmudLang') || 'fr'
let currentData = null
let currentDaf = localStorage.getItem('currentDaf') || '2a'
let dictionaryItems = []
let dictionaryLoaded = false
let dictLang = 'both'
let mishnaIndex = []
let mishnaLoaded = false

app.innerHTML = `
  <header class="topbar">
    <div class="brand">
      <h1>TALMUD AI</h1>
      <p>Beit Midrash numérique</p>
    </div>
    <div class="lang">
      <button id="mobileMenuBtn" class="mobileMenuBtn">☰ Traités</button>
      <button id="frBtn">🇫🇷 Français</button>
      <button id="enBtn">🇬🇧 English</button>
      <button id="dictBtn">📖 Dictionnaire</button>
      <button id="mishnaBtn">📘 Michna</button>
      <input id="globalSearch" placeholder="🔎 Rechercher dans tout le Talmud..." />
    </div>
  </header>

  <div class="layout">
    <aside class="sidebar">
      <h2>📚 Sedarim</h2>
      <input id="masechetSearch" class="masechetSearch" placeholder="🔍 Rechercher un traité..." autocomplete="off" />
      <div id="library"></div>
    </aside>

    <main class="reader">
      <h2 id="dafTitle">Chargement...</h2>
      <div id="dafNav"></div>
      <div id="segments"></div>
    </main>

    <section class="comments">
      <h2>📝 Commentaires</h2>
      <div class="commentActions">
        <button id="rashiBtn">Rachi</button>
        <button id="tosafotBtn">Tossefot</button>
      </div>
      <div id="commentBox" class="commentBox">Choisis un commentaire.</div>
    </section>
  </div>

  <div id="dictOverlay" class="dictOverlay hidden"></div>
  <aside id="dictionaryPanel" class="dictionaryPanel hidden">
    <div class="dictHeader">
      <h2>📖 Dictionnaire araméen</h2>
      <button id="closeDictBtn">✕</button>
    </div>

    <input id="dictSearch" class="dictSearch" placeholder="Écris un mot araméen, français ou anglais..." autocomplete="off" />

    <div class="dictLangButtons">
      <button id="dictBothBtn" class="active">FR + EN</button>
      <button id="dictFrBtn">Français</button>
      <button id="dictEnBtn">English</button>
    </div>

    <div id="dictStatus" class="dictStatus">Dictionnaire prêt.</div>
    <div id="dictResults" class="dictResults"></div>
  </aside>

  <div id="mishnaOverlay" class="dictOverlay hidden"></div>
  <aside id="mishnaPanel" class="dictionaryPanel hidden">
    <div class="dictHeader">
      <h2>📘 Étude de la Michna</h2>
      <button id="closeMishnaBtn">✕</button>
    </div>

    <select id="mishnaBookSelect" class="dictSearch">
      <option value="">Choisir un traité de Michna...</option>
    </select>

    <div id="mishnaStatus" class="dictStatus">Chargement de l’index de la Michna...</div>
    <div id="mishnaResults" class="dictResults"></div>
  </aside>
`

function renderLibrary() {
  const library = document.querySelector('#library')
  const q = (document.querySelector('#masechetSearch')?.value || '').trim().toLowerCase()
  const currentFile = localStorage.getItem('currentFile') || 'berakhot.json'

  library.innerHTML = sedarim.map(seder => {
    const filtered = seder.masechtot.filter(m =>
      m.name.toLowerCase().includes(q) || m.file.toLowerCase().includes(q)
    )

    if (!filtered.length) return ''

    return `
      <div class="seder">
        <h3>${seder.name}</h3>
        ${filtered.map(m => `
          <button class="masechet ${m.file === currentFile ? 'active' : ''}" data-file="${m.file}">
            ${m.name}
          </button>
        `).join('')}
      </div>
    `
  }).join('')

  document.querySelectorAll('.masechet').forEach(btn => {
    btn.addEventListener('click', () => {
      loadMasechet(btn.dataset.file)
      document.querySelector('.sidebar')?.classList.remove('open')
    })
  })
}

async function loadMasechet(file) {
  localStorage.setItem('currentFile', file)
  document.querySelector('#segments').innerHTML = `<div class="empty">Chargement du traité...</div>`
  document.querySelector('#commentBox').innerHTML = 'Choisis un commentaire.'
  renderLibrary()
  document.querySelector('.sidebar')?.classList.remove('open')
  try {
    const res = await fetch(`/data/merged/${file}`)
    if (!res.ok) throw new Error('Données non disponibles')

    currentData = await res.json()
    const dapim = Object.keys(currentData.dapim || {}).sort(sortDaf)
    const savedDaf = localStorage.getItem(`daf_${file}`)

    currentDaf = savedDaf && dapim.includes(savedDaf)
      ? savedDaf
      : (dapim.includes('2a') ? '2a' : dapim[0])

    renderDafNav()
    renderDaf(currentDaf)
  } catch (e) {
    currentData = null
    document.querySelector('#dafTitle').textContent = 'Données non disponibles'
    document.querySelector('#dafNav').innerHTML = ''
    document.querySelector('#segments').innerHTML = `
      <div class="empty">Données non encore disponibles pour ce traité.</div>
    `
  }
}

function parseDaf(daf) {
  const match = String(daf).match(/^(\d+)([ab])$/)
  return {
    num: match ? Number(match[1]) : 0,
    side: match ? match[2] : ''
  }
}

function sortDaf(a, b) {
  const pa = parseDaf(a)
  const pb = parseDaf(b)
  if (pa.num !== pb.num) return pa.num - pb.num
  return pa.side.localeCompare(pb.side)
}

function renderDafNav() {
  const box = document.querySelector('#dafNav')
  if (!currentData || !currentData.dapim) {
    box.innerHTML = ''
    return
  }

  const dapim = Object.keys(currentData.dapim).sort(sortDaf)
  const idx = dapim.indexOf(currentDaf)
  const prev = idx > 0 ? dapim[idx - 1] : null
  const next = idx < dapim.length - 1 ? dapim[idx + 1] : null

  box.innerHTML = `
    <div class="dafNav selectMode">
      <button id="topPrevDafBtn" ${prev ? '' : 'disabled'}>← ${prev || ''}</button>

      <label class="dafSelectLabel">
        Daf
        <select id="dafSelect">
          ${dapim.map(daf => `
            <option value="${daf}" ${daf === currentDaf ? 'selected' : ''}>${daf}</option>
          `).join('')}
        </select>
      </label>

      <button id="topNextDafBtn" ${next ? '' : 'disabled'}>${next || ''} →</button>
    </div>
  `

  document.querySelector('#dafSelect').addEventListener('change', e => {
    goToDaf(e.target.value)
  })

  if (prev) document.querySelector('#topPrevDafBtn').addEventListener('click', () => goToDaf(prev))
  if (next) document.querySelector('#topNextDafBtn').addEventListener('click', () => goToDaf(next))
}

function goToDaf(daf) {
  currentDaf = daf
  renderDafNav()
  renderDaf(daf)
  document.querySelector('.reader').scrollTop = 0
  document.querySelector('#commentBox').innerHTML = 'Choisis un commentaire.'
}

function renderDaf(daf) {
  if (!currentData || !currentData.dapim || !currentData.dapim[daf]) {
    document.querySelector('#segments').innerHTML = `<div class="empty">Daf non disponible.</div>`
    return
  }

  currentDaf = daf
  localStorage.setItem('currentDaf', currentDaf)

  const currentFile = localStorage.getItem('currentFile') || 'berakhot.json'
  localStorage.setItem(`daf_${currentFile}`, currentDaf)

  const data = currentData.dapim[daf]
  const dapim = Object.keys(currentData.dapim).sort(sortDaf)
  const idx = dapim.indexOf(daf)
  const prev = idx > 0 ? dapim[idx - 1] : null
  const next = idx < dapim.length - 1 ? dapim[idx + 1] : null

  document.querySelector('#dafTitle').textContent = `${currentData.title} ${daf}`

  document.querySelector('#segments').innerHTML = `
    ${(data.segments || []).map((seg, index) => `
      <article class="segment">
        <div class="segNum">Segment ${index + 1}</div>
        <div class="he clickableHe">${seg.he || ''}</div>
        <div class="translation">
          ${currentLang === 'fr'
            ? (seg.fr || 'Traduction française en préparation.')
            : (seg.en || 'English translation in preparation.')}
        </div>
      </article>
    `).join('')}

    <div class="bottomNav">
      ${prev ? `<button id="prevDafBtn">← Daf précédent (${prev})</button>` : ''}
      ${next ? `<button id="nextDafBtn">Daf suivant (${next}) →</button>` : ''}
    </div>
  `

  if (prev) document.querySelector('#prevDafBtn').addEventListener('click', () => goToDaf(prev))
  if (next) document.querySelector('#nextDafBtn').addEventListener('click', () => goToDaf(next))

  installHebrewWordClick()
}

function renderCommentary(type) {
  if (!currentData || !currentData.dapim || !currentData.dapim[currentDaf]) return

  const data = currentData.dapim[currentDaf]
  const items = data[type] || []

  document.querySelector('#commentBox').innerHTML = items.length
    ? items.map(x => typeof x === 'string'
      ? `<p class="he">${x}</p>`
      : `<p class="he">${x.he || x.text || ''}</p>`
    ).join('')
    : 'Commentaire non disponible pour ce daf.'
}

function openDictionary(initialSearch = '') {
  document.querySelector('#dictionaryPanel').classList.remove('hidden')
  document.querySelector('#dictOverlay').classList.remove('hidden')

  const input = document.querySelector('#dictSearch')
  input.value = initialSearch || ''
  input.focus()
  input.select()

  if (!dictionaryLoaded) {
    loadDictionary()
  } else {
    renderDictionaryResults()
  }
}

function closeDictionary() {
  document.querySelector('#dictionaryPanel').classList.add('hidden')
  document.querySelector('#dictOverlay').classList.add('hidden')
}

async function loadDictionary() {
  const status = document.querySelector('#dictStatus')
  status.textContent = 'Chargement du dictionnaire...'

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
      const res = await fetch(url, { cache: 'no-store' })

      if (!res.ok) {
        lastError = `${url} : ${res.status}`
        continue
      }

      const raw = await res.json()
      dictionaryItems = normalizeDictionaryJson(raw)
      dictionaryLoaded = true
      status.textContent = `${dictionaryItems.length} entrées chargées.`
      renderDictionaryResults()
      return
    } catch (e) {
      lastError = `${url} : ${e.message}`
    }
  }

  status.textContent = 'Dictionnaire introuvable. Dernier essai : ' + lastError
}

function normalizeDictionaryJson(raw) {
  const items = []

  if (Array.isArray(raw)) {
    raw.forEach((value, index) => {
      if (value && typeof value === 'object') {
        const term = value.term || value.aramic || value.he || value.hebrew || value.word || ''
        items.push({
          term: cleanText(term),
          aramic: cleanText(value.aramic || value.hebrew || value.he || term),
          fr: cleanText(value.fr || value.french || value.traduction || ''),
          en: cleanText(value.en || value.english || ''),
          category: value.category || 'Dictionnaire'
        })
      }
    })
    return mergeDictionaryItems(items)
  }

  for (const [category, entries] of Object.entries(raw || {})) {
    if (!entries || typeof entries !== 'object') continue

    for (const [term, value] of Object.entries(entries)) {
      const parsed = parseDictionaryValue(value, category)
      items.push({
        term: cleanText(term),
        aramic: cleanText(parsed.aramic || term),
        fr: cleanText(parsed.fr),
        en: cleanText(parsed.en),
        category
      })
    }
  }

  return mergeDictionaryItems(items)
}

function isEnglishCategory(category = '') {
  const c = String(category).toLowerCase()
  return c === 'english' || c.includes('eng')
}

function parseDictionaryValue(value, category = '') {
  const english = isEnglishCategory(category)

  if (Array.isArray(value)) {
    return {
      aramic: value[0] || '',
      fr: english ? '' : (value[2] || value[1] || ''),
      en: english ? (value[2] || value[1] || '') : (value[1] || '')
    }
  }

  if (value && typeof value === 'object') {
    return {
      aramic: value.aramic || value.hebrew || value.he || value.term || '',
      fr: english ? '' : (value.fr || value.french || value.traduction || value.translation || ''),
      en: value.en || value.english || (english ? value.translation || '' : '')
    }
  }

  if (typeof value === 'string') {
    const s = value.trim()

    try {
      const parsed = JSON.parse(s)
      if (Array.isArray(parsed)) {
        return {
          aramic: parsed[0] || '',
          fr: english ? '' : (parsed[2] || parsed[1] || ''),
          en: english ? (parsed[2] || parsed[1] || '') : (parsed[1] || '')
        }
      }
    } catch {}

    return {
      aramic: '',
      fr: english ? '' : s,
      en: english ? s : ''
    }
  }

  return { aramic: '', fr: '', en: '' }
}

function mergeDictionaryItems(items) {
  const map = new Map()

  for (const item of items) {
    const key = item.term || item.aramic
    if (!key) continue

    if (!map.has(key)) {
      map.set(key, item)
    } else {
      const old = map.get(key)
      map.set(key, {
        ...old,
        aramic: old.aramic || item.aramic,
        fr: old.fr || item.fr,
        en: old.en || item.en,
        category: old.category || item.category
      })
    }
  }

  return Array.from(map.values())
}

function renderDictionaryResults() {
  const q = cleanText(document.querySelector('#dictSearch').value).toLowerCase()
  const box = document.querySelector('#dictResults')
  const status = document.querySelector('#dictStatus')

  box.innerHTML = ''

  if (!q) {
    status.textContent = dictionaryLoaded
      ? `${dictionaryItems.length} entrées chargées. Écris un mot.`
      : status.textContent
    return
  }

  const exact = []
  const starts = []
  const contains = []

  for (const item of dictionaryItems) {
    const term = cleanText(item.term).toLowerCase()
    const aramic = cleanText(item.aramic).toLowerCase()
    const fr = cleanText(item.fr).toLowerCase()
    const en = cleanText(item.en).toLowerCase()

    if (term === q || aramic === q) {
      exact.push(item)
    } else if (term.startsWith(q) || aramic.startsWith(q)) {
      starts.push(item)
    } else if (fr.includes(q) || en.includes(q)) {
      contains.push(item)
    }
  }

  const results = exact.length
  ? exact
  : [...starts, ...contains].slice(0, 80)
  status.textContent = `${results.length} résultat(s).`

  if (!results.length) {
    box.innerHTML = `<div class="dictEmpty">Aucune traduction trouvée.</div>`
    return
  }

  box.innerHTML = results.map(item => `
    <div class="dictCard">
      <div class="dictTerm">${escapeHtml(item.aramic || item.term)}</div>
      ${item.term && item.term !== item.aramic ? `<div><b>Entrée :</b> ${escapeHtml(item.term)}</div>` : ''}
      ${dictLang !== 'en' && item.fr ? `<div><b>Français :</b> ${escapeHtml(item.fr)}</div>` : ''}
      ${dictLang !== 'fr' && item.en ? `<div><b>English :</b> ${escapeHtml(item.en)}</div>` : ''}
      <small>${escapeHtml(item.category || 'Dictionnaire')}</small>
    </div>
  `).join('')
}

function setDictLang(lang) {
  dictLang = lang

  document.querySelectorAll('.dictLangButtons button').forEach(btn => btn.classList.remove('active'))
  if (lang === 'both') document.querySelector('#dictBothBtn').classList.add('active')
  if (lang === 'fr') document.querySelector('#dictFrBtn').classList.add('active')
  if (lang === 'en') document.querySelector('#dictEnBtn').classList.add('active')

  renderDictionaryResults()
}

function installHebrewWordClick() {
  document.querySelectorAll('.clickableHe').forEach(el => {
    el.addEventListener('dblclick', () => {
      const selection = window.getSelection().toString().trim()
      if (selection) openDictionary(selection)
    })
  })
}

function cleanText(str) {
  return String(str || '')
    .replace(/["“”]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

function escapeHtml(str) {
  return String(str || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
}



function openMishna() {
  document.querySelector('#mishnaPanel')?.classList.remove('hidden')
  document.querySelector('#mishnaOverlay')?.classList.remove('hidden')

  if (!mishnaLoaded) {
    loadMishnaIndex()
  }
}

function closeMishna() {
  document.querySelector('#mishnaPanel')?.classList.add('hidden')
  document.querySelector('#mishnaOverlay')?.classList.add('hidden')
}

async function loadMishnaIndex() {
  const status = document.querySelector('#mishnaStatus')
  const select = document.querySelector('#mishnaBookSelect')

  status.textContent = 'Chargement de la liste des traités de Michna...'

  try {
    const res = await fetch('/data/mishna/index.json', { cache: 'no-store' })
    if (!res.ok) throw new Error(`index.json introuvable (${res.status})`)

    const raw = await res.json()
    mishnaIndex = Array.isArray(raw) ? raw : (raw.masechtot || raw.items || [])
    mishnaLoaded = true

    select.innerHTML = `
      <option value="">Choisir un traité de Michna...</option>
      ${mishnaIndex.map(item => `
        <option value="${escapeHtml(item.file || '')}">
          ${escapeHtml(item.name || item.title || item.file || '')}
        </option>
      `).join('')}
    `

    status.textContent = `${mishnaIndex.length} traité(s) de Michna disponible(s).`
  } catch (e) {
    status.textContent = `Erreur Michna : ${e.message}`
  }
}

async function loadMishnaFile(file) {
  const status = document.querySelector('#mishnaStatus')
  const box = document.querySelector('#mishnaResults')

  if (!file) {
    box.innerHTML = ''
    status.textContent = `${mishnaIndex.length} traité(s) de Michna disponible(s).`
    return
  }

  status.textContent = 'Chargement du traité...'
  box.innerHTML = ''

  try {
    const res = await fetch(`/data/mishna/${file}`, { cache: 'no-store' })
    if (!res.ok) throw new Error(`Fichier introuvable (${res.status})`)

    const data = await res.json()
    const items = flattenMishnaSegments(data)

    status.textContent = `${items.length} Michna/segment(s) chargé(s).`

    box.innerHTML = items.length
      ? items.map((item, index) => renderMishnaCard(item, index)).join('')
      : '<div class="dictEmpty">Aucune Michna détectée dans ce fichier.</div>'
  } catch (e) {
    status.textContent = `Erreur : ${e.message}`
  }
}

function flattenMishnaSegments(node, path = [], output = []) {
  if (Array.isArray(node)) {
    node.forEach((value, index) => flattenMishnaSegments(value, [...path, index], output))
    return output
  }

  if (!node || typeof node !== 'object') return output

  const he = node.he || node.hebrew || node.text_he
  if (typeof he === 'string' && he.trim()) {
    output.push({
      path: path.join('.'),
      id: node.id ?? node.number ?? output.length + 1,
      ref: node.ref || node.reference || '',
      he,
      fr: node.fr || '',
      etude_fr: node.etude_fr || null
    })
    return output
  }

  Object.entries(node).forEach(([key, value]) => {
    flattenMishnaSegments(value, [...path, key], output)
  })

  return output
}

function renderMishnaCard(item, index) {
  const study = item.etude_fr || {}
  const title = item.ref || `Michna ${item.id || index + 1}`

  return `
    <article class="dictCard mishnaCard">
      <h3>${escapeHtml(title)}</h3>

      <div class="he">${item.he || ''}</div>

      <div class="translation">
        <b>Traduction française fidèle :</b><br>
        ${item.fr || study.traduction_fidele || 'Traduction française en préparation.'}
      </div>

      ${study.traduction_fluide ? `
        <div class="mishnaSection">
          <b>Traduction fluide :</b>
          <p>${escapeHtml(study.traduction_fluide)}</p>
        </div>
      ` : ''}

      ${study.introduction ? `
        <div class="mishnaSection">
          <b>Introduction :</b>
          <p>${escapeHtml(study.introduction)}</p>
        </div>
      ` : ''}

      ${study.contexte_general ? `
        <div class="mishnaSection">
          <b>Contexte général :</b>
          <p>${escapeHtml(study.contexte_general)}</p>
        </div>
      ` : ''}

      ${Array.isArray(study.explication_ligne_par_ligne) && study.explication_ligne_par_ligne.length ? `
        <details class="mishnaSection">
          <summary><b>Explication ligne par ligne</b></summary>
          ${study.explication_ligne_par_ligne.map(line => `
            <div class="mishnaLine">
              <div class="he">${line.texte_hebreu || ''}</div>
              <p><b>Traduction :</b> ${escapeHtml(line.traduction_fidele || '')}</p>
              <p><b>Explication :</b> ${escapeHtml(line.explication || '')}</p>
            </div>
          `).join('')}
        </details>
      ` : ''}

      ${Array.isArray(study.mots_difficiles) && study.mots_difficiles.length ? `
        <details class="mishnaSection">
          <summary><b>Mots difficiles</b></summary>
          ${study.mots_difficiles.map(word => `
            <p>
              <b>${escapeHtml(word.mot || '')}</b>
              ${word.translitteration ? `(${escapeHtml(word.translitteration)})` : ''}
              — ${escapeHtml(word.traduction || '')}<br>
              ${escapeHtml(word.explication || '')}
            </p>
          `).join('')}
        </details>
      ` : ''}

      ${Array.isArray(study.mefarshim) && study.mefarshim.length ? `
        <details class="mishnaSection">
          <summary><b>Méfarchim classiques</b></summary>
          ${study.mefarshim.map(comment => `
            <div class="mishnaComment">
              <p><b>${escapeHtml(comment.auteur || '')}</b> — ${escapeHtml(comment.source_precise || '')}</p>
              <p>${escapeHtml(comment.opinion || '')}</p>
              <p><b>Logique :</b> ${escapeHtml(comment.logique || '')}</p>
              ${comment.desaccords ? `<p><b>Désaccords :</b> ${escapeHtml(comment.desaccords)}</p>` : ''}
            </div>
          `).join('')}
        </details>
      ` : ''}

      ${study.halakha_retenue ? `
        <div class="mishnaSection">
          <b>Halakha retenue :</b>
          <p>${escapeHtml(study.halakha_retenue)}</p>
        </div>
      ` : ''}

      ${Array.isArray(study.sources_verifiables) && study.sources_verifiables.length ? `
        <details class="mishnaSection">
          <summary><b>Sources</b></summary>
          <ul>
            ${study.sources_verifiables.map(source => `<li>${escapeHtml(source)}</li>`).join('')}
          </ul>
        </details>
      ` : ''}

      ${study.synthese_finale ? `
        <div class="mishnaSection">
          <b>Synthèse finale :</b>
          <p>${escapeHtml(study.synthese_finale)}</p>
        </div>
      ` : ''}
    </article>
  `
}


function initMobileMenu() {
  document.querySelector('#mobileMenuBtn')?.addEventListener('click', () => {
    document.querySelector('.sidebar')?.classList.toggle('open')
  })
}

function injectMobileStyles() {
  if (document.querySelector('#talmudMobileFixStyle')) return

  const style = document.createElement('style')
  style.id = 'talmudMobileFixStyle'
  style.textContent = `
    @media (max-width: 768px) {
      body {
        overflow-x: hidden !important;
      }

      .layout {
        display: block !important;
        width: 100% !important;
      }

      .topbar {
        position: sticky !important;
        top: 0 !important;
        z-index: 1000 !important;
      }

      .lang {
        display: flex !important;
        flex-wrap: wrap !important;
        gap: 8px !important;
      }

      .mobileMenuBtn {
        display: inline-flex !important;
      }

      .sidebar {
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        width: 86vw !important;
        max-width: 360px !important;
        height: 100vh !important;
        overflow-y: auto !important;
        z-index: 9999 !important;
        transform: translateX(-105%) !important;
        transition: transform .25s ease !important;
        background: #fff !important;
        padding: 16px !important;
        box-shadow: 0 0 30px rgba(0,0,0,.25) !important;
      }

      .sidebar.open {
        transform: translateX(0) !important;
      }

      #library,
      .seder {
        display: block !important;
        width: 100% !important;
      }

      .masechet {
        display: block !important;
        width: 100% !important;
        min-width: 0 !important;
        margin: 6px 0 !important;
        white-space: normal !important;
      }

      .reader {
        width: 100% !important;
        max-width: 100% !important;
        overflow: visible !important;
      }

      .comments {
        width: 100% !important;
        max-width: 100% !important;
      }


      .mishnaCard {
        line-height: 1.65 !important;
      }

      .mishnaSection {
        margin-top: 14px !important;
        padding-top: 12px !important;
        border-top: 1px solid #ddd !important;
      }

      .mishnaLine,
      .mishnaComment {
        padding: 10px !important;
        margin: 8px 0 !important;
        border-radius: 10px !important;
        background: #f7f7f7 !important;
      }

      .dictionaryPanel {
        width: 92vw !important;
        max-width: 92vw !important;
        right: 4vw !important;
        left: 4vw !important;
      }
    }

    @media (min-width: 769px) {
      .mobileMenuBtn {
        display: none !important;
      }
    }
  `
  document.head.appendChild(style)
}


document.querySelector('#frBtn').addEventListener('click', () => {
  currentLang = 'fr'
  localStorage.setItem('talmudLang', currentLang)
  renderDaf(currentDaf)
})

document.querySelector('#enBtn').addEventListener('click', () => {
  currentLang = 'en'
  localStorage.setItem('talmudLang', currentLang)
  renderDaf(currentDaf)
})

document.querySelector('#dictBtn').addEventListener('click', () => openDictionary())
document.querySelector('#mishnaBtn')?.addEventListener('click', openMishna)
document.querySelector('#closeMishnaBtn')?.addEventListener('click', closeMishna)
document.querySelector('#mishnaOverlay')?.addEventListener('click', closeMishna)
document.querySelector('#mishnaBookSelect')?.addEventListener('change', e => loadMishnaFile(e.target.value))
document.querySelector('#closeDictBtn').addEventListener('click', closeDictionary)
document.querySelector('#dictOverlay').addEventListener('click', closeDictionary)
document.querySelector('#dictSearch').addEventListener('input', renderDictionaryResults)
document.querySelector('#dictBothBtn').addEventListener('click', () => setDictLang('both'))
document.querySelector('#dictFrBtn').addEventListener('click', () => setDictLang('fr'))
document.querySelector('#dictEnBtn').addEventListener('click', () => setDictLang('en'))

document.querySelector('#masechetSearch').addEventListener('input', renderLibrary)
document.querySelector('#rashiBtn').addEventListener('click', () => renderCommentary('rashi'))
document.querySelector('#tosafotBtn').addEventListener('click', () => renderCommentary('tosafot'))

injectMobileStyles()
initMobileMenu()
renderLibrary()
loadMasechet(localStorage.getItem('currentFile') || 'berakhot.json')
