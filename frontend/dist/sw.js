/* FamilyRoots Service Worker — handles Web Push notifications */

self.addEventListener('push', function (event) {
  let payload = { title: 'FamilyRoots', body: '', data: {} };
  try {
    if (event.data) payload = event.data.json();
  } catch (_) {}

  const title = payload.title || 'FamilyRoots';
  const options = {
    body: payload.body || '',
    icon: '/favicon.svg',
    badge: '/favicon.svg',
    data: payload.data || {},
    tag: payload.data?.type || 'familyroots',
    renotify: true,
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', function (event) {
  event.notification.close();
  const data = event.notification.data || {};
  const url = data.url || (data.tree_id ? `/trees/${data.tree_id}` : '/dashboard');
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
      for (const client of windowClients) {
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          client.navigate(url);
          return client.focus();
        }
      }
      return clients.openWindow(url);
    })
  );
});
