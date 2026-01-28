const CACHE_NAME = 'celi-ai-v1.6.2';
const ASSETS_TO_CACHE = [
    '/static/manifest.json',
    '/static/image.png',
    '/static/script.js?v=1.5.3',
    'https://cdn.tailwindcss.com'
];

self.addEventListener('install', (event) => {
    self.skipWaiting();
    event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS_TO_CACHE)));
});

self.addEventListener('activate', (event) => {
    event.waitUntil(caches.keys().then((keyList) => Promise.all(keyList.map((key) => { if (key !== CACHE_NAME) return caches.delete(key); }))).then(() => self.clients.claim()));
});

self.addEventListener('fetch', (event) => {
    if (event.request.url.includes('/api/') || event.request.mode === 'navigate' || event.request.destination === 'document') {
        event.respondWith(fetch(event.request).catch(() => new Response("You are offline.", { headers: { 'Content-Type': 'text/plain' } })));
        return;
    }
    event.respondWith(caches.match(event.request).then((cachedResponse) => { if (cachedResponse) return cachedResponse; return fetch(event.request).then((networkResponse) => { if (!networkResponse || networkResponse.status !== 200 || networkResponse.type !== 'basic') return networkResponse; const responseToCache = networkResponse.clone(); caches.open(CACHE_NAME).then((cache) => cache.put(event.request, responseToCache)); return networkResponse; }); }));
});
