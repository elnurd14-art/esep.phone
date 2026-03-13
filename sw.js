// ESEP PWA Service Worker
const CACHE = 'esep-v1';
const ASSETS = [
  './',
  './index.html',
  './manifest.json',
  './icon-192.png',
  './icon-512.png',
  './apple-touch-icon.png',
  'https://telegram.org/js/telegram-web-app.js',
  'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap'
];

// Установка — кешируем все файлы приложения
self.addEventListener('install', function(e) {
  e.waitUntil(
    caches.open(CACHE).then(function(cache) {
      // Кешируем основные файлы, игнорируем ошибки внешних ресурсов
      return Promise.allSettled(
        ASSETS.map(function(url) {
          return cache.add(url).catch(function() {});
        })
      );
    })
  );
  self.skipWaiting();
});

// Активация — удаляем старые кеши
self.addEventListener('activate', function(e) {
  e.waitUntil(
    caches.keys().then(function(keys) {
      return Promise.all(
        keys.filter(function(k) { return k !== CACHE; })
            .map(function(k) { return caches.delete(k); })
      );
    })
  );
  self.clients.claim();
});

// Запросы — сначала сеть, при ошибке кеш (Network First)
self.addEventListener('fetch', function(e) {
  // Supabase запросы всегда идут в сеть (данные должны быть актуальными)
  if (e.request.url.includes('supabase.co')) {
    return; // без кеша
  }

  e.respondWith(
    fetch(e.request)
      .then(function(response) {
        // Кешируем успешные ответы
        if (response && response.status === 200 && response.type === 'basic') {
          var clone = response.clone();
          caches.open(CACHE).then(function(cache) {
            cache.put(e.request, clone);
          });
        }
        return response;
      })
      .catch(function() {
        // Нет сети — берём из кеша
        return caches.match(e.request).then(function(cached) {
          return cached || caches.match('./index.html');
        });
      })
  );
});
