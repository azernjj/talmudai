let mishnaIndex = []
let currentMishnaFile = ''

export function initMishnaEvents() {
  addMishnaSectionToSidebar()
  bindMishnaEvents()
}

function addMishnaSectionToSidebar() {
  const library =
    document.querySelector('#library') ||
    document.querySelector('.sidebar')

  if (!library || document.querySelector('#mishnaLibrarySection')) return

  const section = document.createElement('div')
  section.id = 'mishnaLibrarySection'
  section.className = 'seder mishnaLibrarySection'
  section.innerHTML = `
    <h3>📘 Michna</h3>
    <button id="openMishnaLibraryBtn" class="masechet" type="button">
      Ouvrir la Michna
    </button>
    <div id="mishnaTreatyList" class="mishnaTreatyList"></div>
  `

  library.appendChild(section)
}

function bindMishnaEvents() {
  document.querySelector('#openMishnaLibraryBtn')?.addEventListener('click', async () => {
    await loadMishnaIndex()
    renderMishnaTreatyList()
    renderMishnaHome()
  })
}

async function loadMishnaIndex() {
  if (mishnaIndex.length) return mishnaIndex

  const response = await fetch('/data/mishna/index.json', { cache: 'no-store' })

  if (!response.ok) {
    throw new Error(`Index Michna introuvable (${response.status})`)
  }

  const raw = await response.json()
  mishnaIndex = Array.isArray(raw)
    ? raw
    : (raw.masechtot || raw.items || [])

  return mishnaIndex
}

function renderMishnaTreatyList() {
  const box = document.querySelector('#mishnaTreatyList')
  if (!box) return

  box.innerHTML = mishnaIndex.map(item => `
    <button
      class="masechet mishnaTreatyBtn ${item.file === currentMishnaFile ? 'active' : ''}"
      type="button"
      data-file="${escapeHtml(item.file || '')}"
    >
      ${escapeHtml(item.name || item.title || item.file || '')}
    </button>
  `).join('')

  document.querySelectorAll('.mishnaTreatyBtn').forEach(button => {
    button.addEventListener('click', async () => {
      currentMishnaFile = button.dataset.file
      document.querySelectorAll('.mishnaTreatyBtn')
        .forEach(btn => btn.classList.toggle('active', btn === button))

      await loadMishnaFile(currentMishnaFile)
      document.querySelector('.sidebar')?.classList.remove('open')
    })
  })
}

function renderMishnaHome() {
  const title = document.querySelector('#dafTitle')
  const nav = document.querySelector('#dafNav')
  const segments = document.querySelector('#segments')
  const commentBox = document.querySelector('#commentBox')

  if (title) title.textContent = 'Étude de la Michna'
  if (nav) nav.innerHTML = ''
  if (commentBox) commentBox.innerHTML = 'Choisis un traité de Michna dans la colonne de gauche.'

  if (segments) {
    segments.innerHTML = `
      <div class="empty">
        <h2>📘 Michna</h2>
        <p>Choisis un traité dans la colonne de gauche.</p>
      </div>
    `
  }
}

async function loadMishnaFile(file) {
  const title = document.querySelector('#dafTitle')
  const nav = document.querySelector('#dafNav')
  const segments = document.querySelector('#segments')
  const commentBox = document.querySelector('#commentBox')

  if (title) title.textContent = 'Chargement de la Michna...'
  if (nav) nav.innerHTML = ''
  if (segments) segments.innerHTML = '<div class="empty">Chargement...</div>'
  if (commentBox) commentBox.innerHTML = 'Étude de la Michna.'

  try {
    const response = await fetch(`/data/mishna/${file}`, { cache: 'no-store' })
    if (!response.ok) {
      throw new Error(`Fichier introuvable (${response.status})`)
    }

    const data = await response.json()
    const titleText = data.title || data.name || file.replace('.json', '')
    const items = flattenMishnaSegments(data)

    if (title) title.textContent = titleText
    if (segments) {
      segments.innerHTML = items.length
        ? items.map(renderMishnaCard).join('')
        : '<div class="empty">Aucune Michna détectée dans ce fichier.</div>'
    }
  } catch (error) {
    if (title) title.textContent = 'Erreur Michna'
    if (segments) {
      segments.innerHTML = `
        <div class="empty">
          Erreur : ${escapeHtml(error.message)}<br>
          Vérifie que <b>public/data/mishna/${escapeHtml(file)}</b> existe.
        </div>
      `
    }
  }
}

function flattenMishnaSegments(node, output = []) {
  if (Array.isArray(node)) {
    node.forEach(value => flattenMishnaSegments(value, output))
    return output
  }

  if (!node || typeof node !== 'object') return output

  const he = node.he || node.hebrew || node.text_he

  if (typeof he === 'string' && he.trim()) {
    output.push({
      id: node.id ?? node.number ?? output.length + 1,
      ref: node.ref || node.reference || '',
      he,
      fr: node.fr || '',
      etude_fr: node.etude_fr || null
    })
    return output
  }

  Object.values(node).forEach(value => flattenMishnaSegments(value, output))
  return output
}

function renderMishnaCard(item, index) {
  const study = item.etude_fr || {}
  const title = item.ref || `Michna ${item.id || index + 1}`

  return `
    <article class="segment mishnaCard">
      <div class="segNum">${escapeHtml(title)}</div>

      <div class="he clickableHe">${item.he || ''}</div>

      <div class="translation">
        ${item.fr || study.traduction_fidele || 'Traduction française en préparation.'}
      </div>

      ${study.traduction_fluide ? renderSection('Traduction fluide', study.traduction_fluide) : ''}
      ${study.introduction ? renderSection('Introduction', study.introduction) : ''}
      ${study.contexte_general ? renderSection('Contexte général', study.contexte_general) : ''}
      ${renderLineByLine(study.explication_ligne_par_ligne)}
      ${renderWords(study.mots_difficiles)}
      ${renderMefarshim(study.mefarshim)}
      ${study.halakha_retenue ? renderSection('Halakha retenue', study.halakha_retenue) : ''}
      ${renderListSection('Conséquences pratiques', study.consequences_pratiques)}
      ${renderListSection('Résumé essentiel', study.resume_essentiel)}
      ${renderSources(study.sources_verifiables)}
      ${study.synthese_finale ? renderSection('Synthèse finale', study.synthese_finale) : ''}
    </article>
  `
}

function renderSection(title, content) {
  return `
    <section class="mishnaStudySection">
      <h4>${escapeHtml(title)}</h4>
      <p>${escapeHtml(content)}</p>
    </section>
  `
}

function renderListSection(title, items) {
  if (!Array.isArray(items) || !items.length) return ''

  return `
    <section class="mishnaStudySection">
      <h4>${escapeHtml(title)}</h4>
      <ul>
        ${items.map(item => `<li>${escapeHtml(item)}</li>`).join('')}
      </ul>
    </section>
  `
}

function renderLineByLine(lines) {
  if (!Array.isArray(lines) || !lines.length) return ''

  return `
    <details class="mishnaStudySection">
      <summary>Explication ligne par ligne</summary>
      ${lines.map(line => `
        <div class="mishnaStudyBlock">
          <div class="he">${line.texte_hebreu || ''}</div>
          <p><b>Traduction :</b> ${escapeHtml(line.traduction_fidele || '')}</p>
          <p><b>Explication :</b> ${escapeHtml(line.explication || '')}</p>
        </div>
      `).join('')}
    </details>
  `
}

function renderWords(words) {
  if (!Array.isArray(words) || !words.length) return ''

  return `
    <details class="mishnaStudySection">
      <summary>Mots difficiles</summary>
      ${words.map(word => `
        <div class="mishnaStudyBlock">
          <p>
            <b>${escapeHtml(word.mot || '')}</b>
            ${word.translitteration ? `(${escapeHtml(word.translitteration)})` : ''}
            — ${escapeHtml(word.traduction || '')}
          </p>
          <p>${escapeHtml(word.explication || '')}</p>
        </div>
      `).join('')}
    </details>
  `
}

function renderMefarshim(items) {
  if (!Array.isArray(items) || !items.length) return ''

  return `
    <details class="mishnaStudySection">
      <summary>Méfarchim classiques</summary>
      ${items.map(item => `
        <div class="mishnaStudyBlock">
          <p><b>${escapeHtml(item.auteur || '')}</b> — ${escapeHtml(item.source_precise || '')}</p>
          <p>${escapeHtml(item.opinion || '')}</p>
          <p><b>Logique :</b> ${escapeHtml(item.logique || '')}</p>
          ${item.desaccords ? `<p><b>Désaccords :</b> ${escapeHtml(item.desaccords)}</p>` : ''}
        </div>
      `).join('')}
    </details>
  `
}

function renderSources(sources) {
  if (!Array.isArray(sources) || !sources.length) return ''

  return `
    <details class="mishnaStudySection">
      <summary>Sources</summary>
      <ul>
        ${sources.map(source => `<li>${escapeHtml(source)}</li>`).join('')}
      </ul>
    </details>
  `
}

function escapeHtml(value) {
  return String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
}
