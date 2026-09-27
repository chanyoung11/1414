# 앱 결제 (RevenueCat · 애플·구글 인앱결제) — 가짜 결제 플러그인으로 본다 (tests/test_banner.py 의 가짜 AdMob 처럼)
#
# 사용: CONTI_URL=http://localhost:9942/ CONTI_DB=postgres://… RC_WEBHOOK_SECRET=… .venv/bin/python tests/test_payments.py
#   서버는 RC_WEBHOOK_SECRET · RC_PUBLIC_KEY_IOS=appl_… · RC_PUBLIC_KEY_ANDROID=goog_… 를 켜고 (한도 검사 ENFORCE_PLAN 은 켜도 꺼도 된다 ·
#   TRIAL_DAYS 는 기본 7) (CONTI_DB 는 서버와 같은 DB). 앱은 https://localhost 를 흉내 내고(NATIVE) 요청은 전부 로컬 서버로 — 밖으로 안 나간다.
#   가짜 Purchases 는 플러그인(@revenuecat/purchases-capacitor 13)의 네이티브 답 모양을 따른다:
#   getOfferings → {current, all} · getCustomerInfo·restorePurchases → {customerInfo} · purchasePackage → {productIdentifier, customerInfo, transaction} ·
#   오류는 code 가 문자열 숫자('1' = 사용자가 취소)이고 data 에 자세한 것 · 안드로이드 상품 id 는 '구독 id:기본 요금제 id'
#
# 본다
#  0 서버: /api/health 가 공개 키를 준다 (웹훅 비밀이 없으면 · 비밀 키 모양이면 안 준다) · 구글 상품 id(pro_monthly:monthly)도 플랜으로 ·
#    팀 보기의 payerId (스토어 구독을 산 사람)
#  1 키가 없으면(서버가 iap 를 안 줌) 결제 플러그인을 한 번도 안 부르고 예전 그대로 '결제 준비 중이에요' · 플러그인이 없는 예전 앱도 같다
#  2 웹: 사는 단추 없음 · '결제는 앱에서만' · 결제 쪽 기능 꺼짐
#  3 아이폰: 로그인하면 우리 사용자 id 로 설정(configure · 기기 식별 수집 끔) · 결제 화면에 스토어 가격·기간(월간·연간) ·
#    체험 중이면 '체험 중 · N일 남음' · 자동 갱신 안내 · 이용약관(EULA)·개인정보처리방침 · 구매 복원 · 구독 관리
#  4 취소는 조용히 · 스토어 오류는 한국어 · 사기 직전에 setAttributes({teamId})
#  5 결제 → '결제 확인 중…' → 웹훅이 팀을 올리면 '구독이 시작됐어요' · 설정 → 플랜에 '내 스토어 구독' · 구매 복원 · 구독 관리(App Store)
#  6 늦은 웹훅: 창에서 기다리는 시간을 넘으면 안내하고 뒤에서 계속 기다리다 반영되면 알린다
#  7 안드로이드: Pro → Plus 는 옛 구독을 넘겨(storeProductChangeInfo) 두 개가 되지 않게 · 구독 관리(Play 스토어 · sku) · 로그아웃하면 logOut
#  8 인도자가 아니면 못 산다 (설정 → 플랜도 안 보임) · 다른 팀원의 스토어 구독으로 쓰는 팀은 그 사람만 바꿀 수 있다
import os, sys, time, json, subprocess, urllib.request, urllib.error
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
if not URL.endswith('/'): URL += '/'
API = URL + 'api'
SRV = urlparse(URL)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.environ.get('CONTI_DB') or os.environ.get('DATABASE_URL') or 'postgres://postgres:pg@localhost:54329/postgres'
SECRET = os.environ.get('RC_WEBHOOK_SECRET', '')
tag = str(int(time.time() * 10))[-7:]
def fail(m): print('FAIL:', m); sys.exit(1)

class Sess:
  def __init__(self): self.cookie = ''; self.uid = None
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
  s.uid = j['user']['id']; return s

def db(sql, params=()):
  js = """import('pg').then(async ({default:pg})=>{const c=new pg.Client({connectionString:process.env.DB});await c.connect();
    const r=await c.query(process.env.SQL, JSON.parse(process.env.PARAMS));console.log(JSON.stringify(r.rows));await c.end()})
    .catch(e=>{console.log(JSON.stringify({error:e.message}));process.exit(1)})"""
  out = subprocess.run(['node', '-e', js], cwd=ROOT, capture_output=True, text=True,
                       env={**os.environ, 'DB': DB, 'SQL': sql, 'PARAMS': json.dumps(list(params))})
  try: return json.loads(out.stdout.strip().splitlines()[-1])
  except Exception: fail('DB 질의 실패: %s %s' % (out.stdout[-300:], out.stderr[-300:]))

N = {'ev': 0}
def hook(ev):
  N['ev'] += 1
  ev = {'id': 'ev%s-%d' % (tag, N['ev']), 'expiration_at_ms': int(time.time() * 1000) + 30 * 86400000, **ev}
  req = urllib.request.Request(API + '/iap/webhook', method='POST', data=json.dumps({'event': ev}).encode(),
                               headers={'content-type': 'application/json', 'authorization': SECRET})
  try:
    with urllib.request.urlopen(req, timeout=30) as r: return r.status, json.loads(r.read() or b'{}')
  except urllib.error.HTTPError as e: return e.code, json.loads(e.read() or b'{}')

def node(js, env=None):
  out = subprocess.run(['node', '--input-type=module', '-e', js], cwd=ROOT, capture_output=True, text=True, env={**os.environ, **(env or {})})
  try: return json.loads(out.stdout.strip().splitlines()[-1])
  except Exception: fail('node 실패: %s %s' % (out.stdout[-400:], out.stderr[-600:]))

# ================= 0 서버 =================
if not SECRET: fail('RC_WEBHOOK_SECRET 이 없음 — 서버와 같은 값을 주세요')
hl = json.loads(urllib.request.urlopen(API + '/health', timeout=10).read())
ENF = bool(hl.get('enforcePlan'))
KEYS = hl.get('iap') or {}
if not (KEYS.get('ios', '').startswith('appl_') and KEYS.get('android', '').startswith('goog_')):
  fail('서버가 공개 키를 안 줌 (RC_PUBLIC_KEY_IOS=appl_… · RC_PUBLIC_KEY_ANDROID=goog_… · RC_WEBHOOK_SECRET): %s' % hl)
o = node("""
const env = (e) => { for (const k of ['RC_WEBHOOK_SECRET','RC_PUBLIC_KEY_IOS','RC_PUBLIC_KEY_ANDROID']) delete process.env[k]; Object.assign(process.env, e); };
const m = await import(process.env.ROOT + '/lib/iap.js');
const out = {};
env({ RC_PUBLIC_KEY_IOS: 'appl_abcdefgh12', RC_PUBLIC_KEY_ANDROID: 'goog_abcdefgh12' }); out.noSecret = m.rcPublicKeys();
env({ RC_WEBHOOK_SECRET: 's', RC_PUBLIC_KEY_IOS: 'sk_abcdefgh12345', RC_PUBLIC_KEY_ANDROID: 'goog_abcdefgh12' }); out.secretKey = m.rcPublicKeys();
env({ RC_WEBHOOK_SECRET: 's', RC_PUBLIC_KEY_IOS: 'goog_abcdefgh12' }); out.wrongPlat = m.rcPublicKeys();
env({ RC_WEBHOOK_SECRET: 's' }); out.none = m.rcPublicKeys();
out.gp = m.planFromEvent({ type: 'INITIAL_PURCHASE', product_id: 'plus_yearly:yearly', app_user_id: 'u' });
out.gc = m.planFromEvent({ type: 'PRODUCT_CHANGE', product_id: 'pro_monthly:monthly', new_product_id: 'plus_monthly:monthly', app_user_id: 'u' });
out.gx = m.planFromEvent({ type: 'EXPIRATION', product_id: 'pro_monthly:monthly', app_user_id: 'u' });
console.log(JSON.stringify(out));""", {'ROOT': ROOT})
if o['noSecret'] is not None: fail('웹훅 비밀이 없는데 공개 키를 줌: %s' % o['noSecret'])
if o['secretKey'] != {'ios': '', 'android': 'goog_abcdefgh12'}: fail('비밀 키(sk_) 모양을 그대로 줌: %s' % o['secretKey'])
if o['wrongPlat'] is not None: fail('iOS 자리에 안드로이드 키를 줌: %s' % o['wrongPlat'])
if o['none'] is not None: fail('키가 없는데 iap 를 줌: %s' % o['none'])
if o['gp'].get('kind') != 'grant' or o['gp'].get('plan') != 'plus' or o['gp'].get('product') != 'plus_yearly': fail('구글 상품 id(구독:기본 요금제)를 모름: %s' % o['gp'])
if o['gc'].get('kind') != 'grant' or o['gc'].get('plan') != 'plus': fail('구글 상품 바꾸기를 모름: %s' % o['gc'])
if o['gx'].get('kind') != 'revoke': fail('구글 상품 만료를 모름: %s' % o['gx'])
print('0 ok — /health 공개 키(웹훅 비밀 있을 때 · 공개 키 모양만) · 구글 상품 id')

MOCK = r"""
(() => {
  const PLAT = '__PLAT__', NOPLUG = __NOPLUG__;
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const rc = window.__rc = { calls: [], attrs: {}, uid: null, configured: false, owned: [], buy: 'ok', delay: 400, opened: [], missing: [],
    price: { pro_monthly: ['₩5,500', 5500, null], pro_yearly: ['₩55,000', 55000, '₩4,583'], plus_monthly: ['₩14,000', 14000, null], plus_yearly: ['₩140,000', 140000, '₩11,666'] } };
  const log = (n, a) => rc.calls.push({ n, a: a === undefined ? null : JSON.parse(JSON.stringify(a)) });
  const pid = (id) => PLAT === 'android' ? id + (id.endsWith('yearly') ? ':yearly' : ':monthly') : id;
  const prod = (id) => ({ identifier: pid(id), title: id, description: '', price: rc.price[id][1], priceString: rc.price[id][0], currencyCode: 'KRW',
    subscriptionPeriod: id.endsWith('yearly') ? 'P1Y' : 'P1M', pricePerMonthString: rc.price[id][2], introPrice: null,
    productCategory: 'SUBSCRIPTION', productType: 'AUTO_RENEWABLE_SUBSCRIPTION', presentedOfferingContext: ctx });
  const ctx = { offeringIdentifier: 'default', placementIdentifier: null, targetingContext: null };
  const pkg = (id) => ({ identifier: id, packageType: 'CUSTOM', product: prod(id), offeringIdentifier: 'default', presentedOfferingContext: ctx, webCheckoutUrl: null });
  const ci = () => ({ activeSubscriptions: rc.owned.map(pid), allPurchasedProductIdentifiers: rc.owned.map(pid), entitlements: { active: {}, all: {} },
    managementURL: null, originalAppUserId: rc.uid, latestExpirationDate: null });
  const err = (code, msg, extra) => Object.assign(new Error(msg), { code: String(code), data: Object.assign({ code, message: msg, readableErrorCode: 'E' + code }, extra || {}) });
  const need = () => { if (!rc.configured) throw new Error('Purchases must be configured before calling this function'); };
  const Purchases = {
    configure: async (o) => { log('configure', o); rc.configured = true; rc.uid = o.appUserID || '$RCAnonymousID:a'; },
    isConfigured: async () => { log('isConfigured'); return { isConfigured: rc.configured }; },
    logIn: async (o) => { log('logIn', o); need(); rc.uid = o.appUserID; return { customerInfo: ci(), created: false }; },
    logOut: async () => { log('logOut'); need(); rc.uid = '$RCAnonymousID:b'; rc.owned = []; return { customerInfo: ci() }; },
    setAttributes: async (a) => { log('setAttributes', a); need(); Object.assign(rc.attrs, a); },
    getOfferings: async () => { log('getOfferings'); need(); await sleep(150); if (rc.offFail) throw err(10, 'Error performing request.');
      const ids = ['pro_monthly', 'pro_yearly', 'plus_monthly', 'plus_yearly'].filter((x) => !rc.missing.includes(x));
      const off = { identifier: 'default', serverDescription: '', metadata: {}, availablePackages: ids.map(pkg), lifetime: null, annual: null, sixMonth: null,
        threeMonth: null, twoMonth: null, monthly: null, weekly: null, webCheckoutUrl: null };
      return { current: off, all: { default: off } }; },
    getCustomerInfo: async () => { log('getCustomerInfo'); need(); return { customerInfo: ci() }; },
    purchasePackage: async (o) => { log('purchasePackage', o); need(); await sleep(rc.delay); const m = rc.buy;
      if (m === 'cancel') throw err(1, 'Purchase was cancelled.', { userCancelled: true });
      if (m.startsWith('error:')) throw err(+m.slice(6), 'There was a problem with the store.', { userCancelled: false });
      const id = String(o.aPackage.product.identifier).split(':')[0]; rc.owned = [id];
      return { productIdentifier: o.aPackage.product.identifier, customerInfo: ci(), transaction: { transactionIdentifier: 'tx' + Date.now(), productIdentifier: o.aPackage.product.identifier, purchaseDate: new Date().toISOString() } }; },
    restorePurchases: async () => { log('restorePurchases'); need(); await sleep(150); return { customerInfo: ci() }; },
  };
  window.open = (u) => { rc.opened.push(String(u)); return null; };
  window.Capacitor = {
    getPlatform: () => PLAT, isNativePlatform: () => true, isPluginAvailable: () => false,
    Plugins: Object.assign(NOPLUG ? {} : { Purchases }, {
      App: { addListener: () => Promise.resolve({ remove() {} }), getLaunchUrl: () => Promise.resolve(undefined), exitApp() {}, getInfo: () => Promise.resolve({}) },
      SplashScreen: { hide: () => Promise.resolve() },
    }),
  };
})();
"""

def run():
  with sync_playwright() as p:
    b = p.chromium.launch(); errs = []

    def native(plat, keys=True, plug=True, vw=390, vh=844):
      c = b.new_context(viewport={'width': vw, 'height': vh}, service_workers='block')
      def handler(route):
        u = urlparse(route.request.url)
        if u.scheme == 'https' and u.hostname in ('localhost', 'lets1414.com', 'www.lets1414.com') and u.port is None:
          target = '%s://%s/%s' % (SRV.scheme, SRV.netloc, u.path.lstrip('/')) + ('?' + u.query if u.query else '')
          try:
            r = route.fetch(url=target)
            if u.path == '/api/health' and not keys:   # 키를 안 주는 서버 흉내
              j = r.json(); j.pop('iap', None)
              return route.fulfill(status=r.status, headers={'content-type': 'application/json'}, body=json.dumps(j))
            return route.fulfill(response=r)
          except Exception:
            try: return route.abort()
            except Exception: return
        if u.hostname == SRV.hostname and u.port == SRV.port: return route.continue_()
        return route.abort()   # 바깥(글꼴 CDN·광고)은 막는다
      c.route('**/*', handler)
      c.add_init_script(MOCK.replace('__PLAT__', plat).replace('__NOPLUG__', 'false' if plug else 'true'))
      pg = c.new_page()
      pg.on('pageerror', lambda e: errs.append('%s: %s' % (plat, e))); pg.on('dialog', lambda d: d.accept())
      pg.goto('https://localhost/')
      if not pg.evaluate('/^(capacitor|ionic):/.test(location.protocol)||(location.hostname==="localhost"&&!location.port&&location.protocol==="https:")'): fail('앱 흉내가 안 됨 (NATIVE 아님)')
      return c, pg

    def login(pg, user):
      pg.wait_for_selector('#lgUser', timeout=15000)
      if pg.locator('[data-act="lg-mode"][data-m="login"]').count(): pg.click('[data-act="lg-mode"][data-m="login"]')
      pg.fill('#lgUser', user); pg.fill('#lgPass', 'secret12'); pg.click('[data-act="lg-submit"]')
      pg.wait_for_selector('.shell[data-page]', timeout=15000); pg.wait_for_timeout(600)

    def calls(pg, name=None):
      cs = pg.evaluate('__rc.calls')
      return [x for x in cs if name is None or x['n'] == name]

    def plan_tab(pg):
      pg.evaluate("()=>{location.hash='#/settings'}"); pg.wait_for_timeout(400)
      pg.click('[data-act="set-tab"][data-t="plan"]'); pg.wait_for_timeout(500)

    def open_pay(pg):
      pg.evaluate("()=>{CONTI.closeModal();CONTI.upgradeModal()}")
      pg.wait_for_selector('#pay', timeout=5000)
      pg.wait_for_function("()=>!CONTI.IAP.loading", timeout=10000); pg.wait_for_timeout(150)

    def pay_state(pg):
      return pg.evaluate("""(()=>{const q=s=>document.querySelector(s),t=s=>(q(s)||{}).textContent||'';
        const btns=[...document.querySelectorAll('#pay [data-pay="buy"]')].map(b=>({prod:b.dataset.prod,dis:b.disabled,txt:b.textContent.trim()}));
        return {btns,msg:t('#payMsg'),bad:!!(q('#payMsg')&&q('#payMsg').classList.contains('bad')),block:t('#payBlock'),trial:t('#payTrial'),now:t('#payNow'),
          prices:[...document.querySelectorAll('#pay .paycard')].map(c=>c.dataset.plan+':'+c.querySelector('.payprice').textContent.trim()+' '+c.querySelector('.payprice').nextElementSibling.textContent.trim()),
          legal:t('#payLegal'),lg:[...document.querySelectorAll('#pay [data-lg]')].map(x=>x.dataset.lg),
          restore:!!q('#pay [data-pay="restore"]'),manage:!!q('#pay [data-pay="manage"]'),
          team:{plan:CONTI.S.team.plan,src:CONTI.S.team.planSource,payer:CONTI.S.team.payerId}}})()""")

    def buy_btn(pg, prod):
      return pg.locator('#pay [data-pay="buy"][data-prod="%s"]' % prod)

    def toast_text(pg):
      return pg.evaluate("(()=>{const t=document.getElementById('toast');return t&&t.classList.contains('show')?t.textContent:''})()")

    # ---- 계정: 인도자(체험 팀) · 같은 팀 멤버
    L = signup('pyl' + tag, '리더')
    st, T = L.req('POST', '/teams', {'name': '결제팀' + tag, 'myName': '리더'})
    if st != 200 or T.get('planSource') != 'trial': fail('체험 팀이 안 만들어짐: %s %s' % (st, T))
    TEAM = T['teamId']
    M = signup('pym' + tag, '멤버')
    st, j = M.req('POST', '/invite/%s/join' % T['invite'], {'name': '멤버', 'session': '건반'})
    if st != 200: fail('멤버가 못 들어옴: %s %s' % (st, j))

    # 설정 → 플랜 카드: 구분선(.hr)이 맨 아래에 남거나 두 줄 겹치면 그 자리들 (앱은 코드 칸이 없다)
    HR_BAD = "()=>{const c=document.getElementById('sPlanPill').closest('.card'),k=[...c.children],h=e=>!!e&&e.classList.contains('hr');return k.map((e,i)=>h(e)&&(i===k.length-1||h(k[i+1]))?i:-1).filter(i=>i>=0)}"
    # ================= 1 키가 없으면 · 플러그인이 없는 예전 앱 =================
    for label, kw in [('키 없음', {'keys': False}), ('예전 앱(플러그인 없음)', {'plug': False})]:
      c, pg = native('ios', **kw)
      login(pg, 'pyl' + tag)
      pg.wait_for_timeout(800)
      if kw.get('plug', True) and calls(pg): fail('%s: 결제 플러그인을 부름 %s' % (label, calls(pg)))
      if pg.evaluate('CONTI.iapOn()'): fail('%s: 결제가 켜짐' % label)
      plan_tab(pg)
      # 한도 검사가 켜져 있으면 예전처럼 체험 팀에 '플랜 올리기'가 있다 (눌러도 '결제 준비 중') · 꺼져 있으면 없다
      if pg.locator('#sIap').count() or bool(pg.locator('[data-act="upgrade"]').count()) != ENF: fail('%s: 설정 → 플랜 단추가 예전과 다름 (한도 검사 %s)' % (label, ENF))
      if pg.evaluate(HR_BAD): fail('%s: 플랜 카드 구분선이 맨 아래에 남거나 두 줄 %s' % (label, pg.evaluate(HR_BAD)))
      pg.evaluate("CONTI.upgradeModal()"); pg.wait_for_selector('#modal [data-act="buy"]', timeout=5000)
      if pg.locator('#pay').count(): fail('%s: 새 결제 화면이 열림' % label)
      pg.click('#modal [data-act="buy"][data-p="pro"]'); pg.wait_for_timeout(300)
      if '결제 준비 중이에요' not in toast_text(pg): fail('%s: 예전처럼 "결제 준비 중이에요"가 아님: %r' % (label, toast_text(pg)))
      if kw.get('plug', True) and calls(pg): fail('%s: 결제 플러그인을 부름 %s' % (label, calls(pg)))
      c.close()
    print('1 ok — 키가 없거나 플러그인이 없으면 결제 플러그인을 안 부르고 예전처럼 "결제 준비 중이에요"')

    # ================= 2 웹 =================
    c = b.new_context(viewport={'width': 1200, 'height': 900}, service_workers='block')
    c.route('**/*', lambda r: r.continue_() if urlparse(r.request.url).hostname == SRV.hostname else r.abort())
    pg = c.new_page(); pg.on('pageerror', lambda e: errs.append('web: %s' % e)); pg.on('dialog', lambda d: d.accept())
    pg.goto(URL); login(pg, 'pyl' + tag)
    if pg.evaluate('CONTI.iapOn()'): fail('웹에서 앱 결제가 켜짐')
    plan_tab(pg)
    if pg.locator('#sIap').count(): fail('웹 설정 → 플랜에 구매 복원·구독 관리가 보임')
    pg.evaluate("CONTI.upgradeModal()"); pg.wait_for_selector('#modal .cb-note', timeout=5000)
    w = pg.evaluate("({buy:document.querySelectorAll('#modal [data-act=\"buy\"],#modal [data-pay]').length,note:document.querySelector('#modal .cb-note').textContent,pay:!!document.getElementById('pay')})")
    if w['buy'] or w['pay']: fail('웹에 사는 단추가 있음: %s' % w)
    if '앱에서만' not in w['note']: fail('웹 안내가 "결제는 앱에서만"이 아님: %s' % w)
    c.close()
    print('2 ok — 웹: 사는 단추 없음 · "결제는 앱에서만"')

    # ================= 3~6 아이폰 =================
    c, pg = native('ios')
    login(pg, 'pyl' + tag)
    pg.wait_for_function("__rc.calls.some(x=>x.n==='configure')", timeout=8000)
    cf = calls(pg, 'configure')
    if len(cf) != 1 or cf[0]['a'].get('appUserID') != L.uid or cf[0]['a'].get('apiKey') != KEYS['ios']: fail('3 우리 사용자 id·아이폰 키로 설정하지 않음: %s' % cf)
    if cf[0]['a'].get('automaticDeviceIdentifierCollectionEnabled') is not False: fail('3 기기 식별 정보 수집을 끄지 않음: %s' % cf)
    if calls(pg, 'logIn') or calls(pg, 'purchasePackage'): fail('3 로그인만 했는데 다른 것을 부름: %s' % calls(pg))
    plan_tab(pg)
    pc = pg.evaluate("({up:!!document.querySelector('[data-act=\"upgrade\"]'),iap:!!document.getElementById('sIap'),promo:!!document.getElementById('sPromo')})")
    if not pc['up'] or not pc['iap'] or pc['promo']: fail('3 체험 팀 설정 → 플랜에 플랜 올리기·구매 복원·구독 관리가 없거나 코드 칸이 있음: %s' % pc)
    if pg.evaluate(HR_BAD): fail('3 플랜 카드 구분선이 맨 아래에 남거나 두 줄 %s' % pg.evaluate(HR_BAD))
    pg.click('[data-act="upgrade"]'); pg.wait_for_selector('#pay', timeout=5000)
    pg.wait_for_function("()=>!CONTI.IAP.loading", timeout=10000); pg.wait_for_timeout(150)
    s = pay_state(pg)
    if not s['trial'].startswith('체험 중 ·') or '일 남음' not in s['trial']: fail('3 체험 중 표시가 없음: %s' % s)
    if s['prices'] != ['pro:₩5,500 / 1개월', 'plus:₩14,000 / 1개월']: fail('3 스토어 가격·기간(월간)이 아님: %s' % s['prices'])
    if [x['prod'] for x in s['btns'] if not x['dis']] != ['pro_monthly', 'plus_monthly']: fail('3 체험 중인데 살 수 없음: %s' % s['btns'])
    for must in ['자동으로 갱신', '24시간 전까지 해지하지 않으면', 'Apple ID', 'App Store 계정 설정', '해지해도 이미 결제한 기간']:
      if must not in s['legal']: fail('3 자동 갱신 안내에 "%s" 없음: %s' % (must, s['legal']))
    if sorted(s['lg']) != ['privacy', 'terms'] or not s['restore'] or not s['manage']: fail('3 약관·방침 링크·구매 복원·구독 관리가 없음: %s' % s)
    if '4,900' in json.dumps(s['prices']): fail('3 박아 둔 가격이 보임: %s' % s['prices'])
    pg.click('#pay [data-pay="per"][data-v="y"]'); pg.wait_for_timeout(150)
    s = pay_state(pg)
    if s['prices'] != ['pro:₩55,000 / 1년', 'plus:₩140,000 / 1년']: fail('3 연간 가격·기간이 아님: %s' % s['prices'])
    if '월 ₩4,583꼴' not in pg.locator('#pay .paycard[data-plan="pro"]').inner_text(): fail('3 연간의 월 환산이 없음')
    if [x['prod'] for x in s['btns'] if not x['dis']] != ['pro_yearly', 'plus_yearly']: fail('3 연간 단추가 아님: %s' % s['btns'])
    # 약관 링크는 앱 안 약관으로 (자동 갱신 구독 안내가 있다)
    pg.click('#pay [data-lg="terms"]'); pg.wait_for_selector('.legal', timeout=8000)
    lg = pg.inner_text('.legal')
    if '자동 갱신되는 구독' not in lg or '24시간 전까지 해지하지 않으면' not in lg: fail('3 이용약관에 자동 갱신 구독 안내가 없음')
    print('3 ok — 우리 id 로 설정 · 체험 중 표시 · 스토어 가격(월간·연간) · 자동 갱신 안내 · 약관·방침 · 구매 복원·구독 관리')

    # ---- 4 스토어에 없는 상품은 '준비 중' · 상품을 못 받으면 알리고 다시 불러오기
    pg.evaluate("()=>{__rc.missing=['plus_monthly'];CONTI.IAP.pk=null}")
    open_pay(pg)
    s = pay_state(pg)
    if [(x['prod'], x['dis'], x['txt']) for x in s['btns']] != [('pro_monthly', False, 'Pro 월간 구독하기'), ('', True, '준비 중')]: fail('4 없는 상품이 "준비 중"이 아님: %s' % s['btns'])
    pg.evaluate("()=>{__rc.missing=[];__rc.offFail=true;CONTI.IAP.pk=null}")
    open_pay(pg)
    s = pay_state(pg)
    if any(not x['dis'] for x in s['btns']) or not pg.locator('#pay [data-pay="reload"]').count(): fail('4 상품을 못 받았는데 살 수 있거나 다시 불러오기가 없음: %s' % s)
    if '불러오지 못했어요' not in pg.inner_text('#pay'): fail('4 상품을 못 받았다는 안내가 없음')
    pg.evaluate("()=>{__rc.offFail=false}")
    pg.click('#pay [data-pay="reload"]')
    pg.wait_for_function("()=>!CONTI.IAP.loading&&document.querySelectorAll('#pay [data-pay=\"buy\"]:not([disabled])').length===2", timeout=8000)
    if pg.locator('#pay [data-pay="reload"]').count(): fail('4 다시 불러온 뒤에도 오류 줄이 남음')
    print('4a ok — 없는 상품 "준비 중" · 못 받으면 안내 · 다시 불러오기')

    # ---- 4 취소는 조용히 · 오류는 한국어
    open_pay(pg)
    pg.evaluate("()=>{__rc.buy='cancel'}")
    buy_btn(pg, 'pro_monthly').click(); pg.wait_for_timeout(1000)
    s = pay_state(pg)
    if s['msg'] or s['bad'] or toast_text(pg): fail('4 취소했는데 무언가 알림: %s %r' % (s, toast_text(pg)))
    if [x['prod'] for x in s['btns'] if not x['dis']] != ['pro_monthly', 'plus_monthly']: fail('4 취소 뒤 단추가 돌아오지 않음: %s' % s['btns'])
    sa = calls(pg, 'setAttributes'); pp = calls(pg, 'purchasePackage')
    if not sa or sa[-1]['a'] != {'teamId': TEAM}: fail('4 사기 전에 팀(teamId)을 남기지 않음: %s' % sa)
    cs = [x['n'] for x in calls(pg)]
    if cs.index('setAttributes') > cs.index('purchasePackage'): fail('4 setAttributes 가 결제 뒤에 불림: %s' % cs)
    if pp[-1]['a']['aPackage']['product']['identifier'] != 'pro_monthly' or 'storeProductChangeInfo' in pp[-1]['a']: fail('4 엉뚱한 상품으로 삼: %s' % pp[-1])
    pg.evaluate("()=>{__rc.buy='error:2'}")
    buy_btn(pg, 'pro_monthly').click(); pg.wait_for_timeout(1000)
    s = pay_state(pg)
    if '스토어에 잠깐 문제가 있어요' not in s['msg'] or not s['bad']: fail('4 스토어 오류가 한국어로 안 보임: %s' % s)
    if s['team']['src'] != 'trial': fail('4 오류인데 플랜이 바뀜: %s' % s['team'])
    print('4 ok — 취소는 조용히 · 오류는 한국어 · 사기 직전에 setAttributes({teamId})')

    # ---- 5 결제 → 웹훅 → 반영
    pg.evaluate("()=>{__rc.buy='ok'}")
    buy_btn(pg, 'pro_monthly').click()
    pg.wait_for_function("(document.getElementById('payMsg')||{}).textContent==='결제 확인 중…'", timeout=5000)
    pg.wait_for_timeout(2500)
    s = pay_state(pg)
    if s['msg'] != '결제 확인 중…' or s['team']['src'] != 'trial': fail('5 웹훅 전인데 기다리지 않거나 플랜이 바뀜: %s' % s)
    if any(not x['dis'] for x in s['btns']) or not pg.locator('#pay [data-pay="restore"][disabled]').count(): fail('5 기다리는 동안 단추가 살아 있음: %s' % s['btns'])
    attrs = pg.evaluate('__rc.attrs')
    st, j = hook({'type': 'INITIAL_PURCHASE', 'product_id': 'pro_monthly', 'app_user_id': L.uid, 'subscriber_attributes': {'teamId': {'value': attrs['teamId'], 'updated_at_ms': 1}}})
    if st != 200 or j.get('kind') != 'grant': fail('5 웹훅 실패: %s %s' % (st, j))
    pg.wait_for_function("CONTI.S.team.planSource==='iap'", timeout=10000)
    pg.wait_for_function("(document.getElementById('payMsg')||{}).textContent.includes('구독이 시작됐어요')", timeout=5000)
    s = pay_state(pg)
    if s['team'] != {'plan': 'pro', 'src': 'iap', 'payer': L.uid}: fail('5 팀이 내 스토어 구독 Pro 가 아님: %s' % s['team'])
    btn = {x['prod'] or x['txt']: x for x in s['btns']}
    if not any(x['txt'] == '이용 중' and x['dis'] for x in s['btns']) or not (btn.get('plus_monthly') and not btn['plus_monthly']['dis']): fail('5 Pro 이용 중 · Plus 로 올리기가 아님: %s' % s['btns'])
    if '내 스토어 구독으로 Pro' not in s['now']: fail('5 지금 상태 안내가 없음: %s' % s)
    pg.click('#pay [data-pay="close"]'); plan_tab(pg)
    if '내 스토어 구독이에요' not in pg.inner_text('#sPlanStore'): fail('5 설정 → 플랜에 내 스토어 구독 표시가 없음')
    if pg.inner_text('[data-act="upgrade"]').strip() != 'Pro Plus로 올리기': fail('5 Pro 구독 팀의 올리기 단추가 Plus 로 가지 않음: %r' % pg.inner_text('[data-act="upgrade"]'))
    # 구매 복원 · 구독 관리 (설정 → 플랜에서)
    pg.click('[data-act="iap-restore"]')
    pg.wait_for_function("(document.getElementById('toast')||{}).textContent.includes('구독을 확인했어요')", timeout=8000)
    pg.click('[data-act="iap-manage"]'); pg.wait_for_timeout(500)
    if pg.evaluate('__rc.opened')[-1:] != ['itms-apps://apps.apple.com/account/subscriptions']: fail('5 구독 관리가 App Store 구독 화면이 아님: %s' % pg.evaluate('__rc.opened'))
    print('5 ok — 결제 → "결제 확인 중…" → 웹훅 → "구독이 시작됐어요" · Pro 이용 중 · Plus 로 올리기 · 구매 복원 · 구독 관리(App Store)')

    # ---- 6 늦은 웹훅: 창은 안내하고 뒤에서 기다린다 (Plus 로 올리기)
    open_pay(pg)
    pg.evaluate("()=>{CONTI.IAP.waitMs=2500;CONTI.IAP.bgEvery=800}")
    buy_btn(pg, 'plus_monthly').click()
    pg.wait_for_function("(document.getElementById('payMsg')||{}).textContent.includes('시간이 걸리고 있어요')", timeout=10000)
    if pg.evaluate('CONTI.S.team.plan') != 'pro': fail('6 웹훅 전인데 Plus')
    pg.click('#pay [data-pay="close"]'); pg.wait_for_timeout(300)
    st, j = hook({'type': 'PRODUCT_CHANGE', 'product_id': 'pro_monthly', 'new_product_id': 'plus_monthly', 'app_user_id': L.uid})
    if st != 200 or j.get('kind') != 'grant': fail('6 웹훅 실패: %s %s' % (st, j))
    pg.wait_for_function("CONTI.S.team.plan==='plus'", timeout=10000)
    pg.wait_for_function("(document.getElementById('toast')||{}).textContent.includes('Pro Plus 구독이 시작됐어요')", timeout=5000)
    if pg.evaluate("localStorage.getItem('conti-iap-wait')"): fail('6 반영됐는데 기다리기 기록이 남음')
    print('6 ok — 늦은 웹훅: 창에서 안내 → 뒤에서 기다리다 반영되면 알림')
    c.close()

    # ================= 7 안드로이드 · 8 인도자가 아니면 =================
    # 새 인도자(체험 팀)로 안드로이드에서 Pro 를 사고 Plus 로 올린다
    A2 = signup('pya' + tag, '안드')
    st, T2 = A2.req('POST', '/teams', {'name': '안드팀' + tag, 'myName': '안드'})
    c, pg = native('android')
    login(pg, 'pya' + tag)
    pg.wait_for_function("__rc.calls.some(x=>x.n==='configure')", timeout=8000)
    if calls(pg, 'configure')[0]['a'].get('apiKey') != KEYS['android']: fail('7 안드로이드 키로 설정하지 않음: %s' % calls(pg, 'configure'))
    open_pay(pg)
    s = pay_state(pg)
    for must in ['Google Play 계정', 'Google Play › 결제 및 정기 결제']:
      if must not in s['legal']: fail('7 안드로이드 안내에 "%s" 없음' % must)
    if pay_state(pg)['msg']: fail('7 새 결제 화면에 옛 안내가 남음: %s' % s['msg'])
    buy_btn(pg, 'pro_monthly').click()
    pg.wait_for_function("(document.getElementById('payMsg')||{}).textContent==='결제 확인 중…'", timeout=5000)
    st, j = hook({'type': 'INITIAL_PURCHASE', 'product_id': 'pro_monthly:monthly', 'app_user_id': A2.uid, 'subscriber_attributes': {'teamId': {'value': T2['teamId']}}})
    if st != 200 or j.get('kind') != 'grant': fail('7 구글 상품 id 웹훅 실패: %s %s' % (st, j))
    pg.wait_for_function("CONTI.S.team.planSource==='iap'", timeout=10000)
    buy_btn(pg, 'plus_monthly').click()
    pg.wait_for_function("(document.getElementById('payMsg')||{}).textContent==='결제 확인 중…'", timeout=5000)
    pp = calls(pg, 'purchasePackage')[-1]['a']
    if pp.get('storeProductChangeInfo') != {'oldProductIdentifier': 'pro_monthly', 'replacementMode': 'CHARGE_PRORATED_PRICE'}: fail('7 Plus 로 올릴 때 옛 구독을 넘기지 않음: %s' % pp)
    if pp['aPackage']['product']['identifier'] != 'plus_monthly:monthly': fail('7 엉뚱한 상품: %s' % pp['aPackage']['product'])
    st, j = hook({'type': 'PRODUCT_CHANGE', 'product_id': 'pro_monthly:monthly', 'new_product_id': 'plus_monthly:monthly', 'app_user_id': A2.uid})
    pg.wait_for_function("CONTI.S.team.plan==='plus'", timeout=10000)
    pg.click('#pay [data-pay="manage"]'); pg.wait_for_timeout(300)
    if pg.evaluate('__rc.opened')[-1:] != ['https://play.google.com/store/account/subscriptions?package=com.lets1414.app&sku=plus_monthly']: fail('7 구독 관리가 Play 스토어 구독 화면이 아님: %s' % pg.evaluate('__rc.opened'))
    # 로그아웃하면 결제 쪽도 로그아웃 (다음 사람이 산 것이 앞사람 몫으로 가지 않게)
    pg.click('#pay [data-pay="close"]')
    pg.evaluate("()=>{location.hash='#/settings'}"); pg.wait_for_timeout(300)
    pg.click('[data-act="set-tab"][data-t="app"]'); pg.wait_for_timeout(300)
    pg.click('#sLogout'); pg.wait_for_selector('#lgUser', timeout=10000); pg.wait_for_timeout(500)
    if not calls(pg, 'logOut'): fail('7 로그아웃했는데 결제 쪽은 그대로: %s' % [x['n'] for x in calls(pg)])
    # 같은 기기에서 다른 사람(멤버)이 들어오면 그 사람으로 (logIn) — 8 인도자가 아니면 못 산다
    login(pg, 'pym' + tag)
    pg.wait_for_function("__rc.calls.some(x=>x.n==='logIn'&&x.a.appUserID===%s)" % json.dumps(M.uid), timeout=8000)
    if len(calls(pg, 'configure')) != 1: fail('8 다시 설정(configure)함: %s' % calls(pg, 'configure'))
    plan_tab(pg)
    if '인도자만 볼 수 있어요' not in pg.inner_text('#app'): fail('8 멤버에게 설정 → 플랜이 보임')
    open_pay(pg)
    s = pay_state(pg)
    if '인도자' not in s['block'] or any(not x['dis'] for x in s['btns']): fail('8 멤버가 살 수 있음: %s' % s)
    n0 = len(calls(pg, 'purchasePackage'))
    pg.evaluate("document.querySelectorAll('#pay [data-pay=\"buy\"]').forEach(b=>b.click())"); pg.wait_for_timeout(600)
    if len(calls(pg, 'purchasePackage')) != n0: fail('8 멤버의 누름으로 결제 창이 열림')
    c.close()
    print('7 ok — 안드로이드: 구글 상품 id · Plus 로 올릴 때 옛 구독 넘김 · Play 구독 관리(sku) · 로그아웃 → logOut · 다른 사람 → logIn')

    # ---- 8 다른 팀원의 스토어 구독으로 쓰는 팀: 인도자라도 못 바꾼다
    db("update teams set plan='pro', plan_source='iap', plan_until=now()+interval '30 days', iap_user_id=$2, billing_user_id=$2 where id=$1", [TEAM, M.uid])
    c, pg = native('ios')
    login(pg, 'pyl' + tag)
    open_pay(pg)
    s = pay_state(pg)
    if '멤버님의 스토어 구독' not in s['block'] or any(not x['dis'] for x in s['btns']): fail('8 다른 팀원의 구독인데 인도자가 살 수 있음: %s' % s)
    if s['team']['payer'] != M.uid: fail('8 payerId 가 산 사람이 아님: %s' % s['team'])
    c.close()
    print('8 ok — 인도자가 아니면 못 산다(설정 → 플랜도 안 보임) · 다른 팀원의 스토어 구독 팀은 그 사람만')

    real = [e for e in errs if 'ERR_' not in e]
    if real: fail('페이지 오류: %s' % real[:5])
    b.close()

run()
print('ALL OK — test_payments')
