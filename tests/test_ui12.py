# 실사용 제보 12건 (2026-09-18) — 눌러서 확인한다
#  1 하단 탭 다섯 칸이 같은 폭      2 왼쪽 가장자리 스와이프 = 뒤로
#  3 시트 열면 뒤 화면 스크롤 잠김   4 미리보기 뒤로 → 편집으로
#  5 첫 곡 좌화살표·끝 곡 우화살표 없음
#  6 블록 툴 바가 밝아 보인다        7 악보 블록에 좌우 여백이 안 들어간다
#  8 격자 없이 자유 배치            9 시프트 다중 선택 · ⌘C/V · Delete · 화살표
# 10 곡마다 송폼 블록 · 맨 위 곡명 없음
# 11 크기 조절 중 악보도 같이       12 큰 블록에서도 툴 바가 화면 안에
import os, sys, time
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
SHEET = os.path.join(ROOT, 'docs', 'sample_sheet.jpg')
def fail(m): print('FAIL:', m); sys.exit(1)

def run():
  tag = str(int(time.time()))[-6:]
  with sync_playwright() as p:
    b = p.chromium.launch()
    c = b.new_context(viewport={'width': 1180, 'height': 820}, has_touch=True)   # iPad 가로
    pg = c.new_page()
    errs = []; pg.on('pageerror', lambda e: errs.append(repr(e)[:200])); pg.on('dialog', lambda d: d.accept())
    pg.goto(URL); pg.wait_for_selector('#lgUser')
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName'); pg.check('#lgAgree')
    pg.fill('#lgName','하은'); pg.fill('#lgUser','u12'+tag); pg.fill('#lgPass','secret1'); pg.click('[data-act="lg-submit"]')
    pg.wait_for_selector('#gtTeam'); pg.fill('#gtTeam','12팀'); pg.click('#gtSess .q:has-text("건반")'); pg.click('[data-act="team-create"]')
    pg.wait_for_selector('.shell[data-page]', timeout=10000)

    # 곡 두 개 + 악보
    pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]', timeout=8000)
    pg.fill('[data-f="svc.name"]','9/20 주일')
    for t, k in [('예수로 나의 구주 삼고','G'), ('주 사랑합니다','D')]:
      pg.click('[data-act="add-item"]'); pg.wait_for_timeout(400)
      pg.fill('[data-f="item.title"]', t); pg.fill('[data-f="item.key"]', k); pg.fill('[data-f="item.form"]','Int – AABB')
      pg.set_input_files('#pieceFile', [SHEET])
      pg.wait_for_function("(()=>{const its=CONTI.S.services[0].items;const it=its[its.length-1];const p=(it.pieces||[])[0];return p&&p.w>0})()", timeout=90000)
      pg.wait_for_timeout(700)
    sid = pg.evaluate("CONTI.S.services[0].id")

    # ---- 4 미리보기 → 뒤로 → 편집
    pg.locator('[data-act="view-svc"]').first.click(); pg.wait_for_timeout(1500)
    if 'view/' not in pg.evaluate("location.hash"): fail('미리보기로 안 감: %s' % pg.evaluate("location.hash"))
    pg.click('.top [data-act="edit-svc"]'); pg.wait_for_timeout(1200)
    if 'edit/' not in pg.evaluate("location.hash"): fail('미리보기 뒤로가 편집으로 안 감: %s' % pg.evaluate("location.hash"))
    print('4 미리보기→편집 ok')

    # ---- 5 첫 곡/끝 곡 화살표
    pg.goto(URL + '#/play/' + sid); pg.wait_for_selector('.songnav', timeout=10000); pg.wait_for_timeout(900)
    if pg.locator('.songnav [data-d="-1"].icon').count(): fail('첫 곡인데 좌화살표가 있음')
    if not pg.locator('.songnav [data-d="1"].icon').count(): fail('다음 곡이 있는데 우화살표가 없음')
    pg.click('.songnav [data-d="1"].icon'); pg.wait_for_timeout(900)
    if pg.locator('.songnav [data-d="1"].icon').count(): fail('마지막 곡인데 우화살표가 있음')
    if not pg.locator('.songnav [data-d="-1"].icon').count(): fail('이전 곡이 있는데 좌화살표가 없음')
    print('5 곡 화살표 ok')

    # ---- 1·3 폰 폭: 탭 폭 · 시트 스크롤 잠김
    pg.set_viewport_size({'width':390,'height':844})
    pg.goto(URL + '#/home'); pg.wait_for_selector('.bnav', timeout=8000); pg.wait_for_timeout(800)
    ws = pg.evaluate("[...document.querySelectorAll('.bnav button')].map(b=>Math.round(b.getBoundingClientRect().width))")
    if len(ws) != 5: fail('탭이 5개가 아님: %s' % ws)
    if max(ws) - min(ws) > 1: fail('탭 폭이 서로 다름: %s' % ws)
    print('1 탭 폭 고름 ok', ws)
    pg.click('.bnav [data-act="more-menu"]'); pg.wait_for_selector('.morelist', timeout=3000)
    if pg.evaluate("getComputedStyle(document.documentElement).overflow") != 'hidden': fail('시트를 열었는데 뒤 화면이 스크롤됨')
    pg.keyboard.press('Escape'); pg.evaluate("CONTI.closeModal&&CONTI.closeModal()"); pg.wait_for_timeout(400)
    if pg.evaluate("document.documentElement.classList.contains('noscroll')"): fail('시트를 닫았는데 스크롤 잠김이 남음')
    print('3 시트 스크롤 잠김 ok')

    # ---- 2 왼쪽 가장자리 스와이프 = 뒤로
    pg.goto(URL + '#/library'); pg.wait_for_timeout(900)
    pg.goto(URL + '#/cal'); pg.wait_for_timeout(900)
    pg.touchscreen.tap(8, 400)
    pg.evaluate("""()=>{const fire=(t,x,y)=>{const e=new TouchEvent(t,{bubbles:true,cancelable:true,
        touches:t==='touchend'?[]:[new Touch({identifier:1,target:document.body,clientX:x,clientY:y})],
        changedTouches:[new Touch({identifier:1,target:document.body,clientX:x,clientY:y})]});document.body.dispatchEvent(e)};
      fire('touchstart',8,400);fire('touchend',140,405)}""")
    pg.wait_for_timeout(900)
    if '#/library' not in pg.evaluate("location.hash"): fail('가장자리 스와이프로 뒤로 안 감: %s' % pg.evaluate("location.hash"))
    print('2 가장자리 스와이프 뒤로 ok')

    # ---- 무대 편집 (아이패드 가로)
    pg.set_viewport_size({'width':1180,'height':820})
    pg.goto(URL + '#/view/' + sid); pg.wait_for_selector('[data-act="play"][data-stage="1"]', timeout=10000); pg.wait_for_timeout(1200)
    pg.click('[data-act="play"][data-stage="1"]'); pg.wait_for_selector('#stageWrap .stgpage', timeout=15000); pg.wait_for_timeout(900)

    # 10 곡마다 송폼 블록 · 맨 위 곡명 없음
    if pg.evaluate("CONTI.STG.pref.form") != 'block': fail('송폼 모드가 block 이 아님: %s' % pg.evaluate("CONTI.STG.pref.form"))
    heads = pg.evaluate("CONTI.STG.lay.screens.flatMap(s=>s.blocks).filter(b=>b.type==='head').map(b=>b.idx)")
    if sorted(set(heads)) != [0,1]: fail('곡마다 송폼 블록이 아님: %s' % heads)
    if pg.locator('.stgbar b').inner_text().strip(): fail('맨 위에 곡명이 남음: %r' % pg.locator('.stgbar b').inner_text())
    print('10 송폼 블록 · 맨 위 비움 ok', heads)

    pg.click('[data-stg="edit"]'); pg.wait_for_timeout(700)
    if not pg.locator('.stgpage.edit').count(): fail('편집 모드로 안 들어감')
    if pg.locator('.sgrid').count(): fail('격자가 아직 그려짐 (자유 배치인데)')
    print('8-a 격자 없음 ok')

    # 7 악보 블록 폭 = 그림 폭 (좌우 여백 없음)
    gap = pg.evaluate("""(()=>{const S=CONTI.STG;const W=CONTI.STG.lay.cw;
      const b=S.layout.screens[S.screen].blocks.find(x=>x.type==='slice');
      if(!b)return null;const el=document.querySelector('.sblk[data-sid="'+CSS.escape(b.id)+'"]');
      const img=el.querySelector('img');
      const r=el.getBoundingClientRect(),ir=img.getBoundingClientRect();
      return {box:Math.round(r.width),img:Math.round(ir.width),left:Math.round(ir.left-r.left)}})()""")
    if not gap: fail('악보 블록을 못 찾음')
    if gap['box'] - gap['img'] > 4 or gap['left'] > 4: fail('악보 블록에 좌우 여백이 들어감: %s' % gap)
    print('7 악보 블록 여백 없음 ok', gap)

    # 8-b 자유 배치: 격자에 안 맞는 좌표로 옮겨진다
    ids = pg.evaluate("CONTI.STG.layout.screens[CONTI.STG.screen].blocks.map(b=>b.id)")
    first = pg.locator('.sblk').first
    bb = first.bounding_box()
    pg.mouse.move(bb['x']+30, bb['y']+12); pg.mouse.down()
    pg.mouse.move(bb['x']+30+77, bb['y']+12+53, steps=12); pg.mouse.up(); pg.wait_for_timeout(600)
    xs = pg.evaluate("CONTI.STG.layout.screens[CONTI.STG.screen].blocks.map(b=>b.x)")
    if all(abs(x*12 - round(x*12)) < 1e-6 for x in xs): fail('아직 12칸 격자에만 놓임: %s' % xs)
    print('8-b 자유 배치 ok')

    # 9 시프트 다중 선택 → 화살표로 함께 이동 → ⌘C/⌘V → Delete
    pg.click('[data-stg="auto"]'); pg.wait_for_timeout(1200)     # 앞 단계에서 겹쳐 놓은 것을 되돌린다
    if not pg.locator('.stgpage.edit').count(): fail('자동으로 되돌린 뒤 편집 모드가 풀림')
    JS_AT = ("(i)=>{const S=CONTI.STG;const ids=S.layout.screens[S.screen].blocks.filter(b=>!b.hidden).map(b=>b.id);"
             "const el=document.querySelector('.sblk[data-sid=\"'+CSS.escape(ids[i])+'\"]');const r=el.getBoundingClientRect();"
             "return {id:ids[i],x:r.x+Math.min(20,r.width/3),y:r.y+Math.min(10,r.height/3)}}")
    p0 = pg.evaluate(JS_AT, 0)
    pg.mouse.click(p0['x'], p0['y']); pg.wait_for_timeout(450)
    p1 = pg.evaluate(JS_AT, 1)
    pg.keyboard.down('Shift'); pg.mouse.click(p1['x'], p1['y']); pg.keyboard.up('Shift'); pg.wait_for_timeout(500)
    if pg.evaluate("CONTI.STG.sel.length") != 2: fail('시프트로 두 개가 안 골라짐: %s' % pg.evaluate("CONTI.STG.sel"))
    if not pg.locator('.stgsel').count(): fail('여러 개 골랐는데 안내 띠가 없음')
    before = pg.evaluate("CONTI.STG.sel.map(id=>CONTI.STG.layout.screens[CONTI.STG.screen].blocks.find(b=>b.id===id).x)")
    pg.keyboard.press('ArrowRight'); pg.wait_for_timeout(400)
    after = pg.evaluate("CONTI.STG.sel.map(id=>CONTI.STG.layout.screens[CONTI.STG.screen].blocks.find(b=>b.id===id).x)")
    if not all(a > b0_ + 1e-6 for a, b0_ in zip(after, before)): fail('화살표로 함께 안 움직임: %s → %s' % (before, after))
    print('9-a 다중 선택 · 화살표 이동 ok')
    n0 = pg.evaluate("CONTI.STG.layout.screens[CONTI.STG.screen].blocks.length")
    pg.keyboard.press('Control+c'); pg.wait_for_timeout(300)
    pg.keyboard.press('Control+v'); pg.wait_for_timeout(800)
    n1 = pg.evaluate("CONTI.STG.layout.screens[CONTI.STG.screen].blocks.length")
    if n1 != n0 + 2: fail('붙이기로 두 개가 안 늘어남: %d → %d' % (n0, n1))
    if pg.evaluate("CONTI.STG.sel.length") != 2: fail('붙인 것이 선택돼 있지 않음')
    print('9-b ⌘C / ⌘V ok', n0, '→', n1)
    pg.keyboard.press('Delete'); pg.wait_for_timeout(700)
    vis = pg.evaluate("CONTI.STG.layout.screens[CONTI.STG.screen].blocks.filter(b=>!b.hidden).length")
    if vis != n0: fail('Delete 로 안 숨겨짐: 보이는 블록 %d (기대 %d)' % (vis, n0))
    print('9-c Delete ok')
    pg.keyboard.press('Control+a'); pg.wait_for_timeout(400)
    if pg.evaluate("CONTI.STG.sel.length") != vis: fail('⌘A 전체 선택이 안 됨')
    print('9-d ⌘A ok')
    pg.keyboard.press('Escape'); pg.wait_for_timeout(400)
    if pg.evaluate("CONTI.STG.sel.length"): fail('Escape 로 선택 해제 안 됨')
    if not pg.locator('#stageWrap').count(): fail('Escape 가 무대까지 닫음')
    if not pg.locator('.stgpage.edit').count(): fail('Escape 한 번에 편집까지 나감')
    print('9-e Escape 선택 해제 ok')

    # 6 툴 바가 밝다 · 12 큰 블록에서도 화면 안
    pg.locator('.sblk').first.click(); pg.wait_for_timeout(500)
    if not pg.locator('.sblkmenu').count(): fail('블록 메뉴가 안 열림')
    col = pg.evaluate("(()=>{const m=document.querySelector('.sblkmenu');const bt=m.querySelector('.sbtn2');return {menu:getComputedStyle(m).backgroundColor,btn:getComputedStyle(bt).backgroundColor,txt:getComputedStyle(bt).color}})()")
    def lum(rgb):
      v = [int(x) for x in rgb.replace('rgb(','').replace('rgba(','').replace(')','').split(',')[:3]]
      return 0.299*v[0]+0.587*v[1]+0.114*v[2]
    if abs(lum(col['btn']) - lum(col['txt'])) < 90: fail('툴 바 버튼과 글자 대비가 낮음: %s' % col)
    print('6 툴 바 대비 ok', round(lum(col['btn'])), round(lum(col['txt'])))
    # 블록을 화면 가득 키워도 메뉴가 화면 안에
    pg.evaluate("""()=>{const S=CONTI.STG;const L=S.layout.screens[S.screen];const b=L.blocks.find(x=>x.type==='slice');
      b.x=0;b.y=0;b.w=0.98;b.h=0.98;S.sel=[b.id];S.menu=b.id;CONTI.STG&&window.dispatchEvent(new Event('resize'))}""")
    pg.evaluate("()=>{const f=window.CONTI;f.render&&0;}"); pg.evaluate("()=>{const S=CONTI.STG;S.menu=S.menu;}")
    pg.evaluate("()=>{window.dispatchEvent(new Event('resize'))}"); pg.wait_for_timeout(900)
    box = pg.evaluate("""(()=>{const m=document.querySelector('.sblkmenu');if(!m)return null;const r=m.getBoundingClientRect();
      return {top:Math.round(r.top),bottom:Math.round(r.bottom),vh:window.innerHeight}})()""")
    if box and (box['bottom'] > box['vh'] or box['top'] < 0): fail('큰 블록에서 툴 바가 화면 밖: %s' % box)
    print('12 큰 블록 툴 바 ok', box)

    # 11 크기 조절: 끄는 동안 악보도 같이 커진다 (놓기 전에 이미 커져 있어야 한다)
    pg.click('[data-stg="auto"]'); pg.wait_for_timeout(1200)
    JS_SL = ("()=>{const S=CONTI.STG;const b=S.layout.screens[S.screen].blocks.find(x=>x.type==='slice');"
             "const el=document.querySelector('.sblk[data-sid=\"'+CSS.escape(b.id)+'\"]');const g=el.querySelector('.sgrip');"
             "const gr=g.getBoundingClientRect();const ir=el.querySelector('img').getBoundingClientRect();"
             "return {id:b.id,gx:gr.x+gr.width/2,gy:gr.y+gr.height/2,img:ir.width}}")
    sl = pg.evaluate(JS_SL)
    pg.mouse.move(sl['gx'], sl['gy']); pg.mouse.down()
    pg.mouse.move(sl['gx']+120, sl['gy']+120, steps=10); pg.wait_for_timeout(250)
    mid = pg.evaluate("(id)=>Math.round(document.querySelector('.sblk[data-sid=\"'+CSS.escape(id)+'\"]').querySelector('img').getBoundingClientRect().width)", sl['id'])
    pg.mouse.up(); pg.wait_for_timeout(700)
    end = pg.evaluate("(id)=>Math.round(document.querySelector('.sblk[data-sid=\"'+CSS.escape(id)+'\"]').querySelector('img').getBoundingClientRect().width)", sl['id'])
    if mid <= round(sl['img']) + 8: fail('끄는 동안 악보가 안 커짐: %d → %d (놓은 뒤 %d)' % (round(sl['img']), mid, end))
    if abs(mid - end) > 20: fail('끌 때와 놓은 뒤 크기가 다름: %d vs %d' % (mid, end))
    print('11 끄는 동안 악보 같이 커짐 ok', round(sl['img']), '→', mid, '→', end)

    if errs: fail('콘솔 오류: %s' % errs[:3])
    b.close()
  print('OK — 제보 12건')
run()
