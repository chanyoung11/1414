# 검토(2026-09-08) critical/high 수정 검증
#  - 로그아웃·다른 계정 로그인·팀 전환 시 로컬 콘티가 새지 않음 (계정·팀 단위 스코프)
#  - 인도자 비밀번호 초기화는 다른 팀에도 속한 계정에 대해 거부
#  - 비밀번호 변경 후 다른 기기 세션 무효, 이 기기는 유지
#  - SYNC.repairBlobs 가 실제로 파일을 다시 올림
#  - 가져오기: 덮어쓰기 확인, 메모 그림자 축소(대량 삭제 방지), 이상한 id 정리(XSS)
#  - 크론 인증: 위조 헤더 거부, CRON_SECRET 만 통과
import os, sys, time, json
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHEET = os.path.join(ROOT, 'docs', 'sample_sheet.jpg')
tag = str(int(time.time()))[-6:]
A = ('fa' + tag, 'secret1', '하은')
B = ('fb' + tag, 'secret1', '민수')
H = {'x-conti': '1'}

def fail(msg): print('FAIL:', msg); sys.exit(1)

def signup(pg, u):
    pg.goto(URL); pg.wait_for_selector('#lgUser', timeout=8000)
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName')
    pg.fill('#lgName', u[2]); pg.fill('#lgUser', u[0]); pg.fill('#lgPass', u[1]); pg.click('[data-act="lg-submit"]')

def login(pg, u):
    pg.wait_for_selector('#lgUser', timeout=8000)
    if pg.locator('[data-act="lg-mode"][data-m="login"]').count() and pg.locator('#lgName').count():
        pg.click('[data-act="lg-mode"][data-m="login"]')
    pg.fill('#lgUser', u[0]); pg.fill('#lgPass', u[1]); pg.click('[data-act="lg-submit"]')

def make_team(pg, name):
    pg.wait_for_selector('#gtTeam', timeout=8000); pg.fill('#gtTeam', name); pg.click('[data-act="team-create"]')
    pg.wait_for_selector('.hd [data-act="team"]', timeout=8000)
    return pg.evaluate('CONTI.S.team.id')

def logout_ui(pg):
    pg.goto(URL + '#/home'); pg.wait_for_selector('.hd'); pg.click('.hd [data-act="settings"]'); pg.wait_for_selector('#sLogout'); pg.click('#sLogout')
    pg.wait_for_selector('#lgUser', timeout=8000)

def run():
    with sync_playwright() as p:
        b = p.chromium.launch(); errs = []
        ctx = b.new_context(viewport={'width': 1180, 'height': 820}); pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('dialog', lambda d: d.accept())

        # ---- A: 팀 X, 콘티 + 악보 발행 ----
        signup(pg, A); teamX = make_team(pg, '스코프X')
        uidA = pg.evaluate('CONTI.NET.user.id')
        pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]'); pg.fill('[data-f="svc.name"]', 'X팀 예배')
        pg.click('[data-act="add-item"]'); pg.wait_for_selector('[data-f="item.title"]'); pg.fill('[data-f="item.title"]', 'X곡')
        pg.set_input_files('#pieceFile', [SHEET])
        pg.wait_for_function("(()=>{const p=CONTI.S.services[0].items[0].pieces[0];return p&&p.ocr&&p.ocr!=='pending'})()", timeout=60000)
        svcX = pg.evaluate('CONTI.S.services[0].id')
        pg.click('[data-act="publish"]'); pg.wait_for_selector('#pubOnly'); pg.click('#pubOnly'); pg.wait_for_timeout(5000)
        if svcX not in ctx.request.get(URL + 'api/services?team=' + teamX).text(): fail('X 발행본이 서버에 없음')
        scopeA = pg.evaluate('CONTI.scope()')
        if not scopeA.startswith('state:' + uidA + ':' + teamX): fail('스코프 키가 계정·팀 단위가 아님: ' + scopeA)
        print('A published in X, scope', scopeA)

        # ---- 악보 다시 불러오기: 이 기기 캐시를 비우고 서버에서 다시 받는다 (명세 B.8) ----
        ids = pg.evaluate("CONTI.SYNC.blobIds(CONTI.S.services[0].items)")
        n = pg.evaluate('CONTI.SYNC.refetchBlobs()')
        if not n or n < 1: fail('악보 다시 불러오기 결과 이상: %s' % n)
        back = pg.evaluate("(async ids=>{for(const id of ids){if(!await CONTI.IDB.get('blobs',id))return id}return ''})(%s)" % ids)
        if back: fail('다시 받은 뒤에도 이 기기에 없는 악보가 있음: %s' % back)
        print('refetchBlobs', n)

        # ---- 로그아웃: 로컬 콘티가 화면·상태에서 사라짐 ----
        logout_ui(pg)
        if pg.evaluate('CONTI.S.services.length') != 0: fail('로그아웃 후에도 콘티가 남음')
        if pg.evaluate('CONTI.S.team.id'): fail('로그아웃 후 팀 id 남음')

        # ---- 같은 기기에서 B 가입 → 팀 Y: A 의 콘티가 보이면 안 됨 ----
        pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName'); pg.fill('#lgName', B[2]); pg.fill('#lgUser', B[0]); pg.fill('#lgPass', B[1]); pg.click('[data-act="lg-submit"]')
        teamY = make_team(pg, '스코프Y')
        if pg.evaluate('CONTI.S.services.length') != 0: fail('B 팀 홈에 A 콘티가 새어 나옴')
        if 'X팀 예배' in pg.locator('#app').inner_text(): fail('B 화면에 X팀 예배가 보임')
        linkY = pg.evaluate("location.origin+location.pathname+'#/join/'+CONTI.S.team.invite")
        print('B team Y isolated; invite', linkY[-12:])
        logout_ui(pg)

        # ---- A 재로그인: 자기 콘티 복원 ----
        login(pg, A); pg.wait_for_selector('.hd [data-act="team"]', timeout=8000); pg.wait_for_timeout(800)
        if pg.evaluate('CONTI.S.services.length') < 1 or pg.evaluate('CONTI.S.services[0].name') != 'X팀 예배': fail('A 재로그인 후 콘티 복원 안 됨')
        print('A restored')

        # ---- A 가 Y 에 가입 → 팀 전환 시 격리 ----
        pg.goto(linkY); pg.wait_for_selector('#jnName', timeout=8000); pg.click('[data-act="team-join"]'); pg.wait_for_selector('.hd [data-act="team"]', timeout=8000); pg.wait_for_timeout(800)
        if pg.evaluate('CONTI.S.team.id') != teamY: fail('가입 후 현재 팀이 Y 가 아님')
        if pg.evaluate('CONTI.S.services.length') != 0: fail('Y 로 전환됐는데 X 콘티가 남아 있음 (서버로 새어 올라갈 수 있음)')
        pg.click('.hd [data-act="team"]'); pg.wait_for_selector('.tpage', timeout=10000)
        pg.click('[data-act="team-switch"]'); pg.wait_for_selector('[data-switch]', timeout=5000)
        pg.click('[data-switch="%s"]' % teamX); pg.wait_for_timeout(1500)
        if pg.evaluate('CONTI.S.team.id') != teamX or pg.evaluate('CONTI.S.services.length') < 1: fail('X 로 다시 전환했는데 콘티가 없음')
        if teamX in ctx.request.get(URL + 'api/services?team=' + teamY).text() or svcX in ctx.request.get(URL + 'api/services?team=' + teamY).text(): fail('X 콘티가 Y 서버에 올라감')
        print('team switch isolated')

        # ---- 비밀번호 초기화 제한: Y 인도자(B)가 두 팀에 속한 A 를 초기화 → 403 ----
        ctxB = b.new_context(); rb = ctxB.request
        rb.post(URL + 'api/auth/login', headers=H, data={'username': B[0], 'password': B[1]})
        rr = rb.post(URL + 'api/teams/%s/members/%s/reset' % (teamY, uidA), headers=H)
        if rr.status != 403: fail('다른 팀에도 속한 계정 초기화가 막히지 않음: %s %s' % (rr.status, rr.text()[:120]))
        print('reset blocked:', rr.json().get('message', '')[:40])

        # ---- 비밀번호 변경 → 다른 기기 세션 무효, 이 기기는 유지 ----
        ctxC = b.new_context(); rc = ctxC.request
        rc.post(URL + 'api/auth/login', headers=H, data={'username': A[0], 'password': A[1]})
        if rc.get(URL + 'api/me').status != 200: fail('기기 C 로그인 실패')
        time.sleep(1.1)  # iat 초 단위 → epoch 와 확실히 구분
        rp = ctx.request.post(URL + 'api/auth/password', headers=H, data={'current': A[1], 'next': 'newpass1'})
        if rp.status != 200: fail('비밀번호 변경 실패: %s' % rp.text()[:120])
        if rc.get(URL + 'api/me').status != 401: fail('비밀번호 변경 후에도 다른 기기 세션이 살아 있음')
        if ctx.request.get(URL + 'api/me').status != 200: fail('비밀번호를 바꾼 기기의 세션이 끊김')
        print('session invalidation ok')

        # ---- 가져오기: id 정리 + 메모 그림자 축소 + 덮어쓰기 확인창 ----
        pg.goto(URL + '#/home'); pg.wait_for_selector('.hd'); pg.wait_for_timeout(500)
        pg.evaluate("CONTI.S.noteShadow={};CONTI.S.noteShadow[%s]=['srv-note-1','srv-note-2'];CONTI.save()" % json.dumps(svcX))
        bad = {'app': 'conti', 'v': 1, 'at': 1, 'services': [
            {'id': svcX, 'name': 'X팀 예배(파일)', 'date': '2026-09-09', 'notice': '', 'version': 0, 'items': [], 'published': None},
            {'id': '"><img src=x onerror=window.__xss=1>', 'name': '이상한 id', 'date': '2026-09-09', 'notice': '', 'version': 0, 'items': [{'id': 'ok1', 'title': 't', 'key': '', 'mod': '', 'form': '', 'songNote': '', 'pieces': [], 'media': [], 'notes': []}], 'published': None}
        ], 'library': [], 'blobs': {}}
        pg.evaluate("CONTI.importJSON(new Blob([%s],{type:'application/json'}))" % json.dumps(json.dumps(bad, ensure_ascii=False)))
        pg.wait_for_timeout(1500)
        sh = pg.evaluate("CONTI.S.noteShadow[%s]" % json.dumps(svcX))
        if sh != []: fail('가져오기 후 메모 그림자가 줄지 않음(서버 메모 대량 삭제 위험): %s' % sh)
        ids = pg.evaluate("CONTI.S.services.map(s=>s.id)")
        import re
        if any(not re.match(r'^[A-Za-z0-9_-]{1,64}$', i) for i in ids): fail('이상한 id 가 그대로 들어옴: %s' % ids)
        if pg.evaluate('window.__xss||0'): fail('가져온 파일로 스크립트가 실행됨')
        if pg.evaluate('CONTI.S.services.find(s=>s.id===%s).name' % json.dumps(svcX)) != 'X팀 예배(파일)': fail('확인창 수락 시 덮어쓰기가 안 됨')
        print('import safety ok', len(ids), 'services')

        # ---- 느린 화면이 나중에 그려져 이동한 화면을 덮지 않는지 (render 경쟁) ----
        pg.goto(URL + '#/home'); pg.wait_for_selector('.hd', timeout=10000)
        pg.route('**/api/services/**', lambda route: (time.sleep(2.5), route.continue_()))
        pg.evaluate("location.hash='#/view/' + %s" % json.dumps(svcX)); pg.wait_for_timeout(300)
        pg.evaluate("location.hash='#/home'"); pg.wait_for_timeout(5000)
        pg.unroute('**/api/services/**')
        if pg.locator('.hd').count() == 0: fail('홈으로 갔는데 느린 콘티 화면이 덮어씀: ' + pg.locator('#app').inner_html()[:120])
        if not pg.url.endswith('#/home'): fail('주소가 홈이 아님: ' + pg.url)
        print('render race ok')

        # ---- 크론 인증 ----
        cr = ctx.request.get(URL + 'api/cron/dates', headers={'x-vercel-cron': '1'})
        if cr.status != 403: fail('위조 크론 헤더가 통과함: %s' % cr.status)
        sec = os.environ.get('CRON_SECRET', '')
        if sec:
            cr2 = ctx.request.get(URL + 'api/cron/dates', headers={'authorization': 'Bearer ' + sec})
            if cr2.status != 200: fail('CRON_SECRET 으로 크론 호출 실패: %s' % cr2.text()[:100])
        print('cron auth ok')

        print('errors:', errs)
        if errs: fail('page errors')
        b.close()
    print('FIXES TEST OK')

if __name__ == '__main__':
    run()
