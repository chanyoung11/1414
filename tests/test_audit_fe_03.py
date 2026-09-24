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
#  검증에서 되돌려진 것 (r-*):
#  F69·F18 다시 올리기 409 뒤에도 못 보낸 곡은 '수정 중'으로 남음 · 같은 판을 겹쳐 올려도 가짜 충돌 없음 ·
#          켤 때 온라인이었다가 끊긴 발행도 다시 연결·화면 복귀에 올림 · 올리는 중 표시 · 올린 뒤 홈이 바로 바뀜
#  F67    초안에서만 날짜를 옮긴 콘티의 히어로 · F71 알림 탭을 느린 받기 없이 바로 그림 · 받는 사이 끈 것 유지
#  F66    편성 저장 줄 (닫기·다시 그리기·비우기·자리 수·두 날짜·통보) · F131 로그아웃 전에 못 올린 메모 올리기·경고 · 안 쓰는 파일 지우기
#  G07    쓰기 간격 안의 새로고침·닫기(저널) · 간격이 끝없이 밀리지 않음 · 초기화·팀 전환과 저널
#  마지막 검증 (fe-03 final):
#  F66    기다리던 자리 수를 뒤 고르기가 버리지 않음 · 자리 수 저장이 실패하면 칸도 되돌림
#  F131   다른 팀에 남은 못 올린 메모도 로그아웃 확인이 팀 이름과 함께 알림
#  G07    보기 화면에서 쓰고·지운 메모(editedAt 그대로)도 저널에 적힘
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
    # 켤 때의 목록 받기가 끝난 뒤에 넣는다 — 늦게 끝나면 서버에 없는 지난 예배를 '서버에서 지워진 것'으로 치워 상태가 작아진다
    pg.evaluate('CONTI.SYNC.pullServices()'); pg.wait_for_timeout(300)
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

# ================================================================ 검증에서 되돌려진 것 바로잡기
def toasts_on(pg):
    pg.evaluate("""()=>{if(window.__toasts)return;window.__toasts=[];const t=document.getElementById('toast');
      new MutationObserver(()=>window.__toasts.push(t.textContent)).observe(t,{childList:true,characterData:true,subtree:true})}""")

def delay_put(pg, suffix, ms, times=1):
    # 페이지 안에서 PUT 하나(또는 여러 번)를 늦게 보낸다 (파이썬 route 에서 자면 브라우저 전체가 멈춘다)
    pg.evaluate("""([sfx,ms,times])=>{const of=window.fetch;let n=0;window.fetch=(u,o)=>{if(String(u).endsWith(sfx)&&o&&o.method==='PUT'&&n++<times)
      return new Promise(r=>setTimeout(r,ms)).then(()=>of(u,o));return of(u,o)}}""", [suffix, ms, times])

def svc_of(pg, sid):
    return pg.evaluate("(id)=>{const s=CONTI.S.services.find(x=>x.id===id);return s?{items:s.items.map(i=>i.title),pub:s.published&&s.published.items.map(i=>i.title),v:s.version,pv:s.published&&s.published.version,pending:!!s.pubPending}:null}", sid)

# F69 · F18(1): 다시 올리기가 409 를 받아도 보내지 못한 내 곡은 '수정 중' 초안으로 남는다 · 겹쳐 올려도 가짜 충돌이 없다
def sec_r_pub(b):
    c, u, uid, team = leader(b, 'rq', service_workers='block')
    pg = page(c)
    sid = new_service_ui(pg, '충돌 예배', '곡1')
    publish_ui(pg, sid)
    if not wait_until(pg, "(id)=>{const s=CONTI.S.services.find(x=>x.id===id);return s&&s.published&&!s.pubPending}", arg=sid): fail('v1 발행 실패')
    date = pg.evaluate("(id)=>CONTI.S.services.find(x=>x.id===id).date", sid)
    rx = re.compile(r'.*/api/services/%s$' % re.escape(sid))
    hit = {'n': 0}
    def cut(route):
        if route.request.method == 'PUT' and hit['n'] == 0: hit['n'] += 1; return route.abort('failed')
        route.continue_()
    pg.route(rx, cut)
    publish_ui(pg, sid, add_song='내곡2'); pg.wait_for_timeout(1500)
    st = svc_of(pg, sid)
    if not (st['pending'] and st['pv'] == 2): fail('준비: 실패한 v2 가 발행 대기가 아님: %s' % st)
    pg.unroute(rx, cut)
    other = [{'id': 'o1', 'title': '곡1', 'key': '', 'pieces': [], 'media': []}, {'id': 'o2', 'title': '남의곡2', 'key': '', 'pieces': [], 'media': []}]
    ok(c.request.put(URL + 'api/services/' + sid, headers=H, data={'teamId': team, 'doc': {'id': sid, 'name': '충돌 예배', 'date': date, 'version': 2, 'items': other}}), '다른 기기 v2')
    pg.goto(URL + '#/home'); pg.wait_for_selector('[data-act="repub"]', timeout=8000)
    pg.click('[data-act="repub"]')
    if not wait_until(pg, "(id)=>{const s=CONTI.S.services.find(x=>x.id===id);return s&&!s.pubPending&&s.published.items.some(i=>i.title==='남의곡2')}", 10000, sid):
        fail('충돌 뒤 서버 발행본을 받지 않음: %s' % svc_of(pg, sid))
    st = svc_of(pg, sid)
    if '내곡2' not in st['items']: fail('충돌 뒤 보내지 못한 내 곡이 사라짐 (다시 발행할 게 없음): %s' % st)
    if not st['v'] > st['pv']: fail("충돌 뒤 내 초안이 '수정 중'으로 안 남음: %s" % st)
    pg.wait_for_timeout(400)
    if '수정 중' not in pg.locator('#app').inner_text(): fail("홈에 '수정 중' 표시가 없음")
    publish_ui(pg, sid)
    if not wait_until(pg, "(id)=>{const s=CONTI.S.services.find(x=>x.id===id);return s&&!s.pubPending&&s.published.version===3}", 10000, sid): fail('충돌 뒤 다시 발행이 안 됨: %s' % svc_of(pg, sid))
    doc = ok(c.request.get(URL + 'api/services/%s?team=%s' % (sid, team)))['doc']
    if doc['version'] != 3 or '내곡2' not in [i['title'] for i in doc['items']]: fail('다시 발행한 v3 에 내 곡이 없음: %s' % [i['title'] for i in doc['items']])
    print("F69·F18 다시 올리기 충돌: 못 보낸 내 곡은 '수정 중'으로 남고 v3 으로 다시 발행됨 ok")

    # 켤 때 올리기와 다시 올리기 단추가 겹쳐도(같은 판을 동시에) 가짜 '이미 발행' 충돌이 없다
    toasts_on(pg)
    hit['n'] = 0; pg.route(rx, cut)
    publish_ui(pg, sid, add_song='곡4'); pg.wait_for_timeout(1500)
    if not svc_of(pg, sid)['pending']: fail('준비: 실패한 v4 가 발행 대기가 아님')
    pg.unroute(rx, cut)
    pg.goto(URL + '#/home'); pg.wait_for_timeout(300)
    pg.evaluate("window.__toasts.length=0")
    pg.evaluate("(id)=>Promise.all([CONTI.SYNC.pushPending(),CONTI.SYNC.pushPending(id),CONTI.SYNC.pushPending(id)])", sid)
    pg.wait_for_timeout(300)
    if svc_of(pg, sid)['pending'] or server_version(c, team, sid) != 4: fail('겹친 다시 올리기 뒤 v4 가 안 올라감: %s' % svc_of(pg, sid))
    bad_t = [t for t in pg.evaluate('window.__toasts') if '이미 발행' in t]
    if bad_t: fail('같은 판을 겹쳐 올렸는데 충돌 안내가 뜸: %s' % bad_t)
    # 서버: 같은 판을 동시에 여러 번 받아도 모두 받아 준다 (하나만 쓰이고 나머지는 같은 판으로 본다)
    res = pg.evaluate("""async ([id,team,date])=>{const doc={id,name:'충돌 예배',date,version:9,items:[{id:'z',title:'동시'}]};
      const f=()=>fetch('/api/services/'+id,{method:'PUT',headers:{'x-conti':'1','content-type':'application/json'},body:JSON.stringify({teamId:team,doc})}).then(r=>r.status);
      return Promise.all([f(),f(),f(),f()])}""", [sid, team, date])
    if res != [200, 200, 200, 200]: fail('같은 판을 동시에 보냈는데 가짜 409: %s' % res)
    r = c.request.put(URL + 'api/services/' + sid, headers=H, data={'teamId': team, 'doc': {'id': sid, 'name': 'x', 'date': date, 'version': 9, 'items': []}})
    if r.status != 409: fail('다른 내용의 같은 판은 여전히 409 여야 함: %s' % r.status)
    if pg.errs: fail('JS 오류: %s' % pg.errs[:3])
    print('F69 겹친 다시 올리기·동시에 같은 판: 가짜 충돌 없음 · 다른 판은 409 ok')
    c.close()

# F18(2·3): 켤 때 온라인이었다가 올리다 끊긴 발행도 다시 연결·화면 복귀에 올린다 · 올린 뒤 홈이 바로 바뀐다 · 올리는 중 표시
def sec_r_pub2(b):
    c, u, uid, team = leader(b, 'rr', service_workers='block')
    pg = page(c)
    sid = new_service_ui(pg, '재시도 예배', '곡1')
    publish_ui(pg, sid)
    if not wait_until(pg, "(id)=>{const s=CONTI.S.services.find(x=>x.id===id);return s&&s.published&&!s.pubPending}", arg=sid): fail('v1 발행 실패')
    # 올리는 중에 홈으로 가도 '서버에 못 올림'이 아니다
    delay_put(pg, '/api/services/' + sid, 2500)
    publish_ui(pg, sid, add_song='곡2'); pg.wait_for_timeout(300)
    pg.goto(URL + '#/home'); pg.wait_for_timeout(700)
    t = pg.locator('#app').inner_text()
    if '서버에 못 올림' in t or pg.locator('[data-act="repub"]').count(): fail("올리는 중인데 홈에 '서버에 못 올림'·다시 올리기")
    if '올리는 중' not in t: fail("올리는 중 표시가 없음")
    if not wait_until(pg, "(id)=>{const s=CONTI.S.services.find(x=>x.id===id);return s&&!s.pubPending}", 8000, sid): fail('늦은 발행이 안 끝남')
    pg.wait_for_timeout(500)
    if '서버에 못 올림' in pg.locator('#app').inner_text(): fail("올린 뒤에도 '서버에 못 올림'")
    print("F18 올리는 중에는 '올리는 중' (서버에 못 올림 아님) ok")

    rx = re.compile(r'.*/api/services/%s$' % re.escape(sid))
    hit = {'n': 0}
    def cut(route):
        if route.request.method == 'PUT' and hit['n'] == 0: hit['n'] += 1; return route.abort('failed')
        route.continue_()
    for v, how in ((3, 'online'), (4, 'visible')):
        hit['n'] = 0; pg.route(rx, cut)
        publish_ui(pg, sid, add_song='곡%d' % v); pg.wait_for_timeout(1500)
        if not svc_of(pg, sid)['pending']: fail('준비: 올리다 끊긴 v%d 가 발행 대기가 아님' % v)
        if pg.evaluate('CONTI.NET.server') is not True: fail('준비: 켤 때 온라인이어야 함')
        pg.unroute(rx, cut)
        pg.goto(URL + '#/home'); pg.wait_for_timeout(400)
        if how == 'online': pg.evaluate("window.dispatchEvent(new Event('online'))")
        else: pg.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
        if not wait_until(pg, "(id)=>{const s=CONTI.S.services.find(x=>x.id===id);return s&&!s.pubPending}", 8000, sid):
            fail("온라인으로 켠 뒤 끊긴 발행이 '%s' 에도 다시 안 올라감" % how)
        if server_version(c, team, sid) != v: fail('v%d 가 서버에 없음: %s' % (v, server_version(c, team, sid)))
        pg.wait_for_timeout(600)
        if '서버에 못 올림' in pg.locator('#app').inner_text(): fail("다시 올린 뒤에도 홈에 '서버에 못 올림'이 남음 (%s)" % how)
    print('F18 켤 때 온라인 → 올리다 끊긴 발행: 다시 연결·화면 복귀에 올리고 홈이 바로 바뀜 ok')

    # 오프라인으로 켠 뒤 다시 연결 → 올린 뒤 홈이 다른 화면으로 옮기지 않아도 바뀐다
    off = lambda r: r.abort('internetdisconnected')
    pg.route('**/api/**', off)
    pg.goto(URL + '#/home'); pg.reload(); pg.wait_for_selector('.shell', timeout=15000); pg.wait_for_timeout(500)
    publish_ui(pg, sid, add_song='곡5'); pg.wait_for_timeout(600)
    pg.goto(URL + '#/home'); pg.wait_for_timeout(500)
    if '서버에 못 올림' not in pg.locator('#app').inner_text(): fail("준비: 오프라인 발행이 홈에 '서버에 못 올림'으로 안 보임")
    pg.unroute('**/api/**', off)
    pg.evaluate("window.dispatchEvent(new Event('online'))")
    if not wait_until(pg, "(id)=>{const s=CONTI.S.services.find(x=>x.id===id);return CONTI.NET.server===true&&s&&!s.pubPending}", 15000, sid): fail('다시 연결됐는데 안 올라감')
    pg.wait_for_timeout(1500)
    if '서버에 못 올림' in pg.locator('#app').inner_text(): fail("다시 연결돼 올렸는데 홈에 '서버에 못 올림'이 그대로")
    if pg.errs: fail('JS 오류: %s' % pg.errs[:3])
    print("F18 오프라인 → 다시 연결해 올리면 홈 표시가 바로 바뀜 ok")
    c.close()

# F67: 초안에서만 날짜를 옮긴 콘티 — 히어로는 보여 주는 날의 날짜 행을 쓴다
def sec_r_hero(b):
    cL, _, uidL, team = leader(b, 'rh', service_workers='block')
    code = invite_code(cL, team)
    cM, _, uidM = join(b, 'ri', '민수', team, code, session='드럼')
    d7, d6 = day(7), day(6)
    idA = ok(cL.request.post(URL + 'api/teams/%s/dates' % team, headers=H, data={'date': d7, 'label': '주일예배', 'time': '11:00'}))['date']['id']
    ok(cL.request.get(URL + 'api/services?team=' + team))
    sid = {x['id']: x['serviceId'] for x in ok(cL.request.get(URL + 'api/teams/%s/schedule' % team))['dates']}[idA]
    if not sid: fail('준비: 날짜에 콘티가 안 이어짐')
    ok(cL.request.put(URL + 'api/teams/%s/dates/%s/lineup' % (team, idA), headers=H, data={'lineup': [{'session': '드럼', 'memberId': uidM}]}))
    ok(cL.request.put(URL + 'api/services/' + sid, headers=H, data={'teamId': team, 'doc': {'id': sid, 'name': '주일예배', 'date': d7, 'notice': '', 'message': '', 'messageRev': 0, 'version': 1, 'items': []}}))
    ok(cL.request.put(URL + 'api/services/%s/draft' % sid, headers=H, data={'teamId': team, 'doc': {'id': sid, 'name': '주일예배', 'date': d6, 'version': 2, 'items': []}}))
    dates = ok(cL.request.get(URL + 'api/teams/%s/schedule' % team))['dates']
    if not any(x['serviceId'] == sid and x['date'] == d6 for x in dates): fail('준비: 초안 날짜로 연결이 안 옮겨짐 %s' % dates)
    pm = page(cM)
    if not wait_until(pm, "(id)=>CONTI.S.services.some(s=>s.id===id)&&CONTI.SCH.dates.some(d=>d.serviceId===id)", 12000, sid): fail('멤버가 콘티·일정을 못 받음')
    pm.evaluate('CONTI.render()'); pm.wait_for_timeout(700)
    hero = pm.locator('.hero').inner_text().replace('\n', ' | ')
    if not ('11:00' in hero and '내 자리' in hero): fail('히어로가 보여 주는 날(%s)이 아닌 다른 날의 빈 날짜 행을 붙임: %s' % (d7, hero))
    if pm.errs: fail('JS 오류: %s' % pm.errs[:3])
    print('F67 초안에서만 날짜를 옮긴 콘티: 멤버 히어로가 그날의 시간·내 자리 ok')
    cL.close(); cM.close()

# F71: 알림 탭은 느린 설정 받기를 기다리지 않고 그린다 · 받는 사이 바꾼 것을 옛 값으로 되돌리지 않는다
def sec_r_prefs(b):
    cP, u, uid = account(b, 'rn', '하은', service_workers='block')
    ok(cP.request.post(URL + 'api/teams', headers=H, data={'name': '알림팀2', 'myName': '하은'}))
    pg = page(cP)
    pg.goto(URL + '#/settings'); pg.wait_for_selector('.setpane', timeout=8000)
    pg.click('[data-act="set-tab"][data-t="noti"]'); pg.wait_for_selector('[data-noti="publish"]', timeout=8000)
    pg.click('[data-act="set-tab"][data-t="app"]'); pg.wait_for_timeout(300)
    pg.evaluate("""()=>{const of=window.fetch;window.fetch=(u,o)=>{if(/\\/api\\/me\\/prefs$/.test(String(u))&&!(o&&o.method&&o.method!=='GET'))
      return new Promise(r=>setTimeout(r,4000)).then(()=>of(u,o));return of(u,o)}}""")
    t0 = time.time()
    pg.click('[data-act="set-tab"][data-t="noti"]'); pg.wait_for_selector('[data-noti="publish"]', timeout=9000)
    dt = time.time() - t0
    if dt > 2: fail('알림 탭이 느린 설정 받기(4초)를 기다린 뒤에야 그려짐: %.1f초' % dt)
    pg.uncheck('[data-noti="word.request"]')
    pg.wait_for_timeout(5000)   # 늦은 받기가 돌아온 뒤
    if pg.is_checked('[data-noti="word.request"]'): fail('받는 사이 끈 알림이 늦게 온 옛 값으로 다시 켜져 보임')
    if (ok(cP.request.get(URL + 'api/me/prefs'))['prefs'].get('notiOff') or {}).get('word.request') is not True: fail('끈 알림이 저장 안 됨')
    # 다른 기기에서 바꾼 것은 늦게 와도 받아서 다시 그린다
    ok(cP.request.patch(URL + 'api/me/prefs', headers=H, data={'prefs': {'notiOff': {'publish': True}}}))
    pg.click('[data-act="set-tab"][data-t="app"]'); pg.wait_for_timeout(200)
    pg.click('[data-act="set-tab"][data-t="noti"]'); pg.wait_for_selector('[data-noti="publish"]', timeout=9000)
    if not wait_until(pg, "()=>{const e=document.querySelector('[data-noti=\"publish\"]');return e&&!e.checked}", 7000): fail('다른 기기에서 끈 알림이 늦은 받기 뒤에도 켜져 보임')
    if pg.is_checked('[data-noti="word.request"]'): fail('다시 그렸더니 끈 알림이 켜짐')
    if pg.errs: fail('JS 오류: %s' % pg.errs[:3])
    print('F71 알림 탭: 느린 받기를 안 기다리고 그림 · 받는 사이 끈 것 유지 · 늦게 온 다른 기기 값 반영 ok')
    cP.close()

# F66: 편성 저장 줄 — 고른 그때의 편성을 보낸다 (닫아도·다시 그려도·비우기·자리 수·두 날짜·통보)
def lineup_of(c, team, date_id):
    row = next(x for x in ok(c.request.get(URL + 'api/teams/%s/schedule' % team))['dates'] if x['id'] == date_id)
    return sorted((r['session'], r['memberId']) for r in (row['lineup'] or []) if r.get('memberId')), (row.get('slots') or {}), row.get('notified') or []

def sec_r_lineup(b):
    cL, _, uidL, team = leader(b, 'rk', service_workers='block')
    code = invite_code(cL, team)
    cM, _, uidM = join(b, 'rj', '민수', team, code, session='드럼')
    pl = page(cL)
    both = sorted([('드럼', uidM), ('인도자', uidL)])
    mk = lambda n: ok(cL.request.post(URL + 'api/teams/%s/dates' % team, headers=H, data={'date': day(20 + n), 'label': '예배%d' % n, 'time': '19:30'}))['date']['id']
    def open_(did):
        pl.goto(URL + '#/lineup/' + did); pl.wait_for_selector('[data-lsel="드럼"]', timeout=12000); pl.wait_for_timeout(400)
    delay_put(pl, '/lineup', 800, 1000)   # 모든 편성 저장이 0.8초씩 걸린다 (순서는 그대로)
    # S3 둘 고르고 바로 닫는다
    d = mk(1); open_(d)
    pl.select_option('[data-lsel="드럼"]', uidM); pl.wait_for_timeout(100)
    pl.select_option('[data-lsel="인도자"]', uidL); pl.wait_for_timeout(100)
    pl.click('.lnpanel [data-act="lclose"].icon'); pl.wait_for_timeout(3000)
    if lineup_of(cL, team, d)[0] != both: fail('둘 고르고 바로 닫았더니 뒤 선택이 저장 안 됨: %s' % (lineup_of(cL, team, d)[0],))
    # S9 저장 중에 다른 이유로 다시 그려진다
    d = mk(2); open_(d)
    pl.select_option('[data-lsel="드럼"]', uidM); pl.wait_for_timeout(100)
    pl.select_option('[data-lsel="인도자"]', uidL); pl.wait_for_timeout(50)
    pl.evaluate('CONTI.render()'); pl.wait_for_timeout(3000)
    if lineup_of(cL, team, d)[0] != both: fail('저장 중에 다시 그려졌더니 편성이 되돌아감: %s' % (lineup_of(cL, team, d)[0],))
    if pl.locator('[data-lsel="드럼"]').input_value() != uidM or pl.locator('[data-lsel="인도자"]').input_value() != uidL: fail('다시 그린 화면에서 고른 사람이 빠짐')
    # S5 고르고 바로 비우기
    d = mk(3); open_(d)
    pl.select_option('[data-lsel="드럼"]', uidM); pl.wait_for_timeout(100)
    pl.click('[data-act="lclear"][data-s="드럼"]'); pl.wait_for_timeout(3000)
    if lineup_of(cL, team, d)[0] != []: fail('고르고 바로 비웠는데 서버에 남음: %s' % (lineup_of(cL, team, d)[0],))
    # S6 자리 + 를 빨리 두 번
    d = mk(4); open_(d)
    pl.click('[data-act="lslots"][data-s="드럼"][data-d="1"]'); pl.wait_for_timeout(120)
    pl.click('[data-act="lslots"][data-s="드럼"][data-d="1"]'); pl.wait_for_timeout(3000)
    sl = lineup_of(cL, team, d)[1]
    if sl.get('드럼') != 3: fail('자리 + 두 번이 서버에 %s 로 남음' % sl)
    if pl.locator('[data-lsel="드럼"]').count() != 3: fail('자리 + 두 번 뒤 칸이 3개가 아님')
    # S7b 한 날짜 저장 중에 다른 날짜로 가서 둘 고른다
    dx, dy = mk(5), mk(6)
    open_(dx); pl.select_option('[data-lsel="드럼"]', uidM); pl.wait_for_timeout(100)
    open_(dy); pl.select_option('[data-lsel="드럼"]', uidM); pl.wait_for_timeout(100)
    pl.select_option('[data-lsel="인도자"]', uidL); pl.wait_for_timeout(3500)
    if lineup_of(cL, team, dx)[0] != [('드럼', uidM)]: fail('앞 날짜 편성이 저장 안 됨: %s' % (lineup_of(cL, team, dx)[0],))
    if lineup_of(cL, team, dy)[0] != both: fail('앞 날짜 저장이 끝나며 뒤 날짜의 선택을 버림: %s' % (lineup_of(cL, team, dy)[0],))
    # S8 둘 고르고 바로 통보
    d = mk(7); open_(d)
    pl.select_option('[data-lsel="드럼"]', uidM); pl.wait_for_timeout(100)
    pl.select_option('[data-lsel="인도자"]', uidL); pl.wait_for_timeout(100)
    pl.click('[data-act="lnotify"]'); pl.wait_for_timeout(4000)
    lu, _, nt = lineup_of(cL, team, d)
    if lu != both: fail('고르고 바로 통보했더니 편성이 빠짐: %s' % (lu,))
    if uidM not in nt: fail('통보 기록에 고른 사람이 없음: %s' % nt)
    if pl.errs: fail('JS 오류: %s' % pl.errs[:3])
    print('F66 편성 저장 줄: 닫기·다시 그리기·비우기·자리 수·두 날짜·통보 모두 고른 대로 저장 ok')
    # N1 고름(저장 중) → 자리 + → 고름: 뒤 고르기가 기다리던 자리 수를 버리지 않는다 (다시 열어도 두 칸)
    nsel = lambda: pl.locator('[data-lsel="드럼"]').count()
    d = mk(8); open_(d)
    pl.select_option('[data-lsel="드럼"]', uidM); pl.wait_for_timeout(120)
    pl.click('[data-act="lslots"][data-s="드럼"][data-d="1"]'); pl.wait_for_timeout(150)
    pl.select_option('[data-lsel="인도자"]', uidL); pl.wait_for_timeout(4000)
    lu, sl, _ = lineup_of(cL, team, d)
    if sl.get('드럼') != 2: fail('고름 → 자리 + → 고름: 늘린 자리 수가 서버에 안 감: %s' % sl)
    if lu != both: fail('고름 → 자리 + → 고름: 편성이 빠짐: %s' % (lu,))
    if nsel() != 2: fail('고름 → 자리 + → 고름 뒤 드럼 칸이 2개가 아님: %d' % nsel())
    pl.goto(URL + '#/sched'); pl.reload(); pl.wait_for_selector('.shell[data-page]', timeout=15000)
    delay_put(pl, '/lineup', 800, 1000); open_(d)
    if nsel() != 2: fail('다시 열었더니 늘린 드럼 자리가 사라짐: %d' % nsel())
    # N2 자리 + → 자리 + → 고름: 세 칸 그대로
    d = mk(9); open_(d)
    pl.click('[data-act="lslots"][data-s="드럼"][data-d="1"]'); pl.wait_for_timeout(150)
    pl.click('[data-act="lslots"][data-s="드럼"][data-d="1"]'); pl.wait_for_timeout(150)
    pl.select_option('[data-lsel="인도자"]', uidL); pl.wait_for_timeout(4000)
    lu, sl, _ = lineup_of(cL, team, d)
    if sl.get('드럼') != 3 or lu != [('인도자', uidL)]: fail('자리 + 두 번 → 고름: 서버 %s %s' % (sl, lu))
    if nsel() != 3: fail('자리 + 두 번 → 고름 뒤 드럼 칸이 3개가 아님: %d' % nsel())
    # 자리 + 저장이 끝내 실패하면 미리 늘려 둔 칸도 되돌린다 (서버에 자리 수가 없던 날 — 기본 정원 1)
    d = mk(10); open_(d)
    pl.evaluate("""()=>{const of=window.fetch;window.__lfail=1;window.fetch=(u,o)=>{if(/\\/lineup$/.test(String(u))&&o&&o.method==='PUT'&&window.__lfail>0){window.__lfail--;
      return new Promise(r=>setTimeout(r,300)).then(()=>new Response(JSON.stringify({error:'x',message:'잠시 실패'}),{status:500,headers:{'content-type':'application/json'}}))}return of(u,o)}}""")
    pl.click('[data-act="lslots"][data-s="드럼"][data-d="1"]'); pl.wait_for_timeout(150)
    if nsel() != 2: fail('준비: 자리 + 를 누른 바로 뒤 칸이 늘지 않음')
    pl.wait_for_timeout(1500)
    if lineup_of(cL, team, d)[1].get('드럼'): fail('실패한 자리 수가 서버에 있음')
    if nsel() != 1: fail('자리 수 저장이 실패했는데 늘린 칸이 화면에 남음: %d' % nsel())
    if pl.errs: fail('JS 오류: %s' % pl.errs[:3])
    print('F66 기다리던 자리 수를 뒤 고르기가 버리지 않음 · 실패하면 칸도 되돌림 ok')
    cL.close(); cM.close()

# F131: 로그아웃 — 못 올린 메모는 먼저 올리고, 못 올리면 알린다 · 어느 상태도 안 쓰는 파일도 지운다
def sec_r_logout(b):
    c, u, uid, team = leader(b, 'rl', service_workers='block')
    pg = page(c)
    sid = new_service_ui(pg, '메모 예배', '곡1'); publish_ui(pg, sid)
    if not wait_until(pg, "(id)=>{const s=CONTI.S.services.find(x=>x.id===id);return s&&s.published&&!s.pubPending}", arg=sid): fail('발행 실패')
    pg.goto(URL + '#/home'); pg.wait_for_timeout(500)
    add_note = """(id)=>{CONTI.NET.server=false;const s=CONTI.S.services.find(x=>x.id===id);
      s.items[0].notes=(s.items[0].notes||[]).concat({id:'nofl'+Date.now().toString(36),layer:'mine',text:'오프라인 메모',at:Date.now()});CONTI.save();CONTI.NET.server=true}"""
    pg.evaluate(add_note, sid)
    pg.evaluate("""async ()=>{await CONTI.IDB.put('blobs','bxorph1',new Blob(['o'.repeat(400)],{type:'image/png'}));
      await CONTI.IDB.put('blobs','bxshare2',new Blob(['s'.repeat(400)],{type:'image/png'}));
      await CONTI.IDB.put('kv','state:someoneelse2:none',JSON.stringify({services:[{id:'o',items:[{pieces:[{blob:'bxshare2'}]}]}]}))}""")
    # 닫히기 전에 적어 둔 이 계정의 저널(다른 팀 것 포함)과 다른 계정의 저널
    pg.evaluate("""([uid,team])=>{localStorage.setItem('conti-jr:state:'+uid+':'+team,JSON.stringify({at:1,ids:[],services:[{id:'j',items:[{notes:[{text:'저널 비밀메모'}]}]}]}));
      localStorage.setItem('conti-jr:state:'+uid+':other',JSON.stringify({at:1,ids:[]}));localStorage.setItem('conti-jr:state:someoneelse2:none',JSON.stringify({at:1,ids:[]}))}""", [uid, team])
    pg.goto(URL + '#/settings'); pg.wait_for_selector('.setpane', timeout=8000)
    pg.click('[data-act="set-tab"][data-t="app"]'); pg.wait_for_selector('#sLogout', timeout=8000)
    pg.click('#sLogout'); pg.wait_for_selector('#lgUser', timeout=15000); pg.wait_for_timeout(800)
    d1 = pg.evaluate(IDB_DUMP)
    if 'bxorph1' in d1['blobs']: fail('어느 상태도 쓰지 않는 파일(잘라 낸 원본·지운 조각)이 로그아웃 뒤에도 남음')
    if 'bxshare2' not in d1['blobs']: fail('다른 계정이 쓰는 파일까지 지움')
    jr = pg.evaluate("Object.keys(localStorage).filter(k=>k.startsWith('conti-jr:'))")
    if any(k.startswith('conti-jr:state:%s:' % uid) for k in jr): fail('로그아웃 뒤에도 이 계정의 저널(메모)이 남음: %s' % jr)
    if 'conti-jr:state:someoneelse2:none' not in jr: fail('다른 계정의 저널까지 지움')
    ok(c.request.post(URL + 'api/auth/login', headers=H, data={'username': u, 'password': 'secret1'}))
    notes = ok(c.request.get(URL + 'api/notes?team=%s&service=%s' % (team, sid)))['notes']
    if not any(n.get('text') == '오프라인 메모' for n in notes): fail('못 올린 메모가 로그아웃 때 올라가지도 않고 지워짐')
    if pg.errs: fail('JS 오류: %s' % pg.errs[:3])
    print('F131 로그아웃: 못 올린 메모를 먼저 올림 · 안 쓰는 파일도 지움 ok')
    c.close()
    # 올릴 수 없으면(메모 전송 실패) 확인 창이 알린다
    c2, u2, uid2, team2 = leader(b, 'rm', service_workers='block')
    pg2 = c2.new_page(); msgs = []
    pg2.on('dialog', lambda dl: (msgs.append(dl.message), dl.dismiss()))
    pg2.goto(URL + '#/home'); pg2.wait_for_selector('.shell[data-page]', timeout=15000)
    sid2 = new_service_ui(pg2, '메모 예배2', '곡1'); publish_ui(pg2, sid2)
    if not wait_until(pg2, "(id)=>{const s=CONTI.S.services.find(x=>x.id===id);return s&&s.published&&!s.pubPending}", arg=sid2): fail('발행 실패 2')
    pg2.goto(URL + '#/home'); pg2.wait_for_timeout(500)
    pg2.route('**/api/notes', lambda r: r.abort('failed'))
    pg2.evaluate(add_note, sid2)
    pg2.goto(URL + '#/settings'); pg2.wait_for_selector('.setpane', timeout=8000)
    pg2.click('[data-act="set-tab"][data-t="app"]'); pg2.wait_for_selector('#sLogout', timeout=8000)
    pg2.click('#sLogout'); pg2.wait_for_timeout(2500)
    if not msgs or '못 올린' not in msgs[-1]: fail('못 올린 메모가 있는데 로그아웃 확인에 경고가 없음: %s' % msgs[-1:])
    if pg2.locator('#lgUser').count(): fail('취소했는데 로그아웃됨')
    print('F131 로그아웃: 올리지 못한 메모가 있으면 확인 창이 알림 ok')
    c2.close()
    # 다른 팀(지금 팀이 아닌 팀)에 남은 못 올린 메모도 알린다 — 로그아웃은 이 계정의 모든 팀 저장을 지운다.
    # 그 팀으로 바꿔 로그아웃하면 먼저 올라간다
    c3, u3, uid3, tA = leader(b, 'rn', team_name='앞팀', service_workers='block')
    p3 = c3.new_page(); m3 = []; ans = {'ok': False}; p3.errs = []
    p3.on('pageerror', lambda e: p3.errs.append(str(e)[:200]))
    p3.on('dialog', lambda dl: (m3.append(dl.message), dl.accept() if ans['ok'] else dl.dismiss()))
    p3.goto(URL + '#/home'); p3.wait_for_selector('.shell[data-page]', timeout=15000)
    sid3 = new_service_ui(p3, '앞팀 예배', '곡1'); publish_ui(p3, sid3)
    if not wait_until(p3, "(id)=>{const s=CONTI.S.services.find(x=>x.id===id);return s&&s.published&&!s.pubPending}", arg=sid3): fail('발행 실패 3')
    p3.goto(URL + '#/home'); p3.wait_for_timeout(500)
    p3.evaluate(add_note, sid3); p3.wait_for_timeout(1500)
    tB = ok(c3.request.post(URL + 'api/teams', headers=H, data={'name': '둘째팀', 'myName': '하은', 'session': '인도자'}))['teamId']
    p3.reload(); p3.wait_for_selector('.shell[data-page]', timeout=15000); p3.wait_for_timeout(1000)
    def switch_to(t):
        p3.goto(URL + '#/team'); p3.wait_for_selector('[data-act="team-switch"]', timeout=10000)
        p3.click('[data-act="team-switch"]'); p3.wait_for_selector('[data-switch="%s"]' % t, timeout=5000); p3.click('[data-switch="%s"]' % t)
        if not wait_until(p3, '(t)=>CONTI.S.team.id===t', 10000, t): fail('준비: 팀 전환이 안 됨')
        p3.wait_for_timeout(1200)
    def logout3():
        p3.goto(URL + '#/settings'); p3.wait_for_selector('.setpane', timeout=8000)
        p3.click('[data-act="set-tab"][data-t="app"]'); p3.wait_for_selector('#sLogout', timeout=8000); p3.click('#sLogout')
    if p3.evaluate('CONTI.S.team.id') != tB: switch_to(tB)
    if any(n.get('text') == '오프라인 메모' for n in ok(c3.request.get(URL + 'api/notes?team=%s&service=%s' % (tA, sid3)))['notes']): fail('준비: 메모가 이미 올라감')
    logout3(); p3.wait_for_timeout(2500)
    if not m3 or '앞팀' not in m3[-1] or '못 올린' not in m3[-1]: fail('다른 팀의 못 올린 메모가 있는데 로그아웃 확인에 경고가 없음: %s' % m3[-1:])
    if p3.locator('#lgUser').count(): fail('취소했는데 로그아웃됨 (다른 팀)')
    has = p3.evaluate("(k)=>CONTI.IDB.get('kv',k).then(r=>!!r&&r.includes('오프라인 메모'))", 'state:%s:%s' % (uid3, tA))
    if not has: fail('취소했는데 다른 팀의 메모가 기기에서 지워짐')
    switch_to(tA); ans['ok'] = True
    logout3(); p3.wait_for_selector('#lgUser', timeout=15000); p3.wait_for_timeout(800)
    if '다른 팀' in m3[-1]: fail('그 팀으로 바꿔 올렸는데 다른 팀 경고가 남음: %s' % m3[-1])
    ok(c3.request.post(URL + 'api/auth/login', headers=H, data={'username': u3, 'password': 'secret1'}))
    if not any(n.get('text') == '오프라인 메모' for n in ok(c3.request.get(URL + 'api/notes?team=%s&service=%s' % (tA, sid3)))['notes']):
        fail('그 팀으로 바꿔 로그아웃했는데 메모가 안 올라감')
    if p3.errs: fail('JS 오류: %s' % p3.errs[:3])
    print('F131 로그아웃: 다른 팀의 못 올린 메모도 팀 이름과 함께 알림 · 그 팀으로 바꿔 로그아웃하면 올라감 ok')
    c3.close()

# G07: 쓰기 간격 안에 새로고침·닫기 해도 고친 것이 남는다 · 간격이 끝없이 밀리지 않는다 · 안 쓰던 저장 되살림
def sec_r_save(b):
    c, u, uid, team = leader(b, 'rs', service_workers='block')
    pg = page(c)
    sid = new_service_ui(pg, '저널 예배', '첫 곡'); pg.wait_for_timeout(1500)
    # 큰 상태처럼: 쓰기 한 번이 오래 걸려(0.12초 → 쉬는 간격 0.6초) 쉬는 사이 저널을 적고, 닫히는 페이지에서 시작한 큰 쓰기는
    # 끝나지 못한다 (상태 쓰기가 끝나지 않는 것으로 흉내 — 간격 안의 쓰기도 pagehide 의 쓰기도)
    stall = """()=>{const o=CONTI.IDB.put;CONTI.IDB.put=function(s,k,v){
      if(s==='kv'){const t=performance.now();while(performance.now()-t<120);return new Promise(()=>{})}return o.apply(this,arguments)}}"""
    title = "(id)=>{const s=CONTI.S.services.find(x=>x.id===id);return s&&s.items[0].title}"
    for how, add in (('reload', 'Q0'), ('close', 'Q1')):
        pg.goto(URL + '#/edit/' + sid); pg.wait_for_selector('[data-f="item.title"]', timeout=10000); pg.wait_for_timeout(400)
        pg.evaluate(stall)
        el = pg.locator('[data-f="item.title"]').first
        el.click(); el.press('End'); el.type(add); pg.wait_for_timeout(1500)
        if how == 'reload':
            pg.reload(); pg.wait_for_function("()=>window.CONTI&&document.querySelector('#app').children.length", timeout=15000)
        else:
            pg.close(); pg = page(c, '#/home')
        pg.wait_for_timeout(500)
        want = '첫 곡Q0' if how == 'reload' else '첫 곡Q0Q1'
        if pg.evaluate(title, sid) != want: fail('쓰기 간격 안에 %s 하자 고친 제목이 사라짐: %r' % (how, pg.evaluate(title, sid)))
    pg.wait_for_timeout(1500)
    if pg.evaluate("Object.keys(localStorage).filter(k=>k.startsWith('conti-jr')).length"): fail('되살린 뒤 다 쓴 저널이 남음')
    print('G07 쓰기 간격 안의 새로고침·닫기: 고친 것이 남음 ok')
    # 저장이 계속 불려도 쓰기가 끝없이 밀리지 않는다 (초안 올리기가 부르는 저장 등).
    # 상태 쓰기 한 번이 0.8초 걸리는 큰 팀처럼 만든다 → 쓰기 간격 4초. 0.5초마다 저장을 불러도 첫 변경에서 8초 안에는 쓴다
    pg.evaluate("""()=>{window.__p=0;window.__slow=true;const o=CONTI.IDB.put;CONTI.IDB.put=function(s,k,v){
      if(s==='kv'&&k!=='scope'){window.__p++;const t=performance.now();while(window.__slow&&performance.now()-t<800);}return o.apply(this,arguments)}}""")
    pg.evaluate('CONTI.save()'); pg.wait_for_timeout(1800)   # 한 번 써서 걸리는 시간을 잰다
    pg.evaluate('window.__p=0')
    for i in range(20):
        pg.evaluate('CONTI.save()'); pg.wait_for_timeout(500)
    n = pg.evaluate('window.__p')
    if n < 1: fail('10초 동안 저장이 계속 밀려 한 번도 안 씀')
    if n > 3: fail('큰 상태인데 저장을 부를 때마다 씀: %d번' % n)
    pg.evaluate('window.__slow=false'); pg.evaluate('CONTI.save()'); pg.wait_for_timeout(4500)
    # 메모 그림자만 줄인 것도 저장된다 (홈에서 — 콘티 화면이면 뒤따르는 메모 올리기가 먼저 줄여 버린다)
    pg.goto(URL + '#/home'); pg.wait_for_timeout(1500)
    pg.evaluate("(id)=>{CONTI.S.noteShadow=CONTI.S.noteShadow||{};CONTI.S.noteShadow[id]=[{id:'zz',itemId:'gone-item',mediaId:null}];return CONTI.save()}", sid)
    shadow_saved = "(id)=>CONTI.IDB.get('kv',CONTI.scope()).then(r=>JSON.stringify((JSON.parse(r).noteShadow||{})[id]||[]))"
    if not wait_until(pg, "(id)=>(%s)(id).then(s=>s.includes('zz'))" % shadow_saved, 9000, sid): fail('준비: 그림자가 저장 안 됨')
    pg.wait_for_timeout(3500)   # 저장이 부른 뒤따르는 일(곡 올리기 등)이 다 끝난 뒤
    pg.evaluate("(id)=>CONTI.SYNC.pushNotes(CONTI.S.services.find(x=>x.id===id))", sid); pg.wait_for_timeout(1200)
    if 'zz' in pg.evaluate(shadow_saved, sid): fail('메모 그림자에서 뺀 것이 저장 안 됨')
    # 콘티를 열 때 받은 말씀은 메모가 그대로여도 저장된다
    publish_ui(pg, sid)
    if not wait_until(pg, "(id)=>{const s=CONTI.S.services.find(x=>x.id===id);return s&&s.published&&!s.pubPending}", arg=sid): fail('발행 실패')
    ok(c.request.put(URL + 'api/services/%s/word' % sid, headers=H, data={'teamId': team, 'word': {'passage': '요 3:16', 'title': '사랑'}}))
    pg.goto(URL + '#/home'); pg.wait_for_timeout(300)
    pg.evaluate("(id)=>{const s=CONTI.S.services.find(x=>x.id===id);s.word=null;return CONTI.save()}", sid); pg.wait_for_timeout(1500)
    pg.goto(URL + '#/view/' + sid); pg.wait_for_timeout(2500)
    w = pg.evaluate("(id)=>CONTI.IDB.get('kv',CONTI.scope()).then(r=>{const s=JSON.parse(r).services.find(x=>x.id===id);return s&&s.word&&s.word.passage})", sid)
    if w != '요 3:16': fail('콘티를 열며 받은 말씀이 저장 안 됨: %r' % w)
    if pg.errs: fail('JS 오류: %s' % pg.errs[:3])
    print('G07 저장이 끝없이 밀리지 않음 · 그림자만 준 것·받은 말씀도 저장 ok')
    # 이 기기 초기화: 저널이 남아 지운 콘티를 되살리지 않는다 (막 고친 것이 아직 안 쓰였어도)
    pg.goto(URL + '#/edit/' + sid); pg.wait_for_selector('[data-f="item.title"]', timeout=10000); pg.wait_for_timeout(400)
    pg.evaluate(stall); pg.evaluate('CONTI.save()'); pg.wait_for_timeout(600)   # 느린 쓰기를 한 번 재게 한다
    el = pg.locator('[data-f="item.title"]').first
    el.click(); el.press('End'); el.type('R'); pg.wait_for_timeout(800)
    if not pg.evaluate("Object.keys(localStorage).some(k=>k.startsWith('conti-jr:'))"): fail('준비: 저널이 안 적힘')
    pg.goto(URL + '#/settings'); pg.wait_for_selector('.setpane', timeout=8000)
    pg.click('[data-act="set-tab"][data-t="app"]'); pg.wait_for_selector('#sReset', timeout=8000)
    pg.click('#sReset'); pg.wait_for_timeout(2500)
    pg.wait_for_function("()=>window.CONTI&&document.querySelector('#app').children.length", timeout=15000); pg.wait_for_timeout(800)
    if pg.evaluate("(id)=>CONTI.S.services.some(x=>x.id===id&&x.items[0].title.endsWith('R'))", sid): fail('초기화했는데 저널이 고친 콘티를 되살림')
    left = pg.evaluate("Object.keys(localStorage).filter(k=>k.startsWith('conti-jr:')).map(k=>localStorage.getItem(k)).join('')")
    if sid in left: fail('초기화 뒤에도 지운 콘티가 저널에 남음')
    print('G07 이 기기 초기화: 저널도 지워 되살리지 않음 ok')
    c.close()
    # 팀을 바꾸는 사이(새 팀 상태를 읽는 중) 저널이 적혀도 앞 팀 콘티를 새 팀 이름으로 적지 않는다 (켤 때 새 팀 콘티를 덮는다)
    c3, u3, uid3, teamA = leader(b, 'rt', service_workers='block')
    teamB = ok(c3.request.post(URL + 'api/teams', headers=H, data={'name': '둘째팀', 'myName': '하은', 'session': '인도자'}))['teamId']
    p3 = page(c3)
    cur = p3.evaluate('CONTI.S.team.id'); other = teamB if cur == teamA else teamA
    sidA = new_service_ui(p3, '앞팀 예배', '앞곡'); p3.wait_for_timeout(1500)
    # 큰 상태처럼 쓰기가 0.12초씩 걸려(쉬는 사이 저널을 적는다) 새 팀 상태 읽기가 0.9초 걸리고, 그사이 저장이 불린다
    p3.evaluate("""([uid,other])=>{window.__jw=[];const ss=Storage.prototype.setItem;
      Storage.prototype.setItem=function(k,v){if(String(k).startsWith('conti-jr:'))window.__jw.push([k,JSON.parse(v).ids]);return ss.apply(this,arguments)};
      const o=CONTI.IDB.put;CONTI.IDB.put=function(s){if(s==='kv'){const t=performance.now();while(performance.now()-t<120);}return o.apply(this,arguments)};
      const g=CONTI.IDB.get;CONTI.IDB.get=function(s,k){if(s==='kv'&&k==='state:'+uid+':'+other){setTimeout(()=>CONTI.save(),30);
        const r0=g.apply(this,arguments);return new Promise(r=>setTimeout(()=>r(r0),900))}return g.apply(this,arguments)}}""", [uid3, other])
    p3.evaluate('CONTI.save()'); p3.wait_for_timeout(700)   # 느린 쓰기를 한 번 재게 한다
    p3.goto(URL + '#/team'); p3.wait_for_selector('[data-act="team-switch"]', timeout=10000)
    p3.click('[data-act="team-switch"]'); p3.wait_for_selector('[data-switch="%s"]' % other)
    p3.click('[data-switch="%s"]' % other)
    if not wait_until(p3, '(t)=>CONTI.S.team.id===t', 10000, other): fail('준비: 팀 전환이 안 됨')
    p3.wait_for_timeout(800)
    bad = [k for k, ids in p3.evaluate('window.__jw') if k.endswith(':' + other) and sidA in (ids or [])]
    if bad: fail('팀을 바꾸는 사이 앞 팀 콘티가 새 팀 저널로 적힘: %s' % bad)
    if p3.errs: fail('JS 오류: %s' % p3.errs[:3])
    print('G07 팀 전환 중 저널: 앞 팀 콘티를 새 팀 이름으로 적지 않음 ok')
    c3.close()

# G07: 보기 화면에서 쓰거나 지운 메모 (touch() 를 안 거쳐 editedAt 이 그대로) — 홈으로 나간 뒤 쓰기 간격 안에 닫혀도 남는다
def sec_r_save_note(b):
    c, u, uid, team = leader(b, 'rv', service_workers='block')
    pg = page(c)
    sid = new_service_ui(pg, '메모 저널 예배', '곡1'); publish_ui(pg, sid)
    if not wait_until(pg, "(id)=>{const s=CONTI.S.services.find(x=>x.id===id);return s&&s.published&&!s.pubPending}", arg=sid): fail('발행 실패')
    stall = """()=>{const o=CONTI.IDB.put;CONTI.IDB.put=function(s,k,v){
      if(s==='kv'){const t=performance.now();while(performance.now()-t<120);return new Promise(()=>{})}return o.apply(this,arguments)}}"""
    local = "(a)=>{const s=CONTI.S.services.find(x=>x.id===a[0]);return !!s&&CONTI.SYNC.localNotes(s).some(n=>n.id===a[1])}"
    def reopen():
        pg.reload(); pg.wait_for_function("()=>window.CONTI&&document.querySelector('#app').children.length", timeout=15000); pg.wait_for_timeout(600)
    # 쓴 메모: 보기 화면에서 쓰고 0.3초 만에 홈으로(메모는 콘티 화면에서만 올라간다) → 쓰기가 끝나기 전에 새로고침
    pg.goto(URL + '#/view/' + sid); pg.wait_for_timeout(1500)
    pg.evaluate(stall); pg.evaluate('CONTI.save()'); pg.wait_for_timeout(600)   # 느린 쓰기를 한 번 재게 한다 (쉬는 간격 0.6초)
    nid = 'jn' + tag
    pg.evaluate("""(a)=>{const s=CONTI.S.services.find(x=>x.id===a[0]);const it=s.items[0];it.notes=it.notes||[];
      it.notes.push({id:a[1],marker:null,layer:'mine',session:'인도자',text:'보기 화면 메모',author:'하은',at:Date.now()});CONTI.save()}""", [sid, nid])
    pg.wait_for_timeout(300); pg.evaluate("location.hash='#/home'"); pg.wait_for_timeout(1200)
    reopen()
    if not pg.evaluate(local, [sid, nid]): fail('보기 화면에서 쓴 메모가 홈으로 나간 뒤 새로고침하자 사라짐')
    # 서버까지: 다시 열면 올라간다
    pg.goto(URL + '#/view/' + sid)
    ok_srv = lambda: any(n['id'] == nid for n in ok(c.request.get(URL + 'api/notes?team=%s&service=%s' % (team, sid)))['notes'])
    for _ in range(20):
        if ok_srv(): break
        pg.wait_for_timeout(500)
    else: fail('되살린 메모가 콘티를 다시 열어도 안 올라감')
    if not wait_until(pg, "(a)=>(CONTI.S.noteShadow[a[0]]||[]).some(x=>(x.id||x)===a[1])", 8000, [sid, nid]): fail('준비: 그림자에 안 들어감')
    pg.wait_for_timeout(1500)
    # 지운 메모: 보기 화면에서 지우고 홈으로 → 새로고침해도 되살아나지 않는다 (다음에 열면 서버에서도 지운다)
    pg.evaluate(stall); pg.evaluate('CONTI.save()'); pg.wait_for_timeout(600)
    pg.evaluate("(a)=>{const s=CONTI.S.services.find(x=>x.id===a[0]);s.items[0].notes=s.items[0].notes.filter(n=>n.id!==a[1]);CONTI.save()}", [sid, nid])
    pg.wait_for_timeout(300); pg.evaluate("location.hash='#/home'"); pg.wait_for_timeout(1200)
    reopen()
    if pg.evaluate(local, [sid, nid]): fail('보기 화면에서 지운 메모가 홈으로 나간 뒤 새로고침하자 되살아남')
    pg.goto(URL + '#/view/' + sid)
    for _ in range(20):
        if not ok_srv(): break
        pg.wait_for_timeout(500)
    else: fail('지운 메모가 콘티를 다시 열어도 서버에서 안 지워짐')
    pg.wait_for_timeout(1500)
    if pg.evaluate("Object.keys(localStorage).filter(k=>k.startsWith('conti-jr')).length"): fail('다 쓴 뒤에도 저널이 남음')
    if pg.errs: fail('JS 오류: %s' % pg.errs[:3])
    print('G07 보기 화면에서 쓰고·지운 메모: 홈으로 나간 뒤 쓰기 간격 안에 새로고침해도 남음 ok')
    c.close()

def run():
    only = set(sys.argv[1:])
    secs = [('publish', sec_publish), ('native', sec_native_token), ('hero', sec_hero_lineup), ('fixed', sec_fixed_notes),
            ('prefs', sec_prefs), ('todo', sec_todo), ('logout', sec_logout), ('yt', sec_yt), ('save', sec_save_cost), ('legal', sec_legal),
            ('r-pub', sec_r_pub), ('r-pub2', sec_r_pub2), ('r-hero', sec_r_hero), ('r-prefs', sec_r_prefs), ('r-lineup', sec_r_lineup),
            ('r-logout', sec_r_logout), ('r-save', sec_r_save), ('r-save-note', sec_r_save_note)]
    with sync_playwright() as p:
        b = p.chromium.launch()
        for name, fn in secs:
            if only and name not in only: continue
            fn(b)
        b.close()
    print('OK test_audit_fe_03')

run()
