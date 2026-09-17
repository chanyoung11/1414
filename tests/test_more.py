# 폰 하단 「더보기」 시트의 항목이 실제로 눌리는지 (시트 안 버튼은 전역 클릭이 무시해서 죽어 있었다)
import sys, time
from playwright.sync_api import sync_playwright
URL='http://localhost:8766/'
def fail(m): print('FAIL:', m); sys.exit(1)
def run():
  tag=str(int(time.time()))[-6:]
  with sync_playwright() as p:
    b=p.chromium.launch(); c=b.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True); pg=c.new_page(); pg.on('dialog',lambda d:d.accept())
    errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)[:120]))
    pg.goto(URL); pg.wait_for_selector('#lgUser')
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName'); pg.check('#lgAgree')
    pg.fill('#lgName','더보기'); pg.fill('#lgUser','mo'+tag); pg.fill('#lgPass','secret1'); pg.click('[data-act="lg-submit"]')
    pg.wait_for_selector('#gtTeam'); pg.fill('#gtTeam','팀'); pg.click('#gtSess .q:has-text("건반")'); pg.click('[data-act="team-create"]')
    pg.wait_for_selector('.shell[data-page]',timeout=10000); pg.wait_for_timeout(800)
    for act,page in [('settings','settings'),('team','team'),('sched','sched'),('word','word')]:
      pg.click('.bnav [data-act="more-menu"]'); pg.wait_for_selector('.morelist',timeout=3000)
      pg.click('.morelist [data-act="%s"]'%act); pg.wait_for_timeout(700)
      if pg.locator('.morelist').count(): fail('%s 눌렀는데 시트가 안 닫힘'%act)
      got=pg.evaluate("location.hash")
      if page not in got: fail('%s 눌렀는데 이동 안 함: %s'%(act,got))
      print(act,'→',got,'ok')
    if errs: fail('콘솔 오류: %s'%errs[:2])
    b.close()
  print('OK — 더보기 4항목 전부 눌림')
run()
