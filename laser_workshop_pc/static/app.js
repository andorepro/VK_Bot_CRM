// Базовый JS для PWA
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js')
        .then(() => console.log('Service Worker registered'));
}

console.log('Laser Workshop CRM loaded');
