const CACHE_NAME = "nexora-v1";
const SHELL_URLS = [
  "/",
  "/index.html",
  "/manifest.webmanifest",
  "/icon-192.svg",
  "/icon-512.svg",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      const promises = SHELL_URLS.map((url) =>
        cache.add(url).catch((err) => {
          console.warn("[SW] No se pudo cachear:", url, err);
        }),
      );
      return Promise.allSettled(promises).then(() => self.skipWaiting());
    }),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))),
    ).then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;

  if (event.request.method === "GET") {
    event.respondWith(
      caches.match(event.request).then((cached) => {
        if (cached) return cached;
        return fetch(event.request).catch(() => {
          if (event.request.mode === "navigate") return caches.match("/");
          return new Response("Sin conexión", { status: 503, statusText: "Offline" });
        });
      }),
    );
  }
});
