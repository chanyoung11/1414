# 연습 화면의 메트로놈·건반
import os, sys, time
from playwright.sync_api import sync_playwright
URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
tag = str(int(time.time()))[-6:]
def fail(m): print('FAIL:', m); sys.exit(1)

def run():
  with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    ctx = b.new_context(viewport={'width': 1300, 'height': 950}); L = ctx.new_page()
    L.on('pageerror', lambda e: errs.append(str(e))); L.on('dialog', lambda d: d.accept())
    L.goto(URL); L.wait_for_selector('#lgUser', timeout=8000)
    L.click('[data-act="lg-mode"][data-m="signup"]'); L.wait_for_selector('#lgName'); L.check('#lgAgree')
    L.fill('#lgName', '하은'); L.fill('#lgUser', 'tl' + tag); L.fill('#lgPass', 'secret1')
    L.click('[data-act="lg-submit"]')
    L.wait_for_selector('#gtTeam', timeout=8000); L.fill('#gtTeam', '도구팀'); L.click('[data-act="team-create"]')
    L.wait_for_selector('.shell[data-page]', timeout=8000)
    L.click('[data-act="new-svc"]'); L.wait_for_selector('[data-f="svc.name"]'); L.fill('[data-f="svc.name"]', '도구')
    L.click('[data-act="add-item"]'); L.wait_for_selector('[data-f="item.title"]')
    L.fill('[data-f="item.title"]', '곡'); L.wait_for_timeout(400)
    svc = L.evaluate('CONTI.S.services[0].id')
    L.click('[data-act="publish"]'); L.wait_for_selector('#pubOnly', timeout=6000)
    L.click('#pubOnly'); L.wait_for_timeout(3000)
    L.evaluate("(id)=>location.hash='#/play/'+id", svc); L.wait_for_timeout(2500)

    if not L.locator('[data-act="metro"]').count(): fail('메트로놈 버튼이 없음')
    if not L.locator('[data-act="piano"]').count(): fail('건반 버튼이 없음')

    # 메트로놈
    L.click('[data-act="metro"]'); L.wait_for_timeout(1000)
    if '메트로놈' not in L.locator('#modal').inner_text(): fail('메트로놈 창이 안 뜸')
    before = L.evaluate('CONTI.MET.bpm')
    L.click('[data-act="met-d"][data-d="5"]'); L.wait_for_timeout(400)
    if L.evaluate('CONTI.MET.bpm') != before + 5: fail('BPM 올리기가 안 됨')
    L.click('#metGo'); L.wait_for_timeout(900)
    if not L.evaluate('CONTI.MET.on'): fail('시작이 안 됨')
    if L.locator('#metGo').inner_text().strip() != '멈춤': fail('버튼 글자가 안 바뀜')
    L.click('#metGo'); L.wait_for_timeout(700)
    if L.evaluate('CONTI.MET.on'): fail('멈춤이 안 됨')
    # 박자 바꾸기
    L.click('[data-act="met-beats"][data-n="3"]'); L.wait_for_timeout(400)
    if L.evaluate('CONTI.MET.beats') != 3: fail('박자가 안 바뀜')
    L.keyboard.press('Escape'); L.wait_for_timeout(600)

    # 건반
    L.click('[data-act="piano"]'); L.wait_for_timeout(1000)
    if L.locator('#pkeys .pk.w').count() != 7: fail('흰 건반이 7개가 아님')
    if L.locator('#pkeys .pk.b').count() != 5: fail('검은 건반이 5개가 아님')
    o = L.evaluate('CONTI.PIANO.oct')
    L.click('[data-act="oct"][data-d="1"]'); L.wait_for_timeout(400)
    if L.evaluate('CONTI.PIANO.oct') != o + 1: fail('옥타브 올리기가 안 됨')

    if errs: fail('콘솔 오류: ' + errs[0])
    print('OK — 메트로놈(BPM·시작/멈춤·박자) · 건반(7+5키·옥타브)')
    b.close()

run()
