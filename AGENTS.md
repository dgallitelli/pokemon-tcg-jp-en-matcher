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
  changes, test iPhone 13 viewport (390×844) in particular — the sticky
  bottom bar, EN-first stack, and details-toggle behavior are mobile-only.

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
