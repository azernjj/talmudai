export function renderLayout(app) {
  app.innerHTML = `
    <header class="topbar">
      <div class="brand">
        <h1>TALMUD AI</h1>
        <p>Beit Midrash numérique</p>
      </div>

      <div class="lang">
        <button id="mobileMenuBtn" class="mobileMenuBtn">☰ Menu</button>
        <button id="dictBtn">📖 Dictionnaire</button>
        <button id="parashaBtn">📖 Parachiot</button>
        <button
          id="correctionAdminBtn"
          class="correctionAdminBtn"
          title="Admin correction"
        >
          ⚙
        </button>

        <input
          id="globalSearch"
          placeholder="🔎 Rechercher..."
          autocomplete="off"
        />
      </div>
    </header>


<style>
.commentModeBar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:0 0 12px}
.commentModeBar select{max-width:100%;padding:6px;border-radius:6px}
.syncedHint{font-size:.9rem;opacity:.85}
.syncedSelected{outline:2px solid #ba9555;outline-offset:2px;border-radius:6px}
.syncedInlineComments{margin:12px 0;padding:12px;border-left:3px solid #ba9555;background:rgba(180,140,65,.06)}
.syncedInlineTitle{font-weight:700;margin-bottom:8px}
.syncedComment .he{white-space:normal;line-height:1.9;overflow-wrap:anywhere}
.syncedComment .mefarshemTrad{white-space:normal;overflow-wrap:anywhere}
@media(max-width:800px){.comments{display:block!important}.syncedSelected{outline:none}}
</style>

    <div class="layout">
      <aside class="sidebar">

        <section class="sideBlock">
          <h2>📚 Sedarim</h2>

          <input
            id="masechetSearch"
            class="masechetSearch"
            placeholder="🔍 Rechercher un traité..."
            autocomplete="off"
          />

          <div id="library" class="sideScroll"></div>
        </section>

        <section class="sideBlock">
          <h2>📘 Michna</h2>

          <input
            id="mishnaSearch"
            class="masechetSearch"
            placeholder="🔍 Rechercher un traité de Michna..."
            autocomplete="off"
          />

          <div
            id="mishnaLibrary"
            class="sideScroll smallScroll"
          ></div>
        </section>

        <section class="sideBlock">
          <h2>📜 Choul’han Aroukh</h2>

          <input
            id="saSearch"
            class="masechetSearch"
            placeholder="🔍 Rechercher une section..."
            autocomplete="off"
          />

          <div
            id="shulchanLibrary"
            class="sideScroll smallScroll"
          ></div>
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

        <div id="commentBox" class="commentBox">
          Choisis un commentaire.
        </div>
      </section>
    </div>

    <div id="dictOverlay" class="dictOverlay hidden"></div>

    <aside id="dictionaryPanel" class="dictionaryPanel hidden">
      <div class="dictHeader">
        <h2>📖 Dictionnaire araméen</h2>
        <button id="closeDictBtn">✕</button>
      </div>

      <input
        id="dictSearch"
        class="dictSearch"
        placeholder="Écris un mot araméen, français ou anglais..."
        autocomplete="off"
      />

      <div class="dictLangButtons">
        <button id="dictBothBtn" class="active">FR + EN</button>
        <button id="dictFrBtn">Français</button>
        <button id="dictEnBtn">English</button>
      </div>

      <div id="dictStatus" class="dictStatus">
        Dictionnaire prêt.
      </div>

      <div id="dictResults" class="dictResults"></div>
    </aside>

    <div id="correctionOverlay" class="dictOverlay hidden"></div>

    <aside id="correctionPanel" class="dictionaryPanel hidden">
      <div class="dictHeader">
        <h2>✏️ Correction française</h2>
        <button id="closeCorrectionBtn">✕</button>
      </div>

      <div id="correctionMeta" class="dictStatus"></div>

      <textarea
        id="correctionText"
        class="dictSearch"
        style="min-height:220px; resize:vertical; direction:ltr;"
      ></textarea>

      <div class="dictLangButtons">
        <button id="saveCorrectionBtn" class="active">
          ✅ Corriger
        </button>

        <button id="cancelCorrectionBtn">
          Annuler
        </button>
      </div>

      <div id="correctionStatus" class="dictStatus">
        Prêt.
      </div>
    </aside>
  `
}
