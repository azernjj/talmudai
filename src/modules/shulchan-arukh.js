import { escapeHtml } from './utils.js'

export async function openShulchanArukh() {
  document.querySelector('#dafTitle').textContent = '📜 Choul’han Aroukh'
  document.querySelector('#dafNav').innerHTML = ''
  document.querySelector('#commentBox').innerHTML = 'Choisis une section.'
  document.querySelector('#segments').innerHTML = '<div class="empty">Chargement...</div>'

  const res = await fetch('/data/shulchan-arukh/index.json')
  const sections = await res.json()

  document.querySelector('#segments').innerHTML = sections.map(s => `
    <article class="segment">
      <div class="segNum">${escapeHtml(s.heTitle)} — ${escapeHtml(s.title)}</div>
      <button class="openSA" data-file="${escapeHtml(s.file)}">Ouvrir</button>
    </article>
  `).join('')

  document.querySelectorAll('.openSA').forEach(btn => {
    btn.addEventListener('click', () => loadShulchanSection(btn.dataset.file))
  })
}

async function loadShulchanSection(file) {
  const res = await fetch(`/data/shulchan-arukh/${file}`)
  const data = await res.json()

  document.querySelector('#dafTitle').textContent = `📜 ${data.heTitle} — ${data.title}`
  document.querySelector('#dafNav').innerHTML = ''
  document.querySelector('#commentBox').innerHTML = 'Choisis un siman.'

  document.querySelector('#segments').innerHTML = data.simanim.map(s => `
    <article class="segment">
      <div class="segNum">Siman ${s.siman}</div>
      <button class="openSiman" data-siman="${s.siman}">Ouvrir le siman</button>
    </article>
  `).join('')

  document.querySelectorAll('.openSiman').forEach(btn => {
    const siman = data.simanim.find(x => String(x.siman) === btn.dataset.siman)
    btn.addEventListener('click', () => renderSiman(data, siman))
  })
}

function renderSiman(section, siman) {
  document.querySelector('#dafTitle').textContent = `📜 ${section.heTitle} — Siman ${siman.siman}`
  document.querySelector('#dafNav').innerHTML = `
    <div class="dafNav">
      <button id="backSA">← Retour aux simanim</button>
    </div>
  `

  document.querySelector('#segments').innerHTML = `
    <article class="segment parashaFull">
      ${(siman.seifim || []).map(seif => `
        <section class="parashaSideBySide">
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

  document.querySelector('#backSA')?.addEventListener('click', () => loadShulchanSection(`${section.slug}.json`))
}

export function initShulchanArukhEvents() {
  document.querySelector('#shulchanBtn')?.addEventListener('click', openShulchanArukh)
}
