import { state } from '../state.js'
import { escapeHtml } from './utils.js'

export async function openParashiot() {
  document.querySelector('#dafTitle').textContent = '📖 Parachiot'
  document.querySelector('#dafNav').innerHTML = ''
  document.querySelector('#commentBox').innerHTML = 'Choisis une paracha.'
  document.querySelector('#segments').innerHTML = '<div class="empty">Chargement des parachiot...</div>'

  try {
    const res = await fetch('/data/parashiot/index.json')
    if (!res.ok) throw new Error('Index des parachiot introuvable')

    const parashiot = await res.json()

    const books = {
      Genesis: 'בראשית',
      Exodus: 'שמות',
      Leviticus: 'ויקרא',
      Numbers: 'במדבר',
      Deuteronomy: 'דברים'
    }

    document.querySelector('#segments').innerHTML = Object.entries(books).map(([book, heBook]) => {
      const items = parashiot.filter(p => p.range.startsWith(book))

      return `
        <section class="parashaBook">
          <h2>${heBook} — ${book}</h2>
          <div class="parashaGrid">
            ${items.map(p => `
              <button class="parashaCard openParasha" data-file="${escapeHtml(p.file)}">
                <span class="parashaName">${escapeHtml(p.name)}</span>
                <small>${escapeHtml(p.range)}</small>
              </button>
            `).join('')}
          </div>
        </section>
      `
    }).join('')

    document.querySelectorAll('.openParasha').forEach(btn => {
      btn.addEventListener('click', () => loadParasha(btn.dataset.file))
    })
  } catch (e) {
    document.querySelector('#segments').innerHTML = `<div class="empty">Erreur : ${escapeHtml(e.message)}</div>`
  }
}

export async function loadParasha(file) {
  document.querySelector('#segments').innerHTML = '<div class="empty">Chargement de la paracha...</div>'

  try {
    const res = await fetch(`/data/parashiot/${file}`)
    if (!res.ok) throw new Error('Paracha introuvable')

    const data = await res.json()

    document.querySelector('#dafTitle').textContent = `📖 ${data.name}`
    document.querySelector('#dafNav').innerHTML = `
      <div class="dafNav">
        <button id="backParashiotBtn">← Liste des parachiot</button>
      </div>
    `
    document.querySelector('#commentBox').innerHTML = 'Rachi apparaît sous chaque verset.'

    document.querySelector('#segments').innerHTML = (data.verses || []).map(v => `
      <article class="segment parashaVerse">
        <div class="segNum">${escapeHtml(v.ref)}</div>

        <div class="he parashaHebrew">${v.he || ''}</div>

        <div class="translation">
          ${state.currentLang === 'fr'
            ? (v.fr || 'Traduction française en préparation.')
            : (v.en || 'English translation in preparation.')}
        </div>

        ${(v.rashi || []).length ? `
          <details class="parashaRashi">
            <summary>▶ Rachi (${v.rashi.length})</summary>
            ${(v.rashi || []).map(r => `
              <div class="rashiItem">
                <p class="he">${r.he || ''}</p>
                <p>${state.currentLang === 'fr'
                  ? (r.fr || r.explanation_fr || 'Traduction / explication de Rachi en préparation.')
                  : (r.en || 'Rashi English translation in preparation.')}
                </p>
              </div>
            `).join('')}
          </details>
        ` : ''}
      </article>
    `).join('')

    document.querySelector('#backParashiotBtn')?.addEventListener('click', openParashiot)
  } catch (e) {
    document.querySelector('#segments').innerHTML = `<div class="empty">Erreur : ${escapeHtml(e.message)}</div>`
  }
}

export function initParashiotEvents() {
  document.querySelector('#parashaBtn')?.addEventListener('click', openParashiot)
}
