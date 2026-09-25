# 웹 점검 edge-1: 서비스 워커가 캐시해 둔 앱 자리('./index.html')를 다른 파일로 덮지 않는다
#  - 같은 도메인의 다른 파일(og.png·yt.html·manifest·ads.txt·.well-known·아이콘)을 주소창으로 열어도 앱 자리는 앱 그대로이고,
#    오프라인·약한 와이파이(4초 뒤 캐시)에서도 앱이 열린다. 그 파일들은 서비스 워커가 손대지 않고 네트워크에서 그대로 뜬다
#  - 앱 주소(/ · /?… · /index.html)로 열면 여전히 캐시를 새로 적는다 (네트워크 우선은 그대로)
#  - 옛 캐시(conti-shell-v4 — 앱 자리가 망가진 채 남아 있을 수 있다)는 새 서비스 워커가 켜질 때 지워진다
import os, sys, time
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
ROOT = URL.split('#')[0].split('?')[0].rstrip('/') + '/'
SHELL_KEY = ROOT + 'index.html'
OTHERS = ['og.png', 'yt.html', 'manifest.webmanifest', 'ads.txt', '.well-known/assetlinks.json',
          '.well-known/apple-app-site-association', 'icon-512.png']


def fail(msg):
    print('FAIL:', msg); sys.exit(1)


def shell(pg):
    # 주소가 /.well-known/… 인 쪽에서도 같은 칸을 보도록 절대 주소로 찾는다
    return pg.evaluate("""async(k)=>{const ks=await caches.keys();const r=await caches.match(k);
      if(!r)return {ks};const t=await r.clone().text();
      return {ks,type:r.headers.get('content-type')||'',len:t.length,url:r.url,app:t.indexOf('<title>1414 — 찬양팀 콘티')>=0}}""", SHELL_KEY)


def shell_ok(info):
    return bool(info.get('app')) and 'text/html' in info.get('type', '')


def run():
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 1180, 'height': 820})
        errs = []

        # ---------- 옛 캐시: 망가진 앱 자리가 든 conti-shell-v4 를 먼저 만들어 둔다 (서비스 워커가 아직 없을 때) ----------
        seed = ROOT + '__swseed'
        ctx.route(seed, lambda r: r.fulfill(status=200, body='<title>seed</title>', headers={'content-type': 'text/html'}))
        pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto(seed)
        pg.evaluate("""async(k)=>{const c=await caches.open('conti-shell-v4');
          await c.put(k,new Response('<title>1414 영상</title>',{headers:{'content-type':'text/html'}}))}""", SHELL_KEY)
        ctx.unroute(seed)

        # 앱을 열면 서비스 워커가 깔리고 켜진다 → 옛 캐시는 지워지고 앱 자리는 진짜 앱이다
        pg.goto(URL); pg.wait_for_selector('#lgUser', timeout=15000)
        pg.wait_for_function("navigator.serviceWorker&&navigator.serviceWorker.controller", timeout=15000)
        pg.wait_for_timeout(800)
        info = shell(pg)
        if 'conti-shell-v4' in info['ks']: fail('옛 캐시(conti-shell-v4)가 남아 있음: %s' % info['ks'])
        if not shell_ok(info): fail('서비스 워커가 켜진 뒤 앱 자리가 앱이 아님: %s' % {k: info.get(k) for k in ('ks', 'type', 'len', 'url')})
        print('old cache dropped ok (%s)' % ', '.join(info['ks']))

        # ---------- 다른 파일을 주소창으로 열어도 앱 자리는 그대로 ----------
        probe = ctx.new_page()   # 캐시는 이 탭(앱이 아닌 같은 도메인 화면 — v 가 없는 yt.html 은 아무것도 안 한다)에서 본다
        probe.goto(ROOT + 'yt.html')
        for f in OTHERS:
            pg2 = ctx.new_page()
            res = None
            try: res = pg2.goto(ROOT + f, wait_until='load', timeout=10000)
            except Exception as e:
                # 개발 서버는 ads.txt·AASA 를 내려받기로 준다 — 그래도 요청은 서비스 워커를 거친다
                if 'Download is starting' not in str(e): fail('%s 열기 실패: %s' % (f, e))
            pg2.wait_for_timeout(600)
            if res is not None and res.from_service_worker: fail('%s 를 서비스 워커가 가로채 줌 (앱 파일이 아님)' % f)
            if f == 'yt.html' and pg2.title() != '1414 영상': fail('yt.html 을 열었는데 다른 화면이 뜸: %s' % pg2.title())
            info = shell(probe)
            if not shell_ok(info): fail('%s 를 연 뒤 앱 자리가 바뀜: %s' % (f, {k: info.get(k) for k in ('type', 'len', 'url')}))
            pg2.close()
        print('other files keep shell ok (%d)' % len(OTHERS))

        # ---------- 앱 주소로 열면 캐시를 새로 적는다 ----------
        for q in ('?swcheck=1#/home', 'index.html?swcheck=2'):
            pg.goto(ROOT + q); pg.wait_for_function('window.CONTI', timeout=15000)
            want = (ROOT + q).split('#')[0]
            for _ in range(30):
                info = shell(probe)
                if info.get('url') == want: break
                pg.wait_for_timeout(200)
            if info.get('url') != want or not shell_ok(info): fail('앱 주소(%s)로 열었는데 캐시를 새로 적지 않음: %s' % (q, info.get('url')))
        print('shell refresh ok')

        # 앱 자리를 새로 적은 뒤에 다시 다른 파일을 열어 둔다 (마지막으로 연 것이 앱이 아니게)
        for f in ('og.png', 'yt.html'):
            pg2 = ctx.new_page(); pg2.goto(ROOT + f); pg2.wait_for_timeout(600); pg2.close()

        # ---------- 약한 와이파이: 페이지 요청이 안 끝나면 4초 뒤 캐시로 — 그게 앱이어야 한다 ----------
        hung = []
        ctx.route(lambda u: u.split('#')[0] in (ROOT, ROOT + 'index.html'), lambda r: hung.append(r))
        slow = ctx.new_page(); slow.on('pageerror', lambda e: errs.append(str(e)))
        t0 = time.time()
        try:
            slow.goto(ROOT + '#/home', wait_until='commit', timeout=15000)
            slow.wait_for_function('window.CONTI', timeout=10000)
        except Exception: fail('페이지 요청이 걸려 있는 동안 캐시로 앱이 열리지 않음 (title=%r)' % slow.title())
        if not hung: print('  (이 Playwright 는 서비스 워커의 요청을 가로채지 못해 느린 네트워크는 건너뜀)')
        else: print('slow network -> app from cache ok (%.1fs)' % (time.time() - t0))
        for r in hung:
            try: r.abort()
            except Exception: pass
        slow.close()
        ctx.unroute_all(behavior='ignoreErrors')

        # ---------- 오프라인: 앱이 열린다 ----------
        ctx.set_offline(True)
        off = ctx.new_page(); off.on('pageerror', lambda e: errs.append(str(e)))
        try:
            off.goto(ROOT + '#/home', timeout=15000)
            off.wait_for_function("typeof window.CONTI==='object'", timeout=10000)
        except Exception as e: fail('다른 파일을 연 뒤 오프라인에서 앱이 안 열림 (title=%r): %s' % (off.title(), str(e).splitlines()[0]))
        if '1414' not in off.title() or '영상' in off.title(): fail('오프라인 제목이 앱이 아님: %r' % off.title())
        print('offline app ok')
        ctx.set_offline(False)

        if errs: fail('page errors: %s' % errs[:5])
        ctx.close(); b.close()
    print('WEBFIX SW TEST OK')


if __name__ == '__main__':
    run()
