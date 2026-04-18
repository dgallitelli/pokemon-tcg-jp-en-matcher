# Extract JS and CSS from index.html

**Date:** 2026-04-18  
**Status:** Approved

## Goal

Split `index.html` into three files so that the JavaScript logic is parseable by CodeGraph and all three files are easier to navigate and edit independently.

## Files produced

| File | Contents | Lines (approx) |
|---|---|---|
| `index.html` | HTML skeleton only: DOCTYPE, head, body structure, link/script tags | ~70 |
| `style.css` | Verbatim contents of the `<style>` block | ~450 |
| `app.js` | Verbatim contents of the `<script>` block | ~900 |

## Changes to `index.html`

- Remove `<style>...</style>` block; replace with `<link rel="stylesheet" href="style.css">` in `<head>`
- Remove `<script>...</script>` block; replace with `<script src="app.js"></script>` just before `</body>`
- Everything else (meta tags, font preconnects, preconnect to tcgdex/assets, HTML structure) stays unchanged

## No logic changes

This is a mechanical extraction only. No JavaScript is modified, renamed, or restructured. No CSS is modified. Behavior is identical before and after.

## GitHub Pages compatibility

GitHub Pages serves `.css` and `.js` files with correct MIME types automatically. No extra config needed. The existing service worker (`sw.js`) caches `./` (the HTML page) only — it does not reference `app.js` or `style.css`, so those files will be fetched fresh from the network on every load. This is acceptable and unchanged from current behavior.

## Out of scope

- Splitting JS into ES modules (deferred to a future refactor)
- Splitting CSS into component files
- Any logic changes to the JS
- Updating the service worker to cache `app.js` or `style.css`
