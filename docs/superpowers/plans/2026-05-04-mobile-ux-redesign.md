# Mobile-first UX redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the JP→EN Matcher around the "EN first, JP confirmation" principle — mobile stacks EN on top with a sticky input bar; desktop keeps side-by-side. Bundle the already-staged image-loading fix (M1S/M1L/M2/M2a) into the same push.

**Architecture:** Single static `index.html` + `style.css` + `app.js`. No build step. All changes are in those three files plus `CLAUDE.md`. Mobile/desktop is handled by the existing `@media (max-width: 680px)` block plus a new `.input-bar--sticky` class applied by JS based on viewport + result state. Collapsible sections use the native `<details>` HTML element (zero JS). The JP-image-fallback mechanism built earlier (onerror swap) continues to work unchanged — the renderer just gets a new merged-panel variant when that fallback is in play.

**Tech Stack:** Vanilla HTML/CSS/JS. Browser APIs only (`IntersectionObserver`, `localStorage`, `matchMedia`). No tests framework — verification is manual in chrome-devtools MCP (running the existing `python3 -m http.server 8765` server).

**Working directory:** `/home/ec2-user/pokemon-tcg-jp-en-matcher`. No isolation worktree — this is a single-developer static site with an already-vetted local dev loop.

**Out of scope:** data pipeline, matching logic, scoring, browse grid internals, offline/PWA.

---

## File map

- **`index.html`** — update input section markup (add chip row containers, Browse button next to Match, auto-capitalize on Set ID input).
- **`style.css`** — add chip-row, sticky-bar, details-toggle, merged-panel, mobile-stack rules. Update existing mobile `@media` block.
- **`app.js`** — recents storage helpers, chip rendering, updated `renderCard()` with `compact`/`merged` variants, sticky-bar scroll/IntersectionObserver, remove `renderNavRow` and prev/next callsites.
- **`CLAUDE.md`** — reflect the new EN-priority layout invariant.

## Commit strategy

Two commits on `main`:

1. **Commit A (already staged, unpushed):** image fix — `SEREBII_SLUGS` + JP fallback onerror + doc updates. Tasks 0.1 & 0.2 below.
2. **Commit B (one commit at end of redesign):** the UX redesign. A single commit, not per-task — this is a UI cohesion change and splitting it produces intermediate states where the layout is half-redesigned. Tasks 1–10.

Both commits are pushed at the end (Task 11).

---

## Task 0: Commit + verify the image fix

The image-loading fix is already in the working tree but uncommitted. Commit it first so the UX work lands on a clean base.

**Files:**
- Modify (already staged in working tree): `app.js`, `style.css`, `CLAUDE.md`

- [ ] **Step 0.1: Review the staged diff**

Run:
```bash
git -C /home/ec2-user/pokemon-tcg-jp-en-matcher status
git -C /home/ec2-user/pokemon-tcg-jp-en-matcher diff --stat
```

Expected: three modified files (`app.js`, `style.css`, `CLAUDE.md`). No untracked files apart from `scripts/__pycache__/`.

- [ ] **Step 0.2: Create commit A (image fix)**

Run:
```bash
cd /home/ec2-user/pokemon-tcg-jp-en-matcher
git add app.js style.css CLAUDE.md
git commit -m "$(cat <<'EOF'
Fix EN images for M1S/M1L/M2/M2a; add JP image fallback

sideloadImageUrl() had no cases for ME1-/ME2-/ME2a- card IDs, so the
EN panel rendered image-less for all four sets. Replace the if-chain
with a SEREBII_SLUGS lookup table that includes ME1 (megaevolution),
ME2 (phantasmalflames), ME3 (perfectorder), ME4 (ninjaspinner), and
ME2a (shares the megadreamex slug since numbering is identical).

Add renderCard fallbackImgUrl arg: when the EN image 404s, the onerror
handler swaps src to the JP image, applies a dashed .jp-fallback
outline, and reveals a "Showing Japanese card" hint. All EN call sites
pass cardImageUrl(jpCard) as fallback.

Verified: M1S/001, M1L/001, M2/001, M2a/001 load EN images; SV5a/051
TCGdex path unchanged.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Expected: commit succeeds, `git log --oneline -1` shows the new commit on top of `b76c6fb`.

- [ ] **Step 0.3: Smoke-verify the image fix works**

Start the local server (if not already running):
```bash
cd /home/ec2-user/pokemon-tcg-jp-en-matcher
pkill -f "python3 -m http.server 8765" 2>/dev/null || true
python3 -m http.server 8765 > /tmp/http.log 2>&1 &
sleep 1
```

Then with chrome-devtools MCP:
```
mcp__chrome-devtools__new_page  http://localhost:8765/index.html?set=M1L&num=21
mcp__chrome-devtools__wait_for  ["Sandslash"]
mcp__chrome-devtools__evaluate_script — read both panels' img.src and naturalWidth
```

Expected: EN panel img.src starts with `https://www.serebii.net/card/megaevolution/` and `naturalWidth > 0`.

---

## Task 1: Recents localStorage helpers

Adds a small ring-buffer helper for the 5-most-recent set IDs.

**Files:**
- Modify: `app.js` around line 6 (near the existing `let lastScoredCards = …;` globals)

- [ ] **Step 1.1: Add recents helpers**

Edit `app.js` — add immediately after the existing `let lastScoredCards = new Map(); …` block (around line 6):

```js
// Recent set IDs — ring buffer of max 5, most-recent first. Persisted in localStorage.
const RECENTS_KEY = 'recentSets';
const RECENTS_MAX = 5;

function getRecentSets() {
  try {
    const raw = localStorage.getItem(RECENTS_KEY);
    if (!raw) return [];
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? arr.filter(s => typeof s === 'string') : [];
  } catch { return []; }
}

function pushRecentSet(setId) {
  if (!setId) return;
  const existing = getRecentSets();
  const next = [setId, ...existing.filter(s => s.toLowerCase() !== setId.toLowerCase())].slice(0, RECENTS_MAX);
  try { localStorage.setItem(RECENTS_KEY, JSON.stringify(next)); } catch {}
}
```

- [ ] **Step 1.2: Call `pushRecentSet` on every successful search**

In `doSearch()` find the existing `try { localStorage.setItem('lastSet', setId); } catch {}` call (around line 611) and append:

```js
    try { localStorage.setItem('lastSet', setId); } catch {}
    pushRecentSet(setId);
```

Leave `lastSet` alone — it's still used elsewhere for initial input restoration.

- [ ] **Step 1.3: Browser smoke check**

With chrome-devtools MCP:
```
mcp__chrome-devtools__new_page http://localhost:8765/?set=M1S&num=001
mcp__chrome-devtools__wait_for ["Translation"]
mcp__chrome-devtools__evaluate_script  () => localStorage.getItem('recentSets')
```

Expected: `'["M1S"]'` (or containing `M1S`). Navigate to `?set=M2&num=001`, repeat — expected: `'["M2","M1S"]'`.

---

## Task 2: Chip row — HTML + CSS + rendering

Adds the horizontally-scrollable single-row chip bar under the Set ID input. Shows recents by default; swaps to autocomplete while typing.

**Files:**
- Modify: `index.html` — input section
- Modify: `style.css` — new `.chip-row` block
- Modify: `app.js` — chip render + focus/blur wiring

- [ ] **Step 2.1: Update `index.html` input section**

Replace the entire `<div class="input-section">…</div>` plus the following `<button class="browse-link">` (currently lines 56–68 of index.html) with:

```html
  <div class="input-section" id="inputSection">
    <div class="field">
      <label>Japanese Set ID</label>
      <input id="setInput" type="text" placeholder="e.g. sv8, M1L" list="setList"
             autocomplete="off" autocapitalize="characters" spellcheck="false">
      <datalist id="setList"></datalist>
      <div class="chip-row" id="chipRow" role="listbox" aria-label="Recent or matching set IDs"></div>
    </div>
    <div class="field">
      <label>Card #</label>
      <input id="cardNum" type="text" placeholder="021" inputmode="numeric" pattern="[0-9]*">
    </div>
    <div class="input-actions">
      <button id="searchBtn" onclick="doSearch()">Match</button>
      <button id="browseBtn" class="btn-secondary" onclick="browseSet()" aria-label="Browse set">
        <span class="browse-label">Browse</span>
        <span class="browse-icon" aria-hidden="true">📂</span>
      </button>
    </div>
  </div>
```

The old free-floating `<button class="browse-link" onclick="browseSet()">Browse set →</button>` line is deleted as part of this replacement.

- [ ] **Step 2.2: Add chip-row CSS**

In `style.css`, after the existing `.field input { width: 120px; … }` rule (around line 98), add:

```css
/* ── Chip row (recents / autocomplete) ──────────────────── */
.chip-row {
  display: flex;
  gap: 0.4rem;
  overflow-x: auto;
  scrollbar-width: none;
  padding: 0.3rem 0 0.1rem;
  margin-top: 0.25rem;
  min-height: 0;
}
.chip-row::-webkit-scrollbar { display: none; }
.chip-row:empty { display: none; }
.chip {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 32px;
  min-width: 44px;
  padding: 0.25rem 0.7rem;
  border-radius: 16px;
  background: var(--surface-deep);
  border: 1px solid #2a3a5e;
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 0.78rem;
  font-weight: 500;
  cursor: pointer;
  user-select: none;
  transition: background 0.12s, border-color 0.12s, color 0.12s;
}
.chip:hover, .chip:focus-visible {
  background: #1a2a4e;
  border-color: var(--gold);
  color: var(--gold);
  outline: none;
}
.chip--suggest { border-style: dashed; }

/* Secondary button style for Browse */
.input-actions { display: flex; gap: 0.4rem; align-self: end; }
.btn-secondary {
  background: transparent;
  color: var(--gold);
  border: 1px solid var(--gold);
}
.btn-secondary:hover {
  background: var(--gold-dim);
  color: var(--gold);
  box-shadow: none;
  transform: translateY(-1px);
}
.btn-secondary .browse-icon { display: none; }
```

- [ ] **Step 2.3: Add chip rendering to `app.js`**

Add near the bottom of `app.js`, directly before the closing `// Init:` block (around line 931, immediately before `const sideloadReadyPromise = loadSideloadData();`):

```js
// ── Chip row: recents + autocomplete ─────────────────────
function renderChipRow() {
  const row = document.getElementById('chipRow');
  const input = document.getElementById('setInput');
  if (!row || !input) return;
  const typed = input.value.trim();
  let items = [];
  let mode = 'recent';
  if (typed && document.activeElement === input) {
    // Autocomplete mode: show up to 3 sets whose id contains the typed substring
    const lower = typed.toLowerCase();
    const allIds = [
      ...SIDELOAD_CONFIG.jp.map(c => c.id),
      ...Array.from(document.querySelectorAll('#setList option')).map(o => o.value),
    ];
    const seen = new Set();
    for (const id of allIds) {
      if (!id || seen.has(id.toLowerCase())) continue;
      if (id.toLowerCase() === lower) continue; // don't suggest an exact match
      if (id.toLowerCase().includes(lower)) {
        items.push(id);
        seen.add(id.toLowerCase());
        if (items.length >= 3) break;
      }
    }
    mode = 'suggest';
  } else {
    items = getRecentSets();
  }
  row.innerHTML = items.map(id =>
    `<button type="button" class="chip ${mode === 'suggest' ? 'chip--suggest' : ''}"
             data-set="${safeHtml(id)}" tabindex="0">${safeHtml(id)}</button>`
  ).join('');
}

function wireChipRow() {
  const row = document.getElementById('chipRow');
  const input = document.getElementById('setInput');
  const cardNum = document.getElementById('cardNum');
  if (!row || !input || !cardNum) return;
  row.addEventListener('click', e => {
    const chip = e.target.closest('.chip');
    if (!chip) return;
    input.value = chip.dataset.set;
    renderChipRow();
    cardNum.focus();
  });
  input.addEventListener('focus', renderChipRow);
  input.addEventListener('input', renderChipRow);
  input.addEventListener('blur', () => setTimeout(renderChipRow, 120)); // delay so chip click fires first
}
```

- [ ] **Step 2.4: Call chip wiring at init**

In `app.js`, find the existing init block near the bottom:

```js
const sideloadReadyPromise = loadSideloadData();
loadSets();
```

Replace with:

```js
const sideloadReadyPromise = loadSideloadData();
loadSets().then(renderChipRow);
wireChipRow();
renderChipRow();
```

Also in `doSearch()`'s `try/finally`, after `pushRecentSet(setId)` in Task 1, add one more line — `renderChipRow();` — so a new search immediately refreshes the recents row.

- [ ] **Step 2.5: Update Enter-key behavior on Set ID input**

Find (around line 950):
```js
document.getElementById('setInput').addEventListener('keydown', e => {
  if (e.key === 'Enter') doSearch();
});
```

Replace with:
```js
document.getElementById('setInput').addEventListener('keydown', e => {
  if (e.key === 'Enter') {
    e.preventDefault();
    document.getElementById('cardNum').focus();
  }
});
```

- [ ] **Step 2.6: Browser smoke check**

Reload page. With chrome-devtools MCP:
```
mcp__chrome-devtools__navigate_page  http://localhost:8765/
mcp__chrome-devtools__evaluate_script () => document.querySelectorAll('#chipRow .chip').length
```

Expected: ≥1 (since we've done a few searches by now — recents should exist).

Focus the Set ID input and type "m":
```
mcp__chrome-devtools__click <uid for #setInput>
mcp__chrome-devtools__type_text  "m"
mcp__chrome-devtools__evaluate_script () => Array.from(document.querySelectorAll('.chip')).map(c => c.dataset.set)
```

Expected: array contains uppercased matches like `"M1S"`, `"M1L"`, `"M2"` (up to 3).

Click a chip:
```
mcp__chrome-devtools__click <uid for a chip>
mcp__chrome-devtools__evaluate_script () => [document.getElementById('setInput').value, document.activeElement.id]
```

Expected: `["M1S", "cardNum"]` (or whichever chip was clicked).

---

## Task 3: Details toggle (collapsible meta section)

Makes HP/stage/illustrator/weakness/resistance/retreat/flavor collapse into a `<details>` element. Unchanged on desktop by default (open), collapsed on mobile.

**Files:**
- Modify: `app.js` — `renderCard()` meta block
- Modify: `style.css` — details styling + mobile collapse default

- [ ] **Step 3.1: Refactor meta block in `renderCard()`**

In `app.js`, locate the meta block in `renderCard()` (around lines 228–246 after earlier edits — the `<div class="card-meta">…</div>` block). Wrap the meta rows that belong under "Show details" in a `<details>` element, keeping attacks/abilities outside. Replace the `.card-meta` div contents with:

```js
      <div class="card-meta">
        <div class="meta-head">
          <span class="lbl">Set</span><span>${setName}</span> <span style="color:var(--text-faint)">(${cardId})</span>
        </div>
        ${attacks || abilities ? `<div class="atk-section">${abilities || ''}${attacks || ''}</div>` : ''}
        ${(card.category === 'Trainer' || card.category === 'Energy') && card.effect ? `<div class="trainer-effect">${safeHtml(card.effect)}</div>` : ''}
        <details class="card-details">
          <summary>Show details</summary>
          <div class="details-inner">
            ${card.category ? `<span class="lbl">Category</span><span>${safeHtml(card.category)}${subcategory ? ` — ${subcategory}` : ''}</span><br>` : ''}
            ${hp ? `<span class="lbl">HP</span><span>${hp}</span><br>` : ''}
            ${stage ? `<span class="lbl">Stage</span><span>${stage}</span><br>` : ''}
            ${illustrator ? `<span class="lbl">Art</span><span>${illustrator}</span><br>` : ''}
            ${types ? `<span class="lbl">Type</span>${types}<br>` : ''}
            ${weakness ? `<span class="lbl">Weak</span>${weakness}<br>` : ''}
            ${resistance ? `<span class="lbl">Resist</span>${resistance}<br>` : ''}
            ${retreat ? `<span class="lbl">Retreat</span>${retreat}<br>` : ''}
            ${card.description ? `<div class="card-desc">${safeHtml(card.description)}</div>` : ''}
          </div>
        </details>
      </div>`;
```

(Note: the existing inline style on the description `div` moves to a `.card-desc` CSS class in the next step; the inline style on the trainer-effect moves to `.trainer-effect`.)

- [ ] **Step 3.2: Add details-related CSS**

In `style.css`, add after the existing `.card-meta span { … }` rule (around line 172):

```css
.meta-head { margin-bottom: 0.5rem; }
.card-details { margin-top: 0.6rem; border-top: 1px solid #ffffff10; padding-top: 0.5rem; }
.card-details summary {
  cursor: pointer;
  list-style: none;
  font-size: 0.75rem;
  font-family: var(--font-display);
  color: var(--text-faint);
  letter-spacing: 0.04em;
  text-transform: uppercase;
  user-select: none;
  padding: 0.2rem 0;
}
.card-details summary::-webkit-details-marker { display: none; }
.card-details summary::before {
  content: '▸';
  display: inline-block;
  margin-right: 0.4rem;
  color: var(--gold);
  transition: transform 0.15s;
}
.card-details[open] summary::before { transform: rotate(90deg); }
.card-details summary:hover { color: var(--gold); }
.details-inner { padding-top: 0.4rem; font-size: 0.8rem; color: var(--text-muted); line-height: 1.7; }
.details-inner .lbl { color: var(--text-faint); }
.details-inner span:not(.lbl) { color: var(--text); font-weight: 500; }
.card-desc { margin-top: 0.5rem; font-size: 0.75rem; color: #666; font-style: italic; }
.trainer-effect { margin-top: 0.6rem; font-size: 0.8rem; color: var(--text-muted); font-style: italic; line-height: 1.5; padding: 0.4rem 0.6rem; background: var(--surface-deep); border-radius: 6px; border-left: 2px solid var(--gold-dim); }
```

- [ ] **Step 3.3: Open details by default on desktop, closed on mobile**

Append to `style.css`:

```css
@media (min-width: 681px) {
  .card-details:not([data-forced]) { /* desktop default: allow both states, start open via JS */ }
}
```

And in `app.js`, immediately after setting `results.innerHTML = …` in every branch of `doSearch` and in `showAlternate`, add a one-liner to open details on desktop:

```js
if (window.matchMedia('(min-width: 681px)').matches) {
  document.querySelectorAll('#results .card-details').forEach(d => d.open = true);
}
```

This is a small helper — to avoid repeating the 3-line block in 5 places, define it once near `renderCard`:

```js
function openDetailsOnDesktop() {
  if (window.matchMedia('(min-width: 681px)').matches) {
    document.querySelectorAll('#results .card-details').forEach(d => d.open = true);
  }
}
```

Then call `openDetailsOnDesktop();` immediately after every `document.getElementById('results').innerHTML = …` in `doSearch()` and after `panels[1].outerHTML = …` in `showAlternate()`.

- [ ] **Step 3.4: Browser smoke check**

Reload and search M1S/001. Verify:
- Desktop viewport (≥681px): details sections start open.
- Resize below 680px and reload: details start closed. Click "Show details ▸" → expands.

---

## Task 4: Remove prev/next nav

Per spec: prev/next removed entirely.

**Files:**
- Modify: `app.js` — delete `renderNavRow`, remove its calls

- [ ] **Step 4.1: Delete `renderNavRow` function**

In `app.js`, delete the entire `function renderNavRow() { … }` block (around lines 896–907 before this task — line numbers will have shifted slightly).

- [ ] **Step 4.2: Remove all `${renderNavRow()}` calls**

Grep and remove every `${renderNavRow()}` occurrence in `app.js`. There are approximately 5 such template interpolations inside `doSearch()`. For each, delete the entire interpolation including any surrounding whitespace/newlines that would leave blank output.

Verify with:
```bash
grep -n "renderNavRow" /home/ec2-user/pokemon-tcg-jp-en-matcher/app.js
```

Expected: no matches.

- [ ] **Step 4.3: Browser smoke check**

Reload, run a search. Verify no `← #prev` / `#next →` buttons appear under the result.

---

## Task 5: Mobile layout — EN-first stack with new `renderCard` compact variant

Restructures how the results block is assembled: mobile renders EN then a compact JP; desktop keeps the current two-panel side-by-side.

**Files:**
- Modify: `app.js` — add `renderCardCompactJp`, `assembleResults` helper
- Modify: `style.css` — mobile stacking rules

- [ ] **Step 5.1: Add a compact JP renderer**

Add to `app.js` directly after the existing `renderCard(...)` function:

```js
// Compact JP renderer — used on mobile as a scroll-below confirmation block.
// Only image by default; optional expandable text.
function renderCardCompactJp(card) {
  const imgUrl = cardImageUrl(card);
  const cardName = safeHtml(card.name);
  const cardId = safeHtml(card.id);
  const attacks = (card.attacks || []).map(a => {
    const cost = (a.cost || []).map(t => energyBadge(t)).join('');
    return `<div class="atk-row">${cost ? `<span class="atk-cost">${cost}</span>` : ''}<span class="atk-name">${safeHtml(a.name)}</span>${a.damage != null ? `<span class="atk-dmg">${safeHtml(String(a.damage))}</span>` : ''}</div>${a.effect ? `<div class="atk-effect">${safeHtml(a.effect)}</div>` : ''}`;
  }).join('');
  const abilities = (card.abilities || []).map(a =>
    `<div class="ability-row"><span class="ability-label">Ability</span> <span class="ability-name">${safeHtml(a.name)}</span></div>${a.effect ? `<div class="atk-effect">${safeHtml(a.effect)}</div>` : ''}`
  ).join('');
  return `
    <div class="card-panel card-panel--compact">
      <div class="panel-header">
        <span class="lang-badge ja">日本語 Japanese</span>
        <span class="compact-id">${cardId}</span>
      </div>
      <h2 class="compact-name">${cardName}</h2>
      ${imgUrl ? `<img src="${imgUrl}" alt="${cardName}" loading="lazy" class="compact-img" onerror="this.onerror=null;this.style.display='none'">` : ''}
      ${abilities || attacks ? `<details class="jp-text-toggle">
        <summary>Show JP text</summary>
        <div class="jp-text-inner">${abilities}${attacks}</div>
      </details>` : ''}
    </div>`;
}
```

- [ ] **Step 5.2: Add an `assembleResults` helper**

Add to `app.js` directly after `renderCardCompactJp`:

```js
// Compose the results HTML with mobile-vs-desktop awareness.
// mode: 'pair' (EN + JP side-by-side or stacked), 'merged' (single JP-fallback panel), 'en-only' (no JP panel)
function assembleResults(jpCard, enCard, mode, badge, score) {
  const isMobile = window.matchMedia('(max-width: 680px)').matches;
  if (mode === 'merged') {
    // Single panel: used when EN image = JP image (fallback case)
    return `<div class="cards-container cards-container--merged">${renderCard(enCard, 'en', badge || '🔄 Translation', score, cardImageUrl(jpCard))}</div>`;
  }
  if (mode === 'en-only') {
    return `<div class="cards-container">${renderCard(jpCard, 'ja')}</div>`;
  }
  const jpImg = cardImageUrl(jpCard);
  if (isMobile) {
    return `<div class="cards-container cards-container--stack">
      ${renderCard(enCard, 'en', badge, score, jpImg)}
      ${renderCardCompactJp(jpCard)}
    </div>`;
  }
  return `<div class="cards-container">
    ${renderCard(jpCard, 'ja')}
    <div class="arrow">→</div>
    ${renderCard(enCard, 'en', badge, score, jpImg)}
  </div>`;
}
```

- [ ] **Step 5.3: Replace cards-container markup in every `doSearch` branch**

In `doSearch()`:

**Branch A** — transCard found (around line 748, after our edits):
Replace:
```js
          const jpImg = cardImageUrl(jpCard);
          document.getElementById('results').innerHTML = `
            <div class="cards-container">
              ${renderCard(jpCard, 'ja')}
              <div class="arrow">→</div>
              ${renderCard(transCard, 'en', '🔄 Translation', undefined, jpImg)}
            </div>
            <button class="share-btn" id="shareBtn">🔗 Copy link</button>`;
```
with:
```js
          document.getElementById('results').innerHTML =
            assembleResults(jpCard, transCard, 'pair', '🔄 Translation') +
            `<button class="share-btn" id="shareBtn">🔗 Copy link</button>`;
          openDetailsOnDesktop();
```

**Branch B** — synthetic EN (around line 826):
Replace similarly to `assembleResults(jpCard, syntheticEn, 'pair', '🔄 Translation')` + existing match-info div.

**Branch C** — no EN found (around line 840):
Keep `assembleResults(jpCard, null, 'en-only')` + existing no-match div.

**Branch D** — could-not-fetch (around line 887):
Same — `assembleResults(jpCard, null, 'en-only')` + existing no-match div.

**Branch E** — best match found (around line 892):
Replace the existing `<div class="cards-container">…</div>` block with `assembleResults(jpCard, best.card, 'pair', null, best.score)`.

After each `innerHTML = …` assignment in these branches, ensure `openDetailsOnDesktop();` is called.

- [ ] **Step 5.4: Update `showAlternate` for mobile re-render**

Currently `showAlternate` replaces only `panels[1].outerHTML`. On mobile after stacking, `panels[1]` will be the JP compact panel (EN is panels[0]). Adjust:

```js
async function showAlternate(cardId, score) {
  let card = null;
  for (const sEnSetData of Object.values(SIDELOAD_EN_SETS)) {
    const found = Object.values(sEnSetData.cards).find(c => c.id === cardId);
    if (found) { card = found; break; }
  }
  if (!card) card = lastScoredCards.get(cardId) || null;
  if (!card) {
    card = await cachedApiFetch(`${API}/en/cards/${cardId}`);
    if (!card) return;
  }
  const isMobile = window.matchMedia('(max-width: 680px)').matches;
  const panels = document.querySelectorAll('.card-panel');
  if (panels.length < 2) return;
  // EN panel is panels[0] on mobile (EN-first stack), panels[1] on desktop (side-by-side)
  const enPanel = isMobile ? panels[0] : panels[1];
  const jpImg = (isMobile ? panels[1] : panels[0]).querySelector('img')?.src || null;
  enPanel.outerHTML = renderCard(card, 'en', null, score, jpImg);
  openDetailsOnDesktop();
}
```

- [ ] **Step 5.5: Add mobile stacking CSS**

In `style.css`, at the end of the file, replace the existing `@media (max-width: 680px) { … }` block with:

```css
/* ── Mobile ─────────────────────────────────────────────── */
@media (max-width: 680px) {
  body { padding: 1rem 0.5rem 6rem; } /* bottom padding reserves space for sticky bar */
  h1 { font-size: 1.5rem; }
  .subtitle { font-size: 0.85rem; }
  .input-section { gap: 0.4rem; }
  .field select { min-width: 160px; }
  .field input { width: 100%; }
  .field { flex: 1; min-width: 0; }

  /* EN-first stack */
  .cards-container--stack {
    flex-direction: column;
    align-items: stretch;
    gap: 1rem;
  }
  .cards-container--stack .arrow { display: none; }
  .cards-container { gap: 0.6rem; }
  .card-panel { padding: 0.85rem; min-width: unset; max-width: 100%; }
  .card-panel h2 { font-size: 1.15rem; }
  .arrow { font-size: 1.2rem; }

  /* Compact JP panel below EN */
  .card-panel--compact {
    background: transparent;
    box-shadow: none;
    border: none;
    padding: 0.6rem 0;
    text-align: center;
  }
  .card-panel--compact .panel-header { justify-content: center; gap: 0.5rem; }
  .compact-name { font-size: 0.95rem; color: var(--text-muted); margin-bottom: 0.6rem; text-align: center; font-weight: 600; }
  .compact-id { font-family: var(--font-mono); font-size: 0.7rem; color: var(--text-faint); }
  .compact-img { width: 62%; max-width: 260px; margin: 0 auto 0.6rem; display: block; }
  .jp-text-toggle { margin: 0.3rem auto; max-width: 280px; }
  .jp-text-toggle summary {
    cursor: pointer; list-style: none;
    font-size: 0.75rem; color: var(--text-faint);
    font-family: var(--font-display); letter-spacing: 0.05em; text-transform: uppercase;
    text-align: center; padding: 0.3rem 0;
  }
  .jp-text-toggle summary::-webkit-details-marker { display: none; }
  .jp-text-toggle summary::before { content: '▸'; margin-right: 0.3rem; display: inline-block; transition: transform 0.15s; color: var(--gold); }
  .jp-text-toggle[open] summary::before { transform: rotate(90deg); }
  .jp-text-inner { text-align: left; font-size: 0.78rem; color: var(--text-muted); padding: 0.3rem 0.8rem; background: var(--surface); border-radius: 6px; }

  .howto-content { flex-direction: column; }
  .howto-card { width: 180px; align-self: center; }
  .browse-grid { grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); gap: 0.6rem; }
  .match-info { font-size: 0.8rem; }

  /* Hide the textual Browse button, show compact icon */
  .btn-secondary .browse-label { display: none; }
  .btn-secondary .browse-icon { display: inline; }
  .btn-secondary { padding: 0.6rem 0.8rem; }
  .input-actions { align-self: stretch; }
}
```

- [ ] **Step 5.6: Merged panel CSS**

Append to `style.css`:

```css
/* Merged panel variant — used when EN image falls back to JP image */
.cards-container--merged { justify-content: center; }
.cards-container--merged .card-panel { max-width: 420px; }
```

- [ ] **Step 5.7: Browser smoke check**

Desktop (1280×800) via chrome-devtools MCP:
- Visit `?set=M1S&num=001`. Expect JP left, arrow, EN right (current desktop layout).

Mobile (375×812):
```
mcp__chrome-devtools__resize_page  width=375 height=812
mcp__chrome-devtools__navigate_page reload
mcp__chrome-devtools__wait_for ["Translation"]
mcp__chrome-devtools__take_screenshot fullPage=true
```

Expect: EN panel on top (large image), below it a compact centered JP image (~62% width), "Show JP text" link below. No `→` arrow.

Check details toggles — click "Show JP text" and "Show details" on the EN panel — both expand and collapse without errors.

---

## Task 6: JP-fallback merged panel detection

When the EN image equals the JP image (shouldn't normally happen but can for ME2a where both slugs are `megadreamex`) or when the EN panel's image has 404'd to the JP image, show a single merged panel instead of two.

Since the 404 detection currently happens after render via onerror, the cleanest trigger is at render time: check whether `cardImageUrl(enCard) === cardImageUrl(jpCard)` (same Serebii slug + same number) — if so, render merged mode immediately.

**Files:**
- Modify: `app.js` — adjust `assembleResults` and branches in `doSearch` to detect merged

- [ ] **Step 6.1: Detect equal image URLs and switch to merged mode**

Replace the `assembleResults` function from Task 5.2 with this expanded version:

```js
function assembleResults(jpCard, enCard, mode, badge, score) {
  const isMobile = window.matchMedia('(max-width: 680px)').matches;
  if (mode === 'en-only') {
    return `<div class="cards-container">${renderCard(jpCard, 'ja')}</div>`;
  }
  if (mode === 'merged') {
    return `<div class="cards-container cards-container--merged">${renderCard(enCard, 'en', badge || '🔄 Translation', score, null)}</div>`;
  }
  // Auto-detect merged: EN and JP would render the same image (e.g. ME2a ↔ M2a share the megadreamex slug)
  const jpImg = cardImageUrl(jpCard);
  const enImg = cardImageUrl(enCard);
  if (jpImg && enImg && jpImg === enImg) {
    return `<div class="cards-container cards-container--merged">${renderCard(enCard, 'en', badge || '🔄 Translation', score, null)}<p class="merged-note">Showing Japanese card art — no English print available yet.</p></div>`;
  }
  if (isMobile) {
    return `<div class="cards-container cards-container--stack">
      ${renderCard(enCard, 'en', badge, score, jpImg)}
      ${renderCardCompactJp(jpCard)}
    </div>`;
  }
  return `<div class="cards-container">
    ${renderCard(jpCard, 'ja')}
    <div class="arrow">→</div>
    ${renderCard(enCard, 'en', badge, score, jpImg)}
  </div>`;
}
```

- [ ] **Step 6.2: Style the merged note**

Append to `style.css`:

```css
.merged-note {
  font-size: 0.75rem;
  color: var(--text-muted);
  font-style: italic;
  text-align: center;
  margin: 0.4rem auto 0;
  max-width: 420px;
  opacity: 0.85;
}
```

- [ ] **Step 6.3: Browser smoke check**

Visit `?set=M2a&num=001`. Expected: single merged panel (no JP side), with "Showing Japanese card art — no English print available yet" note below.

---

## Task 7: Sticky input bar on mobile

When a result is visible on mobile, the input section becomes a fixed bottom bar. Uses `IntersectionObserver` watching the EN image to toggle auto-hide during scroll.

**Files:**
- Modify: `app.js` — sticky bar state manager
- Modify: `style.css` — `.input-section--sticky` rules

- [ ] **Step 7.1: Add sticky-bar state manager**

Append to `app.js` (above the init block):

```js
// ── Sticky input bar on mobile ───────────────────────────
let stickyObserver = null;
function refreshStickyBar() {
  const section = document.getElementById('inputSection');
  const results = document.getElementById('results');
  if (!section || !results) return;
  const isMobile = window.matchMedia('(max-width: 680px)').matches;
  const hasResults = results.children.length > 0;
  if (isMobile && hasResults) {
    section.classList.add('input-section--sticky');
  } else {
    section.classList.remove('input-section--sticky', 'input-section--hidden');
  }
  // IntersectionObserver — auto-hide while the EN image is visible (full EN card in view)
  if (stickyObserver) { stickyObserver.disconnect(); stickyObserver = null; }
  if (isMobile && hasResults) {
    // Watch the first .card-panel (EN panel) — hide sticky bar when it's >70% visible
    const enPanel = document.querySelector('#results .card-panel');
    if (enPanel) {
      stickyObserver = new IntersectionObserver(entries => {
        for (const entry of entries) {
          if (entry.intersectionRatio > 0.7) {
            section.classList.add('input-section--hidden');
          } else {
            section.classList.remove('input-section--hidden');
          }
        }
      }, { threshold: [0.3, 0.7] });
      stickyObserver.observe(enPanel);
    }
  }
}
window.addEventListener('resize', refreshStickyBar);
```

- [ ] **Step 7.2: Call `refreshStickyBar()` after every render**

In `doSearch`, in every branch after `document.getElementById('results').innerHTML = …`, add `refreshStickyBar();` (near the `openDetailsOnDesktop();` call).

Also call `refreshStickyBar();` once at init (in the same block where `renderChipRow();` is called).

- [ ] **Step 7.3: Sticky-bar CSS**

Append to `style.css`:

```css
@media (max-width: 680px) {
  .input-section--sticky {
    position: fixed;
    bottom: 0; left: 0; right: 0;
    z-index: 900;
    background: var(--surface);
    padding: 0.5rem 0.6rem 0.6rem;
    margin: 0;
    box-shadow: 0 -4px 16px rgba(0,0,0,0.5);
    border-top: 1px solid #ffffff12;
    transform: translateY(0);
    transition: transform 0.25s ease;
    flex-wrap: nowrap;
    gap: 0.3rem;
    align-items: end;
  }
  .input-section--sticky.input-section--hidden {
    transform: translateY(100%);
  }
  .input-section--sticky .field label { display: none; }
  .input-section--sticky .chip-row { display: none; } /* keep sticky bar thin; chips only in non-sticky mode */
  .input-section--sticky #setInput { width: 100%; padding: 0.45rem 0.6rem; font-size: 0.85rem; }
  .input-section--sticky #cardNum { width: 70px; padding: 0.45rem 0.5rem; font-size: 0.85rem; }
  .input-section--sticky .field { flex: 1; }
  .input-section--sticky .field:nth-child(2) { flex: 0 0 auto; }
  .input-section--sticky button { padding: 0.5rem 0.9rem; font-size: 0.8rem; }
  .input-section--sticky .btn-secondary { padding: 0.5rem 0.6rem; }
}
```

- [ ] **Step 7.4: Browser smoke check**

Mobile viewport (375×812):
- Initial load: input section in normal flow.
- After a match: input section becomes sticky bottom bar.
- Scroll down slowly — the sticky bar remains visible.
- Scroll up so the full EN image is >70% in view → sticky bar hides (slides down).
- Scroll back down → sticky bar re-appears.

Use:
```
mcp__chrome-devtools__evaluate_script  () => document.getElementById('inputSection').className
mcp__chrome-devtools__evaluate_script  () => { window.scrollTo(0, 0); return true; }
```

---

## Task 8: Share button — move into EN panel header

Moves 🔗 Copy Link from below the cards into the EN panel header as a small icon button.

**Files:**
- Modify: `app.js` — `renderCard` header area + remove standalone share button from `doSearch`
- Modify: `style.css` — `.share-icon` style

- [ ] **Step 8.1: Inject share icon into EN panel header**

In `renderCard`, find the `<div class="panel-header">` block and change it so an EN panel includes a share icon:

```js
  const shareBtn = (lang === 'en' || badge) ? `<button class="share-icon" id="shareBtn" title="Copy link" aria-label="Copy link">🔗</button>` : '';
  // …
  return `
    <div class="card-panel${imgUrl ? '' : ' no-image'}">
      <div class="panel-header">
        <span class="lang-badge ${badgeClass}">${badgeLabel}</span>
        ${confidencePip}
        ${shareBtn}
      </div>
      …
```

(Only EN panels and Translation-badged panels get the share icon; JP panels don't.)

- [ ] **Step 8.2: Remove standalone share buttons**

In `doSearch`, remove the `+ <button class="share-btn" id="shareBtn">🔗 Copy link</button>` append from all branches. The share handler in the global click listener already matches `#shareBtn`, so no listener change is needed.

- [ ] **Step 8.3: Style the share icon**

Append to `style.css`:

```css
.panel-header { align-items: center; }
.share-icon {
  margin-left: auto;
  background: transparent;
  border: 1px solid #2a3a5e;
  border-radius: 6px;
  width: 2rem;
  height: 2rem;
  padding: 0;
  font-size: 0.9rem;
  color: var(--text-muted);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: border-color 0.15s, color 0.15s, transform 0.1s;
}
.share-icon:hover { border-color: var(--gold); color: var(--gold); transform: translateY(-1px); box-shadow: none; }
.share-icon.copied { border-color: var(--green); color: var(--green); transform: none; box-shadow: none; }
```

- [ ] **Step 8.4: Update the share handler's success state**

In the existing `document.addEventListener('click', e => { … })` block that handles `#shareBtn`, the current code swaps textContent to "✓ Copied!". That's a poor fit for an icon — update to:

```js
  if (e.target.closest('#shareBtn')) {
    const setId = document.getElementById('setInput').value.trim();
    const num = document.getElementById('cardNum').value.trim();
    const url = `${location.origin}${location.pathname}?set=${encodeURIComponent(setId)}&num=${encodeURIComponent(num)}`;
    navigator.clipboard.writeText(url).then(() => {
      const btn = document.getElementById('shareBtn');
      if (btn) {
        btn.textContent = '✓';
        btn.classList.add('copied');
        setTimeout(() => { btn.textContent = '🔗'; btn.classList.remove('copied'); }, 1500);
      }
    }).catch(() => {});
  }
```

- [ ] **Step 8.5: Browser smoke check**

Run a search. Verify the 🔗 icon sits at the right side of the EN panel header. Click it → changes to ✓ briefly. Verify no standalone "Copy link" button exists below the cards.

---

## Task 9: Update CLAUDE.md invariants

The redesign changes the "never show JP image in EN panel" invariant (we already weakened it in Commit A, but not its wording around layout).

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 9.1: Update the Platform goal section**

Replace the existing "Display priority" list in `CLAUDE.md`:

```md
**Display priority:**
1. If an official English card image is available → show it (the EN card panel is what you show opponents)
2. If no English image is available → show the English text (attacks, abilities, effects)

The layout must always be **side-by-side** (JP left, EN right), adapting panel size to the screen — never stacking vertically.
```

with:

```md
**Display priority:**
1. **EN first, JP confirms.** The EN panel is the primary answer; the JP panel exists to confirm the user typed the correct card.
2. If an official English card image is available → show it large (the EN card panel is what you show opponents).
3. If no English image is available → show English translated text. Attack names may be `—` for synthetic cards.

**Layout:**
- **Desktop (≥ 681px):** side-by-side (JP left, arrow, EN right). Current behavior.
- **Mobile (< 681px):** vertical stack, EN on top (full width), compact JP confirmation block below (image-only by default, "Show JP text" reveals attacks). No arrow.
- **JP-fallback merged panel:** when the EN image URL equals the JP image URL (e.g. ME2a ↔ M2a share `megadreamex`), render a single merged panel instead of two.
```

- [ ] **Step 9.2: Add mobile-specifics to Architecture section**

In the Architecture section, after the existing "Data sources" block, add:

```md
**Mobile-first UX:**
- Input section becomes a fixed sticky bottom bar when results are showing (mobile only). Controlled by `.input-section--sticky` class set by `refreshStickyBar()` in `app.js`.
- The sticky bar auto-hides (`.input-section--hidden`) while the EN image is >70% visible, via `IntersectionObserver`.
- Recents chips (`#chipRow`) show the last 5 set IDs searched (localStorage `recentSets`); autocomplete chips replace them while the Set ID input is focused + non-empty.
- Meta rows (HP, stage, illustrator, etc.) hide behind native `<details>` "Show details" toggles. Auto-opened on desktop; collapsed on mobile. `openDetailsOnDesktop()` is called after every render.
```

---

## Task 10: End-to-end verification matrix

Manual verification before commit.

**Files:** none (verification only)

- [ ] **Step 10.1: Desktop viewport (1280×800) — full regression matrix**

Run (with local server + chrome-devtools MCP):

| URL | Expect |
|---|---|
| `?set=M1S&num=001` | Side-by-side, EN image (megaevolution/6.jpg), JP (megasymphonia/1.jpg) |
| `?set=M1L&num=021` | Side-by-side, EN image (megaevolution/*.jpg), Sandslash |
| `?set=M2&num=001`  | Side-by-side, EN image (phantasmalflames/1.jpg), Oddish |
| `?set=M2a&num=001` | Single merged panel (megadreamex image), "Showing Japanese card art" note |
| `?set=SV5a&num=051`| Side-by-side, TCGdex images, Snorlax |
| `?set=M3&num=001` | Side-by-side via sideload, EN image from perfectorder |
| `?set=M4&num=001` | Side-by-side via sideload, EN image from ninjaspinner |
| `?set=xy-m1&num=001` | Error message about missing set |

For each: verify both images load (naturalWidth > 0), no console errors.

- [ ] **Step 10.2: Mobile viewport (375×812) — same matrix**

For each URL: verify EN panel on top, JP compact panel below (except merged case), sticky bottom bar visible, "Show JP text" toggles work, "Show details" toggles work.

- [ ] **Step 10.3: Interaction flows on mobile**

- Clear localStorage (`localStorage.clear()`). Reload `/`. Chip row should be empty (hidden). Do 3 searches (M1S/001, M2/001, M1L/001). Chip row now shows all 3 as recents.
- Focus Set ID, type "m". Chips swap to autocomplete matches (uppercased). Tap a chip — input fills, focus moves to Card #.
- Tap Browse icon in sticky bar → browse grid opens for current set ID.
- Scroll up so EN image is fully in view → sticky bar hides. Scroll down → reappears.
- Click 🔗 share icon → URL copied, icon briefly turns green ✓.

- [ ] **Step 10.4: No console errors**

```
mcp__chrome-devtools__list_console_messages types=["error","warn"]
```
Expected: empty or only expected 404s (if any).

---

## Task 11: Commit and push

- [ ] **Step 11.1: Review the redesign diff**

```bash
cd /home/ec2-user/pokemon-tcg-jp-en-matcher
git diff --stat
```

Expected: `index.html`, `style.css`, `app.js`, `CLAUDE.md` modified. No stray files.

- [ ] **Step 11.2: Verify docs were updated**

Per global rule (docs-before-commit):
- `README.md` — check if it references the old "side-by-side" wording or prev/next buttons. If so, update.
- `CLAUDE.md` — already updated in Task 9.

Run:
```bash
grep -nE "side-by-side|prev/next|Prev/Next|← #|#[0-9]+ →" /home/ec2-user/pokemon-tcg-jp-en-matcher/README.md
```

If matches exist, update accordingly (verbally mention the new layout).

- [ ] **Step 11.3: Commit B (UX redesign)**

```bash
cd /home/ec2-user/pokemon-tcg-jp-en-matcher
git add index.html style.css app.js CLAUDE.md README.md
git commit -m "$(cat <<'EOF'
Mobile-first UX redesign: EN-first stack, sticky input bar, recents chips

Reorient the UI around the "EN is the answer, JP confirms" principle.

Mobile (<681px):
- Vertical stack, EN panel on top (full width image + attacks), compact
  JP image (62% width) below with "Show JP text" toggle for details
- Sticky bottom input bar when results are showing; auto-hides when
  the EN image is >70% in view (IntersectionObserver)
- Browse button collapses to a 📂 icon in the sticky bar

Desktop (≥681px):
- Side-by-side preserved
- Details/meta rows auto-open; share link moves into panel header

Shared:
- Recents chips row (up to 5) under Set ID input, persisted in
  localStorage. Autocomplete chips replace recents while typing.
- Prev/next buttons removed
- Share button becomes a 🔗 icon in the EN panel header
- Meta rows collapse into native <details> "Show details" toggle
- JP-fallback merged panel: single-panel render when EN image URL
  equals JP image URL (e.g. M2a/ME2a both use megadreamex)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 11.4: Push both commits**

```bash
cd /home/ec2-user/pokemon-tcg-jp-en-matcher
git push origin main
```

Expected: both commits (A image fix + B UX redesign) land on `origin/main`. GitHub Pages builds within ~1 minute.

- [ ] **Step 11.5: Cleanup**

```bash
pkill -f "python3 -m http.server 8765" 2>/dev/null || true
```

---

## Self-review notes

Ran after writing:

- **Spec coverage:** Every spec section maps to tasks — §1 layout → Tasks 5, 6; §2 inputs → Tasks 2, 7; §3 rendering → Tasks 3, 5, 6, 8; §4 state → Task 1; §5 CSS → Tasks 2, 3, 5, 6, 7, 8; §6 file structure → respected (no new files); §7 testing → Task 10. Image fix in Task 0 ties in Commit A.
- **Placeholders:** None. All code blocks complete.
- **Type consistency:** `renderCard` signature `(card, lang, badge, score, fallbackImgUrl)` matches across tasks. `assembleResults(jpCard, enCard, mode, badge, score)` matches its usages. `refreshStickyBar`, `renderChipRow`, `openDetailsOnDesktop` all defined and called.
- **Known tradeoff flagged:** single-commit UX redesign is intentional per commit strategy section — avoids broken intermediate states.
