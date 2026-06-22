import { state, sedarim } from '../state.js'
import { sortDaf } from './utils.js'
import { installHebrewWordClick } from './dictionary.js'
import { renderParashaRashi } from './parashiot.js'

export function renderLibrary() {
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

export async function loadMasechet(file) {
  state.currentMode = 'talmud'
  state.currentParasha = null

  localStorage.setItem('currentFile', file)
  document.querySelector('#segments').innerHTML = '<div class="empty">Chargement du traité...</div>'
  document.querySelector('#commentBox').innerHTML = 'Choisis un commentaire.'

  renderLibrary()
  document.querySelector('.sidebar')?.classList.remove('open')

  try {
    const res = await fetch(`/data/merged/${file}`)
    if (!res.ok) throw new Error('Données non disponibles')

    state.currentData = await res.json()

    const dapim = Object.keys(state.currentData.dapim || {}).sort(sortDaf)
    const savedDaf = localStorage.getItem(`daf_${file}`)

    state.currentDaf = savedDaf && dapim.includes(savedDaf)
      ? savedDaf
      : (dapim.includes('2a') ? '2a' : dapim[0])

    renderDafNav()
    renderDaf(state.currentDaf)
  } catch (e) {
    state.currentData = null
    document.querySelector('#dafTitle').textContent = 'Données non disponibles'
    document.querySelector('#dafNav').innerHTML = ''
    document.querySelector('#segments').innerHTML = '<div class="empty">Données non encore disponibles pour ce traité.</div>'
  }
}

export function renderDafNav() {
  const box = document.querySelector('#dafNav')

  if (!state.currentData || !state.currentData.dapim) {
    box.innerHTML = ''
    return
  }

  const dapim = Object.keys(state.currentData.dapim).sort(sortDaf)
  const idx = dapim.indexOf(state.currentDaf)
  const prev = idx > 0 ? dapim[idx - 1] : null
  const next = idx < dapim.length - 1 ? dapim[idx + 1] : null

  box.innerHTML = `
    <div class="dafNav selectMode">
      <button id="topPrevDafBtn" ${prev ? '' : 'disabled'}>← ${prev || ''}</button>

      <label class="dafSelectLabel">
        Daf
        <select id="dafSelect">
          ${dapim.map(daf => `
            <option value="${daf}" ${daf === state.currentDaf ? 'selected' : ''}>${daf}</option>
          `).join('')}
        </select>
      </label>

      <button id="topNextDafBtn" ${next ? '' : 'disabled'}>${next || ''} →</button>
    </div>
  `

  document.querySelector('#dafSelect').addEventListener('change', e => goToDaf(e.target.value))

  if (prev) document.querySelector('#topPrevDafBtn').addEventListener('click', () => goToDaf(prev))
  if (next) document.querySelector('#topNextDafBtn').addEventListener('click', () => goToDaf(next))
}

export function goToDaf(daf) {
  state.currentDaf = daf
  renderDafNav()
  renderDaf(daf)
  document.querySelector('.reader')?.scrollTo?.(0, 0)
  document.querySelector('#commentBox').innerHTML = 'Choisis un commentaire.'
}

export function renderDaf(daf) {
  if (!state.currentData || !state.currentData.dapim || !state.currentData.dapim[daf]) {
    document.querySelector('#segments').innerHTML = '<div class="empty">Daf non disponible.</div>'
    return
  }

  state.currentDaf = daf
  localStorage.setItem('currentDaf', state.currentDaf)

  const currentFile = localStorage.getItem('currentFile') || 'berakhot.json'
  localStorage.setItem(`daf_${currentFile}`, state.currentDaf)

  const data = state.currentData.dapim[daf]
  const dapim = Object.keys(state.currentData.dapim).sort(sortDaf)
  const idx = dapim.indexOf(daf)
  const prev = idx > 0 ? dapim[idx - 1] : null
  const next = idx < dapim.length - 1 ? dapim[idx + 1] : null

  document.querySelector('#dafTitle').textContent = `${state.currentData.title} ${daf}`

  document.querySelector('#segments').innerHTML = `
    ${(data.segments || []).map((seg, index) => `
      <article class="segment">
        <div class="segNum">Segment ${index + 1}</div>
        <div class="he clickableHe">${seg.he || ''}</div>
        <div class="translation">
          ${state.currentLang === 'fr'
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

  if (prev) document.querySelector('#prevDafBtn')?.addEventListener('click', () => goToDaf(prev))
  if (next) document.querySelector('#nextDafBtn')?.addEventListener('click', () => goToDaf(next))

  installHebrewWordClick()
}

export function renderCommentary(type) {
  if (!state.currentData || !state.currentData.dapim || !state.currentData.dapim[state.currentDaf]) return

  const data = state.currentData.dapim[state.currentDaf]
  const items = data[type] || []

  document.querySelector('#commentBox').innerHTML = items.length
    ? items.map(x => typeof x === 'string'
      ? `<p class="he">${x}</p>`
      : `<p class="he">${x.he || x.text || ''}</p>`
    ).join('')
    : 'Commentaire non disponible pour ce daf.'
}

export function initTalmudEvents() {
  document.querySelector('#masechetSearch')?.addEventListener('input', renderLibrary)

  document.querySelector('#rashiBtn')?.addEventListener('click', () => {
    if (state.currentMode === 'parasha') {
      renderParashaRashi()
    } else {
      renderCommentary('rashi')
    }
  })

  document.querySelector('#tosafotBtn')?.addEventListener('click', () => {
    if (state.currentMode === 'parasha') {
      document.querySelector('#commentBox').innerHTML = 'Tossefot n’existe pas sur les parachiot.'
    } else {
      renderCommentary('tosafot')
    }
  })

  document.querySelector('#frBtn')?.addEventListener('click', () => {
    state.currentLang = 'fr'
    localStorage.setItem('talmudLang', state.currentLang)
    if (state.currentMode === 'talmud' && state.currentData) renderDaf(state.currentDaf)
  })

  document.querySelector('#enBtn')?.addEventListener('click', () => {
    state.currentLang = 'en'
    localStorage.setItem('talmudLang', state.currentLang)
    if (state.currentMode === 'talmud' && state.currentData) renderDaf(state.currentDaf)
  })
}
