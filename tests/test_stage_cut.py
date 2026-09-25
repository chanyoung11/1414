# 무대 조각 자르기(✂ stgCut) · 붙이기(겹쳐 놓기 stgTryMerge) — F96 과 같은 탈 (메모 띠 끼우기 stripIn 을 고친 3c41360 의 검증에서 나온 것)
#   가로에서 만든 조판을 세로에서 열면 악보는 틀 폭대로 그려지고 틀이 악보보다 길다(q>1 — 악보 밑이 빈다). 거기서 자르거나 붙이면
#   두 조각(붙인 하나)의 틀을 그린 악보 높이로 적어 틀이 좁아지지 않고 낮아지기만 해 가로세로 비율이 바뀌었고, 저장한 캔버스(가로)로
#   돌아가면 stgBlockAt 이 악보를 그 낮은 틀에 맞춰 반 크기로 줄여 그렸다. 고친 것: q>1 이면 틀 높이로 잰다 (틀 비율 그대로 —
#   저장한 캔버스에서는 틀을 꽉 채우고, 자른·붙인 캔버스에서는 원래 틀처럼 조각마다 악보 밑이 빈다)
#   1 가로 조판을 세로에서 자르기 → 세로에서 두 조각이 줄지 않음 · 가로로 돌아오면 두 조각이 틀을 꽉 채우고 원래 폭·원래 틀 안
#   2 1 의 두 조각을 세로에서 도로 붙이기 → 가로로 돌아오면 원래 틀 그대로(폭·높이)
#   3 가로에서 자른 두 조각을 세로에서 붙이기 → 가로로 돌아오면 원래 폭 (자르기와 따로 붙이기만). 붙이기·화면 안에 남기기는 보이는
#     악보로 잰다 — 아래 조각을 위 조각 바로 밑(보이는 틈)에 두면 안 붙고, 화면 위로 멀리 끌어도 보이는 악보가 28px 은 남는다
#   4 반대로 세로 조판을 가로에서(악보를 줄여 그린다 — q<1) 자르고 붙여도 세로로 돌아오면 틀을 꽉 채움 (전과 같다)
#   CONTI_URL=http://localhost:8766/ .venv/bin/python tests/test_stage_cut.py   (STAGE_CUT_PART=3 이면 3 만 — 가로·세로 둘 다)
import os, sys, time
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
SHEET = os.path.join(ROOT, 'docs', 'sample_sheet.jpg')
PART = os.environ.get('STAGE_CUT_PART', '')
tag = str(int(time.time()))[-6:]
def fail(m): print('FAIL:', m); sys.exit(1)

LAND, PORT = {'width': 1180, 'height': 820}, {'width': 820, 'height': 1180}
# 같은 아이패드의 세로·가로는 같은 기기 종류(tab-l) 조판을 쓴다
SAVED = "(sid)=>JSON.stringify(((CONTI.PREFS.data||{}).stage||{})['lay:'+sid+'~tab-l']||null)"
# 조각마다 악보 줄이 빠지거나 두 번 나오는지 (test_audit_fe_10 과 같다)
COV = """()=>{const S=CONTI.STG;const scr=S.layout?S.layout.screens:S.lay.screens;const res={};
 S.lay.screens.forEach(sc=>sc.blocks.forEach(b=>{if(b.type!=='slice')return;const k=b.idx+'.'+b.pi;
  if(!res[k])res[k]={units:b.pc.units.map(u=>[u.a,u.b]),got:[]}}));
 scr.forEach(sc=>sc.blocks.forEach(b=>{if(b.type!=='slice'||/~/.test(String(b.id)))return;const k=b.idx+'.'+b.pi;
  if(res[k])b.ranges.forEach(r=>res[k].got.push([r[0],r[1]]))}));
 const out=[];
 for(const k in res){const {units,got}=res[k];
  const pts=[...new Set(units.flat().concat(got.flat()))].sort((a,b)=>a-b);
  for(let i=0;i<pts.length-1;i++){if(pts[i+1]-pts[i]<2)continue;const m=(pts[i]+pts[i+1])/2;
   const e=units.some(r=>r[0]<=m&&m<r[1]);const g=got.filter(r=>r[0]<=m&&m<r[1]).length;
   if(e&&!g)out.push(k+' 빠짐 '+Math.round(pts[i])+'-'+Math.round(pts[i+1]));
   if(g>1)out.push(k+' 두번 '+Math.round(pts[i])+'-'+Math.round(pts[i+1]))}}
 return out}"""
# 이 화면 악보 블록마다 {id, 그린 [왼쪽, 위, 폭, 높이], 틀 [왼쪽, 위, 폭, 높이]} (css px · 편집 중 배율과 상관없이)
SL = """()=>{const S=CONTI.STG;const sc=(S.layout||S.lay).screens[S.screen];const pg=document.querySelector('#stageWrap .stgpage');
 const W=pg.offsetWidth,H=pg.offsetHeight,els=[...pg.children];
 return sc.blocks.filter(b=>!b.hidden).map((b,i)=>{if(b.type!=='slice')return null;const e=els[i].querySelector('.blk')||els[i];
  const o=els[i].classList.contains('sblk')?els[i]:e;
  return {id:b.id,d:[o.offsetLeft,o.offsetTop,e.offsetWidth,e.offsetHeight],f:[b.x*W,b.y*H,b.w*W,b.h*H]}}).filter(Boolean)}"""
# 편집 중 그린 블록 [왼쪽, 위, 폭, 높이] (css px)
BOX = "(id)=>{const e=document.querySelector('.sblk[data-sid=\"'+CSS.escape(id)+'\"]');return e?[e.offsetLeft,e.offsetTop,e.offsetWidth,e.offsetHeight]:null}"
# 여백에서 자를 수 있는 악보 블록 (stgCut 과 같은 셈)
CUTTABLE = """()=>{const S=CONTI.STG;const sc=S.layout.screens[S.screen];
 return sc.blocks.filter(b=>b.type==='slice'&&!b.hidden&&b.pc&&b.pc.units.some(u=>!u.strip&&u.a>b.ranges[0][0]+1&&u.a<b.ranges[b.ranges.length-1][1]-1)).map(b=>b.id)}"""

def run():
  with sync_playwright() as p:
    br = p.chromium.launch(); errs = []
    ctx = br.new_context(viewport=LAND)
    pg = ctx.new_page()
    pg.on('pageerror', lambda e: errs.append(repr(e)[:300])); pg.on('dialog', lambda d: d.accept())

    def open_stage(sid):
        pg.goto(URL + '#/view/' + sid)
        pg.wait_for_selector('[data-act="play"][data-stage="1"]', timeout=15000); pg.wait_for_timeout(900)
        pg.click('[data-act="play"][data-stage="1"]')
        pg.wait_for_selector('#stageWrap .stgpage', timeout=15000); pg.wait_for_timeout(800)
    def exit_stage():
        if pg.locator('.stgpage.edit').count(): pg.click('[data-stg="edit"]'); pg.wait_for_timeout(500)
        pg.click('[data-stg="exit"]'); pg.wait_for_timeout(600)
    def reload_open(vp, sid):
        # 새로고침 — 저장본으로 연다
        pg.set_viewport_size(vp); pg.goto(URL); pg.wait_for_selector('.shell[data-page]', timeout=15000); pg.wait_for_timeout(1200)
        open_stage(sid)
    def edit(): pg.click('[data-stg="edit"]'); pg.wait_for_timeout(700)
    def calm(): pg.evaluate("CONTI.STG.sel=[];CONTI.STG.menu=null;window.dispatchEvent(new Event('resize'))"); pg.wait_for_timeout(450)
    def sblk(i): return '.sblk[data-sid="%s"]' % i
    def slices(): return pg.evaluate(SL)
    def one(sl, i):
        m = [s for s in sl if s['id'] == i]
        return m[0] if m else None
    def drag(sel, dx, dy, oy=30):
        bb = pg.locator(sel).bounding_box()
        sx = bb['x'] + bb['width'] / 2; sy = bb['y'] + oy
        pg.mouse.move(sx, sy); pg.mouse.down(); pg.mouse.move(sx + 12, sy + 12, steps=3)   # 6px 넘게 움직여야 끌기다 (조금만 옮길 때도)
        pg.mouse.move(sx + dx, sy + dy, steps=5); pg.mouse.up(); pg.wait_for_timeout(500); calm()
    def cut(bid):
        pg.evaluate("(id)=>{CONTI.STG.sel=[id];CONTI.STG.menu=id;window.dispatchEvent(new Event('resize'))}", bid); pg.wait_for_timeout(450)
        pg.click('.sblkmenu [data-sm="cut"]'); pg.wait_for_timeout(600); calm()
    def merge(p1, p2):
        # 뒤 조각을 앞 조각 밑에 겹쳐 놓는다 → 도로 하나
        a1, a2 = pg.locator(sblk(p1)).bounding_box(), pg.locator(sblk(p2)).bounding_box()
        n = len(slices())
        drag(sblk(p2), a1['x'] - a2['x'], a1['y'] + a1['height'] - 12 - a2['y'])
        if len(slices()) != n - 1: fail('준비: 겹쳐 놓은 두 조각이 붙지 않음 %s' % [s['id'] for s in slices()])
        if pg.evaluate(COV): fail('붙인 뒤 줄이 빠지거나 두 번 나옴 %s' % pg.evaluate(COV))
    def root(i): return i.split('#')[0].split('~')[0]
    def mine(i): return [s for s in slices() if root(s['id']) == root(i)]
    def fills(what):
        # 저장한 캔버스에서는 악보가 틀을 꽉 채운다 (틀 비율이 바뀌면 낮은 틀에 맞춰 줄여 그려 옆·밑이 빈다)
        for s in slices():
            if abs(s['d'][2] - s['f'][2]) > 2 or abs(s['d'][3] - s['f'][3]) > 2:
                fail('%s 악보 %s 가 틀을 못 채움 — 줄여 그림 (그린 %dx%d · 틀 %dx%d)' % (what, s['id'], s['d'][2], s['d'][3], s['f'][2], s['f'][3]))
        if pg.evaluate(COV): fail('%s 줄이 빠지거나 두 번 나옴 %s' % (what, pg.evaluate(COV)))
    def make_layout(vp, sid):
        # 이 캔버스에서 손으로 고친 조판 (송폼을 조금 옮겨 저장) — 악보 틀은 여기서 그린 악보에 꼭 맞는다
        pg.set_viewport_size(vp); open_stage(sid)
        edit(); pg.click('[data-stg="auto"]'); pg.wait_for_timeout(700)
        pg.evaluate("(()=>{const S=CONTI.STG;S.sel=[S.layout.screens[0].blocks.find(b=>b.type==='head').id]})()")
        pg.keyboard.press('ArrowRight'); pg.wait_for_timeout(500)
        cands = pg.evaluate(CUTTABLE)
        if not cands: fail('준비: 자를 수 있는 악보 블록이 없음')
        bid = cands[0]
        edit()
        if pg.evaluate(SAVED, sid) == 'null': fail('준비: 조판이 저장되지 않음')
        s0 = one(slices(), bid)
        if abs(s0['d'][2] - s0['f'][2]) > 2 or abs(s0['d'][3] - s0['f'][3]) > 2: fail('준비: 만든 캔버스에서 악보가 틀에 안 맞음 %s' % s0)
        return bid, s0

    pg.goto(URL); pg.wait_for_selector('#lgUser', timeout=10000)
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName')
    pg.check('#lgAgree')
    pg.fill('#lgName', '하은'); pg.fill('#lgUser', 'sc' + tag); pg.fill('#lgPass', 'secret1'); pg.click('[data-act="lg-submit"]')
    pg.wait_for_selector('#gtTeam', timeout=10000); pg.fill('#gtTeam', '자르기팀'); pg.click('#gtSess .q:has-text("건반")')
    pg.click('[data-act="team-create"]'); pg.wait_for_selector('.shell[data-page]', timeout=15000)
    pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]', timeout=8000)
    pg.fill('[data-f="svc.name"]', '자르기 예배'); pg.wait_for_timeout(300)
    pg.click('[data-act="add-item"]'); pg.wait_for_timeout(400)
    pg.fill('[data-f="item.title"]', '자를 곡'); pg.fill('[data-f="item.key"]', 'G'); pg.fill('[data-f="item.form"]', 'Int – AABB')
    pg.set_input_files('#pieceFile', [SHEET])
    pg.wait_for_function("(()=>{const it=CONTI.S.services[0].items[0];const ps=(it&&it.pieces)||[];return ps.length===1&&ps[0].w>0})()", timeout=120000)
    pg.wait_for_timeout(700)
    pg.click('[data-act="publish"]'); pg.wait_for_selector('#pubOnly', timeout=8000); pg.click('#pubOnly'); pg.wait_for_timeout(3000)
    sid = pg.evaluate("CONTI.S.services[0].id")

    # ---- 1 다른 캔버스에서 자르기 · 2 그 두 조각을 다른 캔버스에서 도로 붙이기 ----
    # 가로 조판을 세로에서 열면 틀이 그린 악보보다 길다 (q_big — q>1). 반대는 악보를 줄여 그린다 (q<1)
    def part12(home, other, what, q_big):
        bid, s0 = make_layout(home, sid); exit_stage()
        pg.set_viewport_size(other); open_stage(sid)
        o0 = one(slices(), bid)
        if not o0: fail('준비: %s 연 조판에 악보 블록 %s 이 없음' % (what, bid))
        if q_big and not o0['d'][3] < o0['f'][3] - 20: fail('준비: %s 열어도 틀이 악보보다 길지 않음 %s' % (what, o0))
        if not q_big and not o0['d'][2] < o0['f'][2] - 20: fail('준비: %s 열어도 악보를 줄여 그리지 않음 %s' % (what, o0))
        edit()
        e0 = pg.evaluate("(id)=>{const e=document.querySelector('.sblk[data-sid=\"'+CSS.escape(id)+'\"]');return [e.offsetLeft,e.offsetTop,e.offsetWidth,e.offsetHeight]}", bid)
        cut(bid)
        pcs = sorted([s['id'] for s in mine(bid)], key=lambda i: one(slices(), i)['f'][1])
        if len(pcs) != 2: fail('준비: %s 자르기가 안 됨 %s' % (what, [s['id'] for s in slices()]))
        # 자른 캔버스에서는 두 조각이 줄지 않는다 (원래 그린 폭 그대로 · 위 조각은 제자리)
        for i in pcs:
            d = one(slices(), i)['d']
            if abs(d[2] - e0[2]) > 2: fail('%s 자른 조각 %s 이 이 캔버스에서 폭이 바뀜 %s → %s' % (what, i, e0, d))
        if abs(one(slices(), pcs[0])['d'][1] - e0[1]) > 2: fail('%s 자른 위 조각이 제자리가 아님 %s → %s' % (what, e0, one(slices(), pcs[0])['d']))
        if pg.evaluate(COV): fail('%s 자른 뒤 줄이 빠지거나 두 번 나옴 %s' % (what, pg.evaluate(COV)))
        edit(); exit_stage()
        reload_open(home, sid)
        fills('%s 자르고 돌아오니' % what)
        sl = slices(); a, b = one(sl, pcs[0]), one(sl, pcs[1])
        if not a or not b: fail('%s 자른 두 조각이 저장되지 않음 %s' % (what, [s['id'] for s in sl]))
        for s in (a, b):
            if abs(s['d'][2] - s0['d'][2]) > 2: fail('%s 자르고 돌아오니 조각 %s 폭이 바뀜 (%dpx → %dpx)' % (what, s['id'], s0['d'][2], s['d'][2]))
        H = pg.evaluate("document.querySelector('#stageWrap .stgpage').offsetHeight")
        if abs(a['d'][1] - s0['d'][1]) > 2: fail('%s 자르고 돌아오니 위 조각이 제자리가 아님 %s → %s' % (what, s0['d'], a['d']))
        if b['d'][1] < a['d'][1] + a['d'][3] - 2: fail('%s 자르고 돌아오니 두 조각이 겹침 %s / %s' % (what, a['d'], b['d']))
        # 두 조각은 원래 틀 안에 (자를 때 두는 틈 0.01 만큼은 더)
        if b['d'][1] + b['d'][3] > s0['d'][1] + s0['d'][3] + 0.01 * H + 2: fail('%s 자르고 돌아오니 두 조각이 원래 틀 밑으로 넘침 %s → %s %s' % (what, s0['d'], a['d'], b['d']))
        print('1 %s 자르고 돌아와도 악보 %dpx → %s px · 틀을 꽉 채움 ok' % (what, s0['d'][2], [a['d'][2], b['d'][2]]))
        exit_stage()

        # ---- 2 그 두 조각을 다른 캔버스에서 도로 붙이기 ----
        pg.set_viewport_size(other); open_stage(sid); edit()
        merge(pcs[0], pcs[1])
        edit(); exit_stage()
        reload_open(home, sid)
        fills('%s 자르고 붙이고 돌아오니' % what)
        mm = mine(bid)
        if len(mm) != 1: fail('준비: %s 붙인 블록을 못 찾음 %s' % (what, slices()))
        m = mm[0]['d']
        if abs(m[2] - s0['d'][2]) > 2 or abs(m[3] - s0['d'][3]) > 3: fail('%s 자르고 붙인 뒤 돌아오니 악보 크기가 바뀜 %s → %s' % (what, s0['d'], m))
        print('2 %s 자르고 도로 붙여도 돌아오면 원래 크기 %s → %s ok' % (what, s0['d'][2:], m[2:]))
        exit_stage()
    # ---- 3 만든 캔버스에서 자르고, 다른 캔버스에서 붙이기만 ----
    def part3(home, other, what):
        bid, s0 = make_layout(home, sid)
        edit(); cut(bid)
        pcs = sorted([s['id'] for s in mine(bid)], key=lambda i: one(slices(), i)['f'][1])
        if len(pcs) != 2: fail('준비: %s 만든 캔버스에서 자르기가 안 됨' % what)
        edit(); fills('%s 만든 캔버스에서 자른 뒤' % what); exit_stage()
        pg.set_viewport_size(other); open_stage(sid); edit()
        # 붙이기·화면 안에 남기기는 틀이 아니라 보이는 악보로 잰다 (세로에서는 틀이 그린 악보보다 길다 — q>1)
        #  · 아래 조각을 위 조각 바로 밑(보이는 틈 12px)에 두면 붙지 않는다 — 틀로 재면 위 조각의 빈 틀 밑자리에 놓여 붙어 버렸다
        #  · 화면 위로 멀리 끌어도 보이는 악보가 28px(STG_KEEP) 은 남는다 — 틀로 재면 틀의 빈 밑자리만 남아 악보가 사라졌다
        ek = pg.evaluate("(()=>{const p=document.querySelector('#stageWrap .stgpage');return p.getBoundingClientRect().width/p.offsetWidth})()")
        c1, c2 = pg.evaluate(BOX, pcs[0]), pg.evaluate(BOX, pcs[1])
        drag(sblk(pcs[1]), (c1[0] - c2[0]) * ek, (c1[1] + c1[3] + 12 - c2[1]) * ek)
        if len(mine(bid)) != 2: fail('%s 아래 조각을 위 조각 밑에 (보이는 틈 12px) 두었는데 붙어 버림 %s' % (what, [s['id'] for s in mine(bid)]))
        c2b = pg.evaluate(BOX, pcs[1])
        if abs(c2b[1] - (c1[1] + c1[3] + 12)) > 3: fail('준비: %s 아래 조각이 위 조각 밑으로 안 옮겨짐 %s %s' % (what, c1, c2b))
        bb = pg.locator(sblk(pcs[1])).bounding_box()   # 밑자리를 잡아 창 맨 위(y=5)까지 — 악보 밑이 캔버스 위로 나간다
        drag(sblk(pcs[1]), 0, 5 - (bb['y'] + bb['height'] - 10), oy=bb['height'] - 10)
        c2c = pg.evaluate(BOX, pcs[1])
        if c2c is None: fail('%s 위로 끈 조각이 다른 화면으로 감' % what)
        if c2c[1] + c2c[3] < 28 - 1: fail('%s 화면 위로 끈 조각이 화면 안에 %dpx 만 남음 (보이는 악보 %s)' % (what, c2c[1] + c2c[3], c2c))
        drag(sblk(pcs[1]), 0, (c2b[1] - c2c[1]) * ek, oy=(c2c[3] - 10) * ek)   # 보이는 밑자리를 잡아 제자리로
        merge(pcs[0], pcs[1])
        edit(); exit_stage()
        reload_open(home, sid)
        fills('%s 붙이고 돌아오니' % what)
        mm = mine(bid)
        if len(mm) != 1: fail('준비: %s 붙인 블록을 못 찾음 %s' % (what, slices()))
        big = mm[0]['d']
        if abs(big[2] - s0['d'][2]) > 2 or abs(big[3] - s0['d'][3]) > 3: fail('%s 붙이고 돌아오니 악보 크기가 바뀜 %s → %s' % (what, s0['d'], big))
        print('3 %s 붙이기만 해도 돌아오면 원래 크기 %s → %s ok' % (what, s0['d'][2:], big[2:]))
        exit_stage()

    for home, other, what in [(LAND, PORT, '가로 조판을 세로에서'), (PORT, LAND, '세로 조판을 가로에서')]:
        if PART in ('', '1', '2'): part12(home, other, what, home is LAND)
        if PART in ('', '3'): part3(home, other, what)

    if errs: fail('페이지 오류 %s' % errs)
    br.close()
    print('ALL OK')

run()
