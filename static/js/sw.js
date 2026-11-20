/* Service worker: caches the app shell so pages open on weak signal, and shows an offline page. */
var CACHE = 'cc-v5';
var SHELL = ['/offline/', '/static/css/app.css', '/static/js/offline-queue.js', '/static/js/plan.js', '/static/js/voice.js', '/static/js/camera.js', '/static/icons/icon.svg',
             'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css'];

self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(SHELL); }).then(function () { return self.skipWaiting(); }));
});
self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});
self.addEventListener('fetch', function (e) {
  var req = e.request;
  if (req.method !== 'GET') return; // uploads are handled by the IndexedDB queue in the page
  var url = new URL(req.url);
  if (url.pathname.startsWith('/static/') || url.hostname === 'cdn.jsdelivr.net' || url.hostname.endsWith('gstatic.com')) {
    // static files: answer from cache at once (fast on weak signal), refresh the cache in the background
    e.respondWith(caches.open(CACHE).then(function (c) {
      return c.match(req).then(function (hit) {
        var net = fetch(req).then(function (res) { if (res.ok) c.put(req, res.clone()); return res; }).catch(function () { return hit; });
        return hit || net;
      });
    }));
    return;
  }
  if (req.mode === 'navigate') {
    // pages: network first, then the last cached copy, then the offline page
    e.respondWith(fetch(req).then(function (res) {
      if (res.ok) { var copy = res.clone(); caches.open(CACHE).then(function (c) { c.put(req, copy); }); }
      return res;
    }).catch(function () {
      return caches.match(req).then(function (hit) { return hit || caches.match('/offline/'); });
    }));
  }
});
