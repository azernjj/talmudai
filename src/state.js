export const state = {
  currentLang: localStorage.getItem('talmudLang') || 'fr',
  currentData: null,
  currentMode: 'talmud',
  currentParasha: null,
  currentDaf: localStorage.getItem('currentDaf') || '2a',
  dictionaryItems: [],
  dictionaryLoaded: false,
  dictLang: 'both',
  searchIndexes: []
}

export const sedarim = [
  { name: 'Zeraïm', masechtot: [{ name: 'Berakhot', file: 'berakhot.json' }] },
  { name: 'Moed', masechtot: [
    { name: 'Shabbat', file: 'shabbat.json' },
    { name: 'Erouvin', file: 'eruvin.json' },
    { name: 'Pessa’him', file: 'pesachim.json' },
    { name: 'Yoma', file: 'yoma.json' },
    { name: 'Soukka', file: 'sukkah.json' },
    { name: 'Beitsa', file: 'beitzah.json' },
    { name: 'Roch Hachana', file: 'rosh-hashanah.json' },
    { name: 'Taanit', file: 'taanit.json' },
    { name: 'Meguila', file: 'megillah.json' },
    { name: 'Moed Katan', file: 'moed-katan.json' },
    { name: 'Haguiga', file: 'chagigah.json' }
  ]},
  { name: 'Nachim', masechtot: [
    { name: 'Yevamot', file: 'yevamot.json' },
    { name: 'Ketoubot', file: 'ketubot.json' },
    { name: 'Nedarim', file: 'nedarim.json' },
    { name: 'Nazir', file: 'nazir.json' },
    { name: 'Sota', file: 'sotah.json' },
    { name: 'Gittin', file: 'gittin.json' },
    { name: 'Kiddouchin', file: 'kiddushin.json' }
  ]},
  { name: 'Nezikin', masechtot: [
    { name: 'Bava Kama', file: 'bava-kamma.json' },
    { name: 'Bava Metsia', file: 'bava-metzia.json' },
    { name: 'Bava Batra', file: 'bava-batra.json' },
    { name: 'Sanhédrin', file: 'sanhedrin.json' },
    { name: 'Makot', file: 'makkot.json' },
    { name: 'Chevouot', file: 'shevuot.json' },
    { name: 'Avoda Zara', file: 'avodah-zarah.json' },
    { name: 'Horayot', file: 'horayot.json' }
  ]},
  { name: 'Kodachim', masechtot: [
    { name: 'Zevahim', file: 'zevachim.json' },
    { name: 'Menahot', file: 'menachot.json' },
    { name: 'Houlin', file: 'chullin.json' },
    { name: 'Bekhorot', file: 'bekhorot.json' },
    { name: 'Arakhin', file: 'arakhin.json' },
    { name: 'Temoura', file: 'temurah.json' },
    { name: 'Keritot', file: 'keritot.json' },
    { name: 'Meila', file: 'meilah.json' },
    { name: 'Tamid', file: 'tamid.json' },
    { name: 'Midot', file: 'middot.json' },
    { name: 'Kinim', file: 'kinnim.json' }
  ]},
  { name: 'Taharot', masechtot: [{ name: 'Nidda', file: 'niddah.json' }] }
]
