# 배너 광고 검사 — 앱(애드몹) 배너 자리·숨기기·다시 보이기 · 웹(애드센스)은 꺼 둠 (2026-09-25 배너 위치 점검)
#
# 사용: CONTI_URL=http://localhost:8766/ .venv/bin/python tests/test_banner.py   (개발 서버가 떠 있어야 한다)
#
# 앱은 https://localhost 를 흉내 내고(NATIVE) 가짜 AdMob 을 넣는다. 가짜는 플러그인(@capacitor-community/admob 8)의
# 플랫폼별 움직임을 그대로 따른다:
#  · 아이폰: showBanner 는 새 뷰를 만들고 광고가 들어온 순간에야 화면에 붙인다(그 전에는 hide·remove 가 못 찾음) ·
#    들어오면 SizeChanged+Loaded · hide 는 붙은 뷰를 숨김 · resume 은 붙은 뷰가 없으면 거절 · remove 는 붙은 뷰만 뗀다
#  · 안드로이드: showBanner 는 뷰가 있으면 광고만 다시 받는다(보이게 하지 않음) · hide 는 GONE+pause · resume 만 VISIBLE ·
#    remove 는 뷰를 없앤다 · 못 받으면 뷰를 없애고 FailedToLoad · 광고를 만들 때 폭으로 가운데를 맞춘다
# 광고는 __ad.delay ms 뒤에 들어온다.
#
# 본다
#  1 웹: 광고 스위치(WEBADS.on)가 꺼져 있으면 승인된 주소·무료 플랜이라도 자리(.webad)·여백·스크립트·요청이 없다 · 켜면 코드는 그대로 돈다
#  2 아이폰 늦은 배너: 광고가 오기 전에 무대·메모 창·폰 건반을 열거나 연습 화면을 떠나면 늦게 온 배너를 곧바로 숨기고 hasad 를 안 붙인다 ·
#    Loaded 전에는 ADSTATE.on·hasad 가 없다 · 닫으면 resume 으로 다시 보인다 (새로 받지 않음)
#  3 안드로이드: 숨긴 뒤 다시 보일 때 resumeBanner (여러 번 해도 보임) · 받는 중에 내리면 removeBanner → 다음에 새로 · 못 받으면 빈 띠 없음
#  4 크기: 폰은 가로에서도 BANNER · 태블릿(짧은 변 600 이상, 폭 728 이상)만 LEADERBOARD · 돌리면 걷고 새 크기·자리로 다시 ·
#    키보드처럼 높이만 바뀌면 그대로 · 아이폰에서 받는 중에 돌려도 배너가 둘이 되지 않는다
#  5 폰 건반: 여는 동안 배너를 내리고 닫거나 메트로놈으로 바꾸면 다시 · 태블릿 건반은 그대로
#  6 폰: 배너 위 8px 여백
#  늘: 보이는 배너 ⇔ body.hasad (빈 띠도, 본문을 덮는 배너도 없다)
import os, sys, time
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
SRV = urlparse(URL)
tag = str(int(time.time()))[-6:]
N = {'n': 0}
SOFT = os.environ.get('SOFT') == '1'   # 고치기 전 코드에서 전부 재현해 볼 때: 실패해도 끝까지 간다
FAILS = []
def fail(m):
  print('FAIL:', m)
  if SOFT: FAILS.append(m); return
  sys.exit(1)

MOCK = r"""
(() => {
  const PLAT = '__PLAT__';
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const L = {};
  const H = { BANNER: 50, LEADERBOARD: 90 }, W = { BANNER: 320, LEADERBOARD: 728 };
  let seq = 0;
  const ad = window.__ad = { plat: PLAT, delay: 900, fill: true, log: [], shows: 0, maxAttached: 0,
    ios: { cur: null, attached: [] }, and: { v: null } };
  // 웹뷰만 다시 불러온 흉내: 네이티브 배너 뷰는 앞 페이지 것이 남아 있다 (sessionStorage 로 넘긴다)
  try { const pre = sessionStorage.getItem('__adPre'); if (pre && PLAT === 'android') { sessionStorage.removeItem('__adPre'); ad.and.v = { id: 999, size: 'BANNER', hidden: pre === 'hidden', loaded: true, w: innerWidth }; ad.log.push('pre:' + pre); } } catch (e) {}
  const emit = (n, d) => { ad.log.push('ev:' + n + (d && 'height' in d ? ':' + d.height : '')); (L[n] || []).slice().forEach((f) => f(d)); };
  // 지금 화면에 광고가 보이나 · 어떤 크기 · 가운데인가(안드로이드는 만든 때의 폭으로 맞춘다)
  ad.view = () => PLAT === 'ios' ? (ad.ios.attached[0] || ad.ios.cur) : ad.and.v;
  ad.visible = () => {
    if (PLAT === 'ios') return ad.ios.attached.some((v) => !v.hidden);
    const v = ad.and.v; return !!(v && !v.hidden && v.loaded);
  };
  ad.size = () => { const v = PLAT === 'ios' ? ad.ios.attached.find((x) => !x.hidden) : ad.and.v; return v ? v.size : null; };
  ad.centered = () => { const v = ad.and.v; if (PLAT === 'ios' || !v) return true; return Math.abs(v.w - innerWidth) <= 2; };
  ad.fits = () => { const s = ad.size(); return !s || W[s] <= innerWidth; };
  let AdMob;
  if (PLAT === 'ios') {
    const I = ad.ios;
    const tagged = () => I.attached[0];
    const removeTagged = () => { const s = tagged(); if (s) { if (I.cur) I.cur.delegate = false; I.attached.splice(I.attached.indexOf(s), 1); } };
    const receive = (v) => {
      if (!v.delegate) return;
      if (!ad.fill) { removeTagged(); emit('bannerAdSizeChanged', { width: 0, height: 0 }); emit('bannerAdFailedToLoad', { code: 0, message: 'No fill' }); return; }
      if (!I.attached.includes(v)) I.attached.push(v);
      ad.maxAttached = Math.max(ad.maxAttached, I.attached.length);
      v.loaded = true;
      emit('bannerAdSizeChanged', { width: W[v.size], height: H[v.size] }); emit('bannerAdLoaded', {});
    };
    AdMob = {
      showBanner: async (o) => {
        ad.shows++; ad.log.push('show:' + o.adSize);
        const v = { id: ++seq, size: o.adSize, hidden: false, loaded: false, delegate: true };
        I.cur = v; removeTagged(); v.delegate = true;
        setTimeout(() => receive(v), ad.delay);
        await sleep(5);
      },
      hideBanner: async () => { ad.log.push('hide'); await sleep(5); const s = tagged(); if (s) s.hidden = true; emit('bannerAdSizeChanged', { width: 0, height: 0 }); },
      resumeBanner: async () => { ad.log.push('resume'); await sleep(5); const s = tagged(); if (!s) throw new Error('AdMob: not find subView for resumeBanner');
        s.hidden = false; emit('bannerAdSizeChanged', { width: W[s.size], height: H[s.size] }); },
      removeBanner: async () => { ad.log.push('remove'); await sleep(5); removeTagged(); },
    };
  } else {
    const A = ad.and;
    const load = (v) => setTimeout(() => {
      if (v !== A.v) return;   // 걷었거나 바뀐 뷰의 늦은 소식은 버린다 (플러그인도 그렇다)
      if (!ad.fill) { A.v = null; emit('bannerAdSizeChanged', { width: 0, height: 0 }); emit('bannerAdFailedToLoad', { code: 3, message: 'No fill' }); return; }
      v.loaded = true; emit('bannerAdSizeChanged', { width: W[v.size], height: H[v.size] }); emit('bannerAdLoaded', {});
    }, ad.delay);
    AdMob = {
      showBanner: async (o) => {
        ad.shows++; ad.log.push('show:' + o.adSize);
        await sleep(5);
        if (A.v) { ad.log.push('reload'); load(A.v); return new Promise(() => {}); }   // 이미 있는 뷰: 광고만 다시 받고 보이게 하지 않으며, 플러그인처럼 끝내 주지도 않는다
        A.v = { id: ++seq, size: o.adSize, hidden: false, loaded: false, w: innerWidth }; load(A.v);
      },
      hideBanner: async () => { ad.log.push('hide'); await sleep(5); if (!A.v) throw new Error('You tried to hide a banner that was never shown');
        A.v.hidden = true; emit('bannerAdSizeChanged', { width: 0, height: 0 }); },
      resumeBanner: async () => { ad.log.push('resume'); await sleep(5); const v = A.v; if (v) { v.hidden = false; emit('bannerAdSizeChanged', { width: W[v.size], height: H[v.size] }); } },
      removeBanner: async () => { ad.log.push('remove'); await sleep(5); if (A.v) { A.v = null; emit('bannerAdSizeChanged', { width: 0, height: 0 }); } },
    };
  }
  Object.assign(AdMob, {
    trackingAuthorizationStatus: async () => ({ status: 'authorized' }), requestTrackingAuthorization: async () => ({}),
    initialize: async () => {}, requestConsentInfo: async () => ({ status: 'NOT_REQUIRED' }), showConsentForm: async () => {},
    addListener: async (name, fn) => { (L[name] = L[name] || []).push(fn); return { remove: async () => { L[name] = (L[name] || []).filter((f) => f !== fn); } }; },
  });
  window.Capacitor = {
    getPlatform: () => PLAT, isNativePlatform: () => true, isPluginAvailable: () => false,
    Plugins: {
      AdMob,
      App: { addListener: () => Promise.resolve({ remove() {} }), getLaunchUrl: () => Promise.resolve(undefined), exitApp() {}, getInfo: () => Promise.resolve({}) },
      SplashScreen: { hide: () => Promise.resolve() },
    },
  };
})();
"""

def run():
  with sync_playwright() as p:
    b = p.chromium.launch(); errs = []

    def native(plat, vw, vh, sw, sh):
      c = b.new_context(viewport={'width': vw, 'height': vh}, screen={'width': sw, 'height': sh}, service_workers='block')
      def handler(route):
        u = urlparse(route.request.url)
        if u.scheme == 'https' and u.hostname in ('localhost', 'lets1414.com', 'www.lets1414.com') and u.port is None:
          try: return route.fulfill(response=route.fetch(url='%s://%s/%s' % (SRV.scheme, SRV.netloc, u.path.lstrip('/')) + ('?' + u.query if u.query else '')))
          except Exception:
            try: return route.abort()
            except Exception: return
        if u.hostname == SRV.hostname and u.port == SRV.port: return route.continue_()
        return route.abort()   # 바깥(글꼴 CDN·광고)은 막는다
      c.route('**/*', handler)
      c.add_init_script(MOCK.replace('__PLAT__', plat))
      pg = c.new_page()
      pg.on('pageerror', lambda e: errs.append('%s: %s' % (plat, e))); pg.on('dialog', lambda d: d.accept())
      pg.goto('https://localhost/')
      if not pg.evaluate('/^(capacitor|ionic):/.test(location.protocol)||(location.hostname==="localhost"&&!location.port&&location.protocol==="https:")'): fail('앱 흉내가 안 됨 (NATIVE 아님)')
      signup(pg, plat)
      return c, pg

    def signup(pg, who):
      N['n'] += 1
      pg.wait_for_selector('#lgUser', timeout=15000)
      pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName'); pg.check('#lgAgree')
      pg.fill('#lgName', '배너'); pg.fill('#lgUser', 'bn%s%d' % (tag, N['n'])); pg.fill('#lgPass', 'secret12'); pg.click('[data-act="lg-submit"]')
      pg.wait_for_selector('#gtTeam', timeout=15000); pg.fill('#gtTeam', '배너팀%s%d' % (tag, N['n'])); pg.click('[data-act="team-create"]')
      pg.wait_for_selector('.shell[data-page]', timeout=15000)
      pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]', timeout=8000)
      pg.fill('[data-f="svc.name"]', '배너 예배'); pg.click('[data-act="add-item"]'); pg.wait_for_selector('[data-f="item.title"]')
      pg.fill('[data-f="item.title"]', '첫 곡'); pg.wait_for_timeout(500)
      if pg.evaluate("(CONTI.S.team.plan||'free')") != 'free': fail('무료 팀이 아님')

    def play(pg):
      sid = pg.evaluate("CONTI.S.services[0].id")
      pg.evaluate("(x)=>{location.hash=x}", '#/play/' + sid); pg.wait_for_selector('[data-act="metro"]', timeout=10000)
    def home(pg):
      pg.evaluate("()=>{location.hash='#/home'}"); pg.wait_for_timeout(300)

    ST = """(()=>{const v=__ad.visible(),h=document.body.classList.contains('hasad');
      return {vis:v,hasad:h,on:CONTI.ADSTATE.on,view:CONTI.ADSTATE.view,size:__ad.size(),centered:__ad.centered(),fits:__ad.fits(),
        attached:__ad.ios.attached.length,maxAttached:__ad.maxAttached,shows:__ad.shows,log:__ad.log.slice(-8),route:CONTI.route().name}})()"""
    def st(pg): return pg.evaluate(ST)
    # 보이는 배너 ⇔ hasad — 빈 띠(hasad 만)도, 본문을 덮는 배너(배너만)도 안 된다
    def settled(pg, label, want_vis, ms=None):
      pg.wait_for_timeout(ms if ms is not None else pg.evaluate('__ad.delay') + 400)
      s = st(pg)
      if s['vis'] != want_vis: fail('%s: 배너가 %s 이어야 하는데 %s — %s' % (label, '보임' if want_vis else '안 보임', '보임' if s['vis'] else '안 보임', s))
      if s['hasad'] != s['vis'] or s['on'] != s['vis']: fail('%s: 보이는 배너와 hasad·ADSTATE.on 이 어긋남(빈 띠 또는 가림) — %s' % (label, s))
      if not s['fits'] or not s['centered']: fail('%s: 배너가 화면 밖으로 나가거나 가운데가 아님 — %s' % (label, s))
      if s['maxAttached'] > 1: fail('%s: 아이폰 배너 뷰가 둘 붙음 — %s' % (label, s))
      return s
    def fresh(pg, js=None):
      # 새로 연 앱: 연습 화면 주소 그대로 다시 불러 광고를 처음부터 받게 한다 (js: 광고가 들어오기 전에 가짜에 줄 설정)
      pg.reload(); pg.wait_for_selector('[data-act="metro"]', timeout=15000)
      pg.wait_for_function("__ad.log.some(x=>x.startsWith('show:'))", timeout=10000)
      if js: pg.evaluate(js)
      s = st(pg)
      if s['hasad'] or s['on']: fail('광고가 오기 전인데 hasad·ADSTATE.on 이 켜짐 — %s' % s)
    def memo_open(pg):
      pg.evaluate("CONTI.modal('<div class=\"pad\"><textarea id=\"memoTxt\"></textarea><button class=\"btn pri\" id=\"memoSave\">저장</button></div>',{sheet:true})")
      pg.wait_for_selector('#memoSave')
    def memo_close(pg): pg.evaluate("CONTI.closeModal()")
    def stage_open(pg):
      pg.evaluate("CONTI.stageOpen(CONTI.S.services[0],0)"); pg.wait_for_selector('#stageWrap', timeout=10000)
    def stage_close(pg):
      pg.evaluate("CONTI.stageExit()"); pg.wait_for_selector('[data-act="metro"]', timeout=10000)
    def piano_open(pg):
      pg.click('[data-act="piano"]'); pg.wait_for_selector('#sidetool.on #pkeys')
    def tool_close(pg):
      pg.click('[data-act="sidetool-close"]'); pg.wait_for_timeout(300)
    def gap(pg):
      return pg.evaluate("""(()=>{const a=document.getElementById('app'),on=document.body.classList.contains('hasad');
        const with_=parseFloat(getComputedStyle(a).paddingBottom);document.body.classList.remove('hasad');
        const without=parseFloat(getComputedStyle(a).paddingBottom);if(on)document.body.classList.add('hasad');
        return {with_,without,adh:parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--adh'))}})()""")

    # ================= 1 웹: 애드센스는 스위치로 꺼 둠 =================
    c = b.new_context(viewport={'width': 1300, 'height': 950}, service_workers='block')
    adreq = []
    def web_handler(route):
      u = route.request.url
      if any(k in u for k in ('googlesyndication', 'doubleclick', 'adservice', 'adsbygoogle', 'googleads')):
        adreq.append(u); return route.abort()
      h = urlparse(u).hostname
      if h == SRV.hostname: return route.continue_()
      return route.abort()
    c.route('**/*', web_handler)
    pg = c.new_page(); pg.on('pageerror', lambda e: errs.append('web: %s' % e)); pg.on('dialog', lambda d: d.accept())
    pg.goto(URL); signup(pg, 'web')
    if pg.evaluate("CONTI.WEBADS.on") is not False: fail('웹 광고 스위치(WEBADS.on)가 기본으로 꺼져 있지 않음')
    # 운영 주소인 것처럼(승인된 주소 · 무료 플랜) 해도 스위치가 꺼져 있으면 아무것도 없다
    pg.evaluate("()=>{CONTI.AD_HOSTS.add(location.hostname);CONTI.S.team.plan='free';CONTI.render()}")
    play(pg); pg.wait_for_timeout(1200)
    if pg.evaluate("CONTI.webAdsAllowed()"): fail('스위치가 꺼졌는데 웹 광고를 허락함')
    w = pg.evaluate("""(()=>({slot:document.querySelectorAll('.webad,ins.adsbygoogle').length,script:document.querySelectorAll('script[src*="googlesyndication"],script[src*="adsbygoogle"]').length,
      g:typeof window.adsbygoogle,media:(()=>{const m=document.querySelector('.panel.media');return m?[...m.children].map(e=>e.className).join('|'):null})()}))()""")
    if w['slot'] or w['script'] or w['g'] != 'undefined': fail('스위치가 꺼졌는데 광고 자리·스크립트가 있음: %s' % w)
    if adreq: fail('스위치가 꺼졌는데 광고 요청이 나감: %s' % adreq[:3])
    # 다른 화면들도
    for h in ['#/home', '#/library', '#/cal']:
      pg.evaluate("(x)=>{location.hash=x}", h); pg.wait_for_timeout(700)
      if pg.locator('.webad').count() or adreq: fail('스위치가 꺼졌는데 %s 에 광고: %s' % (h, adreq[:3]))
    # 코드는 그대로 — 켜면 연습 화면에 자리가 생기고 스크립트를 부른다 (여기서는 막는다)
    pg.evaluate("()=>{CONTI.WEBADS.on=true}"); play(pg); pg.wait_for_timeout(1200)
    if not pg.evaluate("CONTI.webAdsAllowed()") or not pg.locator('.webad').count(): fail('스위치를 켰는데 웹 광고 코드가 안 돎')
    if not any('adsbygoogle' in u for u in adreq): fail('스위치를 켰는데 애드센스 스크립트를 안 부름: %s' % adreq)
    c.close()
    print('1 웹: 스위치 꺼짐(기본) → 자리·스크립트·요청 없음 · 켜면 코드 그대로 ok')

    # ================= 2 아이폰 폰: 늦게 온 배너 =================
    c, pg = native('ios', 390, 844, 390, 844)
    play(pg)
    s = settled(pg, '아이폰 연습 화면', True)
    if s['size'] != 'BANNER': fail('아이폰 폰 크기가 BANNER 가 아님: %s' % s)
    g = gap(pg)
    if abs((g['with_'] - g['without']) - (g['adh'] + 8)) > 0.6 or g['adh'] != 50: fail('6 폰 배너 위 8px 여백이 없음: %s' % g)
    print('아이폰 연습 화면 → 받은 뒤 보임 · BANNER · 배너 위 8px ok', g)
    for label, opn, cls in [('무대', stage_open, stage_close), ('메모 창', memo_open, memo_close), ('폰 건반', piano_open, tool_close)]:
      fresh(pg)
      opn(pg)
      s = settled(pg, '2 아이폰: 광고가 오기 전에 %s 열기' % label, False)
      if s['view'] != 'ready' or 'ev:bannerAdLoaded' not in s['log']: fail('%s: 광고가 안 들어온 채로 끝남 (검사가 늦은 배너를 못 만듦) %s' % (label, s))
      shows = s['shows']
      cls(pg)
      s = settled(pg, '2 아이폰: %s 닫기' % label, True, 700)
      if s['shows'] != shows or 'resume' not in s['log']: fail('%s 닫은 뒤 숨긴 배너를 다시 보이지(resume) 않고 새로 받음: %s' % (label, s))
      print('2 아이폰: 광고가 오기 전에 %s → 늦은 배너 곧바로 숨김 · hasad 없음 → 닫으면 resume 으로 보임 ok' % label)
    fresh(pg); home(pg)
    settled(pg, '2 아이폰: 광고가 오기 전에 연습 화면을 떠남', False)
    play(pg); settled(pg, '2 아이폰: 연습 화면으로 돌아옴', True, 700)
    print('2 아이폰: 광고가 오기 전에 연습 화면을 떠남 → 숨김 · 돌아오면 보임 ok')
    # 5 폰 건반: 떠 있는 배너를 내리고 · 메트로놈으로 바꾸면 다시 · 닫으면 그대로
    piano_open(pg); settled(pg, '5 아이폰 폰 건반 열기', False, 500)
    pg.click('[data-act="metro"]'); pg.wait_for_selector('#sidetool.on #metBpm')
    settled(pg, '5 건반 → 메트로놈', True, 600)
    tool_close(pg); settled(pg, '5 메트로놈 닫기', True, 400)
    piano_open(pg); settled(pg, '5 건반 다시', False, 500)
    tool_close(pg); settled(pg, '5 건반 닫기', True, 600)
    print('5 아이폰 폰 건반: 여는 동안 배너 내림 · 메트로놈으로 바꾸거나 닫으면 다시 ok')
    # 4 돌리기: 폰은 가로에서도 BANNER · 걷고 새로 띄운다 · 키보드(높이만)는 그대로
    n = len(pg.evaluate('__ad.log'))
    pg.set_viewport_size({'width': 844, 'height': 390})
    s = settled(pg, '4 아이폰 폰을 가로로', True, pg.evaluate('__ad.delay') + 900)
    lg = pg.evaluate('__ad.log').__getitem__(slice(n, None))
    if s['size'] != 'BANNER' or 'remove' not in lg or 'show:BANNER' not in lg: fail('4 폰을 가로로 돌렸는데 BANNER 로 다시 안 띄움: %s %s' % (s, lg))
    n = len(pg.evaluate('__ad.log'))
    pg.set_viewport_size({'width': 844, 'height': 200}); pg.wait_for_timeout(700)
    lg = pg.evaluate('__ad.log').__getitem__(slice(n, None))
    if any(x in ('remove',) or x.startswith('show:') for x in lg): fail('4 높이만 바뀌었는데(키보드) 배너를 다시 띄움: %s' % lg)
    pg.set_viewport_size({'width': 390, 'height': 844}); settled(pg, '4 다시 세로로', True, pg.evaluate('__ad.delay') + 900)
    print('4 아이폰 폰: 가로에서도 BANNER · 돌리면 걷고 새로 · 키보드(높이만)는 그대로 ok')
    c.close()

    # 폰을 가로로 든 채 연 앱도 BANNER (예전: 폭 844 ≥ 728 이라 728×90 이 화면의 28%)
    c, pg = native('ios', 844, 390, 390, 844)
    play(pg); s = settled(pg, '4 아이폰 가로로 연 앱', True)
    if s['size'] != 'BANNER': fail('4 폰 가로인데 LEADERBOARD: %s' % s)
    print('4 폰 가로로 연 앱 → BANNER ok')
    c.close()

    # ================= 3 안드로이드 폰: 숨긴 뒤 다시 보이기 =================
    c, pg = native('android', 412, 915, 412, 915)
    play(pg)
    s = settled(pg, '안드로이드 연습 화면', True)
    if s['size'] != 'BANNER': fail('안드로이드 폰 크기: %s' % s)
    for i in range(3):
      for label, opn, cls in [('메모 창', memo_open, memo_close), ('무대', stage_open, stage_close)]:
        opn(pg); settled(pg, '3 안드로이드 %s 열기 %d' % (label, i + 1), False, 500)
        cls(pg); s = settled(pg, '3 안드로이드 %s 닫기 %d' % (label, i + 1), True, 700)
        if 'resume' not in s['log']: fail('3 숨긴 배너를 resumeBanner 로 다시 보이지 않음: %s' % s)
    home(pg); settled(pg, '3 안드로이드 연습 화면을 떠남', False, 500)
    play(pg); settled(pg, '3 안드로이드 연습 화면으로 돌아옴', True, 700)
    if pg.evaluate('__ad.shows') != 1: fail('3 숨겼다 보일 때마다 광고를 새로 받음: %s' % st(pg))
    print('3 안드로이드: 메모 창·무대·다른 화면을 여러 번 오가도 resume 으로 다시 보임 · 빈 띠 없음 ok')
    # 받는 중에 내리면 걷고(remove) 다음에 새로 만든다 (숨긴 채 다시 받아 보이지 않던 것)
    fresh(pg); memo_open(pg)
    s = settled(pg, '3 안드로이드: 받는 중에 메모 창', False)
    if 'remove' not in s['log']: fail('3 받는 중에 내렸는데 뷰를 걷지 않음: %s' % s)
    memo_close(pg); s = settled(pg, '3 안드로이드: 메모 창 닫기 → 새로 받음', True)
    if 'reload' in pg.evaluate('__ad.log'): fail('3 숨긴 뷰에 광고만 다시 받음(보이지 않는 채): %s' % s)
    # 웹뷰만 다시 불러옴(기기 데이터 지우기·계정 삭제의 reload): 앞 페이지의 네이티브 뷰가 남아도 줄이 막히지 않는다
    for pre in ('hidden', 'shown'):
      pg.evaluate("sessionStorage.setItem('__adPre', %r)" % pre)
      pg.reload(); pg.wait_for_selector('[data-act="metro"]', timeout=15000)
      s = settled(pg, '3 안드로이드 다시 불러옴(%s) → 보임' % pre, True, pg.evaluate('__ad.delay') + 900)
      if 'reload' in s['log']: fail('3 다시 불러온 뒤 남은 뷰에 showBanner 를 불러 줄이 막힘: %s' % s)
      stage_open(pg); settled(pg, '3 다시 불러온 뒤 무대 → 안 보임', False, 500); stage_close(pg)
      settled(pg, '3 다시 불러온 뒤 무대 닫기 → 보임', True, 900)
    print('3 안드로이드: 웹뷰를 다시 불러와도(남은 뷰 숨김·보임) 처음에 걷고 새로 띄움 · 무대에서 내려감 ok')
    # 폰 건반
    piano_open(pg); settled(pg, '5 안드로이드 폰 건반', False, 500)
    tool_close(pg); settled(pg, '5 안드로이드 건반 닫기', True, 700)
    # 못 받으면(무필) 빈 띠 없음
    fresh(pg, "__ad.fill=false")
    s = settled(pg, '3 안드로이드: 광고를 못 받음', False)
    if s['view'] != 'none': fail('3 못 받았는데 뷰가 남음: %s' % s)
    print('3 안드로이드: 받는 중에 내리면 걷고 새로 · 폰 건반 · 못 받으면 빈 띠 없음 ok')
    c.close()

    # ================= 4 태블릿: LEADERBOARD · 돌리면 크기를 다시 고른다 =================
    c, pg = native('android', 600, 960, 600, 960)   # 7인치 태블릿 세로: 짧은 변 600 이지만 폭 600 < 728 → BANNER
    play(pg); s = settled(pg, '4 안드로이드 태블릿 세로', True)
    if s['size'] != 'BANNER': fail('4 폭 600 태블릿 세로인데 BANNER 가 아님: %s' % s)
    pg.set_viewport_size({'width': 960, 'height': 600})
    s = settled(pg, '4 안드로이드 태블릿 가로', True, pg.evaluate('__ad.delay') + 900)
    if s['size'] != 'LEADERBOARD': fail('4 태블릿을 가로로 돌렸는데 LEADERBOARD 로 다시 안 띄움: %s' % s)
    piano_open(pg); settled(pg, '5 태블릿 건반은 배너 그대로', True, 500); tool_close(pg)
    pg.set_viewport_size({'width': 600, 'height': 960})
    s = settled(pg, '4 안드로이드 태블릿 다시 세로', True, pg.evaluate('__ad.delay') + 900)
    if s['size'] != 'BANNER': fail('4 다시 세로인데 크기가 그대로: %s' % s)
    # 숨긴 채 돌리면 다음에 보일 때 새 크기
    home(pg); settled(pg, '4 다른 화면', False, 400)
    pg.set_viewport_size({'width': 960, 'height': 600}); pg.wait_for_timeout(500)
    play(pg); s = settled(pg, '4 숨긴 채 돌린 뒤 연습 화면', True, pg.evaluate('__ad.delay') + 600)
    if s['size'] != 'LEADERBOARD': fail('4 숨긴 채 돌렸는데 옛 크기로 다시 보임: %s' % s)
    print('4 안드로이드 태블릿: 세로 BANNER ↔ 가로 LEADERBOARD 로 다시 띄움 · 가운데 · 태블릿 건반은 배너 그대로 ok')
    c.close()

    c, pg = native('ios', 820, 1180, 820, 1180)   # 아이패드
    play(pg); s = settled(pg, '4 아이패드', True)
    if s['size'] != 'LEADERBOARD': fail('4 아이패드인데 LEADERBOARD 가 아님: %s' % s)
    # 아이폰에서는 받는 중인 배너를 못 걷는다 — 받는 중에 폭이 바뀌어도 배너가 둘 붙지 않고 새 크기로
    pg.set_viewport_size({'width': 600, 'height': 1180}); pg.wait_for_timeout(700)   # 나눠 보기(폭 600) → BANNER
    s = settled(pg, '4 아이패드 나눠 보기', True, pg.evaluate('__ad.delay') + 900)
    if s['size'] != 'BANNER': fail('4 폭 600 인데 LEADERBOARD 그대로: %s' % s)
    fresh(pg)
    pg.set_viewport_size({'width': 820, 'height': 1180}); pg.wait_for_timeout(300)
    s = settled(pg, '4 아이패드: 받는 중에 폭이 바뀜', True, 2 * pg.evaluate('__ad.delay') + 1200)
    if s['size'] != 'LEADERBOARD' or s['attached'] != 1: fail('4 받는 중에 폭이 바뀐 뒤 크기·뷰 수: %s' % s)
    print('4 아이패드: LEADERBOARD · 나눠 보기 폭 600 → BANNER · 받는 중에 바뀌어도 뷰 하나 ok')
    c.close()

    # 창은 좁고(건반이 아래 시트) 기기는 태블릿: 7~8인치 태블릿 세로 · 아이패드 나눠 보기 — 건반이 배너에 붙은 채 남지 않는다
    for plat, vw, vh, sw, sh in (('android', 600, 960, 800, 1280), ('ios', 507, 1180, 820, 1180), ('ios', 375, 1180, 820, 1180)):
      c, pg = native(plat, vw, vh, sw, sh)
      play(pg); settled(pg, '5 좁은 창 %s %dx%d' % (plat, vw, vh), True)
      piano_open(pg); settled(pg, '5 좁은 창 건반(아래 시트) → 배너 내려감 %s %d' % (plat, vw), False, 500)
      tool_close(pg); settled(pg, '5 좁은 창 건반 닫기 → 보임 %s %d' % (plat, vw), True, 900)
      c.close()
    print('5 좁은 창(7~8인치 태블릿 세로 · 아이패드 나눠 보기)에서도 아래 시트 건반이면 배너 내려감 ok')

    ours = [e for e in errs if 'adsbygoogle' not in e]
    if ours: fail('페이지 오류: ' + ours[0])
    if FAILS: print('FAILS %d' % len(FAILS)); sys.exit(1)
    print('OK — 웹 광고 꺼짐 · 아이폰 늦은 배너 숨김 · 안드로이드 다시 보이기 · 크기·돌리기 · 폰 건반 · 8px 여백')
    b.close()

run()
