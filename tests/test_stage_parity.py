# 무대·인쇄의 조각 위 요소가 연습 화면과 같게 나오는지 — "무대 모드에서 조각들마다 마커나 마스크 등 다른 요소들도 함께"
#  · 가림(마스크)·마커 배지·전조 코드가 무대(자동 조판 · 편집 중 · 손으로 고친 조판)와 인쇄에서 보이고, 조각 안 제자리에,
#    악보 그림 위에 서고, 편집 손잡이는 가리지 않는다 (예전: 무대에는 CSS 가 없어 가림은 투명, 배지·코드는 그림 밑에 깔림)
#  · 빨간 전조 코드는 연습과 같은 글자 — 악보 키 → 연주 키로 옮기고 '여기부터 전조'를 따르며 옮길 것이 없는(0) 코드는 안 그린다
#    (예전: 인식한 코드를 그대로, 0 이어도 찍음). 무대는 내 카포까지 빼고, 인쇄(팀 종이)는 카포를 안 뺀다
#  · 무대는 연습 필터(인도자 메모·전조 코드)를 따르고, 무대 설정에 '전조 코드' 끄기가 있으며 다시 열어도 그대로다.
#    인쇄는 연습 필터와 상관없이 팀 종이 그대로
#  · 송폼 '(Key up) C' 의 Key up 이 무대·인쇄 메모 띠에도 붙는다 (예전 pgMods 는 괄호 뒤 빈칸을 몰랐다)
#   CONTI_URL=http://localhost:8766/ .venv/bin/python tests/test_stage_parity.py
#   SHOTS=<폴더> 를 주면 화면을 찍어 둔다 · PARITY_SOFT=1 이면 실패를 모아 끝에 한꺼번에 보인다(고치기 전 기록용)
import os, sys, time, json
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
SHEET = os.path.join(ROOT, 'docs', 'sample_sheet.jpg')
SHOTS = os.environ.get('SHOTS')
SOFT = os.environ.get('PARITY_SOFT') == '1'
FAILS = []
def fail(m):
    print('FAIL:', m)
    if SOFT: FAILS.append(m); return
    sys.exit(1)
def shot(pg, name, loc=None):
    if not SHOTS: return
    os.makedirs(SHOTS, exist_ok=True); p = os.path.join(SHOTS, name)
    (loc or pg).screenshot(path=p); print('  shot', p)

# 연습 화면의 빨간 코드 = 기대값 (같은 규칙으로 그려야 한다)
EXPECT0 = sorted(['F', 'C', 'G/B', 'C', 'Dm7', 'D', 'A'])

NOTE = """const addNote=async(sid,it,marker,id,text)=>{
  const r=await fetch('/api/notes',{method:'POST',credentials:'include',headers:{'content-type':'application/json','x-conti':'1'},
   body:JSON.stringify({teamId:CONTI.S.team.id,serviceId:sid,notes:[{id,itemId:it.id,markerId:marker,layer:'leader',session:null,text,at:Date.now()}]})});
  if(!r.ok)throw new Error('note '+r.status);
  it.notes=(it.notes||[]).concat([{id,marker,layer:'leader',session:null,text,author:'인도자',at:Date.now()}])};"""

# 악보 키 A → 연주 키 C (+3). 좌표는 docs/sample_sheet.jpg(1400×2089)의 오선 줄 안 — 줄 사이 여백(자르는 자리)에 걸치지 않게.
#  A(메모 → 띠) · B(메모 없음 → 배지) · C(메모 → 띠, 송폼 '(Key up) C') · D(여기부터 +2 → 그 뒤 코드 +5) · E(여기부터 −3 → 그 뒤 0 = 안 그림)
SEED = "async(sid)=>{" + NOTE + """const s=CONTI.S.services.find(x=>x.id===sid);const it=s.items[0];const p=it.pieces[0];
  p.sheetKey='A';p.keyConfirmed=true;p.offset=null;
  const mk=(id,label,y,ks)=>({id,label,x:42,y,cut:CONTI.autoCut(p,y),keyShift:ks==null?null:ks});
  p.markers=[mk('mkA','A',365),mk('mkB','B',540),mk('mkC','C',720),mk('mkD','D',890,2),mk('mkE','E',1240,-3)];
  const ch=(id,text,x,y,w)=>({id,text,x,y,w:w||30,h:30,conf:100,fixed:true});
  p.chords=[ch('c1','D',300,190),ch('c2','A',300,370),ch('c3','E/G#',700,545,60),ch('c3b','A',770,545),
            ch('c4','Bm7',300,730),ch('c5','A',300,900),ch('c6','E',300,1055),ch('c7','A',300,1250),ch('c8','D',300,1400)];
  p.hls=[{id:'h1',x:63,y:380,w:658,h:80,kind:'hl'},{id:'m1',x:84,y:276,w:1274,h:26,kind:'mask'}];
  it.notes=[];
  await addNote(sid,it,'mkA','nA'+Date.now().toString(36),'여기서 천천히');
  await addNote(sid,it,'mkC','nC'+Date.now().toString(36),'드럼 빼고');
  CONTI.save();
  return {w:p.w,h:p.h,off:CONTI.chordOffset(it,p),cuts:p.markers.map(m=>[m.label,m.cut])}}"""

# 한 화면(또는 인쇄 미리보기 전체)의 조각 위 요소를 잰다. 그림 위에 섰는지는 그 한가운데에 무엇이 맨 위로 잡히는지로 본다
# (요소들은 누르기를 막아 두어(pointer-events:none) 재는 동안만 잡히게 한다)
PROBE = """(root)=>{const R=document.querySelector(root);if(!R)return null;
 const st=document.createElement('style');st.textContent=root+' .pslice *{pointer-events:auto!important}';document.head.appendChild(st);
 const out={items:[],strips:[],grips:[]};
 R.querySelectorAll('.pslice').forEach(ps=>{ps.querySelectorAll('.mask,.hl,.pmk,.pchord').forEach(el=>{
   // 인쇄 미리보기 틀만 스크롤해 화면 가운데로. scrollIntoView 는 overflow:hidden 인 .pslice·.stgpage 까지 스크롤해
   // 그림이 밀린 채 남는다(무대는 한 화면에 다 보여 스크롤할 필요가 없다)
   if(root==='#printArea'){const r0=el.getBoundingClientRect();R.scrollTop+=r0.top-innerHeight/2;
    const ox=el.closest('.pvout');if(ox)ox.scrollLeft+=r0.left-innerWidth/2}
   const r=el.getBoundingClientRect(),pr=ps.getBoundingClientRect(),cs=getComputedStyle(el);
   // 겹침 비교용 자리는 쪽(화면) 기준 — 인쇄 미리보기는 요소마다 스크롤해서 화면 좌표끼리는 비교할 수 없다
   const pgEl=el.closest('.ppage,.stgpage'),q=pgEl.getBoundingClientRect(),pi=[...R.querySelectorAll('.ppage,.stgpage')].indexOf(pgEl);
   const t=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);
   const kind=el.classList.contains('mask')?'mask':el.classList.contains('hl')?'hl':el.classList.contains('pmk')?'pmk':'chord';
   const bd=el.querySelector('.badge');
   out.items.push({kind,text:kind==='pmk'?(el.firstChild.textContent||'').trim():(el.textContent||'').trim(),badge:bd?bd.textContent:'',
    r:[r.left-q.left,r.top-q.top,r.right-q.left,r.bottom-q.top],pg:pi,w:r.width,h:r.height,
    inside:r.left>=pr.left-1&&r.right<=pr.right+1&&r.top>=pr.top-1&&r.bottom<=pr.bottom+1,
    pos:cs.position,bg:cs.backgroundColor,disp:cs.display,vis:cs.visibility,op:+cs.opacity,z:cs.zIndex,
    top:!t?'none':(t===el||el.contains(t))?'self':t.tagName==='IMG'?'img':(t.closest('.pslice')===ps&&t.matches('.mask,.hl,.pmk,.pchord,.pmk *'))?'overlay':(t.className||t.tagName)})})});
 R.querySelectorAll('.pstrip').forEach(e=>out.strips.push(e.textContent));
 // 편집 손잡이 — 조각 위 요소가 덮으면 안 된다
 R.querySelectorAll('.sgrip').forEach(g=>{const r=g.getBoundingClientRect();const t=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);
   if(t)out.grips.push(t.matches('.mask,.hl,.pmk,.pchord,.pmk *')?'covered:'+t.className:'ok')});
 st.remove();return out}"""

def open_stage(pg, sid):
    pg.goto(URL + '#/view/' + sid)
    pg.wait_for_selector('[data-act="play"][data-stage="1"]', timeout=10000); pg.wait_for_timeout(700)
    pg.click('[data-act="play"][data-stage="1"]')
    pg.wait_for_selector('#stageWrap .stgpage', timeout=15000); pg.wait_for_timeout(700)

def close_stage(pg):
    pg.keyboard.press('Escape'); pg.wait_for_timeout(400)

def open_pop(pg):
    if not pg.locator('.stgpop').count(): pg.click('[data-stg="cfg"]')
    pg.wait_for_selector('.stgpop', timeout=5000)

def stage_all(pg):
    """무대의 모든 화면을 돌며 잰 것을 합친다 (편집 중이면 화면 띠로 넘긴다)"""
    n = pg.evaluate("CONTI.STG.nscreens")
    edit = pg.evaluate("CONTI.STG.edit")
    tot = {'items': [], 'strips': [], 'grips': [], 'screens': n}
    for i in range(n):
        if edit: pg.click('[data-sc="go"][data-i="%d"]' % i)
        else:
            while pg.evaluate("CONTI.STG.screen") > i: pg.keyboard.press('ArrowLeft'); pg.wait_for_timeout(150)
            while pg.evaluate("CONTI.STG.screen") < i: pg.keyboard.press('ArrowRight'); pg.wait_for_timeout(150)
        pg.wait_for_timeout(300)
        g = pg.evaluate(PROBE, '#stageWrap')
        for x in g['items']: x['pg'] = i   # 화면마다 따로 그린다 — 겹침은 같은 화면끼리만
        for k in ('items', 'strips', 'grips'): tot[k] += g[k]
    if edit: pg.click('[data-sc="go"][data-i="0"]')
    else:
        while pg.evaluate("CONTI.STG.screen") > 0: pg.keyboard.press('ArrowLeft'); pg.wait_for_timeout(150)
    pg.wait_for_timeout(250)
    return tot

def goto_play(pg, sid):
    # 같은 주소로 가면 hashchange 가 없어 다시 그리지 않는다 → 예배 화면을 거쳐 간다
    pg.goto(URL + '#/view/' + sid); pg.wait_for_timeout(300)
    pg.goto(URL + '#/play/' + sid + '/0'); pg.wait_for_selector('#sheet .slice', timeout=15000)

def practice_chords(pg, sid):
    goto_play(pg, sid); pg.wait_for_timeout(900)
    return sorted(pg.evaluate("[...document.querySelectorAll('#sheet .chd')].map(e=>e.textContent.trim())"))

def chords_of(g): return sorted(x['text'] for x in g['items'] if x['kind'] == 'chord')
def badges_of(g): return sorted(x['text'] for x in g['items'] if x['kind'] == 'pmk')

def check_view(name, g, want, grips=False):
    """want: 기대하는 코드 글자(정렬). 가림·배지·코드·하이라이트가 보이고, 조각 안에, 그림 위에"""
    it = g['items']
    got = chords_of(g)
    if got != want: fail('%s 전조 코드가 연습과 다름: %s ≠ %s' % (name, got, want))
    for k in ('mask', 'pmk', 'chord', 'hl'):
        if not [x for x in it if x['kind'] == k]: fail('%s 에 %s 이(가) 없음' % (name, k))
    for x in it:
        what = '%s %s %r' % (name, x['kind'], x['text'])
        if not (x['w'] > 0 and x['h'] > 0 and x['disp'] != 'none' and x['vis'] != 'hidden' and x['op'] > 0):
            fail('%s 이 안 보임: %s' % (what, x))
        if x['pos'] != 'absolute': fail('%s 이 제자리에 안 섬(position %s)' % (what, x['pos']))
        if not x['inside']: fail('%s 이 조각 밖으로 나감: %s' % (what, x['r']))
        if x['top'] not in ('self', 'overlay'): fail('%s 이 악보 그림 밑에 깔림 (맨 위: %s)' % (what, x['top']))
    masks = [x for x in it if x['kind'] == 'mask']
    if any(x['bg'] != 'rgb(255, 255, 255)' or x['op'] < 1 for x in masks): fail('%s 가림이 흰색으로 덮지 않음: %s' % (name, masks))
    b = badges_of(g)
    for lab in ('B', 'D', 'E'):
        if lab not in b: fail('%s 마커 배지 %s 가 없음: %s' % (name, lab, b))
    if 'A' in b or 'C' in b: fail('%s 띠가 선 마커(A·C)는 배지를 또 그리지 않는다: %s' % (name, b))
    st = g['strips']
    if len(st) != 2 or not any('여기서 천천히' in s for s in st) or not any('드럼 빼고' in s and 'Key up' in s for s in st):
        fail('%s 메모 띠(A · C + Key up)가 다름: %s' % (name, st))
    # 코드 라벨끼리 겹치지 않는다 (같은 줄 이웃 코드에 닿으면 위로 올린다)
    ch = [x for x in it if x['kind'] == 'chord']
    for i in range(len(ch)):
        for j in range(i + 1, len(ch)):
            a, c = ch[i]['r'], ch[j]['r']
            if ch[i]['pg'] == ch[j]['pg'] and a[0] < c[2] - 0.5 and c[0] < a[2] - 0.5 and a[1] < c[3] - 0.5 and c[1] < a[3] - 0.5:
                fail('%s 코드 라벨이 겹침: %s %s / %s %s' % (name, ch[i]['text'], a, ch[j]['text'], c))
    if grips:
        if not g['grips']: fail('%s 편집 손잡이가 없음' % name)
        bad = [x for x in g['grips'] if x != 'ok']
        if bad: fail('%s 조각 위 요소가 편집 손잡이를 덮음: %s' % (name, bad))
    print('%s ok — 코드 %s · 배지 %s · 가림 %d · 하이라이트 %d · 띠 %d' % (
        name, got, b, len(masks), len([x for x in it if x['kind'] == 'hl']), len(st)))

def open_print(pg, sid):
    pg.goto(URL + '#/view/' + sid); pg.wait_for_selector('[data-act="print"]', timeout=10000); pg.wait_for_timeout(700)
    pg.click('[data-act="print"]'); pg.wait_for_selector('#pvGo', timeout=8000)
    pg.click('#pvGo'); pg.wait_for_selector('#printArea.pv .ppage', timeout=15000); pg.wait_for_timeout(600)

def close_print(pg):
    pg.click('#printArea [data-pv="close"]'); pg.wait_for_timeout(300)

def set_capo(pg, n):
    # 카포는 서버의 내 멤버 정보다 — 화면을 옮기면 팀 정보를 다시 받아 기기 값만 바꾼 것은 덮인다
    pg.evaluate("""async(n)=>{const r=await fetch('/api/me',{method:'PATCH',credentials:'include',headers:{'content-type':'application/json','x-conti':'1'},
      body:JSON.stringify({teamId:CONTI.S.team.id,capo:n})});if(!r.ok)throw new Error('capo '+r.status);CONTI.S.team.me.capo=n;CONTI.save()}""", n)

def pf(pg, sid, k):
    """연습 화면 필터 칩을 누른다 (PL.f) — 무대도 따라야 한다"""
    goto_play(pg, sid); pg.wait_for_timeout(500)
    pg.click('[data-act="pf"][data-k="%s"]' % k); pg.wait_for_timeout(400)
    return pg.evaluate("JSON.stringify(CONTI.pl().f)")

def run():
    tag = str(int(time.time()))[-6:]
    with sync_playwright() as p:
        b = p.chromium.launch()
        c = b.new_context(viewport={'width': 1180, 'height': 820})   # iPad 가로
        pg = c.new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(repr(e)[:300])); pg.on('dialog', lambda d: d.accept())
        pg.goto(URL); pg.wait_for_selector('#lgUser')
        pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName'); pg.check('#lgAgree')
        pg.fill('#lgName', '하은'); pg.fill('#lgUser', 'sp' + tag); pg.fill('#lgPass', 'secret1'); pg.click('[data-act="lg-submit"]')
        pg.wait_for_selector('#gtTeam'); pg.fill('#gtTeam', '무대팀'); pg.click('#gtSess .q:has-text("건반")'); pg.click('[data-act="team-create"]')
        pg.wait_for_selector('.shell[data-page]', timeout=10000)
        pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]', timeout=8000)
        pg.fill('[data-f="svc.name"]', '무대 조각 요소')
        pg.click('[data-act="add-item"]'); pg.wait_for_timeout(400)
        pg.fill('[data-f="item.title"]', '우리 주 하나님'); pg.fill('[data-f="item.key"]', 'C'); pg.fill('[data-f="item.form"]', 'A – B – (Key up) C')
        pg.set_input_files('#pieceFile', [SHEET])
        pg.wait_for_function("(()=>{const p=(CONTI.S.services[0].items[0].pieces||[])[0];return p&&p.w>0})()", timeout=90000)
        pg.wait_for_timeout(800)
        sid = pg.evaluate("CONTI.S.services[0].id")
        seed = pg.evaluate(SEED, sid)
        print('준비:', json.dumps(seed, ensure_ascii=False))
        if seed['off'] != 3: fail('준비가 잘못됨 — 악보 키 A → 연주 키 C 는 +3: %s' % seed)

        # ---------- 연습 = 기대값 ----------
        P0 = practice_chords(pg, sid)
        print('연습 코드:', P0)
        if P0 != EXPECT0: fail('준비가 잘못됨 — 연습 화면 전조 코드가 예상과 다름: %s ≠ %s' % (P0, EXPECT0))
        shot(pg, 'parity_1_practice.png', pg.locator('#sheetpanel'))

        # ---------- 무대: 자동 조판 ----------
        open_stage(pg, sid)
        g = stage_all(pg)
        shot(pg, 'parity_2_stage_auto.png')
        if pg.locator('#stageWrap .stgpage .blk:has(.pslice)').count():
            shot(pg, 'parity_2b_stage_auto_slice.png', pg.locator('#stageWrap .stgpage .blk:has(.pslice)').first)
        check_view('무대 자동(%d화면)' % g['screens'], g, P0)

        # ---------- 무대: 이대로 내보내기 (무대에서 보던 그대로 종이에) ----------
        pg.click('[data-stg="export"]'); pg.wait_for_timeout(700)
        if pg.locator('#pvGo').count(): pg.click('#pvGo')
        pg.wait_for_selector('#printArea.pv .ppage', timeout=15000); pg.wait_for_timeout(600)
        check_view('무대 내보내기', pg.evaluate(PROBE, '#printArea'), P0)
        close_print(pg)

        # ---------- 무대: 편집 중 · 손으로 고친 조판 ----------
        open_stage(pg, sid)
        pg.click('[data-stg="edit"]'); pg.wait_for_timeout(900)
        g = stage_all(pg)
        shot(pg, 'parity_3_stage_edit.png')
        check_view('무대 편집 중', g, P0, grips=True)
        moved = pg.evaluate("""()=>{const L=CONTI.STG.layout;let n=0;L.screens.forEach(sc=>sc.blocks.forEach(b=>{if(b.type==='slice'){b.x+=0.01;b.w*=0.96;n++}}));return n}""")
        pg.click('[data-stg="edit"]'); pg.wait_for_timeout(900)
        if not moved or not pg.evaluate("!!CONTI.STG.layout"): fail('준비가 잘못됨 — 손으로 고친 조판이 안 생김')
        g = stage_all(pg)
        shot(pg, 'parity_4_stage_edited.png')
        check_view('무대 손으로 고친 조판', g, P0)

        # ---------- 무대 설정: 전조 코드 끄기 (저장되어 다시 열어도 그대로) ----------
        open_pop(pg)
        if not pg.locator('.stgpop input[data-stgt="chords"]').count(): fail('무대 설정에 전조 코드 켜고 끄기가 없음')
        else:
            pg.click('.stgpop input[data-stgt="chords"]'); pg.wait_for_timeout(500)
            g = stage_all(pg)
            if chords_of(g): fail('무대 설정에서 전조 코드를 껐는데 코드가 남음: %s' % chords_of(g))
            close_stage(pg); open_stage(pg, sid)
            if pg.evaluate("CONTI.STG.pref.chords") is not False: fail('전조 코드 끄기가 저장되지 않음')
            if chords_of(stage_all(pg)): fail('다시 연 무대에서 전조 코드가 다시 나옴')
            open_pop(pg)
            if pg.locator('.stgpop input[data-stgt="chords"]').is_checked(): fail('다시 연 설정 창에 전조 코드가 켜져 있음')
            pg.click('.stgpop input[data-stgt="chords"]'); pg.wait_for_timeout(500)
            if chords_of(stage_all(pg)) != P0: fail('전조 코드를 다시 켰는데 안 돌아옴')
            print('무대 전조 코드 끄기 ok — 꺼지고 · 다시 열어도 꺼져 있고 · 켜면 돌아옴')
        # 메모 띠를 끄면 A·C 는 배지로, 메모 개수 점과 함께
        open_pop(pg)
        pg.click('.stgpop input[data-stgt="memos"]'); pg.wait_for_timeout(500)
        g = stage_all(pg)
        bd = {x['text']: x['badge'] for x in g['items'] if x['kind'] == 'pmk'}
        if g['strips'] or bd.get('A') != '1' or bd.get('C') != '1' or bd.get('B') != '':
            fail('메모 띠를 끈 무대에서 A·C 배지에 메모 개수가 붙어야 함: %s · 띠 %s' % (bd, g['strips']))
        else: print('메모 띠 끈 무대 ok — 배지 %s' % bd)
        open_pop(pg); pg.click('.stgpop input[data-stgt="memos"]'); pg.wait_for_timeout(400)
        close_stage(pg)

        # ---------- 연습 필터를 무대도 따른다 ----------
        f = pf(pg, sid, 'chords')
        if '"chords":false' not in f: fail('준비가 잘못됨 — 연습 전조 코드 칩: %s' % f)
        if pg.evaluate("document.querySelectorAll('#sheet .chd').length"): fail('준비가 잘못됨 — 연습에서 코드가 안 꺼짐')
        open_stage(pg, sid)
        g = stage_all(pg)
        if chords_of(g): fail('연습에서 전조 코드를 껐는데 무대에 나옴: %s' % chords_of(g))
        open_pop(pg)
        if '연습에서 껐어요' not in pg.locator('.stgpop').inner_text(): fail('무대 설정에 연습에서 껐다는 안내가 없음')
        close_stage(pg)
        # 인쇄는 팀 종이 — 내 연습 필터를 따르지 않는다
        open_print(pg, sid)
        if chords_of(pg.evaluate(PROBE, '#printArea')) != P0: fail('연습 필터가 인쇄 전조 코드까지 끔')
        close_print(pg)
        pf(pg, sid, 'chords')
        f = pf(pg, sid, 'leader')
        if '"leader":false' not in f: fail('준비가 잘못됨 — 연습 인도자 메모 칩: %s' % f)
        open_stage(pg, sid)
        g = stage_all(pg)
        if g['strips']: fail('연습에서 인도자 메모를 껐는데 무대에 메모 띠가 나옴: %s' % g['strips'])
        bd = {x['text']: x['badge'] for x in g['items'] if x['kind'] == 'pmk'}
        if 'A' not in bd or 'C' not in bd or bd['A'] or bd['C']: fail('인도자 메모를 끈 무대에서 A·C 는 메모 없는 배지여야 함: %s' % bd)
        if chords_of(g) != P0: fail('인도자 메모만 껐는데 코드가 달라짐: %s' % chords_of(g))
        close_stage(pg)
        pf(pg, sid, 'leader')
        print('연습 필터 ok — 전조 코드·인도자 메모를 끄면 무대에도 안 나오고, 인쇄는 그대로')

        # ---------- 카포: 무대는 연습처럼 빼고, 인쇄는 안 뺀다 ----------
        set_capo(pg, 2)
        P2 = practice_chords(pg, sid)
        print('연습 코드(카포 2):', P2)
        if P2 == P0 or len(P2) != 9: fail('준비가 잘못됨 — 카포 2 연습 코드: %s' % P2)
        open_stage(pg, sid)
        g = stage_all(pg)
        if chords_of(g) != P2: fail('카포 2 무대 코드가 연습과 다름: %s ≠ %s' % (chords_of(g), P2))
        close_stage(pg)
        open_print(pg, sid)
        if chords_of(pg.evaluate(PROBE, '#printArea')) != P0: fail('인쇄(팀 종이)가 내 카포를 뺐음')
        close_print(pg)
        set_capo(pg, 0)
        print('카포 ok — 무대는 연습과 같게 %s · 인쇄는 연주 키 그대로' % P2)

        # ---------- 보통 인쇄 ----------
        open_print(pg, sid)
        g = pg.evaluate(PROBE, '#printArea')
        if SHOTS:
            pg.evaluate("()=>{const a=document.querySelector('#printArea');a.scrollTo(0,0);a.querySelector('.pvbar').style.visibility='hidden'}")
            shot(pg, 'parity_5_print.png', pg.locator('#printArea .ppage').first)
            pg.evaluate("()=>{document.querySelector('#printArea .pvbar').style.visibility=''}")
        check_view('인쇄', g, P0)
        close_print(pg)

        if errs: fail('페이지 오류: %s' % errs)
        b.close()
    if FAILS:
        print('\n실패 %d건:' % len(FAILS)); [print(' -', m) for m in FAILS]; sys.exit(1)
    print('OK test_stage_parity — 무대(자동·편집·고친 조판)·인쇄에 가림·배지·전조 코드가 연습과 같게')

run()
