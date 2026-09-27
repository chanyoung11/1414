# 운영자 화면 · 무료 코드 (2026-09-27)
#  1 /admin/* 는 운영자(서버 ADMIN_USERS)만 — 로그인 없으면 401 · 운영자가 아니면 403 · 앱(x-conti-app)에서 온 요청은 운영자도 403
#  2 코드 만들기(플랜·기간·팀 수·메모 · 10자, 헷갈리는 글자 없음 · 직접 적은 코드 · 겹치면 409 · 잘못된 값 400)
#  3 코드 넣기 → 목록에 몇 팀이 썼는지·어느 팀인지 · 끄면 못 씀(이미 쓴 팀은 그대로) · 다시 켜면 씀
#  4 팀 목록(이름·인도자·멤버·곡·플랜) · 플랜 주기(이어 붙이기 · 기한 없음 · 무료로 되돌리기 · 스토어 구독 팀은 거절 · 없는 팀 404)
#  5 기록: admin_audit(만들기·끄기·켜기·주기) · 준 팀의 team_audit
#  6 두드리기 막기: 운영자 쓰기 15분 60번 · 코드 넣기 15분 20번 → 429
#  7 화면(웹): 운영자만 설정 → 계정에 '운영자 화면' · 코드 만들기·끄기·플랜 주기 · 운영자가 아니면 #/admin 이 설정으로
#  8 화면(앱 흉내 https://localhost): 설정 → 플랜에 코드 칸·'프로모션' 없음 · 운영자여도 운영자 길 없음 · #/admin 은 설정으로
# 사용: 서버를 ADMIN_USERS=qaadmin1 로 띄우고
#       CONTI_URL=http://localhost:8766/ CONTI_DB=postgres://… ADMIN_USER=qaadmin1 .venv/bin/python tests/test_admin_codes.py
# 앱 흉내는 lets1414.com·localhost 요청을 모두 로컬 서버로 돌린다 — 운영 서버로는 아무것도 안 나간다
import os, sys, time, json, re, subprocess, urllib.request, urllib.error
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
if not URL.endswith('/'): URL += '/'
API = URL + 'api'
SRV = urlparse(URL)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.environ.get('CONTI_DB') or os.environ.get('DATABASE_URL') or 'postgres://postgres:pg@localhost:54329/postgres'
ADMIN = os.environ.get('ADMIN_USER', 'qaadmin1').lower()
tag = str(int(time.time() * 10))[-7:]
def fail(m): print('FAIL:', m); sys.exit(1)

class Sess:
  def __init__(self): self.cookie = ''; self.uid = None; self.team = None
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

def signup(user, name='리더'):
  s = Sess()
  st, j = s.req('POST', '/auth/signup', {'username': user, 'password': 'secret12', 'name': name})
  if st == 409: st, j = s.req('POST', '/auth/login', {'username': user, 'password': 'secret12'})
  if st != 200: fail('가입/로그인 실패 %s: %s %s' % (user, st, j))
  s.uid = j['user']['id']; s.me = j; return s

def team(s, name):
  st, t = s.req('POST', '/teams', {'name': name, 'myName': '리더'})
  if st != 200: fail('팀 만들기 실패 %s %s' % (st, t))
  s.team = t['teamId']; return t

def db(sql, params=()):
  js = """import('pg').then(async ({default:pg})=>{const c=new pg.Client({connectionString:process.env.DB});await c.connect();
    const r=await c.query(process.env.SQL, JSON.parse(process.env.PARAMS));console.log(JSON.stringify(r.rows));await c.end()})
    .catch(e=>{console.log(JSON.stringify({error:e.message}));process.exit(1)})"""
  out = subprocess.run(['node', '-e', js], cwd=ROOT, capture_output=True, text=True,
                       env={**os.environ, 'DB': DB, 'SQL': sql, 'PARAMS': json.dumps(list(params))})
  try: return json.loads(out.stdout.strip().splitlines()[-1])
  except Exception: fail('DB 질의 실패: %s %s' % (out.stdout[-300:], out.stderr[-300:]))

def days_left(team_id):
  r = db("select plan, plan_source, extract(epoch from plan_until - now())/86400 as d from teams where id=$1", [team_id])[0]
  return r['plan'], r['plan_source'], (float(r['d']) if r['d'] is not None else None)

# 운영자 계정. 운영자 두드리기 한도는 사람마다 15분 창이라, 같은 DB 로 여러 번 돌려도 걸리지 않게 먼저 비운다
AD = signup(ADMIN, '운영자')
db("delete from login_attempts where username like $1", ['admin_:' + AD.uid])
if not AD.me['user'].get('admin'): fail('ADMIN_USERS 의 아이디인데 /me 에 admin 이 없음 — 서버를 ADMIN_USERS=%s 로 띄웠는지 확인' % ADMIN)
if not AD.req('GET', '/me')[1].get('teams'): team(AD, '운영자팀' + tag)
N = signup('adn' + tag, '보통')
if N.me['user'].get('admin'): fail('운영자가 아닌데 /me 에 admin 이 있음')

# ---------- 1 누가 부를 수 있나 ----------
anon = Sess()
if anon.req('GET', '/admin/codes')[0] != 401: fail('로그인 없이 /admin/codes 가 401 이 아님')
for m, path, body in [('GET', '/admin/codes', None), ('POST', '/admin/codes', {'plan': 'pro', 'days': 30}), ('GET', '/admin/teams', None),
                      ('PATCH', '/admin/codes/NOPE', {'active': False}), ('POST', '/admin/teams/%s/grant' % '00000000-0000-0000-0000-000000000000', {'plan': 'pro', 'days': 30})]:
  st, j = N.req(m, path, body)
  if st != 403: fail('운영자가 아닌데 %s %s 가 %s' % (m, path, st))
st, j = AD.req('GET', '/admin/codes', headers={'x-conti-app': '1'})
if st != 403: fail('앱에서 온 운영자 요청이 막히지 않음: %s' % st)
if AD.req('GET', '/admin/codes')[0] != 200: fail('운영자가 /admin/codes 를 못 봄')
print('1 ok — 로그인 없음 401 · 운영자 아님 403 · 앱에서 온 요청 403 · 운영자 200')

# ---------- 2 코드 만들기 ----------
for bad_body in [{'plan': 'gold', 'days': 30}, {'plan': 'pro', 'days': 0}, {'plan': 'pro', 'days': 4000}, {'plan': 'pro', 'days': 30, 'uses': 0},
                 {'plan': 'pro', 'days': 30, 'uses': 5000}, {'plan': 'pro', 'days': 1.5}, {'plan': 'pro', 'days': 30, 'code': 'ab-12'}]:
  st, j = AD.req('POST', '/admin/codes', bad_body)
  if st != 400: fail('잘못된 값인데 코드가 만들어짐: %s → %s %s' % (bad_body, st, j))
st, j = AD.req('POST', '/admin/codes', {'plan': 'pro', 'days': 365, 'uses': 2, 'note': '지인 교회 ' + tag})
if st != 200: fail('코드 만들기 실패 %s %s' % (st, j))
C1 = j['code']
if not re.fullmatch(r'[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{10}', C1['code']): fail('코드 모양이 이상함: %s' % C1['code'])
if C1['plan'] != 'pro' or C1['days'] != 365 or C1['maxUses'] != 2 or C1['used'] != 0 or C1['note'] != '지인 교회 ' + tag: fail('만든 코드 내용이 다름: %s' % C1)
C2 = 'QAX' + tag
st, j = AD.req('POST', '/admin/codes', {'plan': 'plus', 'days': 3650, 'uses': 1, 'code': C2.lower()})
if st != 200 or j['code']['code'] != C2 or j['code']['plan'] != 'plus': fail('직접 적은 코드(10년 Plus) 만들기 실패: %s %s' % (st, j))
st, j = AD.req('POST', '/admin/codes', {'plan': 'pro', 'days': 30, 'code': C2})
if st != 409: fail('같은 코드를 또 만들었는데 %s' % st)
print('2 ok — 10자 코드 · 직접 적은 코드 · 겹치면 409 · 잘못된 값 400')

# ---------- 3 넣기 · 목록 · 끄기 · 켜기 ----------
L1 = signup('adl1' + tag); t1 = team(L1, '코드받은팀' + tag)
st, j = L1.req('POST', '/promo/redeem', {'teamId': L1.team, 'code': C1['code'].lower()})
p, src, d = days_left(L1.team)
if st != 200 or p != 'pro' or src != 'promo' or not (371.9 < d < 372.1): fail('1년 코드가 체험 뒤에 안 붙음: %s %s %s %s %s' % (st, j, p, src, d))
codes = AD.req('GET', '/admin/codes')[1]['codes']
row = next((c for c in codes if c['code'] == C1['code']), None)
if not row or row['used'] != 1 or [r['team'] for r in row['redeemed']] != ['코드받은팀' + tag]: fail('목록에 쓴 팀이 안 보임: %s' % row)
st, j = AD.req('PATCH', '/admin/codes/' + C1['code'].lower(), {'active': False})
if st != 200 or not j['code']['disabledAt']: fail('코드 끄기 실패 %s %s' % (st, j))
L2 = signup('adl2' + tag); team(L2, '늦은팀' + tag)
st, j = L2.req('POST', '/promo/redeem', {'teamId': L2.team, 'code': C1['code']})
if st != 400 or '쓸 수 없는' not in j.get('message', ''): fail('끈 코드가 쓰임: %s %s' % (st, j))
if days_left(L2.team)[1] != 'trial': fail('끈 코드를 넣으려다 팀 플랜이 바뀜')
if days_left(L1.team)[0] != 'pro': fail('코드를 끄자 이미 쓴 팀의 기간이 사라짐')
st, j = AD.req('PATCH', '/admin/codes/' + C1['code'], {'active': True})
if st != 200 or j['code']['disabledAt']: fail('코드 다시 켜기 실패 %s %s' % (st, j))
st, j = L2.req('POST', '/promo/redeem', {'teamId': L2.team, 'code': C1['code']})
if st != 200: fail('다시 켠 코드가 안 쓰임 %s %s' % (st, j))
L3 = signup('adl3' + tag); team(L3, '셋째팀' + tag)
st, j = L3.req('POST', '/promo/redeem', {'teamId': L3.team, 'code': C1['code']})
if st != 400: fail('두 팀용 코드를 세 팀이 씀: %s %s' % (st, j))
if AD.req('PATCH', '/admin/codes/NOPE' + tag, {'active': False})[0] != 404: fail('없는 코드 끄기가 404 가 아님')
print('3 ok — 넣으면 목록에 팀 · 끄면 못 씀(쓴 팀은 그대로) · 다시 켜면 씀 · 팀 수 한도')

# ---------- 4 팀 목록 · 플랜 주기 ----------
st, j = AD.req('GET', '/admin/teams?q=' + urllib.request.quote('코드받은팀' + tag))
tl = j.get('teams', []) if st == 200 else []
if len(tl) != 1: fail('팀 이름으로 찾기 실패 %s %s' % (st, tl))
tv = tl[0]
if tv['id'] != L1.team or tv['plan'] != 'pro' or tv['planSource'] != 'promo' or tv['members'] != 1 or tv['songs'] != 0 or \
   [l['username'] for l in tv['leaders']] != ['adl1' + tag]: fail('팀 목록 내용이 다름: %s' % tv)
st, j = AD.req('GET', '/admin/teams?q=' + 'adl2' + tag)
if st != 200 or [t['name'] for t in j['teams']] != ['늦은팀' + tag]: fail('인도자 아이디로 찾기 실패: %s' % j)
st, j = AD.req('GET', '/admin/teams?q=' + urllib.request.quote('%'))
if st != 200 or any('%' not in t['name'] and not any('%' in l['username'] or '%' in l['name'] for l in t['leaders']) for t in j['teams']):
  fail('찾기 글자 % 가 아무거나 맞음')
G = signup('adg' + tag); team(G, '지인팀' + tag)
for bad_body in [{'plan': 'gold', 'days': 30}, {'plan': 'pro', 'days': -1}, {'plan': 'pro', 'days': 4000}, {'plan': 'pro'}]:
  st, j = AD.req('POST', '/admin/teams/%s/grant' % G.team, bad_body)
  if st != 400: fail('잘못된 플랜 주기가 됨: %s → %s' % (bad_body, st))
if AD.req('POST', '/admin/teams/not-a-uuid/grant', {'plan': 'pro', 'days': 30})[0] != 404: fail('이상한 팀 id 가 404 가 아님')
if AD.req('POST', '/admin/teams/00000000-0000-0000-0000-000000000000/grant', {'plan': 'pro', 'days': 30})[0] != 404: fail('없는 팀이 404 가 아님')
st, j = AD.req('POST', '/admin/teams/%s/grant' % G.team, {'plan': 'pro', 'days': 365})
p, src, d = days_left(G.team)
if st != 200 or p != 'pro' or src != 'manual' or not (371.9 < d < 372.1): fail('Pro 1년 주기가 체험 뒤에 안 붙음: %s %s %s %s' % (st, j, p, d))
st, j = AD.req('POST', '/admin/teams/%s/grant' % G.team, {'plan': 'plus', 'days': 3650})
p, src, d = days_left(G.team)
if st != 200 or p != 'plus' or not (3649.9 < d < 3650.1): fail('Pro → Plus 10년 주기가 이상함: %s %s %s' % (st, p, d))
st, j = AD.req('POST', '/admin/teams/%s/grant' % G.team, {'plan': 'pro', 'days': 0})
p, src, d = days_left(G.team)
if st != 200 or p != 'pro' or d is not None or j['team']['planUntil'] is not None: fail('기한 없는 Pro 주기가 이상함: %s %s %s' % (st, p, d))
st, me = G.req('GET', '/me')
if me['team']['plan'] != 'pro' or me['team']['planUntil'] is not None: fail('준 플랜이 팀 인도자에게 안 보임: %s' % me['team'])
st, j = AD.req('POST', '/admin/teams/%s/grant' % G.team, {'plan': 'free'})
if st != 200 or days_left(G.team)[:2] != ('free', None): fail('무료로 되돌리기 실패: %s %s' % (st, days_left(G.team)))
db("update teams set plan='pro', plan_until=now()+interval '20 days', plan_source='iap' where id=$1", [G.team])
st, j = AD.req('POST', '/admin/teams/%s/grant' % G.team, {'plan': 'plus', 'days': 30})
if st != 400 or days_left(G.team)[1] != 'iap': fail('스토어 구독 중인 팀을 덮음: %s %s' % (st, j))
db("update teams set plan='free', plan_until=null, plan_source=null where id=$1", [G.team])
print('4 ok — 팀 찾기(이름·아이디 · % 는 글자) · 이어 붙이기 · Plus 10년 · 기한 없음 · 무료로 · 스토어 구독 거절 · 없는 팀 404')

# ---------- 5 기록 ----------
acts = [r['action'] for r in db("select action from admin_audit where actor_id=$1 and at > now() - interval '10 minutes' order by id", [AD.uid])]
for need in ['code.create', 'code.disable', 'code.enable', 'team.grant']:
  if need not in acts: fail('운영자 기록에 %s 가 없음: %s' % (need, acts))
ta = db("select action, actor_id, meta from team_audit where team_id=$1 and action='admin.grant' order by id", [G.team])
if len(ta) != 4 or ta[0]['actor_id'] != AD.uid or ta[0]['meta'].get('plan') != 'pro': fail('팀 기록에 운영자가 준 플랜이 안 남음: %s' % ta)
print('5 ok — admin_audit(만들기·끄기·켜기·주기) · 팀 team_audit')

# ---------- 6 두드리기 막기 ----------
W = signup('adw' + tag)
sts = [W.req('POST', '/admin/codes', {'plan': 'pro', 'days': 30})[0] for _ in range(61)]
if sts[:60] != [403] * 60 or sts[60] != 429: fail('운영자 쓰기 두드리기가 안 막힘: %s' % sts[55:])
R = signup('adr' + tag); team(R, '맞히기팀' + tag)
sts = [R.req('POST', '/promo/redeem', {'teamId': R.team, 'code': 'WRONG%02d' % i})[0] for i in range(21)]
if sts[:20] != [404] * 20 or sts[20] != 429: fail('코드 맞히기가 안 막힘: %s' % sts[15:])
print('6 ok — 운영자 쓰기 15분 60번 · 코드 넣기 15분 20번에서 429')

# ---------- 7 · 8 화면 ----------
MOCK = r"""
(() => {
  const ok = (v) => Promise.resolve(v);
  window.Capacitor = { getPlatform: () => 'android', isNativePlatform: () => true, isPluginAvailable: () => false,
    Plugins: { App: { addListener: () => ok({ remove() {} }), getLaunchUrl: () => ok(undefined), getInfo: () => ok({}) },
      StatusBar: { setStyle: () => ok(), setBackgroundColor: () => ok(), hide: () => ok(), show: () => ok() },
      SplashScreen: { hide: () => ok() }, KeepAwake: { keepAwake: () => ok(), allowSleep: () => ok() } } };
  try { localStorage.setItem('conti-push-asked', '1'); } catch (e) {}
})();
"""
def ui():
  with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    def web(s):
      c = b.new_context(viewport={'width': 1200, 'height': 900}, service_workers='block', permissions=['clipboard-read', 'clipboard-write'])
      c.add_cookies([{'name': 'conti_s', 'value': s.cookie.split('=', 1)[1], 'url': URL}])
      c.add_init_script("try{localStorage.setItem('conti-push-asked','1')}catch(e){}")
      pg = c.new_page(); pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('dialog', lambda d: d.accept())
      return c, pg
    # 7 운영자 웹
    c, pg = web(AD)
    pg.goto(URL + '#/settings'); pg.wait_for_selector('[data-act="set-tab"][data-t="account"]', timeout=15000)
    pg.click('[data-act="set-tab"][data-t="account"]'); pg.wait_for_selector('#adminCard', timeout=8000)
    pg.click('#adminCard [data-act="admin"]'); pg.wait_for_selector('#admNew', timeout=15000)
    if pg.evaluate("CONTI.route().name") != 'admin': fail('운영자 화면 주소가 #/admin 이 아님')
    pg.click('[data-adm="plan"][data-v="plus"]'); pg.wait_for_timeout(200)
    pg.click('[data-adm="days"][data-v="3650"]'); pg.wait_for_timeout(200)
    pg.fill('#admUses', '3'); pg.fill('#admNote', '화면에서 ' + tag)
    pg.click('[data-adm="create"]'); pg.wait_for_selector('#admLast', timeout=8000)
    code = pg.locator('#admLast').inner_text().strip()
    got = next((x for x in AD.req('GET', '/admin/codes')[1]['codes'] if x['code'] == code), None)
    if not got or got['plan'] != 'plus' or got['days'] != 3650 or got['maxUses'] != 3 or got['note'] != '화면에서 ' + tag:
      fail('화면에서 만든 코드가 고른 대로가 아님: %s' % got)
    # 카톡 안내 문구: 코드 · 플랜 · 기간 · 웹에서 넣는 길
    pg.click('[data-adm="copymsg"]'); pg.wait_for_timeout(400)
    msg = pg.evaluate("navigator.clipboard.readText()")
    if code not in msg or 'Pro Plus 10년' not in msg or 'lets1414.com' not in msg or '프로모션 코드' not in msg: fail('카톡 안내 문구가 이상함: %s' % msg)
    rowsel = '#admCodes [data-code="%s"].mrow' % code
    if '10년' not in pg.locator(rowsel).inner_text(): fail('목록에 새 코드(10년)가 안 보임')
    pg.click(rowsel + ' [data-adm="disable"]'); pg.wait_for_timeout(1200)
    if '꺼짐' not in pg.locator(rowsel).inner_text(): fail('화면에서 끈 코드가 꺼짐으로 안 보임')
    # 팀 찾아 플랜 주기
    H = signup('adh' + tag); team(H, '화면지인팀' + tag)
    pg.fill('#admQ', '화면지인팀' + tag); pg.click('[data-adm="search"]'); pg.wait_for_timeout(1500)
    if pg.locator('#admTeams [data-team].mrow').count() != 1: fail('화면 팀 찾기 결과가 하나가 아님')
    pg.click('#admTeams [data-adm="grant"]'); pg.wait_for_selector('#admG', timeout=5000)
    pg.click('#admG [data-gp="plus"]'); pg.click('#admG [data-gd="365"]'); pg.click('#admGOk'); pg.wait_for_timeout(1500)
    p2, src2, d2 = days_left(H.team)
    # Pro 체험 중인 팀에 Plus 를 주면 다른 플랜이라 지금부터 1년 (같은 플랜일 때만 남은 기간에 이어 붙는다)
    if p2 != 'plus' or src2 != 'manual' or not (364.9 < d2 < 365.1): fail('화면에서 준 플랜이 이상함: %s %s %s' % (p2, src2, d2))
    if 'Pro Plus' not in pg.locator('#admTeams').inner_text(): fail('준 뒤 팀 목록에 Plus 가 안 보임')
    print('7 ok — 운영자 웹: 설정 → 계정 → 운영자 화면 · 코드 만들기(Plus 10년 3팀) · 끄기 · 팀 찾아 플랜 주기')
    c.close()
    # 운영자가 아닌 웹 사용자
    team(N, '보통팀' + tag)
    c, pg = web(N)
    pg.goto(URL + '#/settings'); pg.wait_for_selector('[data-act="set-tab"][data-t="account"]', timeout=15000)
    pg.click('[data-act="set-tab"][data-t="account"]'); pg.wait_for_timeout(800)
    if pg.locator('#adminCard').count(): fail('운영자가 아닌데 운영자 화면 길이 보임')
    pg.evaluate("()=>location.hash='#/admin'"); pg.wait_for_timeout(1500)
    if pg.evaluate("CONTI.route().name") != 'settings' or pg.locator('#admNew').count(): fail('운영자가 아닌데 #/admin 이 열림')
    pg.click('[data-act="set-tab"][data-t="plan"]'); pg.wait_for_selector('#sPlanPill', timeout=8000)
    if not pg.locator('#sPromo').count(): fail('웹 인도자 설정 → 플랜에 코드 칸이 없음')
    print('7 ok — 운영자가 아니면 길 없음 · #/admin 은 설정으로 · 웹에는 코드 칸')
    c.close()

    # 8 앱 흉내 (https://localhost · 가짜 Capacitor). lets1414.com 으로 가는 것은 모두 로컬 서버로
    def handler(route):
      u = urlparse(route.request.url)
      if u.scheme == 'https' and u.hostname in ('localhost', 'lets1414.com', 'www.lets1414.com') and u.port is None:
        try: return route.fulfill(response=route.fetch(url='%s://%s/%s' % (SRV.scheme, SRV.netloc, u.path.lstrip('/')) + ('?' + u.query if u.query else '')))
        except Exception:
          try: return route.abort()
          except Exception: return
      if u.hostname == SRV.hostname and u.port == SRV.port: return route.continue_()
      return route.abort()
    c = b.new_context(viewport={'width': 412, 'height': 915}, is_mobile=True, has_touch=True, service_workers='block')
    c.route('**/*', handler); c.add_init_script(MOCK)
    pg = c.new_page(); pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('dialog', lambda d: d.accept())
    pg.goto('https://localhost/'); pg.wait_for_selector('#lgUser', timeout=15000)
    if not pg.evaluate("CONTI.NET && typeof CONTI.isAdminUI==='function'"): fail('앱 흉내가 안 뜸')
    pg.fill('#lgUser', ADMIN); pg.fill('#lgPass', 'secret12'); pg.click('[data-act="lg-submit"]')
    pg.wait_for_selector('.shell[data-page]', timeout=15000)
    if not pg.evaluate("CONTI.NET.user&&CONTI.NET.user.admin"): fail('앱 흉내 준비: 운영자 표시가 안 내려옴')
    if pg.evaluate("CONTI.isAdminUI()"): fail('앱에서 운영자 화면이 켜짐')
    pg.evaluate("()=>location.hash='#/settings'"); pg.wait_for_selector('[data-act="set-tab"][data-t="account"]', timeout=8000)
    pg.click('[data-act="set-tab"][data-t="account"]'); pg.wait_for_timeout(800)
    if pg.locator('#adminCard').count() or '운영자' in pg.locator('.setpane').inner_text(): fail('앱 설정에 운영자 길이 보임')
    pg.evaluate("()=>location.hash='#/admin'"); pg.wait_for_timeout(1500)
    if pg.evaluate("CONTI.route().name") != 'settings' or pg.locator('#admNew').count(): fail('앱에서 #/admin 이 열림')
    pg.click('[data-act="set-tab"][data-t="plan"]'); pg.wait_for_selector('#sPlanPill', timeout=8000); pg.wait_for_timeout(300)
    txt = pg.locator('.setpane').inner_text()
    if pg.locator('#sPromo').count() or '프로모션' in txt or '받으신 코드' in txt: fail('앱 설정 → 플랜에 코드 칸이 보임: %s' % txt.replace('\n', ' ')[:200])
    print('8 ok — 앱: 코드 칸 없음 · 운영자여도 운영자 길 없음 · #/admin 은 설정으로')
    c.close()
    if errs: fail('콘솔 오류: ' + errs[0])
    b.close()
ui()
print('OK — 운영자 화면: 403 · 코드 만들기·넣기·끄기 · 플랜 주기 · 기록 · 두드리기 막기 · 앱에는 코드 없음')
