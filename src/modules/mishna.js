import { state } from '../state.js'
import { escapeHtml } from './utils.js'

let mishnaIndex = []
let currentMishnaFile = ''
let currentMishnaData = null

export function initMishnaEvents() {
  renderMishnaLibrary()

  document
    .querySelector('#mishnaSearch')
    ?.addEventListener('input', renderMishnaLibrary)
}

export async function renderMishnaLibrary() {
  const library = document.querySelector('#mishnaLibrary')
  if (!library) return

  try {
    if (!mishnaIndex.length) {
      const res = await fetch('/data/mishna/index.json', {
        cache: 'no-store'
      })

      if (!res.ok) {
        throw new Error(`Index Michna introuvable (${res.status})`)
      }

      const raw = await res.json()

      mishnaIndex = Array.isArray(raw)
        ? raw
        : (raw.masechtot || raw.items || [])
    }

    const q = (
      document.querySelector('#mishnaSearch')?.value || ''
    )
      .trim()
      .toLowerCase()

    const filtered = mishnaIndex.filter(item => {
      const name = String(
        item.name || item.title || ''
      ).toLowerCase()

      const file = String(
        item.file || ''
      ).toLowerCase()

      return name.includes(q) || file.includes(q)
    })

    library.innerHTML = filtered.length
      ? filtered.map(item => {
          const file = String(item.file || '')
          const label = String(
            item.name || item.title || file
          )

          return `
            <button
              class="masechet mishnaMasechet ${
                file === currentMishnaFile ? 'active' : ''
              }"
              data-file="${escapeHtml(file)}"
              type="button"
            >
              ${escapeHtml(label)}
            </button>
          `
        }).join('')
      : `
        <div class="empty">
          Aucun traité de Michna trouvé.
        </div>
      `

    document
      .querySelectorAll('#mishnaLibrary .mishnaMasechet')
      .forEach(btn => {
        btn.addEventListener('click', () => {
          loadMishna(btn.dataset.file)
          document
            .querySelector('.sidebar')
            ?.classList.remove('open')
        })
      })
  } catch (error) {
    library.innerHTML = `
      <div class="empty">
        Erreur Michna : ${escapeHtml(error.message)}
      </div>
    `
  }
}

export async function loadMishna(file) {
  state.currentMode = 'mishna'
  currentMishnaFile = file

  localStorage.setItem('currentMishnaFile', file)

  const title = document.querySelector('#dafTitle')
  const nav = document.querySelector('#dafNav')
  const segments = document.querySelector('#segments')
  const commentBox = document.querySelector('#commentBox')

  if (title) {
    title.textContent = 'Chargement de la Michna...'
  }

  if (nav) {
    nav.innerHTML = ''
  }

  if (segments) {
    segments.innerHTML = `
      <div class="empty">
        Chargement...
      </div>
    `
  }

  if (commentBox) {
    commentBox.innerHTML =
      'Étude et commentaires de la Michna.'
  }

  renderMishnaLibrary()

  try {
    const res = await fetch(
      `/data/mishna/${encodeURIComponent(file)}`,
      {
        cache: 'no-store'
      }
    )

    if (!res.ok) {
      throw new Error(
        `Fichier introuvable : /data/mishna/${file} (${res.status})`
      )
    }

    currentMishnaData = await res.json()
    renderCurrentMishna()
  } catch (error) {
    currentMishnaData = null

    if (title) {
      title.textContent = 'Erreur Michna'
    }

    if (segments) {
      segments.innerHTML = `
        <div class="empty">
          ${escapeHtml(error.message)}
        </div>
      `
    }
  }
}

export function refreshCurrentMishnaView() {
  if (
    state.currentMode !== 'mishna' ||
    !currentMishnaData
  ) {
    return
  }

  renderCurrentMishna()
}

function renderCurrentMishna() {
  const title = document.querySelector('#dafTitle')
  const nav = document.querySelector('#dafNav')
  const segments = document.querySelector('#segments')

  if (!currentMishnaData || !segments) return

  const items = flattenMishnaSegments(
    currentMishnaData
  )

  const titleText =
    currentMishnaData.title ||
    currentMishnaData.name ||
    currentMishnaFile.replace(/\.json$/i, '')

  if (title) {
    title.textContent = titleText
  }

  if (nav) {
    nav.innerHTML = ''
  }

  segments.innerHTML = items.length
    ? items.map(renderMishnaCard).join('')
    : `
      <div class="empty">
        Aucune Michna détectée dans ce fichier.
      </div>
    `
}

function flattenMishnaSegments(
  node,
  output = []
) {
  if (Array.isArray(node)) {
    node.forEach(value => {
      flattenMishnaSegments(value, output)
    })

    return output
  }

  if (!node || typeof node !== 'object') {
    return output
  }

  const he =
    node.he ||
    node.hebrew ||
    node.text_he ||
    node.he_text

  if (
    typeof he === 'string' &&
    he.trim()
  ) {
    output.push({
      id:
        node.id ??
        node.number ??
        output.length + 1,

      ref:
        node.ref ||
        node.reference ||
        '',

      he,
      fr: node.fr || '',
      en: node.en || '',
      etude_fr: node.etude_fr || null
    })

    return output
  }

  Object.values(node).forEach(value => {
    flattenMishnaSegments(value, output)
  })

  return output
}

function renderMishnaCard(item, index) {
  const study = item.etude_fr || {}

  const title =
    item.ref ||
    `Michna ${item.id || index + 1}`

  const frenchTranslation =
    item.fr ||
    study.traduction_fr ||
    study.traduction_fidele ||
    'Traduction française en préparation.'

  const translation =
    state.currentLang === 'fr'
      ? frenchTranslation
      : (
          item.en ||
          'English translation in preparation.'
        )

  return `
    <article class="segment mishnaCard">
      <div class="segNum">
        ${escapeHtml(title)}
      </div>

      <div class="he clickableHe">
        ${item.he || ''}
      </div>

      <div class="translation">
        ${escapeHtml(translation)}
      </div>

      ${
        state.currentLang === 'fr'
          ? renderFrenchStudy(study)
          : ''
      }
    </article>
  `
}

function renderFrenchStudy(study) {
  return `
    ${
      study.introduction
        ? section(
            'Introduction',
            study.introduction
          )
        : ''
    }

    ${
      study.contexte_general
        ? section(
            'Contexte général',
            study.contexte_general
          )
        : ''
    }

    ${renderLineByLine(
      study.explication_ligne_par_ligne
    )}

    ${renderWords(
      study.mots_difficiles
    )}

    ${renderListSection(
      'Notions nouvelles',
      study.notions_nouvelles
    )}

    ${renderMefarshim(
      study.mefarshim
    )}

    ${
      study.halakha_retenue
        ? section(
            'Halakha retenue',
            study.halakha_retenue
          )
        : ''
    }

    ${renderListSection(
      'Conséquences pratiques',
      study.consequences_pratiques
    )}

    ${renderLinks(
      study.liens_sources
    )}

    ${renderListSection(
      'Exemples concrets',
      study.exemples_concrets
    )}

    ${renderListSection(
      'Résumé essentiel',
      study.resume_essentiel
    )}

    ${renderQuestions(
      study.questions_revision
    )}

    ${renderSources(
      study.sources_verifiables
    )}

    ${renderListSection(
      'Incertitudes',
      study.incertitudes
    )}

    ${
      study.synthese_finale
        ? section(
            'Synthèse finale',
            study.synthese_finale
          )
        : ''
    }
  `
}

function section(title, content) {
  return `
    <section class="mishnaStudySection">
      <h4>${escapeHtml(title)}</h4>

      <p>
        ${escapeHtml(content)}
      </p>
    </section>
  `
}

function renderListSection(title, items) {
  if (
    !Array.isArray(items) ||
    !items.length
  ) {
    return ''
  }

  return `
    <section class="mishnaStudySection">
      <h4>${escapeHtml(title)}</h4>

      <ul>
        ${items.map(item => `
          <li>
            ${escapeHtml(item)}
          </li>
        `).join('')}
      </ul>
    </section>
  `
}

function renderLineByLine(lines) {
  if (
    !Array.isArray(lines) ||
    !lines.length
  ) {
    return ''
  }

  return `
    <details
      class="mishnaStudySection"
      open
    >
      <summary>
        Explication ligne par ligne
      </summary>

      ${lines.map(line => `
        <div class="mishnaStudyBlock">
          <div class="he">
            ${line.texte_hebreu || ''}
          </div>

          ${renderWordByWord(
            line.mot_a_mot
          )}

          ${
            line.traduction_litterale
              ? `
                <div class="literalTranslation">
                  <b>
                    Traduction littérale :
                  </b>

                  ${escapeHtml(
                    line.traduction_litterale
                  )}
                </div>
              `
              : ''
          }

          ${
            line.explication
              ? `
                <div class="lineExplanation">
                  <b>Explication :</b>

                  ${escapeHtml(
                    line.explication
                  )}
                </div>
              `
              : ''
          }
        </div>
      `).join('')}
    </details>
  `
}

function renderWordByWord(words) {
  if (
    !Array.isArray(words) ||
    !words.length
  ) {
    return ''
  }

  return `
    <div class="wordByWord">
      <h4>Mot à mot</h4>

      <div class="wordByWordHeader">
        <span>Hébreu</span>
        <span>Translittération</span>
        <span>Sens</span>
        <span>Fonction</span>
      </div>

      ${words.map(word => `
        <div class="wordByWordItem">
          <span class="hebrewWord">
            ${word.hebreu || ''}
          </span>

          <span class="transliteration">
            ${escapeHtml(
              word.translitteration || ''
            )}
          </span>

          <span class="wordMeaning">
            ${escapeHtml(
              word.sens_francais || ''
            )}
          </span>

          <span class="wordFunction">
            ${escapeHtml(
              word.fonction_dans_la_phrase || ''
            )}
          </span>
        </div>
      `).join('')}
    </div>
  `
}

function renderWords(words) {
  if (
    !Array.isArray(words) ||
    !words.length
  ) {
    return ''
  }

  return `
    <details class="mishnaStudySection">
      <summary>
        Mots difficiles
      </summary>

      ${words.map(word => `
        <div class="mishnaStudyBlock">
          <p>
            <b>
              ${escapeHtml(word.mot || '')}
            </b>

            ${
              word.translitteration
                ? `
                  (${escapeHtml(
                    word.translitteration
                  )})
                `
                : ''
            }

            —

            ${escapeHtml(
              word.traduction || ''
            )}
          </p>

          <p>
            ${escapeHtml(
              word.explication || ''
            )}
          </p>
        </div>
      `).join('')}
    </details>
  `
}

function renderMefarshim(items) {
  if (
    !Array.isArray(items) ||
    !items.length
  ) {
    return ''
  }

  return `
    <details class="mishnaStudySection">
      <summary>
        Méfarchim classiques
      </summary>

      ${items.map(item => `
        <div class="mishnaStudyBlock">
          <p>
            <b>
              ${escapeHtml(
                item.auteur || ''
              )}
            </b>

            —

            ${escapeHtml(
              item.source_precise || ''
            )}
          </p>

          <p>
            ${escapeHtml(
              item.opinion || ''
            )}
          </p>

          <p>
            <b>Logique :</b>

            ${escapeHtml(
              item.logique || ''
            )}
          </p>

          ${
            item.desaccords
              ? `
                <p>
                  <b>Désaccords :</b>

                  ${escapeHtml(
                    item.desaccords
                  )}
                </p>
              `
              : ''
          }
        </div>
      `).join('')}
    </details>
  `
}

function renderLinks(items) {
  if (
    !Array.isArray(items) ||
    !items.length
  ) {
    return ''
  }

  return `
    <details class="mishnaStudySection">
      <summary>
        Liens avec d’autres sources
      </summary>

      ${items.map(item => `
        <div class="mishnaStudyBlock">
          <p>
            <b>
              ${escapeHtml(
                item.reference || ''
              )}
            </b>

            ${
              item.type_source
                ? `
                  — ${escapeHtml(
                    item.type_source
                  )}
                `
                : ''
            }
          </p>

          <p>
            ${escapeHtml(
              item.explication_du_lien || ''
            )}
          </p>
        </div>
      `).join('')}
    </details>
  `
}

function renderQuestions(items) {
  if (
    !Array.isArray(items) ||
    !items.length
  ) {
    return ''
  }

  return `
    <details class="mishnaStudySection">
      <summary>
        Questions de révision
      </summary>

      ${items.map(item => `
        <div class="mishnaStudyBlock">
          <p>
            <b>Question :</b>

            ${escapeHtml(
              item.question || ''
            )}
          </p>

          <p>
            <b>Réponse :</b>

            ${escapeHtml(
              item.reponse_attendue || ''
            )}
          </p>
        </div>
      `).join('')}
    </details>
  `
}

function renderSources(sources) {
  if (
    !Array.isArray(sources) ||
    !sources.length
  ) {
    return ''
  }

  return `
    <details class="mishnaStudySection">
      <summary>
        Sources
      </summary>

      <ul>
        ${sources.map(source => `
          <li>
            ${escapeHtml(source)}
          </li>
        `).join('')}
      </ul>
    </details>
  `
}
