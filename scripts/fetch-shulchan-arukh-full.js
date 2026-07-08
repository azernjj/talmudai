import fs from 'fs/promises'
import path from 'path'

const OUT_DIR = 'public/data/shulchan-arukh'

const SECTIONS = [
  {
    slug: 'orach-chaim',
    title: "Orach Chayim",
    heTitle: 'אורח חיים',
    sefaria: 'Shulchan Arukh, Orach Chayim'
  },
  {
    slug: 'yore-dea',
    title: "Yoreh De'ah",
    heTitle: 'יורה דעה',
    sefaria: 'Shulchan Arukh, Yoreh Deah'
  },
  {
    slug: 'even-haezer',
    title: 'Even HaEzer',
    heTitle: 'אבן העזר',
    sefaria: 'Shulchan Arukh, Even HaEzer'
  },
  {
    slug: 'hoshen-mishpat',
    title: 'Hoshen Mishpat',
    heTitle: 'חושן משפט',
    sefaria: 'Shulchan Arukh, Choshen Mishpat'
  }
]

async function fetchJson(url) {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} : ${url}`)
  return await res.json()
}

function cleanText(x) {
  return String(x || '')
    .replace(/<[^>]+>/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

async function fetchSection(section) {
  console.log(`\n📘 Téléchargement : ${section.title}`)

  const ref = encodeURIComponent(section.sefaria)
  const url = `https://www.sefaria.org/api/texts/${ref}?context=0&commentary=0`

  const data = await fetchJson(url)

  const he = data.he || []
  const en = data.text || []

  const maxSimanim = Math.max(he.length, en.length)

  const simanim = []

  for (let i = 0; i < maxSimanim; i++) {
    const heSeifim = Array.isArray(he[i]) ? he[i] : []
    const enSeifim = Array.isArray(en[i]) ? en[i] : []

    const maxSeifim = Math.max(heSeifim.length, enSeifim.length)

    const seifim = []

    for (let j = 0; j < maxSeifim; j++) {
      seifim.push({
        seif: j + 1,
        he: cleanText(heSeifim[j]),
        en: cleanText(enSeifim[j]),
        fr: ''
      })
    }

    if (seifim.length) {
      simanim.push({
        siman: i + 1,
        title: `Siman ${i + 1}`,
        heTitle: `סימן ${i + 1}`,
        seifim
      })
    }

    if ((i + 1) % 50 === 0) {
      console.log(`  ✓ ${section.title} : ${i + 1}/${maxSimanim} simanim`)
    }
  }

  const output = {
    slug: section.slug,
    title: section.title,
    heTitle: section.heTitle,
    source: 'Sefaria',
    sefariaRef: section.sefaria,
    simanim
  }

  const filePath = path.join(OUT_DIR, `${section.slug}.json`)
  await fs.writeFile(filePath, JSON.stringify(output, null, 2), 'utf8')

  console.log(`✅ Fichier créé : ${filePath}`)
}

async function main() {
  await fs.mkdir(OUT_DIR, { recursive: true })

  for (const section of SECTIONS) {
    await fetchSection(section)
  }

  const index = SECTIONS.map(s => ({
    slug: s.slug,
    title: s.title,
    heTitle: s.heTitle,
    file: `${s.slug}.json`
  }))

  await fs.writeFile(
    path.join(OUT_DIR, 'index.json'),
    JSON.stringify(index, null, 2),
    'utf8'
  )

  console.log('\n✅ index.json mis à jour.')
  console.log('✅ Choul’han Aroukh complet généré.')
}

main().catch(err => {
  console.error('❌ Erreur :', err)
  process.exit(1)
})
