# 라이브러리 폴더: 곡에 폴더를 정하고, 폴더로 거르고, 여러 곡을 한 번에 옮긴다
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
    L.fill('#lgName', '하은'); L.fill('#lgUser', 'lf' + tag); L.fill('#lgPass', 'secret1')
    L.click('[data-act="lg-submit"]')
    L.wait_for_selector('#gtTeam', timeout=8000); L.fill('#gtTeam', '폴더곡팀'); L.click('[data-act="team-create"]')
    L.wait_for_selector('.shell[data-page]', timeout=8000)

    # 곡 세 개를 라이브러리에 만든다
    for t in ['가곡', '나곡', '다곡']:
      L.evaluate("()=>location.hash='#/library'"); L.wait_for_timeout(1200)
      L.click('[data-act="lib-new"]'); L.wait_for_timeout(900)
      L.wait_for_selector('#nsTitle', timeout=8000)
      L.fill('#nsTitle', t); L.wait_for_timeout(400)
      L.locator('#modal .btn.pri').last.click(); L.wait_for_timeout(2500)
    L.evaluate("()=>location.hash='#/library'"); L.wait_for_timeout(1500)
    n = L.evaluate("(CONTI.S.songs||[]).length")
    if n < 3: fail('곡이 안 만들어짐: %d' % n)

    # 두 곡을 골라 폴더로 옮긴다
    L.click('[data-act="lib-multi"]'); L.wait_for_timeout(800)
    rows = L.locator('#libList [data-songpick], #libList .songrow')
    L.evaluate("()=>{CONTI.LIB.sel=(CONTI.S.songs||[]).slice(0,2).map(s=>s.id);CONTI.render()}")
    L.wait_for_timeout(900)
    if not L.locator('[data-act="lib-move"]').count(): fail('"폴더로 옮기기" 버튼이 없음')
    L.click('[data-act="lib-move"]'); L.wait_for_timeout(1000)
    if '폴더로' not in L.locator('#modal').inner_text(): fail('폴더 창이 안 뜸')
    L.fill('#mvNew', '경배와 찬양'); L.click('#mvGo'); L.wait_for_timeout(3000)

    got = L.evaluate("(CONTI.S.songs||[]).map(s=>[s.title,s.folder||''])")
    moved = [x for x in got if x[1] == '경배와 찬양']
    if len(moved) != 2: fail('두 곡이 안 옮겨짐: %s' % got)

    # 폴더 칩으로 거르기
    L.evaluate("()=>location.hash='#/library'"); L.wait_for_timeout(1500)
    chip = L.locator('[data-lf="folder"][data-v="경배와 찬양"]')
    if not chip.count(): fail('폴더 칩이 안 보임')
    chip.click(); L.wait_for_timeout(1000)
    shown = L.evaluate("document.querySelectorAll('#libList > *').length")
    if shown != 2: fail('폴더로 걸렀는데 %d개 (2개여야 함)' % shown)

    # 서버에도 저장됐는지
    srv = L.evaluate("""async()=>{const r=await fetch('/api/songs?team='+CONTI.S.team.id,{headers:{'x-conti':'1'}});
      const j=await r.json();return (j.songs||[]).map(s=>[s.title,s.folder||''])}""")
    if len([x for x in srv if x[1] == '경배와 찬양']) != 2: fail('서버에 폴더가 안 저장됨: %s' % srv)

    if errs: fail('콘솔 오류: ' + errs[0])
    print('OK — 여러 곡 한 번에 폴더로 · 칩으로 거르기 · 서버 저장')
    b.close()

run()
