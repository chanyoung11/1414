# §1 알림함·홈 카드 + §9 첫날 항목(이름 규칙·예배 병합·라이브러리 중복) + §2.2 콘티 자동 생성
import os, sys, time, json, re, datetime
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
tag = str(int(time.time()))[-6:]
L = ('nl' + tag, 'secret1', '하은')
M = ('nm' + tag, 'secret1', '민수')
H = {'x-conti': '1'}

def fail(msg): print('FAIL:', msg); sys.exit(1)

def signup(pg, u):
    pg.goto(URL); pg.wait_for_selector('#lgUser', timeout=8000)
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName')
    pg.fill('#lgName', u[2]); pg.fill('#lgUser', u[0]); pg.fill('#lgPass', u[1]); pg.click('[data-act="lg-submit"]')

def run():
    with sync_playwright() as p:
        b = p.chromium.launch(); errs = []
        cL = b.new_context(viewport={'width': 1180, 'height': 820}); pl = cL.new_page(); pl.on('pageerror', lambda e: errs.append('L:' + str(e))); pl.on('dialog', lambda d: d.accept())
        signup(pl, L); pl.wait_for_selector('#gtTeam', timeout=8000); pl.fill('#gtTeam', '알림팀'); pl.click('[data-act="team-create"]'); pl.wait_for_selector('.hd [data-act="team"]', timeout=8000)
        team = pl.evaluate('CONTI.S.team.id')
        link = pl.evaluate("location.origin+location.pathname+'#/join/'+CONTI.S.team.invite")
        # 팀 설정이 클라이언트에 내려오는지
        st = pl.evaluate('CONTI.S.team.settings')
        if not st or 'nameRule' not in st: fail('팀 설정이 클라이언트에 없음: %s' % st)

        cM = b.new_context(viewport={'width': 1180, 'height': 820}); pm = cM.new_page(); pm.on('pageerror', lambda e: errs.append('M:' + str(e))); pm.on('dialog', lambda d: d.accept())
        pm.goto(link); pm.wait_for_selector('#lgUser', timeout=8000)
        pm.click('[data-act="lg-mode"][data-m="signup"]'); pm.wait_for_selector('#lgName'); pm.fill('#lgName', M[2]); pm.fill('#lgUser', M[0]); pm.fill('#lgPass', M[1]); pm.click('[data-act="lg-submit"]')
        pm.wait_for_selector('#jnName', timeout=8000); pm.click('[data-act="team-join"]'); pm.wait_for_selector('.hd [data-act="team"]', timeout=8000)

        # ---- 이름 규칙: 이름 없이 발행하면 규칙대로 채워짐 ----
        pl.click('[data-act="new-svc"]'); pl.wait_for_selector('[data-f="svc.name"]')
        ph = pl.locator('[data-f="svc.name"]').get_attribute('placeholder')
        if not re.match(r'^\d+/\d+', ph or ''): fail('이름 규칙 placeholder 아님: %s' % ph)
        pl.click('[data-act="add-item"]'); pl.wait_for_selector('[data-f="item.title"]'); pl.fill('[data-f="item.title"]', '첫 곡'); pl.wait_for_timeout(300)
        pl.click('[data-act="publish"]'); pl.wait_for_selector('#pubOnly'); pl.click('#pubOnly'); pl.wait_for_timeout(4000)
        svc = pl.evaluate('CONTI.S.services[0]')
        if not re.match(r'^\d+/\d+$', svc['name']): fail('발행 시 이름 규칙 미적용: %r' % svc['name'])
        print('name rule ok:', svc['name'])

        # ---- publish 알림: 멤버에게만 ----
        r = cM.request.get(URL + 'api/notifications?team=' + team).json()
        pubs = [n for n in r['notifications'] if n['type'] == 'publish']
        if not pubs or r['unread'] < 1: fail('멤버에게 publish 알림 없음: %s' % r)
        if '콘티 v1' not in pubs[0]['title'] or re.match(r'^(\d+/\d+)\s+\1', pubs[0]['title']) or '첫 곡' not in pubs[0]['body']: fail('publish 알림 내용 이상: %s' % pubs[0])
        ln = cL.request.get(URL + 'api/notifications?team=' + team).json()['notifications']
        if [n for n in ln if n['type'] == 'publish']: fail('발행자 본인에게 발행 알림이 감')
        # 멤버 홈 배지 + 알림함 + 탭하면 이동·읽음
        pm.goto(URL + '#/home'); pm.reload(); pm.wait_for_selector('.hd'); pm.wait_for_timeout(2000)
        badge = pm.locator('[data-noti-badge]').first
        if badge.inner_text().strip() != '1': fail('사이드바 알림 배지가 1이 아님: %r' % badge.inner_text())
        pm.click('.navi[data-act="inbox"]'); pm.wait_for_selector('#modal .nrow.unread', timeout=5000)
        if '콘티 v1' not in pm.locator('#modal').inner_text(): fail('알림함에 발행 알림 없음')
        pm.click('#modal .nrow'); pm.wait_for_timeout(1500)
        if not pm.evaluate('location.hash').startswith('#view/') and '/view/' not in pm.evaluate('location.hash'): fail('알림 탭 후 콘티 보기로 안 감: ' + pm.evaluate('location.hash'))
        if cM.request.get(URL + 'api/notifications?team=' + team).json()['unread'] != 0: fail('탭 후 읽음 처리 안 됨')
        print('publish notification ok')

        # ---- 날짜 열기 → date.opened 카드(홈) → 확인 → 사라짐 ----
        d = (datetime.date.today() + datetime.timedelta(days=10)).isoformat()
        rr = cL.request.post(URL + 'api/teams/%s/dates' % team, headers=H, data={'date': d, 'label': '가을 수련회 저녁집회', 'time': '19:30'})
        if rr.status != 200: fail('날짜 열기 실패: ' + rr.text()[:100])
        pm.goto(URL + '#/home'); pm.reload(); pm.wait_for_selector('.hd'); pm.wait_for_timeout(2000)
        pm.wait_for_selector('.todo-card', timeout=8000)
        if '일정이 열렸어요' not in pm.locator('.todo').inner_text(): fail('홈 카드에 date.opened 없음: ' + pm.locator('.todo').inner_text())
        # §1.5 date.opened 카드는 '달력 열기' → 답하면 카드가 사라진다
        pm.click('.todo-card [data-act="noti-go"]'); pm.wait_for_selector('.cal-cell.on', timeout=15000)
        pm.locator('[data-cal="%s"]' % d).click(); pm.wait_for_timeout(1200)
        pm.goto(URL + '#/home'); pm.reload(); pm.wait_for_selector('.hd', timeout=10000); pm.wait_for_timeout(2500)
        if '일정이 열렸어요' in pm.locator('#app').inner_text(): fail('답했는데도 카드가 남음')
        print('date.opened card ok')

        # ---- 정기 예배 등록 → 콘티 자동 생성(초안) → 인도자 홈 카드 ----
        wd = (datetime.date.today() + datetime.timedelta(days=3)).weekday(); wd_js = (wd + 1) % 7   # python: 월=0 → js: 일=0
        rr = cL.request.post(URL + 'api/teams/%s/recurring' % team, headers=H, data={'weekday': wd_js, 'label': '주일 2부', 'time': '11:00'})
        if rr.status != 200: fail('정기 예배 등록 실패: ' + rr.text()[:100])
        drafts = cL.request.get(URL + 'api/services?team=' + team).json()['drafts']
        if not drafts: fail('자동 생성 초안이 없음')
        pl.goto(URL + '#/home'); pl.wait_for_selector('.hd'); pl.evaluate('CONTI.SYNC.pullServices().then(()=>CONTI.render())'); pl.wait_for_timeout(2500)
        autos = pl.evaluate("CONTI.S.services.filter(s=>/주일 2부/.test(s.name)&&!s.items.length).map(s=>s.name)")
        if not autos: fail('자동 생성 콘티가 인도자 기기에 없음: %s' % pl.evaluate("CONTI.S.services.map(s=>s.name)"))
        if not re.match(r'^\d+/\d+ 주일 2부$', autos[0]): fail('자동 생성 이름이 규칙과 다름: %s' % autos[0])
        if '콘티가 비어 있어요' not in pl.locator('#app').inner_text(): fail('인도자 홈에 "콘티가 비어 있어요" 카드 없음')
        print('auto-create ok:', autos)

        # ---- 라이브러리 중복 합치기 ----
        pl.evaluate("CONTI.S.library.push({id:'d1',title:'주 은혜임을',key:'G',pieces:[],media:[],form:'',songNote:''},{id:'d2',title:'주 은혜임을 (G)',key:'G',pieces:[{}],media:[],form:'A-B',songNote:''});CONTI.save()")
        pl.click('.navi[data-act="nav-lib"]'); pl.wait_for_selector('#libMerge', timeout=5000); pl.click('#libMerge'); pl.wait_for_timeout(600)
        lib = pl.evaluate("CONTI.S.library.filter(s=>/주 은혜임을/.test(s.title))")
        if len(lib) != 1 or lib[0]['id'] != 'd2': fail('중복 합치기 결과 이상: %s' % lib)
        pl.keyboard.press('Escape'); print('library merge ok')

        # ---- 가져오기: 같은 이름·날짜 → 합치기 ----
        pl.goto(URL + '#/home'); pl.wait_for_selector('.hd')
        n0 = pl.evaluate('CONTI.S.services.length')
        inc = {'app': 'conti', 'v': 1, 'at': 1, 'services': [{'id': 'other1', 'name': svc['name'], 'date': svc['date'], 'notice': '', 'version': 0, 'items': [{'id': 'i9', 'title': '둘째 곡', 'key': 'D', 'mod': '', 'form': '', 'songNote': '', 'pieces': [], 'media': [], 'notes': []}], 'published': None}], 'library': [], 'blobs': {}}
        pl.evaluate("CONTI.importJSON(new Blob([%s],{type:'application/json'}))" % json.dumps(json.dumps(inc, ensure_ascii=False))); pl.wait_for_timeout(1200)
        if pl.evaluate('CONTI.S.services.length') != n0: fail('병합 대신 따로 추가됨')
        titles = pl.evaluate("CONTI.S.services.find(s=>s.id===%s).items.map(i=>i.title)" % json.dumps(svc['id']))
        if titles != ['첫 곡', '둘째 곡']: fail('병합 결과 이상: %s' % titles)
        print('import merge ok')

        print('errors:', errs)
        if errs: fail('page errors')
        b.close()
    print('NOTI TEST OK')

if __name__ == '__main__':
    run()
