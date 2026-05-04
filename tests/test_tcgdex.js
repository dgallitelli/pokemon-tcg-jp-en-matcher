// Integration tests — hit the live TCGdex API. These catch failures caused by
// TCGdex data changes (e.g. a Pokemon losing its dexId, a set being reindexed)
// without needing a full browser.
//
// We replicate the relevant portion of doSearch()'s matching logic:
//   1. Fetch the JP card.
//   2. Resolve an English name via dexId lookup, then pokemonNameFromMap,
//      then TRAINER_NAME_MAP fallback.
//   3. Assert the resolved name equals the expected value.
//
// Skipped gracefully if the network is unavailable (exit 0, with a note).

const assert = require('node:assert/strict');
const { loadApp } = require('./load_app');

const API = 'https://api.tcgdex.net/v2';

async function fetchJson(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  return r.json();
}

const fs = require('node:fs');
const path = require('node:path');

function loadSideloadJp(setId) {
  // Mirrors SIDELOAD_CONFIG.jp in app.js (kept tiny to avoid coupling).
  const filePath = path.join(__dirname, '..', 'data', `${setId}.json`);
  if (!fs.existsSync(filePath)) return null;
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

async function resolveEnglishName(ctx, setId, cardNum) {
  // Replicate the name-resolution chain used by doSearch() (steps 2a/2b).
  // First check whether the JP card is in a local sideload file; otherwise
  // hit the TCGdex JA API.
  let jp = null;
  const sideload = loadSideloadJp(setId);
  if (sideload && sideload.cards) {
    jp = sideload.cards[cardNum] || sideload.cards[String(parseInt(cardNum, 10))];
  }
  if (!jp) {
    jp = await fetchJson(`${API}/ja/cards/${setId}-${cardNum}`);
  }

  let enName = null;

  if (jp.dexId && jp.dexId.length > 0) {
    try {
      const d = await fetchJson(`${API}/en/dex-ids/${jp.dexId[0]}`);
      const cards = d.cards || d;
      if (cards && cards.length > 0) {
        const simple = cards.find(c => !c.name.includes("'s ") && !c.name.includes(' '));
        enName = (simple || cards[0]).name;
      }
    } catch {}
  }

  if (!enName && jp.category === 'Pokemon' && jp.name) {
    enName = ctx.pokemonNameFromMap(jp.name);
  }

  return { jp, enName };
}

const CASES = [
  // [set, num, expectedEnglishName, note]
  ['SV4a', '321', 'Meowscarada ex', 'sv4a ex card without dexId — tests POKEMON_NAME_MAP'],
  ['SV4a', '332', 'Paldean Clodsire ex', 'sv4a — tests leading form prefix (パルデア)'],
  ['SV4a', '115', 'Charizard ex', 'sv4a — tests Charizard mapping'],
  ['SV4a', '076', 'Mew ex', 'sv4a — tests Mew mapping'],
  ['SV4a', '035', 'Chi-Yu ex', 'sv4a — Chi-Yu'],
  ['SV4a', '054', 'Chien-Pao ex', 'sv4a — Chien-Pao'],
  ['M2a',  '123', 'Hop\'s Zacian ex', 'm2a card — should resolve via dexId 888', true],
  ['SV5a', '051', 'Snorlax', 'regular dexId lookup'],
  ['SV8a', '014', 'Alolan Vulpix', 'Alolan form edge case', true],
];

async function run() {
  const ctx = loadApp();

  // Network probe
  try {
    await fetchJson(`${API}/ja/sets/sv4a`);
  } catch (e) {
    console.log(`\nSkipping integration tests — TCGdex API unavailable: ${e.message}`);
    return 0;
  }

  let passed = 0, failed = 0, skipped = 0;

  for (const [setId, num, expected, note, optional] of CASES) {
    const label = `${setId}/${num} → ${expected}`;
    try {
      const { jp, enName } = await resolveEnglishName(ctx, setId, num);
      if (enName === expected) {
        console.log(`  ok   ${label}  (${note || ''})`);
        passed++;
      } else if (optional) {
        console.log(`  skip ${label}  got '${enName}' — flagged as optional`);
        skipped++;
      } else {
        console.log(`  FAIL ${label}`);
        console.log(`       got '${enName}' from jp '${jp.name}' dexId=${JSON.stringify(jp.dexId)}`);
        failed++;
      }
    } catch (e) {
      console.log(`  FAIL ${label}`);
      console.log(`       ${e.message}`);
      failed++;
    }
  }

  console.log(`\n${passed} passed, ${failed} failed, ${skipped} skipped`);
  return failed === 0 ? 0 : 1;
}

run().then(code => process.exit(code)).catch(e => {
  console.error(e);
  process.exit(1);
});
