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
      <h2 id="dafTitle">Berakhot 2a</h2>
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
  try {
    const res = await fetch(`/data/bavli/${file}`)
    if (!res.ok) throw new Error('Données non disponibles')
    currentData = await res.json()
    renderDaf('2a')
  } catch (e) {
    document.querySelector('#segments').innerHTML = `
      <div class="empty">
        Données non encore disponibles pour ce traité.
      </div>
    `
  }
}

function renderDaf(daf) {
  if (!currentData || !currentData[daf]) return

  const data = currentData[daf]
  document.querySelector('#dafTitle').textContent = `${currentData.title} ${daf}`

  document.querySelector('#segments').innerHTML = data.segments.map((seg, index) => `
    <article class="segment">
      <div class="segNum">Segment ${index + 1}</div>
      <div class="he">${seg.he}</div>
      <div class="translation">
        ${currentLang === 'fr'
          ? (seg.fr || 'Traduction française en préparation.')
          : (seg.en || 'English translation in preparation.')}
      </div>
    </article>
  `).join('')
}

function renderCommentary(type) {
  if (!currentData || !currentData['2a']) return

  const items = currentData['2a'][type] || []
  document.querySelector('#commentBox').innerHTML = items.length
    ? items.map(x => `<p class="he">${x}</p>`).join('')
    : 'Commentaire non disponible.'
}

document.querySelector('#frBtn').addEventListener('click', () => {
  currentLang = 'fr'
  renderDaf('2a')
})

document.querySelector('#enBtn').addEventListener('click', () => {
  currentLang = 'en'
  renderDaf('2a')
})

document.querySelector('#rashiBtn').addEventListener('click', () => renderCommentary('rashi'))
document.querySelector('#tosafotBtn').addEventListener('click', () => renderCommentary('tosafot'))

renderLibrary()
loadMasechet('berakhot.json')
