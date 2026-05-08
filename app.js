const API = 'https://api.tcgdex.net/v2';

// In-memory caches — survive re-searches within a session
const apiCache = new Map();
const dexNameCache = new Map();
let lastScoredCards = new Map(); // id → full card object, populated after each search

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

async function cachedApiFetch(url) {
  if (apiCache.has(url)) return apiCache.get(url);
  const res = await fetch(url);
  if (!res.ok) return null;
  const data = await res.json();
  apiCache.set(url, data);
  return data;
}

// cardCount values come from known set sizes — avoids fetching JSON just for the dropdown
const SIDELOAD_CONFIG = {
  jp: [
    { id: "M1S", name: "Mega Symphonia",  file: "data/M1S.json", cardCount: 92  },
    { id: "M1L", name: "Mega Brave",      file: "data/M1L.json", cardCount: 92  },
    { id: "M2",  name: "Inferno X",       file: "data/M2.json",  cardCount: 116 },
    { id: "M3",  name: "Nihil Zero",      file: "data/M3.json",  cardCount: 117 },
    { id: "M4",  name: "Ninja Spinner",   file: "data/M4.json",  cardCount: 120 },
    { id: "M2a", name: "MEGA Dream ex",   file: "data/M2a.json", cardCount: 193 },
  ],
  en: [
    { id: "ME1", name: "Mega Evolution",      file: "data/ME1.json" },
    { id: "ME2", name: "Phantasmal Flames",   file: "data/ME2.json" },
    { id: "ME3", name: "Perfect Order",       file: "data/ME3.json" },
    { id: "ME4", name: "Ninja Spinner",       file: "data/ME4.json" },
  ]
};

// O(1) lookup for JP sideload config by set ID
// Keys are uppercased to match setUpper lookups (handles mixed-case IDs like "M2a" → "M2A")
const SIDELOAD_JP_CONFIG = Object.fromEntries(SIDELOAD_CONFIG.jp.map(c => [c.id.toUpperCase(), c]));

// Map JP set IDs to their EN translation sideload set IDs
// Keys must be uppercase to match jpSetId.toUpperCase() lookups
// Note: M2a (MEGA Dream ex) has no EN sideload — it's a different product from
// Destined Rivals (sv10), so M2a falls through to the TCGdex API path.
const JP_TO_EN_SIDELOAD = { "M1S": "ME1", "M1L": "ME1", "M2": "ME2", "M3": "ME3", "M4": "ME4" };

let SIDELOAD_SETS = {};
let SIDELOAD_EN_SETS = {};

// Pre-load only EN sideloads (needed for every search's dexId scan).
// JP sideloads are fetched lazily on first use to avoid blocking page startup.
async function loadSideloadData() {
  await Promise.all(
    SIDELOAD_CONFIG.en.map(async cfg => {
      try {
        const res = await fetch(cfg.file);
        if (res.ok) {
          const data = await res.json();
          // Inject id/set defaults for older sideloads (ME1/ME2) that predate those fields
          const cards = Object.fromEntries(
            Object.entries(data.cards).map(([num, card]) => [num, {
              id: `${cfg.id}-${num}`,
              set: { id: cfg.id, name: cfg.name },
              ...card,
            }])
          );
          SIDELOAD_EN_SETS[cfg.id] = { name: cfg.name, cards };
        }
      } catch {}
    })
  );
}

// Lazy-load a single JP sideload set on first access
async function ensureJpSideloadLoaded(setId) {
  if (SIDELOAD_SETS[setId]) return;
  const cfg = SIDELOAD_JP_CONFIG[setId];
  if (!cfg) return;
  try {
    const res = await fetch(cfg.file);
    if (res.ok) {
      const data = await res.json();
      SIDELOAD_SETS[setId] = { name: cfg.name, cards: data.cards || data };
    }
  } catch {}
}

// Sets known-missing from TCGdex with no sideload data yet.
// These are XY-era Mega Evolution decks, distinct from the new MEGA SV-era sideloaded sets (M1S, M1L, M2, M3, M4).
const MISSING_SETS = {
  'xy-m1': { name: "Mega Brave Deck",          note: "XY — Mega Kangaskhan/Gyarados decks" },
  'xy-m2': { name: "Mega Battle Deck 60",       note: "XY — Mega Aggron/Ampharos" },
  'xy-m4': { name: "Mega Blastoise/Kangaskhan", note: "XY" },
  'xy-m5': { name: "Mega Tokyo Deck",           note: "XY" },
};

// Load Japanese sets into dropdown.
// Uses SIDELOAD_CONFIG directly for offline sets — no need to wait for file fetches.
async function loadSets() {
  const dl = document.getElementById('setList');
  try {
    const res = await fetch(`${API}/ja/sets`);
    const sets = await res.json();
    sets.sort((a, b) => (b.releaseDate || '').localeCompare(a.releaseDate || ''));
    for (const s of sets) {
      const opt = document.createElement('option');
      opt.value = s.id;
      opt.label = `${s.name} — ${s.cardCount.total} cards`;
      dl.appendChild(opt);
    }
  } catch {}
  // Add sideloaded sets using config metadata — no fetch required
  for (const cfg of SIDELOAD_CONFIG.jp) {
    const opt = document.createElement('option');
    opt.value = cfg.id;
    opt.label = `${cfg.name} — ${cfg.cardCount} cards (offline)`;
    dl.appendChild(opt);
  }
}

// Pad card number to 3 digits with leading zeros
function padNum(n) {
  const s = String(n).replace(/^0+/, '');
  return s.padStart(3, '0');
}

function safeHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function setStatus(msg, isError) {
  const el = document.getElementById('status');
  el.className = isError ? 'status error' : 'status';
  el.innerHTML = msg;
}

function scoreLabel(score) {
  if (score >= 70) return `High (${score}/100)`;
  if (score >= 40) return `Medium (${score}/100)`;
  return `Low (${score}/100)`;
}

// Serebii slug map: card-id prefix → /card/<slug>/<n>.jpg
// ME2a has no dedicated EN Serebii page; it reuses the JP megadreamex slug
// (card numbering is identical between M2a and ME2a) — effectively a JP-image fallback.
const SEREBII_SLUGS = {
  'M1S':  'megasymphonia',
  'M1L':  'megabrave',
  'M2':   'infernox',
  'M3':   'nihilzero',
  'M4':   'ninjaspinner',
  'M2a':  'megadreamex',
  'ME1':  'megaevolution',
  'ME2':  'phantasmalflames',
  'ME3':  'perfectorder',
  'ME4':  'ninjaspinner',
};

function sideloadImageUrl(card) {
  const m = card.id && card.id.match(/^([A-Za-z0-9]+)-(\d+)$/);
  if (!m) return null;
  const slug = SEREBII_SLUGS[m[1]];
  if (!slug) return null;
  return `https://www.serebii.net/card/${slug}/${parseInt(m[2], 10)}.jpg`;
}

// Resolve a card's primary image URL using the same rules as renderCard —
// used to pass the JP image as a fallback when the EN panel's image is missing.
function cardImageUrl(card) {
  if (!card) return null;
  if (card.image) return /\.(png|jpg|webp)$/i.test(card.image) ? card.image : card.image + '/high.webp';
  return sideloadImageUrl(card) || null;
}

// Source attribution — which data source this English card came from.
// Returns { label, tooltip } for display in the EN panel, or null for non-EN panels.
function sourceAttribution(card) {
  if (!card?.id) return null;
  const prefix = (card.id.split('-')[0] || '').toUpperCase();
  // Sideload-based EN translations
  if (prefix === 'ME1') return { label: 'Serebii + TCGdex', tooltip: 'Translation assembled from Serebii (Mega Evolution) with TCGdex fallback.' };
  if (prefix === 'ME2') return { label: 'Serebii + TCGdex', tooltip: 'Translation assembled from Serebii (Phantasmal Flames) with TCGdex fallback.' };
  if (prefix === 'ME3') return { label: 'Serebii + TCGdex', tooltip: 'Translation assembled from Serebii (Perfect Order) with TCGdex fallback.' };
  if (prefix === 'ME4') return { label: 'Serebii + PokeBeach', tooltip: 'Translation assembled from Serebii (Ninja Spinner) with PokeBeach fallback.' };
  // Synthetic — a JP card recast as EN using backfilled Serebii text
  if ((card.attacks || []).some(a => a.name === '—')) {
    return { label: 'Serebii (machine-translated)', tooltip: 'No official English print yet — attack names are unavailable.' };
  }
  // Otherwise live TCGdex match
  return { label: 'TCGdex', tooltip: `Live match from TCGdex set ${card.set?.id || ''}.` };
}

// Deep link to Limitless TCG — lets the user cross-check against a canonical source.
// Limitless uses official TCG set codes (TWM, SVI, PAF…) rather than TCGdex's (sv06, sv01, sv04.5…).
// This maps the TCGdex IDs we care about to Limitless codes.
const LIMITLESS_SET_MAP = {
  // Live TCGdex Scarlet & Violet era
  'sv01':   'SVI',  // Scarlet & Violet (base)
  'sv02':   'PAL',  // Paldea Evolved
  'sv03':   'OBF',  // Obsidian Flames
  'sv03.5': 'MEW',  // 151
  'sv04':   'PAR',  // Paradox Rift
  'sv04.5': 'PAF',  // Paldean Fates
  'sv05':   'TEF',  // Temporal Forces
  'sv06':   'TWM',  // Twilight Masquerade
  'sv06.5': 'SFA',  // Shrouded Fable
  'sv07':   'SCR',  // Stellar Crown
  'sv08':   'SSP',  // Surging Sparks
  'sv08.5': 'PRE',  // Prismatic Evolutions
  'sv09':   'JTG',  // Journey Together
  'sv10':   'DRI',  // Destined Rivals
  'svp':    'PR-SV', // SVP Black Star Promos
};
function limitlessLinkFor(card) {
  if (!card?.id) return null;
  const m = card.id.match(/^([A-Za-z0-9.]+)-(\d+)$/);
  if (!m) return null;
  const [, rawSet, num] = m;
  const mapped = LIMITLESS_SET_MAP[rawSet];
  // Skip our machine-translated ME1/2/3/4 sideloads — Limitless wouldn't have those codes
  if (!mapped && /^ME\d/i.test(rawSet)) return null;
  // Only emit a link when we actually have a mapping. Otherwise we'd produce broken 404 URLs.
  if (!mapped) return null;
  return `https://limitlesstcg.com/cards/${mapped}/${parseInt(num, 10)}`;
}

const ENERGY_COLORS = {
  Grass:'#78C850',Fire:'#F08030',Water:'#6890F0',Lightning:'#F8D030',
  Psychic:'#F85888',Fighting:'#C03028',Darkness:'#705848',Metal:'#B8B8D0',
  Dragon:'#7038F8',Fairy:'#EE99AC',Colorless:'#A8A878'
};
function energyBadge(type) {
  const c = ENERGY_COLORS[type] || '#888';
  return `<span class="energy-badge" style="background:${c}">${safeHtml(type.slice(0,3))}</span>`;
}

function renderCard(card, lang, badge, score, fallbackImgUrl) {
  const imgUrl = cardImageUrl(card);
  // If the primary image 404s (e.g. Serebii doesn't have this EN card yet), swap to the
  // fallback — usually the JP version of the same card — before showing the 🃏 placeholder.
  const fallbackAttr = fallbackImgUrl && fallbackImgUrl !== imgUrl
    ? ` data-fallback="${safeHtml(fallbackImgUrl)}"` : '';
  const onErrorJs = fallbackImgUrl && fallbackImgUrl !== imgUrl
    ? `if(this.dataset.fallback){this.src=this.dataset.fallback;this.dataset.fallback='';this.classList.add('jp-fallback');var h=this.parentNode.querySelector('.jp-fallback-hint');if(h)h.style.display='block';return;}this.onerror=null;this.style.display='none';this.nextElementSibling.style.display='flex'`
    : `this.onerror=null;this.style.display='none';this.nextElementSibling.style.display='flex'`;
  const attacks = (card.attacks || []).map(a => {
    const cost = (a.cost || []).map(t => energyBadge(t)).join('');
    let block = `<div class="atk-block"><div class="atk-row">${cost ? `<span class="atk-cost">${cost}</span>` : ''}<span class="atk-name">${safeHtml(a.name)}</span>${a.damage != null ? `<span class="atk-dmg">${safeHtml(String(a.damage))}</span>` : ''}</div>`;
    if (a.effect) block += `<div class="atk-effect">${safeHtml(a.effect)}</div>`;
    block += `</div>`;
    return block;
  }).join('');
  const abilities = (card.abilities || []).map(a => {
    let block = `<div class="atk-block"><div class="ability-row"><span class="ability-label">Ability</span> <span class="ability-name">${safeHtml(a.name)}</span></div>`;
    if (a.effect) block += `<div class="atk-effect">${safeHtml(a.effect)}</div>`;
    block += `</div>`;
    return block;
  }).join('');
  const cardName = safeHtml(card.name);
  const setName = safeHtml(card.set?.name || '?');
  const cardId = safeHtml(card.id);
  const illustrator = card.illustrator ? safeHtml(card.illustrator) : null;
  const types = card.types ? card.types.map(t => energyBadge(t)).join(' ') : null;
  const hp = card.hp ? safeHtml(String(card.hp)) : null;
  const stage = card.stage ? safeHtml(card.stage) : null;
  const weakness = card.weakness ? `${energyBadge(card.weakness.type)} ${safeHtml(card.weakness.value || '')}` : null;
  const resistance = card.resistance ? `${energyBadge(card.resistance.type)} ${safeHtml(card.resistance.value || '')}` : null;
  const retreat = card.retreat != null && card.retreat > 0 ? Array(card.retreat).fill(energyBadge('Colorless')).join('') : null;
  const subcategory = card.subcategory ? safeHtml(card.subcategory) : null;
  const badgeLabel = badge || (lang === 'ja' ? '日本語 Japanese' : '🇺🇸 English');
  const badgeClass = badge ? 'trans' : lang;
  const confidencePip = (score !== undefined && score < 70)
    ? `<span class="confidence-pip">${score < 40 ? 'Low' : 'Med'} match</span>` : '';
  // Share icon appears on EN panels (including Translation-badged synthetic/sideload matches)
  const shareBtn = (lang === 'en' || badge) ? `<button class="share-icon" id="shareBtn" title="Copy link" aria-label="Copy link">🔗</button>` : '';
  // Source attribution on EN / Translation panels only — tells the user where the data came from
  const source = (lang === 'en' || badge) ? sourceAttribution(card) : null;
  const sourceLine = source ? `<div class="source-line" title="${safeHtml(source.tooltip)}">Source: ${safeHtml(source.label)}</div>` : '';
  // Limitless deep link escape hatch — when we can form a valid cards URL
  const limitlessUrl = limitlessLinkFor(card);
  const limitlessLink = (lang === 'en' || badge) && limitlessUrl
    ? `<a class="limitless-link" href="${limitlessUrl}" target="_blank" rel="noopener">View on Limitless ↗</a>` : '';
  return `
    <div class="card-panel${imgUrl ? '' : ' no-image'}">
      <div class="panel-header">
        <span class="lang-badge ${badgeClass}">${badgeLabel}</span>
        ${confidencePip}
        ${shareBtn}
      </div>
      <h2>${cardName}</h2>
      ${imgUrl ? `<img src="${imgUrl}" alt="${cardName}" loading="lazy"${fallbackAttr} onerror="${onErrorJs}"><div class="img-placeholder" style="display:none;width:100%;aspect-ratio:5/7;background:#0f3460;border-radius:8px;margin-bottom:1rem;align-items:center;justify-content:center;color:#555;font-size:2rem">🃏</div>${fallbackAttr ? '<div class="jp-fallback-hint" style="display:none">Showing Japanese card — no English image available.</div>' : ''}` : ''}
      ${sourceLine}
      ${limitlessLink}
      <div class="card-meta">
        <div class="meta-head">
          <span class="lbl">Set</span><span>${setName}</span> <span style="color:var(--text-faint)">(${cardId})</span>
        </div>
        ${abilities || attacks ? `<div class="atk-section">${abilities}${attacks}</div>` : ''}
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
      </div>
    </div>`;
}

// Post-render hook: auto-open details on desktop, activate sticky bar on mobile.
function openDetailsOnDesktop() {
  if (window.matchMedia('(min-width: 681px)').matches) {
    document.querySelectorAll('#results .card-details').forEach(d => d.open = true);
  }
  refreshStickyBar();
}

// Compact JP renderer — used on mobile as a scroll-below confirmation block.
// Image by default, attacks/abilities hidden behind "Show JP text" toggle.
function renderCardCompactJp(card) {
  const imgUrl = cardImageUrl(card);
  const cardName = safeHtml(card.name);
  const cardId = safeHtml(card.id || '');
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

// Compose results HTML for the various render modes.
//   mode='pair'     — EN + JP (side-by-side on desktop, stacked EN-first on mobile)
//   mode='en-only'  — just JP shown (no EN match — we render JP so user sees something)
function assembleResults(jpCard, enCard, mode, badge, score) {
  const isMobile = window.matchMedia('(max-width: 680px)').matches;
  if (mode === 'en-only') {
    return `<div class="cards-container">${renderCard(jpCard, 'ja')}</div>`;
  }
  const jpImg = cardImageUrl(jpCard);
  const enImg = cardImageUrl(enCard);
  // Same image URL on both sides = single Serebii slug serving both JP and EN
  // (e.g. M4/ME4 both use ninjaspinner). Render a single merged panel since the
  // image only needs to be shown once.
  if (jpImg && enImg && jpImg === enImg) {
    return `<div class="cards-container cards-container--merged">${renderCard(enCard, 'en', badge || '🔄 Translation', score, null)}</div>`;
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

// Score how well an English card matches the Japanese card
function matchScore(jpCard, enCard) {
  let score = 0;
  let reasons = [];

  // Category mismatch is a hard penalty — Pokemon should never match Trainer
  if (jpCard.category && enCard.category && jpCard.category !== enCard.category) {
    return { score: 0, reasons: ['category mismatch'] };
  }
  if (jpCard.category && enCard.category && jpCard.category === enCard.category) {
    score += 5;
    reasons.push('category');
  }

  // Illustrator match is very strong signal (same print)
  if (jpCard.illustrator && enCard.illustrator &&
      jpCard.illustrator.toLowerCase() === enCard.illustrator.toLowerCase()) {
    score += 25;
    reasons.push('illustrator');
  }

  // HP match
  if (jpCard.hp && enCard.hp && jpCard.hp === enCard.hp) {
    score += 15;
    reasons.push('HP');
  }

  // Type match
  if (jpCard.types && enCard.types && jpCard.types.length > 0 && enCard.types.length > 0) {
    const jpTypes = jpCard.types.map(t => t.toLowerCase()).sort().join(',');
    const enTypes = enCard.types.map(t => t.toLowerCase()).sort().join(',');
    if (jpTypes === enTypes) {
      score += 8;
      reasons.push('type');
    }
  }

  // Ability count + name match
  const jpAbils = jpCard.abilities || [];
  const enAbils = enCard.abilities || [];
  if (jpAbils.length > 0 && jpAbils.length === enAbils.length) {
    score += 7;
    reasons.push('ability count');
  } else if (jpAbils.length !== enAbils.length) {
    score -= 5; // Mismatch penalty
  }

  // Attack count match
  const jpAtks = jpCard.attacks || [];
  const enAtks = enCard.attacks || [];
  if (jpAtks.length === enAtks.length && jpAtks.length > 0) {
    score += 10;
    reasons.push('attack count');
    // Attack damage match
    const jpDmg = jpAtks.map(a => a.damage).sort().join(',');
    const enDmg = enAtks.map(a => a.damage).sort().join(',');
    if (jpDmg === enDmg) {
      score += 12;
      reasons.push('attack damage');
    }
    // Attack cost match
    const jpCost = jpAtks.map(a => (a.cost || []).length).sort().join(',');
    const enCost = enAtks.map(a => (a.cost || []).length).sort().join(',');
    if (jpCost === enCost) {
      score += 8;
      reasons.push('attack costs');
    }
  }

  // Weakness match
  if (jpCard.weakness && enCard.weakness &&
      jpCard.weakness.type && enCard.weakness.type &&
      jpCard.weakness.type.toLowerCase() === enCard.weakness.type.toLowerCase()) {
    score += 3;
    reasons.push('weakness');
  }

  // Resistance match
  if (jpCard.resistance && enCard.resistance &&
      jpCard.resistance.type && enCard.resistance.type &&
      jpCard.resistance.type.toLowerCase() === enCard.resistance.type.toLowerCase()) {
    score += 2;
    reasons.push('resistance');
  }

  // Retreat cost match
  if (jpCard.retreat !== undefined && enCard.retreat !== undefined && jpCard.retreat === enCard.retreat) {
    score += 3;
    reasons.push('retreat');
  }

  // Stage match
  if (jpCard.stage && enCard.stage && jpCard.stage === enCard.stage) {
    score += 3;
    reasons.push('stage');
  }

  // Rarity tiebreaker (small bonus, not decisive)
  if (jpCard.rarity && enCard.rarity && jpCard.rarity === enCard.rarity) {
    score += 1;
    reasons.push('rarity');
  }

  return { score: Math.max(0, score), reasons };
}

// JP Pokemon name → EN name for cards missing dexId in TCGdex (ex cards, paradox, etc.)
const POKEMON_NAME_MAP = {
  'リーフィア': 'Leafeon', 'カミツオロチ': 'Hydrapple', 'テツノイサハ': 'Iron Leaves',
  'ヤバソチャ': 'Sinistcha', 'オーガポン': 'Ogerpon', 'ブースター': 'Flareon',
  'ウガツホムラ': 'Gouging Fire', 'シャワーズ': 'Vaporeon', 'ガブリアス': 'Garchomp',
  'グレイシア': 'Glaceon', 'イルカマン': 'Palafin', 'ウネルミナモ': 'Walking Wake',
  'サンダース': 'Jolteon', 'テツノカイナ': 'Iron Hands', 'テツノイバラ': 'Iron Thorns',
  'エーフィ': 'Espeon', 'ニンフィア': 'Sylveon', 'テツノブジン': 'Iron Valiant',
  'テツノカシラ': 'Iron Crown', 'スナノケガワ': 'Sandy Shocks', 'ブラッキー': 'Umbreon',
  'トドロクツキ': 'Roaring Moon', 'イイネイヌ': 'Okidogi', 'マシマシラ': 'Munkidori',
  'キチキギス': 'Fezandipiti', 'モモワロウ': 'Pecharunt', 'サーフゴー': 'Gholdengo',
  'ドラパルト': 'Dragapult', 'タケルライコ': 'Raging Bolt', 'イーブイ': 'Eevee',
  'テラパゴス': 'Terapagos', 'ソウブレイズ': 'Ceruledge', 'ピカチュウ': 'Pikachu',
  'ガチグマ': 'Ursaluna',
  // Paldea starters & their finals
  'ニャオハ': 'Sprigatito', 'ニャローテ': 'Floragato', 'マスカーニャ': 'Meowscarada',
  'ホゲータ': 'Fuecoco', 'アチゲータ': 'Crocalor', 'ラウドボーン': 'Skeledirge',
  'クワッス': 'Quaxly', 'ウェルカモ': 'Quaxwell', 'ウェーニバル': 'Quaquaval',
  // Paldea ex regulars
  'フォレトス': 'Forretress', 'リククラゲ': 'Toedscruel', 'クエスパトラ': 'Espathra',
  'フーディン': 'Alakazam', 'ミュウ': 'Mew', 'サーナイト': 'Gardevoir',
  'キラフロル': 'Glimmora', 'リザードン': 'Charizard', 'オンバーン': 'Noivern',
  'ピジョット': 'Pidgeot', 'プクリン': 'Wigglytuff', 'イキリンコ': 'Squawkabilly',
  'ドオー': 'Clodsire',
  // Legendaries / Paradox / Treasures of Ruin
  'ミライドン': 'Miraidon', 'コライドン': 'Koraidon',
  'イダイナキバ': 'Great Tusk', 'テツノワダチ': 'Iron Treads',
  'チオンジェン': 'Wo-Chien', 'パオジアン': 'Chien-Pao', 'ディンルー': 'Ting-Lu',
  'イーユイ': 'Chi-Yu',
  // sv10 Destined Rivals additions
  'オリーヴァ': 'Arboliva', 'ハルクジラ': 'Cetitan', 'レジロック': 'Regirock',
  'ファイヤー': 'Moltres', 'ミュウツー': 'Mewtwo', 'ニドキング': 'Nidoking',
  'クロバット': 'Crobat', 'ペルシアン': 'Persian',
  // Other common Pokemon that surface with trainer ownership prefixes
  'ザシアン': 'Zacian', 'カイロス': 'Pinsir', 'ホウオウ': 'Ho-Oh',
};

// EN form name overrides for JP Pokemon with form suffixes/prefixes (JP → EN prefix)
const POKEMON_FORM_MAP = {
  'みどりのめん': 'Teal Mask', 'かまどのめん': 'Hearthflame Mask',
  'いどのめん': 'Wellspring Mask', 'いしずえのめん': 'Cornerstone Mask',
  'アカツキ': 'Bloodmoon',
  'パルデア': 'Paldean',
};

// Trainer-owned Pokémon prefixes — JP uses "<Trainer>の<Pokémon>"; EN uses
// "<Trainer>'s <Pokémon>". Applied by pokemonNameFromMap when the JP name
// starts with a key here. Example: "ロケット団のミュウツーex" → "Team Rocket's Mewtwo ex".
const TRAINER_OWNED_POKEMON_PREFIX = {
  'ロケット団': "Team Rocket's",
  'ホップ': "Hop's",
  'ヒビキ': "Ethan's",
  'ネモ': "Nemona's",
  'ペパー': "Arven's",
  'ナンジャモ': "Iono's",
  'スグリ': "Kieran's",
  'ゼイユ': "Carmine's",
  'シロナ': "Cynthia's",
  'マリィ': "Marnie's",
  'リーリエ': "Lillie's",
  'マチス': "Lt. Surge's",
};

// Common JP → EN trainer/energy name mappings for cross-language search
const TRAINER_NAME_MAP = {
  'ボスの指令': "Boss's Orders",
  'ナンジャモ': 'Iono',
  'ネモ': 'Nemona',
  'ペパー': 'Arven',
  'オモダカ': 'Geeta',
  'セイボリー': 'Avery',
  'チリ': 'Chili',
  'コルサ': 'Brassius',
  'カエデ': 'Katy',
  'リップ': 'Rika',
  'グルーシャ': 'Grusha',
  'カイ': 'Irida',
  'シロナの覇気': "Cynthia's Ambition",
  'シロナ': 'Cynthia',
  '博士の研究': "Professor's Research",
  'リーリエ': 'Lillie',
  'マリィ': 'Marnie',
  'セレナ': 'Serena',
  'ポケモンいれかえ': 'Switch',
  'ハイパーボール': 'Ultra Ball',
  'レベルボール': 'Level Ball',
  'ネストボール': 'Nest Ball',
  'クイックボール': 'Quick Ball',
  'ふしぎなアメ': 'Rare Candy',
  'きずぐすり': 'Potion',
  'すごいきずぐすり': 'Super Potion',
  'エネルギー回収': 'Energy Retrieval',
  'エネルギーつけかえ': 'Energy Switch',
  'ダブルターボエネルギー': 'Double Turbo Energy',
  'ジェットエネルギー': 'Jet Energy',
  'ギフトエネルギー': 'Gift Energy',
  'セラピーエネルギー': 'Therapeutic Energy',
  'リバーサルエネルギー': 'Reversal Energy',
  'ルミナスエネルギー': 'Luminous Energy',
  'レガシーエネルギー': 'Legacy Energy',
  'ミストエネルギー': 'Mist Energy',
  // M1S / Mega Symphonia trainers (ME1 English names)
  'あやしい時計': 'Strange Timepiece',
  'メガシグナル': 'Mega Signal',
  'アセロラのいたずら': "Acerola's Mischief",
  'ミツルの思いやり': "Wally's Compassion",
  '活力の森': 'Forest of Vitality',
  'なみのりビーチ': 'Surfing Beach',
  'ミステリーガーデン': 'Mystery Garden',
  'なかよしポフィン': 'Buddy-Buddy Poffin',
  // M1L / Mega Brave trainers (ME1 English names)
  'アイアンガード': 'Iron Defender',
  'プレミアムパワープロ': 'Premium Power Pro',
  'ファイトゴング': 'Fighting Gong',
  'むしよけスプレー': 'Repel',
  'マチスのかけひき': "Lt. Surge's Bargain",
  'リーリエのきもち': "Lillie's Determination",
  '危険な廃墟ビル': 'Risky Ruins',
  'ナイトストレッチャー': 'Night Stretcher',
  'エアバルーン': 'Air Balloon',
  // M2 / Infernox trainers (ME2 English names)
  'ジャンボソフト': 'Jumbo Ice Cream',
  'ヒートバーナー': 'Blowtorch',
  'セイクリッドチャーム': 'Sacred Charm',
  'ギーマのかけひき': "Grimsley's Move",
  'ヒカリ': 'Dawn',
  'ファイアーブレーサー': 'Firebreather',
  'バトルコロシアム': 'Battle Cage',
  'めまいのたに': 'Dizzying Valley',
  // SV8a / Terastal Fest ex trainers (Prismatic Evolutions EN names)
  '鬼の仮面': "Ogre's Mask",
  '改造ハンマー': 'Enhanced Hammer',
  'カウンターキャッチャー': 'Counter Catcher',
  'ガラスのラッパ': 'Glass Trumpet',
  'スーパーエネルギー回収': 'Superior Energy Retrieval',
  'つりざおMAX': 'Max Rod',
  '大地の器': 'Earthen Vessel',
  'テクノレーダー': 'Techno Radar',
  'テラスタルオーブ': 'Tera Orb',
  'トレジャーガジェット': 'Treasure Tracker',
  'プライムキャッチャー': 'Prime Catcher',
  'ポケモン回収サイクロン': 'Scoop Up Cyclone',
  'むしとりセット': 'Bug Catching Set',
  '夜のタンカ': 'Night Stretcher',
  'きらめく結晶': 'Sparkling Crystal',
  '緊急ボード': 'Rescue Board',
  'くさりもち': 'Binding Mochi',
  'ゴージャスマント': 'Luxurious Cape',
  'ハバンのみ': 'Haban Berry',
  'ブーストエナジー 古代': 'Ancient Booster Energy Capsule',
  'ブーストエナジー 未来': 'Future Booster Energy Capsule',
  'マキシマムベルト': 'Maximum Belt',
  'ワザマシン エヴォリューション': 'Technical Machine: Evolution',
  'ワザマシン デヴォリューション': 'Technical Machine: Devolution',
  'アオキの手際': "Larry's Skill",
  'アカマツ': 'Crispin',
  'アクロマの執念': "Colress's Tenacity",
  '暗号マニアの解読': "Ciphermaniac's Codebreaking",
  'アンズの秘技': "Janine's Secret Art",
  'オーリム博士の気迫': "Professor Sada's Vitality",
  'スイレンのお世話': "Lana's Aid",
  'スグリ': 'Kieran',
  'ゼイユ': 'Carmine',
  'タロ': 'Lacey',
  '探検家の先導': "Explorer's Guidance",
  'ネリネ': 'Amarys',
  'パルデアの仲間たち': 'Friends in Paldea',
  'フトゥー博士のシナリオ': "Professor Turo's Scenario",
  'ブライア': 'Briar',
  'ベルのまごころ': "Bianca's Devotion",
  'マツバの確信': "Morty's Conviction",
  'メロコ': 'Mela',
  'お祭り会場': 'Festival Grounds',
  'ジャミングタワー': 'Jamming Tower',
  'ゼロの大空洞': 'Area Zero Underdepths',
  '月明かりの丘': 'Moonlit Hill',
  'ニュートラルセンター': 'Neutralization Zone',
  'オルティガ': 'Ortega',
  'シュウメイ': 'Atticus',
  'タイム': 'Tyme',
  'ピーニャ': 'Giacomo',
  'ビワ': 'Eri',
  'レホール': 'Raifort',
  'カキツバタ': 'Drayton',
  // sv5a Crimson Haze — JP-only set; trainers are reprints of sv06 (Twilight Masquerade)
  // except ポケモンキャッチャー which reprints sv01 Pokémon Catcher.
  'アンフェアスタンプ': 'Unfair Stamp',
  'ハイパーアロマ': 'Hyper Aroma',
  'ポケモンキャッチャー': 'Pokémon Catcher',
  'ラブラブボール': 'Love Ball',
  'サバイブギプス': 'Survival Brace',
  'ラッキーメット': 'Lucky Helmet',
  '管理人': 'Caretaker',
  'ゴヨウ': 'Lucian',
  'サザレ': 'Perrin',
  '公民館': 'Community Center',
  'ブーメランエネルギー': 'Boomerang Energy',
  // sv10 Destined Rivals — Team Rocket trainers and energy
  'ロケット団のおじゃまロボ': "Team Rocket's Bother-Bot",
  'ロケット団のスーパーボール': "Team Rocket's Great Ball",
  'ロケット団のびっくりボム': "Team Rocket's Venture Bomb",
  'ロケット団のレシーバー': "Team Rocket's Transceiver",
  'ロケット団のアテナ': "Team Rocket's Ariana",
  'ロケット団のアポロ': "Team Rocket's Archer",
  'ロケット団のサカキ': "Team Rocket's Giovanni",
  'ロケット団のラムダ': "Team Rocket's Petrel",
  'ロケット団のランス': "Team Rocket's Proton",
  'ロケット団の監視塔': "Team Rocket's Watchtower",
  'ロケット団のファクトリー': "Team Rocket's Factory",
  'ロケット団エネルギー': "Team Rocket's Energy",
};

function pokemonNameFromMap(jpName) {
  if (!jpName) return null;
  const isEx = jpName.endsWith('ex');
  const bare = isEx ? jpName.slice(0, -2).trimEnd() : jpName;

  // Trainer-owned Pokémon: "<Trainer>の<Pokemon>" (no space) → "<Trainer>'s <EN>".
  // Example: "ロケット団のミュウツーex" → "Team Rocket's Mewtwo ex".
  for (const [jpPrefix, enPossessive] of Object.entries(TRAINER_OWNED_POKEMON_PREFIX)) {
    const key = jpPrefix + 'の';
    if (bare.startsWith(key)) {
      const inner = bare.slice(key.length);
      const innerEn = POKEMON_NAME_MAP[inner];
      if (innerEn) return `${enPossessive} ${innerEn}${isEx ? ' ex' : ''}`;
    }
  }

  const parts = bare.split(/\s+/);
  // Try forms where the base Pokemon is parts[0] with a trailing form suffix
  // (e.g. "オーガポン みどりのめん" → Teal Mask Ogerpon)
  let baseName = POKEMON_NAME_MAP[parts[0]];
  let formKey = parts.length > 1 ? parts.slice(1).join(' ') : '';
  // Otherwise, try the leading-form-prefix form (e.g. "パルデア ドオー" → Paldean Clodsire)
  if (!baseName && parts.length > 1) {
    const tail = parts.slice(1).join(' ');
    baseName = POKEMON_NAME_MAP[tail];
    formKey = parts[0];
  }
  if (!baseName) return null;
  const formPrefix = (formKey && POKEMON_FORM_MAP[formKey]) ? POKEMON_FORM_MAP[formKey] + ' ' : '';
  return formPrefix + baseName + (isEx ? ' ex' : '');
}

// Pokédex number → English name lookup via TCGdex, with memoization
async function getEnglishName(dexId) {
  if (dexNameCache.has(dexId)) return dexNameCache.get(dexId);
  try {
    const data = await cachedApiFetch(`${API}/en/dex-ids/${dexId}`);
    if (!data) { dexNameCache.set(dexId, null); return null; }
    const cards = data.cards || data;
    if (cards && cards.length > 0) {
      // Find the simplest name (no prefix like "Blaine's")
      const simple = cards.find(c => !c.name.includes("'s ") && !c.name.includes(' '));
      const name = (simple || cards[0]).name;
      dexNameCache.set(dexId, name);
      return name;
    }
    dexNameCache.set(dexId, null);
    return null;
  } catch { dexNameCache.set(dexId, null); return null; }
}

async function browseSet() {
  const setId = document.getElementById('setInput').value.trim();
  if (!setId) { setStatus('Please enter a set ID to browse.', true); return; }

  const setUpper = setId.toUpperCase();
  setStatus('<span class="loading"></span> Loading set...', false);
  document.getElementById('results').innerHTML = '';

  await sideloadReadyPromise;
  if (SIDELOAD_JP_CONFIG[setUpper]) await ensureJpSideloadLoaded(setUpper);

  let cards = [];
  let setName = setId;

  let hasCategories = false;
  if (SIDELOAD_SETS[setUpper]) {
    const sideload = SIDELOAD_SETS[setUpper];
    setName = sideload.name || setUpper;
    hasCategories = true;
    cards = Object.entries(sideload.cards).map(([num, c]) => ({
      num, name: c.name, id: c.id, category: c.category || '',
      image: c.image ? (/\.(png|jpg|webp)$/i.test(c.image) ? c.image : c.image + '/high.webp') : sideloadImageUrl(c)
    }));
  } else {
    try {
      const data = await cachedApiFetch(`${API}/ja/sets/${setId}`);
      if (!data || !data.cards) { setStatus(`Set "${safeHtml(setId)}" not found.`, true); return; }
      setName = data.name || setId;
      cards = data.cards.map(c => ({
        num: c.id.split('-').pop(), name: c.name, id: c.id, category: c.category || '',
        image: c.image ? (/\.(png|jpg|webp)$/i.test(c.image) ? c.image : c.image + '/high.webp') : null
      }));
      if (cards.some(c => c.category)) hasCategories = true;
    } catch { setStatus(`Failed to load set "${safeHtml(setId)}".`, true); return; }
  }

  cards.sort((a, b) => a.num.localeCompare(b.num, undefined, { numeric: true }));

  setStatus('', false);
  const browsePage = document.getElementById('browsePage');
  browsePage.style.display = 'block';

  function renderBrowseCard(c) {
    return `<div class="browse-card" data-cat="${safeHtml(c.category)}" onclick="document.getElementById('setInput').value='${safeHtml(setId)}';document.getElementById('cardNum').value='${safeHtml(c.num)}';closeBrowse();doSearch();">
      ${c.image ? `<img src="${c.image}" alt="${safeHtml(c.name)}" loading="lazy" onerror="this.onerror=null;this.style.display='none';this.nextElementSibling.style.display='flex'"><div style="display:none;width:100%;aspect-ratio:5/7;background:#0f3460;border-radius:6px;align-items:center;justify-content:center;color:#555;font-size:1.5rem">🃏</div>` : `<div style="width:100%;aspect-ratio:5/7;background:#0f3460;border-radius:6px;display:flex;align-items:center;justify-content:center;color:#555;font-size:1.5rem">🃏</div>`}
      <div class="bc-name">${safeHtml(c.name)}</div>
      <div class="bc-num">#${safeHtml(c.num)}</div>
    </div>`;
  }

  browsePage.innerHTML = `
    <div class="browse-header">
      <button class="browse-back" onclick="closeBrowse()">&larr; Back</button>
      <h2>${safeHtml(setName)} (${safeHtml(setId)}) — ${cards.length} cards</h2>
    </div>
    ${hasCategories ? `<div class="browse-filters">
      <button class="browse-filter-btn active" data-filter="All">All</button>
      <button class="browse-filter-btn" data-filter="Pokemon">Pokemon</button>
      <button class="browse-filter-btn" data-filter="Trainer">Trainer</button>
      <button class="browse-filter-btn" data-filter="Energy">Energy</button>
    </div>` : ''}
    <div class="browse-grid">
      ${cards.map(c => renderBrowseCard(c)).join('')}
    </div>`;

  // Wire up filter buttons
  browsePage.querySelectorAll('.browse-filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      browsePage.querySelectorAll('.browse-filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const filter = btn.dataset.filter;
      browsePage.querySelectorAll('.browse-card').forEach(card => {
        card.style.display = (filter === 'All' || card.dataset.cat === filter) ? '' : 'none';
      });
    });
  });
}

function closeBrowse() {
  document.getElementById('browsePage').style.display = 'none';
  document.getElementById('browsePage').innerHTML = '';
}

async function doSearch() {
  const searchBtn = document.getElementById('searchBtn');
  if (searchBtn.disabled) return; // Guard against concurrent calls from Enter key
  const setId = document.getElementById('setInput').value.trim();
  const rawNum = document.getElementById('cardNum').value.trim();
  if (!setId || !rawNum) { setStatus('Please enter a set ID and card number.', true); return; }

  // Update URL for deep linking (without triggering navigation)
  const url = new URL(window.location);
  url.searchParams.set('set', setId);
  url.searchParams.set('num', rawNum);
  history.replaceState(null, '', url);

  closeBrowse(); // Close set browser if open

  searchBtn.disabled = true;
  try { localStorage.setItem('lastSet', setId); } catch {}
  pushRecentSet(setId);
  renderChipRow();
  try {
    const setUpper = setId.toUpperCase();
    const cardNum = padNum(rawNum);

    // Check missing sets (case-insensitive)
    const missKey = Object.keys(MISSING_SETS).find(k => k.toLowerCase() === setId.toLowerCase());
    if (missKey) {
      const info = MISSING_SETS[missKey];
      setStatus(`⚠️ Set <strong>${safeHtml(setId)}</strong> (${safeHtml(info.name)}) is not yet indexed in TCGdex and cannot be matched automatically. You can help by contributing the data at <a href="https://github.com/tcgdex/cards-database" target="_blank" style="color:#ffd700">tcgdex/cards-database</a>.`, true);
      return;
    }

    setStatus('<span class="loading"></span> Fetching Japanese card...', false);
    document.getElementById('results').innerHTML = '';

    // Ensure EN sideloads are ready before proceeding (awaits background load)
    await sideloadReadyPromise;

    // Lazy-load the JP sideload set if this is the first time it's been searched
    if (SIDELOAD_JP_CONFIG[setUpper]) {
      await ensureJpSideloadLoaded(setUpper);
    }

    // 1. Get the Japanese card — from sideload or TCGdex API
    let jpCard;
    if (SIDELOAD_SETS[setUpper]) {
      const sideload = SIDELOAD_SETS[setUpper];
      jpCard = sideload.cards[cardNum] || sideload.cards[rawNum];
      if (!jpCard) {
        setStatus(`❌ Card ${safeHtml(cardNum)} not found in ${safeHtml(setUpper)} (${safeHtml(sideload.name)})`, true);
        return;
      }
    } else {
      const cardId = `${setId}-${cardNum}`;
      try {
        let jpData = await cachedApiFetch(`${API}/ja/cards/${cardId}`);
        if (!jpData) {
          // Try without padding
          jpData = await cachedApiFetch(`${API}/ja/cards/${setId}-${rawNum}`);
          if (!jpData) throw new Error(`Card not found: ${safeHtml(cardId)}`);
        }
        jpCard = jpData;
      } catch (e) {
        setStatus(`❌ ${safeHtml(e.message)}`, true);
        return;
      }
    }

    setStatus('<span class="loading"></span> Searching for English equivalent...', false);

    // 2a. If this JP card comes from a sideloaded set with a translation file, show it directly
    {
      const jpSetId = (jpCard.set?.id || setUpper).toUpperCase();
      const enTransSetId = JP_TO_EN_SIDELOAD[jpSetId];
      const enTransSet = enTransSetId ? SIDELOAD_EN_SETS[enTransSetId] : null;
      if (enTransSet) {
        const jpNum = jpCard.id?.split('-')[1] || cardNum;
        let transCard = null;
        // Sort by card number so lower-numbered (base) cards are preferred over alt-arts/URs
        const enCardsEntries = Object.entries(enTransSet.cards);
        const enCardsSorted = enCardsEntries
          .sort(([ka], [kb]) => parseInt(ka, 10) - parseInt(kb, 10))
          .map(([, v]) => v);
        if (jpCard.category === 'Pokemon' && jpCard.dexId?.length > 0) {
          // Match by dexId + illustrator — card numbers may differ between JP and EN sets
          transCard = enCardsSorted.find(c =>
            c.dexId?.some(id => jpCard.dexId.includes(id)) &&
            c.illustrator && jpCard.illustrator &&
            c.illustrator.toLowerCase() === jpCard.illustrator.toLowerCase()
          ) || enCardsSorted.find(c =>
            c.dexId?.some(id => jpCard.dexId.includes(id))
          );
        } else if (jpCard.category === 'Energy') {
          // Energy: match by category + energy type keyword in name
          // JP energy names contain type kanji: 草=Grass, 炎=Fire, 水=Water, 雷=Lightning,
          // 超=Psychic, 闘=Fighting, 悪=Darkness, 鋼=Metal
          const typeMap = {'草':'Grass','炎':'Fire','水':'Water','雷':'Lightning',
            '超':'Psychic','闘':'Fighting','悪':'Darkness','鋼':'Metal'};
          let matchType = null;
          for (const [kanji, eng] of Object.entries(typeMap)) {
            if (jpCard.name?.includes(kanji)) { matchType = eng; break; }
          }
          if (matchType) {
            transCard = enCardsSorted.find(c =>
              c.category === 'Energy' && c.name?.toLowerCase().includes(matchType.toLowerCase())
            );
          }
          if (!transCard) {
            transCard = enCardsSorted.find(c => c.category === 'Energy');
          }
        } else {
          // Trainer: name-map match first (most precise), then illustrator as fallback
          const mappedName = TRAINER_NAME_MAP[jpCard.name];
          if (mappedName) {
            transCard = enCardsSorted.find(c =>
              c.category !== 'Pokemon' &&
              c.name?.toLowerCase() === mappedName.toLowerCase()
            );
          }
          if (!transCard && jpCard.illustrator) {
            // Illustrator fallback: require name-map confirmation if multiple trainers share artist
            const illustratorMatches = enCardsSorted.filter(c =>
              c.category !== 'Pokemon' &&
              c.illustrator?.toLowerCase() === jpCard.illustrator.toLowerCase()
            );
            // Only use illustrator match when it's unambiguous (exactly one candidate)
            if (illustratorMatches.length === 1) transCard = illustratorMatches[0];
          }
        }
        // Fallback: direct card number, but only if categories match AND (for Pokemon
        // with a dexId) the fallback shares at least one dexId. This prevents picking
        // the wrong Pokemon just because the numbers happen to align.
        if (!transCard) {
          const fallback = enTransSet.cards[jpNum] || enTransSet.cards[rawNum];
          if (fallback && fallback.category === jpCard.category) {
            const jpHasDex = jpCard.dexId?.length > 0;
            const enHasDex = fallback.dexId?.length > 0;
            const dexOk = !jpHasDex || !enHasDex ||
              fallback.dexId.some(id => jpCard.dexId.includes(id));
            if (dexOk) transCard = fallback;
          }
        }
        // Guard: reject sideload match if the card name contains JP text (untranslated)
        const hasJpText = t => t && /[\u3040-\u9FFF]/.test(t);
        if (transCard && hasJpText(transCard.name)) transCard = null;
        if (transCard) {
          setStatus('', false);
          document.getElementById('results').innerHTML = assembleResults(jpCard, transCard, 'pair', '🔄 Translation');
          openDetailsOnDesktop();
          return;
        }
      }
    }

    // 2b. Find English candidates via API
    let enName = null;
    // Try dexId lookup first (Pokemon cards)
    if (jpCard.dexId && jpCard.dexId.length > 0) {
      enName = await getEnglishName(jpCard.dexId[0]);
    }
    // Pokemon without dexId: try JP→EN name map (handles ex cards, paradox Pokemon, forms)
    if (!enName && jpCard.category === 'Pokemon' && jpCard.name) {
      enName = pokemonNameFromMap(jpCard.name);
    }
    // Trainer/Energy: try name map lookup
    if (!enName && jpCard.category !== 'Pokemon' && jpCard.name) {
      enName = TRAINER_NAME_MAP[jpCard.name];
    }

    let candidates = [];
    if (enName) {
      try {
        const params = new URLSearchParams({ name: enName });
        if (jpCard.hp) params.set('hp', jpCard.hp);
        const data = await cachedApiFetch(`${API}/en/cards?${params}`);
        if (data) candidates = data;
      } catch {}

      // If hp filter was too strict, try name only
      if (candidates.length === 0) {
        try {
          const data = await cachedApiFetch(`${API}/en/cards?name=${encodeURIComponent(enName)}`);
          if (data) candidates = data;
        } catch {}
      }
    }

    // Also collect matching EN cards from SIDELOAD_EN_SETS by dexId
    // (only Pokemon — trainer/energy illustrator matching across unrelated sets is too loose)
    const sideloadEnCards = [];
    for (const sEnSetData of Object.values(SIDELOAD_EN_SETS)) {
      for (const enCard of Object.values(sEnSetData.cards)) {
        if (jpCard.dexId && jpCard.dexId.length > 0 &&
            enCard.dexId && enCard.dexId.some(id => jpCard.dexId.includes(id))) {
          sideloadEnCards.push(enCard);
        }
      }
    }

    // 3. Fetch full details for candidates and score them
    if (candidates.length === 0 && sideloadEnCards.length === 0) {
      setStatus('', false);
      // If the JP card already has English effect/attack data, show a synthetic translation card.
      // enName is already resolved above (via dexId lookup or TRAINER_NAME_MAP).
      // Guard: reject text that contains Japanese characters — it wasn't backfilled in English.
      const isEnglish = t => t && !/[\u3040-\u9FFF]/.test(t);
      const hasEnData = isEnglish(jpCard.effect) ||
        (jpCard.attacks || []).some(a => isEnglish(a.effect));
      if (hasEnData) {
        // Strip JP attack names — only cost, damage and effect are available in English.
        const syntheticEn = {
          ...jpCard,
          name: enName || jpCard.name,
          attacks: (jpCard.attacks || []).map(a => ({ ...a, name: '—' })),
        };
        document.getElementById('results').innerHTML =
          assembleResults(jpCard, syntheticEn, 'pair', '🔄 Translation') +
          `<div class="match-info">This card has no official English print yet. Showing translated card text from <span style="color:#ffd700">Serebii</span>. Attack names are not translated.</div>`;
        openDetailsOnDesktop();
      } else {
        document.getElementById('results').innerHTML =
          assembleResults(jpCard, null, 'en-only') +
          `<div class="match-info"><span class="no-match">No English equivalent found.</span>
            ${jpCard.category !== 'Pokemon' ? '<br>Trainer/Energy card matching by name is limited — these often have different names across languages.' : ''}
            ${!jpCard.dexId ? '<br>This card has no Pokédex ID, so name lookup was not possible.' : ''}</div>`;
        openDetailsOnDesktop();
      }
      return;
    }

    setStatus(`<span class="loading"></span> Scoring ${candidates.length} candidates...`, false);

    // Pre-filter candidates: prefer same era by release year if JP card has set release info
    let filteredCandidates = candidates;
    if (candidates.length > 20 && jpCard.set?.releaseDate) {
      const jpYear = parseInt(jpCard.set.releaseDate.substring(0, 4), 10);
      if (jpYear) {
        // Prefer cards from ±2 years of the JP set release
        const nearEra = candidates.filter(c => {
          const ry = c.releaseDate || c.set?.releaseDate;
          if (!ry) return true; // keep if unknown
          const ey = parseInt(String(ry).substring(0, 4), 10);
          return Math.abs(ey - jpYear) <= 2;
        });
        if (nearEra.length >= 5) filteredCandidates = nearEra;
      }
    }

    // Fetch full card data for top candidates (limit to 30); results are cached
    const toFetch = filteredCandidates.slice(0, 30);
    const fetchedCards = await Promise.all(
      toFetch.map(c => cachedApiFetch(`${API}/en/cards/${c.id}`))
    );
    const fullCards = [...fetchedCards, ...sideloadEnCards];

    const scored = fullCards
      .filter(Boolean)
      .map(c => ({ card: c, ...matchScore(jpCard, c) }))
      .sort((a, b) => b.score - a.score);

    // Cache scored cards so showAlternate can swap panels without re-fetching
    lastScoredCards = new Map(scored.map(s => [s.card.id, s.card]));

    const best = scored[0];
    if (!best) {
      setStatus('', false);
      document.getElementById('results').innerHTML =
        assembleResults(jpCard, null, 'en-only') +
        `<div class="match-info"><span class="no-match">Could not fetch English card details for comparison.</span></div>`;
      openDetailsOnDesktop();
      return;
    }

    setStatus('', false);
    document.getElementById('results').innerHTML =
      assembleResults(jpCard, best.card, 'pair', null, best.score) +
      (scored.length > 1 ? `
      <button class="wrong-card-btn" id="wrongCardBtn">Wrong card? Try another →</button>
      <div class="wrong-card-list" id="wrongCardList" style="display:none">
        <ul>${scored.slice(1).map(s =>
          `<li class="candidate-item" data-card-id="${safeHtml(s.card.id)}" data-score="${s.score}" tabindex="0">${safeHtml(s.card.name)} — ${safeHtml(s.card.set?.name || s.card.id)}</li>`
        ).join('')}</ul>
      </div>` : '');
    openDetailsOnDesktop();

    // Attach event listeners to candidate items (avoids inline onclick with user-controlled IDs)
    document.querySelectorAll('.candidate-item').forEach(li => {
      const cardId = li.dataset.cardId;
      const score = parseInt(li.dataset.score, 10);
      li.addEventListener('click', () => showAlternate(cardId, score));
      li.addEventListener('keydown', e => { if (e.key === 'Enter') showAlternate(cardId, score); });
    });
  } finally {
    searchBtn.disabled = false;
  }
}

// Allow clicking alternate candidates
async function showAlternate(cardId, score) {
  let card = null;
  // Check sideloaded EN sets first — these cards won't be in the TCGdex API
  for (const sEnSetData of Object.values(SIDELOAD_EN_SETS)) {
    const found = Object.values(sEnSetData.cards).find(c => c.id === cardId);
    if (found) { card = found; break; }
  }
  // Check cards already fetched during this search — avoids a redundant API call
  if (!card) card = lastScoredCards.get(cardId) || null;
  if (!card) {
    card = await cachedApiFetch(`${API}/en/cards/${cardId}`);
    if (!card) return;
  }
  // EN panel is panels[0] on mobile (EN-first stack) and panels[1] on desktop (JP left, EN right)
  const isMobile = window.matchMedia('(max-width: 680px)').matches;
  const panels = document.querySelectorAll('#results .card-panel');
  if (panels.length < 2) return;
  const enPanel = isMobile ? panels[0] : panels[1];
  const jpPanel = isMobile ? panels[1] : panels[0];
  const jpImg = jpPanel.querySelector('img')?.src || null;
  enPanel.outerHTML = renderCard(card, 'en', null, score, jpImg);
  openDetailsOnDesktop();
}

// ── Sticky input bar on mobile ───────────────────────────
// Activates .input-section--sticky whenever we're on a mobile viewport AND there
// are results rendered. Stays visible at all times while active; the previous
// auto-hide-while-card-visible behavior was too aggressive and hid the bar even
// when the user wanted to type another card number.
function refreshStickyBar() {
  const section = document.getElementById('inputSection');
  const results = document.getElementById('results');
  if (!section || !results) return;
  const isMobile = window.matchMedia('(max-width: 680px)').matches;
  const hasResults = results.children.length > 0;
  if (isMobile && hasResults) {
    section.classList.add('input-section--sticky');
  } else {
    section.classList.remove('input-section--sticky');
  }
  // Legacy hidden class from an earlier auto-hide observer; clear unconditionally
  section.classList.remove('input-section--hidden');
}
window.addEventListener('resize', refreshStickyBar);

// ── Chip row: recents + autocomplete ─────────────────────
function renderChipRow() {
  const row = document.getElementById('chipRow');
  const input = document.getElementById('setInput');
  if (!row || !input) return;
  const typed = input.value.trim();
  let items = [];
  let mode = 'recent';
  if (typed && document.activeElement === input) {
    const lower = typed.toLowerCase();
    const allIds = [
      ...SIDELOAD_CONFIG.jp.map(c => c.id),
      ...Array.from(document.querySelectorAll('#setList option')).map(o => o.value),
    ];
    const seen = new Set();
    for (const id of allIds) {
      if (!id || seen.has(id.toLowerCase())) continue;
      if (id.toLowerCase() === lower) continue;
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
  input.addEventListener('blur', () => setTimeout(renderChipRow, 120));
}

// Init: EN sideloads load in background; dropdown populates immediately from config
const sideloadReadyPromise = loadSideloadData();
loadSets().then(renderChipRow);
wireChipRow();
renderChipRow();

// Deep linking: auto-search if URL has ?set=...&num=...
{
  const params = new URLSearchParams(window.location.search);
  const urlSet = params.get('set');
  const urlNum = params.get('num');
  if (urlSet && urlNum) {
    document.getElementById('setInput').value = urlSet;
    document.getElementById('cardNum').value = urlNum;
    doSearch();
  }
}

// Allow Enter key to trigger search
document.getElementById('cardNum').addEventListener('keydown', e => {
  if (e.key === 'Enter') doSearch();
});
document.getElementById('setInput').addEventListener('keydown', e => {
  if (e.key === 'Enter') {
    e.preventDefault();
    document.getElementById('cardNum').focus();
  }
});

// Restore last-used set
const savedSet = localStorage.getItem('lastSet');
if (savedSet && !document.getElementById('setInput').value) {
  document.getElementById('setInput').value = savedSet;
}

// Card image modal
const imgModal = document.getElementById('img-modal');
const imgModalImg = document.getElementById('img-modal-img');
const imgModalText = document.getElementById('img-modal-text');
document.getElementById('img-modal-close').addEventListener('click', () => imgModal.classList.remove('open'));
imgModal.addEventListener('click', e => { if (e.target === imgModal) imgModal.classList.remove('open'); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') imgModal.classList.remove('open'); });
document.addEventListener('click', e => {
  // Card image → open modal with image + text
  const img = e.target.closest('.card-panel img');
  if (img) {
    imgModalImg.src = img.src;
    imgModalText.innerHTML = '';
    const panel = img.closest('.card-panel');
    if (panel) {
      const header = panel.querySelector('.panel-header');
      const name = panel.querySelector('h2');
      const meta = panel.querySelector('.card-meta');
      if (header) imgModalText.appendChild(header.cloneNode(true));
      if (name) { const h = document.createElement('h2'); h.textContent = name.textContent; imgModalText.appendChild(h); }
      if (meta) imgModalText.appendChild(meta.cloneNode(true));
    }
    imgModal.classList.add('open');
    return;
  }
  // Wrong card toggle
  if (e.target.closest('#wrongCardBtn')) {
    const list = document.getElementById('wrongCardList');
    if (list) list.style.display = list.style.display === 'none' ? '' : 'none';
    return;
  }
  // Share button
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
});

// Unregister any previously installed service worker
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('./sw.js').catch(() => {});
}
