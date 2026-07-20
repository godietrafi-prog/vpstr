/* Poster viewer offline resilience.
 * Core files are installed eagerly; same-origin media is cached as it is shown.
 */
var CACHE_NAME = 'poster-viewer-v1';
var CORE = [
    './vleft.html',
    './vright.html',
    './slides.json',
    './news.json',
    './birthdays.csv',
    './birthday-audio.js',
    './promo-audio.js'
];

self.addEventListener('install', function(event) {
    event.waitUntil(
        caches.open(CACHE_NAME).then(function(cache) {
            return cache.addAll(CORE);
        }).then(function() { return self.skipWaiting(); })
    );
});

self.addEventListener('activate', function(event) {
    event.waitUntil(
        caches.keys().then(function(keys) {
            return Promise.all(keys.map(function(key) {
                if (key !== CACHE_NAME && key.indexOf('poster-viewer-') === 0)
                    return caches.delete(key);
            }));
        }).then(function() { return self.clients.claim(); })
    );
});

self.addEventListener('fetch', function(event) {
    var request = event.request;
    if (request.method !== 'GET') return;
    var url = new URL(request.url);
    if (url.origin !== self.location.origin) return;

    event.respondWith(
        fetch(request).then(function(response) {
            if (response && response.ok) {
                var copy = response.clone();
                caches.open(CACHE_NAME).then(function(cache) { cache.put(request, copy); });
            }
            return response;
        }).catch(function() {
            return caches.match(request, { ignoreSearch: true }).then(function(cached) {
                if (cached) return cached;
                if (request.mode === 'navigate') {
                    var fallback = url.pathname.indexOf('vright') >= 0 ? './vright.html' : './vleft.html';
                    return caches.match(fallback);
                }
                return Response.error();
            });
        })
    );
});
