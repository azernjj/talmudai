import './style.css'

const app = document.querySelector('#app')

const sedarim = [
  { name: 'Zeraïm', masechtot: [{ name: 'Berakhot', file: 'berakhot.json' }] },
  {
    name: 'Moed',
    masechtot: [
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
    ]
  },
  {
    name: 'Nachim',
    masechtot: [
      { name: 'Yevamot', file: 'yevamot.json' },
      { name: 'Ketoubot', file: 'ketubot.json' },
      { name: 'Nedarim', file: 'nedarim.json' },
      { name: 'Nazir', file: 'nazir.json' },
      { name: 'Sota', file: 'sotah.json' },
      { name: 'Gittin', file: 'gittin.json' },
      { name: 'Kiddouchin', file: 'kiddushin.json' }
    ]
  },
  {
    name: 'Nezikin',
    masechtot: [
      { name: 'Bava Kama', file: 'bava-kamma.json' },
      { name: 'Bava Metsia', file: 'bava-metzia.json' },
      { name: 'Bava Batra', file: 'bava-batra.json' },
      { name: 'Sanhédrin', file: 'sanhedrin.json' },
      { name: 'Makot', file: 'makkot.json' },
      { name: 'Chevouot', file: 'shevuot.json' },
      { name: 'Avoda Zara', file: 'avodah-zarah.json' },
      { name: 'Horayot', file: 'horayot.json' }
    ]
  },
  {
    name: 'Kodachim',
    masechtot: [
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
    ]
  },
  { name: 'Taharot', masechtot: [{ name: 'Nidda', file: 'niddah.json' }] }
]

let currentLang = localStorage.getItem('talmudLang') || 'fr'
let currentData = null
let currentDaf = localStorage.getItem('currentDaf') || '2a'
let dictionaryLoaded = false
let dictionaryItems = []
let dictLang = 'both'

app.innerHTML = `
  <header class="topbar">
    <div class="brand">
      <h1>TALMUD AI</h1>
      <p>Beit Midrash numérique</p>
    </div>

    <div class="lang">
      <button id="frBtn">🇫🇷 Français</button>
      <button id="enBtn">🇬🇧 English</button>
      <button id="dictBtn">📖 Dictionnaire</button>
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

    <div id="dictStatus" class="dictStatus">Clique sur le dictionnaire pour charger les données.</div>
    <div id="dictResults" class="dictResults"></div>
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
    btn.addEventListener('click', () => loadMasechet(btn.dataset.file))
  })
}

async function loadMasechet(file) {
  localStorage.setItem('currentFile', file)
  document.querySelector('#segments').innerHTML = `<div class="empty">Chargement du traité...</div>`
  document.querySelector('#commentBox').innerHTML = 'Choisis un commentaire.'
  renderLibrary()

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
    document.querySelector('#segments').innerHTML = `<div class="empty">Données non encore disponibles pour ce traité.</div>`
  }
}

function parseDaf(daf) {
  const match = String(daf).match(/^(\d+)([ab])$/)
  return { num: match ? Number(match[1]) : 0, side: match ? match[2] : '' }
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
          ${dapim.map(daf => `<option value="${daf}" ${daf === currentDaf ? 'selected' : ''}>${daf}</option>`).join('')}
        </select>
      </label>

      <button id="topNextDafBtn" ${next ? '' : 'disabled'}>${next || ''} →</button>
    </div>
  `

  document.querySelector('#dafSelect').addEventListener('change', e => {
    currentDaf = e.target.value
    renderDafNav()
    renderDaf(currentDaf)
    document.querySelector('#commentBox').innerHTML = 'Choisis un commentaire.'
  })

  if (prev) {
    document.querySelector('#topPrevDafBtn').addEventListener('click', () => goToDaf(prev))
  }
  if (next) {
    document.querySelector('#topNextDafBtn').addEventListener('click', () => goToDaf(next))
  }
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
  input.value = initialSearch || input.value || ''
  input.focus()

  if (!dictionaryLoaded) loadDictionary()
  else renderDictionaryResults()
}

function closeDictionary() {
  document.querySelector('#dictionaryPanel').classList.add('hidden')
  document.querySelector('#dictOverlay').classList.add('hidden')
}

async function loadDictionary() {
  const status = document.querySelector('#dictStatus')
  status.textContent = 'Chargement du dictionnaire...'

  try {
    const res = await fetch('/data/dictionary/dictionary.json')

    if (!res.ok) {
      status.textContent = 'Fichier /data/dictionary/dictionary.json introuvable.'
      return
    }

    const raw = await res.json()
    dictionaryItems = normalizeDictionaryJson(raw)
    dictionaryLoaded = true
    status.textContent = `${dictionaryItems.length} entrées chargées.`
    renderDictionaryResults()
  } catch (e) {
    status.textContent = 'Erreur dictionnaire : ' + e.message
  }
}

function normalizeDictionaryJson(raw) {
  const items = []

  function addItem(term, value, category) {
    const parsed = parseDictionaryValue(value)
    items.push({
      term: cleanText(term),
      aramic: cleanText(parsed.aramic || term),
      fr: cleanText(parsed.fr),
      en: cleanText(parsed.en),
      category
    })
  }

  if (raw && typeof raw === 'object') {
    for (const [category, entries] of Object.entries(raw)) {
      if (!entries || typeof entries !== 'object') continue
      for (const [term, value] of Object.entries(entries)) {
        addItem(term, value, category)
      }
    }
  }

  return mergeDictionaryItems(items)
}

function parseDictionaryValue(value) {
  if (Array.isArray(value)) {
    return { aramic: value[0] || '', en: value[1] || '', fr: value[2] || '' }
  }

  if (value && typeof value === 'object') {
    return {
      aramic: value.aramic || value.hebrew || value.he || value.term || '',
      fr: value.fr || value.french || value.traduction || '',
      en: value.en || value.english || ''
    }
  }

  if (typeof value === 'string') {
    const s = value.trim()
    try {
      const parsed = JSON.parse(s)
      if (Array.isArray(parsed)) {
        return { aramic: parsed[0] || '', en: parsed[1] || '', fr: parsed[2] || '' }
      }
    } catch {}
    return { aramic: '', fr: s, en: '' }
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

  const results = dictionaryItems
    .filter(item => `${item.term} ${item.aramic} ${item.fr} ${item.en}`.toLowerCase().includes(q))
    .slice(0, 80)

  status.textContent = `${results.length} résultat(s).`

  if (!results.length) {
    box.innerHTML = `<div class="dictEmpty">Aucune traduction trouvée.</div>`
    return
  }

  box.innerHTML = results.map(item => `
    <div class="dictCard">
      <div class="dictTerm">${escapeHtml(item.aramic || item.term)}</div>
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
  return String(str || '').replace(/\s+/g, ' ').trim()
}

function escapeHtml(str) {
  return String(str || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
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
document.querySelector('#closeDictBtn').addEventListener('click', closeDictionary)
document.querySelector('#dictOverlay').addEventListener('click', closeDictionary)
document.querySelector('#dictSearch').addEventListener('input', renderDictionaryResults)
document.querySelector('#dictBothBtn').addEventListener('click', () => setDictLang('both'))
document.querySelector('#dictFrBtn').addEventListener('click', () => setDictLang('fr'))
document.querySelector('#dictEnBtn').addEventListener('click', () => setDictLang('en'))

document.querySelector('#masechetSearch').addEventListener('input', renderLibrary)
document.querySelector('#rashiBtn').addEventListener('click', () => renderCommentary('rashi'))
document.querySelector('#tosafotBtn').addEventListener('click', () => renderCommentary('tosafot'))

renderLibrary()
loadMasechet(localStorage.getItem('currentFile') || 'berakhot.json')
