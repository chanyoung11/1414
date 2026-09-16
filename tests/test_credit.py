# 크레딧형 코드 인식 (명세서 §7 인수 기준)
#  1. 악보를 올려도 인식이 자동으로 돌지 않는다
#  2. 무료는 누를 때 확인 창이 뜨고, 남은 곡이 1 줄어 보인다
#  3. 상단 바에 크레딧 알약과 상태 줄이 보인다
# ENFORCE_PLAN=1 일 때만 의미가 있으므로 꺼져 있으면 건너뛴다
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
    L.fill('#lgName', '하은'); L.fill('#lgUser', 'cr' + tag); L.fill('#lgPass', 'secret1')
    L.click('[data-act="lg-submit"]')
    L.wait_for_selector('#gtTeam', timeout=8000); L.fill('#gtTeam', '크레딧팀'); L.click('[data-act="team-create"]')
    L.wait_for_selector('.shell[data-page]', timeout=8000)

    L.click('[data-act="new-svc"]'); L.wait_for_selector('[data-f="svc.name"]')
    L.fill('[data-f="svc.name"]', '크레딧 시험')
    L.click('[data-act="add-item"]'); L.wait_for_selector('[data-f="item.title"]')
    L.fill('[data-f="item.title"]', '시험곡'); L.wait_for_timeout(400)
    L.set_input_files('#pieceFile', ['docs/sample_sheet.jpg']); L.wait_for_timeout(5000)

    # 1. 자동 인식이 돌지 않는다
    st = L.evaluate("CONTI.S.services[0].items[0].pieces[0].ocr")
    if st: fail('악보를 올렸는데 인식이 자동으로 돌았다: %r' % st)

    bar = L.locator('.chordbar').first.inner_text()
    if '아직 인식 안 함' not in bar: fail('상태 줄이 "아직 인식 안 함"이 아님: ' + bar[:120])
    if not L.locator('.chordbar [data-act="ocr"]').count(): fail('코드 인식 버튼이 없음')

    enforced = L.evaluate("CONTI.NET.enforcePlan")
    if not enforced:
      print('SKIP(한도) — ENFORCE_PLAN 이 꺼져 있어 크레딧 표시는 확인하지 않음')
      if errs: fail('콘솔 오류: ' + errs[0])
      print('OK — 자동 인식 없음까지 확인'); b.close(); return

    # 2. 크레딧 알약
    if '코드 인식 10/10' not in bar: fail('크레딧 알약이 10/10 이 아님: ' + bar[:160])

    # 3. 확인 창
    L.click('.chordbar [data-act="ocr"]'); L.wait_for_timeout(1200)
    md = L.locator('#modal').inner_text()
    if '코드 인식' not in md or '이번 달 남은 곡' not in md: fail('확인 창이 안 뜸: ' + md[:140])
    if '다음부터 묻지 않기' not in md: fail('"다음부터 묻지 않기"가 없음')
    L.click('#modal [data-act="close"]'); L.wait_for_timeout(600)
    if L.evaluate("CONTI.S.services[0].items[0].pieces[0].ocr"): fail('취소했는데 인식이 돌았다')

    if errs: fail('콘솔 오류: ' + errs[0])
    print('OK — 자동 인식 없음 · 크레딧 알약 · 확인 창 · 취소')
    b.close()

run()
