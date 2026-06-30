import { state } from '../state.js'
import { escapeHtml } from './utils.js'

let currentParashaFile = null
let currentParashaCommentary = null
let parashaCommentaryCache = {}

const mikraotCommentaries = [
  { slug: 'rashi', title: 'Rachi' },
  { slug: 'onkelos', title: 'Onkelos' },
  { slug: 'sforno', title: 'Sforno' },
  { slug: 'ramban', title: 'Ramban' }
]

export async function openParashiot() {
  state.currentMode = 'parasha'
  state.currentParasha = null
  currentParashaFile = null
  currentParashaCommentary = null
  parashaCommentaryCache = {}

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
  currentParashaFile = file
  currentParashaCommentary = null
  parashaCommentaryCache = {}

  document.querySelector('#segments').innerHTML = '<div class="empty">Chargement de la paracha...</div>'

  try {
    const res = await fetch(`/data/parashiot/${file}`)
    if (!res.ok) throw new Error('Paracha introuvable')

    const data = await res.json()

    let frData = null
    try {
      const frRes = await fetch(`/data/parashiot/${file.replace('.json', '.fr.json')}`)
      if (frRes.ok) frData = await frRes.json()
    } catch {}

    const frByRef = new Map((frData?.verses || []).map(v => [v.ref, v]))

    const verses = (data.verses || []).map(v => {
      const frVerse = frByRef.get(v.ref)

      return {
        ...v,
        fr: frVerse?.fr || v.fr || '',
        rashi: (v.rashi || []).map((r, i) => ({
          ...r,
          fr: frVerse?.rashi?.[i]?.fr || r.fr || ''
        }))
      }
    })

    state.currentMode = 'parasha'
    state.currentParasha = {
      ...data,
      file,
      verses
    }

    const fullHe = verses.map(v => `
      <p class="parashaLine">
        <span class="verseNum">${escapeHtml(v.ref)}</span>
        <span class="he">${v.he || ''}</span>
      </p>
    `).join('')

    const fullFr = verses.map(v => `
      <p class="parashaLine">
        <span class="verseNum">${escapeHtml(v.ref)}</span>
        <span>${escapeHtml(v.fr || 'Traduction française en préparation.')}</span>
      </p>
    `).join('')

    const fullEn = verses.map(v => `
      <p class="parashaLine">
        <span class="verseNum">${escapeHtml(v.ref)}</span>
        <span>${escapeHtml(v.en || 'English translation in preparation.')}</span>
      </p>
    `).join('')

    document.querySelector('#dafTitle').textContent = `📖 ${data.name}`
    document.querySelector('#dafNav').innerHTML = `
      <div class="dafNav">
        <button id="backParashiotBtn">← Liste des parachiot</button>
      </div>
    `

    renderParashaCommentaryButtons()

    document.querySelector('#segments').innerHTML = `
      <article class="segment parashaFull">
        <div class="segNum">${escapeHtml(data.range || '')}</div>

        <section class="parashaSideBySide">
          <div class="parashaColumn translationColumn">
            <h2>${state.currentLang === 'fr' ? 'Traduction française' : 'English translation'}</h2>
            ${state.currentLang === 'fr' ? fullFr : fullEn}
          </div>

          <div class="parashaColumn hebrewColumn">
            <h2>Texte hébreu</h2>
            ${fullHe || 'Texte hébreu non disponible.'}
          </div>
        </section>
      </article>
    `

    document.querySelector('#backParashiotBtn')?.addEventListener('click', openParashiot)
  } catch (e) {
    document.querySelector('#segments').innerHTML = `<div class="empty">Erreur : ${escapeHtml(e.message)}</div>`
  }
}

function renderParashaCommentaryButtons() {
  document.querySelector('#commentBox').innerHTML = `
    <div class="commentActions parashaCommentActions">
      ${mikraotCommentaries.map(c => `
        <button class="parashaCommentaryBtn ${currentParashaCommentary === c.slug ? 'activeLang' : ''}" data-commentary="${escapeHtml(c.slug)}">
          ${escapeHtml(c.title)}
        </button>
      `).join('')}
    </div>

    <div id="parashaCommentaryBox" class="saCommentaryBox">
      Choisis un commentaire : Rachi, Onkelos, Sforno ou Ramban.
    </div>
  `

  document.querySelectorAll('.parashaCommentaryBtn').forEach(btn => {
    btn.addEventListener('click', () => renderGenericParashaCommentary(btn.dataset.commentary))
  })
}

export function renderParashaRashi() {
  currentParashaCommentary = 'rashi'
  renderParashaCommentaryButtons()

  const box = document.querySelector('#parashaCommentaryBox') || document.querySelector('#commentBox')
  const data = state.currentParasha

  if (!data?.verses) {
    box.innerHTML = 'Choisis d’abord une paracha.'
    return
  }

  const html = data.verses
    .filter(v => (v.rashi || []).length)
    .map(v => `
      <section class="rashiBlock">
        <h3>${escapeHtml(v.ref)}</h3>
        ${(v.rashi || []).map(r => `
          <div class="rashiItem">
            <p class="he">${r.he || ''}</p>
            <p>${state.currentLang === 'fr'
              ? escapeHtml(r.fr || r.explanation_fr || 'Traduction / explication de Rachi en préparation.')
              : escapeHtml(r.en || 'Rashi English translation in preparation.')}
            </p>
          </div>
        `).join('')}
      </section>
    `).join('')

  box.innerHTML = html || 'Rachi non disponible pour cette paracha.'
}

function mergeFrenchCommentary(commentary, frCommentary) {
  if (!frCommentary?.verses) return commentary

  const frByRef = new Map((frCommentary.verses || []).map(v => [v.ref, v]))

  return {
    ...commentary,
    verses: (commentary.verses || []).map(v => {
      const frVerse = frByRef.get(v.ref)

      return {
        ...v,
        fr: frVerse?.fr || v.fr || ''
      }
    })
  }
}

async function loadParashaCommentary(slug) {
  if (!currentParashaFile) return null
  if (parashaCommentaryCache[slug]) return parashaCommentaryCache[slug]

  const res = await fetch(`/data/parashiot/commentaries/${slug}/${currentParashaFile}`)
  if (!res.ok) return null

  const rawData = await res.json()

  let frData = null
  try {
    const frFile = currentParashaFile.replace('.json', '.fr.json')
    const frRes = await fetch(`/data/parashiot/commentaries/${slug}/${frFile}`)
    if (frRes.ok) frData = await frRes.json()
  } catch {}

  const data = mergeFrenchCommentary(rawData, frData)
  parashaCommentaryCache[slug] = data

  return data
}

export async function renderGenericParashaCommentary(slug) {
  if (slug === 'rashi') {
    renderParashaRashi()
    return
  }

  currentParashaCommentary = slug
  renderParashaCommentaryButtons()

  const commentary = mikraotCommentaries.find(c => c.slug === slug)
  const title = commentary?.title || slug

  const box = document.querySelector('#parashaCommentaryBox') || document.querySelector('#commentBox')
  box.innerHTML = `<div class="empty">Chargement de ${escapeHtml(title)}...</div>`

  try {
    const data = await loadParashaCommentary(slug)

    if (!data?.verses?.length) {
      box.innerHTML = `${escapeHtml(title)} non disponible pour cette paracha.`
      return
    }

    const availableVerses = data.verses.filter(v => v.he || v.en || v.fr)

    box.innerHTML = `
      <h3>${escapeHtml(title)} — ${escapeHtml(data.name || '')}</h3>

      ${availableVerses.map(v => `
        <section class="rashiBlock">
          <h3>${escapeHtml(v.ref)}</h3>

          <div class="rashiItem">
            <p class="he">${v.he || ''}</p>
            <p>${escapeHtml(
              state.currentLang === 'fr'
                ? (v.fr || `Traduction française de ${title} en préparation.`)
                : (v.en || 'English translation unavailable.')
            )}</p>
          </div>
        </section>
      `).join('') || `${escapeHtml(title)} non disponible pour cette paracha.`}
    `
  } catch (e) {
    box.innerHTML = `<div class="empty">Erreur : ${escapeHtml(e.message)}</div>`
  }
}

export function renderParashaOnkelos() {
  return renderGenericParashaCommentary('onkelos')
}

export function initParashiotEvents() {
  document.querySelector('#parashaBtn')?.addEventListener('click', openParashiot)
}
