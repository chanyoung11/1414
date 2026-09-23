# 감사 묶음 "css" — 겹침·안전 영역·대비·레이아웃 (2026-09-24)
#  F12  폰 연습 화면: 광고 배너가 메트로놈·건반 패널 아래쪽을 가림
#  F13  아이폰 세로 무대: '내 조판' 창이 바의 톱니·닫기를 덮고, 바깥을 눌러도 안 닫힘
#  F59  768 미만: 팀 전환·코드로 받기·여러 곡 고르기로 들어갈 길이 없음
#  F60  글자색에 배경 토큰(--muted)을 써서 안 보임 · 악보 종이 안 주 버튼이 다크에서 흰색
#  F61  무대 모드에서 토스트가 무대 뒤에 깔림
#  F62  인쇄 미리보기: 화면보다 넓은 쪽의 왼쪽이 잘리고 스크롤로도 못 감
#  F123 좌우 안전 영역(가로 노치·옆 내비게이션 바)을 아무도 안 피함
#  F124 iOS 입력 확대 방지(16px)가 클래스 규칙에 져서 송폼·편성 칸에서 화면이 확대됨
#  F125 자르기 창에서 긴 악보 사진이 찌그러짐
#  F126 768–1023 아이콘 레일에서 로고 글자가 레일 밖으로 넘침
#  F127 폰 인쇄 미리보기 바가 넘치고 앱에서는 상태바 밑에 깔림
# 안전 영역은 데스크톱 브라우저에서 env() 가 0 이라 --sat 같은 변수를 인라인으로 넣어 흉내 낸다
# (안드로이드 MainActivity 가 하던 방식과 같다). 광고 배너도 body.hasad + --adh 로 흉내 낸다
import os, sys, time, base64
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
SHEET = os.path.join(ROOT, 'docs', 'sample_sheet.jpg')
H = {'x-conti': '1'}
SOFT = os.environ.get('SOFT') == '1'   # 고치기 전 코드에서 전부 재현해 볼 때: 실패해도 끝까지 간다
FAILS = []
def fail(m):
  print('FAIL:', m)
  if SOFT: FAILS.append(m); return
  sys.exit(1)

SHOTS = os.environ.get('SHOTS')   # 폴더를 주면 눈으로 볼 스크린숏을 남긴다
def shot(pg, name):
  if SHOTS: pg.screenshot(path=os.path.join(SHOTS, name + '.png'))

def setvars(pg, **kv):
  pg.evaluate("(kv)=>{for(const k in kv)document.documentElement.style.setProperty('--'+k,kv[k])}", kv)
def clearvars(pg, *names):
  pg.evaluate("(ns)=>ns.forEach(n=>document.documentElement.style.removeProperty('--'+n))", list(names))

RECT = "(s)=>{const e=document.querySelector(s);if(!e)return null;const r=e.getBoundingClientRect();return {x:r.left,y:r.top,r:r.right,b:r.bottom,w:r.width,h:r.height}}"
def rect(pg, sel): return pg.evaluate(RECT, sel)
# 그 자리를 누르면 무엇이 눌리는지 (가운데 점)
def hit(pg, sel):
  return pg.evaluate("""(s)=>{const e=document.querySelector(s);if(!e)return 'missing';const r=e.getBoundingClientRect();
    const t=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);return !!t&&(t===e||e.contains(t))}""", sel)
# 글자색과 배경의 대비 (WCAG). 배경은 투명하지 않은 가장 가까운 조상에서 읽는다
CONTRAST = """(s)=>{const e=document.querySelector(s);if(!e)return null;
  const rgb=c=>{const m=c.match(/[\\d.]+/g).map(Number);return {r:m[0],g:m[1],b:m[2],a:m.length>3?m[3]:1}};
  const L=({r,g,b})=>{const f=v=>{v/=255;return v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4)};return .2126*f(r)+.7152*f(g)+.0722*f(b)};
  let bg=null,n=e;while(n&&n.nodeType===1){const c=rgb(getComputedStyle(n).backgroundColor);if(c.a>0.5){bg=c;break}n=n.parentElement}
  if(!bg)bg=rgb(getComputedStyle(document.body).backgroundColor);
  const fg=rgb(getComputedStyle(e).color);const a=L(fg),b=L(bg);return (Math.max(a,b)+.05)/(Math.min(a,b)+.05)}"""

def run():
  tag = str(int(time.time()))[-6:]
  with sync_playwright() as p:
    b = p.chromium.launch()
    c = b.new_context(viewport={'width': 1300, 'height': 900})
    pg = c.new_page()
    errs = []; pg.on('pageerror', lambda e: errs.append(repr(e)[:200])); pg.on('dialog', lambda d: d.accept())
    pg.goto(URL); pg.wait_for_selector('#lgUser')
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName'); pg.check('#lgAgree')
    pg.fill('#lgName', '하은'); pg.fill('#lgUser', 'cs' + tag); pg.fill('#lgPass', 'secret1'); pg.click('[data-act="lg-submit"]')
    pg.wait_for_selector('#gtTeam'); pg.fill('#gtTeam', '화면팀'); pg.click('#gtSess .q:has-text("건반")'); pg.click('[data-act="team-create"]')
    pg.wait_for_selector('.shell[data-page]', timeout=10000)
    team = pg.evaluate('CONTI.S.team.id')

    # ---- F124: iOS 는 16px 미만 입력에 포커스하면 확대한다. 클래스 규칙에 지지 않게 확대 자체를 막는다
    vp = pg.evaluate("document.querySelector('meta[name=viewport]').content")
    if 'maximum-scale=1' not in vp.replace(' ', ''): fail('F124 viewport 에 maximum-scale=1 이 없음: ' + vp)
    print('F124 ok', vp)

    # ---- F126: 아이콘 레일(768–1023)에서는 로고가 레일 안에 들어간다
    pg.set_viewport_size({'width': 820, 'height': 1180}); pg.wait_for_timeout(500)
    side = rect(pg, '.side')
    logos = pg.evaluate("""[...document.querySelectorAll('.side .head .logo')].filter(e=>getComputedStyle(e).display!=='none').map(e=>{const r=e.getBoundingClientRect();return {c:e.getAttribute('class'),x:r.left,r:r.right,w:r.width}})""")
    if not logos: fail('F126 레일에 로고가 하나도 안 보임')
    for l in logos:
      if l['r'] > side['r'] - 4 or l['x'] < side['x']: fail('F126 로고가 레일(%s–%s) 밖으로 나감: %s' % (side['x'], side['r'], l))
    shot(pg, 'f126_rail')
    pg.set_viewport_size({'width': 1300, 'height': 900}); pg.wait_for_timeout(400)
    if not pg.locator('.side .head .logo.lockup').is_visible(): fail('F126 넓은 화면에서 로고 전체(글자 포함)가 안 보임')
    print('F126 ok', logos)

    # ---- 예배 하나 + 악보 한 장
    pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]', timeout=8000)
    pg.fill('[data-f="svc.name"]', '10/4 주일 2부 청년부 연합 찬양 예배')
    pg.click('[data-act="add-item"]'); pg.wait_for_timeout(400)
    pg.fill('[data-f="item.title"]', '예수로 나의 구주 삼고'); pg.fill('[data-f="item.key"]', 'G'); pg.fill('[data-f="item.form"]', 'Int – AABB')
    pg.set_input_files('#pieceFile', [SHEET])
    pg.wait_for_function("(()=>{const p=(CONTI.S.services[0].items[0].pieces||[])[0];return p&&p.w>0})()", timeout=90000)
    pg.wait_for_timeout(1200)
    sid = pg.evaluate('CONTI.S.services[0].id')

    # ---- F60: 악보 상단 바 상태 글자 · '결제는 앱에서만' 이 보인다 (라이트·다크)
    pg.wait_for_selector('.chordbar .cb-status', timeout=15000)
    for dark in [False, True]:
      pg.evaluate("(d)=>document.documentElement.classList.toggle('dark',d)", dark); pg.wait_for_timeout(200)
      cr = pg.evaluate(CONTRAST, '.chordbar .cb-status')
      if cr < 3: fail('F60 상태 글자 대비 %.2f (다크=%s)' % (cr, dark))
      # 악보는 늘 흰 종이다. 그 위 주 버튼은 다크에서도 어두워야 흰 종이에서 보인다
      pg.evaluate("""()=>{const s=document.querySelector('.sheet');if(!document.getElementById('tpri'))s.insertAdjacentHTML('beforeend','<button class="btn pri" id="tpri">코드 인식</button>')}""")
      bl = pg.evaluate("""(()=>{const m=getComputedStyle(document.getElementById('tpri')).backgroundColor.match(/[\\d.]+/g).map(Number);return (m[0]+m[1]+m[2])/3})()""")
      if bl > 100: fail('F60 악보 종이 위 주 버튼이 밝음(%.0f, 다크=%s) — 흰 종이에 묻힌다' % (bl, dark))
      pg.evaluate("document.getElementById('tpri').remove()")
      # 플랜 올리기 창의 안내 (웹에서만 보인다)
      pg.evaluate("""()=>{const b=document.createElement('button');b.dataset.act='upgrade';b.id='tupg';document.getElementById('app').appendChild(b);b.click()}""")
      pg.wait_for_selector('#modal .cb-note', timeout=5000)
      cr2 = pg.evaluate(CONTRAST, '#modal .cb-note')
      if cr2 < 3: fail('F60 결제 안내 대비 %.2f (다크=%s)' % (cr2, dark))
      pg.keyboard.press('Escape'); pg.wait_for_timeout(300); pg.evaluate("document.getElementById('tupg')&&document.getElementById('tupg').remove()")
      print('F60 ok dark=%s status=%.2f note=%.2f' % (dark, cr, cr2))
    pg.evaluate("document.documentElement.classList.remove('dark')")

    # ---- F125: 긴 악보 사진을 자르기 창에서 찌그러뜨리지 않는다
    tall = pg.evaluate("""()=>{const c=document.createElement('canvas');c.width=700;c.height=2100;const g=c.getContext('2d');
      g.fillStyle='#fff';g.fillRect(0,0,700,2100);g.fillStyle='#000';g.fillRect(10,10,680,6);g.fillRect(10,2084,680,6);g.fillRect(10,10,6,2080);g.fillRect(684,10,6,2080);
      for(let y=120;y<2000;y+=160){for(let k=0;k<5;k++)g.fillRect(40,y+k*12,620,2)}
      return c.toDataURL('image/jpeg',0.9).split(',')[1]}""")
    n0 = pg.evaluate('CONTI.S.services[0].items[0].pieces.length')
    pg.set_input_files('#pieceFile', files=[{'name': 'tall.jpg', 'mimeType': 'image/jpeg', 'buffer': base64.b64decode(tall)}])
    pg.wait_for_function("(n)=>CONTI.S.services[0].items[0].pieces.length>n", arg=n0, timeout=30000); pg.wait_for_timeout(1000)
    pid = pg.evaluate('(()=>{const ps=CONTI.S.services[0].items[0].pieces;return ps[ps.length-1].id})()')
    pg.evaluate("(id)=>document.querySelector('[data-act=\"crop-piece\"][data-id=\"'+id+'\"]').click()", pid)
    pg.wait_for_function("(()=>{const i=document.getElementById('cropImg');return i&&i.complete&&i.naturalWidth>0})()", timeout=8000); pg.wait_for_timeout(300)
    cr = pg.evaluate("""(()=>{const i=document.getElementById('cropImg'),w=document.getElementById('cropWrap');const r=i.getBoundingClientRect(),q=w.getBoundingClientRect();
      return {nat:i.naturalWidth/i.naturalHeight,shown:r.width/r.height,top:r.top-q.top,bottom:q.bottom-r.bottom,wrapScroll:w.scrollHeight-w.clientHeight}})()""")
    if abs(cr['shown'] - cr['nat']) / cr['nat'] > 0.03: fail('F125 자르기 창 사진 비율이 바뀜: %s' % cr)
    if cr['bottom'] < -1 or cr['top'] < -1: fail('F125 사진 일부가 창 밖에 있음 (터치로는 스크롤이 안 된다): %s' % cr)
    shot(pg, 'f125_crop')
    # 처음 그린 고르기 상자가 사진 위 제자리(사방 5% 안쪽)에 있다 — 창이 떠오르는 중에 재서 어긋나던 것
    bx = pg.evaluate("""(()=>{const i=document.getElementById('cropImg').getBoundingClientRect(),b=document.getElementById('cropBox').getBoundingClientRect();
      return {dx:b.left-(i.left+i.width*.05),dy:b.top-(i.top+i.height*.05),dw:b.width-i.width*.9,dh:b.height-i.height*.9}})()""")
    if max(abs(v) for v in bx.values()) > 1.5: fail('F125 고르기 상자가 사진과 어긋남: %s' % bx)
    pg.click('#modal [data-close]'); pg.wait_for_timeout(300)
    print('F125 ok', cr)

    # ---- F12: 폰 연습 화면에 광고 배너가 뜬 채 메트로놈·건반을 열어도 배너가 패널을 안 가린다
    pg.set_viewport_size({'width': 390, 'height': 844})
    pg.evaluate("(id)=>location.hash='#/play/'+id", sid); pg.wait_for_selector('[data-act="metro"]', timeout=10000); pg.wait_for_timeout(1200)
    setvars(pg, sab='34px', adh='50px'); pg.evaluate("document.body.classList.add('hasad')")
    ad_top = 844 - 34 - 50
    pg.click('[data-act="metro"]'); pg.wait_for_selector('#sidetool.on'); pg.wait_for_timeout(500)
    st = rect(pg, '#sidetool')
    beats = pg.evaluate("[...document.querySelectorAll('#sidetool [data-act=\"met-beats\"]')].map(e=>e.getBoundingClientRect().bottom)")
    if not beats: fail('F12 박자 버튼이 없음')
    if st['b'] > ad_top + 0.5 or max(beats) > ad_top + 0.5: fail('F12 메트로놈이 배너(%s~) 아래로 내려감: 패널 %s 박자 %s' % (ad_top, st, beats))
    pg.click('[data-act="met-beats"][data-n="3"]'); pg.wait_for_timeout(300)
    shot(pg, 'f12_metro_ad')
    if pg.evaluate('CONTI.MET.beats') != 3: fail('F12 박자 버튼이 안 눌림')
    pg.click('[data-act="sidetool-close"]'); pg.wait_for_timeout(500)
    pg.click('[data-act="piano"]'); pg.wait_for_selector('#sidetool.on #pkeys'); pg.wait_for_timeout(500)
    kb = pg.evaluate("Math.max(...[...document.querySelectorAll('#pkeys .pk')].map(e=>e.getBoundingClientRect().bottom))")
    if kb > ad_top + 0.5: fail('F12 건반 아래(%s)가 배너(%s~)에 깔림' % (kb, ad_top))
    pg.click('[data-act="sidetool-close"]'); pg.wait_for_timeout(500)
    # 광고가 없으면 홈 인디케이터만 피한다
    pg.evaluate("document.body.classList.remove('hasad')")
    pg.click('[data-act="metro"]'); pg.wait_for_selector('#sidetool.on'); pg.wait_for_timeout(500)
    last = pg.evaluate("Math.max(...[...document.querySelectorAll('#sidetool button')].map(e=>e.getBoundingClientRect().bottom))")
    if last > 844 - 34 + 0.5: fail('F12/F123 광고 없을 때 패널 버튼(%s)이 홈 인디케이터에 깔림' % last)
    pg.click('[data-act="sidetool-close"]'); pg.wait_for_timeout(500)
    # 태블릿: 왼쪽 패널도 배너 위에서 끝난다 · 위는 상태바를 피한다 (F123)
    pg.set_viewport_size({'width': 1024, 'height': 768}); pg.wait_for_timeout(400)
    setvars(pg, sat='24px', sab='20px'); pg.evaluate("document.body.classList.add('hasad')")
    pg.click('[data-act="metro"]'); pg.wait_for_selector('#sidetool.on'); pg.wait_for_timeout(500)
    st = rect(pg, '#sidetool'); cl = rect(pg, '#sidetool [data-act="sidetool-close"]')
    if st['b'] > 768 - 20 - 50 + 0.5: fail('F12 태블릿 왼쪽 패널이 배너에 깔림: %s' % st)
    if cl['y'] < 24: fail('F123 패널 닫기 버튼이 상태바 밑에 있음: %s' % cl)
    pg.click('[data-act="sidetool-close"]'); pg.wait_for_timeout(500)
    pg.evaluate("document.body.classList.remove('hasad')"); clearvars(pg, 'sat', 'sab', 'adh')
    print('F12 ok')

    # ---- F13 · F61: 아이폰 세로 무대 (노치 47px)
    pg.set_viewport_size({'width': 390, 'height': 844}); pg.wait_for_timeout(300)
    setvars(pg, sat='47px', sab='34px')
    pg.evaluate("CONTI.stageOpen(CONTI.S.services[0],0)"); pg.wait_for_selector('#stageWrap .stgbar', timeout=10000); pg.wait_for_timeout(600)
    bar = rect(pg, '.stgbar')
    pg.click('[data-stg="cfg"]'); pg.wait_for_selector('.stgpop'); pg.wait_for_timeout(200)
    pop = rect(pg, '.stgpop')
    if pop['y'] < bar['b'] - 0.5: fail('F13 내 조판 창(%s)이 바(%s) 위를 덮음' % (pop, bar))
    for s in ['[data-stg="cfg"]', '[data-stg="exit"]']:
      if hit(pg, s) is not True: fail('F13 창이 떠 있을 때 %s 가 안 눌림' % s)
    shot(pg, 'f13_stgpop')
    # 바깥(악보)을 누르면 창만 닫힌다 — 화면은 안 넘어간다
    scr = pg.evaluate('CONTI.STG.screen')
    pg.mouse.click(195, 700); pg.wait_for_timeout(300)
    if pg.locator('.stgpop').count(): fail('F13 바깥을 눌러도 내 조판 창이 안 닫힘')
    if pg.evaluate('CONTI.STG.screen') != scr: fail('F13 창을 닫는 탭이 화면까지 넘김')
    # 창 안을 누르면 그대로
    pg.click('[data-stg="cfg"]'); pg.wait_for_selector('.stgpop')
    pg.click('.stgpop .lbl'); pg.wait_for_timeout(200)
    if not pg.locator('.stgpop').count(): fail('F13 창 안을 눌렀는데 닫힘')
    # 톱니로 다시 닫힌다
    pg.click('[data-stg="cfg"]'); pg.wait_for_timeout(200)
    if pg.locator('.stgpop').count(): fail('F13 톱니로 창이 안 닫힘')
    # 가로 폰 — 창이 화면보다 길면 안에서 스크롤된다
    pg.set_viewport_size({'width': 844, 'height': 390}); setvars(pg, sat='0px', sab='21px'); pg.wait_for_timeout(500)
    pg.click('[data-stg="cfg"]'); pg.wait_for_selector('.stgpop'); pg.wait_for_timeout(200)
    pop = rect(pg, '.stgpop')
    if pop['b'] > 390 + 0.5: fail('F13 가로 폰에서 내 조판 창 아래가 화면 밖: %s' % pop)
    pg.click('[data-stg="cfg"]'); pg.wait_for_timeout(200)
    pg.set_viewport_size({'width': 390, 'height': 844}); setvars(pg, sat='47px', sab='34px'); pg.wait_for_timeout(500)
    print('F13 ok')

    # F61: 무대 위에서도 토스트가 보인다 (토스트 자리를 누르면 무엇이 맨 위인지 본다)
    pg.evaluate("()=>{const t=document.getElementById('toast');t.textContent='추천 조판으로 저장했어요';t.classList.add('show');t.style.pointerEvents='auto'}")
    pg.wait_for_timeout(300)
    if hit(pg, '#toast') is not True: fail('F61 무대 위에서 토스트가 가려짐')
    pg.evaluate("()=>{const t=document.getElementById('toast');t.classList.remove('show');t.style.pointerEvents=''}")
    print('F61 ok')

    # ---- F123: 가로 아이폰 — 노치(좌우 47px)를 무대·패널이 피한다
    pg.set_viewport_size({'width': 844, 'height': 390}); setvars(pg, sat='0px', sab='21px', sal='47px', sar='47px'); pg.wait_for_timeout(600)
    pgr = rect(pg, '.stgpage'); prv = rect(pg, '[data-stg="prev"]'); ex = rect(pg, '[data-stg="exit"]')
    if pgr['x'] < 47 or pgr['r'] > 844 - 47: fail('F123 무대 악보가 노치 밑으로 들어감: %s' % pgr)
    if pgr['b'] > 390 - 21 + 0.5: fail('F123 무대 악보 아래가 홈 인디케이터 밑: %s' % pgr)
    if prv['x'] < 47 or ex['r'] > 844 - 47: fail('F123 무대 바 버튼이 노치 밑: %s %s' % (prv, ex))
    shot(pg, 'f123_stage_land')
    pg.evaluate('CONTI.stageExit()'); pg.wait_for_timeout(400)
    print('F123 stage ok', pgr)
    # 가로 폰의 연습 화면 도구 패널(왼쪽)
    pg.click('[data-act="metro"]'); pg.wait_for_selector('#sidetool.on'); pg.wait_for_timeout(500)
    hd = rect(pg, '#sidetool .sthd b')
    if hd['x'] < 47: fail('F123 도구 패널 제목이 노치 밑: %s' % hd)
    pg.click('[data-act="sidetool-close"]'); pg.wait_for_timeout(500)
    # 아래에서 올라오는 시트: 홈 인디케이터를 피한다
    pg.set_viewport_size({'width': 390, 'height': 844}); setvars(pg, sat='47px', sab='34px', sal='0px', sar='0px'); pg.wait_for_timeout(300)
    pg.evaluate("location.hash='#/'"); pg.wait_for_selector('.bnav [data-act="more-menu"]'); pg.wait_for_timeout(500)
    pg.click('.bnav [data-act="more-menu"]'); pg.wait_for_selector('.morelist'); pg.wait_for_timeout(500)
    lb = pg.evaluate("Math.max(...[...document.querySelectorAll('.morelist .btn')].map(e=>e.getBoundingClientRect().bottom))")
    if lb > 844 - 34: fail('F123 더보기 시트 마지막 줄(%s)이 홈 인디케이터에 깔림' % lb)
    pg.keyboard.press('Escape'); pg.wait_for_timeout(400)
    print('F123 sheet ok')

    # ---- F62 · F127: 폰 인쇄 미리보기
    pg.evaluate("(id)=>location.hash='#/view/'+id", sid); pg.wait_for_selector('[data-act="print"]', state='attached', timeout=10000); pg.wait_for_timeout(1000)
    pg.evaluate("document.querySelector('[data-act=\"print\"]').click()"); pg.wait_for_selector('#pvGo', timeout=8000)
    pg.click('[data-po="orient"][data-v="landscape"]'); pg.wait_for_timeout(300)
    pg.click('#pvGo'); pg.wait_for_selector('#printArea.pv .ppage', timeout=10000); pg.wait_for_timeout(800)
    # 가로로 밀 수 있는 곳(미리보기 판이든 쪽 묶음이든)을 끝까지 밀어 본다
    pv = pg.evaluate("""(()=>{const sc=[document.getElementById('printArea'),document.querySelector('.pvout')].find(e=>e.scrollWidth>e.clientWidth+1);
      const pgEl=document.querySelector('.ppage');if(sc)sc.scrollLeft=0;const r=pgEl.getBoundingClientRect();
      if(sc)sc.scrollLeft=1e6;const r2=pgEl.getBoundingClientRect();
      const cb=document.querySelector('[data-pv="close"]').getBoundingClientRect();
      const t=document.elementFromPoint(cb.left+cb.width/2,cb.top+cb.height/2);const closeHit=!!t&&!!t.closest('[data-pv="close"]');
      if(sc)sc.scrollLeft=0;
      return {left:r.left,w:r.width,right2:r2.right,vw:innerWidth,scroller:sc?(sc.id||sc.className):null,closeHit}})()""")
    if pv['w'] <= 390: fail('F62 시험 전제: 쪽이 화면보다 넓어야 함 %s' % pv)
    if pv['left'] < -0.5: fail('F62 쪽 왼쪽이 화면 밖(%s)에 있고 거기로 스크롤할 수 없음' % pv)
    if not pv['scroller'] or pv['right2'] > pv['vw'] + 1: fail('F62 끝까지 밀어도 쪽 오른쪽이 안 보임: %s' % pv)
    if not pv['closeHit']: fail('F62 옆으로 밀면 위 바(닫기)가 같이 밀려 나감: %s' % pv)
    shot(pg, 'f62_f127_preview')
    print('F62 phone ok', pv)
    bar = rect(pg, '.pvbar')
    kids = pg.evaluate("""[...document.querySelectorAll('.pvbar > *')].filter(e=>getComputedStyle(e).display!=='none').map(e=>{const r=e.getBoundingClientRect();return {t:e.textContent.trim().slice(0,12),x:r.left,y:r.top,r:r.right,b:r.bottom,h:r.height}})""")
    for k in kids:
      if k['r'] > 390 + 0.5 or k['x'] < -0.5: fail('F127 미리보기 바의 %s 가 화면 밖: %s' % (k['t'], k))
      if k['y'] < 47: fail('F127 미리보기 바의 %s 가 상태바 밑(%s): %s' % (k['t'], 47, k))
    ttl = [k for k in kids if k['t'].startswith('10/4')]
    if not ttl or ttl[0]['h'] > 26: fail('F127 제목이 한 줄로 안 보임: %s' % ttl)
    for s in ['[data-pv="close"]', '[data-pv="opt"]', '[data-pv="print"]']:
      if hit(pg, s) is not True: fail('F127 %s 가 안 눌림' % s)
    print('F127 ok', bar)
    # 넓은 화면에서는 가운데
    pg.set_viewport_size({'width': 1500, 'height': 900}); clearvars(pg, 'sat', 'sab', 'sal', 'sar'); pg.wait_for_timeout(400)
    pv = pg.evaluate("""(()=>{const a=document.getElementById('printArea');const r=document.querySelector('.ppage').getBoundingClientRect();return {l:r.left,r:a.clientWidth-r.right}})()""")
    if abs(pv['l'] - pv['r']) > 2: fail('F62 넓은 화면에서 쪽이 가운데가 아님: %s' % pv)
    pg.click('[data-pv="close"]'); pg.wait_for_timeout(400)
    print('F62 desktop ok', pv)

    # ---- F123: 태블릿 편성 패널 머리가 상태바를 피하고, 가로 폰에서는 노치를 피한다
    c.request.post(URL + 'api/teams/%s/dates' % team, headers=H, data={'date': '2026-10-04', 'label': '주일 1부', 'time': '11:00'})
    pg.set_viewport_size({'width': 1180, 'height': 820}); setvars(pg, sat='24px', sab='20px')
    pg.goto(URL + '#/sched'); pg.wait_for_selector('.schtab .dcol', timeout=10000); pg.wait_for_timeout(800)
    setvars(pg, sat='24px', sab='20px')
    pg.click('.dcol'); pg.wait_for_selector('.lnpanel', timeout=6000); pg.wait_for_timeout(500)
    x = rect(pg, '.lnhd [data-act="lclose"]'); ft = rect(pg, '.lnft')
    if x['y'] < 24: fail('F123 편성 패널 닫기가 상태바 밑: %s' % x)
    if ft['b'] > 820 - 20 + 0.5: fail('F123 편성 패널 아래가 홈 인디케이터 밑: %s' % ft)
    pg.set_viewport_size({'width': 844, 'height': 390}); setvars(pg, sat='0px', sab='21px', sal='47px', sar='47px'); pg.wait_for_timeout(400)
    x = rect(pg, '.lnhd [data-act="lclose"]')
    if x['r'] > 844 - 47: fail('F123 가로 폰 편성 패널 닫기가 노치 밑: %s' % x)
    pg.click('.lnhd [data-act="lclose"]'); pg.wait_for_timeout(400)
    clearvars(pg, 'sat', 'sab', 'sal', 'sar')
    print('F123 lineup ok')

    # ---- F59: 폰에서도 머리글의 숨은 버튼으로 들어갈 길이 있다
    r = pg.evaluate("""async()=>{const r=await fetch('/api/teams',{method:'POST',credentials:'include',headers:{'content-type':'application/json','x-conti':'1'},body:JSON.stringify({name:'둘째팀',myName:'하은',session:'건반'})});return r.status}""")
    if r >= 300: fail('F59 두 번째 팀을 못 만듦: %s' % r)
    pg.set_viewport_size({'width': 390, 'height': 844})
    pg.goto(URL + '#/team'); pg.reload(); pg.wait_for_selector('.shell[data-page="team"]', timeout=10000); pg.wait_for_timeout(1000)
    if pg.evaluate('CONTI.NET.teams.length') < 2: fail('F59 시험 전제: 팀이 둘이어야 함')
    if pg.locator('.hd [data-act="team-switch"]').is_visible(): fail('F59 시험 전제: 폰에서는 머리글 버튼이 접혀 있어야 함')
    more = pg.locator('.hd [data-act="hd-more"]')
    if not more.count() or not more.is_visible(): fail('F59 폰 팀 화면에 머리글 더보기가 없음')
    more.click(); pg.wait_for_selector('#modal .morelist', timeout=4000)
    items = pg.locator('#modal .morelist .btn').all_inner_texts()
    if not any('팀 전환' in t for t in items): fail('F59 더보기에 팀 전환이 없음: %s' % items)
    shot(pg, 'f59_team_more')
    if any('멤버 초대' in t for t in items): fail('F59 이미 보이는 버튼(멤버 초대)까지 더보기에 들어감: %s' % items)
    pg.click('#modal .morelist .btn:has-text("팀 전환")'); pg.wait_for_selector('#modal [data-switch]', timeout=4000)
    print('F59 team ok', items)
    pg.keyboard.press('Escape'); pg.wait_for_timeout(300)
    pg.goto(URL + '#/library'); pg.wait_for_selector('.shell[data-page="library"]', timeout=10000); pg.wait_for_timeout(800)
    pg.click('.hd [data-act="hd-more"]'); pg.wait_for_selector('#modal .morelist', timeout=4000)
    items = pg.locator('#modal .morelist .btn').all_inner_texts()
    for want in ['코드로 받기', '여러 곡 고르기']:
      if not any(want in t for t in items): fail('F59 라이브러리 더보기에 %s 가 없음: %s' % (want, items))
    pg.click('#modal .morelist .btn:has-text("여러 곡 고르기")'); pg.wait_for_timeout(500)
    if pg.evaluate('CONTI.LIB.pick') != 'multi': fail('F59 더보기에서 여러 곡 고르기가 안 켜짐')
    if pg.locator('#modal .morelist').count(): fail('F59 누른 뒤에도 더보기 시트가 남음')
    pg.click('.hd [data-act="hd-more"]'); pg.wait_for_selector('#modal .morelist', timeout=4000)
    pg.click('#modal .morelist .btn:has-text("코드로 받기")'); pg.wait_for_timeout(600)
    if not pg.locator('#modal .sheetm').count() or pg.locator('#modal .morelist').count(): fail('F59 코드로 받기 창이 안 열림')
    print('F59 library ok', items)
    pg.keyboard.press('Escape'); pg.wait_for_timeout(300)
    # 넓은 화면에서는 버튼이 다 보이니 더보기가 없다
    pg.set_viewport_size({'width': 1300, 'height': 900}); pg.wait_for_timeout(400)
    if pg.locator('.hd [data-act="hd-more"]').is_visible(): fail('F59 넓은 화면에도 머리글 더보기가 보임')
    if not pg.locator('.hd [data-act="lib-receive"]').is_visible(): fail('F59 넓은 화면에서 코드로 받기가 안 보임')
    # 숨길 버튼이 없는 화면(예배)에는 더보기를 안 둔다
    pg.set_viewport_size({'width': 390, 'height': 844}); pg.goto(URL + '#/'); pg.wait_for_selector('.shell[data-page="home"]', timeout=10000); pg.wait_for_timeout(500)
    if pg.locator('.hd [data-act="hd-more"]').count(): fail('F59 숨길 버튼이 없는데 머리글 더보기가 생김')
    print('F59 ok')

    if errs: fail('콘솔 오류: ' + errs[0])
    if FAILS: print('%d FAIL' % len(FAILS)); sys.exit(1)
    print('OK — F12 F13 F59 F60 F61 F62 F123 F124 F125 F126 F127')
    b.close()

run()
