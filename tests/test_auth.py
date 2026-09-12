# 로그인 · 팀 만들기 · 초대 가입 · 권한 (온라인 모드)
# 준비: DATABASE_URL, AUTH_SECRET 설정 후  npm run dev  (기본 http://localhost:8766)
import os, sys, time, json
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
tag = str(int(time.time()))[-6:]
LEADER = ('lead' + tag, 'secret1', '하은')
MEMBER = ('mem' + tag, 'secret1', '민수')

def fail(msg):
    print('FAIL:', msg); sys.exit(1)

def login_or_signup(pg, user, mode):
    pg.goto(URL); pg.wait_for_selector('#lgUser', timeout=8000)
    if mode == 'signup':
        pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName')
        pg.fill('#lgName', user[2])
    pg.fill('#lgUser', user[0]); pg.fill('#lgPass', user[1]); pg.click('[data-act="lg-submit"]')
    pg.wait_for_timeout(700)

def open_sect(pg, key):
    if not pg.locator(f'.tsec[data-sect="{key}"].on').count():
        pg.click(f'[data-sopen="{key}"]'); pg.wait_for_timeout(250)

def run():
    with sync_playwright() as p:
        b = p.chromium.launch()
        errs = []
        # ---- 인도자: 가입 → 팀 만들기 ----
        c1 = b.new_context(viewport={'width': 1180, 'height': 820}); pg = c1.new_page()
        pg.on('pageerror', lambda e: errs.append(str(e)))
        login_or_signup(pg, LEADER, 'signup')
        pg.wait_for_selector('#gtTeam', timeout=8000)                       # 팀 없음 → 팀 만들기 화면
        pg.fill('#gtTeam', 'LIKE 찬양팀'); pg.click('#gtSess .q:has-text("인도자")'); pg.click('[data-act="team-create"]')
        pg.wait_for_selector('.shell[data-page]', timeout=8000)            # 홈 셸
        # 이름·역할은 헤더가 아니라 사이드바 아래 프로필 카드에 있다 (§6.1)
        prof = pg.locator('.side .prof').inner_text()
        if '하은' not in prof or '인도자' not in prof: fail('사이드바 프로필에 이름/역할 없음: ' + prof)
        pg.screenshot(path='t_auth_home.png')
        # 초대 링크
        pg.click('.navi[data-act="team"]'); pg.wait_for_selector('.tpage', timeout=8000)
        open_sect(pg, 'invites')
        link = pg.evaluate("location.origin+location.pathname+'#/join/'+CONTI.S.team.invite")
        if '#/join/' not in link: fail('초대 링크 없음: ' + link)
        if not pg.locator('.tsec[data-sect="invites"]').count(): fail('인도자에게 초대 링크 섹션이 없음')
        open_sect(pg, 'members')
        n_members = pg.locator('#tmMembers .mrow').count()
        pg.screenshot(path='t_auth_team.png'); pg.go_back(); pg.wait_for_timeout(400)
        print('leader ok, invite:', link, 'members:', n_members)

        # ---- 멤버: 초대 링크 열기 → 로그인 필요 → 가입 → 팀 가입 ----
        c2 = b.new_context(viewport={'width': 430, 'height': 900}); pm = c2.new_page()
        pm.on('pageerror', lambda e: errs.append(str(e)))
        pm.goto(link); pm.wait_for_selector('#lgUser', timeout=8000)
        pm.click('[data-act="lg-mode"][data-m="signup"]'); pm.wait_for_selector('#lgName')
        pm.fill('#lgName', MEMBER[2]); pm.fill('#lgUser', MEMBER[0]); pm.fill('#lgPass', MEMBER[1]); pm.click('[data-act="lg-submit"]')
        pm.wait_for_selector('#jnName', timeout=8000)                       # 로그인 후 초대 화면으로 이어짐
        if 'LIKE 찬양팀' not in pm.locator('.auth').inner_text(): fail('초대 화면에 팀 이름 없음')
        pm.click('#gtSess .q:has-text("드럼")'); pm.click('[data-act="team-join"]')
        pm.wait_for_selector('.shell[data-page]', timeout=8000)
        who = pm.evaluate("(()=>{const m=CONTI.S.team.me||{};return [m.name,m.session,m.role].join(' ')})()")
        if '민수' not in who or '드럼' not in who or 'member' not in who: fail('멤버 정보 이상: ' + who)
        if pm.locator('[data-act="new-svc"]').count(): fail('멤버에게 새 예배 버튼이 보임')
        pm.screenshot(path='t_auth_member.png')
        # 멤버가 편집 주소로 직접 접근 → 보기로 튕김
        pm.evaluate("CONTI.S.services.push({id:'svc1',name:'테스트',date:'2026-11-21',notice:'',version:0,items:[],published:null});CONTI.save()")
        pm.goto(URL + '#/edit/svc1'); pm.wait_for_timeout(600)
        if not pm.url.replace('#/', '#').endswith('#view/svc1'): fail('멤버 편집 가드 실패: ' + pm.url)
        # 멤버가 팀 모달을 열면 초대 링크는 없고 멤버 목록만
        # 이 멤버 창은 폰 폭(430)이라 사이드바가 없다 (§7) — 주소로 간다
        pm.goto(URL + '#/team'); pm.wait_for_selector('.tpage', timeout=8000)
        if pm.locator('.tsec[data-sect="invites"]').count(): fail('멤버에게 초대 링크 섹션이 보임')
        if pm.locator('.tsec[data-sect="sessions"]').count(): fail('멤버에게 세션 편집이 보임')
        open_sect(pm, 'members')
        if pm.locator('#tmMembers .mrow').count() != n_members + 1: fail('멤버 수 불일치')
        if pm.locator('[data-medit]').count(): fail('멤버에게 고치기 버튼이 보임')
        pm.goto(URL + '#/home'); pm.wait_for_timeout(400)
        # 설정: 이름·세션 변경이 서버에 반영
        pm.goto(URL + '#/settings'); pm.wait_for_selector('.setpane', timeout=8000); pm.wait_for_selector('#sName')
        if pm.locator('#sRole').count(): fail('온라인 모드에서 역할 토글이 보임')
        pm.fill('#sName', '민수2'); pm.click('#sSess .q:has-text("베이스")'); pm.click('#sOk'); pm.wait_for_timeout(600)
        pm.reload(); pm.wait_for_selector('.hd', timeout=8000); pm.wait_for_timeout(500)
        who = pm.evaluate("(()=>{const m=CONTI.S.team.me||{};return [m.name,m.session].join(' ')})()")
        if '민수2' not in who or '베이스' not in who: fail('설정 변경이 서버에 반영되지 않음: ' + who)
        print('member ok')

        # ---- 인도자: 멤버 역할을 세션리더로 → 멤버 쪽 재로그인 시 반영 ----
        pg.click('.navi[data-act="team"]'); pg.wait_for_selector('.tpage', timeout=8000)
        open_sect(pg, 'members')
        uid = pg.evaluate("CONTI.TM.data.members.find(m=>m.name==='민수2').userId")
        pg.click(f'[data-medit="{uid}"]'); pg.wait_for_selector('#meOk', timeout=5000)
        pg.click('[data-mr="session_lead"]'); pg.click('#meOk'); pg.wait_for_timeout(1500)
        pg.goto(URL + '#/home'); pg.wait_for_timeout(400)
        pm.reload(); pm.wait_for_selector('.hd', timeout=8000); pm.wait_for_timeout(500)
        role = pm.evaluate("(()=>{const m=CONTI.S.team.me||{};return m.role})()")
        if role != 'session_lead': fail('역할 변경 미반영: ' + str(role))
        print('role ok')

        # ---- 로그아웃 → 로그인 화면, 잘못된 비밀번호 → 오류 문구 ----
        pm.goto(URL + '#/settings'); pm.wait_for_selector('.setpane', timeout=8000); pm.click('[data-act="set-tab"][data-t="app"]'); pm.wait_for_selector('#sLogout')
        # 로그아웃은 한 번 더 묻는다 (받아 둔 콘티·악보가 같이 지워지므로)
        cancelled = []
        pm.once('dialog', lambda d: (cancelled.append(d.message), d.dismiss()))
        pm.click('#sLogout'); pm.wait_for_timeout(500)
        if not cancelled: fail('로그아웃 확인 창이 안 뜸')
        if pm.locator('#lgUser').count(): fail('취소했는데도 로그아웃됨')
        pm.once('dialog', lambda d: d.accept())
        pm.click('#sLogout'); pm.wait_for_selector('#lgUser', timeout=8000)
        print('logout confirm ok')
        pm.fill('#lgUser', MEMBER[0]); pm.fill('#lgPass', 'wrong!'); pm.click('[data-act="lg-submit"]'); pm.wait_for_timeout(600)
        if '맞지 않아요' not in pm.locator('#lgErr').inner_text(): fail('잘못된 비밀번호 안내 없음')
        login_or_signup(pm, MEMBER, 'login'); pm.wait_for_selector('.shell[data-page]', timeout=8000)
        print('logout/login ok')

        # ---- 세션 쿠키 없이 API 직접 호출 → 401 ----
        r = c2.request.get(URL + 'api/me', headers={'cookie': ''})
        if r.status != 401: fail('쿠키 없는 /api/me 가 %d' % r.status)
        print('errors:', errs)
        if errs: fail('page errors')
        b.close()
    print('AUTH TEST OK')

if __name__ == '__main__':
    run()
