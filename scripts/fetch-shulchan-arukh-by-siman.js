import fs from 'fs/promises'
import path from 'path'

const OUT_DIR = 'public/data/shulchan-arukh'

const SECTIONS = [
  {
    slug: 'orach-chaim',
    title: 'Orach Chayim',
    heTitle: 'אורח חיים',
    ref: 'Shulchan Arukh, Orach Chayim',
    total: 697
  },
  {
    slug: 'yore-dea',
    title: "Yoreh De'ah",
    heTitle: 'יורה דעה',
    ref: "Shulchan Arukh, Yoreh De'ah",
    total: 403
  },
  {
    slug: 'even-haezer',
    title: 'Even HaEzer',
    heTitle: 'אבן העזר',
    ref: 'Shulchan Arukh, Even HaEzer',
    total: 178
  },
  {
    slug: 'hoshen-mishpat',
    title: 'Choshen Mishpat',
    heTitle: 'חושן משפט',
    ref: 'Shulchan Arukh, Choshen Mishpat',
    total: 427
  }
]

function cleanText(x = '') {
  return String(x)
    .replace(/<[^>]+>/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

async function fetchJson(url) {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return await res.json()
}

async function fetchSiman(section, simanNumber) {
  const ref = `${section.ref} ${simanNumber}`
  const url = `https://www.sefaria.org/api/texts/${encodeURIComponent(ref)}?context=0&commentary=0`

  const data = await fetchJson(url)

  const he = Array.isArray(data.he) ? data.he : []
  const en = Array.isArray(data.text) ? data.text : []

  const max = Math.max(he.length, en.length)

  const seifim = []

  for (let i = 0; i < max; i++) {
    const heText = cleanText(he[i])
    const enText = cleanText(en[i])

    if (!heText && !enText) continue

    seifim.push({
      seif: i + 1,
      he: heText,
      en: enText,
      fr: ''
    })
  }

  return {
    siman: simanNumber,
    title: `Siman ${simanNumber}`,
    heTitle: `סימן ${simanNumber}`,
    seifim
  }
}

async function fetchSection(section) {
  console.log(`\n📘 ${section.title}`)

  const simanim = []

  for (let i = 1; i <= section.total; i++) {
    try {
      const siman = await fetchSiman(section, i)

      if (siman.seifim.length) {
        simanim.push(siman)
      }

      if (i % 25 === 0) {
        console.log(`  ✓ ${i}/${section.total}`)
      }

      await new Promise(resolve => setTimeout(resolve, 80))
    } catch (e) {
      console.log(`  ⚠️ Siman ${i} ignoré : ${e.message}`)
    }
  }

  const output = {
    slug: section.slug,
    title: section.title,
    heTitle: section.heTitle,
    source: 'Sefaria',
    sefariaRef: section.ref,
    simanim
  }

  const file = path.join(OUT_DIR, `${section.slug}.json`)
  await fs.writeFile(file, JSON.stringify(output, null, 2), 'utf8')

  console.log(`✅ ${file} — ${simanim.length} simanim`)
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

  console.log('\n✅ Choul’han Aroukh complet généré.')
}

main().catch(err => {
  console.error('❌ Erreur :', err)
  process.exit(1)
})
