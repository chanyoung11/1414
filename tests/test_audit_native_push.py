# 앱·푸시 점검 (audit native-push: F34 · F35 · F103 · F108 · F145)
#   CONTI_URL=http://localhost:8816/ .venv/bin/python tests/test_audit_native_push.py
# - F34/F103: iOS 푸시가 애플 연결 끊김에 죽지 않고, 잠깐 안 닿을 때 토큰을 지우지 않는다 (scripts/apns-check.mjs)
# - F103: 운영 APNs 가 안 닿아도 샌드박스(개발 빌드) 토큰에는 보낸다 — 지우지는 않는다
# - F108: 웹 푸시가 답 없는 구독 주소에 붙잡혀 발행·크론이 멈추지 않는다 (API 로 끝까지 + scripts/push-check.mjs)
#   끝의 점·한 단어 이름·안쪽 IP 로 풀리는 이름은 막고, 시간을 넘긴 연결은 닫고, 한 사람의 구독 수에 끝이 있다
# - F145: 출시 빌드 웹뷰 디버깅이 설정 파일로 강제로 켜지지 않는다
# - F35: 앱 링크(lets1414.com/#/join/… · #/view/… · #/word-link/…)로 열린 앱이 그 화면으로 간다
#   무대 모드가 떠 있으면 닫고 가고, 다른 팀 콘티 링크면 그 팀으로 바꿔 연다.
#   안드로이드가 되살릴 때 옛 링크를 다시 주지 않게 MainActivity 가 링크를 뗀다 (소스 확인)
#   앱은 https://localhost 에서 돌고 API 는 https://lets1414.com 을 부른다. 테스트는 두 주소를 모두
#   가로채 로컬 서버로 돌린다 — 운영 서버에는 요청이 하나도 나가지 않는다 (나머지 바깥 주소는 막는다)
import os, sys, time, json, re, socket, threading, subprocess
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
BASE = URL if URL.endswith('/') else URL + '/'
H = {'x-conti': '1'}
DB = 'postgres://postgres:pg@localhost:54329/postgres'
tag = str(int(time.time()))[-6:]
NOCOLOR = lambda t: re.sub(r'\x1b\[[0-9;]*m', '', t)

def fail(m): print('FAIL:', m); sys.exit(1)

def node(script, *args, timeout=90):
    r = subprocess.run(['node', script, *args], cwd=ROOT, capture_output=True, text=True, timeout=timeout,
                       env={**os.environ, 'DATABASE_URL': DB})
    out = NOCOLOR(r.stdout.strip())
    return r.returncode, out, NOCOLOR(r.stderr.strip())

def sql(query, *params):
    js = ('import("pg").then(async ({default:pg})=>{const c=new pg.Client({connectionString:%s});await c.connect();'
          'const r=await c.query(%s,%s);console.log(JSON.stringify(r.rows));await c.end()})') % (
        json.dumps(DB), json.dumps(query), json.dumps(list(params)))
    r = subprocess.run(['node', '--input-type=module', '-e', js], cwd=ROOT, capture_output=True, text=True, timeout=30)
    if r.returncode: fail('sql: ' + r.stderr[-300:])
    return json.loads(r.stdout.strip() or '[]')

# ---------------------------------------------------------------- F34 · F103
def apns_checks():
    code, out, err = node('scripts/apns-check.mjs')
    print(out)
    if code != 0 or not out.endswith('OK'): fail('iOS 푸시 확인 실패 (exit %s): %s' % (code, err[-600:]))
    print('F34/F103 iOS 푸시 ok')

# ---------------------------------------------------------------- F145
def debug_flag_check():
    cfg = json.load(open(os.path.join(ROOT, 'capacitor.config.json'), encoding='utf-8'))
    for plat in ('android', 'ios'):
        v = (cfg.get(plat) or {}).get('webContentsDebuggingEnabled')
        if v is not None: fail('%s.webContentsDebuggingEnabled 가 설정 파일에 있음(%r) — 출시 빌드에서도 웹뷰 디버깅이 켜진다' % (plat, v))
    print('F145 웹뷰 디버깅은 디버그 빌드에만 ok')

def android_relaunch_check():
    # 최근 앱에서 다시 켜거나 죽었던 화면을 되살릴 때 안드로이드는 처음의 링크 인텐트를 다시 준다 →
    # super.onCreate(링크를 appUrlOpen 으로 보내는 곳) 전에 링크를 떼야 한다
    src = open(os.path.join(ROOT, 'android/app/src/main/java/com/lets1414/app/MainActivity.java'), encoding='utf-8').read()
    body = src[src.index('public void onCreate'):]
    i_strip, i_super = body.find('setData(null)'), body.find('super.onCreate(')
    if i_strip < 0 or i_super < 0 or i_strip > i_super: fail('MainActivity 가 되살릴 때 옛 앱 링크를 떼지 않음 (F35)')
    for k in ('FLAG_ACTIVITY_LAUNCHED_FROM_HISTORY', 'savedInstanceState != null', 'ACTION_VIEW'):
        if k not in body[:i_super]: fail('MainActivity 링크 떼기 조건에 %s 없음' % k)
    print('안드로이드 되살리기에 옛 앱 링크 안 줌 ok')

# ---------------------------------------------------------------- F108
class Silent:
    """연결만 받고 아무 말도 안 하는 서버 (TLS 인사도 안 한다)"""
    def __init__(self):
        self.s = socket.socket(); self.s.bind(('127.0.0.1', 0)); self.s.listen(8)
        self.port = self.s.getsockname()[1]; self.conns = []
        threading.Thread(target=self.loop, daemon=True).start()
    def loop(self):
        while True:
            try: c, _ = self.s.accept(); self.conns.append(c)
            except OSError: return
    def close(self):
        for c in self.conns:
            try: c.close()
            except OSError: pass
        self.s.close()

KEYS = {'p256dh': 'BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM', 'auth': 'tBHItJI5svbpez7KI4CCXg'}

def webpush_checks(req, uid):
    # 구독 주소는 https 공개 주소만 받는다
    for ep in ('http://fcm.googleapis.com/fcm/send/x' + tag, 'https://127.0.0.1:9/x' + tag, 'https://localhost/x' + tag,
               'https://metadata.google.internal/x' + tag, 'javascript:alert(1)',
               # 끝에 점을 붙이거나 한 단어 이름(안쪽 DNS 가 푸는 것)으로 돌아가던 것
               'https://localhost./x' + tag, 'https://metadata.google.internal./x' + tag, 'https://metadata/x' + tag,
               'https://printer.local/x' + tag, 'https://[::1]/x' + tag):
        r = req.post(BASE + 'api/push/subscribe', headers=H, data={'sub': {'endpoint': ep, 'keys': KEYS}})
        if r.status != 400: fail('이상한 구독 주소를 받음 (%s): %s' % (r.status, ep))
    ok_ep = 'https://example.invalid/push/np' + tag   # 절대 풀리지 않는 이름 — 밖으로 나가지 않는다
    r = req.post(BASE + 'api/push/subscribe', headers=H, data={'sub': {'endpoint': ok_ep, 'keys': KEYS}})
    if r.status != 200: fail('정상 구독 주소를 거절: %s %s' % (r.status, r.text()))
    req.post(BASE + 'api/push/unsubscribe', headers=H, data={'endpoint': ok_ep})
    print('구독 주소 거르기 ok')

    # 한 사람의 구독은 최근 10개까지 — 가짜 구독을 끝없이 올려 시험 발송 한 번에 바깥 요청을 수천 번 쏘게 하던 것
    eps = ['https://example.invalid/push/cap%s-%02d' % (tag, i) for i in range(14)]
    for ep in eps:
        r = req.post(BASE + 'api/push/subscribe', headers=H, data={'sub': {'endpoint': ep, 'keys': KEYS}})
        if r.status != 200: fail('구독 실패: %s %s' % (r.status, r.text()))
    left = [x['endpoint'] for x in sql('select endpoint from push_subs where user_id=$1', uid)]
    if len(left) != 10: fail('한 사람의 구독이 10개로 줄지 않음: %d' % len(left))
    if eps[-1] not in left or eps[0] in left: fail('최근 구독이 남고 옛 구독이 빠져야 함: %s' % sorted(left)[:3])
    # 가장 옛 구독도 다시 올리면(그 브라우저가 다시 켜짐) 최근 것이 되어, 다음에 빠지는 것은 그다음 옛것이다
    for ep in (eps[4], eps[0]):
        r = req.post(BASE + 'api/push/subscribe', headers=H, data={'sub': {'endpoint': ep, 'keys': KEYS}})
        if r.status != 200: fail('구독 실패: %s %s' % (r.status, r.text()))
    left2 = [x['endpoint'] for x in sql('select endpoint from push_subs where user_id=$1', uid)]
    if len(left2) != 10 or eps[4] not in left2 or eps[0] not in left2 or eps[5] in left2:
        fail('다시 올린 구독이 최근 것으로 남지 않음: %d %s' % (len(left2), sorted(left2)[:3]))
    sql('delete from push_subs where user_id=$1', uid)
    print('한 사람 구독 10개까지 ok')

    # 거르기 전에 DB 에 들어온 옛 구독(안쪽 IP 주소) → 연결조차 하지 않고 시험 발송이 곧 끝난다. 지우지는 않는다
    r = req.patch(BASE + 'api/me/prefs', headers=H, data={'prefs': {'quiet': {'on': False, 'from': 22, 'to': 8}}})
    if r.status != 200: fail('조용한 시간 끄기 실패: %s' % r.text())
    srv = Silent()
    ep = 'https://127.0.0.1:%d/push/%s' % (srv.port, tag)
    sql('insert into push_subs(endpoint, user_id, keys) values($1,$2,$3)', ep, uid, json.dumps(KEYS))
    try:
        t0 = time.time()
        try:
            r = req.post(BASE + 'api/push/test', headers=H, timeout=45000)
        except Exception as e:
            fail('답 없는 구독 하나에 시험 발송이 45초 넘게 멈춤 (F108): %s' % str(e)[:120])
        dt = time.time() - t0
        if r.status != 200: fail('시험 발송 오류: %s %s' % (r.status, r.text()))
        if dt > 5: fail('안쪽 주소 옛 구독에 시험 발송이 붙잡힘: %.1fs' % dt)
        time.sleep(0.3)
        if srv.conns: fail('안쪽 주소 옛 구독으로 서버가 연결함 (F108)')
        if not sql('select 1 from push_subs where endpoint=$1', ep): fail('옛 구독이 지워짐 (죽었다고 확인된 것이 아님)')
        print('안쪽 주소 옛 구독은 건드리지 않고 %.1fs 에 끝남 ok' % dt)
    finally:
        sql('delete from push_subs where endpoint=$1', ep); srv.close()
    # 답 없는 곳 · 흘리며 붙잡는 곳(https 로 머리만 주고 몸을 조금씩)은 시간 안에 끝나고 연결도 닫힌다.
    # 공개처럼 보이는 이름이 안쪽 IP 로 풀리면 연결하지 않는다 (서버 프로세스 안에서 이름 풀기를 바꿔 본다)
    code, out, err = node('scripts/push-check.mjs', timeout=60)
    print(out)
    if code != 0 or not out.endswith('OK'): fail('웹 푸시 시간 제한 확인 실패: %s' % err[-400:])
    print('F108 웹 푸시 시간 제한 ok')

# ---------------------------------------------------------------- F35
MOCK = r"""
(() => {
  // 네이티브 셸 흉내: Capacitor 앱 플러그인. 링크로 켜진 앱은 appUrlOpen 을 듣는 쪽이 붙을 때까지
  // 들고 있다가 넘긴다 (retainUntilConsumed). 새로고침 뒤에는 다시 안 준다
  const L = {};
  let launch = null;
  try { if (!sessionStorage.getItem('__launched')) { launch = %s; sessionStorage.setItem('__launched', '1'); } } catch (e) {}
  window.Capacitor = {
    getPlatform: () => 'android', isNativePlatform: () => true, isPluginAvailable: () => false,
    Plugins: {
      App: {
        addListener(name, cb) {
          (L[name] = L[name] || []).push(cb);
          if (name === 'appUrlOpen' && launch) { const u = launch; launch = null; setTimeout(() => cb({ url: u }), 0); }
          return Promise.resolve({ remove() {} });
        },
        getLaunchUrl: () => Promise.resolve(undefined), exitApp() {}, getInfo: () => Promise.resolve({}),
      },
      SplashScreen: { hide: () => Promise.resolve() },
      // 푸시: 권한만 주고 토큰은 안 준다 (알림을 누른 것만 흉내 낸다)
      PushNotifications: {
        checkPermissions: () => Promise.resolve({ receive: 'granted' }), requestPermissions: () => Promise.resolve({ receive: 'granted' }),
        createChannel: () => Promise.resolve(), register: () => Promise.resolve(), unregister: () => Promise.resolve(),
        removeAllListeners: () => { PL = {}; return Promise.resolve(); },
        addListener(name, cb) { (PL[name] = PL[name] || []).push(cb); return Promise.resolve({ remove() {} }); },
      },
    },
  };
  let PL = {};
  window.__appUrlListeners = () => (L.appUrlOpen || []).length;
  window.__fireAppUrl = (u) => (L.appUrlOpen || []).forEach((cb) => cb({ url: u }));
  window.__firePushTap = (data) => (PL.pushNotificationActionPerformed || []).forEach((cb) => cb({ notification: { data } }));
})();
"""

def native_context(b, launch_url):
    """https://localhost 에서 도는 앱 + https://lets1414.com API 를 로컬 서버로 돌린다"""
    c = b.new_context(viewport={'width': 400, 'height': 860}, service_workers='block')
    leaks = {'api': 0, 'blocked': []}
    def handler(route):
        u = urlparse(route.request.url)
        if u.hostname in ('lets1414.com', 'www.lets1414.com'): leaks['api'] += 1
        if u.scheme == 'https' and u.hostname == 'localhost' and u.port is None or u.hostname in ('lets1414.com', 'www.lets1414.com'):
            target = BASE + u.path.lstrip('/') + ('?' + u.query if u.query else '')
            try: return route.fulfill(response=route.fetch(url=target))
            except Exception:   # 창을 닫는 사이 뒤에서 받던 것 (팀을 바꾼 뒤의 동기화 등)
                try: return route.abort()
                except Exception: return
        if u.hostname in ('localhost', '127.0.0.1') and u.port == urlparse(BASE).port:
            return route.continue_()
        leaks['blocked'].append(route.request.url)
        return route.abort()
    c.route('**/*', handler)
    c.add_init_script(MOCK % (json.dumps(launch_url) if launch_url else 'null'))
    return c, leaks

def hash_of(pg): return re.sub(r'^#/?', '', pg.evaluate('location.hash'))

def applink_checks(b, lead_req, team, sid, wtoken, team2, sid2, user_req):
    code = team['invite']
    SITE = 'https://lets1414.com/'
    c, leaks = native_context(b, SITE + '#/join/' + code)
    pg = c.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('dialog', lambda d: d.accept())
    pg.goto('https://localhost/')
    if not pg.evaluate('/^(capacitor|ionic):/.test(location.protocol)||(location.hostname==="localhost"&&!location.port&&location.protocol==="https:")'):
        fail('앱 흉내가 안 됨 (NATIVE 아님)')
    # 꺼져 있던 앱이 초대 링크로 켜졌다 → 로그인 화면이 초대를 들고 있다
    pg.wait_for_selector('#lgUser', timeout=15000)
    try: pg.wait_for_function('/^#\\/?join\\//.test(location.hash)', timeout=8000)
    except Exception: fail('초대 링크로 켠 앱이 링크를 버림: hash=%r (F35)' % pg.evaluate('location.hash'))
    if '초대 링크로 오셨네요' not in pg.inner_text('#app'): fail('로그인 화면에 초대 안내가 없음')
    print('앱 링크(초대)로 켜짐 → 로그인 화면이 초대를 들고 있음 ok')
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName')
    pg.check('#lgAgree'); pg.fill('#lgName', '민수'); pg.fill('#lgUser', 'npm' + tag); pg.fill('#lgPass', 'secret1')
    pg.click('[data-act="lg-submit"]')
    pg.wait_for_selector('#jnName', timeout=15000)                     # 로그인 뒤 그 팀 가입으로 이어짐
    if team['name'] not in pg.inner_text('#app'): fail('가입 화면에 초대한 팀 이름이 없음')
    if not pg.evaluate("!!localStorage.getItem('conti-app-token')||Object.keys(localStorage).some(k=>/token/i.test(k))"):
        fail('앱 토큰이 저장되지 않음 (앱 흉내가 어긋남)')
    pg.click('#gtSess .q:has-text("드럼")'); pg.click('[data-act="team-join"]')
    pg.wait_for_selector('.shell[data-page]', timeout=15000)
    print('로그인 뒤 초대한 팀에 가입 ok')

    # 앱이 켜져 있을 때 콘티 링크 → 그 콘티 화면
    pg.evaluate('h=>__fireAppUrl(h)', SITE + '#/view/' + sid)
    try: pg.wait_for_function('s=>location.hash.replace(/^#\\/?/,"")==="view/"+s', arg=sid, timeout=8000)
    except Exception: fail('콘티 링크를 눌러도 그 화면으로 안 감: %r' % pg.evaluate('location.hash'))
    pg.wait_for_function("document.querySelector('#app').innerText.includes('앱링크 콘티')", timeout=15000)
    print('앱 링크(콘티) → 보기 화면 ok')

    # 우리 첫 화면이 아닌 주소·남의 주소·# 없는 첫 화면 → 지금 화면 그대로
    for u in (SITE + 'yt.html#/join/' + code, 'https://evil.example/#/join/' + code, SITE, 'lets1414://x#/home', 'not a url'):
        pg.evaluate('h=>__fireAppUrl(h)', u); pg.wait_for_timeout(300)
        if hash_of(pg) != 'view/' + sid: fail('앱 화면이 아닌 링크에 끌려감: %s → %r' % (u, pg.evaluate('location.hash')))
    print('앱 화면이 아닌 링크는 모른 척 ok')

    # 말씀 링크 (로그인 없이 여는 페이지) — www 로 와도 된다
    pg.evaluate('h=>__fireAppUrl(h)', 'https://www.lets1414.com/#/word-link/' + wtoken)
    try: pg.wait_for_selector('#wlTitle', timeout=10000)
    except Exception: fail('말씀 링크를 눌러도 그 화면으로 안 감: %r' % pg.evaluate('location.hash'))
    print('앱 링크(말씀) → 말씀 보내기 화면 ok')

    # 앱 안에서 새로고침해도 처음 켤 때의 링크로 다시 끌려가지 않는다
    pg.evaluate("location.hash='#/home'"); pg.wait_for_timeout(300)
    pg.reload(); pg.wait_for_selector('.shell[data-page]', timeout=15000); pg.wait_for_timeout(800)
    if not pg.evaluate('__appUrlListeners()'): fail('새로고침 뒤 앱 링크를 듣지 않음')
    if hash_of(pg) not in ('home', ''): fail('새로고침했더니 옛 링크로 끌려감: %r' % pg.evaluate('location.hash'))
    print('새로고침 뒤에도 옛 링크로 안 끌려감 ok')

    # 무대 모드가 떠 있을 때 링크를 누르면 무대를 닫고 그 화면으로 간다 — 무대가 덮은 채 뒤에서 주소만 바뀌던 것.
    # 지금 화면을 가리키는 링크면 무대는 그대로 둔다
    def open_stage():
        pg.evaluate('h=>__fireAppUrl(h)', SITE + '#/view/' + sid)
        pg.wait_for_function('s=>location.hash.replace(/^#\\/?/,"")==="view/"+s', arg=sid, timeout=8000)
        pg.wait_for_selector('[data-act="play"][data-stage="1"]', timeout=15000); pg.wait_for_timeout(500)
        pg.click('[data-act="play"][data-stage="1"]'); pg.wait_for_selector('#stageWrap .stgpage', timeout=15000)
    open_stage()
    pg.evaluate('h=>__fireAppUrl(h)', SITE + '#/view/' + sid); pg.wait_for_timeout(400)
    if not pg.query_selector('#stageWrap'): fail('지금 화면을 가리키는 링크에 무대가 닫힘')
    pg.evaluate('h=>__fireAppUrl(h)', SITE + '#/home')
    try: pg.wait_for_function('!document.getElementById("stageWrap")&&!document.body.classList.contains("stgon")', timeout=5000)
    except Exception: fail('무대 모드 중 링크를 눌렀는데 무대가 화면을 덮은 채 남음 (F35)')
    if hash_of(pg) != 'home': fail('무대를 닫고 링크 화면으로 안 감: %r' % pg.evaluate('location.hash'))
    # 알림을 누른 것도 같다 (웹·앱 공통 openPushLink)
    open_stage()
    pg.evaluate('()=>__firePushTap({link:"#/home",teamId:CONTI.S.team.id})')
    try: pg.wait_for_function('!document.getElementById("stageWrap")&&location.hash.replace(/^#\\/?/,"")==="home"', timeout=5000)
    except Exception: fail('무대 모드 중 알림을 눌렀는데 무대가 남음')
    print('무대 모드 중 링크·알림 → 무대를 닫고 그 화면 ok')

    # 여러 팀에 있는 사람이 다른 팀 콘티 링크를 누르면 그 팀으로 바꿔 연다 (링크에는 팀이 없다 — 전에는 홈으로)
    tid = pg.evaluate('CONTI.S.team.id')
    me = user_req()
    r = me.post(BASE + 'api/auth/login', headers=H, data={'username': 'npm' + tag, 'password': 'secret1'})
    if r.status != 200: fail('민수 로그인 실패: %s' % r.text())
    r = me.post(BASE + 'api/invite/%s/join' % team2['invite'], headers=H, data={'name': '민수', 'sessions': ['드럼'], 'session': '드럼'})
    if r.status != 200: fail('두 번째 팀 가입 실패: %s %s' % (r.status, r.text()))
    pg.reload(); pg.wait_for_selector('.shell[data-page]', timeout=15000); pg.wait_for_timeout(500)
    if pg.evaluate('CONTI.S.team.id') != tid: fail('새로고침 뒤 지금 팀이 바뀜 (확인이 헛돎)')
    if len(pg.evaluate('CONTI.NET.teams')) != 2: fail('두 팀이 안 보임: %s' % pg.evaluate('CONTI.NET.teams.length'))
    pg.evaluate('h=>__fireAppUrl(h)', SITE + '#/view/' + sid2)
    try: pg.wait_for_function("t=>CONTI.S.team.id===t&&document.querySelector('#app').innerText.includes('다른 팀 콘티')", arg=team2['teamId'], timeout=15000)
    except Exception: fail('다른 팀 콘티 링크가 그 팀으로 안 열림: team=%s hash=%r' % (pg.evaluate('CONTI.S.team.id') == tid and '그대로' or '바뀜', pg.evaluate('location.hash')))
    if hash_of(pg) != 'view/' + sid2: fail('다른 팀 콘티 주소가 아님: %r' % pg.evaluate('location.hash'))
    print('다른 팀 콘티 링크 → 그 팀으로 바꿔 열림 ok')
    # 어느 팀에도 없는 콘티면 예전처럼 알리고 홈으로 ('받는 중'에 멈추지 않는다)
    pg.evaluate('h=>__fireAppUrl(h)', SITE + '#/view/none' + tag)
    try: pg.wait_for_function('location.hash.replace(/^#\\/?/,"")==="home"', timeout=15000)
    except Exception: fail('없는 콘티 링크가 홈으로 안 감: %r' % pg.evaluate('location.hash'))
    print('없는 콘티 링크 → 홈 ok')

    # 앱의 API 요청(https://lets1414.com/api/…)은 전부 가로채 로컬로 갔다 — 운영에는 안 닿았다
    if not leaks['api']: fail('앱 API 요청이 가로채지지 않음 (앱 흉내가 어긋남)')
    if errs: fail('JS 오류: %s' % errs[:3])
    c.close()
    print('F35 앱 링크 ok')

def web_other_team_link(b, team, sid, team2, sid2):
    # 웹도 같은 길이다: 두 팀에 있는 사람이 브라우저로 다른 팀 콘티 링크를 열면 그 팀으로 바꿔 연다
    c = b.new_context(viewport={'width': 400, 'height': 860}, service_workers='block')
    r = c.request.post(BASE + 'api/auth/login', headers=H, data={'username': 'npm' + tag, 'password': 'secret1'})
    if r.status != 200: fail('웹 로그인 실패: %s' % r.text())
    pg = c.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('dialog', lambda d: d.accept())
    pg.goto(BASE); pg.wait_for_selector('.shell[data-page]', timeout=15000)
    cur = pg.evaluate('CONTI.S.team.id')
    other, osid, oname = (team2['teamId'], sid2, '다른 팀 콘티') if cur == team['teamId'] else (team['teamId'], sid, '앱링크 콘티')
    pg.goto(BASE + '#/view/' + osid)
    try: pg.wait_for_function("([t,n])=>CONTI.S.team.id===t&&document.querySelector('#app').innerText.includes(n)", arg=[other, oname], timeout=15000)
    except Exception: fail('웹에서 다른 팀 콘티 링크가 그 팀으로 안 열림: %r' % pg.evaluate('location.hash'))
    if errs: fail('JS 오류: %s' % errs[:3])
    c.close()
    print('웹 — 다른 팀 콘티 링크 → 그 팀으로 바꿔 열림 ok')

def run():
    debug_flag_check()
    android_relaunch_check()
    apns_checks()
    with sync_playwright() as p:
        b = p.chromium.launch()
        lead = p.request.new_context(base_url=BASE)
        r = lead.post(BASE + 'api/auth/signup', headers=H, data={'username': 'npl' + tag, 'password': 'secret1', 'name': '하은'})
        if r.status != 200: fail('인도자 가입 실패: %s' % r.text())
        uid = r.json().get('id') or (r.json().get('user') or {}).get('id')
        if not uid: uid = sql('select id from users where username=$1', 'npl' + tag)[0]['id']
        team = lead.post(BASE + 'api/teams', headers=H, data={'name': '앱링크팀' + tag, 'myName': '하은', 'session': '인도자'}).json()
        if not team.get('invite'): fail('팀 만들기 실패: %s' % team)
        tid = team['teamId']; team['name'] = team['teamName']
        webpush_checks(lead, uid)
        sid = 'np' + tag
        item = lambda t: {'id': 'i1', 'title': t, 'key': 'G', 'mod': '', 'form': '', 'songNote': '', 'pieces': [], 'media': [], 'notes': []}
        doc = {'id': sid, 'name': '앱링크 콘티', 'date': '2026-11-22', 'notice': '', 'version': 1, 'items': [item('첫 곡')]}
        r = lead.put(BASE + 'api/services/' + sid, headers=H, data={'teamId': tid, 'doc': doc})
        if r.status != 200: fail('발행 실패: %s %s' % (r.status, r.text()))
        r = lead.post(BASE + 'api/services/%s/word-link' % sid, headers=H, data={'teamId': tid})
        if r.status != 200: fail('말씀 링크 만들기 실패: %s' % r.text())
        wtoken = r.json()['token']
        # 다른 인도자의 두 번째 팀과 그 팀 콘티 (여러 팀에 있는 사람의 링크 확인용)
        lead2 = p.request.new_context(base_url=BASE)
        r = lead2.post(BASE + 'api/auth/signup', headers=H, data={'username': 'npk' + tag, 'password': 'secret1', 'name': '서준'})
        if r.status != 200: fail('두 번째 인도자 가입 실패: %s' % r.text())
        team2 = lead2.post(BASE + 'api/teams', headers=H, data={'name': '둘째팀' + tag, 'myName': '서준', 'session': '인도자'}).json()
        if not team2.get('invite'): fail('두 번째 팀 만들기 실패: %s' % team2)
        sid2 = 'nq' + tag
        doc2 = {'id': sid2, 'name': '다른 팀 콘티', 'date': '2026-11-29', 'notice': '', 'version': 1, 'items': [item('둘째 곡')]}
        r = lead2.put(BASE + 'api/services/' + sid2, headers=H, data={'teamId': team2['teamId'], 'doc': doc2})
        if r.status != 200: fail('두 번째 팀 발행 실패: %s %s' % (r.status, r.text()))
        applink_checks(b, lead, team, sid, wtoken, team2, sid2, lambda: p.request.new_context(base_url=BASE))
        web_other_team_link(b, team, sid, team2, sid2)
        b.close()
    print('OK test_audit_native_push')

run()
