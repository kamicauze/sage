// Service Worker for Sage PWA
const CACHE_NAME = 'sage-v1';
const STATIC_CACHE = 'sage-static-v1';

// Files to cache immediately
const STATIC_FILES = [
  '/',
  '/brain',
  '/manifest.json'
];

// Install event - cache static assets
self.addEventListener('install', (event) => {
  console.log('[SW] Installing service worker...');
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((cache) => {
        console.log('[SW] Caching static files');
        return cache.addAll(STATIC_FILES);
      })
      .then(() => self.skipWaiting())
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  console.log('[SW] Activating service worker...');
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME && cacheName !== STATIC_CACHE) {
            console.log('[SW] Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(async () => {
      if (self.registration.navigationPreload) {
        await self.registration.navigationPreload.enable();
      }
      return self.clients.claim();
    })
  );
});

// Fetch event - network first, fallback to cache
self.addEventListener('fetch', (event) => {
  // Skip non-GET requests
  if (event.request.method !== 'GET') return;

  // Skip WebSocket and MQTT connections
  if (event.request.url.includes('ws://') || event.request.url.includes('wss://')) {
    return;
  }

  const requestUrl = new URL(event.request.url);
  const isSameOrigin = requestUrl.origin === self.location.origin;
  const isNavigation = event.request.mode === 'navigate';

  // Avoid caching API responses to keep data fresh
  if (isSameOrigin && requestUrl.pathname.startsWith('/api/')) {
    return;
  }

  const respondWithCache = async () => {
    const cache = await caches.open(CACHE_NAME);
    const cachedResponse = await cache.match(event.request);

    const fetchAndCache = async (responsePromise) => {
      try {
        const response = await responsePromise;
        if (response && response.status === 200) {
          cache.put(event.request, response.clone());
        }
        return response;
      } catch (error) {
        throw error;
      }
    };

    if (isNavigation) {
      const preloadResponse = await event.preloadResponse;
      if (cachedResponse) {
        fetchAndCache(preloadResponse || fetch(event.request)).catch(() => null);
        return cachedResponse;
      }
      return fetchAndCache(preloadResponse || fetch(event.request));
    }

    if (cachedResponse) {
      fetchAndCache(fetch(event.request)).catch(() => null);
      return cachedResponse;
    }

    return fetchAndCache(fetch(event.request));
  };

  event.respondWith(
    respondWithCache().catch(async () => {
      const cachedFallback = await caches.match(event.request);
      if (cachedFallback) {
        return cachedFallback;
      }

      if (isNavigation) {
        return caches.match('/');
      }

      return new Response('Offline - no cached version available', {
        status: 503,
        statusText: 'Service Unavailable',
      });
    })
  );
});

// Handle messages from client
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});
