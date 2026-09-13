const CACHE_NAME = 'fieldmoist-amap-v2';

function isAmapResource(request) {
  if (request.method !== 'GET') return false;
  const url = new URL(request.url);
  const amapHost = url.hostname === 'amap.com'
    || url.hostname.endsWith('.amap.com')
    || url.hostname === 'autonavi.com'
    || url.hostname.endsWith('.autonavi.com');
  if (!amapHost) return false;
  const resource = url.pathname + url.search;
  const isTile = /appmaptile|tile|style|satellite|road|vec/i.test(resource);
  const isMapScript = url.hostname === 'webapi.amap.com'
    && (request.destination === 'script' || request.destination === 'style');
  return isTile || isMapScript;
}

self.addEventListener('fetch', (event) => {
  if (!isAmapResource(event.request)) return;
  event.respondWith((async () => {
    const cache = await caches.open(CACHE_NAME);
    const cached = await cache.match(event.request);
    if (cached) return cached;
    try {
      const response = await fetch(event.request);
      if (response.ok || response.type === 'opaque') {
        await cache.put(event.request, response.clone());
      }
      return response;
    } catch (error) {
      return cached || Response.error();
    }
  })());
});

self.addEventListener('install', (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const cacheNames = await caches.keys();
    await Promise.all(cacheNames
      .filter((name) => name.startsWith('fieldmoist-amap-') && name !== CACHE_NAME)
      .map((name) => caches.delete(name)));
    await self.clients.claim();
  })());
});
