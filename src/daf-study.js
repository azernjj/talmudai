import './daf-study.css'

export function initDafStudy(result) {
  const main = document.querySelector('.dafHayomiMain')
  const controls = document.createElement('div')
  controls.className = 'dafStudyActions'
  controls.innerHTML = `<button type="button" id="openDafStudy" aria-expanded="false" aria-controls="dafStudy">Lire le daf en écoutant</button>`
  result.append(controls)

  const section = document.createElement('section')
  section.id = 'dafStudy'
  section.className = 'dafHayomiCard'
  section.hidden = true
  section.setAttribute('aria-label', 'Lecture du daf pendant le cours')
  section.innerHTML = `
    <form class="dafStudyNav">
      <label for="studyAmud">Page du Talmud</label>
      <input id="studyAmud" type="text" placeholder="Ex. 2a ou 2b" pattern="[1-9][0-9]*[aAbB]" required autocomplete="off" aria-describedby="studyPageHint">
      <button type="submit">Afficher</button>
      <button type="button" id="closeDafStudy">Fermer la page</button>
    </form>
    <p id="studyPageHint">Indiquez le numéro et le côté a ou b. Le cours continue pendant la lecture.</p>
    <div id="studyContent"></div>`
  result.after(section)

  const toggle = controls.querySelector('button')
  const form = section.querySelector('form')
  const input = section.querySelector('input')
  const content = section.querySelector('#studyContent')
  let currentFile
  let reader

  function showPage() {
    const amud = input.value.trim().toLowerCase()
    if (!/^[1-9]\d*[ab]$/.test(amud) || !currentFile) return
    input.value = amud
    const path = `/daf/${currentFile.replace(/\.json$/, '')}/${amud}`
    if (!reader) {
      reader = document.createElement('iframe')
      reader.title = 'Texte, traduction, commentaires et daf original'
      reader.addEventListener('load', () => {
        // Keep the existing study page and its normal daf navigation inside the reader.
        const doc = reader.contentDocument
        if (!doc || doc.querySelector('#courseReaderStyle')) return
        const style = doc.createElement('style')
        style.id = 'courseReaderStyle'
        style.textContent = `
          .topbar, .sidebar { display: none !important; }
          .layout { display: block !important; height: auto !important; }
          .reader, .comments { width: 100% !important; overflow: visible !important; }
          body { margin: 0; }
        `
        doc.head.append(style)
      })
      content.append(reader)
    }
    if (reader.getAttribute('src') !== path) reader.src = path
  }

  function close() {
    section.hidden = true
    main.classList.remove('studyActive')
    toggle.setAttribute('aria-expanded', 'false')
  }

  toggle.addEventListener('click', () => {
    section.hidden = false
    main.classList.add('studyActive')
    toggle.setAttribute('aria-expanded', 'true')
    if (input.value) showPage()
    else input.focus()
    section.scrollIntoView({ block: 'start' })
  })
  section.querySelector('#closeDafStudy').addEventListener('click', () => {
    close()
    toggle.focus({ preventScroll: true })
  })
  form.addEventListener('submit', event => {
    event.preventDefault()
    showPage()
  })

  return {
    setCourse(file, name) {
      close()
      currentFile = file
      const match = name.match(/\b(0*[1-9]\d*)\s*([ab])?\b/i)
      input.value = match ? `${Number(match[1])}${match[2]?.toLowerCase() || 'a'}` : ''
      content.replaceChildren()
      reader = null
    },
    reset() {
      close()
      content.replaceChildren()
      reader = null
      currentFile = null
      input.value = ''
    }
  }
}
