# 무대 편집 제보 (2026-09-23) — 눌러서 확인한다
#  1 블록을 화면(악보 판) 밖으로 걸쳐 놓아도 된다. 다만 다시 잡을 만큼은 화면 안에 남는다
#  2 여러 개 고른 채 꼭짓점을 끌면 모두 같은 배율로 커진다 (묶음 테두리 상자 기준)
#  3 크기 조절 손잡이가 꼭짓점 네 곳에 다 있고, 잡은 꼭짓점의 맞은편이 제자리에 있다
#  4 끄는 동안 블록 테두리도 악보와 같이 줄어든다 · 숨기면 테두리도 사라진다
import os, sys, time
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
SHEET = os.path.join(ROOT, 'docs', 'sample_sheet.jpg')
def fail(m): print('FAIL:', m); sys.exit(1)

BLK = "CONTI.STG.layout.screens[CONTI.STG.screen].blocks"
# 블록의 화면 위 사각형 (편집 중 축소까지 들어간 실제 자리)
JS_RECT = ("(id)=>{const el=document.querySelector('.sblk[data-sid=\"'+CSS.escape(id)+'\"]');if(!el)return null;"
           "const r=el.getBoundingClientRect();return {x:r.x,y:r.y,r:r.right,b:r.bottom,w:r.width,h:r.height}}")
JS_GRIP = ("([id,c])=>{const g=document.querySelector('.sblk[data-sid=\"'+CSS.escape(id)+'\"] .sgrip[data-c=\"'+c+'\"]');"
           "if(!g)return null;const r=g.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}}")
JS_PAGE = "(()=>{const r=document.querySelector('.stgpage').getBoundingClientRect();return {x:r.x,y:r.y,r:r.right,b:r.bottom}})()"

def drag(pg, x, y, dx, dy):
  pg.mouse.move(x, y); pg.mouse.down()
  pg.mouse.move(x + dx, y + dy, steps=12); pg.mouse.up(); pg.wait_for_timeout(600)

def run():
  tag = str(int(time.time()))[-6:]
  with sync_playwright() as p:
    b = p.chromium.launch()
    c = b.new_context(viewport={'width': 1180, 'height': 820})   # 아이패드 가로 폭 · 마우스
    pg = c.new_page()
    errs = []; pg.on('pageerror', lambda e: errs.append(repr(e)[:200])); pg.on('dialog', lambda d: d.accept())
    pg.goto(URL); pg.wait_for_selector('#lgUser')
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName'); pg.check('#lgAgree')
    pg.fill('#lgName','하은'); pg.fill('#lgUser','sf'+tag); pg.fill('#lgPass','secret1'); pg.click('[data-act="lg-submit"]')
    pg.wait_for_selector('#gtTeam'); pg.fill('#gtTeam','무대팀'); pg.click('#gtSess .q:has-text("건반")'); pg.click('[data-act="team-create"]')
    pg.wait_for_selector('.shell[data-page]', timeout=10000)
    pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]', timeout=8000)
    pg.fill('[data-f="svc.name"]','9/27 주일')
    for t in ['예수로 나의 구주 삼고', '주 사랑합니다']:
      pg.click('[data-act="add-item"]'); pg.wait_for_timeout(400)
      pg.fill('[data-f="item.title"]', t); pg.fill('[data-f="item.key"]', 'G'); pg.fill('[data-f="item.form"]','Int – AABB')
      pg.set_input_files('#pieceFile', [SHEET])
      pg.wait_for_function("(()=>{const its=CONTI.S.services[0].items;const it=its[its.length-1];const p=(it.pieces||[])[0];return p&&p.w>0})()", timeout=90000)
      pg.wait_for_timeout(700)
    sid = pg.evaluate("CONTI.S.services[0].id")
    pg.goto(URL + '#/view/' + sid); pg.wait_for_selector('[data-act="play"][data-stage="1"]', timeout=10000); pg.wait_for_timeout(1000)
    pg.click('[data-act="play"][data-stage="1"]'); pg.wait_for_selector('#stageWrap .stgpage', timeout=15000); pg.wait_for_timeout(900)
    pg.click('[data-stg="edit"]'); pg.wait_for_timeout(700)
    if not pg.locator('.stgpage.edit').count(): fail('편집 모드로 안 들어감')
    reset = lambda: (pg.click('[data-stg="auto"]'), pg.wait_for_timeout(1000))
    slice_id = lambda i=0: pg.evaluate(BLK + ".filter(b=>b.type==='slice'&&!b.hidden)[%d].id" % i)

    # ---- 3 꼭짓점 네 곳 손잡이
    sid0 = slice_id()
    cs = pg.evaluate("(id)=>[...document.querySelectorAll('.sblk[data-sid=\"'+CSS.escape(id)+'\"] .sgrip')].map(g=>g.dataset.c).sort()", sid0)
    if cs != ['ne','nw','se','sw']: fail('꼭짓점 손잡이가 네 개가 아님: %s' % cs)
    # 꼭짓점마다: 바깥으로 끌면 커지고, 맞은편 꼭짓점은 제자리
    OPP = {'se': ('x','y'), 'nw': ('r','b'), 'ne': ('x','b'), 'sw': ('r','y')}
    OUT = {'se': (1,1), 'nw': (-1,-1), 'ne': (1,-1), 'sw': (-1,1)}
    for cn in ['se','nw','ne','sw']:
      reset(); sid0 = slice_id()
      # 가운데 쯤으로 옮겨 두고 줄여 둔다 (어느 쪽으로 키워도 화면 안에서 보이게)
      pg.evaluate("(id)=>{const b=%s.find(x=>x.id===id);const f=0.6;b.h=b.h*f;b.w=b.w*f;b.x=0.3;b.y=0.2;"
                  "CONTI.STG.sel=[];window.dispatchEvent(new Event('resize'))}" % BLK, sid0)
      pg.wait_for_timeout(700)
      r0 = pg.evaluate(JS_RECT, sid0); g = pg.evaluate(JS_GRIP, [sid0, cn])
      if not g: fail('%s 손잡이가 없음' % cn)
      sx, sy = OUT[cn]
      drag(pg, g['x'], g['y'], sx*70, sy*70)
      r1 = pg.evaluate(JS_RECT, sid0)
      if r1['w'] < r0['w'] + 30: fail('%s 손잡이로 안 커짐: %s → %s' % (cn, r0, r1))
      ax, ay = OPP[cn]
      if abs(r1[ax] - r0[ax]) > 3 or abs(r1[ay] - r0[ay]) > 3:
        fail('%s 로 끌었는데 맞은편 꼭짓점이 움직임: %s → %s' % (cn, r0, r1))
      print('3 %s 손잡이 ok' % cn, round(r0['w']), '→', round(r1['w']))

    # ---- 2 여러 개 고른 채 크기 조절 = 모두 같은 배율, 묶음의 왼쪽 위는 제자리
    reset()
    ids = pg.evaluate(BLK + ".filter(b=>!b.hidden).map(b=>b.id)")
    a, c2 = ids[0], ids[1]
    ra = pg.evaluate(JS_RECT, a); rc = pg.evaluate(JS_RECT, c2)
    pg.mouse.click(ra['x']+20, ra['y']+10); pg.wait_for_timeout(450)
    pg.keyboard.down('Shift'); pg.mouse.click(rc['x']+20, rc['y']+10); pg.keyboard.up('Shift'); pg.wait_for_timeout(500)
    if pg.evaluate("CONTI.STG.sel.length") != 2: fail('두 개가 안 골라짐')
    w0 = pg.evaluate("(ids)=>ids.map(id=>%s.find(b=>b.id===id).w)" % BLK, [a, c2])
    box0 = pg.evaluate("(ids)=>ids.map(id=>{const r=document.querySelector('.sblk[data-sid=\"'+CSS.escape(id)+'\"]').getBoundingClientRect();return [r.x,r.y]})", [a, c2])
    gx0 = min(x for x, y in box0); gy0 = min(y for x, y in box0)
    g = pg.evaluate(JS_GRIP, [c2, 'se'])
    pg.mouse.move(g['x'], g['y']); pg.mouse.down(); pg.mouse.move(g['x']-120, g['y']-60, steps=12)
    mid = pg.evaluate("(ids)=>ids.map(id=>document.querySelector('.sblk[data-sid=\"'+CSS.escape(id)+'\"]').getBoundingClientRect().height)", [a, c2])
    pg.mouse.up(); pg.wait_for_timeout(700)
    if pg.evaluate("CONTI.STG.sel.length") != 2: fail('크기를 바꾼 뒤 선택이 풀림')
    w1 = pg.evaluate("(ids)=>ids.map(id=>%s.find(b=>b.id===id).w)" % BLK, [a, c2])
    f = [w1[i]/w0[i] for i in range(2)]
    if not (f[0] < 0.95 and f[1] < 0.95): fail('둘 다 줄어들지 않음: %s → %s' % (w0, w1))
    if abs(f[0] - f[1]) > 0.01: fail('배율이 서로 다름: %s' % f)
    box1 = pg.evaluate("(ids)=>ids.map(id=>{const r=document.querySelector('.sblk[data-sid=\"'+CSS.escape(id)+'\"]').getBoundingClientRect();return [r.x,r.y]})", [a, c2])
    if abs(min(x for x, y in box1) - gx0) > 3 or abs(min(y for x, y in box1) - gy0) > 3:
      fail('묶음의 왼쪽 위가 움직임: %s → %s' % (box0, box1))
    end = pg.evaluate("(ids)=>ids.map(id=>document.querySelector('.sblk[data-sid=\"'+CSS.escape(id)+'\"]').getBoundingClientRect().height)", [a, c2])
    if abs(mid[1] - end[1]) > 12: fail('끄는 동안 테두리 높이가 놓은 뒤와 다름: %s vs %s' % (mid, end))
    print('2 다중 크기 조절 ok', [round(x, 3) for x in f])
    print('4-a 끄는 동안 악보 테두리도 같이 줄어듦 ok', round(mid[1]), round(end[1]))   # 송폼(글)은 놓으면 줄이 다시 흐른다

    # ---- 1 화면 밖으로 걸쳐 놓기
    reset(); sid0 = slice_id(1)
    pgr = pg.evaluate(JS_PAGE)
    if pg.evaluate("getComputedStyle(document.querySelector('.stgpage')).overflow") != 'visible':
      fail('편집 중에 화면 밖 부분이 잘림')
    r0 = pg.evaluate(JS_RECT, sid0)
    # 오른쪽 아래로 크게 끌어 반쯤 밖으로
    drag(pg, r0['x']+30, r0['y']+30, (pgr['r']-r0['x'])-r0['w']/2, 200)
    bb = pg.evaluate("(id)=>{const b=%s.find(x=>x.id===id);return {x:b.x,y:b.y,w:b.w,h:b.h}}" % BLK, sid0)
    if not (bb['x'] + bb['w'] > 1.05): fail('오른쪽 가장자리 밖으로 못 나감: %s' % bb)
    if not (bb['y'] + bb['h'] > 1.05): fail('아래 가장자리 밖으로 못 나감: %s' % bb)
    if pg.evaluate("CONTI.STG.screen") != 0: fail('걸쳐 놓았는데 옆 화면으로 넘어감')
    print('1-a 오른쪽·아래로 걸쳐 놓기 ok', {k: round(v, 3) for k, v in bb.items()})
    # 위로 아주 멀리 끌어도 가장자리에 잡을 곳이 남는다 (왼쪽 위 송폼 블록과는 안 겹치게 세로로만)
    r1 = pg.evaluate(JS_RECT, sid0); pgr = pg.evaluate(JS_PAGE)
    drag(pg, r1['x']+20, r1['y']+20, -100, -(r1['y']-pgr['y']) - 400)
    bb = pg.evaluate("(id)=>{const b=%s.find(x=>x.id===id);return {x:b.x,y:b.y,w:b.w,h:b.h}}" % BLK, sid0)
    if not (bb['y'] < -0.05): fail('위 가장자리 밖으로 못 나감: %s' % bb)
    r2 = pg.evaluate(JS_RECT, sid0)
    if r2['b'] - pgr['y'] < 15: fail('위로 다 사라져 다시 잡을 곳이 없음: %s page %s' % (r2, pgr))
    # 남은 자리로 다시 잡아 끌어 올 수 있다
    drag(pg, r2['x']+20, r2['b']-8, 60, 300)
    bb2 = pg.evaluate("(id)=>%s.find(x=>x.id===id).y" % BLK, sid0)
    if not (bb2 > bb['y'] + 0.2): fail('밖에 걸친 블록을 다시 못 잡음: %s → %s' % (bb['y'], bb2))
    print('1-b 위로 밀어도 잡을 곳 남음 · 다시 끌어옴 ok', round(bb['y'], 3), '→', round(bb2, 3))
    # 화살표로 밀어도 아주 사라지지 않는다
    pg.mouse.click(r2['x']+20, pg.evaluate(JS_RECT, sid0)['y']+20); pg.wait_for_timeout(300)
    pg.keyboard.press('Escape'); pg.evaluate("(id)=>{CONTI.STG.sel=[id]}", sid0)
    for _ in range(40): pg.keyboard.press('Shift+ArrowRight')
    pg.wait_for_timeout(500)
    bx = pg.evaluate("(id)=>{const b=%s.find(x=>x.id===id);return b.x}" % BLK, sid0)
    if bx > 1 - 20/pg.evaluate("document.querySelector('.stgpage').offsetWidth"): fail('화살표로 화면 밖에 사라짐: x=%s' % bx)
    print('1-c 화살표로도 잡을 곳 남음 ok', round(bx, 3))
    # 보여 줄 때는 화면 테두리에서 잘린다 (편집 끝)
    pg.click('[data-stg="edit"]'); pg.wait_for_timeout(700)
    if pg.evaluate("getComputedStyle(document.querySelector('.stgpage')).overflow") != 'hidden':
      fail('보여 줄 때 화면 밖이 잘리지 않음')
    print('1-d 편집 끝나면 화면 테두리에서 잘림 ok')

    # ---- 4-b 숨기면 테두리도 사라지고, 남은 블록 테두리는 그대로
    pg.click('[data-stg="edit"]'); pg.wait_for_timeout(700); reset()
    ids = pg.evaluate(BLK + ".filter(b=>!b.hidden).map(b=>b.id)")
    pg.evaluate("(id)=>{CONTI.STG.sel=[id]}", slice_id()); pg.keyboard.press('Delete'); pg.wait_for_timeout(700)
    left = pg.evaluate("[...document.querySelectorAll('.sblk')].length")
    if left != len(ids) - 1: fail('숨긴 블록 테두리가 남음: %d (기대 %d)' % (left, len(ids) - 1))
    print('4-b 숨기면 테두리도 사라짐 ok')

    # ---- 4-c 편집기에서 조각을 지우면 무대의 그 조각 틀도 없어진다
    # 블록 번호가 조각 순서라, 앞 조각을 지우면 뒤 조각이 지운 조각의 자리·크기·자른 범위를 입고 나왔다
    pg.click('[data-stg="edit"]'); pg.wait_for_timeout(600); pg.click('[data-stg="exit"]'); pg.wait_for_timeout(800)
    pg.goto(URL + '#/edit/' + sid); pg.wait_for_timeout(1500)
    pg.locator('.list-item[data-act="sel-item"]').first.click(); pg.wait_for_timeout(700)
    pg.set_input_files('#pieceFile', [os.path.join(ROOT, 'docs', 'sample_stacked.jpg')])
    pg.wait_for_function("(()=>{const it=CONTI.S.services[0].items[0];return it.pieces.length===2&&it.pieces[1].w>0})()", timeout=90000)
    pg.wait_for_timeout(700)
    keep = pg.evaluate("CONTI.S.services[0].items[0].pieces[1].id")
    pg.goto(URL + '#/view/' + sid); pg.wait_for_selector('[data-act="play"][data-stage="1"]', timeout=10000); pg.wait_for_timeout(1000)
    pg.click('[data-act="play"][data-stage="1"]'); pg.wait_for_selector('#stageWrap .stgpage', timeout=15000); pg.wait_for_timeout(900)
    pg.click('[data-stg="edit"]'); pg.wait_for_timeout(700); reset()
    ALL = "CONTI.STG.layout.screens.flatMap(s=>s.blocks)"
    # 뒤 조각(악보 2)을 둘로 자른다
    pg.evaluate("(pid)=>{const S=CONTI.STG;S.screen=S.layout.screens.findIndex(s=>s.blocks.some(b=>b.pid===pid));window.dispatchEvent(new Event('resize'))}", keep)
    pg.wait_for_timeout(700)
    kid = pg.evaluate("(pid)=>%s.find(b=>b.pid===pid&&b.type==='slice').id" % BLK, keep)
    kb = pg.evaluate(JS_RECT, kid); pg.mouse.click(kb['x']+40, kb['y']+40); pg.wait_for_timeout(400)
    pg.click('.sblkmenu [data-sm="cut"]'); pg.wait_for_timeout(700)
    cut = pg.evaluate("(pid)=>%s.filter(b=>b.pid===pid).map(b=>[b.id,Math.round(b.height)])" % ALL, keep)
    if len(cut) != 2: fail('뒤 조각이 둘로 안 잘림: %s' % cut)
    pg.click('[data-stg="edit"]'); pg.wait_for_timeout(600); pg.click('[data-stg="exit"]'); pg.wait_for_timeout(800)
    # 앞 조각(악보 1)을 편집기에서 지운다
    pg.goto(URL + '#/edit/' + sid); pg.wait_for_timeout(1500)
    pg.locator('.list-item[data-act="sel-item"]').first.click(); pg.wait_for_timeout(700)
    pg.locator('[data-act="del-piece"]').first.click(); pg.wait_for_timeout(900)
    pg.goto(URL + '#/view/' + sid); pg.wait_for_selector('[data-act="play"][data-stage="1"]', timeout=10000); pg.wait_for_timeout(1000)
    pg.click('[data-act="play"][data-stage="1"]'); pg.wait_for_selector('#stageWrap .stgpage', timeout=15000); pg.wait_for_timeout(900)
    after = pg.evaluate("%s.filter(b=>b.type==='slice'&&b.idx===0).map(b=>[b.id,b.pid,Math.round(b.height)])" % ALL)
    if any(p_ != keep for _, p_, _h in after): fail('지운 조각의 블록이 남음: %s' % after)
    if sorted(h for _, _, h in after) != sorted(h for _, h in cut): fail('남은 조각 틀 크기가 달라짐: %s → %s' % (cut, after))
    print('4-c 조각을 지우면 무대 틀도 같이 없어짐 ok', after)

    if errs: fail('콘솔 오류: %s' % errs[:3])
    b.close()
  print('OK — 무대 편집 제보')
run()
