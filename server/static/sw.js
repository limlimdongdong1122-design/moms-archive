// 서비스 워커: 앱 셸을 캐시해 오프라인에서도 화면이 뜨게 한다.
// API(/api/*)는 항상 최신이 필요하므로 캐시하지 않고 네트워크로 보낸다.
const CACHE = 'bhist-v1';
const SHELL = [
  '/', '/index.html', '/manifest.webmanifest',
  '/icons/icon-192.png', '/icons/icon-512.png'
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (url.pathname.startsWith('/api/')) return; // 기본 네트워크 처리
  e.respondWith(caches.match(e.request).then((r) => r || fetch(e.request)));
});
