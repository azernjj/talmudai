export function renderLayout(app) {
  app.innerHTML = `
    <header class="topbar">
      <div class="brand">
        <h1>TALMUD AI</h1>
        <p>Beit Midrash numérique</p>
      </div>

    <div class="layout">
      <aside class="sidebar">
        <section class="sideBlock">
          <h2>📚 Sedarim</h2>
          <input id="masechetSearch" class="masechetSearch" placeholder="🔍 Rechercher un traité..." autocomplete="off" />
          <div id="library" class="sideScroll"></div>
        </section>

        <section class="sideBlock">
          <h2>📜 Choul’han Aroukh</h2>
          <input id="saSearch" class="masechetSearch" placeholder="🔍 Rechercher une section..." autocomplete="off" />
          <div id="shulchanLibrary" class="sideScroll smallScroll"></div>
        </section>
      </aside>

      <main class="reader">
        <div class="readerTitleRow">
          <h2 id="dafTitle">Chargement...</h2>

          <div class="titleLangButtons">
            <button id="frBtn">🇫🇷 Français</button>
            <button id="enBtn">🇬🇧 English</button>
          </div>
        </div>

        <div id="dafNav"></div>
        <div id="segments"></div>
      </main>

      <section class="comments">
        <h2>📜 Commentaires</h2>
        <div id="commentBox" class="commentBox">Choisis un commentaire.</div>
      </section>
    </div>

    <div id="dictOverlay" class="dictOverlay hidden"></div>

    <aside id="dictionaryPanel" class="dictionaryPanel hidden">
      <div class="dictHeader">
        <h2>📖 Dictionnaire araméen</h2>
        <button id="closeDictBtn">✕</button>
      </div>

      <input id="dictSearch" class="dictSearch" placeholder="Écris un mot araméen, français ou anglais..." autocomplete="off" />

      <div class="dictLangButtons">
        <button id="dictBothBtn" class="active">FR + EN</button>
        <button id="dictFrBtn">Français</button>
        <button id="dictEnBtn">English</button>
      </div>

      <div id="dictStatus" class="dictStatus">Dictionnaire prêt.</div>
      <div id="dictResults" class="dictResults"></div>
    </aside>
  `
}
