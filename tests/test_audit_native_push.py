# 앱·푸시 점검 (audit native-push: F34 · F35 · F103 · F108 · F145)
#   CONTI_URL=http://localhost:8816/ .venv/bin/python tests/test_audit_native_push.py
# - F34/F103: iOS 푸시가 애플 연결 끊김에 죽지 않고, 잠깐 안 닿을 때 토큰을 지우지 않는다 (scripts/apns-check.mjs)
# - F108: 웹 푸시가 답 없는 구독 주소에 붙잡혀 발행·크론이 멈추지 않는다 (API 로 끝까지 + scripts/push-check.mjs)
# - F145: 출시 빌드 웹뷰 디버깅이 설정 파일로 강제로 켜지지 않는다
# - F35: 앱 링크(lets1414.com/#/join/… · #/view/… · #/word-link/…)로 열린 앱이 그 화면으로 간다
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
               'https://metadata.google.internal/x' + tag, 'javascript:alert(1)'):
        r = req.post(BASE + 'api/push/subscribe', headers=H, data={'sub': {'endpoint': ep, 'keys': KEYS}})
        if r.status != 400: fail('이상한 구독 주소를 받음 (%s): %s' % (r.status, ep))
    ok_ep = 'https://example.invalid/push/np' + tag   # 절대 풀리지 않는 이름 — 밖으로 나가지 않는다
    r = req.post(BASE + 'api/push/subscribe', headers=H, data={'sub': {'endpoint': ok_ep, 'keys': KEYS}})
    if r.status != 200: fail('정상 구독 주소를 거절: %s %s' % (r.status, r.text()))
    req.post(BASE + 'api/push/unsubscribe', headers=H, data={'endpoint': ok_ep})
    print('구독 주소 거르기 ok')

    # 이미 DB 에 들어 있는 '답 없는' 구독 (옛 데이터와 같은 경우) → 시험 발송이 멈추지 않고 끝난다
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
        if dt > 20: fail('시험 발송이 너무 오래 걸림: %.1fs' % dt)
        if not srv.conns: fail('답 없는 서버까지 요청이 안 감 (확인이 헛돎)')
        print('답 없는 구독이 있어도 %.1fs 에 끝남 ok' % dt)
    finally:
        sql('delete from push_subs where endpoint=$1', ep); srv.close()
    # 흘리며 붙잡는 곳까지 (https 로 머리만 주고 몸을 조금씩)
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
    },
  };
  window.__appUrlListeners = () => (L.appUrlOpen || []).length;
  window.__fireAppUrl = (u) => (L.appUrlOpen || []).forEach((cb) => cb({ url: u }));
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
            try: resp = route.fetch(url=target)
            except Exception: return route.abort()
            return route.fulfill(response=resp)
        if u.hostname in ('localhost', '127.0.0.1') and u.port == urlparse(BASE).port:
            return route.continue_()
        leaks['blocked'].append(route.request.url)
        return route.abort()
    c.route('**/*', handler)
    c.add_init_script(MOCK % (json.dumps(launch_url) if launch_url else 'null'))
    return c, leaks

def hash_of(pg): return re.sub(r'^#/?', '', pg.evaluate('location.hash'))

def applink_checks(b, lead_req, team, sid, wtoken):
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

    # 앱의 API 요청(https://lets1414.com/api/…)은 전부 가로채 로컬로 갔다 — 운영에는 안 닿았다
    if not leaks['api']: fail('앱 API 요청이 가로채지지 않음 (앱 흉내가 어긋남)')
    if errs: fail('JS 오류: %s' % errs[:3])
    c.close()
    print('F35 앱 링크 ok')

def run():
    debug_flag_check()
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
        doc = {'id': sid, 'name': '앱링크 콘티', 'date': '2026-11-22', 'notice': '', 'version': 1, 'items': []}
        r = lead.put(BASE + 'api/services/' + sid, headers=H, data={'teamId': tid, 'doc': doc})
        if r.status != 200: fail('발행 실패: %s %s' % (r.status, r.text()))
        r = lead.post(BASE + 'api/services/%s/word-link' % sid, headers=H, data={'teamId': tid})
        if r.status != 200: fail('말씀 링크 만들기 실패: %s' % r.text())
        applink_checks(b, lead, team, sid, r.json()['token'])
        b.close()
    print('OK test_audit_native_push')

run()
