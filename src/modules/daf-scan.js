const scanDirectories = {
  berakhot: 'Berachos',
  shabbat: 'Shabbos',
  eruvin: 'Eruvin',
  pesachim: 'Pesachim',
  yoma: 'Yoma',
  sukkah: 'Sukah',
  beitzah: 'Beitzah',
  'rosh-hashanah': 'Rosh Hashanah',
  taanit: "Ta'anis",
  megillah: 'Megilah',
  'moed-katan': 'Moed Katan',
  chagigah: 'Chagigah',
  yevamot: 'Yevamos',
  ketubot: 'Kesuvos',
  nedarim: 'Nedarim',
  nazir: 'Nazir',
  sotah: 'Sotah',
  gittin: 'Gitin',
  kiddushin: 'Kidushin',
  'bava-kamma': 'Bava Kama',
  'bava-metzia': 'Bava Metzia',
  'bava-batra': 'Bava Basra',
  sanhedrin: 'Sanhedrin',
  makkot: 'Makos',
  shevuot: 'Shevuos',
  'avodah-zarah': 'Avodah Zarah',
  horayot: 'Horayos',
  zevachim: 'Zevachim',
  menachot: 'Menachos',
  chullin: 'Chulin',
  bekhorot: 'Bechoros',
  arakhin: 'Erchin',
  temurah: 'Temurah',
  keritot: 'Kerisus',
  meilah: "Me'ilah etc",
  kinnim: "Me'ilah etc",
  tamid: "Me'ilah etc",
  middot: "Me'ilah etc",
  niddah: 'Nidah'
}

// These tractates share a volume and a continuous folio numbering.
const sharedVolumeRanges = {
  meilah: [4, 44],
  kinnim: [45, 50],
  tamid: [51, 67],
  middot: [68, 75]
}

export function dafScanUrl(file, daf) {
  const tractate = file.replace(/\.json$/, '')
  const match = /^(\d+)(a|b)$/.exec(daf)
  if (!Object.hasOwn(scanDirectories, tractate) || !match) return null

  const page = Number(match[1])
  if (page < 2) return null

  const folio = page * 2 + Number(match[2] === 'b')
  const range = sharedVolumeRanges[tractate]
  if (range && (folio < range[0] || folio > range[1])) return null

  return `https://www.dafyomi.org/edafnew/${encodeURIComponent(scanDirectories[tractate])}/${page}${match[2]}.jpg`
}

export function renderDafScan(file, daf, title) {
  const panel = document.querySelector('#dafScan')
  if (!panel) return

  const url = dafScanUrl(file, daf)
  const key = JSON.stringify([file, daf])
  if (!panel.hidden && panel.dataset.dafKey === key) return

  panel.dataset.dafKey = key
  panel.hidden = false

  const reference = panel.querySelector('#dafScanReference')
  const status = panel.querySelector('#dafScanStatus')
  const link = panel.querySelector('#dafScanOpen')
  const preview = panel.querySelector('#dafScanPreview')
  reference.textContent = title
  status.hidden = false
  status.textContent = url
    ? 'Chargement de la page originale…'
    : 'Page originale indisponible pour ce daf.'
  link.hidden = true
  link.removeAttribute('href')
  preview.replaceChildren()
  if (!url) return

  const image = new Image()
  image.alt = `${title}, fac-similé de l’édition de Vilna`
  image.decoding = 'async'
  image.hidden = true
  image.addEventListener('load', () => {
    if (!preview.contains(image)) return
    image.hidden = false
    link.href = url
    link.hidden = false
    status.hidden = true
  }, { once: true })
  image.addEventListener('error', () => {
    if (!preview.contains(image)) return
    image.remove()
    status.textContent = 'Page originale indisponible pour ce daf.'
  }, { once: true })
  preview.append(image)
  image.src = url
}

export function hideDafScan() {
  const panel = document.querySelector('#dafScan')
  if (panel) panel.hidden = true
}
