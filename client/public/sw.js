const CACHE_VERSION = "v3";
const STATIC_CACHE = `nexora-static-${CACHE_VERSION}`;
const HTML_CACHE = `nexora-html-${CACHE_VERSION}`;
const SHELL_URLS = ["/manifest.webmanifest", "/icon-192.svg", "/icon-512.svg"];

function offlineResponse() {
  return new Response("Recurso no disponible sin conexión", {
    status: 503,
    statusText: "Offline",
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) =>
      Promise.allSettled(
        SHELL_URLS.map((url) =>
          cache.add(url).catch((err) => {
            console.warn("[SW] No se pudo cachear:", url, err);
          }),
        ),
      ),
    ).then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key !== STATIC_CACHE && key !== HTML_CACHE)
            .map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

async function cacheIfOk(cacheName, request, response) {
  if (!response || !response.ok || response.type === "opaque") return response;
  const cache = await caches.open(cacheName);
  await cache.put(request, response.clone());
  return response;
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/")) return;

  const isDocument = request.mode === "navigate" || request.destination === "document";

  if (isDocument) {
    event.respondWith(
      fetch(request)
        .then((response) => cacheIfOk(HTML_CACHE, "/index.html", response))
        .catch(async () => (await caches.match("/index.html")) || offlineResponse()),
    );
    return;
  }

  if (
    url.pathname.startsWith("/assets/") ||
    request.destination === "style" ||
    request.destination === "script"
  ) {
    event.respondWith(
      caches.match(request).then((cached) => {
        const network = fetch(request)
          .then((response) => cacheIfOk(STATIC_CACHE, request, response))
          .catch(() => null);
        return cached || network.then((response) => response || offlineResponse());
      }),
    );
    return;
  }

  event.respondWith(
    fetch(request)
      .then((response) => cacheIfOk(STATIC_CACHE, request, response))
      .catch(async () => (await caches.match(request)) || offlineResponse()),
  );
});
