// Pure-logic tests — no network. Covers the regressions we've hit so they
// don't silently come back. If any of these fail, the matcher is broken.

const assert = require('node:assert/strict');
const { loadApp } = require('./load_app');

const ctx = loadApp();

let passed = 0, failed = 0;
function test(name, fn) {
  try {
    fn();
    console.log(`  ok   ${name}`);
    passed++;
  } catch (e) {
    console.log(`  FAIL ${name}`);
    console.log(`       ${e.message}`);
    failed++;
  }
}

console.log('\nPOKEMON_NAME_MAP — sv4a ex regression cards');
const nameFor = (jp) => ctx.pokemonNameFromMap(jp);

const expectations = [
  // sv4a ex (Shiny Treasure) — all 24 unique Pokemon from the "ex" lineup must resolve
  ['フォレトスex', 'Forretress ex'],
  ['マスカーニャex', 'Meowscarada ex'],
  ['リククラゲex', 'Toedscruel ex'],
  ['クエスパトラex', 'Espathra ex'],
  ['チオンジェンex', 'Wo-Chien ex'],
  ['ラウドボーンex', 'Skeledirge ex'],
  ['イーユイex', 'Chi-Yu ex'],
  ['ウェーニバルex', 'Quaquaval ex'],
  ['パオジアンex', 'Chien-Pao ex'],
  ['ミライドンex', 'Miraidon ex'],
  ['フーディンex', 'Alakazam ex'],
  ['ミュウex', 'Mew ex'],
  ['サーナイトex', 'Gardevoir ex'],
  ['キラフロルex', 'Glimmora ex'],
  ['イダイナキバex', 'Great Tusk ex'],
  ['ディンルーex', 'Ting-Lu ex'],
  ['コライドンex', 'Koraidon ex'],
  ['リザードンex', 'Charizard ex'],
  ['テツノワダチex', 'Iron Treads ex'],
  ['オンバーンex', 'Noivern ex'],
  ['ピジョットex', 'Pidgeot ex'],
  ['プクリンex', 'Wigglytuff ex'],
  ['イキリンコex', 'Squawkabilly ex'],
  // Leading form prefix (was the tricky one)
  ['パルデア ドオーex', 'Paldean Clodsire ex'],
  // Trailing form suffix (must still work)
  ['オーガポン みどりのめん', 'Teal Mask Ogerpon'],
  ['ガチグマ アカツキ', 'Bloodmoon Ursaluna'],
  // Plain names without ex/form
  ['ピカチュウ', 'Pikachu'],
  ['ドラパルト', 'Dragapult'],
  // Unknown names must return null (don't fabricate)
  ['知らないポケモン', null],
];

for (const [jp, en] of expectations) {
  test(`${jp} → ${en === null ? 'null' : en}`, () => {
    assert.equal(nameFor(jp), en);
  });
}

console.log('\nTRAINER_NAME_MAP via trainerNameFromMap (if exposed)');
// TRAINER_NAME_MAP is a module-scoped const (not a function) so it's not
// visible in the vm context. We assert it's wired up correctly by running
// a script that exercises it. Skip if app.js doesn't expose a hook.
if (typeof ctx.TRAINER_NAME_MAP !== 'undefined') {
  const trainerCases = [
    ['ボスの指令', "Boss's Orders"],
    ['ナンジャモ', 'Iono'],
    ['博士の研究', "Professor's Research"],
    ['ハイパーボール', 'Ultra Ball'],
    ['ダブルターボエネルギー', 'Double Turbo Energy'],
  ];
  for (const [jp, en] of trainerCases) {
    test(`${jp} → ${en}`, () => {
      assert.equal(ctx.TRAINER_NAME_MAP[jp], en);
    });
  }
} else {
  console.log('  skip (TRAINER_NAME_MAP not exposed as a global — rely on integration tests)');
}

console.log('\nSEREBII_SLUGS — image URL resolution');
test('M1S-001 resolves to megasymphonia', () => {
  assert.equal(ctx.sideloadImageUrl({ id: 'M1S-001' }), 'https://www.serebii.net/card/megasymphonia/1.jpg');
});
test('ME1-006 resolves to megaevolution/6', () => {
  assert.equal(ctx.sideloadImageUrl({ id: 'ME1-006' }), 'https://www.serebii.net/card/megaevolution/6.jpg');
});
test('M2-001 resolves to infernox', () => {
  assert.equal(ctx.sideloadImageUrl({ id: 'M2-001' }), 'https://www.serebii.net/card/infernox/1.jpg');
});
test('Unknown prefix returns null', () => {
  assert.equal(ctx.sideloadImageUrl({ id: 'XYZ-001' }), null);
});
test('Invalid id returns null', () => {
  assert.equal(ctx.sideloadImageUrl({ id: 'bogus' }), null);
  assert.equal(ctx.sideloadImageUrl({}), null);
});

console.log('\ncardImageUrl — prefers card.image over Serebii fallback');
test('card with full url', () => {
  assert.equal(ctx.cardImageUrl({ id: 'X-1', image: 'https://cdn.example.com/x.webp' }),
    'https://cdn.example.com/x.webp');
});
test('card with TCGdex-style base url appends /high.webp', () => {
  assert.equal(ctx.cardImageUrl({ id: 'sv10-003', image: 'https://assets.tcgdex.net/en/sv/sv10/003' }),
    'https://assets.tcgdex.net/en/sv/sv10/003/high.webp');
});
test('card without image falls back to Serebii slug', () => {
  assert.equal(ctx.cardImageUrl({ id: 'M1S-001', image: null }),
    'https://www.serebii.net/card/megasymphonia/1.jpg');
});
test('card without image and unmapped prefix returns null', () => {
  assert.equal(ctx.cardImageUrl({ id: 'XY-001', image: null }), null);
});

console.log('\nmatchScore — dexId + illustrator match scores high');
test('identical Pokemon scores > 60', () => {
  const jp = { category: 'Pokemon', hp: 160, types: ['Colorless'], illustrator: 'Artist', attacks: [{ damage: 120, cost: ['Colorless','Colorless'] }] };
  const en = { category: 'Pokemon', hp: 160, types: ['Colorless'], illustrator: 'Artist', attacks: [{ damage: 120, cost: ['Colorless','Colorless'] }] };
  const r = ctx.matchScore(jp, en);
  assert.ok(r.score > 60, `expected >60, got ${r.score}`);
});
test('Trainer vs Pokemon → score 0 (hard mismatch)', () => {
  const jp = { category: 'Pokemon' };
  const en = { category: 'Trainer' };
  const r = ctx.matchScore(jp, en);
  assert.equal(r.score, 0);
});

console.log('\nLIMITLESS_SET_MAP — link building');
// Access limitlessLinkFor indirectly via the sandbox
test('sv06-136 → TWM/136', () => {
  const url = ctx.limitlessLinkFor({ id: 'sv06-136' });
  assert.equal(url, 'https://limitlesstcg.com/cards/TWM/136');
});
test('sv10-003 → DRI/3', () => {
  const url = ctx.limitlessLinkFor({ id: 'sv10-003' });
  assert.equal(url, 'https://limitlesstcg.com/cards/DRI/3');
});
test('ME1-006 (machine-translated) returns null', () => {
  assert.equal(ctx.limitlessLinkFor({ id: 'ME1-006' }), null);
});
test('Unmapped set returns null (no broken 404 links)', () => {
  assert.equal(ctx.limitlessLinkFor({ id: 'unknownset-001' }), null);
});

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
