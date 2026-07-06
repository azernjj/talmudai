import { state } from '../state.js'
import { escapeHtml } from './utils.js'

let shulchanSectionsCache = null
let currentShulchanSection = null
let currentShulchanSiman = null
let currentShulchanCommentary = null
let commentaryCache = {}

const commentaries = [
  { slug: 'mishnah-berurah', title: 'Mishnah Berurah' },
  { slug: 'beur-halakha', title: 'Biour Halakha' },
  { slug: 'magen-avraham', title: 'Magen Avraham' },
  { slug: 'taz', title: 'Taz' },
  { slug: 'baer-hetev', title: 'Ba’er Hetev' }
]

async function getShulchanSections() {
  if (shulchanSectionsCache) return shulchanSectionsCache

  const res = await fetch('/data/shulchan-arukh/index.json')
  if (!res.ok) throw new Error('Index Choul’han Aroukh introuvable')

  shulchanSectionsCache = await res.json()
  return shulchanSectionsCache
}

async function loadFrenchSection(file) {
  try {
    const frFile = file.replace('.json', '.fr.json')
    const res = await fetch(`/data/shulchan-arukh/${frFile}`)
    if (!res.ok) return null
    return await res.json()
  } catch {
    return null
  }
}

function mergeFrench(section, frSection) {
  if (!frSection?.simanim) return section

  const frBySiman = new Map((frSection.simanim || []).map(s => [String(s.siman), s]))

  return {
    ...section,
    simanim: (section.simanim || []).map(siman => {
      const frSiman = frBySiman.get(String(siman.siman))
      const frBySeif = new Map((frSiman?.seifim || []).map(seif => [String(seif.seif), seif]))

      return {
        ...siman,
        seifim: (siman.seifim || []).map(seif => {
          const frSeif = frBySeif.get(String(seif.seif))

          return {
            ...seif,
            fr: frSeif?.fr || seif.fr || ''
          }
        })
      }
    })
  }
}

function mergeFrenchCommentary(commentary, frCommentary) {
  if (!frCommentary?.simanim) return commentary

  const frBySiman = new Map((frCommentary.simanim || []).map(s => [String(s.siman), s]))

  return {
    ...commentary,
    simanim: (commentary.simanim || []).map(siman => {
      const frSiman = frBySiman.get(String(siman.siman))
      const frById = new Map((frSiman?.items || []).map(item => [String(item.id), item]))

      return {
        ...siman,
        items: (siman.items || []).map(item => {
          const frItem = frById.get(String(item.id))

          return {
            ...item,
            fr: frItem?.fr || item.fr || ''
          }
        })
      }
    })
  }
}

function normalizeText(value = '') {
  return String(value || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[’']/g, '')
    .trim()
}

function parseShulchanSearch(query = '') {
  const q = normalizeText(query)
  const numbers = q.match(/\d+/g) || []
  const simanMatch = q.match(/siman\s*(\d+)/)
  const seifMatch = q.match(/seif\s*(\d+)|paragraph\s*(\d+)/)

  return {
    q,
    raw: String(query || '').trim(),
    numbers,
    siman: simanMatch ? Number(simanMatch[1]) : (numbers[0] ? Number(numbers[0]) : null),
    seif: seifMatch ? Number(seifMatch[1] || seifMatch[2]) : (numbers.length > 1 ? Number(numbers[1]) : null)
  }
}

function seifContains(seif, q) {
  if (!q) return false

  return (
    String(seif.he || '').includes(q) ||
    normalizeText(seif.fr || '').includes(q) ||
    normalizeText(seif.en || '').includes(q)
  )
}

function simanContains(siman, q) {
  if (!q) return false

  return (
    normalizeText(siman.title || '').includes(q) ||
    String(siman.heTitle || '').includes(q) ||
    (siman.seifim || []).some(seif => seifContains(seif, q))
  )
}

function renderShulchanSideButtons(items) {
  const box = document.querySelector('#shulchanLibrary')
  if (!box) return

  box.innerHTML = items.length
    ? items.slice(0, 100).map(r => `
      <button
        class="masechet shulchanSideBtn ${r.type === 'siman' ? 'saSearchResult' : ''}"
        data-file="${escapeHtml(r.section.file)}"
        data-siman="${escapeHtml(r.siman || '')}"
        data-seif="${escapeHtml(r.seif || '')}"
      >
        <span class="saHebrew">${escapeHtml(r.heLabel || r.section.heTitle || '')}</span>
        <small>${escapeHtml(r.label || r.section.title || '')}</small>
      </button>
    `).join('')
    : '<div class="empty">Aucun résultat trouvé.</div>'

  document.querySelectorAll('.shulchanSideBtn').forEach(btn => {
    btn.addEventListener('click', async () => {
      await loadShulchanSection(
        btn.dataset.file,
        btn.dataset.siman ? Number(btn.dataset.siman) : null,
        btn.dataset.seif ? Number(btn.dataset.seif) : null
      )
    })
  })
}

export async function renderShulchanLibrary() {
  const box = document.querySelector('#shulchanLibrary')
  if (!box) return

  try {
    const search = parseShulchanSearch(document.querySelector('#saSearch')?.value || '')
    const sections = await getShulchanSections()

    if (!search.q) {
      renderShulchanSideButtons(sections.map(section => ({
        type: 'section',
        section,
        label: section.title,
        heLabel: section.heTitle
      })))
      return
    }

    box.innerHTML = '<div class="empty">Recherche en cours...</div>'

    const results = []

    for (const section of sections) {
      const sectionMatch =
        normalizeText(section.title || '').includes(search.q) ||
        String(section.heTitle || '').includes(search.raw)

      if (sectionMatch) {
        results.push({
          type: 'section',
          section,
          label: section.title,
          heLabel: section.heTitle
        })
      }

      try {
        const res = await fetch(`/data/shulchan-arukh/${section.file}`)
        if (!res.ok) continue

        const rawData = await res.json()
        const frData = await loadFrenchSection(section.file)
        const merged = mergeFrench(rawData, frData)

        for (const siman of merged.simanim || []) {
          const simanNumber = Number(siman.siman)

          const simanNumberMatch = search.siman
            ? simanNumber === search.siman
            : false

          const textMatch = simanContains(siman, search.q)

          if (simanNumberMatch || textMatch) {
            const matchedSeif = search.seif
              ? (siman.seifim || []).find(seif => Number(seif.seif) === search.seif)
              : null

            results.push({
              type: 'siman',
              section,
              siman: siman.siman,
              seif: matchedSeif ? matchedSeif.seif : '',
              label: `${section.title} — Siman ${siman.siman}${matchedSeif ? `, Seif ${matchedSeif.seif}` : ''}`,
              heLabel: section.heTitle
            })
          }
        }
      } catch {}
    }

    renderShulchanSideButtons(results)
  } catch (e) {
    box.innerHTML = `<div class="empty">Erreur : ${escapeHtml(e.message)}</div>`
  }
}

export async function openShulchanArukh() {
  state.currentMode = 'shulchan'
  state.currentParasha = null
  currentShulchanCommentary = null

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

export async function loadShulchanSection(file, requestedSiman = null, requestedSeif = null) {
  state.currentMode = 'shulchan'
  state.currentParasha = null
  currentShulchanCommentary = null
  commentaryCache = {}

  document.querySelector('#segments').innerHTML = '<div class="empty">Chargement de la section...</div>'

  try {
    const res = await fetch(`/data/shulchan-arukh/${file}`)
    if (!res.ok) throw new Error('Section introuvable')

    const rawData = await res.json()
    const frData = await loadFrenchSection(file)
    const data = {
      ...mergeFrench(rawData, frData),
      file
    }

    currentShulchanSection = data

    document.querySelector('#dafTitle').textContent = `📜 ${data.heTitle} — ${data.title}`

    const simanim = (data.simanim || []).filter(s => (s.seifim || []).length)
    const requested = requestedSiman ? Number(requestedSiman) : null
    const targetSiman = requested
      ? simanim.find(s => Number(s.siman) === requested)
      : null

    renderSimanSelector(data)

    if (targetSiman) {
      renderSiman(data, targetSiman, requestedSeif)
      return
    }

    const firstSiman = simanim[0]

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

      <button id="saFrBtn" class="${state.currentLang === 'fr' ? 'activeLang' : ''}">
        🇫🇷 Français
      </button>

      <button id="saEnBtn" class="${state.currentLang === 'en' ? 'activeLang' : ''}">
        🇬🇧 English
      </button>

      <label class="dafSelectLabel">
        Siman
        <select id="simanSelect">
          ${simanim.map(s => `
            <option value="${escapeHtml(s.siman)}">${escapeHtml(s.siman)}</option>
          `).join('')}
        </select>
      </label>
    </div>
  `

  document.querySelector('#backShulchanBtn')?.addEventListener('click', openShulchanArukh)

  document.querySelector('#saFrBtn')?.addEventListener('click', () => {
    state.currentLang = 'fr'
    localStorage.setItem('talmudLang', state.currentLang)
    renderSimanSelector(section)

    if (currentShulchanSiman) renderSiman(section, currentShulchanSiman)
    if (currentShulchanCommentary) renderShulchanCommentary(currentShulchanCommentary)
  })

  document.querySelector('#saEnBtn')?.addEventListener('click', () => {
    state.currentLang = 'en'
    localStorage.setItem('talmudLang', state.currentLang)
    renderSimanSelector(section)

    if (currentShulchanSiman) renderSiman(section, currentShulchanSiman)
    if (currentShulchanCommentary) renderShulchanCommentary(currentShulchanCommentary)
  })

  document.querySelector('#simanSelect')?.addEventListener('change', e => {
    const siman = simanim.find(s => String(s.siman) === e.target.value)

    if (siman) {
      currentShulchanCommentary = null
      renderSiman(section, siman)
    }
  })
}

function renderSiman(section, siman, focusSeif = null) {
  currentShulchanSiman = siman

  const select = document.querySelector('#simanSelect')
  if (select) select.value = String(siman.siman)

  document.querySelector('#dafTitle').textContent = `📜 ${section.heTitle} — Siman ${siman.siman}`

  renderCommentaryButtons()

  document.querySelector('#segments').innerHTML = `
    <article class="segment parashaFull">
      <div class="segNum">${escapeHtml(section.heTitle)} — Siman ${escapeHtml(siman.siman)}</div>

      ${(siman.seifim || []).map(seif => `
        <section
          class="parashaSideBySide shulchanSeif ${focusSeif && Number(seif.seif) === Number(focusSeif) ? 'targetSeif' : ''}"
          id="sa-seif-${escapeHtml(seif.seif)}"
        >
          <div class="parashaColumn translationColumn">
            <h3>${state.currentLang === 'fr' ? 'Seif' : 'Paragraph'} ${escapeHtml(seif.seif)}</h3>
            <p>${escapeHtml(
              state.currentLang === 'fr'
                ? (seif.fr || 'Traduction française en préparation.')
                : (seif.en || 'English translation in preparation.')
            )}</p>
          </div>

          <div class="parashaColumn hebrewColumn">
            <h3>סעיף ${escapeHtml(seif.seif)}</h3>
            <p class="he">${seif.he || ''}</p>
          </div>
        </section>
      `).join('')}
    </article>
  `

  if (focusSeif) {
    setTimeout(() => {
      document.querySelector(`#sa-seif-${CSS.escape(String(focusSeif))}`)?.scrollIntoView({
        behavior: 'smooth',
        block: 'center'
      })
    }, 100)
  }
}

function renderCommentaryButtons() {
  document.querySelector('#commentBox').innerHTML = `
    <div class="commentActions shulchanCommentActions">
      ${commentaries.map(c => `
        <button class="saCommentaryBtn ${currentShulchanCommentary === c.slug ? 'activeLang' : ''}" data-commentary="${escapeHtml(c.slug)}">
          ${escapeHtml(c.title)}
        </button>
      `).join('')}
    </div>

    <div id="saCommentaryBox" class="saCommentaryBox">
      Choisis un commentaire du Choul’han Aroukh.
    </div>
  `

  document.querySelectorAll('.saCommentaryBtn').forEach(btn => {
    btn.addEventListener('click', () => renderShulchanCommentary(btn.dataset.commentary))
  })
}

async function loadCommentary(slug) {
  const sectionFile = currentShulchanSection?.file || 'orach-chaim.json'
  const key = `${slug}/${sectionFile}`

  if (commentaryCache[key]) return commentaryCache[key]

  const rawRes = await fetch(`/data/shulchan-arukh/commentaries/${slug}/${sectionFile}`)
  if (!rawRes.ok) throw new Error('Commentaire introuvable')

  const rawData = await rawRes.json()

  let frData = null
  try {
    const frFile = sectionFile.replace('.json', '.fr.json')
    const frRes = await fetch(`/data/shulchan-arukh/commentaries/${slug}/${frFile}`)
    if (frRes.ok) frData = await frRes.json()
  } catch {}

  const merged = mergeFrenchCommentary(rawData, frData)
  commentaryCache[key] = merged

  return merged
}

async function renderShulchanCommentary(slug) {
  currentShulchanCommentary = slug

  const box = document.querySelector('#saCommentaryBox') || document.querySelector('#commentBox')

  if (!currentShulchanSiman) {
    box.innerHTML = 'Choisis d’abord un siman.'
    return
  }

  box.innerHTML = '<div class="empty">Chargement du commentaire...</div>'

  try {
    const data = await loadCommentary(slug)
    const siman = (data.simanim || []).find(s => String(s.siman) === String(currentShulchanSiman.siman))
    const title = data.title || slug

    renderCommentaryButtons()

    const targetBox = document.querySelector('#saCommentaryBox') || document.querySelector('#commentBox')

    if (!siman?.items?.length) {
      targetBox.innerHTML = `${escapeHtml(title)} non disponible pour ce siman.`
      return
    }

    targetBox.innerHTML = `
      <h3>${escapeHtml(title)} — Siman ${escapeHtml(currentShulchanSiman.siman)}</h3>

      ${siman.items.map(item => `
        <div class="rashiItem">
          <p class="he">${item.he || ''}</p>
          <p>${escapeHtml(
            state.currentLang === 'fr'
              ? (item.fr || 'Traduction française du commentaire en préparation.')
              : (item.en || 'English translation unavailable.')
          )}</p>
        </div>
      `).join('')}
    `
  } catch (e) {
    box.innerHTML = `<div class="empty">Erreur : ${escapeHtml(e.message)}</div>`
  }
}

export function renderShulchanCommentaryNotice() {
  renderCommentaryButtons()
}

export function initShulchanArukhEvents() {
  document.querySelector('#shulchanBtn')?.addEventListener('click', openShulchanArukh)

  const search = document.querySelector('#saSearch')
  if (search) {
    search.addEventListener('input', () => {
      renderShulchanLibrary()
    })
  }

  renderShulchanLibrary()
}
