import { state, sedarim } from '../state.js'
import { sortDaf, escapeHtml } from './utils.js'
import { installHebrewWordClick } from './dictionary.js'
import { renderParashaRashi, loadParasha } from './parashiot.js'
import { renderShulchanCommentaryNotice } from './shulchan-arukh.js'
import { correctionButtonHtml, installCorrectionButtons } from './correction-admin.js'
import { refreshCurrentMishnaView } from './mishna.js'

let extraCommentaryCache = {}

const COMMENTARY_GROUPS = [
  ['rachi', 'Rachi', ['rachi', 'rashi']],
  ['tossefot', 'Tossefot', ['tossefot', 'tosafot']],
  ['rosh', 'Roch', ['rosh']],
  ['ritva', 'Ritva', ['ritva']]
]
let selectedCommentarySegment = 0
let commentaryFilter = 'all'

function normalizeCommentHebrew(value) {
  return cleanText(value)
    .normalize('NFKD')
    .replace(/[\u0591-\u05c7]/g, '')
    .replace(/בעה["״׳']?ב/g, 'בעל הבית')
    .replace(/רה["״׳']?ר/g, 'רשות הרבים')
    .replace(/רה["״׳']?י/g, 'רשות היחיד')
    .replace(/[\u0022\u0027\u05f3\u05f4`.,:;!?()[\]{}־–—-]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function commentaryStart(item) {
  const he = typeof item === 'string' ? item : (item?.he || item?.text || '')
  const opening = he.split(/\s+[–—-]\s+|[:.]\s+/)[0]
  return normalizeCommentHebrew(opening)
    .replace(/^(?:מתני|מתניתין|גמ|גמרא|ד ה)\s+/, '')
}

function getDafCommentaries(daf) {
  return COMMENTARY_GROUPS.flatMap(([type, label, aliases]) => {
    const items = aliases.map(k => daf[k]).find(a => Array.isArray(a) && a.length) || []
    return items.map((item, order) => ({type, label, item, order}))
  })
}

function locateComment(comment, segments) {
  const start = commentaryStart(comment.item)
  const words = start.split(' ').filter(w => w.length > 1 && w !== 'וכו' && w !== 'וגו')
  if (!words.length) return -1

  const texts = segments.map(s => normalizeCommentHebrew(s.he || '')
    .replace(/^(?:מתני|מתניתין|גמ|גמרא)\s+/, ''))

  for (let n = Math.min(8, words.length); n >= 2; n--) {
    const phrase = words.slice(0, n).join(' ')
    const hits = texts.flatMap((t, i) => t.includes(phrase) ? [i] : [])
    if (hits.length === 1) return hits[0]
    if (hits.length > 1) return -1
  }

  return -1
}

function commentaryCandidates(comment, texts) {
  const words = commentaryStart(comment.item)
    .split(' ')
    .filter(w => w && !['וכו', 'וגו', 'כו'].includes(w))

  if (!words.length) return []

  // Les expressions de deux mots ou plus sont prioritaires.
  for (let n = Math.min(8, words.length); n >= 2; n--) {
    const phrase = words.slice(0, n).join(' ')
    const hits = texts.flatMap((t, i) => t.includes(phrase) ? [i] : [])
    if (hits.length) return hits
  }

  // Un seul mot doit être suffisamment distinctif.
  const word = words[0]
  if (word.length < 4) return []

  return texts.flatMap((t, i) =>
    t.split(' ').includes(word) ? [i] : []
  )
}

function contextualCommentaryMatches(comments, segments) {
  const texts = segments.map(s => normalizeCommentHebrew(s.he || ''))

  // Les correspondances V1 restent nos points d'ancrage.
  const baseline = comments.map(c => locateComment(c, segments))
  const result = [...baseline]

  comments.forEach((comment, i) => {
    if (baseline[i] >= 0) return

    const words = commentaryStart(comment.item)
      .split(' ')
      .filter(w => w && !['וכו', 'וגו', 'כו'].includes(w))

    if (!words.length) return

    // Éviter les associations basées sur un mot générique.
    if (words.length === 1 &&
        ['מתניתין', 'מתני', 'גמרא', 'גמ'].includes(words[0])) return

    const hits = commentaryCandidates(comment, texts)
    if (!hits.length) return

    const before = baseline.slice(0, i).filter(n => n >= 0)
    const after = baseline.slice(i + 1).filter(n => n >= 0)

    const lower = before.length ? before[before.length - 1] : 0
    const upper = after.length ? after[0] : texts.length - 1

    if (lower > upper) return

    const valid = hits.filter(n => n >= lower && n <= upper)

    // Une seule correspondance compatible avec l'ordre.
    if (valid.length === 1) result[i] = valid[0]
  })

  return result
}

function commentaryEntries(daf) {
  const segments = daf.segments || []
  const comments = getDafCommentaries(daf)
  const positions = new Map()

  // Rachi, Tossefot et les autres commentateurs sont
  // analysés séparément pour respecter leur propre ordre.
  for (const [type] of COMMENTARY_GROUPS) {
    const group = comments.filter(c => c.type === type)
    const matches = contextualCommentaryMatches(group, segments)
    group.forEach((comment, i) => positions.set(comment, matches[i]))
  }

  return comments.map(c => ({
    ...c,
    segmentIndex: positions.get(c) ?? -1
  }))
}

function commentaryCard(c) {
  const he = typeof c.item === 'string' ? c.item : (c.item?.he || c.item?.text || '')
  const fr = typeof c.item === 'string' ? '' : (c.item?.fr || '')
  const en = typeof c.item === 'string' ? '' : (c.item?.en || '')
  const translation = state.currentLang === 'fr'
    ? (fr || 'Traduction française en préparation.')
    : (en || 'English translation in preparation.')
  return `<details class="mefarshemDetails syncedComment">
    <summary class="mefarshemSummary">📖 ${escapeHtml(c.label)}</summary>
    <div class="mefarshemBody">
      <p class="he" dir="rtl">${escapeHtml(he)}</p>
      <p class="mefarshemTrad">${escapeHtml(cleanText(translation))}</p>
    </div>
  </details>`
}

function currentCommentaryMode() {
  const choice = localStorage.getItem('talmudCommentaryMode') || 'auto'
  if (choice === 'auto') return window.matchMedia('(max-width: 800px)').matches ? 'inline' : 'side'
  return choice
}

function renderSyncedCommentaries() {
  if (state.currentMode !== 'talmud') return
  const daf = state.currentData?.dapim?.[state.currentDaf]
  const box = document.querySelector('#commentBox')
  if (!daf || !box) return
  const entries = commentaryEntries(daf)
  const mode = currentCommentaryMode()
  const allowed = c => commentaryFilter === 'all' || c.type === commentaryFilter
  const selected = Math.min(selectedCommentarySegment, Math.max(0, (daf.segments || []).length - 1))
  const associated = entries.filter(c => c.segmentIndex === selected && allowed(c))
  const unmatched = entries.filter(c => c.segmentIndex < 0 && allowed(c))
  const controls = `<div class="commentModeBar">
    <label for="commentModeSelect">Affichage :</label>
    <select id="commentModeSelect" aria-label="Affichage des commentaires">
      <option value="auto" ${(!localStorage.getItem('talmudCommentaryMode') || localStorage.getItem('talmudCommentaryMode') === 'auto') ? 'selected' : ''}>Automatique</option>
      <option value="side" ${localStorage.getItem('talmudCommentaryMode') === 'side' ? 'selected' : ''}>Colonne droite</option>
      <option value="inline" ${localStorage.getItem('talmudCommentaryMode') === 'inline' ? 'selected' : ''}>Sous le texte</option>
    </select>
  </div>`
  const inline = document.querySelectorAll('#segments .syncedInlineComments')
  inline.forEach((el, i) => {
    const related = entries.filter(c => c.segmentIndex === i && allowed(c))
    el.innerHTML = mode === 'inline' && related.length
      ? `<div class="syncedInlineTitle">Commentaires de ce passage</div>${related.map(commentaryCard).join('')}`
      : ''
    el.style.display = mode === 'inline' && related.length ? 'block' : 'none'
  })
  document.querySelectorAll('#segments .segment').forEach((el, i) => {
    el.classList.toggle('syncedSelected', mode === 'side' && i === selected)
  })
  box.style.display = 'block'
  box.innerHTML = controls + (mode === 'side'
    ? `<p class="syncedHint">Passage ${selected + 1} — cliquez sur un passage de la Guemara pour voir ses commentaires.</p>
       ${associated.length ? associated.map(commentaryCard).join('') : '<p>Aucun commentaire associé avec certitude à ce passage.</p>'}`
    : '<p>Les commentaires sont affichés sous les passages correspondants.</p>')
    + (unmatched.length ? `<details class="mefarshemDetails">
      <summary class="mefarshemSummary">Autres commentaires du daf (${unmatched.length}) — correspondance à vérifier</summary>
      <div class="mefarshemBody">${unmatched.map(commentaryCard).join('')}</div>
    </details>` : '')
  box.querySelector('#commentModeSelect')?.addEventListener('change', e => {
    localStorage.setItem('talmudCommentaryMode', e.target.value)
    renderSyncedCommentaries()
  })
}

function installSyncedCommentaryClicks() {
  document.querySelectorAll('#segments .segment').forEach((el, i) => {
    el.addEventListener('click', event => {
      if (event.target.closest('button, a, details, summary, input, select, textarea, .clickableHe')) return
      selectedCommentarySegment = i
      renderSyncedCommentaries()
    })
  })
}



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


function hasContent(value) {
  if (Array.isArray(value)) return value.length > 0
  if (value && typeof value === 'object') return Object.keys(value).length > 0
  return String(value ?? '').trim().length > 0
}

function studyDetails(title, content, className = '') {
  if (!hasContent(content)) return ''
  return `
    <details class="mefarshemDetails talmudStudyDetails ${escapeHtml(className)}">
      <summary class="mefarshemSummary">${escapeHtml(title)}</summary>
      <div class="mefarshemBody talmudStudyBody">${content}</div>
    </details>
  `
}

function studyParagraph(value, className = '') {
  if (!hasContent(value)) return ''
  return `<p class="${escapeHtml(className)}">${escapeHtml(cleanText(value))}</p>`
}

function studyList(items) {
  if (!Array.isArray(items) || !items.length) return ''
  return `
    <ul class="talmudStudyList">
      ${items
        .filter(hasContent)
        .map(item => `<li>${escapeHtml(cleanText(item))}</li>`)
        .join('')}
    </ul>
  `
}

function renderLineByLine(items) {
  if (!Array.isArray(items) || !items.length) return ''
  const content = items.map(item => {
    if (typeof item === 'string') {
      return `<div class="talmudStudyItem">${studyParagraph(item)}</div>`
    }

    const original = item?.texte || item?.texte_original || item?.he || ''
    const translation = item?.traduction || item?.traduction_fr || item?.fr || ''
    const explanation = item?.explication || item?.commentaire || ''

    if (!hasContent(original) && !hasContent(translation) && !hasContent(explanation)) return ''

    return `
      <div class="talmudStudyItem">
        ${hasContent(original) ? `<p class="he clickableHe">${original}</p>` : ''}
        ${studyParagraph(translation, 'talmudStudyTranslation')}
        ${hasContent(explanation)
          ? `<p><strong>Explication :</strong> ${escapeHtml(cleanText(explanation))}</p>`
          : ''}
      </div>
    `
  }).join('')

  return studyDetails('🧩 Explication ligne par ligne', content)
}

function renderWordByWord(items) {
  if (!Array.isArray(items) || !items.length) return ''

  const rows = items.map(item => {
    if (typeof item === 'string') {
      return `
        <tr>
          <td colspan="5">${escapeHtml(cleanText(item))}</td>
        </tr>
      `
    }

    return `
      <tr>
        <td class="he clickableHe">${item?.mot_hebreu || item?.mot || ''}</td>
        <td>${escapeHtml(cleanText(item?.translitteration || ''))}</td>
        <td>${escapeHtml(cleanText(item?.sens_francais || item?.sens || item?.traduction || ''))}</td>
        <td>${escapeHtml(cleanText(item?.fonction_grammaticale || item?.fonction || ''))}</td>
        <td>${escapeHtml(cleanText(item?.note || ''))}</td>
      </tr>
    `
  }).join('')

  return studyDetails('🔤 Mot à mot', `
    <div class="talmudStudyTableWrap">
      <table class="talmudStudyTable">
        <thead>
          <tr>
            <th>Mot</th>
            <th>Translittération</th>
            <th>Sens</th>
            <th>Fonction</th>
            <th>Note</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `)
}

function renderDifficultWords(items) {
  if (!Array.isArray(items) || !items.length) return ''

  const content = items.map(item => {
    if (typeof item === 'string') return `<li>${escapeHtml(cleanText(item))}</li>`

    const term = item?.terme || item?.mot || ''
    const definition = item?.definition || item?.sens || ''
    const role = item?.role_dans_le_passage || item?.role || ''

    return `
      <li>
        ${hasContent(term) ? `<strong class="he">${term}</strong>` : ''}
        ${hasContent(definition) ? ` — ${escapeHtml(cleanText(definition))}` : ''}
        ${hasContent(role) ? `<div><em>Dans le passage :</em> ${escapeHtml(cleanText(role))}</div>` : ''}
      </li>
    `
  }).join('')

  return studyDetails('📚 Mots difficiles', `<ul class="talmudStudyList">${content}</ul>`)
}

function renderNewNotions(items) {
  if (!Array.isArray(items) || !items.length) return ''

  const content = items.map(item => {
    if (typeof item === 'string') return `<li>${escapeHtml(cleanText(item))}</li>`

    const notion = item?.notion || item?.titre || ''
    const explanation = item?.explication || item?.definition || ''

    return `
      <li>
        ${hasContent(notion) ? `<strong>${escapeHtml(cleanText(notion))}</strong>` : ''}
        ${hasContent(explanation) ? ` — ${escapeHtml(cleanText(explanation))}` : ''}
      </li>
    `
  }).join('')

  return studyDetails('💡 Notions nouvelles', `<ul class="talmudStudyList">${content}</ul>`)
}

function renderMefarshim(items) {
  if (!Array.isArray(items) || !items.length) return ''

  const content = items.map(item => {
    if (typeof item === 'string') {
      return `<div class="talmudStudyItem">${studyParagraph(item)}</div>`
    }

    const author = item?.auteur || item?.nom || 'Commentaire'
    const reference = item?.reference || ''
    const opinion = item?.opinion || item?.explication || ''
    const logic = item?.logique || ''
    const disagreements = item?.desaccords || item?.desaccord || ''
    const certainty = item?.niveau_certitude || ''

    return `
      <details class="mefarshemDetails talmudInnerDetails">
        <summary class="mefarshemSummary">
          ${escapeHtml(cleanText(author))}
          ${hasContent(reference) ? ` — ${escapeHtml(cleanText(reference))}` : ''}
        </summary>
        <div class="mefarshemBody">
          ${studyParagraph(opinion)}
          ${hasContent(logic)
            ? `<p><strong>Logique :</strong> ${escapeHtml(cleanText(logic))}</p>`
            : ''}
          ${hasContent(disagreements)
            ? `<p><strong>Désaccords :</strong> ${escapeHtml(cleanText(disagreements))}</p>`
            : ''}
          ${hasContent(certainty)
            ? `<p><small>Niveau de certitude : ${escapeHtml(cleanText(certainty))}</small></p>`
            : ''}
        </div>
      </details>
    `
  }).join('')

  return studyDetails('📖 Méfarchim classiques', content)
}

function renderHalakha(value) {
  if (!hasContent(value)) return ''

  if (typeof value === 'string') {
    return studyDetails('⚖️ Halakha', studyParagraph(value))
  }

  const decision = value?.decision || value?.halakha_retenue || ''
  const sources = Array.isArray(value?.sources) ? value.sources : []
  const reserve = value?.reserve || ''

  const content = `
    ${studyParagraph(decision)}
    ${sources.length ? `<p><strong>Sources halakhiques :</strong></p>${studyList(sources)}` : ''}
    ${hasContent(reserve)
      ? `<p><strong>Réserve :</strong> ${escapeHtml(cleanText(reserve))}</p>`
      : ''}
  `

  return studyDetails('⚖️ Halakha', content)
}

function renderSourceLinks(items) {
  if (!Array.isArray(items) || !items.length) return ''

  const content = items.map(item => {
    if (typeof item === 'string') return `<li>${escapeHtml(cleanText(item))}</li>`

    const type = item?.type || ''
    const reference = item?.reference || ''
    const explanation = item?.lien_explique || item?.explication || ''

    return `
      <li>
        ${hasContent(type) ? `<strong>${escapeHtml(cleanText(type))}</strong>` : ''}
        ${hasContent(reference) ? ` — ${escapeHtml(cleanText(reference))}` : ''}
        ${hasContent(explanation) ? `<div>${escapeHtml(cleanText(explanation))}</div>` : ''}
      </li>
    `
  }).join('')

  return studyDetails('🔗 Liens avec les sources', `<ul class="talmudStudyList">${content}</ul>`)
}

function renderQuestions(items) {
  if (!Array.isArray(items) || !items.length) return ''

  const content = items.map((item, index) => {
    if (typeof item === 'string') return `<li>${escapeHtml(cleanText(item))}</li>`

    const question = item?.question || ''
    const answer = item?.reponse || item?.réponse || ''

    return `
      <li>
        <strong>${index + 1}. ${escapeHtml(cleanText(question))}</strong>
        ${hasContent(answer) ? `<div>${escapeHtml(cleanText(answer))}</div>` : ''}
      </li>
    `
  }).join('')

  return studyDetails('❓ Questions de révision', `<ol class="talmudStudyList">${content}</ol>`)
}

function renderSources(items) {
  if (!Array.isArray(items) || !items.length) return ''

  const content = items.map(item => {
    if (typeof item === 'string') return `<li>${escapeHtml(cleanText(item))}</li>`

    const work = item?.auteur_ou_ouvrage || item?.ouvrage || item?.auteur || ''
    const reference = item?.reference || ''
    const usage = item?.usage || ''
    const status = item?.statut || ''

    return `
      <li>
        ${hasContent(work) ? `<strong>${escapeHtml(cleanText(work))}</strong>` : ''}
        ${hasContent(reference) ? ` — ${escapeHtml(cleanText(reference))}` : ''}
        ${hasContent(usage) ? `<div>${escapeHtml(cleanText(usage))}</div>` : ''}
        ${hasContent(status) ? `<small>Statut : ${escapeHtml(cleanText(status))}</small>` : ''}
      </li>
    `
  }).join('')

  return studyDetails('📑 Sources', `<ul class="talmudStudyList">${content}</ul>`)
}

function renderTalmudStudy(seg) {
  const study = seg?.etude_complete_fr
  if (!study || typeof study !== 'object') return ''

  const simpleSection = (title, value, icon = '') =>
    hasContent(value)
      ? studyDetails(`${icon}${title}`, studyParagraph(value))
      : ''

  return `
    <div class="talmudCompleteStudy">
      ${hasContent(seg.fr_fluide || study.traduction_fluide)
        ? simpleSection('Traduction fluide', seg.fr_fluide || study.traduction_fluide, '📝 ')
        : ''}
      ${renderLineByLine(study.explication_ligne_par_ligne)}
      ${renderWordByWord(study.mot_a_mot)}
      ${renderDifficultWords(study.mots_difficiles)}
      ${renderNewNotions(study.notions_nouvelles)}
      ${simpleSection('Introduction', study.introduction, '📘 ')}
      ${simpleSection('Contexte général', study.contexte_general, '🧭 ')}
      ${renderMefarshim(study.mefarshim)}
      ${renderHalakha(study.halakha || study.halakha_retenue)}
      ${Array.isArray(study.consequences_pratiques) && study.consequences_pratiques.length
        ? studyDetails('✅ Conséquences pratiques', studyList(study.consequences_pratiques))
        : ''}
      ${renderSourceLinks(study.liens_sources)}
      ${Array.isArray(study.exemples_concrets) && study.exemples_concrets.length
        ? studyDetails('🧪 Exemples concrets', studyList(study.exemples_concrets))
        : ''}
      ${Array.isArray(study.resume) && study.resume.length
        ? studyDetails('📌 Résumé', studyList(study.resume))
        : ''}
      ${simpleSection('Synthèse finale', study.synthese_finale, '🎯 ')}
      ${renderSources(study.sources)}
      ${Array.isArray(study.avertissements) && study.avertissements.length
        ? studyDetails('⚠️ Avertissements', studyList(study.avertissements))
        : ''}
    </div>
  `
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

  const commentBox = document.querySelector('#commentBox')
  if (commentBox) commentBox.style.display = 'none'

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

function renderCommentaireDetails(items, label) {
  if (!items || !items.length) return ''
  const content = items.map(x => {
    const he = typeof x === 'string' ? x : (x.he || '')
    const fr = typeof x === 'string' ? '' : (x.fr || '')
    const en = typeof x === 'string' ? '' : (x.en || '')
    if (!he.trim()) return ''
    const trad = state.currentLang === 'fr'
      ? (fr || 'Traduction française en préparation.')
      : (en || 'English translation in preparation.')
    return `
      <div class="mefarshemItem">
        <p class="he">${he}</p>
        <p class="mefarshemTrad">${escapeHtml(cleanText(trad))}</p>
      </div>
    `
  }).join('')
  if (!content.trim()) return ''
  return `
    <details class="mefarshemDetails">
      <summary class="mefarshemSummary">📖 ${escapeHtml(label)}</summary>
      <div class="mefarshemBody">${content}</div>
    </details>
  `
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
  selectedCommentarySegment = 0
  const dapim = Object.keys(state.currentData.dapim).sort(sortDaf)
  const idx = dapim.indexOf(daf)
  const prev = idx > 0 ? dapim[idx - 1] : null
  const next = idx < dapim.length - 1 ? dapim[idx + 1] : null

  document.querySelector('#dafTitle').textContent = `${state.currentData.title} ${daf}`

  document.querySelector('#segments').innerHTML = `
    ${(data.segments || []).map((seg, index) => {
      return `
      <article class="segment" data-segment-index="${index}" tabindex="0">
        <div class="segNum">
          Segment ${index + 1}
          ${correctionButtonHtml('segments', index)}
        </div>
        <div class="he clickableHe">${seg.he || ''}</div>
        ${state.currentLang === 'fr' && hasContent(seg.fr_html)
          ? `
            <div class="talmudV72Study">
              ${seg.fr_html}
            </div>
          `
          : `
            <div class="translation">
              ${state.currentLang === 'fr'
                ? escapeHtml(cleanText(seg.fr || 'Traduction française en préparation.'))
                : escapeHtml(cleanText(seg.en || 'English translation in preparation.'))}
            </div>
          `}
        ${state.currentLang === 'fr' && !hasContent(seg.fr_html)
          ? renderTalmudStudy(seg)
          : ''}
        <div class="syncedInlineComments" style="display:none"></div>
      </article>
      `
    }).join('')}

    <div class="bottomNav">
      ${prev ? `<button id="prevDafBtn">← Daf précédent (${escapeHtml(prev)})</button>` : ''}
      ${next ? `<button id="nextDafBtn">Daf suivant (${escapeHtml(next)}) →</button>` : ''}
    </div>
  `



  if (prev) document.querySelector('#prevDafBtn')?.addEventListener('click', () => goToDaf(prev))
  if (next) document.querySelector('#nextDafBtn')?.addEventListener('click', () => goToDaf(next))

  installHebrewWordClick()
  installCorrectionButtons()
  installSyncedCommentaryClicks()
  renderSyncedCommentaries()
}

async function renderExtraInline(slug, title, boxSelector) {
  const box = document.querySelector(boxSelector)
  if (!box) return
  box.innerHTML = `<div class="empty">Chargement de ${escapeHtml(title)}...</div>`

  try {
    const data = await loadExtraCommentary(slug)
    if (!data?.dapim?.length) {
      box.innerHTML = ''
      return
    }

    const daf = (data.dapim || []).find(d => String(d.daf) === String(state.currentDaf))
    if (!daf?.comments?.length) {
      box.innerHTML = ''
      return
    }

    const items = daf.comments
    box.innerHTML = renderCommentaireDetails(items, title)
  } catch (e) {
    box.innerHTML = `<div class="empty">Erreur : ${escapeHtml(e.message)}</div>`
  }
}

export function renderCommentary(type) {
  if (!state.currentData || !state.currentData.dapim || !state.currentData.dapim[state.currentDaf]) return
  const data = state.currentData.dapim[state.currentDaf]
  const aliases = {
    rachi: ['rashi', 'rachi'],
    tossefot: ['tosafot', 'tossefot']
  }
  const keys = aliases[type] || [type]
  const items = keys.map(key => data[key]).find(
    value => Array.isArray(value) && value.length > 0
  ) || []
  const box = document.querySelector('#talmudCommentaryBox') || document.querySelector('#commentBox')
  if (!box) return

  box.innerHTML = items.length
    ? items.map(x => {
      if (typeof x === 'string') return `<div class="rashiItem"><p class="he">${x}</p></div>`
      return `
        <div class="rashiItem">
          <p class="he">${x.he || x.text || ''}</p>
          <p>${escapeHtml(state.currentLang === 'fr'
            ? cleanText(x.fr || x.en || 'Traduction française en préparation.')
            : cleanText(x.en || 'English translation unavailable.'))}</p>
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
  if (!box) return
  box.innerHTML = `<div class="empty">Chargement de ${escapeHtml(title)}...</div>`

  try {
    const data = await loadExtraCommentary(slug)
    if (!data?.dapim?.length) { box.innerHTML = `${escapeHtml(title)} non disponible pour ce traité.`; return }
    const daf = (data.dapim || []).find(d => String(d.daf) === String(state.currentDaf))
    if (!daf?.comments?.length) { box.innerHTML = `${escapeHtml(title)} non disponible pour ce daf.`; return }

    box.innerHTML = `
      <h3>${escapeHtml(title)} — ${escapeHtml(data.masechet || '')} ${escapeHtml(state.currentDaf)}</h3>
      ${daf.comments.map(item => `
        <div class="rashiItem">
          <p class="he">${item.he || ''}</p>
          <p>${escapeHtml(state.currentLang === 'fr'
            ? cleanText(item.fr || item.en || 'Traduction française en préparation.')
            : cleanText(item.en || 'English translation unavailable.'))}</p>
        </div>
      `).join('')}
    `
  } catch (e) {
    box.innerHTML = `<div class="empty">Erreur : ${escapeHtml(e.message)}</div>`
  }
}

function refreshCurrentViewAfterLanguageChange() {
  if (state.currentMode === 'parasha' && state.currentParasha?.file) { loadParasha(state.currentParasha.file); return }
  if (state.currentMode === 'talmud' && state.currentData && state.currentDaf) { renderDaf(state.currentDaf); return }
  if (state.currentMode === 'shulchan') { renderShulchanCommentaryNotice(); return }
  if (state.currentMode === 'mishna') { refreshCurrentMishnaView() }
}

export function initTalmudEvents() {
  document.querySelector('#masechetSearch')?.addEventListener('input', renderLibrary)
  window.addEventListener('resize', () => { if (state.currentMode === 'talmud') renderSyncedCommentaries() })

  document.querySelector('#rashiBtn')?.addEventListener('click', () => {
    if (state.currentMode === 'parasha') { renderParashaRashi() }
    else if (state.currentMode === 'shulchan') { renderShulchanCommentaryNotice() }
    else { commentaryFilter = commentaryFilter === 'rachi' ? 'all' : 'rachi'; renderSyncedCommentaries() }
  })

  document.querySelector('#tosafotBtn')?.addEventListener('click', () => {
    if (state.currentMode === 'parasha') { document.querySelector('#commentBox').innerHTML = 'Tossefot n\'existe pas sur les parachiot.' }
    else if (state.currentMode === 'shulchan') { renderShulchanCommentaryNotice() }
    else { commentaryFilter = commentaryFilter === 'tossefot' ? 'all' : 'tossefot'; renderSyncedCommentaries() }
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
