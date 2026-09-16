# 프로모션 코드: 코드를 넣으면 그 팀이 일정 기간 유료가 된다
#  - 인도자만 쓸 수 있다
#  - 같은 팀이 같은 코드를 두 번 못 쓴다
#  - 한도가 유료 기준으로 바뀐다
import os, sys, time, json
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
CODE = os.environ.get('PROMO_CODE', 'TEST30')
tag = str(int(time.time()))[-6:]
def fail(m): print('FAIL:', m); sys.exit(1)

def run():
  with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    ctx = b.new_context(viewport={'width': 1300, 'height': 950}); L = ctx.new_page()
    L.on('pageerror', lambda e: errs.append(str(e))); L.on('dialog', lambda d: d.accept())
    L.goto(URL); L.wait_for_selector('#lgUser', timeout=8000)
    L.click('[data-act="lg-mode"][data-m="signup"]'); L.wait_for_selector('#lgName'); L.check('#lgAgree')
    L.fill('#lgName', '하은'); L.fill('#lgUser', 'pr' + tag); L.fill('#lgPass', 'secret1')
    L.click('[data-act="lg-submit"]')
    L.wait_for_selector('#gtTeam', timeout=8000); L.fill('#gtTeam', '코드팀'); L.click('[data-act="team-create"]')
    L.wait_for_selector('.shell[data-page]', timeout=8000)

    if not L.evaluate("CONTI.NET.enforcePlan"):
      print('SKIP — ENFORCE_PLAN 이 꺼져 있음'); b.close(); return

    L.evaluate("()=>location.hash='#/settings'"); L.wait_for_timeout(1500)
    L.click('[data-act="set-tab"][data-t="plan"]'); L.wait_for_timeout(2500)
    card = L.locator('#app .card').first.inner_text()
    if '0/10곡' not in card: fail('무료 한도가 안 보임: ' + card.replace('\n', ' ')[:140])

    L.fill('#sPromo', CODE); L.wait_for_timeout(300)
    L.click('#sPromoGo'); L.wait_for_timeout(4500)
    if L.evaluate("CONTI.S.team.plan") != 'pro': fail('코드를 넣었는데 Pro 가 안 됨')
    if not L.evaluate("CONTI.S.team.planUntil"): fail('만료 날짜가 안 내려옴')

    L.click('[data-act="set-tab"][data-t="plan"]'); L.wait_for_timeout(2000)
    card2 = L.locator('#app .card').first.inner_text()
    if '0/100곡' not in card2: fail('Pro 한도로 안 바뀜: ' + card2.replace('\n', ' ')[:140])

    # 같은 코드를 두 번 쓰면 막힌다
    L.fill('#sPromo', CODE); L.wait_for_timeout(300)
    L.click('#sPromoGo'); L.wait_for_timeout(3000)
    msg = L.locator('#sPromoMsg').inner_text()
    if '이미' not in msg: fail('같은 코드를 두 번 쓸 수 있음: ' + msg[:80])

    if errs: fail('콘솔 오류: ' + errs[0])
    print('OK — 코드 적용 · 한도 상승 · 재사용 차단')
    b.close()

run()
