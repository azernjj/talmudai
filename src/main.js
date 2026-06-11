import './style.css'

const app = document.querySelector('#app')

const sedarim = [
  {
    name: 'Zeraïm',
    masechtot: [
      { name: 'Berakhot', file: 'berakhot.json' }
    ]
  },
  {
    name: 'Moed',
    masechtot: [
      { name: 'Shabbat', file: 'shabbat.json' },
      { name: 'Erouvin', file: 'eruvin.json' },
      { name: 'Pessa’him', file: 'pesachim.json' }
    ]
  }
]

let currentLang = 'fr'
let currentData = null
let currentDaf = '2a'

app.innerHTML = `
  <header class="topbar">
    <div>
      <h1>TALMUD AI</h1>
      <p>Beit Midrash numérique</p>
    </div>
    <div class="lang">
      <button id="frBtn">🇫🇷 Français</button>
      <button id="enBtn">🇬🇧 English</button>
    </div>
  </header>

  <div class="layout">
    <aside class="sidebar">
      <h2>📚 Sedarim</h2>
      <div id="library"></div>
    </aside>

    <main class="reader">
      <h2 id="dafTitle">Chargement...</h2>
      <div id="dafNav"></div>
      <div id="segments"></div>
    </main>

    <section class="comments">
      <h2>📝 Commentaires</h2>
      <button id="rashiBtn">Rachi</button>
      <button id="tosafotBtn">Tossefot</button>
      <div id="commentBox" class="commentBox">
        Choisis un commentaire.
      </div>
    </section>
  </div>
`

function renderLibrary() {
  const library = document.querySelector('#library')

  library.innerHTML = sedarim.map(seder => `
    <div class="seder">
      <h3>${seder.name}</h3>
      ${seder.masechtot.map(m => `
        <button class="masechet" data-file="${m.file}">
          ${m.name}
        </button>
      `).join('')}
    </div>
  `).join('')

  document.querySelectorAll('.masechet').forEach(btn => {
    btn.addEventListener('click', () => loadMasechet(btn.dataset.file))
  })
}

async function loadMasechet(file) {
  document.querySelector('#segments').innerHTML = `<div class="empty">Chargement du traité...</div>`

  try {
    const res = await fetch(`/data/bavli/${file}`)

    if (!res.ok) {
      throw new Error('Données non disponibles')
    }

    currentData = await res.json()

    const dapim = Object.keys(currentData.dapim || {}).sort(sortDaf)
    currentDaf = dapim.includes('2a') ? '2a' : dapim[0]

    renderDafNav()
    renderDaf(currentDaf)
  } catch (e) {
    currentData = null
    document.querySelector('#dafTitle').textContent = 'Données non disponibles'
    document.querySelector('#dafNav').innerHTML = ''
    document.querySelector('#segments').innerHTML = `
      <div class="empty">
        Données non encore disponibles pour ce traité.
      </div>
    `
  }
}

function sortDaf(a, b) {
  const pa = parseDaf(a)
  const pb = parseDaf(b)

  if (pa.num !== pb.num) return pa.num - pb.num
  return pa.side.localeCompare(pb.side)
}

function parseDaf(daf) {
  const match = daf.match(/^(\d+)([ab])$/)
  return {
    num: match ? Number(match[1]) : 0,
    side: match ? match[2] : ''
  }
}

function renderDafNav() {
  const box = document.querySelector('#dafNav')

  if (!currentData || !currentData.dapim) {
    box.innerHTML = ''
    return
  }

  const dapim = Object.keys(currentData.dapim).sort(sortDaf)

  box.innerHTML = `
    <div class="dafNav">
      ${dapim.map(daf => `
        <button class="dafBtn ${daf === currentDaf ? 'active' : ''}" data-daf="${daf}">
          ${daf}
        </button>
      `).join('')}
    </div>
  `

  document.querySelectorAll('.dafBtn').forEach(btn => {
    btn.addEventListener('click', () => {
      currentDaf = btn.dataset.daf
      renderDafNav()
      renderDaf(currentDaf)
      document.querySelector('#commentBox').innerHTML = 'Choisis un commentaire.'
    })
  })
}

function renderDaf(daf) {
  if (!currentData || !currentData.dapim || !currentData.dapim[daf]) {
    document.querySelector('#segments').innerHTML = `<div class="empty">Daf non disponible.</div>`
    return
  }

  const data = currentData.dapim[daf]
  document.querySelector('#dafTitle').textContent = `${currentData.title} ${daf}`

  document.querySelector('#segments').innerHTML = (data.segments || []).map((seg, index) => `
    <article class="segment">
      <div class="segNum">Segment ${index + 1}</div>
      <div class="he">${seg.he || ''}</div>
      <div class="translation">
        ${currentLang === 'fr'
          ? (seg.fr || 'Traduction française en préparation.')
          : (seg.en || 'English translation in preparation.')}
      </div>
    </article>
  `).join('')
}

function renderCommentary(type) {
  if (!currentData || !currentData.dapim || !currentData.dapim[currentDaf]) {
    return
  }

  const data = currentData.dapim[currentDaf]
  const items = data[type] || []

  document.querySelector('#commentBox').innerHTML = items.length
    ? items.map(x => `<p class="he">${x}</p>`).join('')
    : 'Commentaire non disponible pour ce daf.'
}

document.querySelector('#frBtn').addEventListener('click', () => {
  currentLang = 'fr'
  renderDaf(currentDaf)
})

document.querySelector('#enBtn').addEventListener('click', () => {
  currentLang = 'en'
  renderDaf(currentDaf)
})

document.querySelector('#rashiBtn').addEventListener('click', () => renderCommentary('rashi'))
document.querySelector('#tosafotBtn').addEventListener('click', () => renderCommentary('tosafot'))

renderLibrary()
loadMasechet('berakhot.json')
