import { escapeHtml } from './utils.js'

let shulchanSectionsCache = null
let currentShulchanSection = null

async function getShulchanSections() {
  if (shulchanSectionsCache) return shulchanSectionsCache

  const res = await fetch('/data/shulchan-arukh/index.json')
  if (!res.ok) throw new Error('Index Choul’han Aroukh introuvable')

  shulchanSectionsCache = await res.json()
  return shulchanSectionsCache
}

export async function renderShulchanLibrary() {
  const box = document.querySelector('#shulchanLibrary')
  if (!box) return

  try {
    const q = (document.querySelector('#saSearch')?.value || '').trim().toLowerCase()
    const sections = await getShulchanSections()

    box.innerHTML = sections
      .filter(s =>
        (s.title || '').toLowerCase().includes(q) ||
        (s.heTitle || '').includes(q)
      )
      .map(s => `
        <button class="masechet shulchanSideBtn" data-file="${escapeHtml(s.file)}">
          <span class="saHebrew">${escapeHtml(s.heTitle)}</span>
          <small>${escapeHtml(s.title)}</small>
        </button>
      `).join('')

    document.querySelectorAll('.shulchanSideBtn').forEach(btn => {
      btn.addEventListener('click', () => loadShulchanSection(btn.dataset.file))
    })
  } catch (e) {
    box.innerHTML = `<div class="empty">Erreur : ${escapeHtml(e.message)}</div>`
  }
}

export async function openShulchanArukh() {
  document.querySelector('#dafTitle').textContent = '📜 Choul’han Aroukh'
  document.querySelector('#dafNav').innerHTML = ''
  document.querySelector('#commentBox').innerHTML = 'Choisis une section.'
  document.querySelector('#segments').innerHTML = '<div class="empty">Chargement...</div>'

  try {
    const sections = await getShulchanSections()

    document.querySelector('#segments').innerHTML = `
      <div class="saGrid">
        ${sections.map(s => `
          <button class="saCard openSA" data-file="${escapeHtml(s.file)}">
            <span class="saHebrew">${escapeHtml(s.heTitle)}</span>
            <span class="saTitle">${escapeHtml(s.title)}</span>
          </button>
        `).join('')}
      </div>
    `

    document.querySelectorAll('.openSA').forEach(btn => {
      btn.addEventListener('click', () => loadShulchanSection(btn.dataset.file))
    })
  } catch (e) {
    document.querySelector('#segments').innerHTML = `<div class="empty">Erreur : ${escapeHtml(e.message)}</div>`
  }
}

export async function loadShulchanSection(file) {
  document.querySelector('#segments').innerHTML = '<div class="empty">Chargement de la section...</div>'

  try {
    const res = await fetch(`/data/shulchan-arukh/${file}`)
    if (!res.ok) throw new Error('Section introuvable')

    const data = await res.json()
    currentShulchanSection = data

    document.querySelector('#dafTitle').textContent = `📜 ${data.heTitle} — ${data.title}`
    document.querySelector('#commentBox').innerHTML = 'Choisis un siman.'

    renderSimanSelector(data)

    const firstSiman = (data.simanim || []).find(s => (s.seifim || []).length)
    if (firstSiman) {
      renderSiman(data, firstSiman)
    } else {
      document.querySelector('#segments').innerHTML = '<div class="empty">Aucun siman disponible.</div>'
    }
  } catch (e) {
    document.querySelector('#dafTitle').textContent = 'Choul’han Aroukh'
    document.querySelector('#dafNav').innerHTML = ''
    document.querySelector('#segments').innerHTML = `<div class="empty">Erreur : ${escapeHtml(e.message)}</div>`
  }
}

function renderSimanSelector(section) {
  const simanim = (section.simanim || []).filter(s => (s.seifim || []).length)

  document.querySelector('#dafNav').innerHTML = `
    <div class="dafNav selectMode">
      <button id="backShulchanBtn">← Choul’han Aroukh</button>

      <label class="dafSelectLabel">
        Siman
        <select id="simanSelect">
          ${simanim.map(s => `
            <option value="${s.siman}">
              ${s.siman}
            </option>
          `).join('')}
        </select>
      </label>
    </div>
  `

  document.querySelector('#backShulchanBtn')?.addEventListener('click', openShulchanArukh)

  document.querySelector('#simanSelect')?.addEventListener('change', e => {
    const siman = simanim.find(s => String(s.siman) === e.target.value)
    if (siman) renderSiman(section, siman)
  })
}

function renderSiman(section, siman) {
  const select = document.querySelector('#simanSelect')
  if (select) select.value = String(siman.siman)

  document.querySelector('#dafTitle').textContent = `📜 ${section.heTitle} — Siman ${siman.siman}`
  document.querySelector('#commentBox').innerHTML = `Section : ${escapeHtml(section.title)} — Siman ${siman.siman}`

  document.querySelector('#segments').innerHTML = `
    <article class="segment parashaFull">
      <div class="segNum">${escapeHtml(section.heTitle)} — Siman ${siman.siman}</div>

      ${(siman.seifim || []).map(seif => `
        <section class="parashaSideBySide shulchanSeif">
          <div class="parashaColumn translationColumn">
            <h3>Seif ${seif.seif}</h3>
            <p>${escapeHtml(seif.fr || seif.en || 'Traduction française en préparation.')}</p>
          </div>

          <div class="parashaColumn hebrewColumn">
            <h3>סעיף ${seif.seif}</h3>
            <p class="he">${seif.he || ''}</p>
          </div>
        </section>
      `).join('')}
    </article>
  `
}

export function initShulchanArukhEvents() {
  document.querySelector('#shulchanBtn')?.addEventListener('click', openShulchanArukh)

  renderShulchanLibrary()
  document.querySelector('#saSearch')?.addEventListener('input', renderShulchanLibrary)
}
