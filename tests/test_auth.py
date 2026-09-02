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
        pg.wait_for_selector('.hd [data-act="team"]', timeout=8000)            # 홈: 팀 버튼
        head = pg.locator('.hd').inner_text()
        if '하은' not in head or '인도자' not in head: fail('홈 헤더에 이름/역할 없음: ' + head)
        pg.screenshot(path='t_auth_home.png')
        # 초대 링크
        pg.click('.hd [data-act="team"]'); pg.wait_for_selector('#tmLink', timeout=8000)
        link = pg.locator('#tmLink').inner_text().strip()
        if '#/join/' not in link: fail('초대 링크 없음: ' + link)
        n_members = pg.locator('#tmList .mrow').count()
        pg.screenshot(path='t_auth_team.png'); pg.keyboard.press('Escape')
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
        pm.wait_for_selector('.hd [data-act="team"]', timeout=8000)
        head = pm.locator('.hd').inner_text()
        if '민수' not in head or '드럼' not in head or '멤버' not in head: fail('멤버 헤더 이상: ' + head)
        if pm.locator('[data-act="new-svc"]').count(): fail('멤버에게 새 예배 버튼이 보임')
        pm.screenshot(path='t_auth_member.png')
        # 멤버가 편집 주소로 직접 접근 → 보기로 튕김
        pm.evaluate("CONTI.S.services.push({id:'svc1',name:'테스트',date:'2026-11-21',notice:'',version:0,items:[],published:null});CONTI.save()")
        pm.goto(URL + '#/edit/svc1'); pm.wait_for_timeout(600)
        if not pm.url.replace('#/', '#').endswith('#view/svc1'): fail('멤버 편집 가드 실패: ' + pm.url)
        # 멤버가 팀 모달을 열면 초대 링크는 없고 멤버 목록만
        pm.goto(URL + '#/home'); pm.wait_for_selector('.hd [data-act="team"]'); pm.click('.hd [data-act="team"]'); pm.wait_for_selector('#tmList', timeout=8000)
        if pm.locator('#tmLink').count(): fail('멤버에게 초대 링크가 보임')
        if pm.locator('#tmList .mrow').count() != n_members + 1: fail('멤버 수 불일치')
        pm.keyboard.press('Escape')
        # 설정: 이름·세션 변경이 서버에 반영
        pm.click('.hd [data-act="settings"]'); pm.wait_for_selector('#sName')
        if pm.locator('#sRole').count(): fail('온라인 모드에서 역할 토글이 보임')
        pm.fill('#sName', '민수2'); pm.click('#sSess .q:has-text("베이스")'); pm.click('#sOk'); pm.wait_for_timeout(600)
        pm.reload(); pm.wait_for_selector('.hd', timeout=8000); pm.wait_for_timeout(500)
        head = pm.locator('.hd').inner_text()
        if '민수2' not in head or '베이스' not in head: fail('설정 변경이 서버에 반영되지 않음: ' + head)
        print('member ok')

        # ---- 인도자: 멤버 역할을 세션리더로 → 멤버 쪽 재로그인 시 반영 ----
        pg.click('.hd [data-act="team"]'); pg.wait_for_selector('#tmList select', timeout=8000)
        sel = pg.locator('#tmList .mrow').filter(has_text='민수2').locator('select')
        sel.select_option('session_lead'); pg.wait_for_timeout(500); pg.keyboard.press('Escape')
        pm.reload(); pm.wait_for_selector('.hd', timeout=8000); pm.wait_for_timeout(500)
        if '세션리더' not in pm.locator('.hd').inner_text(): fail('역할 변경 미반영: ' + pm.locator('.hd').inner_text())
        print('role ok')

        # ---- 로그아웃 → 로그인 화면, 잘못된 비밀번호 → 오류 문구 ----
        pm.click('.hd [data-act="settings"]'); pm.wait_for_selector('#sLogout'); pm.click('#sLogout'); pm.wait_for_selector('#lgUser', timeout=8000)
        pm.fill('#lgUser', MEMBER[0]); pm.fill('#lgPass', 'wrong!'); pm.click('[data-act="lg-submit"]'); pm.wait_for_timeout(600)
        if '맞지 않아요' not in pm.locator('#lgErr').inner_text(): fail('잘못된 비밀번호 안내 없음')
        login_or_signup(pm, MEMBER, 'login'); pm.wait_for_selector('.hd [data-act="team"]', timeout=8000)
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
