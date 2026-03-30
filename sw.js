var CACHE_NAME = "ftu-labs-v1";

var PRECACHE = [
  "/vendor/hljs/highlight.min.js",
  "/vendor/hljs/atom-one-dark.min.css",
  "/vendor/hljs/languages/latex.min.js",
  "/vendor/hljs/languages/dockerfile.min.js",
  "/vendor/hljs/languages/ini.min.js",
  "/css/style.css",
  "/js/main.js",
  "/js/hljs.js",
  "/img/logo.png",
];

self.addEventListener("install", function (e) {
  e.waitUntil(
    caches.open(CACHE_NAME).then(function (cache) {
      return cache.addAll(PRECACHE);
    })
  );
  self.skipWaiting();
});

self.addEventListener("activate", function (e) {
  e.waitUntil(
    caches.keys().then(function (names) {
      return Promise.all(
        names
          .filter(function (name) {
            return name !== CACHE_NAME;
          })
          .map(function (name) {
            return caches.delete(name);
          })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener("fetch", function (e) {
  var url = new URL(e.request.url);

  // Only handle same-origin GET requests
  if (e.request.method !== "GET" || url.origin !== self.location.origin) {
    return;
  }

  var path = url.pathname;

  // Cache-first for vendor files and static assets that rarely change
  var isCacheFirst =
    path.startsWith("/vendor/") ||
    path.endsWith(".css") ||
    path.endsWith(".js") ||
    path.endsWith(".woff2") ||
    path.endsWith(".png");

  if (isCacheFirst) {
    e.respondWith(
      caches.match(e.request).then(function (cached) {
        if (cached) {
          return cached;
        }
        return fetch(e.request).then(function (response) {
          if (response.ok) {
            var clone = response.clone();
            caches.open(CACHE_NAME).then(function (cache) {
              cache.put(e.request, clone);
            });
          }
          return response;
        });
      })
    );
    return;
  }

  // Network-first for HTML pages (so content updates are seen quickly)
  e.respondWith(
    fetch(e.request)
      .then(function (response) {
        if (response.ok) {
          var clone = response.clone();
          caches.open(CACHE_NAME).then(function (cache) {
            cache.put(e.request, clone);
          });
        }
        return response;
      })
      .catch(function () {
        return caches.match(e.request);
      })
  );
});
