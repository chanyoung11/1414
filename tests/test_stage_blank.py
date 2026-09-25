# 무대 빈 화면 (2026-09-25 실사용 제보 · 데스크톱 크롬) — 무대 편집에서 조각을 모두 숨긴 화면은 흰 쪽인데 🗑 를 누르면
# '빈 화면만 지울 수 있어요'(숨긴 블록도 블록으로 셌다)로 막혔고, 공연(무대 보기)에서도 그 흰 쪽을 넘겨야 했다.
# 고친 것(최소 · 송폼 '조각 위'(기본)에서만): 보이는 블록(숨기지 않은 송폼·악보·메모 띠·글이 있는 글)이 없는 화면을
#  · 보기에서는 넘김(← → · 탭 · 앞뒤 단추)·쪽 번호 n/m·처음 여는 화면·내보내기 종이에서 건너뛴다 — 조판(저장본)은 지우지도 번호를 바꾸지도 않는다
#  · 편집에서는 🗑 로 지울 수 있다 — 숨긴 블록은 숨긴 채 앞 화면(첫 화면이면 뒤 화면)으로, '숨김 되돌리기'는 제 화면을 새로 만들어 제자리에
# 그 밖에는 화면을 저절로 지우지 않는다 (앞선 시도들이 옮기기·숨기기·저장·열기마다 지워 송폼 모드·새 곡 자리·되돌리기 순서가 어긋났다).
# 다른 송폼 모드(자동·상단 바·숨김)는 곡 제목이 바·off 에 있어 캔버스가 비어도 그 곡 화면이다 — 고치기 전(main)과 똑같이 둔다
# (건너뛰면 악보 없는 첫 곡 제목이 무대에 안 나왔고, 🗑 가 제목만 남은 화면의 제목을 숨겼다)
# 1부 — 데스크톱 · 조각 위
#   1 제보 그대로 — 마지막 화면을 모두 숨기면 편집에서는 그대로 두고, 보기(새로고침 뒤에도)·내보내기에서 건너뛴다
#   2 가운데 화면이 비면 → ← · 탭 · 앞뒤 단추가 건너뛴다 · 첫 화면이 비면 다음 화면으로 연다 · 모두 비면 첫 화면 하나
#   3 🗑 — 숨긴 블록만 남은 화면을 지운다 (숨긴 블록은 숨긴 채 앞 화면에 · 새로고침 뒤에도) · 보이는 블록이 있으면 막는다 ·
#     숨김 되돌리기는 제 화면으로 (다른 곡 위에 안 겹친다)
#   4 첫 화면을 🗑 (잇달아 두 번) → 되돌려도 화면 순서 그대로
#   5 조각 위에서 🗑 로 옮긴 무리가 있는 조판을 숨김·자동·상단 바로 보면 그저 숨긴 블록(블록이 있으면 🗑 가 막고 모든 화면을 넘김 ·
#     블록을 잃지 않음 · 그 모드로 저장·새로고침해도) → 조각 위로 돌아와 되돌리면 제 화면·제 순서. 다른 모드에서 되돌리면
#     고치기 전처럼 제자리에서(송폼 모드가 뺀 숨긴 송폼은 숨긴 채) — 조각 위로 돌아와 되돌려도 잃는 블록 없음
#   6 자른 반쪽을 숨겨 🗑 로 남은 반쪽 화면에 옮긴 뒤 남은 반쪽을 끌어도 숨긴 반쪽과 안 붙는다
#   7 블록을 › 로 모두 보냈다 ‹ 로 되돌리면 전과 같다 (빈 화면을 저절로 지우지 않는다 — 고치기 전과 같다)
# 2부 — 세로 태블릿(1열 · 곡마다 한 화면) · 악보 없는 곡(송폼만) 하나. 고치기 전 앱(main 의 app/index.html — 이 고침을 들인 커밋의 앞
#   커밋, STAGE_BLANK_BASE=<rev> 로 바꿀 수 있다)을 Playwright route 로 띄운 브라우저와 지금 앱을 나란히 같은 순서로 몰아 견준다
#   8 자동 조판 · 송폼 자동/상단 바/숨김 · 악보 없는 곡이 첫·가운데·끝 — 처음 여는 화면 · 넘김(단추·←→ 키·탭)·쪽 번호 · 내보내기 ·
#     🗑 (제목만 남은 곡 화면) · 저장본 · 다시 넘김 이 main 과 같다
#   9 저장한 조판(조각 위로 고친 것) · 송폼 자동/상단 바/숨김 — 여는 화면 · 넘김 · 모두 숨긴 화면의 🗑(블록이 있어 막힘) · 넘김(흰 쪽도
#     main 처럼) · 내보내기 · 제목만 남은 곡 화면 🗑 · 숨김 되돌리기 · 저장본 이 main 과 같다
#  10 저장한 조판 · 송폼 자동/상단 바/숨김으로 악보 없는 곡과 악보 있는 곡을 (두 차례로) 더한 뒤 여는 화면 · 넘김 · 조각 위로
#     되돌린 조판이 main 과 같고 겹침 없이 곡마다 한 화면
#  11 (지금 앱만 · 조각 위) 악보 없는 곡의 블록을 › 로 보냈다 ‹ 로 되돌리면 전과 같다 · 송폼이 선 악보 없는 곡 화면은 안 건너뛰고,
#     그 다음 화면을 모두 숨겨 🗑 로 지우고 되돌려도 그 송폼 화면에 넣지 않는다
#   CONTI_URL=http://localhost:8766/ .venv/bin/python tests/test_stage_blank.py   (STAGE_BLANK_PART=1|2 로 한쪽만)
import os, re, sys, time, json, subprocess, threading
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
SHEET = os.path.join(ROOT, 'docs', 'sample_sheet.jpg')
PART = os.environ.get('STAGE_BLANK_PART', '')
tag = str(int(time.time()))[-6:]
def fail(m):
    th = threading.current_thread().name
    print('FAIL:', ('[%s] ' % th if th != 'MainThread' else '') + m); sys.exit(1)

BLK = "CONTI.STG.layout.screens[CONTI.STG.screen].blocks"
# 지금 상태: 화면마다 [블록 수, 보이는 블록 수] · 숨긴 블록 수 (조판이 없으면 자동 조판)
ST = """()=>{const S=CONTI.STG;const L=S.layout;const scr=L?L.screens:S.lay.screens;
 const vis=sc=>sc.blocks.filter(b=>!b.hidden&&!(b.type==='text'&&!String(b.text||'').trim())).length;
 return {screen:S.screen,n:S.nscreens,edit:S.edit,total:scr.length,cnt:scr.map(sc=>[sc.blocks.length,vis(sc)]),
  hidden:scr.reduce((a,sc)=>a+sc.blocks.filter(b=>b.hidden).length,0)}}"""
# 화면마다 보이는 블록 id (차례대로)
IDS = "()=>CONTI.STG.layout.screens.map(sc=>sc.blocks.filter(b=>!b.hidden).map(b=>b.id))"
# 조판의 모든 블록 id (숨긴 것 · 송폼 모드가 뺀 것까지)
ALLIDS = "()=>{const L=CONTI.STG.layout;return [].concat(...L.screens.map(sc=>sc.blocks.map(b=>String(b.id))),(L.off||[]).map(o=>String(o.b.id))).sort()}"
# 화면마다 보이는 곡 번호 (조판이 없으면 자동 조판)
SONGS = """()=>{const L=CONTI.STG.layout;const scr=L?L.screens:CONTI.STG.lay.screens;
 return scr.map(sc=>[...new Set(sc.blocks.filter(b=>!b.hidden&&b.idx!=null).map(b=>b.idx))].sort((a,b)=>a-b))}"""
# 한 화면에서 다른 곡끼리 겹친 보이는 블록 [화면, 블록, 블록, 가로, 세로]
OVL = """()=>{const out=[];const L=CONTI.STG.layout;if(!L)return out;L.screens.forEach((sc,i)=>{const v=sc.blocks.filter(b=>!b.hidden&&b.idx!=null);
 v.forEach((a,ai)=>v.forEach((b,bi)=>{if(bi<=ai||a.idx===b.idx)return;
  const ix=Math.min(a.x+a.w,b.x+b.w)-Math.max(a.x,b.x),iy=Math.min(a.y+a.h,b.y+b.h)-Math.max(a.y,b.y);
  if(ix>0.01&&iy>0.01)out.push([i,a.id,b.id,+ix.toFixed(2),+iy.toFixed(2)])}))});return out}"""
# 제 곡 악보는 다른 화면에 두고, 다른 곡 악보가 있는 화면에 선 송폼 [화면, 송폼]
MIS = """()=>{const out=[];const L=CONTI.STG.layout;if(!L)return out;const scr=L.screens;
 const has=new Set([].concat(...scr.map(sc=>sc.blocks.filter(b=>!b.hidden&&b.type!=='head'&&b.idx!=null).map(b=>b.idx))));
 scr.forEach((sc,i)=>{const v=sc.blocks.filter(b=>!b.hidden);
 const music=new Set(v.filter(b=>b.type!=='head'&&b.idx!=null).map(b=>b.idx));
 v.filter(b=>b.type==='head'&&music.size&&!music.has(b.idx)&&has.has(b.idx)).forEach(h=>out.push([i,h.id]))});return out}"""
# 저장본 (서버로 보낼 값 = PREFS) — 화면마다 [블록 수, 보이는 블록 수]
SAVED = """(slot)=>{const v=((CONTI.PREFS.data||{}).stage||{})[slot];
 return v&&v.screens?v.screens.map(s=>[(s.blocks||[]).length,(s.blocks||[]).filter(b=>!b.hidden).length]):null}"""
PUT_LAY = """async([slot,v])=>{const r=await fetch('/api/me/prefs/stage/'+encodeURIComponent(slot),{method:'PUT',credentials:'same-origin',
  headers:{'x-conti':'1','content-type':'application/json'},body:JSON.stringify({value:v})});
 if(!r.ok)throw new Error('put '+r.status);
 CONTI.PREFS.data.stage=CONTI.PREFS.data.stage||{};CONTI.PREFS.data.stage[slot]=v;
 localStorage.setItem('conti-'+slot+'@'+CONTI.NET.user.id,JSON.stringify(v))}"""
# ---- main 과 견줄 값 (곡·조각 id(pid·iid)와 🗑 무리 id 는 사람마다 달라 뺀다) ----
# 보기: [화면, 바의 곡, 넘겨 볼 화면 수, 쪽 번호, 바 제목, 바 송폼, ← 막힘, → 막힘, 그린 블록 수]
VIEW = r"""()=>{const S=CONTI.STG;const q=s=>document.querySelector('#stageWrap '+s);const t=s=>{const e=q(s);return e?e.textContent.replace(/\s+/g,' ').trim():null};
 return [S.screen,S.idx,S.nscreens,t('.stgpg'),t('.stgbar b'),t('.stgform'),!!q('[data-stg="prev"][disabled]'),!!q('[data-stg="next"][disabled]'),
  document.querySelectorAll('#stageWrap .stgpage .blk').length]}"""
# 조판: 화면마다 블록 [id, 종류, 숨김, x, y, w, h] · 송폼 모드가 뺀 송폼 [화면, id, 숨김] · 화면 띠 글(숨김 N개 되돌리기 · 화면마다 보이는 수)
LAYX = r"""()=>{const S=CONTI.STG,L=S.layout;const r=v=>+(+(v||0)).toFixed(3);
 const bl=b=>[String(b.id),b.type,!!b.hidden,r(b.x),r(b.y),r(b.w),r(b.h)];
 const st=document.querySelector('#stageWrap .stgstrip');
 return {screen:S.screen,n:S.nscreens,edit:S.edit,custom:!!L,
  scr:L?L.screens.map(sc=>sc.blocks.map(bl)):S.lay.screens.map(sc=>sc.blocks.map(b=>[String(b.id),b.type,!!b.hidden])),
  off:L&&L.off?L.off.map(o=>[o.s,String(o.b.id),!!o.b.hidden]):null,
  strip:st?st.textContent.replace(/\s+/g,' ').trim():null}}"""
SAVEDX = """(slot)=>{const v=((CONTI.PREFS.data||{}).stage||{})[slot];
 return v==null?null:JSON.parse(JSON.stringify(v,(k,x)=>k==='pid'||k==='iid'||k==='lone'?undefined:x))}"""
REORDER = "(ts)=>{const s=CONTI.S.services[0];const by={};s.items.forEach(it=>{by[it.title]=it});s.items=ts.map(t=>by[t]).filter(Boolean);CONTI.save()}"
HAS_FIX = "[...document.scripts].some(s=>s.textContent.includes('stgBlockForm'))"
FORMS = ('auto', 'bar', 'hide')

def signup(pg, user, name):
    pg.goto(URL); pg.wait_for_selector('#lgUser', timeout=10000)
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName')
    pg.check('#lgAgree')
    pg.fill('#lgName', name); pg.fill('#lgUser', user); pg.fill('#lgPass', 'secret1'); pg.click('[data-act="lg-submit"]')

def new_team_service(pg, user, svc):
    signup(pg, user, '하은')
    pg.wait_for_selector('#gtTeam'); pg.fill('#gtTeam', '무대팀'); pg.click('#gtSess .q:has-text("건반")'); pg.click('[data-act="team-create"]')
    pg.wait_for_selector('.shell[data-page]', timeout=10000)
    pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]', timeout=8000)
    pg.fill('[data-f="svc.name"]', svc)

def add_song(pg, title):
    pg.click('[data-act="add-item"]'); pg.wait_for_timeout(400)
    pg.fill('[data-f="item.title"]', title); pg.fill('[data-f="item.key"]', 'G'); pg.fill('[data-f="item.form"]', 'Int – AABB')
    pg.set_input_files('#pieceFile', [SHEET])
    pg.wait_for_function("(t)=>{const it=CONTI.S.services[0].items.find(x=>x.title===t);const p=it&&(it.pieces||[])[0];return p&&p.w>0}", arg=title, timeout=90000)
    pg.wait_for_timeout(700)

def add_song_bare(pg, title):
    # 악보 없는 곡 (제목·키·송폼만)
    pg.click('[data-act="add-item"]'); pg.wait_for_timeout(400)
    pg.fill('[data-f="item.title"]', title); pg.fill('[data-f="item.key"]', 'A'); pg.fill('[data-f="item.form"]', 'V – C')
    pg.wait_for_timeout(700)

def open_stage(pg, sid):
    pg.goto(URL + '#/view/' + sid)
    pg.wait_for_selector('[data-act="play"][data-stage="1"]', timeout=15000); pg.wait_for_timeout(900)
    pg.click('[data-act="play"][data-stage="1"]')
    pg.wait_for_selector('#stageWrap .stgpage', timeout=15000); pg.wait_for_timeout(1500)

def exit_stage(pg):
    # 편집을 끄지 않고 나간다 (편집을 끄면 지금 조판을 저장한다)
    pg.click('[data-stg="exit"]'); pg.wait_for_timeout(700)

def edit_on(pg):
    if not pg.locator('.stgpage.edit').count(): pg.click('[data-stg="edit"]'); pg.wait_for_timeout(700)

def edit_off(pg):
    if pg.locator('.stgpage.edit').count(): pg.click('[data-stg="edit"]'); pg.wait_for_timeout(900)

def rerender(pg):
    pg.evaluate("window.dispatchEvent(new Event('resize'))"); pg.wait_for_timeout(500)

def goto_screen(pg, i):
    pg.click('.sthumb[data-i="%d"]' % i); pg.wait_for_timeout(450)

def reload(pg):
    pg.reload(); pg.wait_for_function("!!(window.CONTI&&CONTI.NET&&CONTI.NET.user)", timeout=15000); pg.wait_for_timeout(1500)

def toast(pg): return pg.evaluate("document.querySelector('#toast').textContent")

def auto_again(pg):
    edit_on(pg); pg.click('[data-stg="auto"]'); pg.wait_for_timeout(1000)

def set_form(pg, f):
    # 편집 띠의 송폼 모드 단추로 돈다 (자동 → 상단 바 → 조각 위 → 숨김)
    for _ in range(5):
        if pg.evaluate("CONTI.STG.pref.form") == f: return
        pg.click('[data-sc="form"]'); pg.wait_for_timeout(450)
    fail('송폼 모드를 %s 로 못 바꿈' % f)

def open_menu(pg, bid):
    pg.evaluate("(id)=>{CONTI.STG.menu=id;CONTI.STG.sel=[id];window.dispatchEvent(new Event('resize'))}", bid); pg.wait_for_timeout(450)

def hide_all_here(pg):
    # 지금 화면의 보이는 블록을 하나씩 골라 Delete (숨기기)
    for i in pg.evaluate(BLK + ".filter(b=>!b.hidden).map(b=>b.id)"):
        pg.evaluate("(id)=>{CONTI.STG.sel=[id];CONTI.STG.menu=null}", i); pg.keyboard.press('Delete'); pg.wait_for_timeout(300)
    if pg.evaluate(BLK + ".some(b=>!b.hidden)"): fail('준비: 화면의 블록을 다 못 숨김')

def trash(pg):
    pg.click('[data-sc="del"]'); pg.wait_for_timeout(450)

def show_all(pg):
    pg.click('[data-sc="show"]'); pg.wait_for_timeout(600)

def nudge(pg):
    # 손으로 고친 조판으로 (지금 화면 첫 블록을 → 로 조금 · 저장된다)
    ids = pg.evaluate(BLK + ".filter(b=>!b.hidden).map(b=>b.id)")
    pg.evaluate("(id)=>{CONTI.STG.sel=[id];CONTI.STG.menu=null}", ids[0]); pg.keyboard.press('ArrowRight'); pg.wait_for_timeout(600)
    pg.evaluate("CONTI.STG.sel=[]")

def label(pg): return pg.inner_text('#stageWrap .stgpg').split(' ')[0]

def drawn(pg): return pg.evaluate("document.querySelectorAll('#stageWrap .stgpage .blk').length")

def walk(pg, what):
    # 보기: 넘겨 볼 첫 화면부터 → 단추로 끝까지 — 쪽마다 무엇이든 그려져 있고 쪽 번호가 1/n … n/n
    st = pg.evaluate(ST)
    if st['edit']: fail('%s 편집 중에 walk' % what)
    n = st['n']
    pg.evaluate("(()=>{const S=CONTI.STG;S.screen=(S.nav||[0])[0];window.dispatchEvent(new Event('resize'))})()"); pg.wait_for_timeout(500)
    seen = []
    for k in range(n):
        if not drawn(pg): fail('%s %d번째 쪽이 흰 쪽 (%s) %s' % (what, k + 1, label(pg), pg.evaluate(ST)))
        if label(pg) != '%d/%d' % (k + 1, n): fail('%s 쪽 번호가 이상함: %s (기대 %d/%d) %s' % (what, label(pg), k + 1, n, pg.evaluate(ST)))
        seen.append(pg.evaluate("CONTI.STG.screen"))
        if k < n - 1:
            pg.click('[data-stg="next"]'); pg.wait_for_timeout(350)
    if not pg.locator('[data-stg="next"][disabled]').count(): fail('%s 마지막 쪽인데 → 가 살아 있음' % what)
    return seen

def export_pages(pg):
    pg.click('[data-stg="export"]'); pg.wait_for_selector('#pvGo', timeout=8000)
    pg.click('#pvGo'); pg.wait_for_selector('#printArea.pv .ppage', timeout=15000); pg.wait_for_timeout(600)
    n = pg.locator('#printArea .ppage').count()
    blank = pg.evaluate("[...document.querySelectorAll('#printArea .ppage')].filter(p=>!p.querySelector('.blk,.pslice,.pstrip')).length")
    pg.click('#printArea [data-pv="close"]'); pg.wait_for_timeout(400)
    return n, blank

def clean(pg, what, songs=None):
    ov, mi = pg.evaluate(OVL), pg.evaluate(MIS)
    if ov or mi: fail('%s 다른 곡 위에 겹침 %s · 남의 화면에 선 송폼 %s · 곡 %s' % (what, ov, mi, pg.evaluate(SONGS)))
    if songs is not None and pg.evaluate(SONGS) != songs: fail('%s 화면마다 곡이 다름: %s (기대 %s)' % (what, pg.evaluate(SONGS), songs))

# 조각 위 송폼이 제 곡 악보가 없는 화면에 보이면 = 다른 곡 악보 위에 겹쳐 선 것
STACK = """()=>{const out=[];CONTI.STG.layout.screens.forEach((sc,i)=>{const vis=sc.blocks.filter(b=>!b.hidden);
 const music=new Set(vis.filter(b=>b.type!=='head').map(b=>b.idx));
 vis.filter(b=>b.type==='head'&&!music.has(b.idx)).forEach(h=>out.push([i,h.id,+(+h.x).toFixed(2),+(+h.y).toFixed(2)]))});return out}"""

def run1():
    with sync_playwright() as p:
        b = p.chromium.launch()
        c = b.new_context(viewport={'width': 1600, 'height': 1000})   # 제보 기기: 데스크톱 크롬
        pg = c.new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(repr(e)[:200])); pg.on('dialog', lambda d: d.accept())
        new_team_service(pg, 'sb' + tag, '9/28 주일')
        for t in ['하나', '둘', '셋', '넷', '다섯']:
            add_song(pg, t)
        sid = pg.evaluate("CONTI.S.services[0].id")
        slot = 'lay:%s~desktop' % sid
        open_stage(pg, sid)
        if pg.evaluate("CONTI.STG.pref.form") != 'block': fail('준비: 기본 송폼 모드가 조각 위가 아님 %s' % pg.evaluate("CONTI.STG.pref.form"))
        st = pg.evaluate(ST)
        N = st['total']
        if N < 3 or any(v == 0 for _, v in st['cnt']): fail('준비: 자동 조판이 세 화면 이상이 아님 %s' % st)
        edit_on(pg); nudge(pg)
        I0 = pg.evaluate(IDS); S0 = pg.evaluate(SONGS)
        print('준비 — 곡 5 · 자동 조판 %d화면 %s' % (N, st['cnt']))

        # ---- 1 제보 그대로: 마지막 화면의 조각을 모두 숨긴다 ----
        goto_screen(pg, N - 1); hide_all_here(pg)
        st = pg.evaluate(ST)
        if st['total'] != N or st['cnt'][N - 1][1] != 0: fail('1 편집 중에 화면을 저절로 지우거나 바꿈: %s' % st)
        if pg.evaluate(OVL): fail('1 겹침 %s' % pg.evaluate(OVL))
        edit_off(pg)
        if pg.evaluate(SAVED, slot) != [[len(x), len(x)] for x in I0[:-1]] + [[len(I0[-1]), 0]]:
            fail('1 저장본의 화면을 지우거나 번호를 바꿈: %s' % pg.evaluate(SAVED, slot))
        seen = walk(pg, '1 무대')
        if seen != list(range(N - 1)): fail('1 무대가 모두 숨긴 화면을 안 건너뜀: %s %s' % (seen, pg.evaluate(ST)))
        n, blank = export_pages(pg)
        if n != N - 1 or blank: fail('1 내보내기 종이 %d장 · 흰 종이 %d (기대 %d장)' % (n, blank, N - 1))
        reload(pg); open_stage(pg, sid)
        if pg.evaluate(ST)['total'] != N: fail('1 새로고침 뒤 조판 화면 수가 다름 %s' % pg.evaluate(ST))
        if walk(pg, '1 새로고침 뒤 무대') != list(range(N - 1)): fail('1 새로고침 뒤 무대가 흰 쪽을 안 건너뜀 %s' % pg.evaluate(ST))
        print('1 모두 숨긴 화면 — 편집에서는 그대로, 무대(새로고침 뒤에도)·쪽 번호·내보내기에서 건너뜀 ok', pg.evaluate(ST)['cnt'])

        # ---- 2 가운데 화면 · 첫 화면 · 모두 빈 조판 ----
        edit_on(pg); show_all(pg)
        if pg.evaluate(IDS) != I0: fail('2 준비: 되돌리기가 제자리로 안 옴 %s' % pg.evaluate(IDS))
        goto_screen(pg, 1)
        pg.keyboard.press('Control+a'); pg.wait_for_timeout(300); pg.keyboard.press('Delete'); pg.wait_for_timeout(500)
        if pg.evaluate(ST)['cnt'][1][1] != 0: fail('2 준비: 가운데 화면이 안 비었음 %s' % pg.evaluate(ST))
        edit_off(pg)
        st = pg.evaluate(ST)
        if st['screen'] != 2 or label(pg) != '2/%d' % (N - 1) or not drawn(pg): fail('2 편집을 끝낸 빈 화면 대신 다음 화면이 아님: %s %s' % (st, label(pg)))
        pg.keyboard.press('ArrowLeft'); pg.wait_for_timeout(400)
        if pg.evaluate("CONTI.STG.screen") != 0 or label(pg) != '1/%d' % (N - 1): fail('2 ← 가 빈 화면을 안 건너뜀 %s' % pg.evaluate(ST))
        if not pg.locator('[data-stg="prev"][disabled]').count(): fail('2 첫 쪽인데 ← 단추가 살아 있음')
        pg.keyboard.press('ArrowRight'); pg.wait_for_timeout(400)
        if pg.evaluate("CONTI.STG.screen") != 2: fail('2 → 가 빈 화면을 안 건너뜀 %s' % pg.evaluate(ST))
        pg.click('[data-stg="prev"]'); pg.wait_for_timeout(400)
        if pg.evaluate("CONTI.STG.screen") != 0: fail('2 앞 단추가 빈 화면을 안 건너뜀 %s' % pg.evaluate(ST))
        box = pg.locator('#stageWrap .stgcanvas').bounding_box()
        pg.mouse.click(box['x'] + box['width'] - 20, box['y'] + 20); pg.wait_for_timeout(450)
        if pg.evaluate("CONTI.STG.screen") != 2: fail('2 탭이 빈 화면을 안 건너뜀 %s' % pg.evaluate(ST))
        if N == 3:
            pg.mouse.click(box['x'] + box['width'] - 20, box['y'] + 20); pg.wait_for_timeout(450)
            if pg.evaluate("CONTI.STG.screen") != 0: fail('2 마지막 쪽에서 탭하면 첫 쪽으로 %s' % pg.evaluate(ST))
        walk(pg, '2 가운데 빈 화면')
        # 첫 화면이 비면 그 다음 화면으로 연다
        edit_on(pg); show_all(pg); goto_screen(pg, 0); hide_all_here(pg); edit_off(pg)
        exit_stage(pg); open_stage(pg, sid)
        st = pg.evaluate(ST)
        if st['screen'] != 1 or label(pg) != '1/%d' % (N - 1) or not drawn(pg): fail('2 첫 화면이 빈 조판이 흰 쪽으로 열림: %s %s' % (st, label(pg)))
        # 모두 비면 첫 화면 하나 (1/1)
        edit_on(pg)
        pg.evaluate("(()=>{CONTI.STG.layout.screens.forEach(sc=>sc.blocks.forEach(b=>{b.hidden=true}));window.dispatchEvent(new Event('resize'))})()"); pg.wait_for_timeout(500)
        edit_off(pg)
        st = pg.evaluate(ST)
        if st['screen'] != 0 or label(pg) != '1/1' or not pg.locator('[data-stg="next"][disabled]').count(): fail('2 모두 빈 조판이 첫 화면 하나가 아님: %s %s' % (st, label(pg)))
        edit_on(pg); show_all(pg)
        if pg.evaluate(IDS) != I0: fail('2 되돌리기가 제자리로 안 옴 %s' % pg.evaluate(IDS))
        print('2 가운데 빈 화면은 → ← · 앞뒤 단추 · 탭이 건너뜀 · 첫 화면이 비면 다음 화면으로 열림 · 모두 비면 1/1 ok')

        # ---- 3 🗑 — 숨긴 블록만 남은 화면 ----
        goto_screen(pg, 0); trash(pg)
        if pg.evaluate(ST)['total'] != N or '보이는 블록' not in toast(pg): fail('3 보이는 블록이 있는 화면이 지워지거나 알림이 이상함: %s · %s' % (pg.evaluate(ST), toast(pg)))
        goto_screen(pg, N - 1); hide_all_here(pg)
        last = I0[-1]
        trash(pg)
        st = pg.evaluate(ST)
        if st['total'] != N - 1: fail('3 숨긴 블록만 남은 화면이 🗑 로 안 지워짐 (알림: %s) %s' % (toast(pg), st))
        if st['screen'] != N - 2: fail('3 지운 뒤 앞 화면이 아님 %s' % st)
        moved = pg.evaluate("(i)=>CONTI.STG.layout.screens[i].blocks.filter(b=>b.hidden).map(b=>b.id)", N - 2)
        if sorted(moved) != sorted(last): fail('3 숨긴 블록이 숨긴 채 앞 화면으로 안 옴: %s (기대 %s)' % (moved, last))
        if pg.evaluate(IDS) != I0[:-1]: fail('3 남은 화면의 보이는 블록이 바뀜 %s' % pg.evaluate(IDS))
        edit_off(pg)
        if pg.evaluate(SAVED, slot) is None or len(pg.evaluate(SAVED, slot)) != N - 1: fail('3 저장본 %s' % pg.evaluate(SAVED, slot))
        walk(pg, '3 🗑 뒤 무대')
        reload(pg); open_stage(pg, sid); edit_on(pg)
        if pg.evaluate(ST)['total'] != N - 1 or pg.evaluate(ST)['hidden'] != len(last): fail('3 새로고침 뒤 %s' % pg.evaluate(ST))
        show_all(pg)
        if pg.evaluate(IDS) != I0: fail('3 되돌리기가 제 화면으로 안 옴: %s (기대 %s)' % (pg.evaluate(IDS), I0))
        clean(pg, '3 되돌린 뒤', S0)
        print('3 🗑 — 숨긴 블록만 남은 화면을 지우고(새로고침 뒤에도) 되돌리면 제 화면 · 보이는 블록이 있으면 막음 ok')

        # ---- 4 첫 화면을 🗑 → 되돌려도 순서 그대로 (잇달아 두 번) ----
        goto_screen(pg, 0); hide_all_here(pg); trash(pg)
        if pg.evaluate(ST)['total'] != N - 1 or pg.evaluate("CONTI.STG.screen") != 0: fail('4 첫 화면이 🗑 로 안 지워짐 %s' % pg.evaluate(ST))
        show_all(pg)
        if pg.evaluate(IDS) != I0: fail('4-a 첫 화면을 되돌린 순서가 다름: %s (기대 %s)' % (pg.evaluate(IDS), I0))
        goto_screen(pg, 0); hide_all_here(pg); trash(pg)
        goto_screen(pg, 0); hide_all_here(pg); trash(pg)
        if pg.evaluate(ST)['total'] != N - 2: fail('4-b 두 화면이 안 지워짐 %s' % pg.evaluate(ST))
        show_all(pg)
        if pg.evaluate(IDS) != I0: fail('4-b 두 화면을 되돌린 순서가 다름: %s (기대 %s)' % (pg.evaluate(IDS), I0))
        clean(pg, '4 되돌린 뒤', S0)
        print('4 첫 화면을 🗑 로 지우고(잇달아 두 번) 되돌려도 화면 순서 그대로 ok')

        # ---- 5 조각 위에서 🗑 로 옮긴 무리 → 다른 송폼 모드 → 조각 위 ----
        ALL = pg.evaluate(ALLIDS)
        if ALL != sorted(sum(I0, [])): fail('5 준비: 숨긴 블록이 남음 %s' % pg.evaluate(ST))
        heads0 = [i for i in I0[0] if i.startswith('h')]
        if not heads0 or not [i for i in I0[-1] if i.startswith('h')]: fail('5 준비: 첫·마지막 화면에 송폼이 없음 %s' % I0)
        goto_screen(pg, N - 1); hide_all_here(pg); trash(pg)
        if pg.evaluate(ST)['total'] != N - 1: fail('5-a 준비: 🗑 로 안 지워짐 %s' % pg.evaluate(ST))
        for f in ('hide', 'auto', 'bar'):
            set_form(pg, f)
            st = pg.evaluate(ST)
            if st['total'] != N - 1 or pg.evaluate(ALLIDS) != ALL: fail('5-a %s 모드에서 블록이 사라지거나 화면이 바뀜 %s · %s' % (f, st, pg.evaluate(ALLIDS)))
            # 고치기 전처럼 블록이 하나라도 있으면 막는다 (숨긴 블록만 남은 화면도)
            goto_screen(pg, N - 2); pg.evaluate("document.querySelector('#toast').textContent=''"); trash(pg)
            if pg.evaluate(ST)['total'] != N - 1 or '빈 화면만 지울 수 있어요' not in toast(pg): fail('5-a %s 모드 🗑 가 고치기 전과 다름: %s · %s' % (f, pg.evaluate(ST), toast(pg)))
        edit_off(pg)   # 상단 바로 저장 — 송폼 모드가 뺀 송폼(off)도 무리 표시를 지닌 채
        if walk(pg, '5-a 상단 바 무대') != list(range(N - 1)): fail('5-a 상단 바 무대가 모든 화면을 넘기지 않음 %s' % pg.evaluate(ST))
        reload(pg); open_stage(pg, sid); edit_on(pg)
        if pg.evaluate("CONTI.STG.pref.form") != 'bar' or pg.evaluate(ALLIDS) != ALL: fail('5-a 새로고침 뒤 블록이 사라짐 %s' % pg.evaluate(ALLIDS))
        set_form(pg, 'block')
        show_all(pg)
        # 화면 안 블록 차례는 안 본다 — 송폼 모드를 한 바퀴 돌면 뺐던 송폼이 화면 블록 끝에 붙는다 (고치기 전과 같다)
        if [sorted(x) for x in pg.evaluate(IDS)] != [sorted(x) for x in I0]: fail('5-a 조각 위로 돌아와 되돌렸는데 제 화면·제 순서가 아님: %s (기대 %s)' % (pg.evaluate(IDS), I0))
        clean(pg, '5-a 되돌린 뒤', S0)
        # 첫 화면을 🗑 → 숨김 모드에서 되돌리기 = 고치기 전처럼 제자리에서 (송폼 모드가 뺀 숨긴 송폼은 숨긴 채)
        goto_screen(pg, 0); hide_all_here(pg); trash(pg)
        if pg.evaluate(ST)['total'] != N - 1: fail('5-b 준비: 첫 화면이 🗑 로 안 지워짐 %s' % pg.evaluate(ST))
        set_form(pg, 'hide'); show_all(pg)
        st = pg.evaluate(ST)
        hid_off = pg.evaluate("(CONTI.STG.layout.off||[]).filter(o=>o.b.hidden).map(o=>String(o.b.id)).sort()")
        if st['total'] != N - 1 or st['hidden'] or hid_off != sorted(heads0) or pg.evaluate(ALLIDS) != ALL:
            fail('5-b 숨김 모드 되돌리기가 고치기 전과 다름 (제자리 · 뺀 송폼은 숨긴 채): %s · 숨긴 송폼 %s (기대 %s)' % (st, hid_off, heads0))
        set_form(pg, 'block')
        if pg.evaluate(ST)['hidden'] != len(heads0): fail('5-b 조각 위로 돌아온 숨긴 송폼 %s' % pg.evaluate(ST))
        show_all(pg)
        st = pg.evaluate(ST)
        if st['total'] != N - 1 or st['hidden'] or sorted(sum(pg.evaluate(IDS), [])) != ALL: fail('5-b 조각 위 되돌리기 뒤 잃은 블록 %s · %s' % (st, pg.evaluate(IDS)))
        print('5 조각 위 🗑 무리 — 숨김·자동·상단 바에서는 고치기 전처럼(🗑 막음 · 모든 화면 · 잃는 블록 없음 · 저장·새로고침) · 조각 위로 돌아와 되돌리면 제 화면 ok')

        # ---- 6 자른 반쪽을 숨겨 🗑 로 남은 반쪽 화면에 옮긴 뒤 남은 반쪽을 끌어도 안 붙는다 ----
        auto_again(pg)
        T = pg.evaluate(ST)['total']
        goto_screen(pg, T - 1)
        root = None
        for bid in pg.evaluate(BLK + ".filter(b=>b.type==='slice'&&!b.hidden).map(b=>b.id)"):
            open_menu(pg, bid); pg.click('.sblkmenu [data-sm="cut"]'); pg.wait_for_timeout(450)
            r0 = re.split('[#~]', bid)[0]
            halves = pg.evaluate("(r)=>" + BLK + ".filter(b=>b.type==='slice'&&String(b.id).split(/[#~]/)[0]===r).map(b=>({id:b.id,ranges:b.ranges}))", r0)
            if len(halves) == 2: root = r0; break
        if not root: fail('6 준비: 자를 수 있는 악보 블록이 없음')
        halves.sort(key=lambda h: h['ranges'][0][0])
        top, bot = halves
        open_menu(pg, bot['id']); pg.click('.sblkmenu [data-sm="next"]'); pg.wait_for_timeout(450)
        if pg.evaluate(ST)['total'] != T + 1: fail('6 준비: 아래 반쪽을 새 화면으로 못 보냄 %s' % pg.evaluate(ST))
        goto_screen(pg, T); hide_all_here(pg)
        if pg.evaluate(ST)['total'] != T + 1: fail('6 숨겼다고 화면을 저절로 지움 %s' % pg.evaluate(ST))
        trash(pg)
        st = pg.evaluate(ST)
        if st['total'] != T or st['screen'] != T - 1 or st['hidden'] != 1: fail('6 준비: 숨긴 반쪽만 남은 화면이 🗑 로 안 지워짐 %s' % st)
        pg.evaluate("([t,b])=>{const bs=%s;const T=bs.find(x=>x.id===t),B=bs.find(x=>x.id===b);T.x=B.x;T.y=B.y;window.dispatchEvent(new Event('resize'))}" % BLK, [top['id'], bot['id']]); pg.wait_for_timeout(500)
        y0 = pg.evaluate("(id)=>" + BLK + ".find(b=>b.id===id).y", top['id'])
        rc = pg.evaluate("(id)=>{const r=document.querySelector('.sblk[data-sid=\"'+CSS.escape(id)+'\"]').getBoundingClientRect();return [r.x,r.y]}", top['id'])
        pg.mouse.move(rc[0] + 30, rc[1] + 12); pg.mouse.down(); pg.mouse.move(rc[0] + 30, rc[1] + 37, steps=6); pg.mouse.up(); pg.wait_for_timeout(600)
        vis = pg.evaluate("(r)=>" + BLK + ".filter(b=>b.type==='slice'&&!b.hidden&&String(b.id).split(/[#~]/)[0]===r).map(b=>b.ranges)", root)
        hid = pg.evaluate("(r)=>" + BLK + ".filter(b=>b.hidden&&String(b.id).split(/[#~]/)[0]===r).map(b=>b.ranges)", root)
        if pg.evaluate(ST)['hidden'] != 1 or vis != [top['ranges']] or hid != [bot['ranges']]:
            fail('6 남은 반쪽을 끌었더니 숨긴 반쪽과 붙어 무대에 도로 나옴: 보이는 %s · 숨긴 %s (기대 %s · %s)' % (vis, hid, [top['ranges']], [bot['ranges']]))
        y1 = pg.evaluate("(id)=>{const b=" + BLK + ".find(b=>b.id===id);return b?b.y:null}", top['id'])
        if y1 is None or y1 <= y0: fail('6 준비: 남은 반쪽이 안 끌림 (y %s → %s)' % (y0, y1))
        show_all(pg)
        if pg.evaluate(ST)['hidden'] or pg.evaluate(ST)['total'] != T + 1: fail('6 숨김 되돌리기 %s' % pg.evaluate(ST))
        print('6 자른 반쪽을 숨겨 🗑 로 옮긴 뒤 남은 반쪽을 끌어도 숨긴 반쪽과 안 붙음 ok')

        # ---- 7 › 로 모두 보냈다 ‹ 로 되돌리기 (가운데 · 첫 화면) ----
        auto_again(pg); nudge(pg)
        J0 = [sorted(x) for x in pg.evaluate(IDS)]
        for src in (1, 0):
            goto_screen(pg, src)
            ids = pg.evaluate(BLK + ".map(b=>b.id)")
            for i in ids:
                open_menu(pg, i); pg.click('.sblkmenu [data-sm="next"]'); pg.wait_for_timeout(350)
            st = pg.evaluate(ST)
            if st['total'] != len(J0) or st['cnt'][src] != [0, 0]: fail('7 블록을 다 보낸 화면을 저절로 지움 (되돌릴 자리가 없어진다) %s' % st)
            goto_screen(pg, src + 1)
            for i in ids:
                open_menu(pg, i); pg.click('.sblkmenu [data-sm="prev"]'); pg.wait_for_timeout(350)
            got = [sorted(x) for x in pg.evaluate(IDS)]
            if got != J0: fail('7 › 로 보냈다 ‹ 로 되돌렸는데 전과 다름 (화면 %d): %s (기대 %s)' % (src, got, J0))
        print('7 › 로 모두 보냈다 ‹ 로 되돌리면 전과 같음 (가운데 · 첫 화면) ok')

        if errs: fail('콘솔 오류: %s' % errs[:3])
        b.close()

# ---------------- 2부: 다른 송폼 모드는 main 과 똑같이 ----------------
def base_html():
    # 고치기 전 앱 — 이 고침(stgBlockForm)을 처음 들인 커밋의 앞 커밋 (아직 커밋 전이면 HEAD)
    rev = os.environ.get('STAGE_BLANK_BASE')
    if not rev:
        r = subprocess.run(['git', 'log', '--format=%H', '-S', 'stgBlockForm', '--reverse', '--', 'app/index.html'], cwd=ROOT, capture_output=True, text=True)
        first = (r.stdout.split() or [None])[0]
        rev = first + '^' if first else 'HEAD'
    r = subprocess.run(['git', 'show', rev + ':app/index.html'], cwd=ROOT, capture_output=True, text=True)
    if r.returncode or '<html' not in r.stdout: fail('main 의 app/index.html 을 못 읽음 (%s): %s' % (rev, r.stderr[:200]))
    if 'stgBlockForm' in r.stdout or 'stgDropScreen' in r.stdout: fail('견줄 앱(%s)에 이미 빈 화면 고침이 있음 — STAGE_BLANK_BASE 로 고치기 전 커밋을 주세요' % rev)
    return rev, r.stdout

O_MID = ['하나', '둘', '셋', '넷']      # 둘 = 악보 없는 곡
O_FIRST = ['둘', '하나', '셋', '넷']
O_LAST = ['하나', '셋', '넷', '둘']

def walk_all(pg, taps=True):
    # 여는 화면에서 → 단추로 끝까지 · ← 키로 처음까지 · → 키 한 번 · 탭으로 한 바퀴 — 걸음마다 보기 값
    out = [('open', pg.evaluate(VIEW))]
    for _ in range(12):
        if pg.locator('#stageWrap [data-stg="next"][disabled]').count(): break
        pg.click('#stageWrap [data-stg="next"]'); pg.wait_for_timeout(300); out.append(('next', pg.evaluate(VIEW)))
    for _ in range(12):
        if pg.locator('#stageWrap [data-stg="prev"][disabled]').count(): break
        pg.keyboard.press('ArrowLeft'); pg.wait_for_timeout(300); out.append(('left', pg.evaluate(VIEW)))
    pg.keyboard.press('ArrowRight'); pg.wait_for_timeout(300); out.append(('right', pg.evaluate(VIEW)))
    if taps:
        box = pg.locator('#stageWrap .stgcanvas').bounding_box()
        for _ in range((pg.evaluate("CONTI.STG.nscreens") or 1) + 1):
            pg.mouse.click(box['x'] + box['width'] - 12, box['y'] + 12); pg.wait_for_timeout(350); out.append(('tap', pg.evaluate(VIEW)))
    return out

def export_all(pg):
    # 내보내기 종이마다 [악보 조각 수, 메모 띠 수, 블록 수, 글]
    pg.click('#stageWrap [data-stg="export"]'); pg.wait_for_selector('#pvGo', timeout=8000)
    pg.click('#pvGo'); pg.wait_for_selector('#printArea.pv .ppage', timeout=15000); pg.wait_for_timeout(600)
    r = pg.evaluate(r"""()=>[...document.querySelectorAll('#printArea .ppage')].map(p=>[p.querySelectorAll('.pslice').length,p.querySelectorAll('.pstrip').length,
      p.querySelectorAll('.blk').length,p.innerText.replace(/\s+/g,' ').trim()])""")
    pg.click('#printArea [data-pv="close"]'); pg.wait_for_timeout(400)
    return r

def trash_rec(pg):
    # 🗑 을 누르고 [알림, 조판]
    pg.evaluate("document.querySelector('#toast').textContent=''"); trash(pg)
    return [toast(pg), pg.evaluate(LAYX)]

def show_rec(pg):
    # 숨김 되돌리기 (단추가 없으면 — 고치기 전처럼 화면 블록에 숨긴 것이 없으면 — 없다고 적는다)
    if not pg.locator('[data-sc="show"]').count(): return ['단추 없음', pg.evaluate(LAYX)]
    show_all(pg); return ['되돌림', pg.evaluate(LAYX)]

def run2_build(who, base, box):
    # who = 'main'(고치기 전 앱을 route 로) | 'br'(지금 앱). 같은 곡·같은 순서로 몰고 걸음마다 값을 box['rec'] 에 적는다
    rec = box['rec'] = []
    def put(k, v): rec.append((k, v))
    with sync_playwright() as p:
        b = p.chromium.launch()
        c = b.new_context(viewport={'width': 834, 'height': 1194}, service_workers='block')
        if base is not None:
            c.route(lambda u: urlparse(u).path in ('/', '/index.html'),
                    lambda r: r.fulfill(status=200, content_type='text/html; charset=utf-8', body=base))
        pg = c.new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(repr(e)[:200])); pg.on('dialog', lambda d: d.accept())
        new_team_service(pg, ('sm' if base is not None else 'sn') + tag, '10/5 주일')
        if pg.evaluate(HAS_FIX) != (base is None): fail('준비: %s 앱이 아님 (빈 화면 고침 %s)' % (who, pg.evaluate(HAS_FIX)))
        add_song(pg, '하나'); add_song_bare(pg, '둘'); add_song(pg, '셋'); add_song(pg, '넷')
        sid = pg.evaluate("CONTI.S.services[0].id")
        slot = 'lay:%s~tab-l' % sid
        open_stage(pg, sid)
        if pg.evaluate("CONTI.STG.lay.screens.length") != 4: fail('준비: 곡마다 한 화면이 아님 %s' % pg.evaluate(SONGS))
        edit_on(pg); set_form(pg, 'block'); auto_again(pg); nudge(pg); edit_off(pg)
        if pg.evaluate(SONGS) != [[0], [1], [2], [3]]: fail('준비: 곡마다 한 화면이 아님 %s' % pg.evaluate(SONGS))
        good = pg.evaluate("(slot)=>CONTI.PREFS.data.stage[slot]", slot)
        if not good or len(good['screens']) != 4: fail('준비: 저장본 %s' % good)
        exit_stage(pg)
        put('준비', pg.evaluate(SAVEDX, slot))

        def start(order, lay, form):
            # 곡 순서 · 조판(저장본 · 자동으로 보기) · 송폼 모드를 맞추고 무대를 연다 (편집을 끄지 않고 나가 조판은 안 바뀐다)
            pg.evaluate(REORDER, order); pg.wait_for_timeout(400)
            pg.evaluate(PUT_LAY, [slot, lay])
            open_stage(pg, sid); edit_on(pg); set_form(pg, form); exit_stage(pg)
            open_stage(pg, sid)

        # ---- 8 자동 조판 · 악보 없는 곡이 첫·가운데·끝 ----
        for oname, order in (('첫', O_FIRST), ('가운데', O_MID), ('끝', O_LAST)):
            for form in FORMS:
                k = '8 자동 조판 · %s · 악보 없는 곡 %s' % (form, oname)
                start(order, {'v': 2, 'auto': 1}, form)
                put(k + ' · 여는 화면', [pg.evaluate(VIEW), pg.evaluate(LAYX)])
                put(k + ' · 넘김', walk_all(pg))
                put(k + ' · 내보내기', export_all(pg))
                open_stage(pg, sid); edit_on(pg)
                put(k + ' · 편집', pg.evaluate(LAYX))
                bare = pg.evaluate("CONTI.STG.layout.screens.findIndex(sc=>!sc.blocks.length)")
                if bare >= 0:
                    goto_screen(pg, bare); put(k + ' · 제목만 남은 곡 화면 🗑', trash_rec(pg))
                put(k + ' · 숨김 되돌리기', show_rec(pg))
                edit_off(pg)
                put(k + ' · 저장본', pg.evaluate(SAVEDX, slot))
                put(k + ' · 다시 넘김', walk_all(pg, taps=False))
                exit_stage(pg)

        # ---- 9 저장한 조판 · 모두 숨긴 화면 · 제목만 남은 곡 화면 ----
        for form in FORMS:
            k = '9 저장한 조판 · %s' % form
            start(O_MID, good, form)
            put(k + ' · 여는 화면', [pg.evaluate(VIEW), pg.evaluate(LAYX)])
            put(k + ' · 넘김', walk_all(pg))
            edit_on(pg); goto_screen(pg, 3); hide_all_here(pg)
            put(k + ' · 모두 숨김', pg.evaluate(LAYX))
            put(k + ' · 모두 숨긴 화면 🗑', trash_rec(pg))
            edit_off(pg)
            put(k + ' · 모두 숨긴 뒤 저장본', pg.evaluate(SAVEDX, slot))
            put(k + ' · 모두 숨긴 뒤 넘김', walk_all(pg))
            put(k + ' · 모두 숨긴 뒤 내보내기', export_all(pg))
            open_stage(pg, sid)
            put(k + ' · 다시 연 화면', pg.evaluate(VIEW))
            edit_on(pg)
            bare = pg.evaluate("CONTI.STG.layout.screens.findIndex(sc=>!sc.blocks.length)")
            put(k + ' · 제목만 남은 곡 화면', bare)
            if bare >= 0:
                goto_screen(pg, bare); put(k + ' · 제목만 남은 곡 화면 🗑', trash_rec(pg))
            put(k + ' · 숨김 되돌리기', show_rec(pg))
            edit_off(pg)
            put(k + ' · 저장본', pg.evaluate(SAVEDX, slot))
            put(k + ' · 되돌린 뒤 넘김', walk_all(pg, taps=False))
            exit_stage(pg)

        # ---- 10 저장한 조판에 곡 더하기 ----
        for order in (('bare', 'sheet'), ('sheet', 'bare')):
            for form in FORMS:
                k = '10 %s · %s' % (form, '악보 없는 곡 → 악보 있는 곡' if order[0] == 'bare' else '악보 있는 곡 → 악보 없는 곡')
                start(O_MID, good, form); exit_stage(pg)
                pg.goto(URL + '#/edit/' + sid); pg.wait_for_timeout(1500)
                for n, kind in enumerate(order):
                    (add_song_bare if kind == 'bare' else add_song)(pg, ['다섯', '여섯'][n])
                open_stage(pg, sid)
                if pg.evaluate("CONTI.STG.pref.form") != form: fail('%s 준비: 송폼 모드 %s' % (k, pg.evaluate("CONTI.STG.pref.form")))
                put(k + ' · 여는 화면', [pg.evaluate(VIEW), pg.evaluate(LAYX)])
                put(k + ' · 넘김', walk_all(pg, taps=False))
                edit_on(pg); set_form(pg, 'block')
                put(k + ' · 조각 위로 되돌린 조판', [pg.evaluate(LAYX), pg.evaluate(SONGS), pg.evaluate(OVL), pg.evaluate(MIS)])
                if base is None: clean(pg, k + ' 조각 위로 되돌린 뒤', [[0], [1], [2], [3], [4], [5]])
                exit_stage(pg)
                pg.evaluate("(()=>{const s=CONTI.S.services[0];s.items=s.items.slice(0,4);CONTI.save()})()"); pg.wait_for_timeout(600)

        # ---- 11 (지금 앱만 · 조각 위) ----
        if base is None:
            start(O_MID, good, 'block')
            edit_on(pg); goto_screen(pg, 1)
            ids = pg.evaluate(BLK + ".map(b=>b.id)")
            for i in ids:
                open_menu(pg, i); pg.click('.sblkmenu [data-sm="next"]'); pg.wait_for_timeout(350)
            goto_screen(pg, 2)
            for i in ids:
                open_menu(pg, i); pg.click('.sblkmenu [data-sm="prev"]'); pg.wait_for_timeout(350)
            clean(pg, '11 › ‹ 뒤', [[0], [1], [2], [3]])
            exit_stage(pg)
            start(O_MID, good, 'block')
            if walk(pg, '11 조각 위 무대') != [0, 1, 2, 3]: fail('11 조각 위에서 송폼이 선 악보 없는 곡 화면을 건너뜀 %s' % pg.evaluate(ST))
            edit_on(pg); goto_screen(pg, 2); hide_all_here(pg); trash(pg)
            st = pg.evaluate(ST)
            if st['total'] != 3 or st['screen'] != 1: fail('11 🗑 로 안 지워짐 %s · %s' % (st, toast(pg)))
            show_all(pg)
            st = pg.evaluate(ST)
            if st['total'] != 4 or st['hidden']: fail('11 되돌리기로 화면이 안 돌아옴 %s' % st)
            clean(pg, '11 되돌린 뒤', [[0], [1], [2], [3]])
            edit_off(pg)
            if walk(pg, '11 무대') != [0, 1, 2, 3]: fail('11 무대 %s' % pg.evaluate(ST))
            exit_stage(pg)

        if errs: fail('콘솔 오류: %s' % errs[:3])
        b.close()
    box['ok'] = True

def first_diff(a, b, path=''):
    if type(a) != type(b): return path, a, b
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b), key=str):
            if k not in a or k not in b: return path + '.' + str(k), a.get(k), b.get(k)
            d = first_diff(a[k], b[k], path + '.' + str(k))
            if d: return d
        return None
    if isinstance(a, (list, tuple)):
        for i, (x, y) in enumerate(zip(a, b)):
            d = first_diff(x, y, '%s[%d]' % (path, i))
            if d: return d
        return None if len(a) == len(b) else (path + ' (길이)', len(a), len(b))
    return None if a == b else (path, a, b)

def run2():
    rev, base = base_html()
    print('2부 — 견줄 main: %s' % rev)
    boxes = {'main': {}, 'br': {}}
    ths = [threading.Thread(target=run2_build, args=('main', base, boxes['main']), name='main', daemon=True),
           threading.Thread(target=run2_build, args=('br', None, boxes['br']), name='br', daemon=True)]
    for t in ths: t.start()
    # 두 쪽이 간 데까지 걸음마다 곧바로 견준다 (다르면 거기서 멈춘다 — 한쪽이 먼저 멈췄어도 그 앞의 다름을 먼저 알린다)
    k, last = 0, ''
    while True:
        alive = any(t.is_alive() for t in ths)
        rm, rb = boxes['main'].get('rec', []), boxes['br'].get('rec', [])
        while k < min(len(rm), len(rb)):
            (km, vm), (kb, vb) = rm[k], rb[k]
            if km != kb: fail('2부 걸음이 어긋남: main %s · br %s' % (km, kb))
            d = first_diff(vm, vb)
            if d: fail('%s — main 과 다름 (%s): main %s · br %s\n  main %s\n  br   %s' % (km, d[0], json.dumps(d[1], ensure_ascii=False)[:300],
                       json.dumps(d[2], ensure_ascii=False)[:300], json.dumps(vm, ensure_ascii=False)[:1200], json.dumps(vb, ensure_ascii=False)[:1200]))
            head = ' '.join(km.split(' · ')[:3])
            if head != last: print(head, '— main 과 같음 ok', flush=True); last = head
            k += 1
        if not alive: break
        time.sleep(0.5)
    for who in ('main', 'br'):
        if not boxes[who].get('ok'): fail('2부 %s 쪽이 끝까지 못 감 (위 FAIL)' % who)
    if len(rm) != len(rb): fail('2부 걸음 수가 다름 main %d · br %d' % (len(rm), len(rb)))
    print('2부 %d 걸음 모두 main 과 같음 · 11 (조각 위) 악보 없는 곡 › ‹ · 송폼이 선 곡 화면은 안 건너뜀 · 🗑 뒤 되돌리면 제 화면 ok' % k)

if PART != '2': run1()
if PART != '1': run2()
print('OK — 무대 빈 화면')
