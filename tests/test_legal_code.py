# 법률 점검(2026-10-01)에서 코드까지 고친 것 — 서버 API 와 화면(웹 · 가짜 iOS/안드로이드 앱)으로 본다
#
# 사용: CONTI_URL=http://localhost:9211/ CONTI_DB=postgres://… CRON_SECRET=… RC_WEBHOOK_SECRET=… .venv/bin/python tests/test_legal_code.py
#   서버는 RC_PUBLIC_KEY_IOS=appl_… · RC_PUBLIC_KEY_ANDROID=goog_… · RC_WEBHOOK_SECRET · CRON_SECRET · GEMINI_API_KEY=mock 로 (CONTI_DB 는 서버와 같은 DB).
#   앱 흉내는 https://localhost 로 열고 요청은 모두 로컬 서버로 돌린다 — 밖으로 안 나간다
#
# 본다
#  a 계정 삭제: '나만 보기' 고정 메모·녹음 메모는 지운다 · 팀에 보이게 쓴 고정 메모·녹음 메모는 남기고 쓴 사람을 '지워진 사용자'로 ·
#    곡 코드로 받아 온 메모는 지우지도 이름을 바꾸지도 않는다 · 다른 사람 메모는 그대로 · 올린 녹음은 '지워진 사용자' ·
#    그 사람의 시도 기록(아이디|주소 · 사람 id 키)도 지운다
#  b 크론(/cron/dates)이 30일 지난 로그인·가입·코드 시도 기록을 지운다 (30일 안의 것은 남긴다)
#  c 계정 삭제 창: 웹은 늘 구독 해지 안내 한 줄 · 앱에서 내 스토어 구독이 살아 있으면 '요금은 계속 청구' + [구독 관리] (막지는 않는다 — 실제로 지워진다) ·
#    팀 삭제 창: 스토어 구독으로 유료인 팀이면 '구독한 사람이 스토어에서 해지해야 결제가 멈춰요'
#  d 결제 화면: 청약철회 7일 · 기간 중 해지는 다음 갱신만 멈춤
#  e 안드로이드 결제 화면은 '다음 결제일 전에 해지' (애플 24시간 안내가 아니다) · 아이폰은 24시간 그대로
#  f 플랜 혜택에 없는 기능(저장 5GB/30GB · 크레딧 팩 · 읽기 전용 뷰)이 없다 (웹 안내 · 앱 결제 화면)
#  g AI 악보 인식 동의: 코드 인식·채보·악보 만들기는 처음 쓸 때 묻고, 취소하면 /ocr·/omr·/score 를 부르지 않는다 ·
#    한 번 동의하면 다시 묻지 않는다(다른 기기에서도 — 계정 설정) · 설정 › 앱에서 끄면 다시 묻는다 · 광고 보상 인식도 광고 전에 묻는다
#  h 아이폰 앱도 홈에서 시스템 알림 창보다 '알림을 받을까요?'가 먼저 · 이미 허락했으면 조용히 등록 ·
#    '지금 녹음' 아래 마이크 안내 — 마이크를 한 번 받으면 사라진다
import os, sys, time, json, subprocess, urllib.request, urllib.error
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
if not URL.endswith('/'): URL += '/'
API = URL + 'api'
SRV = urlparse(URL)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.environ.get('CONTI_DB') or os.environ.get('DATABASE_URL') or 'postgres://postgres:pg@localhost:54329/postgres'
CRON = os.environ.get('CRON_SECRET', '')
tag = str(int(time.time() * 10))[-7:]
DEL = '지워진 사용자'
def fail(m): print('FAIL:', m); sys.exit(1)

class Sess:
  def __init__(self): self.cookie = ''; self.uid = None; self.user = ''
  def req(self, method, path, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    h = {'content-type': 'application/json', 'x-conti': '1'}
    if self.cookie: h['cookie'] = self.cookie
    h.update(headers or {})
    r = urllib.request.Request(API + path, method=method, data=data, headers=h)
    try:
      with urllib.request.urlopen(r, timeout=60) as resp: st, raw, hd = resp.status, resp.read(), resp.headers
    except urllib.error.HTTPError as e: st, raw, hd = e.code, e.read(), e.headers
    for c in hd.get_all('Set-Cookie') or []:
      if c.startswith('conti_s='): self.cookie = c.split(';')[0]
    try: return st, json.loads(raw or b'{}')
    except Exception: return st, {'raw': raw[:200]}

def signup(user, name):
  s = Sess()
  st, j = s.req('POST', '/auth/signup', {'username': user, 'password': 'secret12', 'name': name})
  if st != 200: fail('가입 실패 %s: %s %s' % (user, st, j))
  s.uid = j['user']['id']; s.user = user; return s

def db(sql, params=()):
  js = """import('pg').then(async ({default:pg})=>{const c=new pg.Client({connectionString:process.env.DB});await c.connect();
    const r=await c.query(process.env.SQL, JSON.parse(process.env.PARAMS));console.log(JSON.stringify(r.rows));await c.end()})
    .catch(e=>{console.log(JSON.stringify({error:e.message}));process.exit(1)})"""
  out = subprocess.run(['node', '-e', js], cwd=ROOT, capture_output=True, text=True,
                       env={**os.environ, 'DB': DB, 'SQL': sql, 'PARAMS': json.dumps(list(params))})
  try: return json.loads(out.stdout.strip().splitlines()[-1])
  except Exception: fail('DB 질의 실패: %s %s' % (out.stdout[-300:], out.stderr[-300:]))

def team_of(s, name):
  st, T = s.req('POST', '/teams', {'name': name, 'myName': s.user})
  if st != 200: fail('팀 만들기 실패: %s %s' % (st, T))
  return T

# ================= a 계정 삭제: 메모 =================
def dbw(sql, params=()):
  r = db(sql, params)
  if isinstance(r, dict) and r.get('error'): fail('DB 쓰기 실패: %s' % r['error'])
  return r
# M 이 팀을 만들고(인도자) L 이 들어온다. M 이 곡 코드를 받고 메모를 쓴 뒤 L 에게 인도자를 넘기고 계정을 지운다
# (팀에 인도자는 한 사람뿐이라 받은 사람이 인도자를 넘긴 뒤 지우는 것이 받은 메모가 팀에 남는 길이다)
M = signup('lgm' + tag, '민수')
T1 = team_of(M, '메모팀' + tag)
TEAM1 = T1['teamId']
L = signup('lgl' + tag, '리더')
st, j = L.req('POST', '/invite/%s/join' % T1['invite'], {'name': '리더', 'session': '건반'})
if st != 200: fail('a 멤버가 못 들어옴: %s %s' % (st, j))
# 다른 팀이 보낸 곡 코드를 M 이 받는다 → 받은 메모는 M 의 id 로 들어간다
st, j = M.req('POST', '/share/take', {'teamId': TEAM1, 'payload': {'v': 1, 'kind': 'song', 'from': {'team': '보낸팀'},
  'songs': [{'title': '받은 곡' + tag, 'arr': {'name': '기본', 'notes': [{'label': 'A', 'text': '받은 메모'}]}}]}})
if st != 200 or not j.get('songs'): fail('a 곡 코드 받기 실패: %s %s' % (st, j))
ARR = j['songs'][0]['arrangementId']; SONG = j['songs'][0]['songId']
def note(s, layer, text, session=None):
  st, j = s.req('POST', '/arrangements/%s/notes' % ARR, {'teamId': TEAM1, 'layer': layer, 'text': text, 'markerLabel': 'A', **({'session': session} if session else {})})
  if st != 200: fail('a 고정 메모 쓰기 실패 (%s): %s %s' % (layer, st, j))
  return j['note']['id']
n_mine = note(M, 'mine', 'M 나만')
n_all = note(M, 'all', 'M 전체')
n_ses = note(M, 'session', 'M 세션', '건반')
rcv = db("select id, author_name from arrangement_notes where arrangement_id=$1 and text='받은 메모'", [ARR])
if len(rcv) != 1 or rcv[0]['author_name'] != '보낸팀 (받음)': fail('a 받은 메모가 예상과 다름: %s' % rcv)
# 녹음: M 이 올린 녹음에 M·L 이 메모
REH = dbw("""insert into rehearsals(team_id, service_id, date, label, blob_id, uploaded_by, expires_at)
            values($1, 'svc-legal', current_date, '법률 녹음', 'rlegal' || $3, $2, now() + interval '90 days') returning id""", [TEAM1, M.uid, tag])[0]['id']
def rnote(s, layer, text, nid):
  st, j = s.req('POST', '/rehearsals/%s/notes' % REH, {'teamId': TEAM1, 'note': {'id': nid, 't': 5, 'layer': layer, 'text': text}})
  if st != 200: fail('a 녹음 메모 실패 (%s): %s %s' % (layer, st, j))
rnote(M, 'mine', 'M 녹음 나만', 'rmine' + tag)
rnote(M, 'session', 'M 녹음 세션', 'rses' + tag)
rnote(M, 'leader', 'M 녹음 전체', 'rlead' + tag)
# 인도자 넘기기 (M → L)
dbw("update members set role='member' where team_id=$1 and user_id=$2", [TEAM1, M.uid])
dbw("update members set role='leader' where team_id=$1 and user_id=$2", [TEAM1, L.uid])
n_L = note(L, 'all', 'L 전체')
n_Lmine = note(L, 'mine', 'L 나만')
rnote(L, 'leader', 'L 녹음 전체', 'rlL' + tag)
rnote(L, 'mine', 'L 녹음 나만', 'rlLm' + tag)
# 시도 기록: M 의 틀린 로그인(아이디|주소) · 사람 id 키 (코드 입력)
st, _ = Sess().req('POST', '/auth/login', {'username': M.user, 'password': 'wrong-pass'})
if st != 401: fail('a 틀린 로그인이 401 이 아님: %s' % st)
dbw("insert into login_attempts(username, n, last) values('promo:' || $1, 1, now()) on conflict do nothing", [M.uid])
dbw("insert into login_attempts(username, n, last) values($1, 1, now()) on conflict do nothing", [M.user + 'x|1.2.3.4'])   # 아이디가 M 의 아이디로 시작하는 다른 사람 (지우면 안 된다)
before = db("select username from login_attempts where username like $1 || '%' or username = 'promo:' || $2", [M.user, M.uid])
if len(before) < 3: fail('a 시도 기록이 안 생김: %s' % before)
# 삭제
st, j = M.req('POST', '/auth/delete', {'username': M.user, 'password': 'secret12'})
if st != 200: fail('a 계정 삭제 실패: %s %s' % (st, j))
rows = {r['id']: r for r in db("select id, layer, author_id, author_name, text from arrangement_notes where arrangement_id=$1", [ARR])}
if n_mine in rows: fail("a M 의 '나만 보기' 고정 메모가 남음")
for nid in (n_all, n_ses):
  r = rows.get(nid)
  if not r: fail('a 팀에 보이게 쓴 고정 메모가 사라짐: %s' % nid)
  if r['author_id'] is not None or r['author_name'] != DEL: fail("a 팀 메모의 쓴 사람이 '지워진 사용자'가 아님: %s" % r)
r = rows.get(rcv[0]['id'])
if not r or r['author_name'] != '보낸팀 (받음)' or r['text'] != '받은 메모': fail('a 곡 코드로 받은 메모가 지워지거나 바뀜: %s' % r)
if not rows.get(n_L) or rows[n_L]['author_id'] != L.uid or rows[n_L]['author_name'] == DEL: fail('a 다른 사람(L)의 메모가 바뀜: %s' % rows.get(n_L))
if not rows.get(n_Lmine): fail("a 다른 사람(L)의 '나만' 메모가 지워짐")
rn = db("select notes from rehearsals where id=$1", [REH])[0]['notes']
by = {x['id']: x for x in rn}
if 'rmine' + tag in by: fail("a M 의 '나만' 녹음 메모가 남음: %s" % rn)
for k in ('rses' + tag, 'rlead' + tag):
  x = by.get(k)
  if not x: fail('a 팀에 보이는 녹음 메모가 사라짐: %s' % k)
  if 'authorId' in x or x.get('author') != DEL: fail("a 녹음 메모의 쓴 사람이 '지워진 사용자'가 아님: %s" % x)
if not by.get('rlL' + tag) or by['rlL' + tag].get('authorId') != L.uid: fail('a L 의 녹음 메모가 바뀜: %s' % by.get('rlL' + tag))
if not by.get('rlLm' + tag): fail("a L 의 '나만' 녹음 메모가 지워짐")
# 화면에 보이는 이름: 곡의 고정 메모 · 녹음 목록의 올린 사람
st, sj = L.req('GET', '/songs/%s?team=%s' % (SONG, TEAM1))
names = {n['id']: n['authorName'] for n in sj.get('notes', [])}
if names.get(n_all) != DEL: fail("a 곡 화면에 지운 사람의 메모가 '지워진 사용자'로 안 보임: %s" % names)
st, rj = L.req('GET', '/rehearsals?team=%s' % TEAM1)
rr = [x for x in rj.get('rehearsals', []) if x['id'] == REH]
if not rr or rr[0].get('uploaderName') != DEL: fail("a 지운 사람이 올린 녹음이 '지워진 사용자'로 안 보임: %s" % rr)
after = db("select username from login_attempts where username like $1 || '%' or username = 'promo:' || $2", [M.user, M.uid])
if [x['username'] for x in after] != [M.user + 'x|1.2.3.4']: fail('a 지운 사람의 시도 기록이 남거나 남의 것까지 지움: %s' % after)
print("a ok — 계정 삭제: '나만' 메모 삭제 · 팀 메모는 '지워진 사용자' · 받은 메모 그대로 · 남의 메모 그대로 · 올린 녹음 '지워진 사용자' · 시도 기록 삭제")

# ================= b 크론: 30일 지난 시도 기록 =================
if not CRON: fail('CRON_SECRET 이 없음 — 서버와 같은 값을 주세요')
dbw("insert into login_attempts(username, n, last) values($1, 3, now() - interval '31 days'), ($2, 3, now() - interval '29 days'), ($3, 1, now() - interval '400 days')",
   ['old' + tag + '|9.9.9.9', 'new' + tag + '|9.9.9.9', 'signup:|' + tag])
req = urllib.request.Request(API + '/cron/dates', headers={'authorization': 'Bearer ' + CRON})
with urllib.request.urlopen(req, timeout=120) as r: cj = json.loads(r.read())
left = sorted(x['username'] for x in db("select username from login_attempts where username in ($1, $2, $3)", ['old' + tag + '|9.9.9.9', 'new' + tag + '|9.9.9.9', 'signup:|' + tag]))
if left != ['new' + tag + '|9.9.9.9']: fail('b 30일 지난 시도 기록이 남거나 30일 안의 것이 지워짐: %s' % left)
if not isinstance(cj.get('attemptsPurged'), int) or cj['attemptsPurged'] < 2: fail('b 크론 응답에 지운 수가 없음: %s' % cj)
print('b ok — 크론이 30일 지난 시도 기록(로그인·가입)을 지움 · 30일 안의 것은 남김')

# ================= 브라우저 =================
MOCK = r"""
(() => {
  const PLAT = '__PLAT__';
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const rc = window.__rc = { calls: [], configured: false, uid: null, owned: [], opened: [], push: { perm: '__PERM__', req: 0, reg: 0 } };
  const log = (n, a) => rc.calls.push({ n, a: a === undefined ? null : JSON.parse(JSON.stringify(a)) });
  const pid = (id) => PLAT === 'android' ? id + (id.endsWith('yearly') ? ':yearly' : ':monthly') : id;
  const ctx = { offeringIdentifier: 'default', placementIdentifier: null, targetingContext: null };
  const price = { pro_monthly: '₩5,500', pro_yearly: '₩55,000', plus_monthly: '₩14,000', plus_yearly: '₩140,000' };
  const pkg = (id) => ({ identifier: id, packageType: 'CUSTOM', offeringIdentifier: 'default', presentedOfferingContext: ctx,
    product: { identifier: pid(id), title: id, price: 1, priceString: price[id], currencyCode: 'KRW', subscriptionPeriod: id.endsWith('yearly') ? 'P1Y' : 'P1M',
      pricePerMonthString: null, introPrice: null, presentedOfferingContext: ctx } });
  const ci = () => ({ activeSubscriptions: rc.owned.map(pid), allPurchasedProductIdentifiers: rc.owned.map(pid), entitlements: { active: {}, all: {} }, originalAppUserId: rc.uid });
  const need = () => { if (!rc.configured) throw new Error('Purchases must be configured before calling this function'); };
  const Purchases = {
    configure: async (o) => { log('configure', o); rc.configured = true; rc.uid = o.appUserID; },
    isConfigured: async () => ({ isConfigured: rc.configured }),
    logIn: async (o) => { log('logIn', o); need(); rc.uid = o.appUserID; return { customerInfo: ci(), created: false }; },
    logOut: async () => { log('logOut'); need(); return { customerInfo: ci() }; },
    setAttributes: async (a) => { log('setAttributes', a); need(); },
    getOfferings: async () => { log('getOfferings'); need(); const off = { identifier: 'default', availablePackages: Object.keys(price).map(pkg) }; return { current: off, all: { default: off } }; },
    getCustomerInfo: async () => { log('getCustomerInfo'); need(); return { customerInfo: ci() }; },
    purchasePackage: async () => { throw Object.assign(new Error('x'), { code: '1', userCancelled: true }); },
    restorePurchases: async () => { need(); return { customerInfo: ci() }; },
  };
  const PushNotifications = {
    checkPermissions: async () => ({ receive: rc.push.perm }),
    requestPermissions: async () => { rc.push.req++; rc.push.perm = 'granted'; return { receive: 'granted' }; },
    register: async () => { rc.push.reg++; }, unregister: async () => {}, createChannel: async () => {},
    removeAllListeners: async () => {}, addListener: async () => ({ remove() {} }),
  };
  window.open = (u) => { rc.opened.push(String(u)); return null; };
  window.Capacitor = {
    getPlatform: () => PLAT, isNativePlatform: () => true, isPluginAvailable: () => false,
    Plugins: { Purchases, PushNotifications,
      App: { addListener: () => Promise.resolve({ remove() {} }), getLaunchUrl: () => Promise.resolve(undefined), exitApp() {}, getInfo: () => Promise.resolve({}) },
      SplashScreen: { hide: () => Promise.resolve() } },
  };
})();
"""

def run():
  with sync_playwright() as p:
    b = p.chromium.launch(args=['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream']); errs = []
    DLG = {'mode': 'accept', 'msgs': []}
    def on_dialog(d):
      DLG['msgs'].append(d.message)
      if DLG['mode'] == 'dismiss': d.dismiss()
      else: d.accept()

    def web():
      c = b.new_context(viewport={'width': 1200, 'height': 900}, service_workers='block')
      c.route('**/*', lambda r: r.continue_() if urlparse(r.request.url).hostname == SRV.hostname else r.abort())
      pg = c.new_page(); pg.on('pageerror', lambda e: errs.append('web: %s' % e)); pg.on('dialog', on_dialog)
      pg.goto(URL); return c, pg

    def native(plat, perm='denied'):
      c = b.new_context(viewport={'width': 390, 'height': 844}, service_workers='block')
      def handler(route):
        u = urlparse(route.request.url)
        if u.scheme == 'https' and u.hostname in ('localhost', 'lets1414.com', 'www.lets1414.com') and u.port is None:
          target = '%s://%s/%s' % (SRV.scheme, SRV.netloc, u.path.lstrip('/')) + ('?' + u.query if u.query else '')
          try: return route.fulfill(response=route.fetch(url=target))
          except Exception:
            try: return route.abort()
            except Exception: return
        if u.hostname == SRV.hostname and u.port == SRV.port: return route.continue_()
        return route.abort()
      c.route('**/*', handler)
      c.add_init_script(MOCK.replace('__PLAT__', plat).replace('__PERM__', perm))
      pg = c.new_page(); pg.on('pageerror', lambda e: errs.append('%s: %s' % (plat, e))); pg.on('dialog', on_dialog)
      pg.goto('https://localhost/')
      return c, pg

    def login(pg, user):
      pg.wait_for_selector('#lgUser', timeout=15000)
      if pg.locator('[data-act="lg-mode"][data-m="login"]').count(): pg.click('[data-act="lg-mode"][data-m="login"]')
      pg.fill('#lgUser', user); pg.fill('#lgPass', 'secret12'); pg.click('[data-act="lg-submit"]')
      pg.wait_for_selector('.shell[data-page]', timeout=15000); pg.wait_for_timeout(500)

    def settings_tab(pg, t):
      pg.evaluate("()=>{CONTI.closeModal();location.hash='#/settings'}"); pg.wait_for_timeout(400)
      pg.click('[data-act="set-tab"][data-t="%s"]' % t); pg.wait_for_timeout(400)

    # ================= c 계정 삭제 · 팀 삭제 창 =================
    W = signup('lgw' + tag, '웹'); team_of(W, '웹팀' + tag)
    c, pg = web(); login(pg, W.user)
    settings_tab(pg, 'account'); pg.click('#sDel'); pg.wait_for_selector('#daSub', timeout=5000)
    t = pg.inner_text('#daSub')
    if '앱에서 구독 중이라면 계정을 지우기 전에 App Store·Google Play 구독 관리에서 먼저 해지해 주세요' not in t: fail('c 웹 계정 삭제 창에 구독 해지 안내가 없음: %r' % t)
    if pg.locator('#daManage').count(): fail('c 웹에 구독 관리 단추가 있음')
    if pg.locator('#daGo').is_disabled(): fail('c 삭제 단추가 막힘')
    # 팀 삭제: 무료 팀은 구독 줄 없음 · 스토어 구독 팀은 있음 (prompt 는 취소)
    pg.evaluate("()=>{CONTI.closeModal();location.hash='#/team'}"); pg.wait_for_selector('[data-act="tm-delete"]', state='attached', timeout=10000)
    DLG['mode'] = 'dismiss'; DLG['msgs'].clear()
    pg.evaluate("document.querySelector('[data-act=\"tm-delete\"]').click()"); pg.wait_for_timeout(500)
    if not DLG['msgs'] or '30일 뒤에' not in DLG['msgs'][-1] or '스토어' in DLG['msgs'][-1]: fail('c 무료 팀 삭제 창이 이상함: %s' % DLG['msgs'])
    dbw("update teams set plan='pro', plan_source='iap', plan_until=now()+interval '30 days', iap_user_id=$2 where id=(select team_id from members where user_id=$1 limit 1)", [W.uid, W.uid])
    pg.reload(); pg.wait_for_selector('.shell[data-page]', timeout=15000); pg.wait_for_timeout(800)
    pg.evaluate("()=>{location.hash='#/team'}"); pg.wait_for_selector('[data-act="tm-delete"]', state='attached', timeout=10000); pg.wait_for_timeout(300)
    DLG['msgs'].clear(); pg.evaluate("document.querySelector('[data-act=\"tm-delete\"]').click()"); pg.wait_for_timeout(500)
    if not DLG['msgs'] or '구독한 사람이 스토어에서 해지해야 결제가 멈춰요' not in DLG['msgs'][-1]: fail('c 스토어 구독 팀 삭제 창에 안내가 없음: %s' % DLG['msgs'])
    DLG['mode'] = 'accept'
    if db("select deleted_at from teams where id=(select team_id from members where user_id=$1 limit 1)", [W.uid])[0]['deleted_at']: fail('c 취소했는데 팀이 지워짐')
    # f 웹 플랜 안내에 없는 기능이 없다
    pg.evaluate("CONTI.upgradeModal()"); pg.wait_for_selector('#modal li', timeout=5000)
    lis = pg.evaluate("[...document.querySelectorAll('#modal li')].map(x=>x.textContent)")
    bad = [x for x in lis if any(k in x for k in ('저장', '크레딧', '읽기 전용'))]
    if bad or '멤버 25명' not in lis or '채보 월 50곡' not in lis: fail('f 웹 플랜 안내 줄이 실제와 다름: %s' % lis)
    c.close()
    print('c ok — 웹 계정 삭제 창: 구독 해지 안내 한 줄 · 팀 삭제 창: 스토어 구독 팀만 "구독한 사람이 스토어에서 해지해야" · f 웹 플랜 줄')

    # 앱(아이폰): 내 스토어 구독이 살아 있으면 '계속 청구' + [구독 관리] · 그래도 지울 수 있다
    PY = signup('lgp' + tag, '구독자'); TP = team_of(PY, '구독팀' + tag)
    dbw("update teams set plan='pro', plan_source='iap', plan_until=now()+interval '30 days', iap_user_id=$2 where id=$1", [TP['teamId'], PY.uid])
    c, pg = native('ios'); login(pg, PY.user)
    settings_tab(pg, 'account'); pg.click('#sDel'); pg.wait_for_selector('#daSub', timeout=8000)
    t = pg.inner_text('#daSub')
    if '계정을 지워도 스토어 구독 요금은 계속 청구돼요. 먼저 [구독 관리]에서 해지해 주세요' not in t or not pg.locator('#daManage').count(): fail('c 앱에서 내 구독이 있는데 안내·구독 관리 단추가 없음: %r' % t)
    pg.click('#daManage'); pg.wait_for_timeout(300)
    if pg.evaluate('__rc.opened')[-1:] != ['itms-apps://apps.apple.com/account/subscriptions']: fail('c 구독 관리가 App Store 구독 화면이 아님: %s' % pg.evaluate('__rc.opened'))
    if not pg.locator('#daSub').count(): fail('c 구독 관리를 누르니 삭제 창이 닫힘')
    pg.fill('#daUser', PY.user); pg.fill('#daPw', 'secret12'); pg.click('#daGo')
    for _ in range(40):
      if not db("select 1 from users where id=$1", [PY.uid]): break
      pg.wait_for_timeout(250)
    else: fail('c 구독 안내가 있어도 계정은 지울 수 있어야 함 (안 지워짐)')
    c.close()
    # 앱에서 구독이 없으면 한 줄 안내만
    c, pg = native('android'); login(pg, L.user)
    settings_tab(pg, 'account'); pg.click('#sDel'); pg.wait_for_selector('#daSub', timeout=8000)
    if pg.locator('#daManage').count() or '먼저 해지해 주세요' not in pg.inner_text('#daSub'): fail('c 구독 없는 앱 사용자 삭제 창이 이상함: %r' % pg.inner_text('#daSub'))
    if pg.evaluate("__rc.calls.filter(x=>x.n==='configure').length"): fail('c 구독 없는 사람의 삭제 창이 결제 쪽(RevenueCat)에 붙음')
    pg.evaluate("CONTI.closeModal()")
    # d·e·f 안드로이드 결제 화면
    pg.evaluate("CONTI.upgradeModal()"); pg.wait_for_selector('#pay', timeout=5000); pg.wait_for_function("()=>!CONTI.IAP.loading", timeout=10000)
    lg = pg.inner_text('#payLegal')
    for must in ['다음 결제일 전에 해지하지 않으면 결제일에 같은 요금으로 다음 기간 요금이 청구돼요', '결제 후 7일 이내에는 청약을 철회할 수 있어요',
                 '결제 뒤 유료 기능을 쓰기 시작했다면 철회가 제한될 수 있어요 · 이용약관 제5조의2', '기간 중에 해지하면 다음 갱신만 멈추고, 이미 결제한 기간 요금은 자동으로 돌아가지 않아요']:
      if must not in lg: fail('d/e 안드로이드 결제 안내에 "%s" 없음: %s' % (must, lg))
    if '24시간' in lg: fail('e 안드로이드에 애플 24시간 안내가 나옴: %s' % lg)
    cards = pg.inner_text('#pay')
    if any(k in cards for k in ('저장 5GB', '저장 30GB', '크레딧 팩', '읽기 전용 뷰')): fail('f 결제 화면에 없는 기능이 있음')
    c.close()
    c, pg = native('ios'); login(pg, L.user)
    pg.evaluate("CONTI.upgradeModal()"); pg.wait_for_selector('#pay', timeout=5000); pg.wait_for_function("()=>!CONTI.IAP.loading", timeout=10000)
    lg = pg.inner_text('#payLegal')
    if '24시간 전까지 해지하지 않으면' not in lg or '다음 결제일' in lg or '청약을 철회할 수 있어요' not in lg: fail('d/e 아이폰 결제 안내가 이상함: %s' % lg)
    c.close()
    print('c ok — 앱: 내 구독이 있으면 "계속 청구" + 구독 관리(App Store) · 그래도 지워짐 · 구독 없으면 한 줄(결제 쪽 안 붙음) · d·e·f 결제 화면')

    # ================= g AI 악보 인식 동의 =================
    G = signup('lgg' + tag, '지은'); team_of(G, 'AI팀' + tag)
    c, pg = web(); login(pg, G.user)
    sent = []
    pg.on('request', lambda r: sent.append(urlparse(r.url).path) if r.method == 'POST' and urlparse(r.url).path in ('/api/ocr', '/api/omr', '/api/score') else None)
    pg.evaluate("""async()=>{const c=document.createElement('canvas');c.width=600;c.height=400;const x=c.getContext('2d');x.fillStyle='#fff';x.fillRect(0,0,600,400);
      x.fillStyle='#000';x.font='40px sans-serif';x.fillText('G   C   D   Em',40,80);for(let i=0;i<5;i++)x.fillRect(20,150+i*12,560,1);
      const b=await new Promise(r=>c.toBlob(r,'image/jpeg',0.9));await CONTI.IDB.put('blobs','lgblob',b);
      window.__p={id:'lgp',blob:'lgblob',w:600,h:400,chords:[],markers:[]};window.__it={id:'lgit',pieces:[window.__p]};window.__svc={id:'lgsvc',items:[window.__it]}}""")
    if pg.evaluate('CONTI.aiOk()'): fail('g 새 사람인데 이미 동의한 것으로 나옴')
    for fn in ('askOcr', 'transcribePiece', 'rebuildScore', 'recognizeChords'):
      pg.evaluate("()=>{window.__r=CONTI.%s(__svc,__it,__p)}" % fn)
      pg.wait_for_selector('#aiCons', timeout=5000)
      tx = pg.inner_text('#aiCons')
      if '악보를 AI로 읽어요' not in tx or '구글(Gemini·Cloud Vision, 미국)' not in tx or '사진은 인식에만 쓰여요' not in tx: fail('g 동의 창 문구가 다름 (%s): %r' % (fn, tx))
      if not pg.locator('#aiConsNo').count() or '동의하고 계속' not in pg.inner_text('#aiConsOk'): fail('g 동의 창 단추가 다름')
      pg.wait_for_timeout(300)
      if sent: fail('g 동의하기 전에 서버로 보냄 (%s): %s' % (fn, sent))
      pg.click('#aiConsNo'); pg.wait_for_timeout(600)
      if sent: fail('g 취소했는데 서버로 보냄 (%s): %s' % (fn, sent))
      if pg.evaluate('__p.ocr'): fail('g 취소했는데 인식이 시작됨 (%s): %s' % (fn, pg.evaluate('__p.ocr')))
    # 바깥을 눌러 닫아도 취소
    pg.evaluate("()=>{window.__r=CONTI.transcribePiece(__svc,__it,__p)}"); pg.wait_for_selector('#aiCons', timeout=5000)
    pg.evaluate("CONTI.closeModal()"); pg.wait_for_timeout(500)
    if sent: fail('g 동의 창을 닫았는데 서버로 보냄: %s' % sent)
    # 동의 → 그 자리에서 이어서 보낸다
    pg.evaluate("()=>{window.__r=CONTI.askOcr(__svc,__it,__p)}"); pg.wait_for_selector('#aiCons', timeout=5000)
    pg.click('#aiConsOk')
    for _ in range(60):
      if '/api/ocr' in sent: break
      if pg.locator('#ocrGo').count(): pg.click('#ocrGo')   # 한도 검사가 켜진 서버면 남은 곡 확인 창이 이어서 뜬다
      pg.wait_for_timeout(250)
    else: fail('g 동의했는데 코드 인식을 보내지 않음')
    pg.wait_for_timeout(1500)
    pref = G.req('GET', '/me/prefs')[1].get('prefs', {})
    if not isinstance(pref.get('aiOk'), str) or not pref['aiOk'].startswith('20'): fail('g 동의가 계정 설정에 안 남음: %s' % pref.get('aiOk'))
    # 한 번 동의하면 다른 기능도 묻지 않는다
    pg.evaluate("CONTI.closeModal()")
    n0 = len(sent)
    pg.evaluate("()=>{window.__r=CONTI.transcribePiece(__svc,__it,__p)}")
    for _ in range(60):
      if '/api/omr' in sent[n0:]: break
      if pg.locator('#aiCons').count(): fail('g 동의했는데 채보에서 또 물음')
      pg.wait_for_timeout(250)
    else: fail('g 동의 뒤 채보를 보내지 않음')
    c.close()
    # 다른 기기(새 브라우저)에서도 묻지 않는다 — 계정 설정을 따라온다
    c, pg = web(); login(pg, G.user)
    pg.wait_for_function("()=>CONTI.PREFS.data!==null", timeout=8000)
    if not pg.evaluate('CONTI.aiOk()'): fail('g 다른 기기에서 동의가 안 따라옴')
    # 설정 › 앱에서 끄면 다시 묻는다
    settings_tab(pg, 'app'); pg.wait_for_selector('#sAiOk', timeout=5000)
    if not pg.is_checked('#sAiOk'): fail('g 설정의 동의 상자가 꺼져 있음')
    pg.click('#sAiOk'); pg.wait_for_timeout(1200)
    pref = G.req('GET', '/me/prefs')[1].get('prefs', {})
    if pref.get('aiOk') is not False: fail('g 설정에서 끈 것이 계정 설정에 안 남음: %s' % pref.get('aiOk'))
    if pg.evaluate('CONTI.aiOk()'): fail('g 끈 뒤에도 동의한 것으로 나옴')
    if pg.evaluate("localStorage.getItem('conti-ai-ok')") not in (None, '{}'): fail('g 끈 뒤에 이 기기 기록이 남음: %s' % pg.evaluate("localStorage.getItem('conti-ai-ok')"))
    pg.evaluate("""async()=>{const c=document.createElement('canvas');c.width=200;c.height=100;const b=await new Promise(r=>c.toBlob(r,'image/jpeg',0.9));
      await CONTI.IDB.put('blobs','lgblob2',b);window.__p={id:'lgp2',blob:'lgblob2',w:200,h:100,chords:[],markers:[]};window.__it={id:'lgit2',pieces:[window.__p]};window.__svc={id:'lgsvc2',items:[window.__it]}}""")
    pg.evaluate("()=>{window.__r=CONTI.transcribePiece(__svc,__it,__p)}"); pg.wait_for_selector('#aiCons', timeout=5000)
    pg.click('#aiConsNo')
    c.close()
    # 앱의 광고 보상 인식도 광고 전에 묻는다 (광고가 붙지 않는 흉내라 코드 순서로 본다)
    src = open(os.path.join(ROOT, 'app', 'index.html'), encoding='utf-8').read()
    body = src[src.index('async function rewardSheet('):]
    body = body[:body.index('\nasync function ', 10) if '\nasync function ' in body[10:] else 4000]
    if body.find('aiConsent()') < 0 or body.find('aiConsent()') > body.find('rewardStatusOf('): fail('g 광고 보상 인식이 광고 전에 동의를 묻지 않음')
    print('g ok — AI 동의: 네 기능 모두 처음에 묻고 취소·닫기면 안 보냄 · 동의하면 이어서 보냄 · 계정 설정에 남아 다른 기기도 · 설정에서 끄면 다시 물음 · 광고 보상도 광고 전에')

    # ================= h 아이폰 알림 안내 · 마이크 안내 =================
    c, pg = native('ios', perm='prompt'); login(pg, L.user)
    pg.evaluate("()=>{location.hash='#/home'}")
    pg.wait_for_selector('#pbYes', timeout=8000)
    if '알림을 받을까요?' not in pg.inner_text('#modal'): fail('h 아이폰 알림 안내 창 문구가 다름')
    if pg.evaluate('__rc.push.req'): fail('h 아이폰에서 안내 창보다 시스템 권한 창이 먼저 뜸')
    pg.click('#pbYes'); pg.wait_for_timeout(800)
    if pg.evaluate('__rc.push.req') != 1 or not pg.evaluate('__rc.push.reg'): fail('h "알림 받기"를 눌렀는데 권한을 묻거나 등록하지 않음: %s' % pg.evaluate('__rc.push'))
    c.close()
    c, pg = native('ios', perm='granted'); login(pg, L.user)
    pg.evaluate("()=>{location.hash='#/home'}"); pg.wait_for_timeout(2500)
    if pg.locator('#pbYes').count(): fail('h 이미 허락한 아이폰에 안내 창이 또 뜸')
    if not pg.evaluate('__rc.push.reg') or pg.evaluate('__rc.push.req'): fail('h 이미 허락한 아이폰이 조용히 등록하지 않음: %s' % pg.evaluate('__rc.push'))
    c.close()
    # 마이크 안내 (웹 · 가짜 마이크)
    c, pg = web(); login(pg, L.user)
    pg.evaluate("()=>{try{localStorage.removeItem('conti-mic-ok')}catch(e){}CONTI.rehAddModal({id:'svc-legal',date:'2026-10-01'})}")
    pg.wait_for_selector('#rhRec', timeout=5000)
    if not pg.locator('#rhMicNote').count() or '녹음하려면 마이크 권한이 필요해요 · 허용하지 않아도 다른 기능은 그대로 쓸 수 있어요' not in pg.inner_text('#rhMicNote'): fail('h 지금 녹음 아래 마이크 안내가 없음')
    pg.click('#rhRec'); pg.wait_for_function("(document.getElementById('rhPick')||{}).textContent==='녹음 중…'", timeout=8000)
    if pg.locator('#rhMicNote').count(): fail('h 마이크를 받았는데 안내가 남음')
    pg.click('#rhRec'); pg.wait_for_timeout(600)
    pg.evaluate("CONTI.closeModal()"); pg.wait_for_timeout(300)
    pg.evaluate("CONTI.rehAddModal({id:'svc-legal',date:'2026-10-01'})"); pg.wait_for_selector('#rhRec', timeout=5000)
    if pg.locator('#rhMicNote').count(): fail('h 마이크를 한 번 받은 뒤에도 안내가 또 나옴')
    pg.evaluate("CONTI.closeModal()")
    c.close()
    print('h ok — 아이폰: 시스템 창보다 "알림을 받을까요?"가 먼저 · 허락한 기기는 조용히 등록 · 마이크 안내는 처음에만')

    real = [e for e in errs if 'ERR_' not in e]
    if real: fail('페이지 오류: %s' % real[:5])
    b.close()

run()
print('ALL OK — test_legal_code')
