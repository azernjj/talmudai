import fs from "fs";
import path from "path";

const outDir = "public/data/shulchan-arukh";
fs.mkdirSync(outDir, { recursive: true });

const sections = [
  {
    slug: "orach-chaim",
    title: "Orach Chayim",
    heTitle: "אורח חיים",
    sefaria: "Shulchan Arukh, Orach Chayim"
  }
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

async function getText(ref, lang = "he") {
  const url = `https://www.sefaria.org/api/texts/${encodeURIComponent(ref)}?lang=${lang}&context=0&commentary=0`;

  try {
    const res = await fetch(url);
    if (!res.ok) {
      console.log("Erreur Sefaria", ref, res.status);
      return null;
    }
    return await res.json();
  } catch (e) {
    console.log("Erreur réseau", ref, e.message);
    return null;
  }
}

async function fetchSection(section) {
  console.log(`\n📜 ${section.title}`);

  const heData = await getText(section.sefaria, "he");
  await sleep(300);
  const enData = await getText(section.sefaria, "en");

  const heText = heData?.he || [];
  const enText = enData?.text || [];

  const simanim = [];

  const maxSimanim = Math.max(heText.length, enText.length);

  for (let i = 0; i < maxSimanim; i++) {
    const heSiman = Array.isArray(heText[i]) ? heText[i] : [];
    const enSiman = Array.isArray(enText[i]) ? enText[i] : [];

    const maxSeifim = Math.max(heSiman.length, enSiman.length);
    const seifim = [];

    for (let j = 0; j < maxSeifim; j++) {
      seifim.push({
        seif: j + 1,
        he: cleanHtml(heSiman[j] || ""),
        en: cleanHtml(enSiman[j] || ""),
        fr: "",
        commentaries: {}
      });
    }

    simanim.push({
      siman: i + 1,
      title: "",
      seifim
    });

    console.log(`Siman ${i + 1} : ${seifim.length} seifim`);
  }

  const out = {
    slug: section.slug,
    title: section.title,
    heTitle: section.heTitle,
    sefaria: section.sefaria,
    simanim
  };

  fs.writeFileSync(
    path.join(outDir, `${section.slug}.json`),
    JSON.stringify(out, null, 2),
    "utf8"
  );

  console.log(`✅ ${section.slug}.json sauvegardé`);
}

async function main() {
  fs.writeFileSync(
    path.join(outDir, "index.json"),
    JSON.stringify(sections.map(s => ({
      slug: s.slug,
      title: s.title,
      heTitle: s.heTitle,
      file: `${s.slug}.json`
    })), null, 2),
    "utf8"
  );

  for (const section of sections) {
    await fetchSection(section);
  }

  console.log("\n✅ Choul'han Aroukh — étape 1 terminée.");
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
