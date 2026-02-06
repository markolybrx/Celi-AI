const CACHE_NAME = 'celi-ai-v1.7.0'; // Bumped version to force update
const ASSETS_TO_CACHE = [
    '/',
    '/static/manifest.json',
    '/static/image.png',
    
    // CSS Modules
    '/static/css/base.css',
    '/static/css/layout.css',
    '/static/css/components.css',
    '/static/css/ranks.css',
    '/static/css/chat.css',
    '/static/css/animations.css',
    
    // JS Modules
    '/static/js/core.js',
    '/static/js/data.js',
    '/static/js/chat.js',
    '/static/js/ranks.js',
    '/static/js/galaxy.js',

    // External
    'https://cdn.tailwindcss.com'
];

// Install Event: Cache all assets
self.addEventListener('install', (event) => {
    self.skipWaiting();
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => cache.addAll(ASSETS_TO_CACHE))
            .catch((err) => console.error("Cache failed:", err))
    );
});

// Activate Event: Clean up old caches
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keyList) => {
            return Promise.all(keyList.map((key) => {
                if (key !== CACHE_NAME) {
                    return caches.delete(key);
                }
            }));
        }).then(() => self.clients.claim())
    );
});

// Fetch Event: Network First for API, Cache First for Assets
self.addEventListener('fetch', (event) => {
    // 1. API & Navigation: Network Only (No Cache)
    if (event.request.url.includes('/api/') || 
        event.request.mode === 'navigate' || 
        event.request.destination === 'document') {
        
        event.respondWith(
            fetch(event.request).catch(() => {
                return new Response("You are offline. Connect to the stars.", { 
                    headers: { 'Content-Type': 'text/plain' } 
                });
            })
        );
        return;
    }

    // 2. Assets: Cache First, then Network
    event.respondWith(
        caches.match(event.request).then((cachedResponse) => {
            if (cachedResponse) return cachedResponse;
            
            return fetch(event.request).then((networkResponse) => {
                // Check if valid response
                if (!networkResponse || networkResponse.status !== 200 || networkResponse.type !== 'basic') {
                    return networkResponse;
                }

                // Cache new assets dynamically
                const responseToCache = networkResponse.clone();
                caches.open(CACHE_NAME).then((cache) => {
                    cache.put(event.request, responseToCache);
                });

                return networkResponse;
            });
        })
    );
});