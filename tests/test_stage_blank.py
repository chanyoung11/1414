# 무대 빈 화면 (2026-09-25 실사용 제보 · 데스크톱 크롬) — 무대 편집에서 조각을 모두 숨긴 화면은 흰 쪽인데 🗑 를 누르면
# '빈 화면만 지울 수 있어요'(숨긴 블록도 블록으로 셌다)로 막혔고, 공연(무대 보기)에서도 그 흰 쪽을 넘겨야 했다.
# 고친 것(최소 · 송폼 '조각 위'(기본)에서만): 보이는 블록(숨기지 않은 송폼·악보·메모 띠·글이 있는 글)이 없는 화면을
#  · 보기에서는 넘김(← → · 탭 · 앞뒤 단추)·쪽 번호 n/m·처음 여는 화면·내보내기 종이에서 건너뛴다 — 조판(저장본)은 지우지도 번호를 바꾸지도 않는다
#  · 편집에서는 🗑 로 지울 수 있다 — 숨긴 블록은 숨긴 채 앞 화면(첫 화면이면 뒤 화면)으로, '숨김 되돌리기'는 제 화면을 새로 만들어 제자리에
# 그 밖에는 화면을 저절로 지우지 않는다 (앞선 시도들이 옮기기·숨기기·저장·열기마다 지워 송폼 모드·새 곡 자리·되돌리기 순서가 어긋났다).
# 다른 송폼 모드(자동·상단 바·숨김)는 곡 제목이 바·off 에 있어 캔버스가 비어도 그 곡 화면이다 — 🗑 는 고치기 전(main)과 똑같이 둔다
# (🗑 가 제목만 남은 화면의 제목을 숨겼다). 보기(넘김·쪽 번호·처음 화면·내보내기)는 그 모드들도 모두 숨긴 흰 쪽을 건너뛴다(09-26) —
# 블록이 있는데 보이는 것이 없는 화면만: 블록이 하나도 없는 화면(악보 없는 곡 화면 — 송폼이 바에 있다)과, 바에 띄운 송폼이 그 곡의
# 전부인 화면(그 곡의 숨긴 블록이 없다)은 곡 화면이라 main 처럼 남는다 (건너뛰면 악보 없는 첫 곡 제목이 무대에 안 나왔다).
# 다만 조각 위 🗑 로 옮긴 무리는 어느 모드에서 되돌려도 제 화면·제 순서로 (main 에는 없는 것 — 제자리에서 보이면 다른 곡 악보 위에 겹쳤다)
# 1부 — 데스크톱 · 조각 위
#   1 제보 그대로 — 마지막 화면을 모두 숨기면 편집에서는 그대로 두고, 보기(새로고침 뒤에도)·내보내기에서 건너뛴다
#   2 가운데 화면이 비면 → ← · 탭 · 앞뒤 단추가 건너뛴다 · 첫 화면이 비면 다음 화면으로 연다 · 모두 비면 첫 화면 하나
#   3 🗑 — 숨긴 블록만 남은 화면을 지운다 (숨긴 블록은 숨긴 채 앞 화면에 · 새로고침 뒤에도) · 보이는 블록이 있으면 막는다 ·
#     숨김 되돌리기는 제 화면으로 (다른 곡 위에 안 겹친다)
#   4 첫 화면을 🗑 (잇달아 두 번) → 되돌려도 화면 순서 그대로
#   5 조각 위에서 🗑 로 옮긴 무리가 있는 조판을 숨김·자동·상단 바로 보면 숨긴 블록(블록이 있으면 🗑 가 막고 모든 화면을 넘김 ·
#     블록을 잃지 않음 · 그 모드로 저장·새로고침해도) → 조각 위로 돌아와 되돌리면 제 화면·제 순서. 숨김 모드에서 되돌려도
#     제 화면·제 순서(무리의 숨긴 송폼도 함께 · 숨긴 것이 안 남는다) — 조각 위로 돌아와도 그대로
#   6 자른 반쪽을 숨겨 🗑 로 남은 반쪽 화면에 옮긴 뒤 남은 반쪽을 끌어도 숨긴 반쪽과 안 붙는다
#   7 블록을 › 로 모두 보냈다 ‹ 로 되돌리면 전과 같다 (빈 화면을 저절로 지우지 않는다 — 고치기 전과 같다)
# 2부 — 세로 태블릿(1열 · 곡마다 한 화면) · 악보 없는 곡(송폼만) 하나. 고치기 전 앱(main 의 app/index.html — 이 고침을 들인 커밋의 앞
#   커밋, STAGE_BLANK_BASE=<rev> 로 바꿀 수 있다)을 Playwright route 로 띄운 브라우저와 지금 앱을 나란히 같은 순서로 몰아 견준다
#   8 자동 조판 · 송폼 자동/상단 바/숨김 · 악보 없는 곡이 첫·가운데·끝 — 처음 여는 화면 · 넘김(단추·←→ 키·탭)·쪽 번호 · 내보내기 ·
#     🗑 (제목만 남은 곡 화면) · 저장본 · 다시 넘김 이 main 과 같다
#   9 저장한 조판(조각 위로 고친 것) · 송폼 자동/상단 바/숨김 — 여는 화면 · 넘김 · 모두 숨긴 화면의 🗑(블록이 있어 막힘) · 제목만 남은
#     곡 화면 🗑 · 숨김 되돌리기 · 저장본 이 main 과 같다. 모두 숨긴 뒤의 넘김 · 내보내기 · 다시 연 화면은 일부러 다르다 — main 에서
#     모두 숨긴 그 화면(흰 쪽)만 뺀 것과 같아야 한다 (그 화면에 안 섬 · 넘겨 볼 화면 하나 적음 · 다른 화면은 main 과 같게 보임 · 그 종이만 빠짐)
#  10 저장한 조판 · 송폼 자동/상단 바/숨김으로 악보 없는 곡과 악보 있는 곡을 (두 차례로) 더한 뒤 여는 화면 · 넘김 · 조각 위로
#     되돌린 조판이 main 과 같고 겹침 없이 곡마다 한 화면
#  11 (지금 앱만 · 조각 위) 악보 없는 곡의 블록을 › 로 보냈다 ‹ 로 되돌리면 전과 같다 · 송폼이 선 악보 없는 곡 화면은 안 건너뛰고,
#     그 다음 화면을 모두 숨겨 🗑 로 지우고 되돌려도 그 송폼 화면에 넣지 않는다
#  12 조각 위에서 한 화면을 모두 숨기기만(🗑 없이) 하고 송폼 자동/상단 바/숨김에서 되돌리기 → 조각 위로 (무리가 없는 흐름) — main 과 같다
# 3부 — 조각 위 🗑 무리를 다른 송폼 모드에서 되돌리기 (검증 제보: 옆 화면 다른 곡 악보 위에 겹쳤다). 데스크톱 1600x1000 · 세로 태블릿
#   834x1194 × 악보 없는 곡이 첫·가운데·끝 (여섯 브라우저를 나란히) — 첫·가운데·끝 화면을(태블릿은 첫 화면 잇달아 두 번 + 끝 화면도 —
#   한 화면에 앞 무리 둘·뒤 무리 하나) 조각 위에서 모두 숨겨 🗑 한 뒤
#   a 같은 사람이 송폼 자동/상단 바/숨김으로 바꿔 되돌린다 → 그 모드에서 · 저장·새로고침 뒤 · 조각 위로 돌아와서
#   b 인도자가 그 조판을 추천하고, 멤버가 자동/상단 바/숨김으로 열어 되돌린다 → 그 모드에서 · 조각 위로 돌아와서 (추천 조판은 그대로)
#   되돌린 뒤: 화면 수·화면마다 악보(제 화면·제 순서) · 숨긴 블록 없음(숨김 N개 단추 없음 — 되돌리기 전 단추 수 = 화면의 숨긴 블록) ·
#   잃은 블록 없음 · 다른 곡끼리 겹침 없음 · 남의 화면에 선 송폼 없음
# 4부 — 다른 송폼 모드(자동·상단 바·숨김) 보기의 빈 화면 · 무리 되돌리기 순서 (09-26 검증 제보)
#   세로 태블릿 · 곡 하나/둘/빈(악보 없음)/셋 — 곡마다 한 화면
#  13 저장한 조판: 셋 화면을 모두 숨기면 편집에서는 그대로(🗑 는 main 처럼 막음) · 보기(편집을 끝낸 자리·넘김·쪽 번호·새로고침 뒤·내보내기)는
#     건너뛰고 빈 화면(송폼만 — 캔버스가 빈 곡 화면)은 남긴다 · 첫 화면도 숨기면 둘 화면으로 연다 · 되돌리면 네 화면.
#     빈 화면에 숨긴 글 블록이 있어도(블록이 있는 흰 캔버스) 빈 곡 화면은 남긴다 — 그 모드에서 만든 조판(모드가 뺀 송폼이 조판에 없다)에서도
#  14 조각 위에서 셋 화면·빈 화면을 잇달아 🗑 (둘 화면에 무리 둘 — 빈 송폼뿐인 무리 · 셋 무리) → 둘을 콘티에서 뺀 뒤 그 모드로 열어
#     되돌리면 하나 · 빈 · 셋 차례 (전에는 저장본에서 센 번호로 끼운 빈 송폼이 셋 무리 뒤로 밀려 하나 · 셋 · 빈) — 그 모드에서 · 조각 위로
#   데스크톱 1열 · 곡마다 두 화면
#  15 조각 위에서 둘의 첫 화면·하나의 둘째 화면을 잇달아 🗑 (하나 첫 화면에 무리 둘) → 하나 첫 악보에 인도자 메모를 단 뒤(새 메모 띠가
#     악보를 나눈다) 그 모드에서 되돌리면 하나·하나·둘·둘 차례 (전에는 하나·둘·하나·둘)
#   데스크톱 2열 · 하나/둘/셋/넷 — 한 화면에 곡 둘
#  16 둘 송폼을 하나 악보 위에 옮겨 둔 첫 화면을 조각 위에서 모두 숨겨 🗑 (한 무리에 두 곡) → 그 모드로 열어 편집을 끝내면(저장) 무리 안
#     블록 차례가 main 그대로 하나 송폼·하나 악보·둘 송폼·둘 악보 (그 모드 · 저장본 · 조각 위로 돌아와 되돌린 뒤 — 둘 송폼이 하나 악보
#     위에 그려진다). 전에는 무리 송폼을 무리 첫 블록 앞에 끼워 하나 송폼·둘 송폼·하나 악보·둘 악보가 되어 둘 송폼이 악보 밑에 묻혔다
#   CONTI_URL=http://localhost:8766/ .venv/bin/python tests/test_stage_blank.py   (STAGE_BLANK_PART=1|2|3|4 으로 하나만)
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
# 화면마다 보이는 송폼 아닌 블록(악보·띠·글) id — 송폼 모드마다 송폼 자리(off·바)는 달라도 악보는 제 화면에 있어야 한다
NONHEAD = "()=>CONTI.STG.layout.screens.map(sc=>sc.blocks.filter(b=>!b.hidden&&b.type!=='head').map(b=>String(b.id)).sort())"
# 편집 띠의 '숨김 N개 되돌리기' 단추 글 (없으면 null)
SHOWBTN = "()=>{const e=document.querySelector('#stageWrap [data-sc=\"show\"]');return e?e.textContent.trim():null}"
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

def new_team_service(pg, user, svc, sess='건반'):
    signup(pg, user, '하은')
    pg.wait_for_selector('#gtTeam'); pg.fill('#gtTeam', '무대팀'); pg.click('#gtSess .q:has-text("%s")' % sess); pg.click('[data-act="team-create"]')
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
    pg.evaluate("document.getElementById('stageWrap')&&CONTI.stageExit()")   # 미리보기를 닫으면 무대로 돌아온다(E9) — 전처럼 닫고 뒤에서 다시 연다
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
        # 첫 화면을 🗑 → 숨김 모드에서 되돌려도 제 화면·제 순서 (전에는 제자리에서 보여 둘째 화면 곡 악보 위에 겹쳤다) ·
        # 무리의 숨긴 송폼(숨김 모드가 빼는 송폼)도 숨김 N개에 들고 함께 되돌아온다 — 조각 위로 돌아와 숨긴 것이 안 남는다
        goto_screen(pg, 0); hide_all_here(pg); trash(pg)
        if pg.evaluate(ST)['total'] != N - 1: fail('5-b 준비: 첫 화면이 🗑 로 안 지워짐 %s' % pg.evaluate(ST))
        set_form(pg, 'hide')
        st = pg.evaluate(ST)
        if st['hidden'] != len(I0[0]) or pg.evaluate(SHOWBTN) != '숨김 %d개 되돌리기' % len(I0[0]):
            fail('5-b 숨김 모드의 숨김 N개가 🗑 로 옮긴 블록 수와 다름: %s · %s (기대 %d)' % (st, pg.evaluate(SHOWBTN), len(I0[0])))
        show_all(pg)
        st = pg.evaluate(ST)
        if st['total'] != N or st['hidden'] or pg.evaluate(SHOWBTN) or pg.evaluate(ALLIDS) != ALL or pg.evaluate(NONHEAD) != [sorted(i for i in x if not i.startswith('h')) for x in I0]:
            fail('5-b 숨김 모드 되돌리기가 제 화면·제 순서가 아님: %s · %s (기대 %s)' % (st, pg.evaluate(NONHEAD), I0))
        if pg.evaluate("(CONTI.STG.layout.off||[]).some(o=>o.b.hidden)"): fail('5-b 숨김 모드가 뺀 송폼이 숨긴 채 남음 %s' % pg.evaluate(LAYX))
        clean(pg, '5-b 숨김 모드 되돌린 뒤')
        set_form(pg, 'block')
        st = pg.evaluate(ST)
        if st['total'] != N or st['hidden'] or [sorted(x) for x in pg.evaluate(IDS)] != [sorted(x) for x in I0]: fail('5-b 조각 위로 돌아와 제 화면이 아님 %s · %s' % (st, pg.evaluate(IDS)))
        clean(pg, '5-b 조각 위로 돌아온 뒤', S0)
        print('5 조각 위 🗑 무리 — 숨김·자동·상단 바에서 🗑 는 고치기 전처럼 막음 · 모든 화면 · 잃는 블록 없음(저장·새로고침) · 조각 위에서도 숨김 모드에서도 되돌리면 제 화면 ok')

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
    pg.evaluate("document.getElementById('stageWrap')&&CONTI.stageExit()")   # 미리보기를 닫으면 무대로 돌아온다(E9) — 전처럼 닫고 뒤에서 다시 연다
    # 바닥글의 세션 이름은 견주지 않는다 — 인도자는 인쇄 목록에 없어 이제 '전체'로 찍힌다(C6 · main 은 '인도자'). 쪽·조각·블록은 그대로 견준다
    return [x[:3] + [re.sub(r' · (인도자|전체) (\d+ / \d+)', r' · 세션 \2', x[3])] for x in r]

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
        # main 은 팀 만들기에서 고른 세션을 무시하고 늘 '인도자'로 만든다(A1 고치기 전) — 두 앱의 내 세션(내보내기 바닥글에 찍힘)이 같게 인도자로 고른다
        new_team_service(pg, ('sm' if base is not None else 'sn') + tag, '10/5 주일', '인도자')
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

        # ---- 12 조각 위에서 숨기기만(🗑 없이) → 송폼 자동/상단 바/숨김에서 되돌리기 → 조각 위 (🗑 무리가 없는 흐름 = main 과 같다) ----
        # 첫 화면 · 악보 없는 곡 화면(송폼뿐 — 그 모드는 숨긴 송폼을 off 로 뺀다) · 끝 화면
        for form in FORMS:
            for kk in (0, 1, 3):
                k = '12 %s · 화면 %d 숨김' % (form, kk + 1)
                start(O_MID, good, 'block')
                edit_on(pg); goto_screen(pg, kk); hide_all_here(pg)
                set_form(pg, form)
                put(k + ' · 그 모드', pg.evaluate(LAYX))
                put(k + ' · 되돌리기', show_rec(pg))
                set_form(pg, 'block')
                put(k + ' · 조각 위로', pg.evaluate(LAYX))
                put(k + ' · 조각 위 되돌리기', show_rec(pg))
                edit_off(pg)
                put(k + ' · 저장본', pg.evaluate(SAVEDX, slot))
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

# 2부에서 일부러 main 과 다른 걸음 (09-26) — 다른 송폼 모드도 보기에서 모두 숨긴 흰 쪽(9 의 넷 화면)을 건너뛴다.
# 지금 앱 = main 에서 그 화면만 뺀 것: 그 화면에 안 서고 · 넘겨 볼 화면이 하나 적고(쪽 번호·앞뒤 단추도 그대로 줄고) ·
# 다른 화면은 main 과 같게 보이고(그린 블록 수 · 그린 것이 있는 화면의 바 제목·송폼) · 내보내기는 그 종이만 빠진다
HID9 = 3   # 9 에서 모두 숨기는 화면 (넷 — O_MID 의 끝 화면)
def skip_walk(vm, vb, hid=HID9):
    m, b = [v for _, v in vm], [v for _, v in vb]
    n = m[0][2]
    if not any(v[0] == hid and v[8] == 0 for v in m): return ('main 이 모두 숨긴 흰 쪽을 안 보임', m, b)
    if any(v[0] == hid for v in b): return ('모두 숨긴 화면에 섬', hid, b)
    nav = sorted({v[0] for v in m} - {hid})
    if sorted({v[0] for v in b}) != nav: return ('넘긴 화면', nav, b)
    for v in b:
        k = nav.index(v[0])
        if v[2] != n - 1 or not v[3].startswith('%d/%d 화면' % (k + 1, n - 1)) or v[6] != (k == 0) or v[7] != (k == len(nav) - 1):
            return ('넘겨 볼 화면 수·쪽 번호·앞뒤 단추', nav, v)
    per = lambda xs: {v[0]: (v[8], v[4], v[5]) if v[8] else (0,) for v in xs if v[0] != hid}
    if per(m) != per(b): return ('화면마다 보이는 것', per(m), per(b))
    return None

def skip_export(em, eb, hid=HID9):
    pg_ = lambda p: p[:3] + [re.sub(r'\s*\d+ / \d+$', '', p[3])]
    if len(em) <= hid or em[hid][:3] != [0, 0, 0]: return ('main 이 모두 숨긴 화면을 흰 종이로 안 찍음', em, eb)
    want = [pg_(p) for i, p in enumerate(em) if i != hid]
    return None if [pg_(p) for p in eb] == want else ('종이', want, eb)

def skip_open(vm, vb):
    want = vm[:2] + [vm[2] - 1, vm[3].replace('/%d 화면' % vm[2], '/%d 화면' % (vm[2] - 1))] + vm[4:]
    return None if vb == want else ('다시 연 화면', want, vb)

SKIPPED = ((' · 모두 숨긴 뒤 넘김', skip_walk), (' · 모두 숨긴 뒤 내보내기', skip_export), (' · 다시 연 화면', skip_open))

def run2():
    rev, base = base_html()
    print('2부 — 견줄 main: %s' % rev)
    boxes = {'main': {}, 'br': {}}
    ths = [threading.Thread(target=run2_build, args=('main', base, boxes['main']), name='main', daemon=True),
           threading.Thread(target=run2_build, args=('br', None, boxes['br']), name='br', daemon=True)]
    for t in ths: t.start()
    # 두 쪽이 간 데까지 걸음마다 곧바로 견준다 (다르면 거기서 멈춘다 — 한쪽이 먼저 멈췄어도 그 앞의 다름을 먼저 알린다)
    k, last, nskip = 0, '', 0
    while True:
        alive = any(t.is_alive() for t in ths)
        rm, rb = boxes['main'].get('rec', []), boxes['br'].get('rec', [])
        while k < min(len(rm), len(rb)):
            (km, vm), (kb, vb) = rm[k], rb[k]
            if km != kb: fail('2부 걸음이 어긋남: main %s · br %s' % (km, kb))
            rule = next((f for s, f in SKIPPED if km.startswith('9 ') and km.endswith(s)), None)
            d = rule(vm, vb) if rule else first_diff(vm, vb)
            if d: fail('%s — main %s (%s): main %s · br %s\n  main %s\n  br   %s' % (km, '에서 모두 숨긴 흰 쪽만 뺀 것과 다름' if rule else '과 다름', d[0],
                       json.dumps(d[1], ensure_ascii=False)[:300], json.dumps(d[2], ensure_ascii=False)[:300],
                       json.dumps(vm, ensure_ascii=False)[:1200], json.dumps(vb, ensure_ascii=False)[:1200]))
            if rule:
                nskip += 1; print(km, '— main 에서 모두 숨긴 흰 쪽만 뺀 것과 같음 ok', flush=True)
            head = ' '.join(km.split(' · ')[:3])
            if head != last: print(head, '— main 과 같음 ok', flush=True); last = head
            k += 1
        if not alive: break
        time.sleep(0.5)
    for who in ('main', 'br'):
        if not boxes[who].get('ok'): fail('2부 %s 쪽이 끝까지 못 감 (위 FAIL)' % who)
    if len(rm) != len(rb): fail('2부 걸음 수가 다름 main %d · br %d' % (len(rm), len(rb)))
    if nskip != len(SKIPPED) * len(FORMS): fail('2부 모두 숨긴 흰 쪽을 건너뛰는 걸음이 %d (기대 %d)' % (nskip, len(SKIPPED) * len(FORMS)))
    print('2부 %d 걸음 main 과 같음(그중 %d 걸음은 main 에서 모두 숨긴 흰 쪽만 뺀 것) · 11 (조각 위) 악보 없는 곡 › ‹ · 송폼이 선 곡 화면은 안 건너뜀 · 🗑 뒤 되돌리면 제 화면 ok' % (k, nskip))

# ---------------- 3부: 조각 위 🗑 무리를 다른 송폼 모드에서 되돌리기 ----------------
VPS = {'D': {'width': 1600, 'height': 1000}, 'T': {'width': 834, 'height': 1194}}
SLOT_JS = """()=>{const w=innerWidth,h=innerHeight,s=Math.min(w,h),l=Math.max(w,h);
 return 'lay:'+CONTI.STG.svc.id+'~'+(s<600?'phone':l<1100?'tab-s':l<1500?'tab-l':'desktop')}"""
# 이 기기 종류의 인도자 추천 조판 (멤버가 받은 발행본)
REC_JS = """([sid,dc])=>{const s=CONTI.S.services.find(x=>x.id===sid);const r=s&&s.published&&s.published.stageLayouts&&s.published.stageLayouts[dc];
 return r?JSON.parse(JSON.stringify(r)):null}"""

def publish(pg, sid):
    pg.goto(URL + '#/edit/' + sid); pg.wait_for_timeout(1500)
    pg.click('[data-act="publish"]'); pg.wait_for_selector('#pubOnly', timeout=8000); pg.click('#pubOnly'); pg.wait_for_timeout(2500)

def join_team(M, invite, user):
    signup(M, user, '민수'); M.wait_for_selector('#gtTeam', timeout=20000)
    M.goto(URL + '#/join/' + invite); M.wait_for_selector('#jnName', timeout=15000)
    M.click('[data-act="team-join"]'); M.wait_for_selector('.shell[data-page]', timeout=15000); M.wait_for_timeout(1500)

def lone_before(pg, what, ref, gone):
    # 🗑 뒤 · 되돌리기 전 (그 모드): 지운 만큼 화면 적음 · 잃은 블록 없음 · 숨김 N개 = 화면의 숨긴 블록 수
    st = pg.evaluate(ST)
    if st['total'] != ref['n'] - gone or pg.evaluate(ALLIDS) != ref['all']: fail('%s 되돌리기 전 화면·블록이 이상함 %s · %s' % (what, st, pg.evaluate(ALLIDS)))
    if not st['hidden'] or pg.evaluate(SHOWBTN) != '숨김 %d개 되돌리기' % st['hidden']: fail('%s 숨김 N개가 숨긴 블록 수와 다름 %s · %s' % (what, pg.evaluate(SHOWBTN), st))

def lone_after(pg, what, ref, form):
    # 되돌린 뒤: 화면 수 그대로 · 화면마다 제 악보(제 순서) · 숨긴 블록 없음(단추 없음) · 잃은 블록 없음 · 다른 곡끼리 안 겹침
    st = pg.evaluate(ST)
    if st['total'] != ref['n']: fail('%s 화면 수 %d (기대 %d) — 되돌린 무리가 제 화면에 안 섬 %s' % (what, st['total'], ref['n'], pg.evaluate(LAYX)))
    if st['hidden'] or pg.evaluate(SHOWBTN): fail('%s 숨긴 블록이 남음 %s · %s' % (what, st, pg.evaluate(SHOWBTN)))
    if pg.evaluate(NONHEAD) != ref['nonhead']: fail('%s 화면마다 악보가 제 화면·제 순서가 아님: %s (기대 %s)' % (what, pg.evaluate(NONHEAD), ref['nonhead']))
    if pg.evaluate(ALLIDS) != ref['all']: fail('%s 잃거나 늘어난 블록: %s (기대 %s)' % (what, pg.evaluate(ALLIDS), ref['all']))
    if form == 'block':
        if [sorted(x) for x in pg.evaluate(IDS)] != ref['ids']: fail('%s 조각 위에서 화면마다 블록이 다름: %s (기대 %s)' % (what, pg.evaluate(IDS), ref['ids']))
        clean(pg, what, ref['songs'])
    else:
        clean(pg, what)

def run3_build(V, pname, order, box):
    who = '%s·%s' % (V, pname)
    with sync_playwright() as p:
        b = p.chromium.launch()
        c = b.new_context(viewport=VPS[V], service_workers='block')
        pg = c.new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(repr(e)[:200])); pg.on('dialog', lambda d: d.accept())
        uid = '%s%s%s' % (V.lower(), 'fml'[['첫', '가운데', '끝'].index(pname)], tag)
        new_team_service(pg, 'l' + uid, '10/12 주일')
        for t in order: (add_song_bare if t == '둘' else add_song)(pg, t)
        sid = pg.evaluate("CONTI.S.services[0].id")
        publish(pg, sid)
        open_stage(pg, sid)
        slot = pg.evaluate(SLOT_JS); dc = slot.split('~')[1]
        edit_on(pg); set_form(pg, 'block'); auto_again(pg); nudge(pg); edit_off(pg)
        good = pg.evaluate("(slot)=>CONTI.PREFS.data.stage[slot]", slot)
        if not good or not good.get('screens'): fail('%s 준비: 저장본 %s' % (who, good))
        edit_on(pg)
        ref = {'ids': [sorted(x) for x in pg.evaluate(IDS)], 'nonhead': pg.evaluate(NONHEAD), 'all': pg.evaluate(ALLIDS), 'songs': pg.evaluate(SONGS)}
        ref['n'] = N = len(ref['ids'])
        if N < 2 or pg.evaluate(ST)['hidden'] or sorted(sum(ref['ids'], [])) != ref['all']: fail('%s 준비: 조판 %s' % (who, pg.evaluate(ST)))
        exit_stage(pg)
        m = b.new_context(viewport=VPS[V], service_workers='block')
        M = m.new_page(); M.on('pageerror', lambda e: errs.append('멤버 ' + repr(e)[:200])); M.on('dialog', lambda d: d.accept())
        join_team(M, pg.evaluate("CONTI.S.team.invite"), 'm' + uid)
        print('3부 %s 준비 — %d화면 %s' % (who, N, ref['songs']), flush=True)
        # 첫·가운데·끝 화면 하나씩 · (네 화면 이상) 첫 화면 잇달아 두 번 + 끝 화면 — 한 화면에 앞 무리 둘·뒤 무리 하나 (제 순서로 되돌아와야)
        seqs = [[k] for k in sorted({0, N // 2, N - 1})] + ([[0, 0, -1]] if N >= 4 else [])
        for seq in seqs:
            kw = '3 %s 화면 %s/%d' % (who, '·'.join('끝' if k < 0 else str(k + 1) for k in seq), N)
            pg.evaluate(PUT_LAY, [slot, good]); open_stage(pg, sid); edit_on(pg)
            if pg.evaluate("CONTI.STG.pref.form") != 'block': fail('%s 준비: 송폼 모드 %s' % (kw, pg.evaluate("CONTI.STG.pref.form")))
            for k in seq:
                goto_screen(pg, k if k >= 0 else pg.evaluate(ST)['total'] - 1); hide_all_here(pg); trash(pg)
            if pg.evaluate(ST)['total'] != N - len(seq) or pg.evaluate(ALLIDS) != ref['all']: fail('%s 준비: 🗑 로 안 지워짐 %s · %s' % (kw, pg.evaluate(ST), toast(pg)))
            gb = pg.evaluate("(slot)=>CONTI.PREFS.data.stage[slot]", slot)
            exit_stage(pg)
            # a 같은 사람이 송폼 모드를 바꿔 되돌린다 → 그 모드로 저장·새로고침 → 조각 위로
            for f in FORMS:
                w = '%s · %s 에서 되돌리기' % (kw, f)
                pg.evaluate(PUT_LAY, [slot, gb]); open_stage(pg, sid); edit_on(pg); set_form(pg, f)
                lone_before(pg, w, ref, len(seq))
                show_all(pg); lone_after(pg, w, ref, f)
                edit_off(pg)
                if pg.evaluate(ST)['n'] != N: fail('%s 무대 넘김 화면 수 %s' % (w, pg.evaluate(ST)))
                reload(pg); open_stage(pg, sid); edit_on(pg)
                if pg.evaluate("CONTI.STG.pref.form") != f: fail('%s 새로고침 뒤 송폼 모드 %s' % (w, pg.evaluate("CONTI.STG.pref.form")))
                lone_after(pg, w + ' · 저장·새로고침 뒤', ref, f)
                set_form(pg, 'block'); lone_after(pg, w + ' · 조각 위로', ref, 'block')
                exit_stage(pg)
            # b 인도자가 🗑 뒤 조판을 추천 → 멤버가 송폼 자동/상단 바/숨김으로 열어 되돌린다 → 조각 위로
            pg.evaluate(PUT_LAY, [slot, gb]); open_stage(pg, sid); edit_on(pg)
            pg.evaluate("document.querySelector('#toast').textContent=''"); pg.click('[data-sc="rec"]'); pg.wait_for_timeout(1800)
            if '추천 조판으로 저장' not in toast(pg): fail('%s 추천 조판 저장 %s' % (kw, toast(pg)))
            exit_stage(pg)
            # 추천 조판은 무대를 열 때 받아 온다 (stageOpen — 발행 뒤에 붙어 목록 동기화로는 안 내려온다)
            M.evaluate(PUT_LAY, [slot, None]); open_stage(M, sid)
            M.wait_for_function("([sid,dc,n])=>{const s=CONTI.S.services.find(x=>x.id===sid);const r=s&&s.published&&s.published.stageLayouts&&s.published.stageLayouts[dc];return !!(r&&r.screens&&r.screens.length===n)}",
                                arg=[sid, dc, N - len(seq)], timeout=20000)
            exit_stage(M)
            rec0 = M.evaluate(REC_JS, [sid, dc])
            if not any(bb.get('lone') for sc in rec0['screens'] for bb in sc['blocks']): fail('%s 추천 조판에 🗑 무리가 없음 %s' % (kw, rec0))
            for f in FORMS:
                w = '%s · 추천 → 멤버가 %s 에서 되돌리기' % (kw, f)
                M.evaluate(PUT_LAY, [slot, None])   # 멤버 조판 없음 = 추천 조판으로 시작
                open_stage(M, sid); edit_on(M); set_form(M, f); exit_stage(M)
                open_stage(M, sid); edit_on(M)
                lone_before(M, w, ref, len(seq))
                show_all(M); lone_after(M, w, ref, f)
                set_form(M, 'block'); lone_after(M, w + ' · 조각 위로', ref, 'block')
                exit_stage(M)
                if M.evaluate(REC_JS, [sid, dc]) != rec0: fail('%s 인도자 추천 조판이 바뀜' % w)
            print('%s — 자동·상단 바·숨김에서 되돌려도(같은 사람 · 추천 받은 멤버) 제 화면·제 순서 ok' % kw, flush=True)
        if errs: fail('콘솔 오류: %s' % errs[:3])
        b.close()
    box['ok'] = True

def run3():
    ths, boxes = [], []
    for V in ('D', 'T'):
        for pname, order in (('첫', O_FIRST), ('가운데', O_MID), ('끝', O_LAST)):
            box = {}; boxes.append((V + '·' + pname, box))
            ths.append(threading.Thread(target=run3_build, args=(V, pname, order, box), name='%s·%s' % (V, pname), daemon=True))
    for t in ths: t.start()
    for t in ths: t.join()
    bad = [n for n, bx in boxes if not bx.get('ok')]
    if bad: fail('3부 %s 가 끝까지 못 감 (위 FAIL)' % ', '.join(bad))
    print('3부 조각 위 🗑 무리 — 데스크톱·태블릿 × 악보 없는 곡 첫·가운데·끝 × 첫·가운데·끝 화면: 자동·상단 바·숨김에서 되돌려도 제 화면 ok')

# ---------------- 4부: 다른 송폼 모드 보기의 빈 화면 · 무리 되돌리기 순서 ----------------
def open_in(pg, sid, slot, lay, form):
    # 조판(저장본)과 송폼 모드를 맞추고, 저장본을 그 모드로 처음 그리게 무대를 다시 연다 (편집을 끄지 않고 나가 조판은 안 바뀐다)
    pg.evaluate(PUT_LAY, [slot, lay]); open_stage(pg, sid); edit_on(pg); set_form(pg, form); exit_stage(pg)
    open_stage(pg, sid)

def nav(pg): return pg.evaluate("CONTI.STG.nav")

def walk_view(pg):
    # 보기: 넘겨 볼 첫 화면부터 → 단추로 끝까지 — 걸음마다 [화면, 쪽 번호]
    pg.evaluate("(()=>{const S=CONTI.STG;S.screen=(S.nav||[0])[0];window.dispatchEvent(new Event('resize'))})()"); pg.wait_for_timeout(450)
    out = []
    for _ in range(12):
        out.append([pg.evaluate("CONTI.STG.screen"), label(pg)])
        if pg.locator('#stageWrap [data-stg="next"][disabled]').count(): break
        pg.click('#stageWrap [data-stg="next"]'); pg.wait_for_timeout(300)
    return out

def add_hidden_text(pg):
    # 지금 화면에 ＋ 글 → 그 글 블록을 숨긴다 (블록은 있는데 보이는 것이 없는 캔버스)
    n0 = pg.evaluate(BLK + ".length")
    pg.click('[data-sc="text"]'); pg.wait_for_timeout(500)
    tid = pg.evaluate(BLK + ".filter(b=>b.type==='text').map(b=>b.id).pop()")
    if pg.evaluate(BLK + ".length") != n0 + 1 or not tid: fail('준비: 글 블록을 못 더함')
    pg.evaluate("(id)=>{CONTI.STG.sel=[id];CONTI.STG.menu=null}", tid); pg.keyboard.press('Delete'); pg.wait_for_timeout(400)
    if not pg.evaluate("(id)=>" + BLK + ".find(b=>b.id===id).hidden", tid): fail('준비: 글 블록을 못 숨김')

ITEM_IDS = "()=>CONTI.S.services[0].items.map(i=>i.id)"
OFFP = "()=>(CONTI.STG.layout.off||[]).map(o=>[o.s,o.b.pid||o.b.iid])"

def run4_tab(box):
    # 세로 태블릿 · 하나/둘/빈(악보 없음)/셋 — 곡마다 한 화면
    with sync_playwright() as p:
        b = p.chromium.launch()
        c = b.new_context(viewport={'width': 834, 'height': 1194}, service_workers='block')
        pg = c.new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(repr(e)[:200])); pg.on('dialog', lambda d: d.accept())
        new_team_service(pg, 'v' + tag, '10/19 주일')
        add_song(pg, '하나'); add_song(pg, '둘'); add_song_bare(pg, '빈'); add_song(pg, '셋')
        sid = pg.evaluate("CONTI.S.services[0].id"); slot = 'lay:%s~tab-l' % sid
        open_stage(pg, sid)
        edit_on(pg); set_form(pg, 'block'); auto_again(pg); nudge(pg); edit_off(pg)
        if pg.evaluate(SONGS) != [[0], [1], [2], [3]]: fail('4부 준비: 곡마다 한 화면이 아님 %s' % pg.evaluate(SONGS))
        good = pg.evaluate("(slot)=>CONTI.PREFS.data.stage[slot]", slot)
        exit_stage(pg)

        # ---- 13 다른 송폼 모드 보기: 모두 숨긴 화면은 건너뛰고 빈 곡 화면은 남긴다 ----
        for f in FORMS:
            k = '13 %s' % f
            open_in(pg, sid, slot, good, f)
            if nav(pg) != [0, 1, 2, 3] or pg.evaluate("CONTI.STG.layout.screens[2].blocks.length"): fail('%s 준비: 네 화면 · 빈 곡 화면은 블록 없음이 아님 %s' % (k, pg.evaluate(LAYX)))
            edit_on(pg); goto_screen(pg, 3); hide_all_here(pg)
            st = pg.evaluate(ST)
            if st['total'] != 4 or st['n'] != 4: fail('%s 편집 중에 화면을 저절로 지우거나 건너뜀 %s' % (k, st))
            pg.evaluate("document.querySelector('#toast').textContent=''"); trash(pg)
            if pg.evaluate(ST)['total'] != 4 or '빈 화면만 지울 수 있어요' not in toast(pg): fail('%s 🗑 가 main 과 다름 %s · %s' % (k, pg.evaluate(ST), toast(pg)))
            edit_off(pg)
            sv = pg.evaluate(SAVED, slot)
            if not sv or len(sv) != 4 or sv[2] != [0, 0] or sv[3][0] < 1 or sv[3][1] != 0: fail('%s 저장본의 화면을 지우거나 번호를 바꿈 %s' % (k, sv))
            st = pg.evaluate(ST)
            if nav(pg) != [0, 1, 2] or st['screen'] != 2 or label(pg) != '3/3': fail('%s 편집을 끝낸 모두 숨긴 화면 대신 앞 화면(빈 곡 화면)이 아님 %s %s %s' % (k, nav(pg), st, label(pg)))
            if drawn(pg): fail('%s 준비: 빈 곡 화면 캔버스에 블록이 그려짐 %d' % (k, drawn(pg)))
            if walk_view(pg) != [[0, '1/3'], [1, '2/3'], [2, '3/3']]: fail('%s 넘김이 모두 숨긴 화면을 안 건너뜀 %s' % (k, pg.evaluate(ST)))
            pg.keyboard.press('ArrowRight'); pg.wait_for_timeout(350)
            if pg.evaluate("CONTI.STG.screen") != 2: fail('%s 끝 쪽에서 → 가 모두 숨긴 화면으로 감' % k)
            pg.keyboard.press('ArrowLeft'); pg.wait_for_timeout(350)
            if pg.evaluate("CONTI.STG.screen") != 1: fail('%s ← %s' % (k, pg.evaluate(ST)))
            cbox = pg.locator('#stageWrap .stgcanvas').bounding_box()
            got = []
            for _ in range(3):
                pg.mouse.click(cbox['x'] + cbox['width'] - 12, cbox['y'] + 12); pg.wait_for_timeout(350); got.append(pg.evaluate("CONTI.STG.screen"))
            if got != [2, 0, 1]: fail('%s 탭이 모두 숨긴 화면을 안 건너뜀 %s' % (k, got))
            n, blank = export_pages(pg)
            if n != 3 or blank != 1: fail('%s 내보내기 종이 %d장 · 흰 종이 %d (기대 3장 · 빈 곡 종이 하나 — main 처럼)' % (k, n, blank))
            reload(pg); open_stage(pg, sid)
            if pg.evaluate("CONTI.STG.pref.form") != f or nav(pg) != [0, 1, 2] or label(pg) != '1/3': fail('%s 새로고침 뒤 %s %s' % (k, nav(pg), label(pg)))
            # 첫 화면(하나)도 모두 숨기면 둘 화면으로 연다
            edit_on(pg); goto_screen(pg, 0); hide_all_here(pg); edit_off(pg); exit_stage(pg); open_stage(pg, sid)
            if nav(pg) != [1, 2] or pg.evaluate("CONTI.STG.screen") != 1 or label(pg) != '1/2': fail('%s 첫 화면을 모두 숨겼는데 둘 화면으로 안 엶 %s %s' % (k, nav(pg), label(pg)))
            edit_on(pg); show_all(pg); edit_off(pg)
            if nav(pg) != [0, 1, 2, 3] or pg.evaluate(ST)['hidden']: fail('%s 되돌린 뒤 네 화면이 아님 %s' % (k, pg.evaluate(ST)))
            # 빈 곡 화면에 숨긴 글 — 블록이 있는 흰 캔버스지만 바에 띄운 송폼(빈)이 그 곡의 전부라 곡 화면으로 남는다
            edit_on(pg); goto_screen(pg, 2); add_hidden_text(pg); edit_off(pg)
            if nav(pg) != [0, 1, 2, 3]: fail('%s 숨긴 글이 있는 빈 곡 화면을 건너뜀 %s' % (k, pg.evaluate(LAYX)))
            exit_stage(pg)
            # 그 모드에서 만든 조판 (자동 조판에서 편집을 켜면 모드가 뺀 송폼은 조판에 안 들어간다 — 송폼 자리는 자동 조판 자리)
            open_in(pg, sid, slot, {'v': 2, 'auto': 1}, f)
            if pg.evaluate("!!CONTI.STG.layout") or nav(pg) != [0, 1, 2, 3]: fail('%s 자동 조판이 네 화면을 안 넘김 %s' % (k, nav(pg)))
            edit_on(pg)
            if pg.evaluate("(CONTI.STG.layout.off||[]).length") or pg.evaluate("CONTI.STG.layout.screens[2].blocks.length"): fail('%s 준비: 모드가 뺀 송폼이 조판에 있음 %s' % (k, pg.evaluate(LAYX)))
            goto_screen(pg, 2); add_hidden_text(pg); goto_screen(pg, 3); hide_all_here(pg); edit_off(pg)
            if nav(pg) != [0, 1, 2]: fail('%s 그 모드에서 만든 조판: 빈 곡 화면을 건너뛰거나 모두 숨긴 셋 화면을 안 건너뜀 %s %s' % (k, nav(pg), pg.evaluate(LAYX)))
            exit_stage(pg)
            print('%s — 모두 숨긴 화면은 보기(넘김·키·탭·쪽 번호·새로고침·내보내기)에서 건너뛰고 빈 곡 화면은 남김 · 편집·저장본·🗑 는 그대로 ok' % k, flush=True)

        # ---- 14 한 화면에 무리 둘(빈 송폼뿐 · 셋) → 그 화면 곡(둘)을 콘티에서 뺀 뒤 다른 모드에서 되돌리기 ----
        for f in FORMS:
            k = '14 %s' % f
            open_in(pg, sid, slot, good, 'block'); edit_on(pg)
            goto_screen(pg, 3); hide_all_here(pg); trash(pg)
            goto_screen(pg, 2); hide_all_here(pg); trash(pg)
            gs = pg.evaluate("[...new Set(CONTI.STG.layout.screens[1].blocks.filter(b=>b.hidden&&b.lone).map(b=>b.lone))]")
            if pg.evaluate(ST)['total'] != 2 or len(gs) != 2: fail('%s 준비: 둘 화면에 무리 둘이 아님 %s' % (k, pg.evaluate(LAYX)))
            edit_off(pg); gb = pg.evaluate("(slot)=>CONTI.PREFS.data.stage[slot]", slot); exit_stage(pg)
            gone = pg.evaluate("(()=>{const s=CONTI.S.services[0];const it=s.items.splice(1,1)[0];CONTI.save();return it})()"); pg.wait_for_timeout(600)
            ids = pg.evaluate(ITEM_IDS)   # 하나 · 빈 · 셋
            open_in(pg, sid, slot, gb, f); edit_on(pg)
            if pg.evaluate(SHOWBTN) != '숨김 3개 되돌리기': fail('%s 되돌리기 전 숨김 수 %s %s' % (k, pg.evaluate(SHOWBTN), pg.evaluate(LAYX)))
            show_all(pg)
            st = pg.evaluate(ST)
            # 하나 · (뺀 둘의 빈 화면) · 빈(송폼 — off) · 셋
            if st['total'] != 4 or st['hidden'] or pg.evaluate(SONGS) != [[0], [], [], [2]] or sorted(pg.evaluate(OFFP)) != [[0, ids[0]], [2, ids[1]], [3, ids[2]]]:
                fail('%s 그 모드에서 되돌린 화면 차례가 하나·빈·셋이 아님: %s · 송폼 %s (빈 %s · 셋 %s)' % (k, pg.evaluate(SONGS), pg.evaluate(OFFP), ids[1], ids[2]))
            clean(pg, k + ' 되돌린 뒤')
            set_form(pg, 'block')
            if pg.evaluate(SONGS) != [[0], [], [1], [2]]: fail('%s 조각 위로 돌아온 화면 차례가 하나·빈·셋이 아님 %s' % (k, pg.evaluate(SONGS)))
            clean(pg, k + ' 조각 위로')
            edit_off(pg)
            if nav(pg) != [0, 2, 3]: fail('%s 조각 위 무대 %s' % (k, nav(pg)))
            exit_stage(pg)
            pg.evaluate("(it)=>{const s=CONTI.S.services[0];s.items.splice(1,0,it);CONTI.save()}", gone); pg.wait_for_timeout(600)
            print('%s — 한 화면의 무리 둘을 그 화면 곡을 뺀 뒤 되돌려도 하나·빈·셋 차례 (그 모드 · 조각 위로) ok' % k, flush=True)
        if errs: fail('4부 태블릿 콘솔 오류: %s' % errs[:3])
        b.close()
    box['ok'] = True

# 하나 첫 악보에 인도자 메모(마커 A) — 서버 메모 목록에도 올린다 (화면을 옮길 때 서버 것으로 덮는다). 메모 띠가 설 줄은 이 화면 악보 범위 안의 여백
MEMO = """async([sid,lo,hi])=>{const s=CONTI.S.services.find(x=>x.id===sid);const it=s.items[0];const p=it.pieces[0];
 const q=(p.gaps||[]).find(g=>(g.s+g.e)/2>lo+40&&(g.s+g.e)/2<hi-40);if(!q)return {gaps:p.gaps,lo,hi};
 p.markers=[{id:'mkA',label:'A',x:42,y:q.e,cut:null}];const cut=CONTI.autoCut(p,q.e);
 const id='nA'+Date.now().toString(36);
 const r=await fetch('/api/notes',{method:'POST',credentials:'include',headers:{'content-type':'application/json','x-conti':'1'},
  body:JSON.stringify({teamId:CONTI.S.team.id,serviceId:sid,notes:[{id,itemId:it.id,markerId:'mkA',layer:'leader',session:null,text:'여기서 천천히',at:Date.now()}]})});
 it.notes=[{id,marker:'mkA',layer:'leader',session:null,text:'여기서 천천히',author:'인도자',at:Date.now()}];
 CONTI.save();return {status:r.status,cut}}"""

def run4_desk(box):
    # 데스크톱 1열 · 하나/둘 — 곡마다 두 화면
    with sync_playwright() as p:
        b = p.chromium.launch()
        c = b.new_context(viewport={'width': 1600, 'height': 1000}, service_workers='block')
        pg = c.new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(repr(e)[:200])); pg.on('dialog', lambda d: d.accept())
        new_team_service(pg, 'w' + tag, '10/26 주일')
        add_song(pg, '하나'); add_song(pg, '둘')
        sid = pg.evaluate("CONTI.S.services[0].id"); slot = 'lay:%s~desktop' % sid
        publish(pg, sid)
        open_stage(pg, sid)
        pg.click('[data-stg="cfg"]'); pg.wait_for_timeout(400); pg.click('[data-stg="cols"][data-v="1"]'); pg.wait_for_timeout(500); pg.click('[data-stg="cfg"]'); pg.wait_for_timeout(400)
        edit_on(pg); set_form(pg, 'block'); auto_again(pg); nudge(pg); edit_off(pg)
        ref = pg.evaluate(SONGS)
        s1 = ref.index([1]) if [1] in ref else -1
        if s1 < 2 or ref != [[0]] * s1 + [[1]] * (len(ref) - s1) or len(ref) - s1 < 2: fail('4부 준비: 1열에서 곡마다 두 화면 이상이 아님 %s' % ref)
        good = pg.evaluate("(slot)=>CONTI.PREFS.data.stage[slot]", slot)
        # 둘의 첫 화면 → 하나의 끝 화면 🗑 — 하나의 끝에서 둘째 화면(host)에 무리 둘 (하나 끝 조각 · 둘 첫 화면)
        edit_on(pg); goto_screen(pg, s1); hide_all_here(pg); trash(pg); goto_screen(pg, s1 - 1); hide_all_here(pg); trash(pg)
        host = s1 - 2
        gs = pg.evaluate("(i)=>[...new Set(CONTI.STG.layout.screens[i].blocks.filter(b=>b.hidden&&b.lone).map(b=>b.lone))]", host)
        rg = pg.evaluate("(i)=>CONTI.STG.layout.screens[i].blocks.filter(b=>!b.hidden&&b.type==='slice'&&b.idx===0).map(b=>b.ranges)", host)
        if pg.evaluate(ST)['total'] != len(ref) - 2 or len(gs) != 2 or len(rg) != 1: fail('4부 준비: 하나 화면에 무리 둘이 아님 %s' % pg.evaluate(LAYX))
        edit_off(pg); gb = pg.evaluate("(slot)=>CONTI.PREFS.data.stage[slot]", slot); exit_stage(pg)
        pg.goto(URL + '#/edit/' + sid); pg.wait_for_timeout(1500)
        r = pg.evaluate(MEMO, [sid, rg[0][0][0], rg[0][-1][1]])
        if r.get('status') != 200 or r.get('cut') is None: fail('4부 준비: 메모를 못 닮 %s' % r)
        publish(pg, sid)
        for f in FORMS:
            k = '15 %s' % f
            open_in(pg, sid, slot, gb, f); edit_on(pg)
            if not pg.evaluate("(i)=>CONTI.STG.layout.screens[i].blocks.some(b=>b.type==='strip'&&!b.hidden)", host): fail('%s 준비: 메모 띠가 하나 악보를 안 나눔 %s' % (k, pg.evaluate(LAYX)))
            show_all(pg)
            st = pg.evaluate(ST)
            if st['total'] != len(ref) or st['hidden'] or pg.evaluate(SONGS) != ref: fail('%s 그 모드에서 되돌린 화면 차례가 다름: %s (기대 %s)' % (k, pg.evaluate(SONGS), ref))
            clean(pg, k + ' 되돌린 뒤')
            set_form(pg, 'block')
            if pg.evaluate(SONGS) != ref: fail('%s 조각 위로 돌아온 화면 차례가 다름: %s (기대 %s)' % (k, pg.evaluate(SONGS), ref))
            clean(pg, k + ' 조각 위로', ref)
            exit_stage(pg)
            print('%s — 메모 띠가 나눈 화면의 무리 둘을 되돌려도 하나·하나·둘·둘 차례 (그 모드 · 조각 위로) ok' % k, flush=True)
        if errs: fail('4부 데스크톱 콘솔 오류: %s' % errs[:3])
        b.close()
    box['ok'] = True

# 화면 i 의 숨긴 🗑 무리 블록 id (블록 줄 차례) — 지금 조판 · 저장본
LONE_IDS = "(i)=>(CONTI.STG.layout.screens[i]||{blocks:[]}).blocks.filter(b=>b.hidden&&b.lone).map(b=>String(b.id))"
LONE_SAVED = """([slot,i])=>{const v=((CONTI.PREFS.data||{}).stage||{})[slot];const sc=v&&v.screens&&v.screens[i];
 return sc?(sc.blocks||[]).filter(b=>b.hidden&&b.lone).map(b=>String(b.id)):null}"""
# 블록 id 의 상자 가운데에 그려진 블록 (무대 쪽 · data-sblk)
TOP_AT = """(id)=>{const S=CONTI.STG;const b=S.layout.screens[S.screen].blocks.find(x=>String(x.id)===id);if(!b)return 'no '+id;
 const r=document.querySelector('#stageWrap .stgpage').getBoundingClientRect();
 const e=document.elementFromPoint(r.left+(b.x+b.w/2)*r.width,r.top+(b.y+b.h/2)*r.height);const k=e&&e.closest('.blk');
 return k?k.getAttribute('data-sblk')||'blk':String(e&&e.className)}"""

def run4_desk2(box):
    # 데스크톱 2열 · 하나/둘/셋/넷 — 한 화면에 곡 둘
    with sync_playwright() as p:
        b = p.chromium.launch()
        c = b.new_context(viewport={'width': 1600, 'height': 1000}, service_workers='block')
        pg = c.new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(repr(e)[:200])); pg.on('dialog', lambda d: d.accept())
        new_team_service(pg, 'y' + tag, '11/2 주일')
        for t in ['하나', '둘', '셋', '넷']: add_song(pg, t)
        sid = pg.evaluate("CONTI.S.services[0].id"); slot = 'lay:%s~desktop' % sid
        publish(pg, sid)
        open_stage(pg, sid)
        edit_on(pg); set_form(pg, 'block'); auto_again(pg); nudge(pg); edit_off(pg)
        order = ['h0', 's0.0.0', 'h1', 's1.0.0']
        if pg.evaluate(SONGS) != [[0, 1], [2, 3]] or pg.evaluate("CONTI.STG.layout.screens[0].blocks.map(b=>String(b.id))") != order:
            fail('4부 준비: 한 화면에 곡 둘(하나 송폼·하나 악보·둘 송폼·둘 악보)이 아님 %s' % pg.evaluate(LAYX))
        base = pg.evaluate("(slot)=>CONTI.PREFS.data.stage[slot]", slot)
        exit_stage(pg)
        # 둘 송폼(h1)을 하나 악보(s0.0.0) 위로 — 사람이 그렇게 둔 자리
        for bl in base['screens'][0]['blocks']:
            if bl['id'] == 'h1': bl['x'] = 0.08; bl['y'] = 0.40
        open_in(pg, sid, slot, base, 'block')
        if pg.evaluate(TOP_AT, 'h1') != 'head:1': fail('4부 준비: 하나 악보 위에 둘 송폼이 안 보임 %s' % pg.evaluate(TOP_AT, 'h1'))
        edit_on(pg); goto_screen(pg, 0); hide_all_here(pg); trash(pg)
        if pg.evaluate(ST)['total'] != 1 or pg.evaluate(LONE_IDS, 0) != order: fail('4부 준비: 무리가 하나 송폼·하나 악보·둘 송폼·둘 악보가 아님 %s' % pg.evaluate(LAYX))
        edit_off(pg); gb = pg.evaluate("(slot)=>CONTI.PREFS.data.stage[slot]", slot); exit_stage(pg)
        for f in FORMS:
            k = '16 %s' % f
            open_in(pg, sid, slot, gb, f); edit_on(pg)
            if pg.evaluate(LONE_IDS, 0) != order: fail('%s 그 모드 조판의 무리 차례가 바뀜: %s (main 과 같게 %s)' % (k, pg.evaluate(LONE_IDS, 0), order))
            nudge(pg); edit_off(pg)
            if pg.evaluate(LONE_SAVED, [slot, 0]) != order: fail('%s 그 모드로 저장한 무리 차례가 바뀜: %s (main 과 같게 %s)' % (k, pg.evaluate(LONE_SAVED, [slot, 0]), order))
            sv = pg.evaluate("(slot)=>CONTI.PREFS.data.stage[slot]", slot); exit_stage(pg)
            open_in(pg, sid, slot, sv, 'block'); edit_on(pg)
            if pg.evaluate(LONE_IDS, 0) != order: fail('%s 조각 위로 돌아온 무리 차례가 바뀜: %s' % (k, pg.evaluate(LONE_IDS, 0)))
            show_all(pg); edit_off(pg)
            pg.evaluate("(()=>{const S=CONTI.STG;S.screen=S.nav[0];window.dispatchEvent(new Event('resize'))})()"); pg.wait_for_timeout(500)
            if pg.evaluate("CONTI.STG.layout.screens[CONTI.STG.screen].blocks.map(b=>String(b.id))") != order or pg.evaluate(ST)['hidden']:
                fail('%s 되돌린 화면의 블록 차례가 바뀜: %s' % (k, pg.evaluate(LAYX)))
            if pg.evaluate(TOP_AT, 'h1') != 'head:1': fail('%s 되돌린 뒤 둘 송폼이 하나 악보 밑에 묻힘 (그 자리에 %s)' % (k, pg.evaluate(TOP_AT, 'h1')))
            exit_stage(pg)
            print('%s — 한 무리의 두 곡 블록 차례가 그 모드·저장본·조각 위로 돌아와 되돌린 뒤에도 main 그대로 (둘 송폼이 하나 악보 위) ok' % k, flush=True)
        if errs: fail('4부 데스크톱 2열 콘솔 오류: %s' % errs[:3])
        b.close()
    box['ok'] = True

def run4():
    boxes = [('태블릿', {}), ('데스크톱', {}), ('데스크톱 2열', {})]
    ths = [threading.Thread(target=run4_tab, args=(boxes[0][1],), name='4부 태블릿', daemon=True),
           threading.Thread(target=run4_desk, args=(boxes[1][1],), name='4부 데스크톱', daemon=True),
           threading.Thread(target=run4_desk2, args=(boxes[2][1],), name='4부 데스크톱 2열', daemon=True)]
    for t in ths: t.start()
    for t in ths: t.join()
    bad = [n for n, bx in boxes if not bx.get('ok')]
    if bad: fail('4부 %s 가 끝까지 못 감 (위 FAIL)' % ', '.join(bad))
    print('4부 다른 송폼 모드 — 모두 숨긴 화면은 보기에서 건너뛰고 빈 곡 화면은 남김 · 한 화면의 무리 둘을 되돌려도 제 차례 · 한 무리의 두 곡 블록 차례는 main 그대로 ok')

if PART in ('', '1'): run1()
if PART in ('', '2'): run2()
if PART in ('', '3'): run3()
if PART in ('', '4'): run4()
print('OK — 무대 빈 화면')
