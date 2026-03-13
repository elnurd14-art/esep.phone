# ESEP Analytics — PWA

Приложение аналитики для ресторанов. Работает как PWA (Progressive Web App).

## Установка на телефон

1. Открыть ссылку в Chrome на Android
2. Нажать "Добавить на главный экран"
3. Готово — иконка появится на рабочем столе

## Структура файлов

```
index.html          — основное приложение
manifest.json       — конфигурация PWA
sw.js               — service worker (офлайн кеш)
icon-192.png        — иконка 192x192
icon-512.png        — иконка 512x512
apple-touch-icon.png — иконка для iOS
favicon.png         — иконка 32x32
```

## Деплой на GitHub Pages

1. Создать репозиторий на GitHub
2. Загрузить все файлы
3. Settings → Pages → Branch: main → Save
4. Через 2-3 минуты доступно на: https://USERNAME.github.io/REPO
