# 감사 fe-03 회귀 (2026-09-24)
#  F18·F69 발행 대기: 오프라인·끊긴 발행이 다시 연결될 때·다시 켤 때 올라간다. 새 콘티가 지워지지 않는다.
#          응답만 잃은 발행을 다시 보내면 서버가 받아 준다('서버에 못 올림'이 남지 않는다)
#  F72    켤 때 건강검진이 한 번 실패해도(503) 다시 묻고 서버에 붙는다 (타이머·화면 복귀)
#  F19    앱(네이티브): 말씀 링크를 만들어도 로그인 토큰이 바뀌지 않는다 (쿠키 없이 다시 켜도 로그인 유지)
#  F67    홈 히어로: 같은 날 예배 둘이면 이름·시간·편성이 같은 예배에서 온다
#  F66    편성: 빨리 연달아 고르면 앞 저장이 뒤 선택을 지우던 것
#  F68    발행본의 곡 고정 메모: 남의 '나만'·다른 세션 메모가 멤버에게 내려가지 않는다
#  F71    알림 설정: 계정 값으로 보이고, 한 종류를 바꿔도 다른 기기에서 끈 것이 되살아나지 않는다
#  F129   말씀 수정 요청·불가능으로 바꿈 카드는 할 일이 끝나면 내려간다
#  F130   석 달짜리 스케줄 요청 카드는 첫 달만 답해서는 안 내려간다
#  F131   로그아웃하면 이 계정의 콘티·메모·악보가 IndexedDB 에서 지워진다
#  G30    유튜브: 늦게 준비돼도(중계) '재생할 수 없어요'가 남지 않는다
#  G07    큰 상태에서 글자마다 전체 저장이 돌지 않는다 · 바뀐 것 없는 곡 받기는 저장하지 않는다
#  F70    개인정보처리방침 처리위탁 표 (Cloud Run·R2)
import os, sys, time, re, json, datetime, subprocess
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
BASE = URL.rstrip('/')
DB = os.environ.get('DATABASE_URL', 'postgres://postgres:pg@localhost:54329/postgres')
H = {'x-conti': '1'}
tag = str(int(time.time()))[-6:]
N = [0]
def fail(m): print('FAIL:', m); sys.exit(1)
def ok(r, what=''):
    if not r.ok: fail('%s %s %s' % (what, r.status, r.text()[:200]))
    return r.json()
def uname(p): N[0] += 1; return '%s%s%d' % (p, tag, N[0])
def day(n): return (datetime.date.today() + datetime.timedelta(days=n)).isoformat()
def month_add(k, n):
    y, m = map(int, k.split('-')); m += n; y += (m - 1) // 12; m = (m - 1) % 12 + 1
    return '%04d-%02d' % (y, m)

def sql(query, params=()):
    js = ('import("pg").then(async ({default:pg})=>{const c=new pg.Client({connectionString:process.env.DATABASE_URL});'
          'await c.connect();const r=await c.query(process.argv[1],JSON.parse(process.argv[2]));'
          'console.log(JSON.stringify(r.rows));await c.end()})')
    out = subprocess.run(['node', '-e', js, query, json.dumps(list(params))], cwd=ROOT, capture_output=True, text=True,
                         env={**os.environ, 'DATABASE_URL': DB})
    if out.returncode: fail('sql: ' + out.stderr[-300:])
    return json.loads(out.stdout.strip() or '[]')

def account(b, prefix, name, **ctx):
    c = b.new_context(viewport={'width': 1240, 'height': 900}, **ctx)
    u = uname(prefix)
    me = ok(c.request.post(URL + 'api/auth/signup', headers=H, data={'username': u, 'password': 'secret1', 'name': name}), 'signup')
    return c, u, me['user']['id']

def leader(b, prefix, team_name='감사팀', **ctx):
    c, u, uid = account(b, prefix, '하은', **ctx)
    t = ok(c.request.post(URL + 'api/teams', headers=H, data={'name': team_name, 'myName': '하은', 'session': '인도자'}), 'team')
    return c, u, uid, t['teamId']

def join(b, prefix, name, team, code, session='드럼', role=None, lead_ctx=None):
    c, u, uid = account(b, prefix, name)
    if role:
        code = ok(lead_ctx.request.post(URL + 'api/teams/%s/invites' % team, headers=H, data={'role': role, 'days': 0}), 'invite')['invite']['code']
    ok(c.request.post(URL + 'api/invite/%s/join' % code, headers=H, data={'name': name, 'session': session}), 'join')
    return c, u, uid

def invite_code(c, team):
    return ok(c.request.get(URL + 'api/teams/%s' % team), 'team get')['invite']

def page(c, hash_='#/home'):
    pg = c.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:200])); pg.on('dialog', lambda d: d.accept())
    pg.goto(URL + hash_); pg.wait_for_selector('.shell[data-page]', timeout=15000)
    pg.errs = errs
    return pg

def wait_until(pg, expr, ms=12000, arg=None):
    try: pg.wait_for_function(expr, arg=arg, timeout=ms); return True
    except Exception: return False

def new_service_ui(pg, name, song):
    pg.goto(URL + '#/home'); pg.wait_for_selector('[data-act="new-svc"]', timeout=10000)
    pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]', timeout=8000)
    pg.fill('[data-f="svc.name"]', name)
    pg.click('[data-act="add-item"]'); pg.wait_for_selector('[data-f="item.title"]', timeout=8000)
    pg.fill('[data-f="item.title"]', song); pg.wait_for_timeout(400)
    return pg.evaluate('CONTI.route().a')

def publish_ui(pg, sid, add_song=None):
    pg.goto(URL + '#/edit/' + sid); pg.wait_for_selector('[data-f="item.title"]', timeout=10000); pg.wait_for_timeout(300)
    if add_song:
        pg.click('[data-act="add-item"]'); pg.wait_for_timeout(300); pg.fill('[data-f="item.title"] >> nth=-1', add_song); pg.wait_for_timeout(300)
    pg.click('[data-act="publish"]'); pg.wait_for_selector('#pubOnly', timeout=6000); pg.click('#pubOnly')

def svc_state(pg, sid):
    return pg.evaluate("(id)=>{const s=CONTI.S.services.find(x=>x.id===id);return s?{pending:!!s.pubPending,pub:s.published&&s.published.version}:null}", sid)

def server_version(c, team, sid):
    for s in ok(c.request.get(URL + 'api/services?team=' + team))['services']:
        if s['id'] == sid: return s['version']
    return None

# ---------------------------------------------------------------- F18 · F69 · F72
def sec_publish(b):
    c, u, uid, team = leader(b, 'pp', service_workers='block')
    pg = page(c)
    sB = new_service_ui(pg, '온라인 예배', '곡1')
    publish_ui(pg, sB)
    if not wait_until(pg, "(id)=>{const s=CONTI.S.services.find(x=>x.id===id);return s&&s.published&&!s.pubPending}", arg=sB): fail('온라인 발행이 안 끝남')
    if server_version(c, team, sB) != 1: fail('v1 이 서버에 없음')

    # 서버를 못 찾는 채로 켠다 (오프라인으로 켠 앱과 같다)
    off = lambda r: r.abort('internetdisconnected')
    pg.route('**/api/**', off)
    pg.goto(URL + '#/home'); pg.reload(); pg.wait_for_selector('.shell', timeout=15000); pg.wait_for_timeout(500)
    if pg.evaluate('CONTI.NET.server') is True: fail('오프라인인데 서버에 붙었다고 봄')
    sA = new_service_ui(pg, '오프라인 예배', '오프곡')
    publish_ui(pg, sA); pg.wait_for_timeout(600)
    st = svc_state(pg, sA)
    if not (st and st['pub'] == 1 and st['pending']): fail('오프라인 발행에 발행 대기 표시가 없음: %s' % st)
    publish_ui(pg, sB, add_song='곡2'); pg.wait_for_timeout(600)
    st = svc_state(pg, sB)
    if not (st and st['pub'] == 2 and st['pending']): fail('오프라인 v2 에 발행 대기 표시가 없음: %s' % st)
    pg.wait_for_timeout(300)   # 저장(250ms) 뒤에

    # 다시 연결
    pg.unroute('**/api/**', off)
    pg.evaluate("window.dispatchEvent(new Event('online'))")
    if not wait_until(pg, "([a,b])=>{const f=id=>CONTI.S.services.find(x=>x.id===id);return CONTI.NET.server===true&&f(a)&&!f(a).pubPending&&f(b)&&!f(b).pubPending}", 15000, [sA, sB]):
        fail('다시 연결됐는데 발행 대기가 안 올라감: A=%s B=%s' % (svc_state(pg, sA), svc_state(pg, sB)))
    pg.wait_for_timeout(1500)   # 이어서 도는 pullServices 가 끝나도록
    if not svc_state(pg, sA): fail('오프라인에서 발행한 새 콘티가 다시 연결되자 지워짐')
    if server_version(c, team, sA) != 1: fail('오프라인 발행 A 가 서버에 없음')
    if server_version(c, team, sB) != 2: fail('오프라인 v2 가 서버에 안 올라감: %s' % server_version(c, team, sB))
    print('F18 오프라인 발행 → 다시 연결되면 올라감 · 새 콘티 안 지워짐 ok')

    # 올리다 끊김 → 다시 켜면 올라간다
    rx = re.compile(r'.*/api/services/%s$' % re.escape(sB))
    hit = {'n': 0}
    def cut(route):
        if route.request.method == 'PUT' and hit['n'] == 0: hit['n'] += 1; return route.abort('failed')
        route.continue_()
    pg.route(rx, cut)
    publish_ui(pg, sB, add_song='곡3'); pg.wait_for_timeout(1500)
    if not svc_state(pg, sB)['pending']: fail('올리다 실패했는데 발행 대기가 없음')
    pg.unroute(rx, cut)
    pg.goto(URL + '#/home'); pg.reload(); pg.wait_for_selector('.shell[data-page]', timeout=15000)
    if not wait_until(pg, "(id)=>{const s=CONTI.S.services.find(x=>x.id===id);return s&&!s.pubPending}", 12000, sB): fail('다시 켜도 발행 대기가 안 올라감')
    if server_version(c, team, sB) != 3: fail('다시 켤 때 v3 이 안 올라감: %s' % server_version(c, team, sB))
    print('F18 올리다 끊긴 발행 → 다시 켜면 올라감 ok')

    # F69: 서버엔 들어갔는데 응답을 잃음 → 다시 보내면 같은 판으로 받아 준다
    hit['n'] = 0
    def lose(route):
        if route.request.method == 'PUT' and hit['n'] == 0:
            hit['n'] += 1; route.fetch(); return route.abort('failed')
        route.continue_()
    pg.route(rx, lose)
    publish_ui(pg, sB, add_song='곡4'); pg.wait_for_timeout(1500)
    if server_version(c, team, sB) != 4: fail('서버에 v4 가 안 들어감')
    if not svc_state(pg, sB)['pending']: fail('응답을 잃었는데 발행 대기가 없음')
    pg.unroute(rx, lose)
    pg.goto(URL + '#/home'); pg.wait_for_selector('[data-act="repub"]', timeout=8000)
    pg.click('[data-act="repub"]')
    if not wait_until(pg, "(id)=>{const s=CONTI.S.services.find(x=>x.id===id);return s&&!s.pubPending}", 8000, sB): fail('같은 판 다시 올리기가 막힘 (409)')
    t = pg.locator('#toast').inner_text()
    if '이미 발행' in t: fail('같은 판인데 충돌로 봄: ' + t)
    r = c.request.put(URL + 'api/services/' + sB, headers=H, data={'teamId': team, 'doc': {'id': sB, 'name': 'x', 'date': day(1), 'version': 4, 'items': []}})
    if r.status != 409: fail('다른 내용의 같은 버전은 여전히 409 여야 함: %s' % r.status)
    print('F69 응답 잃은 발행 → 다시 올리면 같은 판으로 받아 줌 · 다른 판은 409 ok')

    # F69: 실패한 v5 뒤 v6 발행에 성공하면 발행 대기가 풀린다
    hit['n'] = 0
    pg.route(rx, cut)
    publish_ui(pg, sB, add_song='곡5'); pg.wait_for_timeout(1500)
    if not svc_state(pg, sB)['pending']: fail('실패한 발행에 대기 표시가 없음')
    pg.unroute(rx, cut)
    publish_ui(pg, sB, add_song='곡6')
    if not wait_until(pg, "(id)=>{const s=CONTI.S.services.find(x=>x.id===id);return s&&!s.pubPending&&s.published.version===6}", 10000, sB): fail('성공한 발행이 발행 대기를 안 풀어 줌: %s' % svc_state(pg, sB))
    pg.goto(URL + '#/home'); pg.wait_for_timeout(600)
    if '서버에 못 올림' in pg.locator('#app').inner_text(): fail('성공했는데 서버에 못 올림 표시가 남음')
    print('F69 성공한 발행은 발행 대기를 푼다 ok')
    if pg.errs: fail('JS 오류: %s' % pg.errs[:3])

    # F72: 켤 때 건강검진이 503 → 타이머로 다시 붙는다 / 화면 복귀로 바로 붙는다
    for how in ('timer', 'visible'):
        n = {'k': 0}
        def h(route):
            n['k'] += 1
            if n['k'] == 1: return route.fulfill(status=503, body='busy')
            route.continue_()
        pg.route('**/api/health', h)
        pg.goto(URL + '#/home'); pg.reload(); pg.wait_for_selector('.shell', timeout=15000); pg.wait_for_timeout(300)
        v = pg.evaluate('CONTI.NET.server')
        if v is True: fail('503 인데 붙었다고 봄')
        if v is False: fail('일시 오류(503)를 서버 없음(false)으로 굳힘')
        if how == 'visible':
            pg.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
            if not wait_until(pg, "CONTI.NET.server===true", 3000): fail('화면 복귀에도 서버에 다시 안 붙음')
        else:
            if not wait_until(pg, "CONTI.NET.server===true", 9000): fail('503 뒤로 계속 오프라인 (다시 묻지 않음)')
        pg.unroute('**/api/health', h)
        pg.wait_for_timeout(800)
        if '이 기기 전용' in pg.locator('body').inner_text(): fail('다시 붙었는데 이 기기 전용 표시')
    print('F72 503 한 번 뒤 다시 묻기(타이머·화면 복귀) ok')
    c.close()

# ---------------------------------------------------------------- F19
def sec_native_token(b):
    c = b.new_context(viewport={'width': 1180, 'height': 820}, service_workers='block')
    def app_files(route):
        path = route.request.url.split('https://localhost', 1)[1].split('?')[0].split('#')[0] or '/'
        if path == '/': path = '/index.html'
        f = os.path.join(ROOT, 'app', path.lstrip('/'))
        if not os.path.isfile(f): return route.fulfill(status=404, body='')
        route.fulfill(status=200, body=open(f, 'rb').read(), headers={'content-type': 'text/html; charset=utf-8' if f.endswith('.html') else 'application/octet-stream'})
    def to_local(route):   # 앱이 부르는 운영 주소를 로컬 개발 서버로 돌린다. 운영에는 절대 안 나간다
        u = route.request.url
        if not u.startswith('https://lets1414.com/api/'): return route.abort()
        route.fulfill(response=route.fetch(url=BASE + u[len('https://lets1414.com'):]))
    c.route(re.compile(r'^https://localhost(/.*)?$'), app_files)
    c.route(re.compile(r'^https://lets1414\.com(/.*)?$'), to_local)
    pg = c.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('dialog', lambda d: d.accept())
    pg.goto('https://localhost/'); pg.wait_for_selector('#lgUser', timeout=15000)
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName')
    pg.check('#lgAgree'); pg.fill('#lgName', '하은'); pg.fill('#lgUser', uname('nt')); pg.fill('#lgPass', 'secret1'); pg.click('[data-act="lg-submit"]')
    pg.wait_for_selector('#gtTeam', timeout=10000); pg.fill('#gtTeam', '앱팀'); pg.click('[data-act="team-create"]'); pg.wait_for_selector('.shell[data-page]', timeout=10000)
    sess = pg.evaluate("localStorage.getItem('conti-app-token')")
    if not sess or '.' not in sess: fail('앱 로그인 토큰이 없음: %r' % sess)
    pg.evaluate("()=>{const s={id:'wl'+Date.now().toString(36),name:'말씀 예배',date:'%s',notice:'',version:0,items:[],published:null};CONTI.S.services.push(s);location.hash='#/edit/'+s.id}" % day(5))
    pg.wait_for_timeout(800)
    pg.evaluate("()=>{const b=document.createElement('button');b.dataset.act='word-link';document.body.appendChild(b);b.click()}")
    pg.wait_for_selector('.linkbox', timeout=8000)
    if '#/word-link/' not in pg.locator('.linkbox').inner_text(): fail('말씀 링크가 이상함')
    if pg.evaluate("localStorage.getItem('conti-app-token')") != sess: fail('말씀 링크 값이 로그인 토큰을 덮음')
    c.clear_cookies()   # iOS 는 앱을 다시 켜면 다른 도메인 쿠키를 버린다
    pg.reload(); pg.wait_for_timeout(2500)
    if not pg.evaluate("!!(CONTI.NET.user&&CONTI.NET.user.id)") or pg.locator('#lgUser').count(): fail('말씀 링크를 만든 뒤 다시 켜니 로그아웃됨')
    if errs: fail('JS 오류: %s' % errs[:3])
    c.unroute_all(behavior='ignoreErrors'); c.close()
    print('F19 앱: 말씀 링크를 만들어도 토큰 유지 · 다시 켜도 로그인 ok')

# ---------------------------------------------------------------- F67 · F66
def sec_hero_lineup(b):
    cL, _, uidL, team = leader(b, 'hv', service_workers='block')
    code = invite_code(cL, team)
    cM, _, uidM = join(b, 'hw', '민수', team, code, session='드럼')
    d1 = day(3)
    id1 = ok(cL.request.post(URL + 'api/teams/%s/dates' % team, headers=H, data={'date': d1, 'label': '1부 예배', 'time': '09:00'}))['date']['id']
    id2 = ok(cL.request.post(URL + 'api/teams/%s/dates' % team, headers=H, data={'date': d1, 'label': '2부 예배', 'time': '11:00'}))['date']['id']
    ok(cL.request.get(URL + 'api/services?team=' + team))   # 인도자가 목록을 받으면 날짜마다 초안이 생기고 이어진다
    links = {x['id']: x['serviceId'] for x in ok(cL.request.get(URL + 'api/teams/%s/schedule' % team))['dates']}
    a1, a2 = links[id1], links[id2]
    ok(cL.request.put(URL + 'api/teams/%s/dates/%s/lineup' % (team, id1), headers=H, data={'lineup': [{'session': '드럼', 'memberId': uidL}]}))
    ok(cL.request.put(URL + 'api/teams/%s/dates/%s/lineup' % (team, id2), headers=H, data={'lineup': [{'session': '드럼', 'memberId': uidM}]}))
    for sid, name in ((a2, '2부 예배'), (a1, '1부 예배')):
        ok(cL.request.put(URL + 'api/services/' + sid, headers=H, data={'teamId': team, 'doc': {'id': sid, 'name': name, 'date': d1, 'notice': '', 'message': '', 'messageRev': 0, 'version': 1, 'items': []}}))
    pm = page(cM)
    if not wait_until(pm, "CONTI.S.services.length>=2&&CONTI.SCH.dates.length>=2", 12000): fail('멤버가 콘티·일정을 못 받음')
    for first in ('2부', '1부'):
        pm.evaluate("(f)=>{CONTI.S.services.sort((a,b)=>(a.name.includes(f)?0:1)-(b.name.includes(f)?0:1));CONTI.render()}", first)
        pm.wait_for_timeout(700)
        hero = pm.locator('.hero').inner_text().replace('\n', ' | ')
        if first == '2부' and not ('2부' in hero and '11:00' in hero and '내 자리' in hero): fail('히어로가 2부 이름에 다른 예배의 시간·편성: %s' % hero)
        if first == '1부' and not ('1부' in hero and '09:00' in hero and '쉬어요' in hero): fail('히어로가 1부 이름에 다른 예배의 시간·편성: %s' % hero)
    pl = page(cL)
    if not wait_until(pl, "CONTI.S.services.some(s=>s.published)&&CONTI.SCH.dates.length>=2", 12000): fail('인도자가 콘티·일정을 못 받음')
    pl.wait_for_timeout(800)
    for first in ('2부', '1부'):
        pl.evaluate("(f)=>{CONTI.S.services.sort((a,b)=>(a.name.includes(f)?0:1)-(b.name.includes(f)?0:1));CONTI.render()}", first); pl.wait_for_timeout(700)
        hsid = pl.locator('.hero [data-act="view-svc"], .hero [data-act="edit-svc"]').first.get_attribute('data-id')
        want = id1 if hsid == a1 else id2 if hsid == a2 else None
        btn = pl.locator('.hero [data-act="lineup"]')
        got = btn.get_attribute('data-id') if btn.count() else None
        if got != want: fail('히어로 편성 버튼이 다른 예배 날짜를 엶: 콘티 %s → %s (기대 %s)' % (hsid, got, want))
    print('F67 같은 날 두 예배: 히어로 이름·시간·편성·편성 버튼이 한 예배 ok')

    # F66: 편성 칸을 빨리 연달아 고른다. 첫 저장이 늦게 닿게 한다
    d2 = day(9)
    id3 = ok(cL.request.post(URL + 'api/teams/%s/dates' % team, headers=H, data={'date': d2, 'label': '수요예배', 'time': '19:30'}))['date']['id']
    pl.goto(URL + '#/lineup/' + id3); pl.wait_for_selector('[data-lsel="드럼"]', timeout=12000); pl.wait_for_timeout(500)
    pl.evaluate("""()=>{const of=window.fetch;let n=0;window.fetch=(u,o)=>{if(/\\/lineup$/.test(String(u))&&o&&o.method==='PUT'&&n++===0)return new Promise(r=>setTimeout(r,1500)).then(()=>of(u,o));return of(u,o)}}""")
    pl.select_option('[data-lsel="드럼"]', uidM)
    pl.wait_for_timeout(150)
    pl.select_option('[data-lsel="인도자"]', uidL)
    pl.wait_for_timeout(4000)
    sch = ok(cL.request.get(URL + 'api/teams/%s/schedule' % team))
    row = next(x for x in sch['dates'] if x['id'] == id3)
    got = sorted((r['session'], r['memberId']) for r in (row['lineup'] or []) if r.get('memberId'))
    want = sorted([('드럼', uidM), ('인도자', uidL)])
    if got != want: fail('빨리 고른 편성이 서버에서 빠짐: %s' % got)
    if pl.errs or pm.errs: fail('JS 오류: %s' % (pl.errs + pm.errs)[:3])
    print('F66 빨리 연달아 고른 편성이 둘 다 저장됨 ok')
    cL.close(); cM.close()

# ---------------------------------------------------------------- F68
def sec_fixed_notes(b):
    cL, _, uidL, team = leader(b, 'fx', service_workers='block')
    code = invite_code(cL, team)
    cD, _, uidD = join(b, 'fd', '드러머', team, code, session='드럼')
    cV, _, uidV = join(b, 'fv', '보컬', team, code, session='싱어')
    ok(cL.request.patch(URL + 'api/teams/%s/members/%s' % (team, uidD), headers=H, data={'role': 'session_lead'}))
    sid = ok(cL.request.post(URL + 'api/songs', headers=H, data={'teamId': team, 'title': '누수곡', 'key': 'G', 'form': 'A – B'}))['song']['id']
    det = ok(cL.request.get(URL + 'api/songs/%s?team=%s' % (sid, team)))
    aid = (det.get('arrangements') or det['song'].get('arrangements'))[0]['id']
    note = lambda cx, layer, text, session=None: ok(cx.request.post(URL + 'api/arrangements/%s/notes' % aid, headers=H, data={'teamId': team, 'markerLabel': 'A', 'layer': layer, 'session': session or '', 'text': text}))
    note(cD, 'session', '드럼 전용', '드럼'); note(cD, 'mine', '드러머 개인'); note(cL, 'mine', '인도자 개인'); note(cL, 'all', '모두 보기')
    pl = page(cL)
    pl.evaluate("CONTI.pullSongs(true)"); pl.wait_for_timeout(1500)
    svc = pl.evaluate("""([sid,aid,d])=>{const s={id:'fx'+Date.now().toString(36),name:'고정 메모 예배',date:d,notice:'',version:0,published:null,
      items:[{id:'i1',title:'누수곡',key:'G',mod:'',form:'',songNote:'',pieces:[],media:[],notes:[],songId:sid,arrId:aid}]};
      CONTI.S.services.push(s);CONTI.save();return s.id}""", [sid, aid, day(4)])
    publish_ui(pl, svc)
    if not wait_until(pl, "(id)=>{const s=CONTI.S.services.find(x=>x.id===id);return s&&s.published&&!s.pubPending}", 10000, svc): fail('고정 메모 예배 발행 실패')
    texts = lambda cx: sorted(n['text'] for it in ok(cx.request.get(URL + 'api/services/%s?team=%s' % (svc, team)))['doc']['items'] for n in (it.get('fixedNotes') or []))
    if texts(cV) != ['모두 보기']: fail('보컬이 남의 메모를 받음: %s' % texts(cV))
    if texts(cD) != sorted(['모두 보기', '드럼 전용']): fail('드러머가 받는 고정 메모가 이상함: %s' % texts(cD))
    if '인도자 개인' in texts(cL): fail("발행본에 인도자의 '나만' 메모가 담김")
    # 인도자 화면에서는 내 '나만' 메모가 곡에서 바로 보인다
    mine = pl.evaluate("""(id)=>{const s=CONTI.S.services.find(x=>x.id===id);const it={...s.published.items[0],pieces:[{markers:[{id:'m1',label:'A'}]}]};
      return CONTI.fixedNotesOf(it,'m1',null).map(n=>n.text)}""", svc)
    if '인도자 개인' not in mine: fail("인도자 발행본 화면에서 내 '나만' 메모가 사라짐: %s" % mine)
    # 예전에 발행된 문서(모든 메모가 굳어 있음)도 서버가 보는 사람대로 거른다
    old = [{'id': 'o1', 'markerLabel': 'A', 'layer': 'mine', 'authorId': uidL, 'text': '옛 인도자 개인'},
           {'id': 'o2', 'markerLabel': 'A', 'layer': 'session', 'session': '드럼', 'authorId': uidD, 'text': '옛 드럼'},
           {'id': 'o3', 'markerLabel': 'A', 'layer': 'all', 'authorId': uidL, 'text': '옛 전체'}]
    ok(cL.request.put(URL + 'api/services/' + svc, headers=H, data={'teamId': team, 'doc': {'id': svc, 'name': '고정 메모 예배', 'date': day(4), 'version': 9, 'items': [{'id': 'i1', 'title': '누수곡', 'fixedNotes': old}]}}))
    if texts(cV) != ['옛 전체']: fail('옛 발행본의 메모가 보컬에게 샘: %s' % texts(cV))
    if texts(cD) != sorted(['옛 전체', '옛 드럼']): fail('옛 발행본에서 드러머 메모가 이상함: %s' % texts(cD))
    if pl.errs: fail('JS 오류: %s' % pl.errs[:3])
    print("F68 발행본 고정 메모: 남의 '나만'·다른 세션 메모 안 내려감 (옛 발행본 포함) ok")
    for x in (cL, cD, cV): x.close()

# ---------------------------------------------------------------- F71
def sec_prefs(b):
    cP, u, uid = account(b, 'np', '하은', service_workers='block')
    ok(cP.request.post(URL + 'api/teams', headers=H, data={'name': '알림팀', 'myName': '하은'}))
    cQ = b.new_context(viewport={'width': 1240, 'height': 900}, service_workers='block')
    ok(cQ.request.post(URL + 'api/auth/login', headers=H, data={'username': u, 'password': 'secret1'}))
    pc = page(cP); phone = page(cQ)
    pc.wait_for_timeout(800)   # PC 는 홈에서 설정을 이미 받아 둔 상태
    phone.goto(URL + '#/settings'); phone.wait_for_selector('.setpane', timeout=8000)
    phone.click('[data-act="set-tab"][data-t="noti"]'); phone.wait_for_selector('[data-noti="publish"]', timeout=8000)
    phone.uncheck('[data-noti="publish"]'); phone.wait_for_timeout(1000)
    ok(cQ.request.patch(URL + 'api/me/prefs', headers=H, data={'prefs': {'quiet': {'from': 1, 'to': 6}}}))
    pc.goto(URL + '#/settings'); pc.wait_for_selector('.setpane', timeout=8000)
    pc.click('[data-act="set-tab"][data-t="noti"]'); pc.wait_for_selector('[data-noti="publish"]', timeout=8000); pc.wait_for_timeout(300)
    if pc.is_checked('[data-noti="publish"]'): fail('폰에서 끈 콘티 발행 알림이 PC 설정에 켜져 보임')
    pc.uncheck('[data-noti="date.closed"]'); pc.wait_for_timeout(1000)
    pc.uncheck('#sQuiet'); pc.wait_for_timeout(1000)
    pr = ok(pc.request.get(URL + 'api/me/prefs'))['prefs']
    off = pr.get('notiOff') or {}
    if off.get('publish') is not True: fail('PC 에서 다른 종류를 끄자 폰에서 끈 콘티 발행이 되살아남: %s' % off)
    if off.get('date.closed') is not True: fail('PC 에서 끈 종류가 저장 안 됨: %s' % off)
    q = pr.get('quiet') or {}
    if q.get('on') is not False or q.get('from') != 1 or q.get('to') != 6: fail('조용한 시간을 끄자 폰에서 정한 시간이 바뀜: %s' % q)
    if pc.errs or phone.errs: fail('JS 오류: %s' % (pc.errs + phone.errs)[:3])
    print('F71 알림 설정: 계정 값으로 보임 · 한 종류만 합쳐 저장 · 조용한 시간 부분 저장 ok')
    cP.close(); cQ.close()

# ---------------------------------------------------------------- F129 · F130
def notis(c, team, typ):
    return [n for n in ok(c.request.get(URL + 'api/notifications?team=' + team))['notifications'] if n['type'] == typ]

def sec_todo(b):
    cL, _, uidL, team = leader(b, 'td', service_workers='block')
    code = invite_code(cL, team)
    cM, _, uidM = join(b, 'tm', '민수', team, code, session='드럼')
    cP, _, uidP = join(b, 'tp', '목사', team, code, role='pastor', lead_ctx=cL)
    # 말씀 수정 요청: 그 예배 날짜로 기한이 붙고, 목회자가 말씀을 적으면 카드가 내려간다
    dW = day(2)
    ok(cL.request.post(URL + 'api/teams/%s/dates' % team, headers=H, data={'date': dW, 'label': '주일', 'time': '11:00'}))
    sW = 'w' + tag
    ok(cL.request.put(URL + 'api/services/%s/draft' % sW, headers=H, data={'teamId': team, 'doc': {'id': sW, 'name': '주일 예배', 'date': dW, 'items': []}}))
    sql("insert into notifications(team_id,user_id,type,target_id,title,actionable,expires_at) values($1,$2,'word.request',$3,'이번 주 말씀 알려주세요',true,$4)",
        [team, uidP, day(6), day(6) + 'T23:59:59+09:00'])
    ok(cL.request.post(URL + 'api/services/%s/word-request' % sW, headers=H, data={'teamId': team}))
    wr = [n for n in notis(cP, team, 'word.request') if n['targetId'] == sW]
    if not wr or not wr[0]['expiresAt']: fail('말씀 수정 요청에 기한이 없음: %s' % wr)
    if wr[0]['ackAt']: fail('수정 요청이 처음부터 처리됨')
    ok(cP.request.put(URL + 'api/services/%s/word' % sW, headers=H, data={'teamId': team, 'word': {'passage': '요 3:16', 'title': '사랑'}}))
    for n in notis(cP, team, 'word.request'):
        if not n['ackAt']: fail('목회자가 말씀을 적었는데 카드가 남음: %s' % n['title'])
    ok(cL.request.post(URL + 'api/services/%s/word-request' % sW, headers=H, data={'teamId': team}))
    if [n for n in notis(cP, team, 'word.request') if n['targetId'] == sW][0]['ackAt']: fail('다시 요청했는데 카드가 안 뜸')
    print('F129 말씀 수정 요청: 기한 · 목회자가 적으면 내려감 · 다시 요청하면 다시 뜸 ok')

    # 편성된 사람이 불가능으로 바꿈 → 편성에서 빼면 / 본인이 거두면 카드가 내려간다
    dC = day(10)
    idC = ok(cL.request.post(URL + 'api/teams/%s/dates' % team, headers=H, data={'date': dC, 'label': '수요', 'time': '19:30'}))['date']['id']
    ok(cL.request.put(URL + 'api/teams/%s/dates/%s/lineup' % (team, idC), headers=H, data={'lineup': [{'session': '드럼', 'memberId': uidM}]}))
    av = lambda st: ok(cM.request.put(URL + 'api/teams/%s/availability' % team, headers=H, data={'date': dC, 'state': st}))
    av('no')
    cf = notis(cL, team, 'avail.conflict')
    if not cf or cf[0]['ackAt']: fail('불가능으로 바꿈 알림이 없음')
    pl = page(cL)
    pl.evaluate("Promise.all([CONTI.pullNoti(),CONTI.pullSchedule(null,true)])"); pl.wait_for_timeout(800)
    titles = pl.evaluate("CONTI.todoCards().map(c=>c.title)")
    if not any('불가능' in t for t in titles): fail('인도자 할 일에 불가능 카드가 없음: %s' % titles)
    av('ok')
    if not notis(cL, team, 'avail.conflict')[0]['ackAt']: fail('본인이 불가능을 거뒀는데 카드가 남음')
    av('no')
    if notis(cL, team, 'avail.conflict')[0]['ackAt']: fail('다시 불가능으로 바꿨는데 카드가 안 뜸')
    ok(cL.request.put(URL + 'api/teams/%s/dates/%s/lineup' % (team, idC), headers=H, data={'lineup': []}))
    if not notis(cL, team, 'avail.conflict')[0]['ackAt']: fail('편성에서 뺐는데 불가능 카드가 남음')
    pl.evaluate("Promise.all([CONTI.pullNoti(),CONTI.pullSchedule(null,true)])"); pl.wait_for_timeout(800)
    if any('불가능' in t for t in pl.evaluate("CONTI.todoCards().map(c=>c.title)")): fail('처리한 불가능 카드가 홈에 남음')
    print('F129 불가능으로 바꿈 카드: 편성에서 빼거나 거두면 내려감 ok')

    # 석 달짜리 스케줄 요청: 첫 달만 답하면 남고, 다 답하면 내려간다
    cur = datetime.date.today().isoformat()[:7]
    months = [month_add(cur, 1), month_add(cur, 2), month_add(cur, 3)]
    ds = [m + '-12' for m in months]
    for d in ds: ok(cL.request.post(URL + 'api/teams/%s/dates' % team, headers=H, data={'date': d, 'label': '주일', 'time': '11:00'}))
    y, mo = map(int, months[2].split('-')); last = (datetime.date(y + (mo // 12), mo % 12 + 1, 1) - datetime.timedelta(days=1)).isoformat()
    sql("insert into notifications(team_id,user_id,type,target_id,title,body,actionable,expires_at) values($1,$2,'avail.request',$3,$4,'',true,$5)",
        [team, uidM, months[0], '%d~%d월 스케줄 알려주세요' % (int(months[0][5:]), int(months[2][5:])), last + 'T23:59:59+09:00'])
    pm = page(cM)
    avd = lambda d: ok(cM.request.put(URL + 'api/teams/%s/availability' % team, headers=H, data={'date': d, 'state': 'ok'}))
    avd(ds[0])
    if [n for n in notis(cM, team, 'avail.request') if n['targetId'] == months[0]][0]['ackAt']: fail('첫 달만 답했는데 서버가 카드를 내림')
    for mk in (cur, months[0]):   # 홈(이번 달)과 달력(다음 달)에서 본 창 모두
        pm.evaluate("(k)=>Promise.all([CONTI.pullNoti(),CONTI.pullSchedule(k,true)])", mk); pm.wait_for_timeout(600)
        if not any('스케줄' in t for t in pm.evaluate("CONTI.todoCards().map(c=>c.title)")): fail('첫 달만 답했는데 석 달 요청 카드가 사라짐 (창 %s)' % mk)
    avd(ds[1]); avd(ds[2])
    if not [n for n in notis(cM, team, 'avail.request') if n['targetId'] == months[0]][0]['ackAt']: fail('석 달을 다 답했는데 카드가 안 내려감')
    pm.evaluate("Promise.all([CONTI.pullNoti(),CONTI.pullSchedule(null,true)])"); pm.wait_for_timeout(600)
    if any('스케줄' in t for t in pm.evaluate("CONTI.todoCards().map(c=>c.title)")): fail('다 답한 스케줄 요청 카드가 홈에 남음')
    if pl.errs or pm.errs: fail('JS 오류: %s' % (pl.errs + pm.errs)[:3])
    print('F130 석 달 스케줄 요청: 첫 달만으론 남고, 다 답하면 내려감 ok')
    for x in (cL, cM, cP): x.close()

# ---------------------------------------------------------------- F131
IDB_DUMP = """()=>new Promise((res,rej)=>{const r=indexedDB.open('conti-v1');r.onsuccess=()=>{const db=r.result;const out={kv:{},blobs:[]};
  const t=db.transaction(['kv','blobs'],'readonly');const kv=t.objectStore('kv');
  kv.getAllKeys().onsuccess=e=>{const ks=e.target.result;let n=ks.length;if(!n)return;ks.forEach(k=>{kv.get(k).onsuccess=ev=>{out.kv[k]=String(ev.target.result).slice(0,200000)}})};
  t.objectStore('blobs').getAllKeys().onsuccess=e=>{out.blobs=e.target.result};t.oncomplete=()=>res(out)};r.onerror=()=>rej(r.error)})"""

def sec_logout(b):
    c, u, uid, team = leader(b, 'lo', service_workers='block')
    pg = page(c)
    pg.evaluate("""async ()=>{await CONTI.IDB.put('blobs','bxmine1',new Blob(['x'.repeat(400)],{type:'image/png'}));
      await CONTI.IDB.put('blobs','bxshare1',new Blob(['y'.repeat(400)],{type:'image/png'}));
      await CONTI.IDB.put('kv','state:someoneelse:none',JSON.stringify({services:[{id:'o',items:[{pieces:[{blob:'bxshare1'}]}]}]}));
      const s={id:'lg'+Date.now().toString(36),name:'비밀 예배',date:'2026-12-01',notice:'',version:0,published:null,
        items:[{id:'i1',title:'곡',pieces:[{id:'p1',blob:'bxmine1',markers:[]},{id:'p2',blob:'bxshare1',markers:[]}],media:[],notes:[{id:'n1',layer:'mine',text:'아무도 보면 안 되는 메모'}]}]};
      CONTI.S.services.push(s);CONTI.save()}""")
    pg.wait_for_timeout(800)
    d0 = pg.evaluate(IDB_DUMP)
    mine = [k for k in d0['kv'] if k.startswith('state:%s:' % uid)]
    if not mine or not any('아무도 보면 안 되는 메모' in d0['kv'][k] for k in mine): fail('준비: 메모가 IndexedDB 에 없음')
    pg.goto(URL + '#/settings'); pg.wait_for_selector('.setpane', timeout=8000)
    pg.click('[data-act="set-tab"][data-t="app"]'); pg.wait_for_selector('#sLogout', timeout=8000)
    pg.click('#sLogout'); pg.wait_for_selector('#lgUser', timeout=10000); pg.wait_for_timeout(800)
    d1 = pg.evaluate(IDB_DUMP)
    left = [k for k in d1['kv'] if k.startswith('state:%s:' % uid)]
    if left: fail('로그아웃했는데 이 계정 상태가 남음: %s' % left)
    if any('아무도 보면 안 되는 메모' in v for v in d1['kv'].values()): fail('로그아웃 뒤에도 메모 글이 IndexedDB 에 남음')
    if 'bxmine1' in d1['blobs']: fail('로그아웃 뒤에도 이 계정 악보 파일이 남음')
    if 'bxshare1' not in d1['blobs']: fail('다른 계정이 쓰는 파일까지 지움')
    if 'state:someoneelse:none' not in d1['kv']: fail('다른 계정 상태까지 지움')
    if pg.errs: fail('JS 오류: %s' % pg.errs[:3])
    print('F131 로그아웃: 이 계정 상태·파일만 지움 ok')
    c.close()

# ---------------------------------------------------------------- G30
STUB = """<!doctype html><script>setTimeout(()=>parent.postMessage(JSON.stringify({event:'onReady',id:1,channel:'widget'}),'*'),%d)</script>"""
def sec_yt(b):
    c, u, uid, team = leader(b, 'yt', service_workers='block')
    c.route(re.compile(r'^https://www\.youtube\.com/embed/.*'), lambda r: r.fulfill(status=200, body=STUB % 3200, headers={'content-type': 'text/html'}))
    c.route(re.compile(r'.*/ytstub\.html.*'), lambda r: r.fulfill(status=200, body=STUB % 3200, headers={'content-type': 'text/html'}))
    pg = page(c)
    sid = pg.evaluate("""()=>{const s={id:'yt'+Date.now().toString(36),name:'영상 예배',date:'2026-12-01',notice:'',version:0,published:null,
      items:[{id:'i1',title:'곡',key:'',mod:'',form:'',songNote:'',pieces:[],notes:[],media:[{id:'m1',type:'youtube',url:'https://youtu.be/dQw4w9WgXcQ',notes:[]}]}]};
      CONTI.S.services.push(s);CONTI.save();return s.id}""")
    for relay in (False, True):
        pg.goto(URL + '#/home'); pg.wait_for_timeout(300)
        pg.evaluate("(r)=>{CONTI.YT.relay=r?location.origin+'/ytstub.html':''}", relay)
        pg.goto(URL + '#/play/' + sid); pg.wait_for_selector('#yt', state='attached', timeout=10000)
        pg.wait_for_timeout(4500)
        h = pg.locator('#ytHint').inner_text()
        if not pg.evaluate('CONTI.P.ytReady'): fail('가짜 플레이어가 준비를 못 알림')
        if '재생할 수 없어요' in h: fail('준비됐는데 재생할 수 없다는 안내가 남음 (중계=%s): %s' % (relay, h))
    if pg.errs: fail('JS 오류: %s' % pg.errs[:3])
    print('G30 늦게 준비된 유튜브: 안내가 되돌아옴 · 중계는 더 기다림 ok')
    c.close()

# ---------------------------------------------------------------- G07
def sec_save_cost(b):
    c, u, uid, team = leader(b, 'sv', service_workers='block')
    ok(c.request.post(URL + 'api/songs', headers=H, data={'teamId': team, 'title': '저장곡'}))
    pg = page(c)
    # 몇 년 치가 쌓인 팀처럼 상태를 크게 만든다
    pg.evaluate("""()=>{const big='가'.repeat(2000);for(let i=0;i<400;i++){const items=[];for(let k=0;k<6;k++)items.push({id:'i'+i+'_'+k,title:'곡'+k,pieces:[{id:'p',blob:'',markers:[],chords:Array.from({length:40},(_,j)=>({t:big.slice(0,40),x:j}))}],media:[],notes:[{id:'n'+k,text:big}]});
      CONTI.S.services.push({id:'old'+i,name:'지난 예배 '+i,date:'2024-01-01',notice:'',version:1,items,published:{version:1,items:JSON.parse(JSON.stringify(items))}})}}""")
    sid = new_service_ui(pg, '이번 주', '첫 곡')
    cdp = c.new_cdp_session(pg); cdp.send('Emulation.setCPUThrottlingRate', {'rate': 6})
    pg.evaluate("()=>{window.__puts=0;const o=CONTI.IDB.put;CONTI.IDB.put=function(s,k,v){if(s==='kv'&&k!=='scope')window.__puts++;return o.apply(this,arguments)}}")
    pg.evaluate("CONTI.save()"); pg.wait_for_timeout(2500)   # 한 번 써서 걸리는 시간을 잰다
    pg.evaluate("window.__puts=0")
    el = pg.locator('[data-f="item.title"]').first
    el.click(); el.press('End')
    for ch in '새로운제목입니다':
        el.type(ch); pg.wait_for_timeout(300)
    puts_typing = pg.evaluate('window.__puts')
    pg.evaluate("document.dispatchEvent(new Event('visibilitychange'))")   # 보이는 상태라 아무 일 없다
    pg.evaluate("Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});document.dispatchEvent(new Event('visibilitychange'))")
    pg.wait_for_timeout(1500)
    cdp.send('Emulation.setCPUThrottlingRate', {'rate': 1})
    saved = pg.evaluate("""()=>CONTI.IDB.get('kv',CONTI.scope()).then(r=>{const s=JSON.parse(r);const v=s.services.find(x=>x.name==='이번 주');return v&&v.items[0].title})""")
    if puts_typing > 3: fail('큰 상태에서 글자마다 전체 저장이 돔: %d번 (8글자)' % puts_typing)
    if saved != '첫 곡새로운제목입니다': fail('가려질 때 저장이 안 됨: %r' % saved)
    pg.evaluate("Object.defineProperty(document,'hidden',{configurable:true,get:()=>false})")
    # 바뀐 것 없는 곡 받기는 저장·다시 그리기를 부르지 않는다
    pg.evaluate("CONTI.pullSongs(true)")
    again = pg.evaluate("CONTI.pullSongs(true)")
    if again: fail('바뀐 게 없는데 곡 받기가 바뀜으로 보고함')
    if pg.errs: fail('JS 오류: %s' % pg.errs[:3])
    print('G07 큰 상태에서 타이핑 중 저장 %d번 · 가려질 때 저장 · 같은 곡 다시 받기는 저장 안 함 ok' % puts_typing)
    c.close()

# ---------------------------------------------------------------- F70
def sec_legal(b):
    c = b.new_context(); pg = c.new_page()
    pg.goto(URL + '#/legal/privacy'); pg.wait_for_selector('.legal', timeout=10000); pg.wait_for_timeout(300)
    t = pg.locator('.legal').inner_text()
    for must in ('Google Cloud Run', '싱가포르', 'Cloudflare', 'Neon'):
        if must not in t: fail('개인정보처리방침에 "%s" 없음' % must)
    if 'Vercel' in t: fail('더 쓰지 않는 Vercel 이 남아 있음')
    c2, u, uid = account(b, 'lv', '하은')
    ver = ok(c2.request.get(URL + 'api/me'))['user']['legalVer']
    if ver not in t: fail('방침 시행일(%s)이 서버 약관 버전과 다름' % ver)
    print('F70 처리위탁 표: Cloud Run·Neon(싱가포르)·Cloudflare R2 · 시행일 = 서버 버전 ok')
    c.close(); c2.close()

def run():
    only = set(sys.argv[1:])
    secs = [('publish', sec_publish), ('native', sec_native_token), ('hero', sec_hero_lineup), ('fixed', sec_fixed_notes),
            ('prefs', sec_prefs), ('todo', sec_todo), ('logout', sec_logout), ('yt', sec_yt), ('save', sec_save_cost), ('legal', sec_legal)]
    with sync_playwright() as p:
        b = p.chromium.launch()
        for name, fn in secs:
            if only and name not in only: continue
            fn(b)
        b.close()
    print('OK test_audit_fe_03')

run()
