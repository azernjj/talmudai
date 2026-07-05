import { state, sedarim } from '../state.js'
import { sortDaf, escapeHtml } from './utils.js'
import { installHebrewWordClick } from './dictionary.js'
import { renderParashaRashi, loadParasha } from './parashiot.js'
import { renderShulchanCommentaryNotice } from './shulchan-arukh.js'
import { correctionButtonHtml, installCorrectionButtons } from './correction-admin.js'

let extraCommentaryCache = {}

function cleanText(text = '') {
  return String(text)
    .replace(/<\/?b>/gi, '')
    .replace(/<\/?i>/gi, '')
    .replace(/<\/?strong>/gi, '')
    .replace(/<\/?em>/gi, '')
    .replace(/<[^>]+>/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

export function renderLibrary() {
  const library = document.querySelector('#library')
  const q = (document.querySelector('#masechetSearch')?.value || '').trim().toLowerCase()
  const currentFile = localStorage.getItem('currentFile') || 'berakhot.json'

  if (!library) return

  library.innerHTML = sedarim.map(seder => {
    const filtered = seder.masechtot.filter(m =>
      m.name.toLowerCase().includes(q) || m.file.toLowerCase().includes(q)
    )

    if (!filtered.length) return ''

    return `
      <div class="seder">
        <h3>${escapeHtml(seder.name)}</h3>
        ${filtered.map(m => `
          <button class="masechet talmudMasechet ${m.file === currentFile ? 'active' : ''}" data-file="${escapeHtml(m.file)}">
            ${escapeHtml(m.name)}
          </button>
        `).join('')}
      </div>
    `
  }).join('')

  document.querySelectorAll('#library .talmudMasechet').forEach(btn => {
    btn.addEventListener('click', () => {
      loadMasechet(btn.dataset.file)
      document.querySelector('.sidebar')?.classList.remove('open')
    })
  })
}

export async function loadMasechet(file) {
  state.currentMode = 'talmud'
  state.currentParasha = null
  extraCommentaryCache = {}

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
  } catch {
    state.currentData = null
    document.querySelector('#dafTitle').textContent = 'Données non disponibles'
    document.querySelector('#dafNav').innerHTML = ''
    document.querySelector('#segments').innerHTML = '<div class="empty">Données non encore disponibles pour ce traité.</div>'
  }
}

export function renderDafNav() {
  const box = document.querySelector('#dafNav')
  if (!box) return

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
      <button id="topPrevDafBtn" ${prev ? '' : 'disabled'}>← ${escapeHtml(prev || '')}</button>

      <label class="dafSelectLabel">
        Daf
        <select id="dafSelect">
          ${dapim.map(daf => `
            <option value="${escapeHtml(daf)}" ${daf === state.currentDaf ? 'selected' : ''}>${escapeHtml(daf)}</option>
          `).join('')}
        </select>
      </label>

      <button id="topNextDafBtn" ${next ? '' : 'disabled'}>${escapeHtml(next || '')} →</button>
    </div>
  `

  document.querySelector('#dafSelect')?.addEventListener('change', e => goToDaf(e.target.value))
  if (prev) document.querySelector('#topPrevDafBtn')?.addEventListener('click', () => goToDaf(prev))
  if (next) document.querySelector('#topNextDafBtn')?.addEventListener('click', () => goToDaf(next))
}

export function goToDaf(daf) {
  state.currentDaf = daf
  renderDafNav()
  renderDaf(daf)
  document.querySelector('.reader')?.scrollTo?.(0, 0)
}

export function renderDaf(daf) {
  if (!state.currentData || !state.currentData.dapim || !state.currentData.dapim[daf]) {
    document.querySelector('#segments').innerHTML = '<div class="empty">Daf non disponible.</div>'
    return
  }

  state.currentMode = 'talmud'
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
      <div class="segNum">
         Segment ${index + 1}
         ${correctionButtonHtml('segments', index)}
        </div>
        <div class="he clickableHe">${seg.he || ''}</div>
        <div class="translation">
          ${state.currentLang === 'fr'
            ? escapeHtml(cleanText(seg.fr || 'Traduction française en préparation.'))
            : escapeHtml(cleanText(seg.en || 'English translation in preparation.'))}
        </div>
      </article>
    `).join('')}

    <div class="bottomNav">
      ${prev ? `<button id="prevDafBtn">← Daf précédent (${escapeHtml(prev)})</button>` : ''}
      ${next ? `<button id="nextDafBtn">Daf suivant (${escapeHtml(next)}) →</button>` : ''}
    </div>
  `

  renderTalmudCommentaryButtons()

  if (prev) document.querySelector('#prevDafBtn')?.addEventListener('click', () => goToDaf(prev))
  if (next) document.querySelector('#nextDafBtn')?.addEventListener('click', () => goToDaf(next))

  installHebrewWordClick()
  installCorrectionButtons()
}

function renderTalmudCommentaryButtons() {
  document.querySelector('#commentBox').innerHTML = `
    <div class="commentActions">
      <button id="rashiBtnLocal">Rachi</button>
      <button id="tosafotBtnLocal">Tossefot</button>
      <button id="ritvaBtnLocal">Ritva</button>
      <button id="roshBtnLocal">Roch</button>
      </div>

    <div id="talmudCommentaryBox">
      Choisis un commentaire.
    </div>
  `

  document.querySelector('#rashiBtnLocal')?.addEventListener('click', () => renderCommentary('rashi'))
  document.querySelector('#tosafotBtnLocal')?.addEventListener('click', () => renderCommentary('tosafot'))
  document.querySelector('#ritvaBtnLocal')?.addEventListener('click', () => renderExtraCommentary('ritva', 'Ritva'))
  document.querySelector('#roshBtnLocal')?.addEventListener('click', () => renderExtraCommentary('rosh', 'Roch'))
}

export function renderCommentary(type) {
  if (!state.currentData || !state.currentData.dapim || !state.currentData.dapim[state.currentDaf]) return

  const data = state.currentData.dapim[state.currentDaf]
  const items = data[type] || []
  const box = document.querySelector('#talmudCommentaryBox') || document.querySelector('#commentBox')

  box.innerHTML = items.length
    ? items.map(x => {
      if (typeof x === 'string') {
        return `<div class="rashiItem"><p class="he">${x}</p></div>`
      }

      return `
        <div class="rashiItem">
          <p class="he">${x.he || x.text || ''}</p>
          <p>${escapeHtml(
            state.currentLang === 'fr'
              ? cleanText(x.fr || x.en || 'Traduction française en préparation.')
              : cleanText(x.en || 'English translation unavailable.')
          )}</p>
        </div>
      `
    }).join('')
    : 'Commentaire non disponible pour ce daf.'
}

async function loadExtraCommentary(slug) {
  const currentFile = localStorage.getItem('currentFile') || 'berakhot.json'
  const key = `${slug}/${currentFile}`

  if (extraCommentaryCache[key]) return extraCommentaryCache[key]

  const res = await fetch(`/data/commentaries/${slug}/${currentFile}`)
  if (!res.ok) return null

  const data = await res.json()
  extraCommentaryCache[key] = data
  return data
}

export async function renderExtraCommentary(slug, title) {
  const box = document.querySelector('#talmudCommentaryBox') || document.querySelector('#commentBox')
  box.innerHTML = `<div class="empty">Chargement de ${escapeHtml(title)}...</div>`

  try {
    const data = await loadExtraCommentary(slug)

    if (!data?.dapim?.length) {
      box.innerHTML = `${escapeHtml(title)} non disponible pour ce traité.`
      return
    }

    const daf = (data.dapim || []).find(d => String(d.daf) === String(state.currentDaf))

    if (!daf?.comments?.length) {
      box.innerHTML = `${escapeHtml(title)} non disponible pour ce daf.`
      return
    }

    box.innerHTML = `
      <h3>${escapeHtml(title)} — ${escapeHtml(data.masechet || '')} ${escapeHtml(state.currentDaf)}</h3>

      ${daf.comments.map(item => `
        <div class="rashiItem">
          <p class="he">${item.he || ''}</p>
          <p>${escapeHtml(
            state.currentLang === 'fr'
              ? cleanText(item.fr || item.en || 'Traduction française en préparation.')
              : cleanText(item.en || 'English translation unavailable.')
          )}</p>
        </div>
      `).join('')}
    `
  } catch (e) {
    box.innerHTML = `<div class="empty">Erreur : ${escapeHtml(e.message)}</div>`
  }
}

function refreshCurrentViewAfterLanguageChange() {
  if (state.currentMode === 'parasha' && state.currentParasha?.file) {
    loadParasha(state.currentParasha.file)
    return
  }

  if (state.currentMode === 'talmud' && state.currentData && state.currentDaf) {
    renderDaf(state.currentDaf)
    return
  }

  if (state.currentMode === 'shulchan') {
    renderShulchanCommentaryNotice()
  }
}

export function initTalmudEvents() {
  document.querySelector('#masechetSearch')?.addEventListener('input', renderLibrary)

  document.querySelector('#rashiBtn')?.addEventListener('click', () => {
    if (state.currentMode === 'parasha') {
      renderParashaRashi()
    } else if (state.currentMode === 'shulchan') {
      renderShulchanCommentaryNotice()
    } else {
      renderCommentary('rashi')
    }
  })

  document.querySelector('#tosafotBtn')?.addEventListener('click', () => {
    if (state.currentMode === 'parasha') {
      document.querySelector('#commentBox').innerHTML = 'Tossefot n’existe pas sur les parachiot.'
    } else if (state.currentMode === 'shulchan') {
      renderShulchanCommentaryNotice()
    } else {
      renderCommentary('tosafot')
    }
  })

  document.querySelector('#frBtn')?.addEventListener('click', () => {
    state.currentLang = 'fr'
    localStorage.setItem('talmudLang', 'fr')
    refreshCurrentViewAfterLanguageChange()
  })

  document.querySelector('#enBtn')?.addEventListener('click', () => {
    state.currentLang = 'en'
    localStorage.setItem('talmudLang', 'en')
    refreshCurrentViewAfterLanguageChange()
  })
}
