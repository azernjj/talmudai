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
    const verses = data.verses || []

      
      const fullHe = verses.map(v => `
      <p class="parashaLine">
        <span class="verseNum">${escapeHtml(v.ref)}</span>
        <span class="he">${v.he || ''}</span>
      </p>
    `).join('')
    
    const fullEn = verses.map(v => `
      <p class="parashaLine">
        <span class="verseNum">${escapeHtml(v.ref)}</span>
        <span>${escapeHtml(v.en || '')}</span>
      </p>
    `).join('')
    
    const fullFr = verses.map(v => `
      <p class="parashaLine">
        <span class="verseNum">${escapeHtml(v.ref)}</span>
        <span>${escapeHtml(v.fr || '') || 'Traduction française en préparation.'}</span>
      </p>
    `).join('')
    
    const fullRashi = verses
      .filter(v => (v.rashi || []).length)
      .map(v => `
        <section class="rashiBlock">
          <h3>${escapeHtml(v.ref)}</h3>
          ${(v.rashi || []).map(r => `
            <div class="rashiItem">
              <p class="he">${r.he || ''}</p>
              <p>${state.currentLang === 'fr'
                ? (r.fr || r.explanation_fr || 'Traduction / explication de Rachi en préparation.')
                : (r.en || 'Rashi English translation in preparation.')}
              </p>
            </div>
          `).join('')}
        </section>
      `).join('')

    document.querySelector('#dafTitle').textContent = `📖 ${data.name}`
    document.querySelector('#dafNav').innerHTML = `
      <div class="dafNav">
        <button id="backParashiotBtn">← Liste des parachiot</button>
      </div>
    `
    document.querySelector('#commentBox').innerHTML = 'Texte complet de la paracha avec Rachi.'

    document.querySelector('#segments').innerHTML = `
      <article class="segment parashaFull">
        <div class="segNum">${escapeHtml(data.range || '')}</div>

        <section class="parashaFullSection">
          <h2>Texte hébreu</h2>
          <div class="parashaFullText">${fullHe || 'Texte hébreu non disponible.'}</div>
        </section>

        <section class="parashaFullSection">
          <h2>Traduction</h2>
          <div class="translation parashaFullTranslation">
            ${state.currentLang === 'fr'
              ? (fullFr || 'Traduction française en préparation.')
              : (fullEn || 'English translation in preparation.')}
          </div>
        </section>

        <details class="parashaRashiFull">
          <summary>Rachi complet</summary>
          ${fullRashi || '<div class="empty">Rachi non disponible.</div>'}
        </details>
      </article>
    `

    document.querySelector('#backParashiotBtn')?.addEventListener('click', openParashiot)
  } catch (e) {
    document.querySelector('#segments').innerHTML = `<div class="empty">Erreur : ${escapeHtml(e.message)}</div>`
  }
}

export function initParashiotEvents() {
  document.querySelector('#parashaBtn')?.addEventListener('click', openParashiot)
}
