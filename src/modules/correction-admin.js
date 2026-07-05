import { state } from '../state.js'

let correctionAdminUnlocked = sessionStorage.getItem('talmudCorrectionAdmin') === '1'
let currentCorrectionTarget = null

export function initCorrectionAdminEvents() {
  document.querySelector('#correctionAdminBtn')?.addEventListener('click', toggleCorrectionAdmin)
  document.querySelector('#closeCorrectionBtn')?.addEventListener('click', closeCorrectionPanel)
  document.querySelector('#cancelCorrectionBtn')?.addEventListener('click', closeCorrectionPanel)
  document.querySelector('#correctionOverlay')?.addEventListener('click', closeCorrectionPanel)
  document.querySelector('#saveCorrectionBtn')?.addEventListener('click', saveFrenchCorrection)

  window.installCorrectionButtons = installCorrectionButtons
}

function toggleCorrectionAdmin() {
  if (correctionAdminUnlocked) {
    correctionAdminUnlocked = false
    sessionStorage.removeItem('talmudCorrectionAdmin')
    sessionStorage.removeItem('talmudCorrectionPassword')
    location.reload()
    return
  }

  const password = prompt('Code admin correction :')
  if (!password) return

  sessionStorage.setItem('talmudCorrectionPassword', password)
  correctionAdminUnlocked = true
  sessionStorage.setItem('talmudCorrectionAdmin', '1')
  location.reload()
}

export function correctionButtonHtml(type, index) {
  if (!correctionAdminUnlocked || state.currentLang !== 'fr') return ''

  return `
    <button class="editFrBtn" data-type="${type}" data-index="${index}">
      ✏️ Corriger
    </button>
  `
}

export function installCorrectionButtons() {
  document.querySelectorAll('.editFrBtn').forEach(btn => {
    btn.addEventListener('click', () => {
      openCorrectionPanel(btn.dataset.type, Number(btn.dataset.index))
    })
  })
}

function openCorrectionPanel(type, index) {
  const data = state.currentData?.dapim?.[state.currentDaf]
  if (!data) return

  const arr = data[type] || []
  const item = arr[index]
  if (!item) return

  currentCorrectionTarget = {
    file: localStorage.getItem('currentFile') || 'berakhot.json',
    daf: state.currentDaf,
    type,
    index,
    id: item.id || index + 1
  }

  document.querySelector('#correctionMeta').textContent =
    `${state.currentData?.title || ''} ${state.currentDaf} — ${type} ${index + 1}`

  document.querySelector('#correctionText').value = item.fr || ''
  document.querySelector('#correctionStatus').textContent = 'Modifie le français puis clique sur Corriger.'

  document.querySelector('#correctionPanel').classList.remove('hidden')
  document.querySelector('#correctionOverlay').classList.remove('hidden')
}

function closeCorrectionPanel() {
  document.querySelector('#correctionPanel').classList.add('hidden')
  document.querySelector('#correctionOverlay').classList.add('hidden')
  currentCorrectionTarget = null
}

async function saveFrenchCorrection() {
  if (!currentCorrectionTarget) return

  const password = sessionStorage.getItem('talmudCorrectionPassword') || ''
  const value = document.querySelector('#correctionText').value.trim()
  const status = document.querySelector('#correctionStatus')

  if (!password) {
    status.textContent = 'Code admin manquant. Clique à nouveau sur ⚙.'
    return
  }

  if (!value) {
    status.textContent = 'La correction française est vide.'
    return
  }

  status.textContent = 'Enregistrement dans GitHub en cours...'

  try {
    const res = await fetch('/api/correction-fr', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        password,
        ...currentCorrectionTarget,
        value
      })
    })

    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data.error || `Erreur HTTP ${res.status}`)

    const arr = state.currentData.dapim[currentCorrectionTarget.daf][currentCorrectionTarget.type]
    arr[currentCorrectionTarget.index].fr = value

    status.textContent = '✅ Correction enregistrée dans GitHub. Vercel va redéployer automatiquement.'
    setTimeout(closeCorrectionPanel, 1000)
  } catch (e) {
    status.textContent = '❌ Erreur : ' + e.message
  }
}
