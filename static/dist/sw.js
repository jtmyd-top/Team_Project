const CACHE_NAME = 'team-project-static-v3';
const STATIC_PREFIX = '/static/';
const PRIVATE_PREFIXES = ['/api/', '/uploads/', '/protected_uploads/'];

self.addEventListener('install', () => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys
          .filter((key) => key.startsWith('team-project-') && key !== CACHE_NAME)
          .map((key) => caches.delete(key)),
      ))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);

  if (request.method !== 'GET' || url.origin !== self.location.origin) return;
  if (PRIVATE_PREFIXES.some((prefix) => url.pathname.startsWith(prefix))) return;

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).catch(() => new Response(
        '<!doctype html><meta charset="utf-8"><title>网络不可用</title><main><h1>网络不可用</h1><p>请恢复网络后重试。</p></main>',
        {
          headers: { 'Content-Type': 'text/html; charset=utf-8' },
          status: 503,
        },
      )),
    );
    return;
  }

  if (url.pathname.startsWith(STATIC_PREFIX)) {
    event.respondWith(
      caches.open(CACHE_NAME).then(async (cache) => {
        const cached = await cache.match(request);
        const network = fetch(request)
          .then((response) => {
            if (response.ok) cache.put(request, response.clone());
            return response;
          })
          .catch(() => cached);
        return cached || network;
      }),
    );
  }
});

self.addEventListener('push', (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch (error) {
    payload = {
      title: '新通知',
      body: event.data ? event.data.text() : '',
    };
  }

  const title = payload.title || '新通知';
  const options = {
    body: payload.body || '',
    icon: '/static/dist/pwa-icon.svg',
    tag: payload.tag || 'team-project-notification',
    data: {
      url: payload.url || '/',
    },
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const requestedUrl = event.notification.data?.url || '/';
  const targetUrl = new URL(requestedUrl, self.location.origin);
  if (targetUrl.origin !== self.location.origin) {
    targetUrl.href = new URL('/', self.location.origin).href;
  }

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true })
      .then(async (windowClients) => {
        const existingClient = windowClients.find((client) =>
          new URL(client.url).origin === targetUrl.origin,
        );
        if (existingClient) {
          if (typeof existingClient.navigate === 'function') {
            await existingClient.navigate(targetUrl.href);
          }
          return existingClient.focus();
        }
        return self.clients.openWindow(targetUrl.href);
      }),
  );
});
