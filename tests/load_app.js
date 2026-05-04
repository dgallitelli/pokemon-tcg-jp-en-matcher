// Load app.js in a Node vm context with a minimal browser-API shim.
// We only need access to the pure-logic exports (POKEMON_NAME_MAP,
// pokemonNameFromMap, matchScore, etc.) — DOM/network calls happen
// lazily inside doSearch() which we don't invoke here.

const fs = require('fs');
const path = require('path');
const vm = require('vm');

function loadApp() {
  const appPath = path.join(__dirname, '..', 'app.js');
  const src = fs.readFileSync(appPath, 'utf8');

  // Stubs — every DOM/network call that runs at module-load time must be no-op.
  // fetch is needed by loadSideloadData() and loadSets(); return a rejected
  // promise so the top-level loaders don't hang but also don't crash.
  const rejectingFetch = () => Promise.reject(new Error('fetch disabled in test context'));
  const ls = {
    store: new Map(),
    getItem(k) { return this.store.has(k) ? this.store.get(k) : null; },
    setItem(k, v) { this.store.set(k, String(v)); },
    removeItem(k) { this.store.delete(k); },
    clear() { this.store.clear(); },
  };
  const listeners = {};
  const stubEl = {
    value: '', className: '', innerHTML: '', textContent: '',
    classList: { add() {}, remove() {}, contains() { return false; }, toggle() {} },
    style: {},
    children: [],
    appendChild() {}, addEventListener() {}, removeEventListener() {},
    querySelector() { return null; }, querySelectorAll() { return []; },
    getBoundingClientRect() { return { x: 0, y: 0, width: 0, height: 0, top: 0, left: 0, right: 0, bottom: 0 }; },
    focus() {}, blur() {},
  };
  const document = {
    getElementById() { return stubEl; },
    querySelector() { return null; },
    querySelectorAll() { return []; },
    addEventListener() {},
    createElement() { return { ...stubEl, setAttribute() {} }; },
    readyState: 'complete',
    body: stubEl,
  };
  const window = {
    matchMedia() { return { matches: false, addEventListener() {}, removeEventListener() {} }; },
    addEventListener() {},
    scrollTo() {},
    innerWidth: 1280, innerHeight: 800,
    location: { origin: 'http://test', pathname: '/', search: '' },
    history: { replaceState() {} },
  };
  const URL_ = global.URL;
  const URLSearchParams_ = global.URLSearchParams;
  const navigator = { serviceWorker: { register: rejectingFetch }, clipboard: { writeText: rejectingFetch } };

  const sandbox = {
    fetch: rejectingFetch,
    localStorage: ls,
    document,
    window,
    navigator,
    URL: URL_,
    URLSearchParams: URLSearchParams_,
    setTimeout, clearTimeout, setInterval, clearInterval,
    console,
    IntersectionObserver: function () { this.observe = () => {}; this.disconnect = () => {}; this.unobserve = () => {}; },
    Promise, Map, Set, Array, Object, JSON, parseInt, parseFloat, String, Number, RegExp, Math, Date, Error,
  };

  const context = vm.createContext(sandbox);

  // Suppress unhandled rejection noise from the rejectingFetch calls that
  // the module fires off at load time (loadSets, loadSideloadData).
  const origOnUnhandled = process.listeners('unhandledRejection');
  const swallow = (reason) => { /* ignore */ };
  process.on('unhandledRejection', swallow);

  try {
    vm.runInContext(src, context, { filename: 'app.js' });
  } finally {
    process.removeListener('unhandledRejection', swallow);
  }

  return context;
}

module.exports = { loadApp };
