// DualSoul Service Worker — offline shell + cache
const CACHE_NAME = 'dualsoul-v87nianlun2';
const SHELL_URLS = ['/', '/static/manifest.json'];

// Install: cache the app shell
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_URLS))
  );
  self.skipWaiting();
});

// Activate: clean up old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Fetch: network-first for API, cache-first for shell
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Skip non-GET requests and WebSocket
  if (event.request.method !== 'GET') return;
  if (url.pathname.startsWith('/ws')) return;

  // API requests: network-only with offline JSON fallback
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(event.request).catch(() =>
        new Response(JSON.stringify({success: false, error: 'offline'}),
          {status: 503, headers: {'Content-Type': 'application/json'}})
      )
    );
    return;
  }

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        // Update cache with fresh response
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        return response;
      })
      .catch(() => {
        // Offline fallback: serve from cache
        return caches.match(event.request);
      })
  );
});
