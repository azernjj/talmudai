import fs from "fs";
import path from "path";

const outDir = "public/data/parashiot";
fs.mkdirSync(outDir, { recursive: true });

const parashiot = [
  { slug: "bereshit", name: "Bereshit", range: "Genesis 1:1-6:8" },
  { slug: "noach", name: "Noa'h", range: "Genesis 6:9-11:32" },
  { slug: "lekh-lekha", name: "Lekh Lekha", range: "Genesis 12:1-17:27" },
  { slug: "vayera", name: "Vayera", range: "Genesis 18:1-22:24" },
  { slug: "chayei-sarah", name: "Chayei Sarah", range: "Genesis 23:1-25:18" },
  { slug: "toledot", name: "Toledot", range: "Genesis 25:19-28:9" },
  { slug: "vayetze", name: "Vayetze", range: "Genesis 28:10-32:3" },
  { slug: "vayishlach", name: "Vayishlach", range: "Genesis 32:4-36:43" },
  { slug: "vayeshev", name: "Vayeshev", range: "Genesis 37:1-40:23" },
  { slug: "miketz", name: "Miketz", range: "Genesis 41:1-44:17" },
  { slug: "vayigash", name: "Vayigash", range: "Genesis 44:18-47:27" },
  { slug: "vayechi", name: "Vayechi", range: "Genesis 47:28-50:26" },

  { slug: "shemot", name: "Shemot", range: "Exodus 1:1-6:1" },
  { slug: "vaera", name: "Vaera", range: "Exodus 6:2-9:35" },
  { slug: "bo", name: "Bo", range: "Exodus 10:1-13:16" },
  { slug: "beshalach", name: "Beshalach", range: "Exodus 13:17-17:16" },
  { slug: "yitro", name: "Yitro", range: "Exodus 18:1-20:23" },
  { slug: "mishpatim", name: "Mishpatim", range: "Exodus 21:1-24:18" },
  { slug: "terumah", name: "Terouma", range: "Exodus 25:1-27:19" },
  { slug: "tetzaveh", name: "Tetsaveh", range: "Exodus 27:20-30:10" },
  { slug: "ki-tisa", name: "Ki Tisa", range: "Exodus 30:11-34:35" },
  { slug: "vayakhel", name: "Vayakhel", range: "Exodus 35:1-38:20" },
  { slug: "pekudei", name: "Pekoudei", range: "Exodus 38:21-40:38" },

  { slug: "vayikra", name: "Vayikra", range: "Leviticus 1:1-5:26" },
  { slug: "tzav", name: "Tsav", range: "Leviticus 6:1-8:36" },
  { slug: "shemini", name: "Shemini", range: "Leviticus 9:1-11:47" },
  { slug: "tazria", name: "Tazria", range: "Leviticus 12:1-13:59" },
  { slug: "metzora", name: "Metsora", range: "Leviticus 14:1-15:33" },
  { slug: "acharei-mot", name: "A'harei Mot", range: "Leviticus 16:1-18:30" },
  { slug: "kedoshim", name: "Kedoshim", range: "Leviticus 19:1-20:27" },
  { slug: "emor", name: "Emor", range: "Leviticus 21:1-24:23" },
  { slug: "behar", name: "Behar", range: "Leviticus 25:1-26:2" },
  { slug: "bechukotai", name: "Be'houkotaï", range: "Leviticus 26:3-27:34" },

  { slug: "bamidbar", name: "Bamidbar", range: "Numbers 1:1-4:20" },
  { slug: "nasso", name: "Nasso", range: "Numbers 4:21-7:89" },
  { slug: "behaalotekha", name: "Beha'alotekha", range: "Numbers 8:1-12:16" },
  { slug: "shelach", name: "Shelach Lekha", range: "Numbers 13:1-15:41" },
  { slug: "korach", name: "Kora'h", range: "Numbers 16:1-18:32" },
  { slug: "chukat", name: "Houkat", range: "Numbers 19:1-22:1" },
  { slug: "balak", name: "Balak", range: "Numbers 22:2-25:9" },
  { slug: "pinchas", name: "Pin'has", range: "Numbers 25:10-30:1" },
  { slug: "matot", name: "Matot", range: "Numbers 30:2-32:42" },
  { slug: "masei", name: "Massei", range: "Numbers 33:1-36:13" },

  { slug: "devarim", name: "Devarim", range: "Deuteronomy 1:1-3:22" },
  { slug: "vaetchanan", name: "Vaet'hanan", range: "Deuteronomy 3:23-7:11" },
  { slug: "ekev", name: "Ekev", range: "Deuteronomy 7:12-11:25" },
  { slug: "reeh", name: "Reeh", range: "Deuteronomy 11:26-16:17" },
  { slug: "shoftim", name: "Shoftim", range: "Deuteronomy 16:18-21:9" },
  { slug: "ki-teitzei", name: "Ki Teitsei", range: "Deuteronomy 21:10-25:19" },
  { slug: "ki-tavo", name: "Ki Tavo", range: "Deuteronomy 26:1-29:8" },
  { slug: "nitzavim", name: "Nitsavim", range: "Deuteronomy 29:9-30:20" },
  { slug: "vayelekh", name: "Vayelekh", range: "Deuteronomy 31:1-31:30" },
  { slug: "haazinu", name: "Haazinou", range: "Deuteronomy 32:1-32:52" },
  { slug: "vezot-haberakha", name: "Vezot Haberakha", range: "Deuteronomy 33:1-34:12" }
];

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function cleanHtml(str = "") {
  return String(str)
    .replace(/<br\s*\/?>/gi, " ")
    .replace(/<[^>]+>/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function parseRange(range) {
  const m = range.match(/^(.+?) (\d+):(\d+)-(\d+):(\d+)$/);
  if (!m) throw new Error("Range invalide : " + range);

  return {
    book: m[1],
    startChapter: Number(m[2]),
    startVerse: Number(m[3]),
    endChapter: Number(m[4]),
    endVerse: Number(m[5])
  };
}

function isInsideRange(ref, range) {
  const r = parseRange(range);
  const m = ref.match(/^(.+?) (\d+):(\d+)$/);
  if (!m) return false;

  const book = m[1];
  const chapter = Number(m[2]);
  const verse = Number(m[3]);

  if (book !== r.book) return false;
  if (chapter < r.startChapter || chapter > r.endChapter) return false;
  if (chapter === r.startChapter && verse < r.startVerse) return false;
  if (chapter === r.endChapter && verse > r.endVerse) return false;

  return true;
}

async function getText(ref, lang = "he") {
  const url = `https://www.sefaria.org/api/texts/${encodeURIComponent(ref)}?lang=${lang}&context=0&commentary=0`;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 20000);

  try {
    const res = await fetch(url, { signal: controller.signal });
    if (!res.ok) {
      console.log("Erreur Sefaria", ref, res.status);
      return null;
    }

    const data = await res.json();
    return data;
  } catch (e) {
    console.log("Erreur fetch", ref, e.message);
    return null;
  } finally {
    clearTimeout(timer);
  }
}

function chapterToVerses(book, chapterNumber, heChapter = [], enChapter = []) {
  const max = Math.max(heChapter.length, enChapter.length);
  const verses = [];

  for (let i = 0; i < max; i++) {
    const ref = `${book} ${chapterNumber}:${i + 1}`;

    verses.push({
      ref,
      he: cleanHtml(heChapter[i] || ""),
      en: cleanHtml(enChapter[i] || ""),
      fr: "",
      rashi: []
    });
  }

  return verses;
}

async function fetchBookChapters(book, startChapter, endChapter) {
  const all = [];

  for (let chapter = startChapter; chapter <= endChapter; chapter++) {
    console.log(`Téléchargement ${book} ${chapter}`);

    const heData = await getText(`${book} ${chapter}`, "he");
    await sleep(150);

    const enData = await getText(`${book} ${chapter}`, "en");
    await sleep(150);

    const heChapter = Array.isArray(heData?.he) ? heData.he : [];
    const enChapter = Array.isArray(enData?.text) ? enData.text : [];

    all.push(...chapterToVerses(book, chapter, heChapter, enChapter));
  }

  return all;
}

async function fetchRashiForVerse(ref) {
  const he = await getText(`Rashi on ${ref}`, "he");
  await sleep(120);

  const en = await getText(`Rashi on ${ref}`, "en");
  await sleep(120);

  const heItems = Array.isArray(he?.he) ? he.he.flat(Infinity).filter(Boolean) : [];
  const enItems = Array.isArray(en?.text) ? en.text.flat(Infinity).filter(Boolean) : [];

  return heItems.map((item, i) => ({
    id: i + 1,
    he: cleanHtml(item),
    en: cleanHtml(enItems[i] || ""),
    fr: "",
    explanation_fr: ""
  }));
}

async function processParasha(p) {
  const range = parseRange(p.range);
  const outFile = path.join(outDir, `${p.slug}.json`);

  let existing = null;
  if (fs.existsSync(outFile)) {
    existing = JSON.parse(fs.readFileSync(outFile, "utf8"));
  }

  const existingByRef = new Map((existing?.verses || []).map(v => [v.ref, v]));

  console.log(`\n📖 ${p.name} — ${p.range}`);

  const chapters = await fetchBookChapters(range.book, range.startChapter, range.endChapter);
  const verses = chapters.filter(v => isInsideRange(v.ref, p.range));

  for (const verse of verses) {
    const old = existingByRef.get(verse.ref);

    if (old?.rashi?.length) {
      verse.rashi = old.rashi;
      verse.fr = old.fr || "";
      continue;
    }

    verse.rashi = await fetchRashiForVerse(verse.ref);
    console.log(`✓ ${verse.ref} Rachi:${verse.rashi.length}`);

    fs.writeFileSync(outFile, JSON.stringify({
      ...p,
      verses
    }, null, 2), "utf8");
  }

  fs.writeFileSync(outFile, JSON.stringify({
    ...p,
    verses
  }, null, 2), "utf8");

  console.log(`✅ ${p.name} sauvegardé : ${verses.length} versets`);
}

async function main() {
  fs.writeFileSync(
    path.join(outDir, "index.json"),
    JSON.stringify(parashiot.map(p => ({
      slug: p.slug,
      name: p.name,
      range: p.range,
      file: `${p.slug}.json`
    })), null, 2),
    "utf8"
  );

  for (const p of parashiot) {
    await processParasha(p);
  }

  console.log("\n✅ Toutes les parachiot sont terminées.");
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
