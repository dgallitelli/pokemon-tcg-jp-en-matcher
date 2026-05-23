# Agent development guide

This file captures the development conventions for this repo. Applies to any
AI coding agent (Claude Code, Copilot CLI, Codex, Gemini) or human working
with one.

## Project at a glance

Mobile-first static site matching Japanese Pokémon TCG cards with their
English equivalents. Single `index.html` + `style.css` + `app.js`, zero build
step, deployed to GitHub Pages. JP sideloads in `data/M*.json`, EN
translation sideloads in `data/ME*.json`, live TCGdex API for standard sets.

See `CLAUDE.md` (project-scoped, not tracked) for the display priority,
layout invariants, and data pipeline details.

## Rendering pipeline

Both online (TCGdex API) and sideload (`data/M*.json`, `data/ME*.json`)
cards flow through the **same** render path. Only the image-URL resolution
differs by source.

### Image URL resolution — `cardImageUrl()` (app.js:192)

Order of precedence:

1. **`card.image` field** → if present, use it. TCGdex returns a base path,
   so we append `/high.webp` unless `card.image` already has an extension.
   ME2a sideload cards have a full `assets.tcgdex.net/...` URL baked into
   `card.image` at build time (`scripts/generate_tcgdex_m2a.py`).
2. **`sideloadImageUrl()` Serebii slug** (app.js:182) → for cards
   without `card.image`, derive
   `https://www.serebii.net/card/<slug>/<num>.jpg` from the set
   prefix via the `SEREBII_SLUGS` constant (app.js:169).

Net effect: live lookups use the **TCGdex CDN**, ME1/ME2/ME3/ME4 sideloads
use **Serebii**, ME2a uses **TCGdex** (pre-baked).

### Text rendering — single funnel via `renderCard()` (app.js:260)

`renderCard(card, lang, badge, score, fallbackImgUrl)` walks `card.attacks`
and `card.abilities` arrays identically regardless of source. Sideload
cards arrive with that shape because the data pipeline (Serebii scrape →
TCGdex backfill → `normalize_data.py`) populates them. Synthetic EN cards
keep attack `name = '—'` so the dash renders verbatim. `isEnglish()`
rejects any text containing JP unicode (U+3040–9FFF) before it reaches the
EN panel.

### Image-load fallback — JP image rescues a missing EN image

The 5th arg to `renderCard` is the fallback URL. The `<img>` always tries
its own resolved URL first; on `onerror` (e.g. Serebii 404 for a card not
yet up), an inline handler swaps `src` to `fallbackImgUrl`, adds the
`.jp-fallback` dashed-outline class, and reveals the "Showing Japanese
card" hint. If both fail, the 🃏 placeholder shows. `assembleResults`
(app.js:380) passes `cardImageUrl(jpCard)` as the fallback for the EN
panel.

### Layout decision — `assembleResults()` (app.js:380)

Three branches, in order:

| Condition | Output |
|-----------|--------|
| `cardImageUrl(jpCard) === cardImageUrl(enCard)` | Single **merged panel** (e.g. ME2a/M2a both resolve to `megadreamex` Serebii slug) |
| Mobile (`max-width: 680px`) | **Vertical stack:** full `renderCard` for EN on top, `renderCardCompactJp` (image-only, "Show JP text" toggle) below |
| Desktop | **Side-by-side:** `renderCard(jpCard)` → arrow → `renderCard(enCard)` |

### When you change rendering, preserve these guarantees

- EN-first ordering on mobile. EN panel always above the compact JP block.
- JP image only appears in the EN slot via `onerror` fallback, and only
  when visually marked with `.jp-fallback` + the hint.
- Adding a new sideload set: register its Serebii slug in `SEREBII_SLUGS`
  *or* bake an absolute URL into `card.image` at build time. Don't add a
  third resolution path.
- Don't bypass `renderCard` — anything that adds image+text rendering
  somewhere else duplicates the fallback logic and the `isEnglish()` guard.

## The iron rules

1. **Opus-level reasoning for code changes.** Any change touching matching
   logic, data flow, or the mobile/desktop layout MUST be made with a model
   at Opus capability (currently `claude-opus-4-7`). Cheaper/faster models
   are fine for typo fixes or copy changes, not for behavior.
2. **Never commit directly to `main`.** Every change goes through a PR.
3. **Tests gate the merge.** The CI workflow at `.github/workflows/test.yml`
   must be green before merging. `pages.yml` is also gated on tests via
   `needs: test` — a failing matcher cannot reach production. **Wait for CI
   to complete before merging** — no merging "optimistically" while checks
   are still pending, even if local runs pass. See the *Waiting for CI*
   section below.
4. **Every behavioral fix adds a test.** When you fix a bug, add a case to
   `tests/test_matcher.js` or `tests/test_tcgdex.js` so the same regression
   can't silently come back.
5. **Agent/dev artifacts stay out of the repo.** `CLAUDE.md`, `AGENTS.md`,
   `docs/superpowers/`, `.codegraph/`, and anything under `.claude/` are
   gitignored. Do not commit them.

## Branching + PR workflow

```
          main (always green, always deployable)
            ↑
            | PR with passing tests
            |
       feat/<short-name>   (your working branch)
```

### Standard flow

```bash
# 1. Start from an up-to-date main
git checkout main && git pull --ff-only

# 2. Branch for the change. Name it feat/<kebab-case> or fix/<kebab-case>.
git checkout -b fix/sv4a-missing-dex-ids

# 3. Make changes. For non-trivial work, use subagent-driven development:
#    - Spawn an Explore/general-purpose subagent to investigate and report
#    - Review the report, decide on the fix yourself (don't delegate
#      understanding), then implement
#    - If the change touches UI, verify locally with chrome-devtools MCP
#      before committing
git add -p && git commit -m "Fix X by Y"

# 4. Run tests locally before pushing.
node tests/test_matcher.js && node tests/test_tcgdex.js

# 5. Push the branch.
git push -u origin fix/sv4a-missing-dex-ids

# 6. Open the PR. GitHub Actions runs tests automatically on PR open/update.
gh pr create --fill --base main

# 7. WAIT for CI to finish. Do not merge while checks are pending.
#    Either poll:
gh pr checks --watch            # blocks until all checks finish
#    Or script it (handy from an agent):
while :; do
  status=$(gh pr checks --json state --jq '[.[].state] | unique | join(",")')
  case "$status" in
    *PENDING*|*IN_PROGRESS*|*QUEUED*) sleep 10 ;;
    *FAILURE*|*CANCELLED*|*TIMED_OUT*) echo "CI failed: $status"; exit 1 ;;
    *) echo "CI status: $status"; break ;;
  esac
done

# 8. Only after the required `test` check reports SUCCESS, merge.
#    Non-gating checks (e.g. optional bots, code-review advisories) do
#    not need to pass — just the required workflows. Prefer squash-merge
#    for a clean main history.
gh pr merge --squash --delete-branch

# 9. Pages deploys automatically from main. The deploy workflow re-runs
#    tests as a final gate via `needs: test`, so a broken merge is blocked
#    before going live. After merging, verify the deploy:
gh run list --workflow=pages.yml --limit 1
#    Wait for the deploy run to complete with status=success before
#    considering the change shipped.
```

### Commits

- Imperative mood, one-sentence subject, blank line, then a paragraph
  explaining the *why*.
- Co-author trailer for AI-assisted commits:
  ```
  Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
  ```
- Never use `--amend` on already-pushed commits. Never force-push `main`.

### Waiting for CI

The whole point of the test gate is that it runs in the real CI
environment, not just locally. Local tests pass != CI will pass (Node
version mismatch, path differences, network flakes on the integration
suite, etc.). Always wait.

**Agent rule of thumb:** after `git push` or `gh pr create`, the next
command is `gh pr checks --watch` (or the polling loop above). Do not
invoke `gh pr merge` until the required checks are `SUCCESS`. Do not rely
on "it'll be fine, the diff is tiny."

If CI fails: inspect with `gh run view --log-failed`, push a fix to the
same branch (CI re-runs automatically on each push to the PR), wait
again, then merge.

**Verifying deployment after merge:** `gh run list --workflow=pages.yml
--limit 1` should show `success` within a minute or two of the merge.
If it's still in progress, wait for it before claiming the change is
live.

### What NOT to do

- Don't push straight to `main`.
- Don't merge with red or *pending* CI. Pending is not green.
- Don't bypass hooks (`--no-verify`).
- Don't skip the subagent-driven review step for non-trivial changes. Cheap
  edits are fine inline; anything that might touch correctness isn't.
- Don't claim a change is "deployed" until the `pages.yml` run shows
  `success` on `main`.

## Subagent-driven development

**When to spawn a subagent:**

- Open-ended investigation (e.g. "what could cause X to mismatch Y?")
- Cross-file refactoring that would blow the main context with reads
- Parallel independent tasks (e.g. investigate two bugs at once)
- Testing deployed behavior via chrome-devtools MCP without polluting main
  session context with hundreds of snapshot lines

**How to dispatch:**

- Use the parent agent's `Agent` tool (Claude Code: `subagent_type`).
- Brief the subagent like it walked into the room cold: state the goal,
  what's already known, what files/URLs matter, expected output format
  (e.g. "report in under 500 words, include file:line references").
- Subagents cannot commit or push. They report back; the parent agent
  synthesizes and acts on the findings.

**Anti-pattern — never delegate understanding.** Don't write "based on your
findings, fix the bug." Read the report, decide what to do, include
concrete file paths and line numbers in your implementation prompts.

## Testing

- **Unit tests** (`tests/test_matcher.js`) — no network. Run locally or in
  CI with `node tests/test_matcher.js`. Tests the JP→EN name resolution,
  form prefix/suffix parsing, image URL construction, match scoring,
  Limitless link building.
- **Integration tests** (`tests/test_tcgdex.js`) — hits live TCGdex API.
  Run with `node tests/test_tcgdex.js`. Gracefully skips if offline.
- **Visual** — `python3 -m http.server 8765` + chrome-devtools MCP. For UI
  changes, test iPhone 13 viewport (390×844) in particular — the EN-first
  stack and details-toggle behavior are mobile-only.

### Adding a test for a bug you fixed

Every fix commit should add at least one test. Example pattern from the
sv4a ex regression:

```js
// tests/test_matcher.js
const expectations = [
  // ... existing entries ...
  ['マスカーニャex', 'Meowscarada ex'],   // sv4a ex without dexId
  ['パルデア ドオーex', 'Paldean Clodsire ex'],  // leading form prefix
];
```

And if the bug can only be caught by end-to-end name resolution through
TCGdex, add an integration-test case:

```js
// tests/test_tcgdex.js
const CASES = [
  // ... existing entries ...
  ['SV4a', '321', 'Meowscarada ex', 'sv4a ex card without dexId'],
];
```

## CI/CD

- **`.github/workflows/test.yml`** — runs on every push to any branch and
  every PR. Runs both test suites.
- **`.github/workflows/pages.yml`** — runs on push to `main`. Gated on a
  test job (`needs: test`), then deploys to GitHub Pages. So a failing test
  blocks both PR merge and production deploy.
- **No preview deploys.** Trust the tests + local visual review. If you
  find yourself shipping broken UX, revisit this decision.

## Data pipeline

Scripts under `scripts/` regenerate the sideload JSON files. Run manually
when a new JP set releases (see `CLAUDE.md` for the full sequence). Do not
add generated sideloads to CI — their scrapers hit external sites and
aren't deterministic.

## Tracking upstream TCGdex updates

TCGdex is the authoritative source for both live lookups (`api.tcgdex.net/v2`)
and our ME2a/ME4 sideload builds. When their dataset changes, our matcher
behavior can change too — especially when they add `dexId` fields, new JP
sets, or `evolveFrom` data we previously had to fill in ourselves.

**Watch (in priority order):**

1. **GitHub releases (semver-tagged, most authoritative)**
   - Page: <https://github.com/tcgdex/cards-database/releases>
   - Atom feed: <https://github.com/tcgdex/cards-database/releases.atom>
   - Subscribe a feed reader to the Atom URL. Each tag's body lists merged
     PRs grouped under "What's Changed". Recent examples worth knowing
     about: **v2.44.0** (added the `dexId` field to cards generically —
     directly affects our ex-name matcher), **v2.40.0** (added SV11W JP),
     **v2.45.0** (backfilled missing `dexId`s for `me03` = our M3/ME3).
2. **Master commits feed** (catches additions before a release tag)
   - <https://github.com/tcgdex/cards-database/commits/master.atom>
3. **Discord** (TCGdex's primary community channel, often hears about new
   sets first): <https://tcgdex.dev/discord>
4. **Status page** (per-language / per-set completeness, useful for
   answering "is M5 in TCGdex yet?" — cf. `docs/m5-launch-notes.md`):
   <https://tcgdex.dev/status>

**When a release lands, ask:**

- Does it add a JP set we sideload (or could now stop sideloading)?
  → Update `SIDELOAD_JP_CONFIG` / `JP_TO_EN_SIDELOAD` / `LIMITLESS_SET_MAP`
  in `app.js`.
- Does it backfill `dexId`s for cards we currently match by name only?
  → Re-run `fetch_tcgdex_en.py` and `normalize_data.py`; add a regression
  test for any newly-matchable card.
- Does it touch a set we already pin (e.g. ME2a / sv10)?
  → Re-run `generate_tcgdex_m2a.py` so our pre-baked image URLs and
  attack text stay in sync.
