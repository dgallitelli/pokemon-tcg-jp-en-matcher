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
  // sv10 Destined Rivals ex cards (Pokemon without dexId in TCGdex JA)
  ['オリーヴァex', 'Arboliva ex'],
  ['ハルクジラex', 'Cetitan ex'],
  ['レジロックex', 'Regirock ex'],
  // sv10 Team Rocket's Pokemon (JP-prefix pattern "ロケット団の<Pokemon>ex")
  ['ロケット団のファイヤーex', "Team Rocket's Moltres ex"],
  ['ロケット団のミュウツーex', "Team Rocket's Mewtwo ex"],
  ['ロケット団のニドキングex', "Team Rocket's Nidoking ex"],
  ['ロケット団のクロバットex', "Team Rocket's Crobat ex"],
  ['ロケット団のペルシアンex', "Team Rocket's Persian ex"],
  // Other trainer-owned Pokemon patterns
  ['ホップのザシアンex', "Hop's Zacian ex"],
  ['ヒビキのカイロスex', "Ethan's Pinsir ex"],
  // Unknown names must return null (don't fabricate)
  ['知らないポケモン', null],
];

for (const [jp, en] of expectations) {
  test(`${jp} → ${en === null ? 'null' : en}`, () => {
    assert.equal(nameFor(jp), en);
  });
}

console.log('\nTRAINER_NAME_MAP coverage — spot-check presence via app.js source');
// TRAINER_NAME_MAP is a module-scoped const (not visible in vm context).
// Grep the source instead so missing entries fail loudly without a full integration run.
const fs = require('node:fs');
const appSrc = fs.readFileSync(require('node:path').join(__dirname, '..', 'app.js'), 'utf8');
const trainerCases = [
  ['ボスの指令', "Boss's Orders"],
  ['ナンジャモ', 'Iono'],
  ['博士の研究', "Professor's Research"],
  ['ハイパーボール', 'Ultra Ball'],
  ['ダブルターボエネルギー', 'Double Turbo Energy'],
  // sv10 Destined Rivals — Team Rocket trainers
  ['ロケット団のアテナ', "Team Rocket's Ariana"],
  ['ロケット団のアポロ', "Team Rocket's Archer"],
  ['ロケット団のサカキ', "Team Rocket's Giovanni"],
  ['ロケット団のラムダ', "Team Rocket's Petrel"],
  ['ロケット団のランス', "Team Rocket's Proton"],
  ['ロケット団のおじゃまロボ', "Team Rocket's Bother-Bot"],
  ['ロケット団のスーパーボール', "Team Rocket's Great Ball"],
  ['ロケット団のびっくりボム', "Team Rocket's Venture Bomb"],
  ['ロケット団のレシーバー', "Team Rocket's Transceiver"],
  ['ロケット団の監視塔', "Team Rocket's Watchtower"],
  ['ロケット団のファクトリー', "Team Rocket's Factory"],
  ['ロケット団エネルギー', "Team Rocket's Energy"],
  // sv1v Violet ex — trainers fetched live from TCGdex JP, exact name match required
  ['ミモザ', 'Miriam'],
  ['テーブルシティ', 'Mesagoza'],
  ['エレキジェネレーター', 'Electric Generator'],
  ['ピクニックバスケット', 'Picnic Basket'],
  ['ゴツゴツメット', 'Rocky Helmet'],
  ['博士の研究（フトゥー博士）', "Professor's Research"],
  // SV6a Night Wanderer — secret-rare / set-exclusive trainers
  ['カシオペア', 'Cassiopeia'],
  ['クセロシキのたくらみ', "Xerosic's Machinations"],
  ['デンジャラス光線', 'Dangerous Laser'],
  ['ポケバイタルA', 'Poké Vital A'],
  ['力の砂時計', 'Powerglass'],
  ['夜のアカデミー', 'Academy at Night'],
];
for (const [jp, en] of trainerCases) {
  test(`${jp} → ${en}`, () => {
    // Look for a line like:  'ぼすのしれい': "Boss's Orders",
    const pattern = new RegExp(
      `['"\`]${jp.replace(/[-/\\^$*+?.()|[\]{}]/g, '\\$&')}['"\`]\\s*:\\s*['"\`]${en.replace(/'/g, "'").replace(/[-/\\^$*+?.()|[\]{}]/g, '\\$&')}`
    );
    assert.match(appSrc, pattern);
  });
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
test('SV6a-001 resolves to nightwanderer/1', () => {
  assert.equal(ctx.sideloadImageUrl({ id: 'SV6a-001' }), 'https://www.serebii.net/card/nightwanderer/1.jpg');
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

// ME4 → CRI (Chaos Rising). PokeBeach pre-release numbering diverges from the
// official EN print at position 48 (Mega Gallade ex inserted), so cards 048+
// shift by +1 on Limitless.
test('ME4-001 → CRI/1 (no shift below 48)', () => {
  assert.equal(ctx.limitlessLinkFor({ id: 'ME4-001' }), 'https://limitlesstcg.com/cards/CRI/1');
});
test('ME4-047 → CRI/47 (last unshifted card)', () => {
  assert.equal(ctx.limitlessLinkFor({ id: 'ME4-047' }), 'https://limitlesstcg.com/cards/CRI/47');
});
test('ME4-048 → CRI/49 (shift starts at 48)', () => {
  assert.equal(ctx.limitlessLinkFor({ id: 'ME4-048' }), 'https://limitlesstcg.com/cards/CRI/49');
});
test('ME4-050 (Crobat) → CRI/51', () => {
  // PokeBeach numbered Crobat 050; official EN puts Crobat at 051.
  assert.equal(ctx.limitlessLinkFor({ id: 'ME4-050' }), 'https://limitlesstcg.com/cards/CRI/51');
});
test('ME4-083 → CRI/84 (last mainline)', () => {
  assert.equal(ctx.limitlessLinkFor({ id: 'ME4-083' }), 'https://limitlesstcg.com/cards/CRI/84');
});

console.log('\nrenderEffect — energy tokens like {G}/{R} render as badges, not literals');
test('single {G} token is replaced with a Grass energy badge', () => {
  const out = ctx.renderEffect('Search your deck for a Basic {G} Energy card.');
  assert.ok(!out.includes('{G}'), `output still contains literal {G}: ${out}`);
  assert.ok(/energy-badge/.test(out), `output missing energy-badge span: ${out}`);
  assert.ok(/Grass|#78C850/i.test(out), `output not coloured/labelled as Grass: ${out}`);
});
test('multiple distinct tokens are each replaced', () => {
  const out = ctx.renderEffect('Discard 1 {R} and 2 {W} Energy from this Pokémon.');
  assert.ok(!/\{[A-Z]\}/.test(out), `output still contains a token: ${out}`);
  // two badge spans expected
  const badges = out.match(/energy-badge/g) || [];
  assert.equal(badges.length, 2, `expected 2 badges, got ${badges.length}: ${out}`);
});
test('effect with no tokens is HTML-escaped but otherwise unchanged', () => {
  const out = ctx.renderEffect('Heal 30 damage from this Pokémon.');
  assert.equal(out, 'Heal 30 damage from this Pokémon.');
});
test('HTML in surrounding text is escaped (no XSS)', () => {
  const out = ctx.renderEffect('Attach a {G} <img src=x onerror=alert(1)>');
  assert.ok(!out.includes('<img'), `raw <img tag leaked through: ${out}`);
  assert.ok(out.includes('&lt;img'), `expected escaped <img, got: ${out}`);
  assert.ok(/energy-badge/.test(out), `token still rendered: ${out}`);
});
test('null/undefined effect returns empty string', () => {
  assert.equal(ctx.renderEffect(null), '');
  assert.equal(ctx.renderEffect(undefined), '');
});
test('unknown token like {X} is left untouched (escaped)', () => {
  // Defensive: TCGdex could introduce a new code we don't know yet.
  // Better to leave it as literal escaped text than silently drop it.
  const out = ctx.renderEffect('Future-token {X} placeholder.');
  assert.ok(out.includes('{X}'), `unknown token should be preserved: ${out}`);
});
test('all 11 documented energy types resolve to a badge', () => {
  // G/R/W/L/P/F/D/M/Y/N/C — Grass/Fire/Water/Lightning/Psychic/Fighting/Darkness/Metal/Fairy/Dragon/Colorless
  const all = '{G}{R}{W}{L}{P}{F}{D}{M}{Y}{N}{C}';
  const out = ctx.renderEffect(all);
  assert.ok(!/\{[A-Z]\}/.test(out), `at least one token went unrendered: ${out}`);
  const badges = out.match(/energy-badge/g) || [];
  assert.equal(badges.length, 11, `expected 11 badges, got ${badges.length}: ${out}`);
});

console.log('\nME1/ME2 image migration — every card has a TCGdex image URL');
const fsImg = require('node:fs');
const pathImg = require('node:path');
const me1Data = JSON.parse(fsImg.readFileSync(pathImg.join(__dirname, '..', 'data', 'ME1.json'), 'utf8'));
const me2Data = JSON.parse(fsImg.readFileSync(pathImg.join(__dirname, '..', 'data', 'ME2.json'), 'utf8'));
const me3Data = JSON.parse(fsImg.readFileSync(pathImg.join(__dirname, '..', 'data', 'ME3.json'), 'utf8'));

test('every ME1 card has a TCGdex image URL', () => {
  const missing = Object.entries(me1Data.cards).filter(([, c]) => !c.image || !c.image.startsWith('https://assets.tcgdex.net/'));
  assert.equal(missing.length, 0, `${missing.length} ME1 cards missing tcgdex image; first: ${missing[0]?.[0]} → ${missing[0]?.[1]?.image}`);
});
test('every ME2 card has a TCGdex image URL', () => {
  const missing = Object.entries(me2Data.cards).filter(([, c]) => !c.image || !c.image.startsWith('https://assets.tcgdex.net/'));
  assert.equal(missing.length, 0, `${missing.length} ME2 cards missing tcgdex image; first: ${missing[0]?.[0]} → ${missing[0]?.[1]?.image}`);
});
test('ME3 is NOT touched (no tcgdex images injected)', () => {
  // ME3's text was manually cleaned ({C} → "Colorless") in scripts/enrich_m3_me3.py.
  // Re-pulling from tcgdex would regress that, so this PR explicitly leaves ME3 alone.
  const withImage = Object.entries(me3Data.cards).filter(([, c]) => c.image);
  assert.equal(withImage.length, 0, `ME3 should have no images; ${withImage.length} found (regression — we'd be re-introducing {C} tokens).`);
});
test('ME1-001 attack effect text is preserved exactly', () => {
  const expected = "During your opponent's next turn, the Defending Pokémon can't retreat.";
  assert.equal(me1Data.cards['001'].attacks[0].effect, expected,
    'ME1 text must not be overwritten by the migration — only image fields change.');
});
test('ME1-004 (Exeggcute) keeps its {G} energy token in attack effect', () => {
  // Tokens are now rendered correctly by renderEffect (Part A); the data must keep the raw token.
  assert.match(me1Data.cards['004'].attacks[0].effect, /\{G\}/,
    'ME1-004 attack effect should still contain a literal {G} token (rendering is renderEffect\'s job, not the data\'s).');
});
test('cardImageUrl resolves an ME1 sideload card to its TCGdex high.webp', () => {
  // sanity: the runtime resolution path picks up the new card.image and appends /high.webp
  const card = { id: 'ME1-001', image: me1Data.cards['001'].image };
  const url = ctx.cardImageUrl(card);
  assert.match(url, /^https:\/\/assets\.tcgdex\.net\/en\/me\/me01\/001\/high\.webp$/);
});

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
