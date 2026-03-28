const CACHE_NAME = 'ptcg-matcher-v5';
const APP_SHELL = [
  './',
  './index.html',
  './favicon.svg',
  './manifest.json',
  './data/ME1.json',
  './data/ME2.json',
  './data/ME3.json',
  './data/ME4.json',
  './data/M1S.json',
  './data/M1L.json',
  './data/M2.json',
  './data/M3.json',
  './data/M4.json',
];

// Install: pre-cache app shell + sideload data
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
});

// Activate: clean old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Fetch strategy:
// - App shell (data/*.json, index.html): cache-first
// - API calls (api.tcgdex.net): network-first with cache fallback
// - Images (assets.tcgdex.net, serebii): cache-first with network fallback
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // API: network-first
  if (url.hostname === 'api.tcgdex.net') {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
          return response;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  // Images: cache-first
  if (url.hostname === 'assets.tcgdex.net' || url.hostname === 'www.serebii.net') {
    event.respondWith(
      caches.match(event.request).then(cached => {
        if (cached) return cached;
        return fetch(event.request).then(response => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
          }
          return response;
        }).catch(() => new Response('', { status: 404 }));
      })
    );
    return;
  }

  // App shell and sideloads: cache-first
  event.respondWith(
    caches.match(event.request).then(cached => cached || fetch(event.request))
  );
});
