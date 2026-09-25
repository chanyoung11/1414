/* 콘티 service worker — 오프라인 지원.
   index.html: 네트워크 우선(새 버전 자동 반영), 실패 시 캐시.  나머지 같은 도메인 파일: 캐시 우선.  /api/ 는 절대 캐시하지 않음. */
// v4: 오류 응답은 캐시하지 않는다(오프라인에서 오류 페이지가 뜨던 문제)
// v5: 앱 자리에 다른 파일(og.png·yt.html 등)이 들어간 캐시를 버리고 새로 받는다
const CACHE = 'conti-shell-v5';
const SHELL = ['./', './index.html', './manifest.webmanifest', './icon-180.png', './icon-512.png', './favicon-32.png', './favicon-16.png'];
self.addEventListener('install', e => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())); });
self.addEventListener('activate', e => { e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener('fetch', e => {
  const req = e.request; if (req.method !== 'GET') return;
  const url = new URL(req.url); if (url.origin !== location.origin) return;
  if (url.pathname.startsWith('/api/') || url.pathname === '/api') return;
  // 앱 화면은 첫 화면 주소(/ · /index.html) 하나뿐이다. 전에는 주소창으로 연 파일이면 무엇이든(og.png·yt.html·manifest·ads.txt·.well-known)
  // 앱 자리('./index.html')에 넣어, 그걸 한 번 열고 나면 오프라인·약한 와이파이(4초 뒤)에 앱 대신 그 파일이 떴다
  const root = self.location.pathname.replace(/sw\.js$/, '');
  const isPage = url.pathname === root || url.pathname === root + 'index.html';
  if (!isPage && req.mode === 'navigate') return;   // 다른 파일을 여는 것은 손대지 않는다 (네트워크 그대로)
  if (isPage) {
    // 약한 와이파이·교회 포털에서는 네트워크가 끝없이 붙잡고 있어 흰 화면이 1분씩 갔다.
    // 캐시가 있으면 4초만 기다리고 캐시로 연다. 늦게 온 응답은 뒤에서 캐시에 넣어 다음에 쓴다 (HTML 일 때만 — 앱 자리를 다른 것이 덮지 않게)
    const net = fetch(req).then(res => { if (res && res.ok && /text\/html/i.test(res.headers.get('content-type') || '')) { const copy = res.clone(); caches.open(CACHE).then(c => { c.put('./index.html', copy); }); } return res; });
    e.respondWith(new Promise(resolve => {
      let done = false; const fin = r => { if (!done && r) { done = true; resolve(r); } };
      const t = setTimeout(() => caches.match('./index.html').then(fin), 4000);
      net.then(r => { clearTimeout(t); fin(r); })
        .catch(() => { clearTimeout(t); caches.match('./index.html').then(hit => fin(hit || Response.error())); });
    }));
    e.waitUntil(net.catch(() => {}));
    return;
  }
  e.respondWith(caches.match(req).then(hit => hit || fetch(req).then(res => { if (res && res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); } return res; })));
});

/* ---------- 푸시 알림 ---------- */
self.addEventListener('push', e => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch (err) { d = { title: '1414', body: e.data ? e.data.text() : '' }; }
  const title = d.title || '1414';
  e.waitUntil(self.registration.showNotification(title, {
    body: d.body || '',
    icon: './icon-180.png',
    badge: './favicon-32.png',
    tag: d.tag || d.type || 'conti',
    renotify: true,
    data: { link: d.link || '#/home', teamId: d.teamId || '' }
  }));
});
// 링크는 팀 안 주소다(#/view/…). 여러 팀에 있는 사람이 다른 팀 알림을 누르면 지금 팀에서 열려
// 엉뚱한 팀에 답하거나 '발행된 콘티가 없어요'가 떴다 → 알림의 팀을 화면에 넘겨 그 팀으로 바꾼 뒤 연다
self.addEventListener('notificationclick', e => {
  e.notification.close();
  const data = e.notification.data || {};
  const link = data.link || '#/home', team = data.teamId || '';
  // 새로 여는 창은 주소의 ?team= 으로 팀을 안다 (화면이 켜질 때 읽고 지운다)
  const base = self.location.origin + self.location.pathname.replace(/sw\.js$/, '') + (team ? '?team=' + encodeURIComponent(team) : '');
  const url = new URL(link.replace(/^#\/?/, '#/'), base).href;
  e.waitUntil(clients.matchAll({ type: 'window', includeUncontrolled: true }).then(async list => {
    const c = list.find(x => x.url.indexOf(self.location.origin) === 0 && 'focus' in x);
    if (!c) return clients.openWindow(url);
    // 이미 열려 있는 창이 있으면 그 창에 알린다. 답이 없으면(메시지를 모르는 예전 화면) 주소로 옮긴다 —
    // ?team= 이 붙은 주소라 새로 열리며 팀을 바꾼다
    await c.focus().catch(() => {});
    const ok = await new Promise(res => {
      const ch = new MessageChannel(); const t = setTimeout(() => res(false), 1500);
      ch.port1.onmessage = () => { clearTimeout(t); res(true); };
      try { c.postMessage({ type: 'push-open', link, teamId: team }, [ch.port2]); } catch (err) { clearTimeout(t); res(false); }
    });
    if (!ok && c.navigate) return c.navigate(url).catch(() => clients.openWindow(url));
  }));
});
