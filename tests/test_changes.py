# 발행 시 바뀐 부분이 팀원에게 함께 뜬다
import os, sys, time
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
tag = str(int(time.time()))[-6:]
H = {'x-conti': '1'}
def fail(m): print('FAIL:', m); sys.exit(1)

def run():
  with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    cL = b.new_context(viewport={'width': 1300, 'height': 950}); L = cL.new_page()
    L.on('pageerror', lambda e: errs.append('L:' + str(e))); L.on('dialog', lambda d: d.accept())
    L.goto(URL); L.wait_for_selector('#lgUser', timeout=8000)
    L.click('[data-act="lg-mode"][data-m="signup"]'); L.wait_for_selector('#lgName')
    L.fill('#lgName', '하은'); L.fill('#lgUser', 'cg' + tag); L.fill('#lgPass', 'secret1'); L.click('[data-act="lg-submit"]')
    L.wait_for_selector('#gtTeam', timeout=8000); L.fill('#gtTeam', '변경팀'); L.click('[data-act="team-create"]')
    L.wait_for_selector('.hd [data-act="team"]', timeout=8000)
    link = L.evaluate("location.origin+location.pathname+'#/join/'+CONTI.S.team.invite")

    L.click('[data-act="new-svc"]'); L.wait_for_selector('[data-f="svc.name"]'); L.fill('[data-f="svc.name"]', '변경 예배')
    L.click('[data-act="add-item"]'); L.wait_for_selector('[data-f="item.title"]')
    L.fill('[data-f="item.title"]', '첫째 곡'); L.fill('[data-f="item.key"]', 'G'); L.wait_for_timeout(500)
    svc = L.evaluate('CONTI.S.services[0].id')
    L.click('[data-act="publish"]'); L.wait_for_selector('#pubOnly', timeout=6000); L.click('#pubOnly'); L.wait_for_timeout(3500)
    if L.evaluate("CONTI.S.services[0].published.changes.length"): fail('첫 발행인데 변경 목록이 생김')
    print('v1 ok (변경 목록 없음)')

    # ---- 멤버 가입 ----
    cM = b.new_context(viewport={'width': 430, 'height': 900}); M = cM.new_page()
    M.on('pageerror', lambda e: errs.append('M:' + str(e))); M.on('dialog', lambda d: d.accept())
    M.goto(link); M.wait_for_selector('#lgUser', timeout=8000)
    M.click('[data-act="lg-mode"][data-m="signup"]'); M.wait_for_selector('#lgName')
    M.fill('#lgName', '지우'); M.fill('#lgUser', 'cm' + tag); M.fill('#lgPass', 'secret1'); M.click('[data-act="lg-submit"]')
    M.wait_for_selector('#jnName', timeout=8000); M.click('[data-act="team-join"]')
    M.wait_for_selector('.hd [data-act="team"]', timeout=10000); M.wait_for_timeout(1500)

    # ---- 인도자가 키·순서·곡을 고쳐 v2 발행 ----
    L.goto(URL + '#/edit/' + svc); L.wait_for_selector('[data-f="item.key"]', timeout=10000); L.wait_for_timeout(500)
    L.fill('[data-f="item.key"]', 'A'); L.fill('[data-f="item.form"]', 'Intro – A – B'); L.wait_for_timeout(500)
    L.click('[data-act="add-item"]'); L.wait_for_selector('[data-f="item.title"]')
    L.fill('[data-f="item.title"]', '둘째 곡'); L.wait_for_timeout(500)
    L.fill('[data-f="svc.notice"]', '20분 전 모입니다'); L.wait_for_timeout(500)
    L.click('[data-act="publish"]'); L.wait_for_selector('#pubOnly', timeout=6000); L.click('#pubOnly'); L.wait_for_timeout(4000)
    chg = L.evaluate("CONTI.S.services[0].published.changes.map(c=>c.text)")
    print('changes:', chg)
    joined = ' / '.join(chg)
    for want in ['둘째 곡 추가', '키 G → A', '송폼', '공지']:
        if want not in joined: fail('변경 목록에 %r 이 없음: %s' % (want, chg))

    # ---- 알림 본문에 바뀐 것이 들어간다 ----
    team = M.evaluate("CONTI.S.team.id")
    noti = cM.request.get(URL + 'api/notifications?team=' + team).json()['notifications']
    pubs = [n for n in noti if n['type'] == 'publish']
    if not pubs: fail('발행 알림이 없음')
    if '추가' not in pubs[0]['body'] and '키' not in pubs[0]['body']:
        fail('알림 본문이 변경 요약이 아님: %r' % pubs[0]['body'])
    print('notification ok:', pubs[0]['body'])

    # ---- 멤버 콘티 보기에 "바뀐 것" 카드 ----
    M.evaluate("CONTI.SYNC.pullServices()"); M.wait_for_timeout(2500)
    M.goto(URL + '#/view/' + svc); M.wait_for_selector('.card', timeout=10000); M.wait_for_timeout(1200)
    if not M.locator('.chgcard').count(): fail('바뀐 것 카드가 안 보임')
    txt = M.locator('.chgcard').inner_text()
    if '둘째 곡 추가' not in txt: fail('카드 내용이 이상함:\n' + txt)
    if not M.locator('.chgcard.fresh').count(): fail('새 버전인데 강조가 안 됨')
    print('member card ok')

    # ---- 한 번 보면 강조가 풀린다 ----
    M.click('.chgcard'); M.wait_for_timeout(600)
    if M.locator('.chgcard.fresh').count(): fail('보고 나서도 계속 강조됨')
    M.reload(); M.wait_for_selector('.chgcard', timeout=10000); M.wait_for_timeout(1200)
    if M.locator('.chgcard.fresh').count(): fail('새로고침하니 다시 강조됨')
    print('seen ok')

    if errs: fail('페이지 오류:\n' + '\n'.join(errs[:5]))
    print('PASS test_changes')
    b.close()

run()
