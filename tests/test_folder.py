# 예배 폴더: 인도자가 정한 폴더로 목록을 거를 수 있고, 발행하면 팀원에게도 내려간다
import os, sys, time
from playwright.sync_api import sync_playwright
URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
tag = str(int(time.time()))[-6:]
def fail(m): print('FAIL:', m); sys.exit(1)

def run():
  with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    cL = b.new_context(viewport={'width': 1300, 'height': 950}); L = cL.new_page()
    L.on('pageerror', lambda e: errs.append('L:' + str(e))); L.on('dialog', lambda d: d.accept())
    L.goto(URL); L.wait_for_selector('#lgUser', timeout=8000)
    L.click('[data-act="lg-mode"][data-m="signup"]'); L.wait_for_selector('#lgName'); L.check('#lgAgree')
    L.fill('#lgName', '하은'); L.fill('#lgUser', 'fd' + tag); L.fill('#lgPass', 'secret1')
    L.click('[data-act="lg-submit"]')
    L.wait_for_selector('#gtTeam', timeout=8000); L.fill('#gtTeam', '폴더팀'); L.click('[data-act="team-create"]')
    L.wait_for_selector('.shell[data-page]', timeout=8000)
    link = L.evaluate("location.origin+location.pathname+'#/join/'+CONTI.S.team.invite")

    # 폴더가 있는 예배와 없는 예배
    for name, folder in [('상반기 예배', '2026 상반기'), ('그냥 예배', '')]:
      L.evaluate("()=>location.hash='#/home'"); L.wait_for_timeout(800)
      L.click('[data-act="new-svc"]'); L.wait_for_selector('[data-f="svc.name"]')
      L.fill('[data-f="svc.name"]', name)
      if folder: L.fill('[data-f="svc.folder"]', folder)
      L.click('[data-act="add-item"]'); L.wait_for_selector('[data-f="item.title"]')
      L.fill('[data-f="item.title"]', '곡'); L.wait_for_timeout(500)
      L.click('[data-act="publish"]'); L.wait_for_selector('#pubOnly', timeout=6000)
      L.click('#pubOnly'); L.wait_for_timeout(3000)

    L.evaluate("()=>location.hash='#/home'"); L.wait_for_timeout(1500)
    chips = L.locator('[data-act="home-folder"]')
    if chips.count() < 3: fail('폴더 칩이 안 보임 (전체/폴더/폴더 없음): %d' % chips.count())
    # 폴더로 거르기
    L.click('[data-act="home-folder"][data-v="2026 상반기"]'); L.wait_for_timeout(900)
    rows = L.locator('.svcrow').count()
    if rows != 1: fail('폴더로 걸렀는데 %d개 (1개여야 함)' % rows)
    L.click('[data-act="home-folder"][data-v="__none"]'); L.wait_for_timeout(900)
    if L.locator('.svcrow').count() != 1: fail('"폴더 없음"으로 거르기 실패')
    L.click('[data-act="home-folder"][data-v=""]'); L.wait_for_timeout(900)
    if L.locator('.svcrow').count() != 2: fail('전체로 돌아오지 않음')

    # 팀원에게도 폴더가 내려간다
    cM = b.new_context(viewport={'width': 1300, 'height': 950}); M = cM.new_page()
    M.on('pageerror', lambda e: errs.append('M:' + str(e))); M.on('dialog', lambda d: d.accept())
    M.goto(link); M.wait_for_selector('#lgUser', timeout=8000)
    M.click('[data-act="lg-mode"][data-m="signup"]'); M.wait_for_selector('#lgName'); M.check('#lgAgree')
    M.fill('#lgName', '민수'); M.fill('#lgUser', 'fm' + tag); M.fill('#lgPass', 'secret1')
    M.click('[data-act="lg-submit"]')
    M.wait_for_selector('#jnName', timeout=8000); M.click('[data-act="team-join"]')
    M.wait_for_selector('.shell[data-page]', timeout=10000); M.wait_for_timeout(1500)
    M.wait_for_function("(()=>CONTI.S.services.length>=2)()", timeout=20000)
    got = M.evaluate("CONTI.S.services.map(s=>[s.name,s.folder||''])")
    if not any(x[1] == '2026 상반기' for x in got): fail('팀원에게 폴더가 안 내려감: %s' % got)

    if errs: fail('콘솔 오류: ' + errs[0])
    print('OK — 폴더 거르기 · 팀원 전달')
    b.close()

run()
