# 감사 fe-10 — 무대 모드 · 연습 도구(건반·메트로놈) 제보 회귀 검사
#   F28 발행된 예배의 무대에 구간 메모 띠가 하나도 안 나옴 (내보내기도)
#   F29 앞 곡이 열을 채우면 긴 곡의 송폼 블록이 화면 밖(열 바닥 아래)에 놓임
#   F95 무대 '크기' −/+ 가 화면에서 아무 일도 안 함
#   F96 자른 블록은 저장한 범위, 이어지는 블록은 캔버스 크기 따라 바뀌어 줄이 빠지거나 두 번 나옴
#   F97 무대 조판 기기 사본이 사용자 없이 저장돼 다음 사람이 앞 사람의 글 블록을 받음
#   F98 새로고침 뒤 붙인 블록이 저장본과 같은 이름표(~c1)를 받아 끌면 옛 블록이 움직임
#   G35 같은 곡이 콘티에 두 번 — 하나를 빼면 남은 곡 악보가 두 틀에 같은 이름표로 나옴
#   F93 건반·메트로놈 패널이 화면을 옮겨도 남아 하단 탭·창을 가리고 인쇄에도 찍힘
#   F94 패널을 다시 열 때마다 클릭 처리가 쌓여 +5 가 +10, 옥타브가 두 칸
#   F138 메트로놈 빠르기를 틱마다 PATCH, 새로고침하면 90 으로 돌아감
# 되짚기 (검증에서 나온 것)
#   F28 인도자 추천 조판(띠 포함)을 메모가 다른 멤버가 열면 띠를 번호로 찾아 A 메모가 B 줄 위에 섬
#   F96 모든 블록 범위를 고정하니 화면비가 다른 캔버스에서 악보가 틀보다 길어져 화면 아래로 잘림
#   F93 연습 화면을 떠나면 패널은 닫히는데 메트로놈은 멈출 단추 없이 계속 울림
# 되짚기 2
#   F96 편집 중 그릴 때마다 줄여 그린 폭을 조판에 적어, 편집을 켰다 끄기만 해도(편집 중 화면을 돌려도) 저장한
#       캔버스(세로 화면·다른 아이패드)의 악보가 반 크기로 줄어 저장됨. 끌기·꼭짓점·±·자르기·붙이기·화면 안에 남기기는 보이는 상자로
import os, sys, time, base64, json
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
SHEET = os.path.join(ROOT, 'docs', 'sample_sheet.jpg')
tag = str(int(time.time()))[-6:]
def fail(m): print('FAIL:', m); sys.exit(1)

def signup(pg, user, name):
    pg.goto(URL); pg.wait_for_selector('#lgUser', timeout=10000)
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName')
    pg.check('#lgAgree')
    pg.fill('#lgName', name); pg.fill('#lgUser', user); pg.fill('#lgPass', 'secret1'); pg.click('[data-act="lg-submit"]')

def add_song(pg, si, title, files):
    pg.click('[data-act="add-item"]'); pg.wait_for_timeout(400)
    pg.fill('[data-f="item.title"]', title); pg.fill('[data-f="item.key"]', 'G'); pg.fill('[data-f="item.form"]', 'Int – AABB')
    pg.set_input_files('#pieceFile', files)
    pg.wait_for_function("""([si,n])=>{const its=CONTI.S.services[si].items;const it=its[its.length-1];
        const ps=it.pieces||[];return ps.length===n&&ps.every(p=>p.w>0)}""", arg=[si, len(files)], timeout=120000)
    pg.wait_for_timeout(700)

def new_service(pg, name):
    pg.goto(URL + '#/home'); pg.wait_for_selector('[data-act="new-svc"]', timeout=10000)
    pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]', timeout=8000)
    pg.fill('[data-f="svc.name"]', name); pg.wait_for_timeout(300)
    return pg.evaluate("(n)=>CONTI.S.services.findIndex(s=>s.name===n)", name)

def publish(pg):
    pg.click('[data-act="publish"]'); pg.wait_for_selector('#pubOnly', timeout=8000)
    pg.click('#pubOnly'); pg.wait_for_timeout(3000)

def open_stage(pg, sid):
    pg.goto(URL + '#/view/' + sid)
    pg.wait_for_selector('[data-act="play"][data-stage="1"]', timeout=15000); pg.wait_for_timeout(900)
    pg.click('[data-act="play"][data-stage="1"]')
    pg.wait_for_selector('#stageWrap .stgpage', timeout=15000); pg.wait_for_timeout(800)

def exit_stage(pg):
    if pg.locator('.stgpage.edit').count(): pg.click('[data-stg="edit"]'); pg.wait_for_timeout(500)
    pg.click('[data-stg="exit"]'); pg.wait_for_timeout(600)

def rerender(pg):
    pg.evaluate("window.dispatchEvent(new Event('resize'))"); pg.wait_for_timeout(500)

# 조각마다 악보 줄이 빠지거나 두 번 나오는지 (숨긴 블록은 사람이 뺀 것이라 덮은 것으로 센다, 복사본(~)은 뺀다)
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
IDS = "(()=>{const S=CONTI.STG;return (S.layout?S.layout.screens:S.lay.screens).flatMap(s=>s.blocks.map(b=>b.id))})()"
POS = "(id)=>{for(const s of CONTI.STG.layout.screens)for(const b of s.blocks)if(b.id===id)return [b.x,b.y];return null}"
FRAMES = "(()=>JSON.stringify(CONTI.STG.layout.screens.map(s=>s.blocks.map(b=>[b.id,+(+b.x).toFixed(4),+(+b.y).toFixed(4),+(+b.w).toFixed(4),+(+b.h).toFixed(4)]))))()"
# 화면에서 캔버스 아래로 넘친 블록 (.stgpage 는 넘치는 것을 잘라, 잘린 줄은 어느 화면에도 안 나온다)
CLIP = """()=>{const pg=document.querySelector('#stageWrap .stgpage');const pr=pg.getBoundingClientRect();const out=[];
 pg.querySelectorAll('.blk').forEach(e=>{const r=e.getBoundingClientRect();const ov=Math.round(r.bottom-pr.bottom);
  if(r.height>=1&&ov>1)out.push(ov)});return out}"""
# 그려진 메모 띠마다: 구간 이름, 메모 글, 띠 아래 끝과 띠가 가리키는 줄(cut)이 실제로 그려진 y 의 차이 (DOM 에서 잰다)
PLACE = """()=>{const S=CONTI.STG;const sc=(S.layout||S.lay).screens[S.screen];
 const pg=document.querySelector('#stageWrap .stgpage');const pr=pg.getBoundingClientRect();
 const vis=sc.blocks.filter(b=>!b.hidden);const els=[...pg.children];
 const rect=b=>{const e=els[vis.indexOf(b)];return e?e.getBoundingClientRect():null};
 const strips=vis.filter(b=>b.type==='strip').map(s=>{const cut=s.markers[0].cut;const sr=rect(s);
  const sl=vis.find(b=>b.type==='slice'&&!/~/.test(b.id)&&b.ranges.some(r=>r[0]-1<=cut&&cut<r[1]));
  let ly=null;if(sl){const r=rect(sl);const q=r.width/sl.pc.im.w;
   ly=r.top-pr.top+sl.ranges.reduce((a,x)=>a+Math.max(0,Math.min(x[1],cut)-x[0])*q,0)}
  return {label:s.markers.map(m=>m.label).join(''),texts:s.markers.flatMap(m=>m.vis.map(n=>n.text)).join(' '),
   gap:ly==null?null:Math.round(ly-(sr.bottom-pr.top))}});
 const st=[...pg.querySelectorAll('.pstrip')].map(e=>e.getBoundingClientRect());let ov=0;
 for(let i=0;i<st.length;i++)for(let j=i+1;j<st.length;j++){const a=st[i],b=st[j];
  if(Math.min(a.right,b.right)-Math.max(a.left,b.left)>2&&Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>2)ov++}
 return {strips,overlap:ov}}"""

def clipped(pg):
    out = []
    for s in range(pg.evaluate("CONTI.STG.nscreens||1")):
        pg.evaluate("(s)=>{CONTI.STG.screen=s;window.dispatchEvent(new Event('resize'))}", s); pg.wait_for_timeout(350)
        out += ['화면%d %dpx' % (s + 1, v) for v in pg.evaluate(CLIP)]
    pg.evaluate("CONTI.STG.screen=0;window.dispatchEvent(new Event('resize'))"); pg.wait_for_timeout(350)
    return out

def strips_ok(pg, want, what):
    # 띠마다 제 구간 메모를 달고, 띠 바로 밑(2px)이 그 줄이어야 한다. 띠끼리 겹치지 않는다
    r = pg.evaluate(PLACE)
    got = {s['label']: s for s in r['strips']}
    if sorted(got) != sorted(want): fail('%s 띠 구간이 %s (기대 %s)' % (what, sorted(got), sorted(want)))
    for lb, s in got.items():
        if want[lb] not in s['texts']: fail('%s %s 띠에 다른 메모: %s' % (what, lb, s))
        if s['gap'] is None or not -2 <= s['gap'] <= 6: fail('%s %s 띠가 제 줄 위에 없음 (띠 아래 끝과 줄 차이 %s px) %s' % (what, lb, s['gap'], r))
    if r['overlap']: fail('%s 띠끼리 겹침 %s' % (what, r))
    return r

def tall_sheet(pg):
    # 악보 한 장을 세 번 이어 붙인 긴 조각 (한 열에 안 들어가 여러 블록으로 나뉜다)
    b64 = base64.b64encode(open(SHEET, 'rb').read()).decode()
    data = pg.evaluate("""async (b64)=>{const im=new Image();im.src='data:image/jpeg;base64,'+b64;await im.decode();
        const c=document.createElement('canvas');c.width=im.width;c.height=im.height*3;const x=c.getContext('2d');
        for(let i=0;i<3;i++)x.drawImage(im,0,im.height*i);return c.toDataURL('image/jpeg',0.8).split(',')[1]}""", b64)
    return {'name': 'tall.jpg', 'mimeType': 'image/jpeg', 'buffer': base64.b64decode(data)}

def run():
  with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    ctx = b.new_context(viewport={'width': 1180, 'height': 820})   # iPad 가로
    pg = ctx.new_page()
    pg.on('pageerror', lambda e: errs.append(repr(e)[:300])); pg.on('dialog', lambda d: d.accept())
    signup(pg, 'fa' + tag, '하은')
    pg.wait_for_selector('#gtTeam', timeout=10000); pg.fill('#gtTeam', '감사팀'); pg.click('#gtSess .q:has-text("건반")')
    pg.click('[data-act="team-create"]'); pg.wait_for_selector('.shell[data-page]', timeout=15000)
    A_ID = pg.evaluate("CONTI.NET.user.id")

    # ---- 예배 1: 한 장 곡 + 두 장 곡, 첫 곡에 마커 ----
    si = new_service(pg, '감사 예배')
    add_song(pg, si, '한 장 곡', [SHEET])
    add_song(pg, si, '두 장 곡', [SHEET, SHEET])
    pg.evaluate("""(si)=>{const it=CONTI.S.services[si].items[0];const p=it.pieces[0];
      p.markers=[{id:'m1',label:'A',x:Math.round(p.w*0.08),y:Math.round(p.h*0.35),cut:null}];CONTI.save()}""", si)
    publish(pg)
    sid = pg.evaluate("(si)=>CONTI.S.services[si].id", si)
    pg.goto(URL + '#/view/' + sid); pg.wait_for_selector('[data-act="play"][data-stage="1"]', timeout=15000); pg.wait_for_timeout(1500)
    # 메모는 콘티 쪽(svc.items)에만 산다 — 발행본에는 없다.
    # id 는 서버가 받는 꼴(4자 이상)로 — 'n1' 처럼 짧으면 서버가 거절하고, 앱은 거절된 메모를 이 기기에서도 뺀다 (F50)
    pg.evaluate("""(si)=>{const it=CONTI.S.services[si].items[0];
      it.notes=[{id:'nt10a',marker:'m1',layer:'leader',text:'여기부터 천천히'}];CONTI.save()}""", si)
    if pg.evaluate("(si)=>(CONTI.S.services[si].published.items[0].notes||[]).length", si): fail('준비: 발행본에 메모가 들어 있음')
    open_stage(pg, sid)

    # ---- F28 무대에 메모 띠 ----
    strips = pg.locator('#stageWrap .pstrip').all_inner_texts()
    if not any('여기부터 천천히' in s for s in strips): fail('F28 무대에 구간 메모 띠가 없음: %s' % strips)
    cov = pg.evaluate(COV)
    if cov: fail('F28 메모 띠 밑 줄이 빠지거나 겹침: %s' % cov)
    # 띠가 제자리에 서서 보인다 (무대에 띠 CSS 가 없으면 송폼 상자 밑에 깔린다)
    seen = pg.evaluate("""()=>{const s=document.querySelector('#stageWrap .pstrip');const r=s.getBoundingClientRect();
        const hit=document.elementFromPoint(r.left+Math.min(60,r.width/2),r.top+r.height/2);
        return getComputedStyle(s).position==='absolute'&&!!hit&&!!hit.closest('.pstrip')}""")
    if not seen: fail('F28 메모 띠가 제자리에 안 보임')
    print('F28 무대 메모 띠 ok · 제자리에 보임 · 띠 밑 줄도 그대로', len(strips))
    # 내보내기(이 조판 그대로 인쇄)에도
    pg.click('[data-stg="export"]'); pg.wait_for_selector('#pvGo', timeout=8000); pg.click('#pvGo')
    pg.wait_for_selector('#printArea .ppage', timeout=15000); pg.wait_for_timeout(800)
    pt = ' '.join(pg.locator('#printArea .pstrip').all_inner_texts())
    if '여기부터 천천히' not in pt: fail('F28 무대 내보내기에 메모 띠가 없음')
    print('F28 무대 내보내기 메모 띠 ok')
    pg.evaluate("(()=>{const a=document.querySelector('#printArea');if(a)a.remove();document.body.classList.remove('printing')})()")
    open_stage(pg, sid)

    # ---- F29 송폼 블록이 화면 안에, 첫 조각과 같은 열 ----
    bad = pg.evaluate("""()=>{const S=CONTI.STG;const H=document.querySelector('#stageWrap .stgpage').offsetHeight;const bad=[];
      S.lay.screens.forEach((sc,si)=>sc.blocks.forEach(b=>{if(b.type!=='head')return;
       if(b.top+b.height>H+1)bad.push('송폼 '+b.idx+' 화면 밖 top='+Math.round(b.top)+' H='+H);
       const f=sc.blocks.find(x=>x.idx===b.idx&&x.type!=='head');
       if(!f||f.col!==b.col)bad.push('송폼 '+b.idx+' 첫 조각과 다른 열/화면')}));
      return bad}""")
    if bad: fail('F29 %s' % bad)
    heads = pg.evaluate("CONTI.STG.lay.screens.flatMap((s,i)=>s.blocks.filter(b=>b.type==='head').map(b=>[i,b.col,Math.round(b.top)]))")
    print('F29 송폼 블록 화면 안 · 첫 조각과 같은 열 ok', heads)

    # ---- F95 크기 −/+ ----
    W1 = "document.querySelector('#stageWrap .pslice').getBoundingClientRect().width"
    w1 = pg.evaluate(W1)
    pg.click('[data-stg="cfg"]'); pg.wait_for_timeout(300)
    pg.click('[data-stg="z"][data-d="-1"]'); pg.wait_for_timeout(300); pg.click('[data-stg="z"][data-d="-1"]'); pg.wait_for_timeout(500)
    if '×0.8' not in pg.inner_text('.stgpop'): fail('F95 크기 표시가 ×0.8 이 아님')
    w2 = pg.evaluate(W1)
    if not w2 < w1 * 0.9: fail('F95 ×0.8 인데 악보가 안 작아짐 %.0f → %.0f' % (w1, w2))
    for _ in range(4): pg.click('[data-stg="z"][data-d="1"]'); pg.wait_for_timeout(250)
    pg.wait_for_timeout(300)
    w3 = pg.evaluate(W1)
    shrunk = pg.evaluate("(()=>{const b=CONTI.STG.lay.screens[0].blocks.find(x=>x.type==='slice');return b.pc.im.w*b.scale<CONTI.STG.lay.cw-2})()")
    if w3 < w1 - 1: fail('F95 ×1.2 인데 ×1.0 보다 작음 %.0f → %.0f' % (w1, w3))
    for _ in range(2): pg.click('[data-stg="z"][data-d="-1"]'); pg.wait_for_timeout(250)
    pg.wait_for_timeout(300)
    w4 = pg.evaluate(W1)
    if abs(w4 - w1) > 1: fail('F95 ×1.0 으로 돌아왔는데 크기가 다름 %.0f → %.0f' % (w1, w4))
    pg.click('[data-stg="cfg"]'); pg.wait_for_timeout(300)
    print('F95 크기 ×0.8 %.0f → %.0f px · ×1.2 %.0f · ×1.0 %.0f ok' % (w1, w2, w3, w4))

    # ---- F98 새로고침 뒤 붙인 블록의 이름표 ----
    pg.click('[data-stg="edit"]'); pg.wait_for_timeout(500)
    sh = pg.evaluate("(()=>{const s=document.querySelector('.sblk .pstrip');return s?s.closest('.sblk').offsetHeight:-1})()")
    if sh < 20: fail('F28 편집 중 메모 띠 블록 높이가 %s' % sh)
    pg.evaluate("CONTI.STG.sel=['h0']")
    pg.keyboard.press('Control+c'); pg.keyboard.press('Control+v'); pg.wait_for_timeout(500)
    ids1 = pg.evaluate(IDS)
    cp1 = [i for i in ids1 if i.startswith('h0~')]
    if len(cp1) != 1: fail('F98 준비: 복사본이 안 생김 %s' % ids1)
    p1 = pg.evaluate(POS, cp1[0])
    pg.click('[data-stg="edit"]'); pg.wait_for_timeout(700)
    pg.goto(URL); pg.wait_for_selector('.shell[data-page]', timeout=15000); pg.wait_for_timeout(1500)   # 새로고침
    open_stage(pg, sid)
    pg.click('[data-stg="edit"]'); pg.wait_for_timeout(600)
    pg.evaluate("CONTI.STG.sel=['h0']")
    pg.keyboard.press('Control+c'); pg.keyboard.press('Control+v'); pg.wait_for_timeout(500)
    ids2 = pg.evaluate(IDS)
    if len(ids2) != len(set(ids2)): fail('F98 이름표가 겹침 %s' % ids2)
    cp2 = [i for i in ids2 if i.startswith('h0~') and i not in cp1]
    if len(cp2) != 1: fail('F98 새 복사본을 못 찾음 %s' % ids2)
    # 새 복사본을 끌면 새 것만 움직인다
    bb = pg.locator('.sblk[data-sid="%s"]' % cp2[0]).bounding_box()
    pg.mouse.move(bb['x'] + bb['width'] / 2, bb['y'] + 14); pg.mouse.down()
    pg.mouse.move(bb['x'] + bb['width'] / 2 + 120, bb['y'] + 14 + 70, steps=10); pg.mouse.up(); pg.wait_for_timeout(500)
    pa, pb = pg.evaluate(POS, cp1[0]), pg.evaluate(POS, cp2[0])
    if abs(pa[0] - p1[0]) > 0.002 or abs(pa[1] - p1[1]) > 0.002: fail('F98 새 복사본을 끌었는데 옛 복사본이 움직임 %s → %s' % (p1, pa))
    if abs(pb[0] - (p1[0] + 0.02)) < 0.02: fail('F98 새 복사본이 안 움직임 %s' % pb)
    print('F98 새로고침 뒤 붙인 블록 이름표 %s · 끌면 그것만 움직임 ok' % cp2[0])
    pg.click('[data-stg="edit"]'); pg.wait_for_timeout(500)
    exit_stage(pg)

    # ---- F96 자른 블록 + 캔버스 크기 바뀜 ----
    si2 = new_service(pg, '긴 곡 예배')
    add_song(pg, si2, '긴 곡', [tall_sheet(pg)])
    publish(pg)
    sid2 = pg.evaluate("(si)=>CONTI.S.services[si].id", si2)
    open_stage(pg, sid2)
    n_auto = pg.evaluate("CONTI.STG.lay.screens.flatMap(s=>s.blocks).filter(b=>b.type==='slice').length")
    if n_auto < 2: fail('F96 준비: 긴 조각이 안 나뉨 (%d)' % n_auto)
    pg.click('[data-stg="edit"]'); pg.wait_for_timeout(500)
    cid = pg.evaluate("(()=>{const S=CONTI.STG;return S.layout.screens[S.screen].blocks.find(x=>x.type==='slice').id})()")
    pg.click('.sblk[data-sid="%s"]' % cid); pg.wait_for_timeout(400)
    pg.click('.sblkmenu [data-sm="cut"]'); pg.wait_for_timeout(600)
    if len([i for i in pg.evaluate(IDS) if '#' in i]) != 2: fail('F96 준비: 자르기가 안 됨')
    pg.click('[data-stg="edit"]'); pg.wait_for_timeout(500)
    for (w, h) in [(1180, 760), (1180, 700), (1180, 900), (1100, 820), (1366, 1024), (1180, 820)]:
        pg.set_viewport_size({'width': w, 'height': h}); pg.wait_for_timeout(600)
        cov = pg.evaluate(COV)
        if cov: fail('F96 %dx%d 에서 줄이 빠지거나 두 번 나옴: %s' % (w, h, cov))
        ids = pg.evaluate(IDS)
        if len(ids) != len(set(ids)): fail('F96 %dx%d 이름표 겹침 %s' % (w, h, ids))
        # 범위가 맞아도 악보가 틀보다 길어져 화면 아래로 잘리면 그 줄은 어느 화면에도 안 나온다 (되짚기)
        cl = clipped(pg)
        if cl: fail('F96 %dx%d 에서 악보가 화면 아래로 잘림: %s' % (w, h, cl))
    pg.evaluate("CONTI.STG.pref.bar=!CONTI.STG.pref.bar"); rerender(pg)
    if pg.evaluate(COV): fail('F96 바를 끄니 줄이 빠지거나 두 번 나옴: %s' % pg.evaluate(COV))
    pg.evaluate("CONTI.STG.pref.bar=!CONTI.STG.pref.bar"); rerender(pg)
    # 예전 저장본(곡 id·범위 없이 번호만 남긴 것)도 줄이 맞아야 한다
    pg.evaluate("""(()=>{const S=CONTI.STG;S.layout={v:2,screens:S.layout.screens.map(sc=>({blocks:sc.blocks.map(b=>{
        const o={id:b.id,pid:b.pid,type:b.type,x:b.x,y:b.y,w:b.w,h:b.h};if(b.type==='slice'&&/[#~]/.test(b.id))o.ranges=b.ranges;return o})}))}})()""")
    pg.set_viewport_size({'width': 1180, 'height': 700}); pg.wait_for_timeout(700)
    if pg.evaluate(COV): fail('F96 예전 저장본에서 줄이 빠지거나 두 번 나옴: %s' % pg.evaluate(COV))
    pg.set_viewport_size({'width': 1180, 'height': 820}); pg.wait_for_timeout(600)
    if pg.evaluate(COV): fail('F96 예전 저장본 복원 뒤 크기를 바꾸니 어긋남: %s' % pg.evaluate(COV))
    print('F96 자른 블록이 있어도 캔버스 크기·바·예전 저장본에서 줄이 빠지거나 겹치지 않음 ok')
    # 되짚기 — 편집 중에도 잘리지 않는다. 줄여 그린 폭은 그릴 때만 쓰고 조판(틀)에는 적지 않는다 (되짚기 2)
    pg.set_viewport_size({'width': 1180, 'height': 700}); pg.wait_for_timeout(600)
    fr0 = pg.evaluate(FRAMES)
    pg.click('[data-stg="edit"]'); pg.wait_for_timeout(600)
    cl = clipped(pg)
    if cl: fail('F96 편집 중 악보가 화면 아래로 잘림: %s' % cl)
    if pg.evaluate(FRAMES) != fr0: fail('F96 편집을 켜기만 했는데 조판의 틀이 바뀜\n%s\n%s' % (fr0, pg.evaluate(FRAMES)))
    pg.click('[data-stg="edit"]'); pg.wait_for_timeout(600)
    exit_stage(pg)
    # 같은 기기 종류(tab-l)의 화면비가 다른 기기 — 1366x1024 에서 조금 옮겨 저장한 조판을 1180x820 에서 연다
    pg.set_viewport_size({'width': 1366, 'height': 1024}); open_stage(pg, sid2)
    pg.click('[data-stg="edit"]'); pg.wait_for_timeout(500)
    pg.click('[data-stg="auto"]'); pg.wait_for_timeout(700)
    pg.evaluate("(()=>{const S=CONTI.STG;S.sel=[S.layout.screens[0].blocks.find(b=>b.type==='slice').id]})()")
    pg.keyboard.press('ArrowRight'); pg.wait_for_timeout(500)
    pg.click('[data-stg="edit"]'); pg.wait_for_timeout(800)
    if not pg.evaluate("!!CONTI.STG.layout"): fail('F96 준비: 손으로 고친 조판이 아님')
    for (w, h) in [(1180, 820), (1180, 700)]:
        pg.set_viewport_size({'width': w, 'height': h}); pg.wait_for_timeout(700)
        cl = clipped(pg)
        if cl: fail('F96 1366x1024 에서 저장한 조판을 %dx%d 에서 여니 악보가 화면 아래로 잘림: %s' % (w, h, cl))
        if pg.evaluate(COV): fail('F96 1366x1024 조판을 %dx%d 에서 여니 줄이 빠지거나 두 번 나옴: %s' % (w, h, pg.evaluate(COV)))
    pg.set_viewport_size({'width': 1180, 'height': 820}); pg.wait_for_timeout(500)
    print('F96 되짚기 — 화면비가 다른 캔버스·다른 기기·편집 중에도 악보가 화면 아래로 잘리지 않음 ok')
    exit_stage(pg)

    # ---- F96 되짚기 2 — 줄여 그린 폭(보이기만 하는 것)이 조판에 적혀 저장한 캔버스로 돌아가도 작아진 채 남음 ----
    # 같은 아이패드의 세로·가로는 같은 기기 종류(tab-l) 조판을 쓴다. 세로에서 만든 조판을 가로에서 열면 악보를 줄여 그린다
    SAVED = "(sid)=>JSON.stringify(((CONTI.PREFS.data||{}).stage||{})['lay:'+sid+'~tab-l']||null)"
    GEOM = """()=>{const pg=document.querySelector('#stageWrap .stgpage');const pr=pg.getBoundingClientRect();
     return [...pg.querySelectorAll('.blk')].map(e=>{const r=e.getBoundingClientRect();
      return [Math.round(r.left-pr.left),Math.round(r.top-pr.top),Math.round(r.width),Math.round(r.height)]})}"""
    # 악보 블록마다 [이름표, 그린 폭, 틀 폭, 그린 높이, 틀 높이] (css px, 화면에 그린 순서 그대로)
    FIT = """()=>{const S=CONTI.STG;const sc=S.layout.screens[S.screen];const pg=document.querySelector('#stageWrap .stgpage');
     const W=pg.offsetWidth,H=pg.offsetHeight,els=[...pg.children];
     return sc.blocks.filter(b=>!b.hidden).map((b,i)=>{if(b.type!=='slice')return null;const e=els[i].querySelector('.blk')||els[i];
      return [b.id,e.offsetWidth,b.w*W,e.offsetHeight,b.h*H]}).filter(Boolean)}"""
    FR = "(id)=>{for(const s of CONTI.STG.layout.screens)for(const b of s.blocks)if(b.id===id)return [b.x,b.y,b.w,b.h];return null}"
    BOX = "(id)=>{const e=document.querySelector('.sblk[data-sid=\"'+CSS.escape(id)+'\"]');return e?[e.offsetLeft,e.offsetTop,e.offsetWidth,e.offsetHeight]:null}"
    SLICES = "(()=>{const S=CONTI.STG;return S.layout.screens[S.screen].blocks.filter(b=>b.type==='slice'&&!b.hidden).map(b=>b.id)})()"
    def edit(): pg.click('[data-stg="edit"]'); pg.wait_for_timeout(700)
    def sblk(i): return '.sblk[data-sid="%s"]' % i
    def calm(): pg.evaluate("CONTI.STG.sel=[];CONTI.STG.menu=null;window.dispatchEvent(new Event('resize'))"); pg.wait_for_timeout(450)
    def drag(sel, dx, dy, ox=None, oy=None, mid=None):
        bb = pg.locator(sel).bounding_box()
        sx = bb['x'] + (bb['width'] / 2 if ox is None else ox); sy = bb['y'] + (bb['height'] / 2 if oy is None else oy)
        pg.mouse.move(sx, sy); pg.mouse.down(); pg.mouse.move(sx + dx / 2, sy + dy / 2, steps=5)
        r = mid() if mid else None
        pg.mouse.move(sx + dx, sy + dy, steps=5); pg.mouse.up(); pg.wait_for_timeout(500); calm()
        return r
    def near(a, b, t): return all(abs(x - y) <= t for x, y in zip(a, b)) and len(a) == len(b)
    pg.set_viewport_size({'width': 820, 'height': 1180}); open_stage(pg, sid2)
    edit(); pg.click('[data-stg="auto"]'); pg.wait_for_timeout(700)
    pg.evaluate("(()=>{const S=CONTI.STG;S.sel=[S.layout.screens[0].blocks.find(b=>b.type==='head').id]})()")
    pg.keyboard.press('ArrowRight'); pg.wait_for_timeout(500)
    edit()
    L0 = pg.evaluate(SAVED, sid2); P0 = pg.evaluate(GEOM)
    if L0 == 'null': fail('F96 준비: 세로 조판이 저장되지 않음')
    pg.set_viewport_size({'width': 1180, 'height': 820}); pg.wait_for_timeout(700)
    if not any(w < fw - 20 for _, w, fw, _, _ in pg.evaluate(FIT)): fail('F96 준비: 가로에서 세로 조판 악보를 줄여 그리지 않음 %s' % pg.evaluate(FIT))
    edit(); edit()
    if pg.evaluate(SAVED, sid2) != L0: fail('F96 가로에서 편집을 켰다 끄기만 했는데 세로에서 만든 조판이 바뀜\n%s\n%s' % (L0, pg.evaluate(SAVED, sid2)))
    edit()
    pg.set_viewport_size({'width': 820, 'height': 1180}); pg.wait_for_timeout(700)
    pg.set_viewport_size({'width': 1180, 'height': 820}); pg.wait_for_timeout(700)
    edit()
    if pg.evaluate(SAVED, sid2) != L0: fail('F96 편집 중 화면을 돌렸다 돌아와 끄니 조판이 바뀜\n%s\n%s' % (L0, pg.evaluate(SAVED, sid2)))
    pg.set_viewport_size({'width': 820, 'height': 1180}); pg.wait_for_timeout(700)
    P1 = pg.evaluate(GEOM)
    if not all(near(a, b, 1) for a, b in zip(P0, P1)) or len(P0) != len(P1): fail('F96 가로에서 편집만 켰다 끈 뒤 세로 악보 크기가 바뀜 %s → %s' % (P0, P1))
    print('F96 되짚기 2 — 가로에서 편집을 켰다 끄거나 편집 중 돌려도 세로 조판·악보 크기 그대로 ok')

    # 가로에서 줄여 그린 악보를 고친다 — 편집은 보이는 상자로 재고, 조판에는 틀을 옮기거나 같은 배율로 키운 것만
    pg.set_viewport_size({'width': 1180, 'height': 820}); pg.wait_for_timeout(700); edit()
    bid = pg.evaluate(SLICES)[0]
    b0, f0 = pg.evaluate(BOX, bid), pg.evaluate(FR, bid)
    m = drag(sblk(bid), 60, 20, mid=lambda: pg.evaluate(BOX, bid))
    if abs(m[2] - b0[2]) > 1.5: fail('F96 줄여 그린 악보를 잡자마자 폭이 바뀜 %s → %s' % (b0, m))
    b1, f1 = pg.evaluate(BOX, bid), pg.evaluate(FR, bid)
    if abs(f1[2] - f0[2]) > 1e-4 or abs(f1[3] - f0[3]) > 1e-4: fail('F96 옮기기만 했는데 틀 크기가 바뀜 %s → %s' % (f0, f1))
    if f1[0] <= f0[0] or abs(b1[2] - b0[2]) > 1.5: fail('F96 옮긴 자리·폭이 이상함 %s → %s / %s → %s' % (f0, f1, b0, b1))
    # 꼭짓점: 잡은 꼭짓점의 맞은편(보이는 왼쪽 위)이 제자리에 있고, 틀은 가로세로 같은 배율로
    pg.evaluate("(id)=>{CONTI.STG.sel=[id];window.dispatchEvent(new Event('resize'))}", bid); pg.wait_for_timeout(450)
    b2, f2 = pg.evaluate(BOX, bid), pg.evaluate(FR, bid)
    drag(sblk(bid) + ' .sgrip[data-c="se"]', -40, -40)
    b3, f3 = pg.evaluate(BOX, bid), pg.evaluate(FR, bid)
    if abs(b3[0] - b2[0]) > 1.5 or abs(b3[1] - b2[1]) > 1.5: fail('F96 꼭짓점으로 줄이니 보이는 왼쪽 위가 움직임 %s → %s' % (b2, b3))
    if not b3[2] < b2[2] - 10: fail('F96 꼭짓점으로 줄여지지 않음 %s → %s' % (b2, b3))
    if abs(f3[3] / f3[2] - f2[3] / f2[2]) > 0.002: fail('F96 꼭짓점 크기 조절이 틀 비율을 바꿈 %s → %s' % (f2, f3))
    # ＋: 보이는 왼쪽 끝은 그대로, 틀은 같은 배율로
    pg.evaluate("(id)=>{CONTI.STG.sel=[id];CONTI.STG.menu=id;window.dispatchEvent(new Event('resize'))}", bid); pg.wait_for_timeout(450)
    b4 = pg.evaluate(BOX, bid)
    pg.click('.sblkmenu [data-sm="big"]'); pg.wait_for_timeout(450)
    b5, f5 = pg.evaluate(BOX, bid), pg.evaluate(FR, bid)
    if abs(b5[0] - b4[0]) > 1.5 or not b5[2] > b4[2] * 1.05: fail('F96 ＋ 가 보이는 왼쪽 끝을 옮기거나 안 커짐 %s → %s' % (b4, b5))
    if abs(f5[3] / f5[2] - f2[3] / f2[2]) > 0.002: fail('F96 ＋ 가 틀 비율을 바꿈 %s → %s' % (f2, f5))
    calm()
    # 화면 오른쪽 끝으로 끌어도 보이는 악보가 STG_KEEP(28px) 은 남는다 (틀로 재면 틀의 빈 옆자리만 남았다)
    pr, bb = pg.locator('#stageWrap .stgpage').bounding_box(), pg.locator(sblk(bid)).bounding_box()
    drag(sblk(bid), pr['x'] + pr['width'] - 8 - (bb['x'] + 10), 0, ox=10)
    b6, Wc = pg.evaluate(BOX, bid), pg.evaluate("document.querySelector('#stageWrap .stgpage').offsetWidth")
    if b6 is None: fail('F96 오른쪽 끝으로 끈 악보가 다른 화면으로 감')
    if b6[0] > Wc - 28 + 1: fail('F96 오른쪽 끝으로 끈 악보가 화면 안에 %dpx 만 남음' % (Wc - b6[0]))
    bb = pg.locator(sblk(bid)).bounding_box()
    drag(sblk(bid), pr['x'] + 20 - bb['x'], 0, ox=10)
    # 자른 두 조각을 나란히 (보이는 틈 20px) 두면 붙지 않고, 겹치면 붙는다
    pg.evaluate("(id)=>{CONTI.STG.menu=id;window.dispatchEvent(new Event('resize'))}", bid); pg.wait_for_timeout(450)
    pg.click('.sblkmenu [data-sm="cut"]'); pg.wait_for_timeout(600); calm()
    pcs = pg.evaluate(SLICES)
    if len(pcs) != 2: fail('F96 준비: 가로에서 자르기가 안 됨 %s' % pcs)
    a1, a2 = pg.locator(sblk(pcs[0])).bounding_box(), pg.locator(sblk(pcs[1])).bounding_box()
    drag(sblk(pcs[1]), a1['x'] + a1['width'] + 20 - a2['x'], a1['y'] - a2['y'], oy=30)
    if len(pg.evaluate(SLICES)) != 2: fail('F96 나란히 둔 두 조각이 (보이는 틈이 있는데) 붙어 버림')
    c1, c2 = pg.evaluate(BOX, pcs[0]), pg.evaluate(BOX, pcs[1])
    if c2[0] - (c1[0] + c1[2]) < 10: fail('F96 준비: 두 조각이 나란히 놓이지 않음 %s %s' % (c1, c2))
    a1, a2 = pg.locator(sblk(pcs[0])).bounding_box(), pg.locator(sblk(pcs[1])).bounding_box()
    drag(sblk(pcs[1]), a1['x'] + 10 - a2['x'], a1['y'] + a1['height'] - 10 - a2['y'], oy=30)
    if len(pg.evaluate(SLICES)) != 1: fail('F96 겹쳐 놓은 두 조각이 붙지 않음 %s' % pg.evaluate(SLICES))
    if pg.evaluate(COV): fail('F96 가로에서 자르고 붙인 뒤 줄이 빠지거나 두 번 나옴 %s' % pg.evaluate(COV))
    edit()
    # 세로로 돌아오면 가로에서 고친 악보도 틀을 꽉 채운다 (줄인 폭을 적었으면 좁고 밑이 빈다)
    pg.set_viewport_size({'width': 820, 'height': 1180}); pg.wait_for_timeout(700)
    for s_ in range(pg.evaluate("CONTI.STG.nscreens||1")):
        pg.evaluate("(s)=>{CONTI.STG.screen=s;window.dispatchEvent(new Event('resize'))}", s_); pg.wait_for_timeout(350)
        for (i_, w_, fw_, h_, fh_) in pg.evaluate(FIT):
            if abs(w_ - fw_) > 2 or abs(h_ - fh_) > 2: fail('F96 세로에서 악보 %s 가 틀보다 작음 (그린 %dx%d · 틀 %dx%d)' % (i_, w_, h_, fw_, fh_))
    pg.evaluate("CONTI.STG.screen=0;window.dispatchEvent(new Event('resize'))"); pg.wait_for_timeout(350)
    if pg.evaluate(COV): fail('F96 세로로 돌아오니 줄이 빠지거나 두 번 나옴 %s' % pg.evaluate(COV))
    pg.set_viewport_size({'width': 1180, 'height': 820}); pg.wait_for_timeout(500)
    print('F96 되짚기 2 — 가로에서 끌기·꼭짓점·＋·끝으로 끌기·자르기·붙이기를 보이는 대로 재고, 세로 조판은 줄지 않음 ok')
    exit_stage(pg)

    # ---- G35 같은 곡 두 번 ----
    si3 = new_service(pg, '반복 곡 예배')
    add_song(pg, si3, '여는곡', [SHEET])
    add_song(pg, si3, '가운데곡', [SHEET])
    # 라이브러리 → 예배에 넣기처럼 조각을 그대로 복사한 같은 곡을 두 번 더
    pg.evaluate("""(si)=>{const s=CONTI.S.services[si];const it=s.items[0];
      ['r1'+Date.now(),'r2'+Date.now()].forEach(id=>s.items.push({...JSON.parse(JSON.stringify(it)),id}));CONTI.save()}""", si3)
    pg.goto(URL + '#/edit/' + pg.evaluate("(si)=>CONTI.S.services[si].id", si3)); pg.wait_for_timeout(1200)
    publish(pg)
    sid3 = pg.evaluate("(si)=>CONTI.S.services[si].id", si3)
    if pg.evaluate("(si)=>new Set(CONTI.S.services[si].published.items.map(x=>x.pieces[0].id)).size", si3) != 2:
        fail('G35 준비: 같은 곡 조각 id 가 같지 않음')
    pg.set_viewport_size({'width': 1180, 'height': 820}); open_stage(pg, sid3)
    pg.click('[data-stg="edit"]'); pg.wait_for_timeout(500)
    pg.evaluate("(()=>{const S=CONTI.STG;const b=S.layout.screens[0].blocks.find(x=>x.type==='slice');b.x+=0.01})()")
    pg.click('[data-stg="edit"]'); pg.wait_for_timeout(700)   # 저장
    exit_stage(pg)
    # 첫 반복(3번째 곡)을 뺀다
    pg.evaluate("(si)=>{const s=CONTI.S.services[si];s.items.splice(2,1);CONTI.save()}", si3)
    pg.goto(URL + '#/edit/' + sid3); pg.wait_for_timeout(1200)
    publish(pg)
    open_stage(pg, sid3)
    info = pg.evaluate("""(()=>{const S=CONTI.STG;const bs=(S.layout?S.layout.screens:S.lay.screens).flatMap(s=>s.blocks).filter(b=>!b.hidden);
      return {ids:bs.map(b=>b.id),slices:bs.filter(b=>b.type==='slice').map(b=>[b.idx,b.iid]),n:CONTI.pubOrDraft(S.svc).items.length,
        iids:CONTI.pubOrDraft(S.svc).items.map(x=>x.id)}})()""")
    if len(info['ids']) != len(set(info['ids'])): fail('G35 이름표 겹침 %s' % info['ids'])
    per = {}
    for idx, iid in info['slices']: per[idx] = per.get(idx, 0) + 1
    if sorted(per.keys()) != list(range(info['n'])): fail('G35 곡마다 악보가 하나씩이 아님 %s' % info['slices'])
    if any(iid != info['iids'][idx] for idx, iid in info['slices']): fail('G35 다른 곡 악보가 들어감 %s' % info['slices'])
    if pg.evaluate(COV): fail('G35 줄이 빠지거나 겹침 %s' % pg.evaluate(COV))
    print('G35 같은 곡 두 번 → 하나 빼도 이름표·악보가 곡마다 하나 ok', per)
    exit_stage(pg)

    # ---- F93 · F94 · F138 건반·메트로놈 ----
    patches = []
    pg.on('request', lambda r: patches.append(r.url) if r.method == 'PATCH' and '/me/prefs' in r.url else None)
    pg.goto(URL + '#/play/' + sid); pg.wait_for_selector('[data-act="metro"]', timeout=15000); pg.wait_for_timeout(1000)
    pg.click('[data-act="metro"]'); pg.wait_for_timeout(500); pg.click('[data-act="metro"]'); pg.wait_for_timeout(600)
    b0 = pg.evaluate('CONTI.MET.bpm')
    pg.click('[data-act="met-d"][data-d="5"]'); pg.wait_for_timeout(300)
    if pg.evaluate('CONTI.MET.bpm') != b0 + 5: fail('F94 두 번 연 뒤 +5 가 %d' % (pg.evaluate('CONTI.MET.bpm') - b0))
    pg.click('[data-act="piano"]'); pg.wait_for_timeout(500); pg.click('[data-act="piano"]'); pg.wait_for_timeout(600)
    o0 = pg.evaluate('CONTI.PIANO.oct')
    pg.click('[data-act="oct"][data-d="1"]'); pg.wait_for_timeout(300)
    if pg.evaluate('CONTI.PIANO.oct') != o0 + 1: fail('F94 두 번 연 뒤 옥타브가 %d 칸' % (pg.evaluate('CONTI.PIANO.oct') - o0))
    print('F94 다시 열어도 +5 · 옥타브 한 칸 ok')
    # F93 창보다 아래, 인쇄에 안 찍힘, 다른 화면으로 가면 닫힘
    z = int(pg.evaluate("getComputedStyle(document.querySelector('#sidetool')).zIndex"))
    if z >= 50: fail('F93 패널이 창(.ov 50) 위에 있음: %d' % z)
    pg.emulate_media(media='print')
    if pg.evaluate("getComputedStyle(document.querySelector('#sidetool')).display") != 'none': fail('F93 인쇄에 패널이 찍힘')
    pg.emulate_media(media='screen')
    pg.evaluate("location.hash='#/home'"); pg.wait_for_timeout(700)
    if pg.locator('#sidetool').count(): fail('F93 홈으로 가도 패널이 남음')
    print('F93 패널 z %d · 인쇄 숨김 · 화면 옮기면 닫힘 ok' % z)
    # F138 슬라이더를 끌면 한 번만 저장, 새로고침 뒤에도 그 값
    pg.goto(URL + '#/play/' + sid); pg.wait_for_selector('[data-act="metro"]', timeout=15000); pg.wait_for_timeout(800)
    pg.click('[data-act="metro"]'); pg.wait_for_timeout(500)
    patches.clear()
    pg.evaluate("""(()=>{const r=document.querySelector('#metRange');for(let v=100;v<=140;v+=2){r.value=v;r.dispatchEvent(new Event('input'))}})()""")
    pg.wait_for_timeout(1500)
    if len(patches) > 1: fail('F138 슬라이더 한 번 끄는 데 PATCH %d 번' % len(patches))
    if len(patches) < 1: fail('F138 빠르기가 저장되지 않음')
    pg.goto(URL); pg.wait_for_selector('.shell[data-page]', timeout=15000); pg.wait_for_timeout(1500)   # 새로고침
    pg.goto(URL + '#/play/' + sid); pg.wait_for_selector('[data-act="metro"]', timeout=15000); pg.wait_for_timeout(800)
    pg.click('[data-act="metro"]'); pg.wait_for_timeout(1500)
    if pg.evaluate('CONTI.MET.bpm') != 140 or pg.inner_text('#metBpm').strip() != '140':
        fail('F138 새로고침 뒤 빠르기가 %s' % pg.evaluate('CONTI.MET.bpm'))
    print('F138 PATCH %d 번 · 새로고침 뒤 140 ok' % len(patches))
    # F93 되짚기 — 메트로놈은 X 로 닫아도·곡을 넘겨도 계속 울리고(연습 중 도구), 연습 화면을 떠나면 멈춘다
    pg.click('#metGo'); pg.wait_for_timeout(300)
    if not pg.evaluate('CONTI.MET.on'): fail('F93 준비: 메트로놈이 안 켜짐')
    pg.click('[data-act="sidetool-close"]'); pg.wait_for_timeout(400)
    if not pg.evaluate('CONTI.MET.on'): fail('F93 패널을 X 로 닫았는데 메트로놈이 멈춤')
    pg.locator('[data-act="pn"][data-d="1"]').first.click(); pg.wait_for_timeout(600)
    if not pg.evaluate('CONTI.MET.on'): fail('F93 연습 화면에서 곡만 넘겼는데 메트로놈이 멈춤')
    pg.evaluate("location.hash='#/home'"); pg.wait_for_timeout(600)
    if pg.evaluate('CONTI.MET.on'): fail('F93 연습 화면을 떠났는데 메트로놈이 멈출 단추 없이 계속 울림')
    print('F93 되짚기 — 닫아도·곡을 넘겨도 계속, 연습 화면을 떠나면 메트로놈 멈춤 ok')

    # ---- F28 되짚기: 인도자 추천 조판(띠 포함)을 메모가 다른 멤버가 연다 ----
    # 띠를 조각 안 순서(번호)로 찾으면 인도자의 C 띠(첫 번째) 자리에 멤버의 B 메모 띠가 섰다
    pg.set_viewport_size({'width': 1180, 'height': 820})
    si4 = new_service(pg, '추천 조판 예배')
    add_song(pg, si4, '세 구간 곡', [SHEET])
    pg.evaluate("""(si)=>{const p=CONTI.S.services[si].items[0].pieces[0];
      p.markers=['A','B','C'].map((l,i)=>({id:'mk'+l,label:l,x:40,y:Math.round(p.h*(0.22+i*0.24)),cut:null}));CONTI.save()}""", si4)
    publish(pg)
    team, sid4, it4 = pg.evaluate("(si)=>{const s=CONTI.S.services[si];return [CONTI.S.team.id,s.id,s.items[0].id]}", si4)
    def note(c, nid, mk, layer, text):
        r = c.request.post(URL + 'api/notes', headers={'x-conti': '1', 'content-type': 'application/json'}, data=json.dumps(
            {'teamId': team, 'serviceId': sid4, 'notes': [{'id': nid, 'itemId': it4, 'markerId': mk, 'layer': layer,
             'session': None, 'text': text, 'at': int(time.time() * 1000)}]}))
        if r.status != 200: fail('F28 준비: 메모 올리기 %d' % r.status)
    note(ctx, 'lc' + tag, 'mkC', 'leader', 'C크게')
    pg.evaluate("""([si,id])=>{const it=CONTI.S.services[si].items[0];
      it.notes=[{id,marker:'mkC',layer:'leader',session:null,text:'C크게',author:'하은',at:Date.now()}];CONTI.save()}""", [si4, 'lc' + tag])
    open_stage(pg, sid4)
    pg.click('[data-stg="edit"]'); pg.wait_for_timeout(500)
    pg.evaluate("(()=>{const b=CONTI.STG.layout.screens[0].blocks.find(x=>x.type==='slice');b.x+=0.01})()")
    pg.click('[data-sc="rec"]'); pg.wait_for_timeout(1500)
    rec = pg.evaluate("(sid)=>{const r=(CONTI.S.services.find(s=>s.id===sid).published.stageLayouts||{})['tab-l'];return r?r.screens.flatMap(s=>s.blocks).filter(b=>b.type==='strip').length:-1}", sid4)
    if rec != 1: fail('F28 준비: 추천 조판에 C 띠가 없음 (%s)' % rec)
    exit_stage(pg)
    invite = pg.evaluate("CONTI.S.team.invite")
    ctx2 = b.new_context(viewport={'width': 1180, 'height': 820}); M = ctx2.new_page()
    M.on('pageerror', lambda e: errs.append('멤버 ' + repr(e)[:300])); M.on('dialog', lambda d: d.accept())
    signup(M, 'fm' + tag, '민수'); M.wait_for_selector('#gtTeam', timeout=10000)
    M.goto(URL + '#/join/' + invite); M.wait_for_selector('#jnName', timeout=10000)
    M.click('[data-act="team-join"]'); M.wait_for_selector('.shell[data-page]', timeout=15000); M.wait_for_timeout(1500)
    note(ctx2, 'mb' + tag, 'mkB', 'mine', 'B내메모')
    M.goto(URL + '#/home'); M.wait_for_timeout(1500)
    open_stage(M, sid4)
    if not M.evaluate("!!CONTI.STG.layout"): fail('F28 준비: 멤버 무대에 추천 조판이 안 불러와짐')
    strips_ok(M, {'B': 'B내메모', 'C': 'C크게'}, 'F28 추천 조판을 연 멤버')
    if M.evaluate(COV): fail('F28 추천 조판을 연 멤버 악보 줄이 빠지거나 두 번 나옴 %s' % M.evaluate(COV))
    # 멤버가 제 조판으로 저장한 뒤 인도자가 앞 구간(A)에 메모를 더한다 — 새 띠도 제 줄 위에
    M.click('[data-stg="edit"]'); M.wait_for_timeout(500); M.click('[data-stg="edit"]'); M.wait_for_timeout(1200)
    exit_stage(M)
    note(ctx, 'la' + tag, 'mkA', 'leader', 'A천천히')
    M.goto(URL); M.wait_for_selector('.shell[data-page]', timeout=15000); M.wait_for_timeout(1500)   # 새로고침
    open_stage(M, sid4)
    if not M.evaluate("!!CONTI.STG.layout"): fail('F28 준비: 멤버가 저장한 조판이 안 불러와짐')
    strips_ok(M, {'A': 'A천천히', 'B': 'B내메모', 'C': 'C크게'}, 'F28 멤버 조판 저장 뒤 앞 구간에 메모가 생김')
    if M.evaluate(COV): fail('F28 새 띠를 넣은 뒤 악보 줄이 빠지거나 두 번 나옴 %s' % M.evaluate(COV))
    # 예전 저장본의 띠(줄 cut 없음)는 버리고 지금 띠를 그 줄 위에 세운다
    M.evaluate("(()=>{const S=CONTI.STG;S.layout.screens.forEach(sc=>sc.blocks.forEach(b=>{if(b.type==='strip')delete b.cut}))})()")
    rerender(M)
    strips_ok(M, {'A': 'A천천히', 'B': 'B내메모', 'C': 'C크게'}, 'F28 줄을 모르는 예전 띠')
    print('F28 되짚기 — 추천 조판·제 조판을 메모가 다른 사람이 열어도 띠마다 제 줄 위에 ok')
    ctx2.close()

    # ---- F97 여럿이 쓰는 기기: 다음 사람이 앞 사람 조판을 받지 않는다 ----
    open_stage(pg, sid)
    pg.click('[data-stg="edit"]'); pg.wait_for_timeout(500)
    pg.evaluate("window.prompt=()=>'A 개인 메모: 목사님께 말하지 말 것'")
    pg.click('[data-sc="text"]'); pg.wait_for_timeout(400)
    pg.click('[data-stg="edit"]'); pg.wait_for_timeout(800)
    keys = pg.evaluate("Object.keys(localStorage).filter(k=>k.indexOf('conti-lay:')===0)")
    if not keys or any(not k.endswith('@' + A_ID) for k in keys): fail('F97 기기 사본 키에 사용자가 없음 %s' % keys)
    invite = pg.evaluate("CONTI.S.team.invite")
    exit_stage(pg)
    # 예전 버전이 남긴 사용자 없는 사본
    pg.evaluate("(sid)=>localStorage.setItem('conti-lay:'+sid+'~tab-l',JSON.stringify({v:2,screens:[{blocks:[{id:'xold',type:'text',text:'옛 버전 개인 메모',x:0.1,y:0.1,w:0.4,h:0.08}]}]}))", sid)
    pg.goto(URL + '#/settings'); pg.wait_for_selector('.setpane', timeout=8000); pg.click('[data-act="set-tab"][data-t="app"]')
    pg.wait_for_selector('#sLogout'); pg.click('#sLogout'); pg.wait_for_selector('#lgUser', timeout=10000)
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName'); pg.check('#lgAgree')
    pg.fill('#lgName', '지우'); pg.fill('#lgUser', 'fb' + tag); pg.fill('#lgPass', 'secret1'); pg.click('[data-act="lg-submit"]')
    pg.wait_for_selector('#gtTeam', timeout=10000)
    pg.goto(URL + '#/join/' + invite); pg.wait_for_selector('#jnName', timeout=10000)
    pg.click('[data-act="team-join"]'); pg.wait_for_selector('.shell[data-page]', timeout=15000); pg.wait_for_timeout(2500)
    if pg.evaluate("CONTI.STG.clip"): fail('F97 앞 사람 복사 버퍼가 남음')
    open_stage(pg, sid)
    txt = pg.inner_text('#stageWrap')
    if '개인 메모' in txt: fail('F97 다음 사람 무대에 앞 사람 글 블록이 보임')
    if pg.evaluate("!!CONTI.STG.layout&&CONTI.STG.layout.screens.some(s=>s.blocks.some(b=>b.type==='text'))"): fail('F97 앞 사람 조판이 불러와짐')
    if pg.evaluate("(sid)=>localStorage.getItem('conti-lay:'+sid+'~tab-l')", sid) is not None: fail('F97 사용자 없는 예전 사본이 남음')
    print('F97 다음 사람은 앞 사람 조판·글 블록을 받지 않음 ok')

    if errs: fail('페이지 오류: %s' % errs[:3])
    b.close()
  print('OK — fe-10 무대 · 연습 도구')

run()
