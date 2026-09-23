# 폰: 가로로 쓸어 옆 탭 · 가장자리 뒤로가 손가락을 따라옴 · 더보기 시트가 올라오고 내려감
#   python tests/test_swipe.py            (움직임 켬)
#   python tests/test_swipe.py reduce     (움직임 줄이기 — 넘어가기만 하고 따라오기·애니메이션 없음)
import os, sys, time
from playwright.sync_api import sync_playwright
URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
def fail(m): print('FAIL:', m); sys.exit(1)
def run(rm):
  tag = str(int(time.time()*10))[-7:]
  with sync_playwright() as p:
    b = p.chromium.launch()
    c = b.new_context(viewport={'width':390,'height':844}, is_mobile=True, has_touch=True, reduced_motion=rm)
    pg = c.new_page(); pg.on('dialog', lambda d: d.accept())
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:160]))
    cdp = c.new_cdp_session(pg)
    def touch(typ, pts):
      cdp.send('Input.dispatchTouchEvent', {'type': typ, 'touchPoints': [{'x': x, 'y': y} for x, y in pts]})
    def swipe(x0, y0, x1, y1, steps=10, dt=16, release=True, mid=None):
      touch('touchStart', [(x0, y0)])
      out = None
      for i in range(1, steps+1):
        touch('touchMove', [(x0+(x1-x0)*i/steps, y0+(y1-y0)*i/steps)]); pg.wait_for_timeout(dt)
        if mid and i == steps: out = pg.evaluate(mid)
      if release: touch('touchEnd', [])
      return out
    H = lambda: pg.evaluate('location.hash')
    pg.goto(URL); pg.wait_for_selector('#lgUser')
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName'); pg.check('#lgAgree')
    pg.fill('#lgName','쓸기'); pg.fill('#lgUser','sw'+tag); pg.fill('#lgPass','secret1'); pg.click('[data-act="lg-submit"]')
    pg.wait_for_selector('#gtTeam'); pg.fill('#gtTeam','팀'); pg.click('#gtSess .q:has-text("건반")'); pg.click('[data-act="team-create"]')
    pg.wait_for_selector('.shell[data-page]', timeout=10000); pg.wait_for_timeout(800)
    acts = pg.evaluate("[...document.querySelectorAll('.bnav button')].map(b=>b.dataset.act)")
    print('tabs', acts)
    TR = "(document.querySelector('#app>.shell')||{style:{}}).style.transform"
    # 1 왼쪽으로 쓸기 → 다음 탭, 손가락을 따라 움직인다
    tr = swipe(300, 500, 120, 505, mid=TR); pg.wait_for_timeout(900)
    print('mid transform', repr(tr))
    if rm == 'no-preference' and 'translate3d(-180px' not in (tr or ''): fail('본문이 손가락을 안 따라감: %r' % tr)
    if rm == 'reduce' and tr: fail('움직임 줄이기인데 따라감: %r' % tr)
    if 'cal' not in H(): fail('왼쪽으로 쓸었는데 일정으로 안 감: %s' % H())
    if pg.evaluate(TR): fail('넘어간 뒤 transform 이 남음')
    print('1 home→cal ok')
    swipe(300, 500, 120, 500); pg.wait_for_timeout(900)
    if 'sched' not in H(): fail('cal→sched 안 됨: %s' % H())
    swipe(100, 500, 300, 500); pg.wait_for_timeout(900)
    if 'cal' not in H(): fail('오른쪽으로 쓸었는데 이전 탭으로 안 감: %s' % H())
    print('1 sched→cal (오른쪽) ok')
    # 짧게 쓸면 제자리
    swipe(250, 500, 200, 500, steps=6, dt=60); pg.wait_for_timeout(500)
    if 'cal' not in H(): fail('짧은 쓸기에 넘어감: %s' % H())
    if pg.evaluate(TR): fail('덜 민 뒤 transform 이 남음: %r' % pg.evaluate(TR))
    # 빠르게 휙 (60px 이지만 빠르게)
    swipe(260, 500, 200, 500, steps=3, dt=8); pg.wait_for_timeout(900)
    if 'sched' not in H(): fail('빠른 짧은 쓸기가 안 넘어감: %s' % H())
    swipe(120, 500, 300, 500); pg.wait_for_timeout(900)
    print('1 짧게/빠르게 ok')
    # 세로 스크롤은 무시
    swipe(200, 600, 230, 300); pg.wait_for_timeout(600)
    if 'cal' not in H(): fail('세로로 쓸었는데 탭이 바뀜: %s' % H())
    print('3 세로 ok')
    # 가로 스크롤 영역 안에서는 탭이 안 바뀐다
    pg.evaluate("""()=>{const d=document.createElement('div');d.id='hx';d.style.cssText='overflow-x:auto;width:300px;height:120px;position:fixed;left:40px;top:300px;z-index:30;background:#eee';
      d.innerHTML='<div style="width:1200px;height:100px">가로 스크롤</div>';document.body.appendChild(d)}""")
    # fixed div 는 #app 밖 — 실제 페이지와 같게 본문 안에 넣는다
    pg.evaluate("()=>{const d=document.getElementById('hx');document.querySelector('#app>.shell main').prepend(d);d.style.position='relative';d.style.left='0';d.style.top='0'}")
    r = pg.evaluate("(()=>{const r=document.getElementById('hx').getBoundingClientRect();return [r.left,r.top,r.width,r.height]})()")
    y = r[1]+r[3]/2
    swipe(r[0]+250, y, r[0]+40, y); pg.wait_for_timeout(800)
    if 'cal' not in H(): fail('가로 스크롤 영역 안에서 쓸었는데 탭이 바뀜: %s' % H())
    print('4 가로 스크롤 안 ok (scrollLeft=%s)' % pg.evaluate("document.getElementById('hx')&&document.getElementById('hx').scrollLeft"))
    # 끝 탭(예배)에서 오른쪽으로 → 제자리
    pg.click('.bnav [data-act="home"]'); pg.wait_for_timeout(800)
    swipe(100, 500, 300, 500); pg.wait_for_timeout(700)
    if not H().endswith('home'): fail('첫 탭에서 오른쪽 쓸기가 뭔가를 함: %s' % H())
    if pg.evaluate(TR): fail('고무줄 뒤 transform 이 남음')
    print('5 첫 탭 고무줄 ok')
    # 누르기: 탭바·달력 셀
    import datetime
    _t = datetime.date.today(); d1 = (_t + datetime.timedelta(days=3)).isoformat()
    print('open date', pg.evaluate("d=>fetch('/api/teams/'+CONTI.S.team.id+'/dates',{method:'POST',headers:{'x-conti':'1','content-type':'application/json'},body:JSON.stringify({date:d,label:'주일',time:'11:00'})}).then(r=>r.status)", d1))
    pg.evaluate("CONTI.SCH.at=0")
    pg.tap('.bnav [data-act="cal"]'); pg.wait_for_timeout(1500)
    if 'cal' not in H(): fail('탭바 누르기 안 됨')
    pg.goto(URL + '#/cal/' + d1[:7]); pg.wait_for_selector('[data-cal="%s"]' % d1, timeout=10000); pg.wait_for_timeout(500)
    st = lambda: pg.evaluate("d=>(CONTI.SCH.availability.find(a=>a.date===d&&a.userId===CONTI.NET.user.id)||{}).state||'unset'", d1)
    before = st(); pg.locator('[data-cal="%s"]' % d1).tap(); pg.wait_for_timeout(1200)
    after = st(); print('cal cell', before, '→', after)
    if before == after: fail('달력 셀 누르기가 안 먹음')
    # 셀 위에서 시작한 가로 쓸기: 탭은 넘어가되 셀 상태는 안 바뀐다
    pg.evaluate("CONTI.SCH.at=0"); pg.goto(URL + '#/cal/' + d1[:7]); pg.wait_for_selector('[data-cal="%s"]' % d1, timeout=10000); pg.wait_for_timeout(500)
    bx = pg.locator('[data-cal="%s"]' % d1).bounding_box(); cx, cy = bx['x']+bx['width']/2, bx['y']+bx['height']/2
    s0 = st(); swipe(min(cx, 330), cy, min(cx, 330)-200 if cx > 230 else min(cx,330)+200, cy); pg.wait_for_timeout(1200)
    print('swipe from cell → %s, state %s → %s' % (H(), s0, st()))
    if st() != s0: fail('셀에서 시작한 쓸기가 셀 상태를 바꿈')
    if H().startswith('#/cal') or H().startswith('#cal'): fail('셀 위에서 쓸었는데 탭이 안 바뀜: %s' % H())
    print('6 누르기 ok')
    # 가장자리 뒤로: 따라오기 + 취소 + 완료
    pg.goto(URL + '#/library'); pg.wait_for_timeout(1000)
    pg.goto(URL + '#/cal'); pg.wait_for_timeout(1000)
    tr = swipe(8, 400, 48, 402, steps=5, mid=TR); pg.wait_for_timeout(500)
    print('edge cancel mid', repr(tr))
    if rm == 'no-preference' and 'translate3d(40px' not in (tr or ''): fail('가장자리 쓸기에 페이지가 안 따라옴: %r' % tr)
    if 'cal' not in H(): fail('조금 밀었는데 뒤로 감')
    if pg.evaluate(TR): fail('취소 뒤 transform 이 남음: %r' % pg.evaluate(TR))
    tr = swipe(8, 400, 200, 405, steps=8, mid=TR); pg.wait_for_timeout(900)
    if 'library' not in H(): fail('가장자리 쓸기 뒤로 안 감: %s' % H())
    if pg.evaluate(TR) or pg.evaluate("document.getElementById('app').style.transform"): fail('뒤로 간 뒤 transform 이 남음')
    print('7 가장자리 뒤로 따라오기·취소·완료 ok')
    # 더보기 시트: 올라오고 내려간다, 눌린다
    pg.tap('.bnav [data-act="more-menu"]'); pg.wait_for_selector('.morelist')
    an = pg.evaluate("getComputedStyle(document.querySelector('#modal .sheetm')).animationName")
    print('sheet animation', an)
    if rm == 'no-preference' and an != 'sheet-up': fail('시트가 올라오는 애니메이션이 아님: %s' % an)
    if rm == 'reduce' and an not in ('none',): fail('움직임 줄이기인데 애니메이션: %s' % an)
    pg.wait_for_timeout(400)
    pg.mouse.click(200, 100)   # 바깥(배경) 누르면 닫힌다
    pg.wait_for_timeout(30)
    ghost = pg.evaluate("(()=>{const g=document.querySelector('body>.ov.out');return g?[getComputedStyle(g.querySelector('.sheetm')).animationName,getComputedStyle(g).pointerEvents]:null})()")
    print('ghost', ghost, 'modal empty', pg.evaluate("!document.getElementById('modal').firstChild"))
    if rm == 'no-preference' and (not ghost or ghost[0] != 'sheet-down' or ghost[1] != 'none'): fail('닫을 때 내려가지 않음: %s' % ghost)
    pg.wait_for_timeout(600)
    if pg.locator('.ov').count(): fail('닫힌 시트 껍데기가 남음')
    pg.tap('.bnav [data-act="more-menu"]'); pg.wait_for_selector('.morelist'); pg.wait_for_timeout(350)
    pg.tap('.morelist [data-act="settings"]'); pg.wait_for_timeout(800)
    if 'settings' not in H(): fail('시트 항목 누르기 안 됨')
    # 설정(탭 아님)에서는 가로 쓸기 무시
    swipe(300, 500, 100, 500); pg.wait_for_timeout(700)
    if 'settings' not in H(): fail('탭이 아닌 화면에서 쓸기가 먹음: %s' % H())
    print('8 더보기 시트 ok')
    if errs: fail('콘솔 오류 %s' % errs[:3])
    b.close()
  print('OK', rm)
run(sys.argv[1] if len(sys.argv) > 1 else 'no-preference')
