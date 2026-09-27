# 7일 Pro 체험 (2026-09-27 운영자 결정)
#  1 처음 팀을 만든 사람의 그 팀만 Pro 체험 7일 (plan_source='trial') · 한 사람에 한 번 (users.trial_at)
#    - 둘째 팀 · 지우고 다시 만든 팀은 무료 · 동시에 여러 팀을 만들어도 한 팀만
#    - 초대로 들어가는 것은 체험을 주지도 쓰지도 않는다 (그 사람이 나중에 만든 팀은 받는다)
#  2 plan_until 이 지나면 저절로 무료 (/me · /usage)
#  3 체험 중에 코드를 넣으면 남은 체험 뒤에 이어 붙는다 (Pro · Plus 모두 올라감, 내려가지 않음)
#  4 스토어 결제는 체험 위에 올라가고, 결제 만료는 체험 팀을 건드리지 않는다 (서버를 이 프로세스 안에서 — 밖으로 안 나감)
#  5 화면: 설정 → 플랜에 'Pro 체험 중 · N일 남음' · 한도 검사가 꺼져 있으면 홈에 알림 없음 ·
#    켜져 있고 이틀 안에 끝나면 홈 '지금 할 일'에 한 번 (누르면 플랜 탭, 다시 안 뜸) · 약관 제5조에 체험 한 줄
# 사용: CONTI_URL=http://localhost:8766/ CONTI_DB=postgres://… .venv/bin/python tests/test_plans_trial.py
#      (CONTI_DB 는 서버와 같은 DB. 서버는 TRIAL_DAYS 를 비워 둔 기본(7일)이어야 한다)
import os, sys, time, json, subprocess, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
if not URL.endswith('/'): URL += '/'
API = URL + 'api'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.environ.get('CONTI_DB') or os.environ.get('DATABASE_URL') or 'postgres://postgres:pg@localhost:54329/postgres'
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
  if st != 200: fail('가입 실패 %s: %s %s' % (user, st, j))
  s.uid = j['user']['id']; return s

def team(s, name):
  st, t = s.req('POST', '/teams', {'name': name, 'myName': '리더'})
  if st != 200: fail('팀 만들기 실패 %s %s' % (st, t))
  return t

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

def par(fns, n=10):
  with ThreadPoolExecutor(max_workers=n) as ex: return list(ex.map(lambda f: f(), fns))

# 한도 검사(ENFORCE_PLAN)가 켜진 서버면 무료로는 팀을 하나만 만들 수 있어 둘째 팀·동시 다섯 팀 중 넷은 402 다
ENF = json.loads(urllib.request.urlopen(API + '/health', timeout=10).read()).get('enforcePlan')

# ---------- 1 한 사람에 한 번 ----------
A = signup('tra' + tag)
if db('select trial_at from users where id=$1', [A.uid])[0]['trial_at'] is not None: fail('가입만 했는데 체험을 쓴 것으로 적힘')
t1 = team(A, '체험팀' + tag)
if t1.get('plan') != 'pro' or t1.get('planSource') != 'trial' or not t1.get('planUntil'): fail('첫 팀이 Pro 체험이 아님: %s' % {k: t1.get(k) for k in ('plan', 'planSource', 'planUntil')})
p, src, d = days_left(t1['teamId'])
if not (6.95 < d < 7.01): fail('체험 기간이 7일이 아님: %.3f' % d)
if db('select trial_at from users where id=$1', [A.uid])[0]['trial_at'] is None: fail('체험을 받았는데 사람에게 안 적힘')
if not ENF:
  t2 = team(A, '둘째팀' + tag)
  if t2.get('plan') != 'free' or t2.get('planSource'): fail('둘째 팀도 체험을 받음: %s %s' % (t2.get('plan'), t2.get('planSource')))
st, _ = A.req('DELETE', '/teams/' + t1['teamId'], {'name': '체험팀' + tag})
if st != 200: fail('팀 삭제 실패 %s' % st)
t3 = team(A, '다시팀' + tag)
if t3.get('plan') != 'free': fail('팀을 지우고 다시 만들었더니 체험을 또 받음: %s' % t3.get('plan'))
if ENF: t2 = t3   # 아래 초대 검사는 A 의 무료 팀으로
print('1 ok — 첫 팀만 7일 Pro 체험 · 둘째 팀·지우고 다시 만든 팀은 무료')

# 초대로 들어간 사람: 체험을 받지도 쓰지도 않는다 → 나중에 만든 자기 팀은 받는다
B = signup('trb' + tag, '멤버')
st, j = B.req('POST', '/invite/%s/join' % t2['invite'], {'name': '멤버', 'sessions': ['드럼']})
if st != 200: fail('초대로 들어가기 실패 %s %s' % (st, j))
if db('select trial_at from users where id=$1', [B.uid])[0]['trial_at'] is not None: fail('초대로 들어갔는데 체험을 쓴 것으로 적힘')
if days_left(t2['teamId'])[0] != 'free': fail('멤버가 들어오자 팀이 체험을 받음')
tb = team(B, '멤버의팀' + tag)
if tb.get('plan') != 'pro' or tb.get('planSource') != 'trial': fail('초대로 들어갔던 사람이 처음 만든 팀이 체험을 못 받음: %s' % tb.get('plan'))
print('1 ok — 초대로 들어가기는 체험을 주지도 쓰지도 않음')

# 동시에 다섯 팀 → 체험은 한 팀
C = signup('trc' + tag)
res = par([(lambda i=i: C.req('POST', '/teams', {'name': '동시%d' % i + tag, 'myName': '리더'})) for i in range(5)], 5)
if any(st not in ((200, 402) if ENF else (200,)) for st, _ in res) or not any(st == 200 for st, _ in res):
  fail('동시 팀 만들기 실패: %s' % [st for st, _ in res])
nt = sum(1 for _, t in res if t.get('planSource') == 'trial')
nt_db = db("select count(*)::int n from teams where created_by=$1 and plan_source='trial'", [C.uid])[0]['n']
if nt != 1 or nt_db != 1: fail('동시에 만든 다섯 팀 중 체험 팀이 %d개 (DB %d)' % (nt, nt_db))
print('1 ok — 동시에 다섯 팀을 만들어도 체험은 한 팀')

# ---------- 2 기한이 지나면 무료 ----------
db("update teams set plan_until = now() - interval '1 minute' where id=$1", [tb['teamId']])
st, me = B.req('GET', '/me')
tv = [x for x in me.get('teams', []) if x['teamId'] == tb['teamId']]
if st != 200 or not tv or tv[0]['plan'] != 'free': fail('체험 기한이 지났는데 무료가 아님: %s' % (tv[:1],))
st, u = B.req('GET', '/teams/%s/usage' % tb['teamId'])
if st != 200 or u.get('plan') != 'free': fail('/usage 가 끝난 체험을 아직 Pro 로 봄: %s %s' % (st, u))
print('2 ok — 체험 기한이 지나면 무료')

# ---------- 3 체험 위에 코드 ----------
D = signup('trd' + tag); td = team(D, '코드체험팀' + tag)
CP, CPL = 'TRP' + tag, 'TRL' + tag
db("insert into promo_codes(code, plan, days, max_uses) values($1,'pro',30,5),($2,'plus',30,5)", [CP, CPL])
st, j = D.req('POST', '/promo/redeem', {'teamId': td['teamId'], 'code': CP})
p, src, d = days_left(td['teamId'])
if st != 200 or p != 'pro' or src != 'promo' or not (36.9 < d < 37.1): fail('체험 중 Pro 30일 코드가 남은 체험 뒤에 안 붙음: %s %s %s %s %.2f' % (st, j, p, src, d or 0))
E = signup('tre' + tag); te = team(E, '플러스체험팀' + tag)
st, j = E.req('POST', '/promo/redeem', {'teamId': te['teamId'], 'code': CPL})
p, src, d = days_left(te['teamId'])
if st != 200 or p != 'plus' or src != 'promo' or not (36.9 < d < 37.1): fail('체험 중 Plus 코드로 안 올라감: %s %s %s %s %.2f' % (st, j, p, src, d or 0))
print('3 ok — 체험 중 코드는 남은 체험 뒤에 이어 붙고(Pro 37일) · Plus 코드는 Plus 로')

# ---------- 4 스토어 결제 (서버를 이 프로세스 안에서, fetch 막음) ----------
INPROC = r"""
process.env.RC_WEBHOOK_SECRET = 'trial-secret'; process.env.DATABASE_URL = process.env.DB;
process.env.AUTH_SECRET = process.env.AUTH_SECRET || 'local-dev-secret-0123456789'; delete process.env.TRIAL_DAYS;
globalThis.fetch = async (u) => { throw new Error('blocked ' + u); };
const { default: api } = await import(process.env.ROOT + '/api/index.js');
const { one } = await import(process.env.ROOT + '/lib/db.js');
const call = (method, path, body, headers = {}) => new Promise((resolve) => {
  const h = {};
  const res = { statusCode: 200, setHeader(k, v) { h[k.toLowerCase()] = v; }, getHeader(k) { return h[k.toLowerCase()]; },
    end(s) { let j = null; try { j = JSON.parse(s); } catch {} resolve({ status: this.statusCode, body: j, headers: h }); } };
  api({ method, url: '/api' + path, headers: { 'x-conti': '1', 'content-type': 'application/json', ...headers }, body, socket: { remoteAddress: '127.0.0.1' } }, res);
});
const T = process.env.TAG, day = 86400000, out = {};
const user = async (n) => { const r = await call('POST', '/auth/signup', { username: n + T, password: 'secret12', name: n });
  return { id: r.body.user.id, cookie: String(r.headers['set-cookie']).split(';')[0] }; };
const row = (id) => one("select plan, plan_source, extract(epoch from plan_until - now())/86400 as d from teams where id=$1", [id]);
const hook = (who, ev) => call('POST', '/iap/webhook', { event: { app_user_id: who.id, ...ev } }, { authorization: 'trial-secret' }).then((r) => r.body);
const a = await user('tia');
const t = (await call('POST', '/teams', { name: '결제체험팀', myName: '가' }, { cookie: a.cookie })).body;
out.start = await row(t.teamId);
out.expireFirst = await hook(a, { type: 'EXPIRATION', product_id: 'pro_monthly', id: 'te0' + T });
out.afterExpireFirst = await row(t.teamId);
out.buy = await hook(a, { type: 'INITIAL_PURCHASE', product_id: 'plus_monthly', expiration_at_ms: Date.now() + 30 * day, id: 'te1' + T, subscriber_attributes: { teamId: { value: t.teamId } } });
out.afterBuy = await row(t.teamId);
out.expire = await hook(a, { type: 'EXPIRATION', product_id: 'plus_monthly', id: 'te2' + T });
out.afterExpire = await row(t.teamId);
console.log(JSON.stringify(out));
process.exit(0);
"""
def node(js, env=None):
  out = subprocess.run(['node', '--input-type=module', '-e', js], cwd=ROOT, capture_output=True, text=True,
                       env={**os.environ, 'ROOT': ROOT, **(env or {})}, timeout=120)
  lines = [l for l in out.stdout.strip().splitlines() if l.startswith('{')]
  if not lines: fail('node 실행 실패: %s %s' % (out.stdout[-500:], out.stderr[-800:]))
  return json.loads(lines[-1])
o = node(INPROC, {'DB': DB, 'TAG': tag})
if o['start']['plan_source'] != 'trial': fail('결제 준비: 체험 팀이 아님 %s' % o['start'])
if 'skipped' not in (o['expireFirst'] or {}) or o['afterExpireFirst']['plan_source'] != 'trial' or o['afterExpireFirst']['plan'] != 'pro':
  fail('산 적 없는 결제 만료가 체험을 끊음: %s %s' % (o['expireFirst'], o['afterExpireFirst']))
ab = o['afterBuy']
if (o['buy'] or {}).get('kind') != 'grant' or ab['plan'] != 'plus' or ab['plan_source'] != 'iap' or not (29.9 < float(ab['d']) < 30.1):
  fail('체험 중 스토어 결제가 안 올라감: %s %s' % (o['buy'], ab))
if o['afterExpire']['plan'] != 'free': fail('결제 만료 뒤 무료로 안 돌아감: %s' % o['afterExpire'])
print('4 ok — 스토어 결제는 체험 위에(Plus 30일) · 산 적 없는 만료는 체험을 안 건드림 · 결제 만료 뒤 무료')

# ---------- 5 화면 ----------
def ui():
  with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    F = signup('trf' + tag, '하은'); tf = team(F, '화면체험팀' + tag)
    c = b.new_context(viewport={'width': 1200, 'height': 860}, service_workers='block')
    c.add_cookies([{'name': 'conti_s', 'value': F.cookie.split('=', 1)[1], 'url': URL}])
    c.add_init_script("try{localStorage.setItem('conti-push-asked','1')}catch(e){}")
    pg = c.new_page(); pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('dialog', lambda d: d.accept())
    pg.goto(URL + '#/home'); pg.wait_for_selector('.shell[data-page]', timeout=15000)
    if pg.evaluate("CONTI.S.team.planSource") != 'trial': fail('화면이 체험인 줄 모름: %s' % pg.evaluate("CONTI.S.team.planSource"))
    enforced = pg.evaluate("CONTI.NET.enforcePlan")
    pg.evaluate("()=>location.hash='#/settings'"); pg.wait_for_selector('[data-act="set-tab"][data-t="plan"]', timeout=8000)
    pg.click('[data-act="set-tab"][data-t="plan"]'); pg.wait_for_selector('#sPlanPill', timeout=8000); pg.wait_for_timeout(300)
    card = pg.locator('.setpane .card').first.inner_text()
    if 'Pro 체험 중' not in card or '7일 남음' not in card: fail('설정 → 플랜에 체험·남은 날이 안 보임: %s' % card.replace('\n', ' ')[:160])
    if '자동으로 결제되지 않아요' not in card: fail('체험이 끝나면 어떻게 되는지 안 알려 줌')
    if not pg.locator('#sPromo').count(): fail('웹 설정 → 플랜에 코드 칸이 없음')
    print('5 ok — 설정 → 플랜: Pro 체험 중 · 7일 남음 · 웹에는 코드 칸')

    # 이틀 안에 끝나는 체험. 한도 검사가 꺼져 있으면 홈에 아무것도 없다
    db("update teams set plan_until = now() + interval '36 hours' where id=$1", [tf['teamId']])
    pg.goto(URL + '#/home'); pg.reload(); pg.wait_for_selector('.shell[data-page="home"]', timeout=15000); pg.wait_for_timeout(800)
    left = pg.evaluate("CONTI.trialLeft()")
    if left != 2: fail('남은 날 계산이 이상함: %s' % left)
    has = pg.evaluate("CONTI.todoCards().some(c=>c.act==='trial-plan')")
    if not enforced and has: fail('한도 검사가 꺼져 있는데 홈에 체험 알림이 뜸')
    # 한도 검사가 켜진 것처럼 보고 다시 그린다 → 홈 '지금 할 일'에 한 번
    pg.evaluate("()=>{CONTI.NET.enforcePlan=true;CONTI.render()}"); pg.wait_for_timeout(500)
    btn = pg.locator('.todo [data-act="trial-plan"]')
    if not btn.count(): fail('한도 검사가 켜져 있고 이틀 남았는데 홈에 체험 알림이 없음')
    txt = pg.locator('.todo').inner_text()
    if 'Pro 체험이 2일 남았어요' not in txt or '코드' in txt: fail('홈 체험 알림 문구가 이상함: %s' % txt.replace('\n', ' ')[:160])
    btn.first.click(); pg.wait_for_timeout(1200)
    if pg.evaluate("CONTI.route().name") != 'settings' or not pg.locator('#sPlanPill').count(): fail('체험 알림을 눌렀는데 플랜 탭으로 안 감')
    pg.evaluate("()=>{CONTI.go('home')}"); pg.wait_for_timeout(800)
    pg.evaluate("()=>{CONTI.NET.enforcePlan=true;CONTI.render()}"); pg.wait_for_timeout(400)
    if pg.locator('.todo [data-act="trial-plan"]').count(): fail('한 번 누른 체험 알림이 또 뜸')
    print('5 ok — 홈 체험 알림: 한도 검사가 꺼져 있으면 없음 · 켜져 있고 이틀 남으면 한 번 · 누르면 플랜 탭')

    # 약관 제5조에 체험 한 줄
    pg.goto(URL + '#/legal/terms'); pg.wait_for_selector('.legal', timeout=8000)
    lg = pg.locator('.legal').inner_text()
    if '7일 동안 Pro 플랜을 무료로 체험' not in lg or '자동으로 결제되지 않습니다' not in lg: fail('약관에 체험 안내가 없음')
    if '시행일: 2026-09-27' not in lg: fail('약관 시행일이 안 바뀜')
    print('5 ok — 약관 제5조에 7일 체험 · 시행일 2026-09-27')
    if errs: fail('콘솔 오류: ' + errs[0])
    b.close()
ui()
print('OK — 7일 Pro 체험: 한 사람 한 번 · 기한 · 코드·결제는 위로 · 화면')
