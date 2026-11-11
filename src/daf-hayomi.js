import './style.css'
import './daf-hayomi.css'
import { sedarim } from './state.js'

// Public anon key used by the Android app for the shared catalogue.
const supabaseUrl = 'https://hhidfgtxvmpfbxajadpd.supabase.co'
const supabaseAnonKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhoaWRmZ3R4dm1wZmJ4YWphZHBkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTMzNjMzMjQsImV4cCI6MjA2ODkzOTMyNH0.l4zDNQlj3xQgwG9piODu0YlvmXcQ_PXxgn-ay6lkPhc'

const sederSelect = document.querySelector('#videoSeder')
const masechetSelect = document.querySelector('#videoMasechet')
const dafSelect = document.querySelector('#videoDaf')
const status = document.querySelector('#videoStatus')
const retry = document.querySelector('#retryVideos')
const result = document.querySelector('#videoResult')
const title = document.querySelector('#videoTitle')
const player = document.querySelector('#videoPlayer')
const youtubeLink = document.querySelector('#videoYouTube')

const aliases = {
  'shabbat.json': ['Chabbat'],
  'sukkah.json': ['Sukka'],
  'rosh-hashanah.json': ['Rosh Hashana'],
  'megillah.json': ['Megilla'],
  'chagigah.json': ['Hagiga'],
  'sanhedrin.json': ['Sanhedrine', 'Sanhedine'],
  'makkot.json': ['Maccot'],
  'chullin.json': ['Hullin']
}

function normalizeTitle(value) {
  return value.normalize('NFD').replace(/\p{Diacritic}/gu, '')
    .toLowerCase().replace(/[^a-z0-9 ]/g, '').replace(/\s+/g, ' ').trim()
}

const masechetNames = sedarim.flatMap(({ masechtot }) =>
  masechtot.flatMap(({ name, file }) =>
    [name, file.replace(/\.json$/, '').replaceAll('-', ' '), ...(aliases[file] || [])]
      .map(alias => ({ file, alias: normalizeTitle(alias) }))
  )
).sort((a, b) => b.alias.length - a.alias.length)

const titleOrder = new Intl.Collator('fr', { numeric: true, sensitivity: 'base' })
let catalogue = new Map()

function youtubeVideo(link) {
  let url
  try {
    url = new URL(link)
  } catch {
    return null
  }
  if (url.protocol !== 'https:') return null

  const youtubeHosts = ['www.youtube.com', 'youtube.com', 'm.youtube.com']
  const id = url.hostname === 'youtu.be'
    ? url.pathname.slice(1)
    : youtubeHosts.includes(url.hostname)
      ? url.pathname === '/watch'
        ? url.searchParams.get('v')
        : url.pathname.match(/^\/(?:embed|shorts|live)\/([^/]+)\/?$/)?.[1]
      : null
  if (!id || !/^[\w-]{11}$/.test(id)) return null

  const time = url.searchParams.get('t') || url.searchParams.get('start') || ''
  const seconds = /^\d+s?$/.test(time) ? Number.parseInt(time, 10) : 0
  const watch = new URL('https://www.youtube.com/watch')
  watch.searchParams.set('v', id)
  const embed = new URL(`/embed/${id}`, watch.origin)
  if (seconds) {
    watch.searchParams.set('t', `${seconds}s`)
    embed.searchParams.set('start', seconds)
  }
  return { watch: watch.href, embed: embed.href }
}

function firstAmud(name) {
  const daf = name.match(/\b(\d+)([ab])\b/i)
  return daf ? Number(daf[1]) * 2 + Number(daf[2].toLowerCase() === 'b') : Infinity
}

function groupVideos(rows) {
  const groups = new Map()
  const seen = new Set()
  for (const { nom, lien } of rows) {
    if (typeof nom !== 'string' || typeof lien !== 'string') continue

    const name = nom.trim()
    const video = youtubeVideo(lien)
    if (!video) continue

    const normalizedName = normalizeTitle(name).replace(/^(?:siyoum|syoum) /, '')
    const masechet = masechetNames.find(({ alias }) =>
      normalizedName === alias || normalizedName.startsWith(`${alias} `)
    )
    const key = JSON.stringify([name, video.watch])
    if (!masechet || seen.has(key)) continue

    seen.add(key)
    const videos = groups.get(masechet.file) || []
    videos.push({ name, ...video })
    groups.set(masechet.file, videos)
  }

  for (const videos of groups.values()) {
    videos.sort((a, b) =>
      (firstAmud(a.name) - firstAmud(b.name)) || titleOrder.compare(a.name, b.name)
    )
  }
  return groups
}

async function fetchVideos() {
  const pageSize = 1000
  const rows = []
  const url = new URL('/rest/v1/Talmud', supabaseUrl)
  url.searchParams.set('select', 'nom,lien')
  url.searchParams.set('order', 'nom.asc,lien.asc')
  url.searchParams.set('limit', pageSize)

  for (let offset = 0; ; offset += pageSize) {
    url.searchParams.set('offset', offset)
    const response = await fetch(url, {
      headers: { apikey: supabaseAnonKey },
      signal: globalThis.AbortSignal?.timeout?.(20000)
    })
    if (!response.ok) throw new Error(`Catalogue vidéo (${response.status})`)
    const page = await response.json()
    if (!Array.isArray(page)) throw new Error('Catalogue vidéo invalide')
    rows.push(...page)
    if (page.length < pageSize) return rows
  }
}

function setOptions(select, options, placeholder) {
  select.replaceChildren(new Option(placeholder, ''), ...options)
  select.disabled = options.length === 0
}

function hideVideo() {
  result.hidden = true
  player.replaceChildren()
  youtubeLink.removeAttribute('href')
}

function updateDapim() {
  hideVideo()
  const videos = catalogue.get(masechetSelect.value) || []
  setOptions(dafSelect, videos.map(({ name }, index) => new Option(name, index)), 'Choisir un daf')
  status.textContent = videos.length
    ? ''
    : masechetSelect.value
      ? 'Aucun cours disponible pour ce traité.'
      : 'Choisissez un traité.'
}

function updateMasechtot() {
  const seder = sedarim.find(({ name }) => name === sederSelect.value)
  const masechtot = seder?.masechtot || []
  setOptions(masechetSelect, masechtot.map(({ name, file }) => new Option(name, file)), 'Choisir un traité')
  updateDapim()
  if (!seder) status.textContent = 'Choisissez un seder.'
  else if (!masechtot.some(({ file }) => catalogue.has(file))) {
    status.textContent = 'Aucun cours disponible pour ce seder.'
  }
}

function showVideo() {
  hideVideo()
  const video = catalogue.get(masechetSelect.value)?.[dafSelect.value]
  if (!video) return

  const iframe = document.createElement('iframe')
  iframe.title = video.name
  iframe.src = video.embed
  iframe.allow = 'accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture'
  iframe.allowFullscreen = true
  iframe.referrerPolicy = 'strict-origin-when-cross-origin'

  title.textContent = video.name
  youtubeLink.href = video.watch
  player.append(iframe)
  result.hidden = false
}

async function loadCatalogue() {
  retry.hidden = true
  status.textContent = 'Chargement des cours…'
  try {
    catalogue = groupVideos(await fetchVideos())
    setOptions(sederSelect, sedarim.map(({ name }) => new Option(name, name)), 'Choisir un seder')
    updateMasechtot()
    if (!catalogue.size) status.textContent = 'Aucun cours disponible pour le moment.'
  } catch {
    status.textContent = 'Le catalogue des cours est indisponible pour le moment.'
    retry.hidden = false
  }
}

sederSelect.addEventListener('change', updateMasechtot)
masechetSelect.addEventListener('change', updateDapim)
dafSelect.addEventListener('change', showVideo)
retry.addEventListener('click', loadCatalogue)
loadCatalogue()
