# 팀 화면 (명세 B부): 초대 링크 · 멤버 고치기 · 비활성 · 인도자 넘기기 · 세션 이름 연쇄 · 팀 삭제
import os, sys, time
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
tag = str(int(time.time()))[-6:]
def fail(m): print('FAIL:', m); sys.exit(1)

def signup(pg, user, name):
    pg.goto(URL); pg.wait_for_selector('#lgUser', timeout=8000)
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName')
    pg.fill('#lgName', name); pg.fill('#lgUser', user); pg.fill('#lgPass', 'secret1')
    pg.click('[data-act="lg-submit"]')

def open_sect(pg, key):
    if not pg.locator(f'.tsec[data-sect="{key}"].on').count():
        pg.click(f'[data-sopen="{key}"]'); pg.wait_for_timeout(250)

def run():
  with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    c1 = b.new_context(viewport={'width': 1300, 'height': 950}); L = c1.new_page()
    L.on('pageerror', lambda e: errs.append('leader: ' + str(e))); L.on('dialog', lambda d: d.accept())

    # ---- 인도자: 팀 만들기 ----
    signup(L, 'tl' + tag, '하은')
    L.wait_for_selector('#gtTeam', timeout=8000); L.fill('#gtTeam', '팀테스트'); L.click('[data-act="team-create"]')
    L.wait_for_selector('.hd [data-act="team"]', timeout=8000)
    L.click('.hd [data-act="team"]'); L.wait_for_selector('.tpage', timeout=8000)
    if '팀테스트' not in L.locator('.top h1').inner_text(): fail('팀 화면 제목이 틀림')
    print('team page ok')

    # ---- 초대 링크: 역할·1회용 ----
    open_sect(L, 'invites')
    n0 = L.locator('#modal').count()
    L.click('.tsec[data-sect="invites"] [data-act="tm-invite"]'); L.wait_for_selector('[data-ir]', timeout=5000)
    L.click('[data-ir="session_lead"]'); L.click('[data-id2="7"]'); L.click('[data-iu="1"]')
    L.click('#ivOk'); L.wait_for_timeout(1200)
    inv = L.evaluate("CONTI.TM.invites")
    made = [x for x in inv if x['role'] == 'session_lead']
    if not made: fail('세션리더 링크가 안 만들어짐: %s' % inv)
    if made[0]['maxUses'] != 1: fail('1회용이 아님: %s' % made[0])
    code = made[0]['code']
    print('invite made:', made[0]['role'], made[0]['maxUses'])
    # 옛 링크가 살아 있는지 (이행 확인)
    if len(inv) < 2: fail('팀 만들 때의 기본 링크가 안 보임: %s' % inv)

    # ---- 멤버가 그 링크로 들어옴 → 세션리더가 된다 ----
    c2 = b.new_context(viewport={'width': 430, 'height': 900}); M = c2.new_page()
    M.on('pageerror', lambda e: errs.append('member: ' + str(e))); M.on('dialog', lambda d: d.accept())
    signup(M, 'tm' + tag, '지우')
    M.wait_for_selector('#gtTeam', timeout=8000)
    M.goto(URL + '#/join/' + code); M.wait_for_selector('#jnName', timeout=8000)
    M.fill("#jnName", "지우"); M.click("[data-act=\"team-join\"]")
    M.wait_for_selector('.hd [data-act="team"]', timeout=10000)
    role = M.evaluate("CONTI.S.team.role||(CONTI.S.members&&CONTI.S.members[0])")
    print('member joined')

    # ---- 1회용 링크는 두 번 못 쓴다 ----
    c3 = b.new_context(); X = c3.new_page(); X.on('dialog', lambda d: d.accept())
    signup(X, 'tx' + tag, '한나'); X.wait_for_selector('#gtTeam', timeout=8000)
    X.goto(URL + '#/join/' + code); X.wait_for_timeout(1500)
    body = X.locator('#app').inner_text()
    if '다 쓰였' not in body and '쓸 수 없' not in body: fail('1회용 링크가 재사용됨:\n' + body[:300])
    print('one-shot invite ok')
    c3.close()

    # ---- 인도자 화면에서 멤버 확인 · 역할 · 비활성 ----
    L.reload(); L.wait_for_selector('.tpage', timeout=10000)
    open_sect(L, 'members')
    mem = [m for m in L.evaluate("CONTI.TM.data.members") if m['name'] == '지우']
    if not mem: fail('멤버 목록에 지우가 없음')
    if mem[0]['role'] != 'session_lead': fail('초대 역할이 안 붙음: %s' % mem[0]['role'])
    uid = mem[0]['userId']
    print('member role ok:', mem[0]['role'])

    L.click(f'[data-mmore="{uid}"]'); L.wait_for_selector('#mmOff', timeout=5000)
    L.click('#mmOff'); L.wait_for_timeout(1500)
    mem = [m for m in L.evaluate("CONTI.TM.data.members") if m['userId'] == uid][0]
    if mem['active'] is not False: fail('비활성이 안 됨: %s' % mem)
    print('deactivate ok')
    # 비활성 멤버는 팀에 못 들어온다
    M.reload(); M.wait_for_timeout(3000)
    mbody = M.locator('#app').inner_text()
    if '들어갈 수 없' not in mbody: fail('비활성 멤버에게 안내가 안 보임:\n' + mbody[:300])
    print('blocked screen ok')
    # 되돌리기
    L.click(f'[data-mmore="{uid}"]'); L.wait_for_selector('#mmOn', timeout=5000)
    L.click('#mmOn'); L.wait_for_timeout(1500)
    if L.evaluate(f"CONTI.TM.data.members.find(m=>m.userId==='{uid}').active") is not True: fail('다시 활성이 안 됨')
    print('reactivate ok')

    # ---- 세션 이름 바꾸기 연쇄 ----
    open_sect(L, 'sessions')
    L.fill('[data-sname="0"]', '드럼셋')
    L.click('[data-act="tm-sess-save"]'); L.wait_for_timeout(2000)
    ss = L.evaluate("CONTI.S.team.sessions")
    if ss[0] != '드럼셋': fail('세션 이름이 안 바뀜: %s' % ss)
    print('session rename ok:', ss[0])

    # ---- 인도자 넘기기 ----
    open_sect(L, 'team')
    L.click('[data-act="tm-transfer"]'); L.wait_for_selector('[data-tu]', timeout=5000)
    L.click(f'[data-tu="{uid}"]'); L.click('#trOk'); L.wait_for_timeout(2500)
    who = L.evaluate("CONTI.TM.data.members.map(m=>[m.name,m.role])")
    d = dict((n, r) for n, r in who)
    if d.get('지우') != 'leader': fail('넘기기 실패: %s' % who)
    if d.get('하은') != 'session_lead': fail('옛 인도자가 세션 리더가 안 됨: %s' % who)
    print('transfer ok:', who)

    # ---- 넘겨받은 사람이 팀 삭제 예약 → 취소 ----
    M.reload(); M.wait_for_timeout(2500)
    M.goto(URL + '#/team'); M.wait_for_selector('.tpage', timeout=10000)
    open_sect(M, 'team')
    M.evaluate("window.prompt=()=>'팀테스트'")
    M.click('[data-act="tm-delete"]'); M.wait_for_timeout(2000)
    if not M.evaluate("CONTI.TM.data.deletedAt"): fail('팀 삭제 예약이 안 됨')
    M.click('[data-act="team-undelete"]'); M.wait_for_timeout(2000)
    if M.evaluate("CONTI.TM.data.deletedAt"): fail('삭제 취소가 안 됨')
    print('team delete/undelete ok')

    if errs: fail('페이지 오류:\n' + '\n'.join(errs[:6]))
    print('PASS test_team')
    b.close()

run()
