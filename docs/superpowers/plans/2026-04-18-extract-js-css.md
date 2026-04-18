# Extract JS and CSS from index.html Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Split `index.html` into three files — `style.css`, `app.js`, and a clean HTML skeleton — so the JS is parseable by CodeGraph and all three files are independently navigable.

**Architecture:** Purely mechanical extraction. Copy the `<style>` block verbatim into `style.css` and the `<script>` block verbatim into `app.js`. Replace both blocks in `index.html` with `<link>` and `<script src>` tags. No logic changes.

**Tech Stack:** Vanilla HTML/CSS/JS, GitHub Pages static hosting.

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `style.css` | All CSS (verbatim from `<style>` block, lines 13–450 of `index.html`) |
| Create | `app.js` | All JS (verbatim from `<script>` block, lines 511–1417 of `index.html`) |
| Modify | `index.html` | HTML skeleton only; add `<link>` and `<script src>` tags |

---

### Task 1: Create `style.css`

**Files:**
- Create: `style.css`
- Modify: `index.html`

- [x] **Step 1: Create `style.css` with the extracted CSS**

  Create `/home/ec2-user/pokemon-tcg-jp-en-matcher/style.css` containing exactly the contents of the `<style>` block from `index.html` (lines 14–449, i.e. everything between `<style>` and `</style>`, not including those tags themselves).

  The file should start with:
  ```css
  /* ── Reset & CSS variables ─────────────────────────────── */
  :root {
    --gold: #ffd700;
  ```
  and end with:
  ```css
    }
  }
  ```

- [x] **Step 2: Replace `<style>` block in `index.html` with a `<link>` tag**

  In `index.html`, replace:
  ```html
    <style>
      /* ── Reset & CSS variables ─────────────────────────────── */
      ...
    </style>
  ```
  with:
  ```html
    <link rel="stylesheet" href="style.css">
  ```
  (Place it where the `<style>` block was, after the Google Fonts `<link>` tag.)

- [x] **Step 3: Verify the CSS extracted correctly**

  Run:
  ```bash
  wc -l style.css
  ```
  Expected: ~437 lines (the `<style>` block was lines 13–450 of the original file).

  Also verify `index.html` no longer contains `<style>`:
  ```bash
  grep -c '<style>' index.html
  ```
  Expected: `0`

- [x] **Step 4: Commit**

  ```bash
  git add style.css index.html
  git commit -m "Extract CSS into style.css"
  ```

---

### Task 2: Create `app.js`

**Files:**
- Create: `app.js`
- Modify: `index.html`

- [x] **Step 1: Create `app.js` with the extracted JavaScript**

  Create `/home/ec2-user/pokemon-tcg-jp-en-matcher/app.js` containing exactly the contents of the `<script>` block from `index.html` (everything between `<script>` and `</script>`, not including those tags themselves).

  The file should start with:
  ```js
  const API = 'https://api.tcgdex.net/v2';
  ```
  and end with:
  ```js
    navigator.serviceWorker.register('./sw.js').catch(() => {});
  }
  ```

- [x] **Step 2: Replace `<script>` block in `index.html` with a `<script src>` tag**

  In `index.html`, replace:
  ```html
    <script>
      const API = 'https://api.tcgdex.net/v2';
      ...
    </script>
  ```
  with:
  ```html
    <script src="app.js"></script>
  ```
  (Place it in the same position, just before `</body>`.)

- [x] **Step 3: Verify the JS extracted correctly**

  Run:
  ```bash
  wc -l app.js
  ```
  Expected: ~907 lines (the `<script>` block was lines 511–1417 of the original file).

  Also verify `index.html` no longer contains `<script>` content:
  ```bash
  grep -c 'const API' index.html
  ```
  Expected: `0`

  And verify `app.js` has it:
  ```bash
  grep -c 'const API' app.js
  ```
  Expected: `1`

- [x] **Step 4: Verify `index.html` is now a clean skeleton**

  Run:
  ```bash
  wc -l index.html
  ```
  Expected: ~75 lines.

- [x] **Step 5: Commit**

  ```bash
  git add app.js index.html
  git commit -m "Extract JS into app.js"
  ```

---

### Task 3: Smoke-test and re-index CodeGraph

**Files:**
- No file changes

- [x] **Step 1: Verify the three files exist at the repo root**

  ```bash
  ls -la index.html style.css app.js
  ```
  Expected: all three files present.

- [x] **Step 2: Verify no inline `<style>` or `<script>` blocks remain in `index.html`**

  ```bash
  grep -n '<style\|<script' index.html
  ```
  Expected: one line only — `<script src="app.js"></script>`. No `<style>` lines, no inline `<script>` blocks.

- [x] **Step 3: Re-index CodeGraph**

  ```bash
  codegraph index
  ```
  Expected: output includes `app.js` with a non-trivial symbol count (50+ symbols).

- [x] **Step 4: Verify CodeGraph sees `app.js`**

  Use the `codegraph_files` tool (or run `codegraph_search` for a known symbol like `doSearch`). Confirm `app.js` appears in the index with functions like `doSearch`, `renderCard`, `matchScore`, `browseSet`, `loadSideloadData`.

- [x] **Step 5: Commit (if any index files changed)**

  ```bash
  git add .codegraph/
  git commit -m "Re-index CodeGraph after JS/CSS extraction"
  ```
