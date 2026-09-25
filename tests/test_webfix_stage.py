# 운영 점검(2026-09-25) 무대 모드 회귀 검사
#   desk-1  ✎ 편집을 켰다 끄기만 해도 조판이 왼쪽 끝으로 붙어 저장됨 — 자동 조판은 쓰는 열이 캔버스보다 좁으면
#           가운데에 놓는데(stageRender box.left) 고칠 수 있는 조판으로 바꿀 때(stgToLayout) 그 몫을 빠뜨렸다.
#           아무것도 안 고치고 끄면 '손으로 고친 조판'으로 남기지 않는다 · ↻ 뒤 끄면 자동으로 돌아간다
#   phone-1 무대 메모 띠가 '나만' 메모를 '전체'로 표시 — 연습 화면(noteChip)처럼 '나'
#   phone-2 폰 무대 메모 띠가 끝 메모를 말줄임표 없이 잘라 읽을 길이 없음 — 칩이 줄어들며 …, 잘린 띠를 탭하면 전문
import os, sys, time
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
SHEET = os.path.join(ROOT, 'docs', 'sample_sheet.jpg')
SHOT = os.environ.get('SHOT_DIR')   # 주면 폰 무대 띠·메모 창을 찍어 둔다
tag = str(int(time.time()))[-6:]
def fail(m): print('FAIL:', m); sys.exit(1)

def open_stage(pg, sid, reload=False):
    if pg.locator('#stageWrap').count(): pg.click('[data-stg="exit"]'); pg.wait_for_timeout(500)
    pg.goto(URL + '#/view/' + sid)
    if reload: pg.reload()
    pg.wait_for_selector('[data-act="play"][data-stage="1"]', timeout=15000); pg.wait_for_timeout(900)
    pg.click('[data-act="play"][data-stage="1"]')
    pg.wait_for_selector('#stageWrap .stgpage', timeout=15000); pg.wait_for_timeout(800)

# 블록들이 차지한 가로 범위를 화면(.stgpage) 폭에 대한 비율로 — 편집 중에는 화면을 줄여(scale) 그리므로 비율로 잰다
GAPS = """()=>{const pg=document.querySelector('#stageWrap .stgpage');const pr=pg.getBoundingClientRect();
 const els=[...pg.querySelectorAll(pg.classList.contains('edit')?'.sblk':'.blk,.pstrip')].filter(e=>!e.parentElement.closest('.blk,.sblk'));
 if(!els.length)return null;
 const L=Math.min(...els.map(e=>e.getBoundingClientRect().left)),R=Math.max(...els.map(e=>e.getBoundingClientRect().right));
 return {l:(L-pr.left)/pr.width,r:(pr.right-R)/pr.width,W:pr.width}}"""
# 인도자 전체 · 나만 · 내 세션 공유 메모 (메모는 콘티 쪽 svc.items 에만 산다 — 발행본에는 없다). 무대가 보는 세션을 돌려준다
LONG = '브릿지에서는 패드만 길게 깔고 리듬은 빼 주세요'
NOTES = """([sid,LONG])=>{const s=CONTI.S.services.find(x=>x.id===sid);const it=s.items[0];
  const ses=CONTI.pl().session||CONTI.S.team.me.session||'전체';
  it.notes=[{id:'wfs-lead',marker:'wfm1',layer:'leader',session:null,text:'인도자 전체 메모',author:'인도자'},
            {id:'wfs-mine',marker:'wfm1',layer:'mine',session:null,text:'내 개인 메모',author:'하은'},
            {id:'wfs-sess',marker:'wfm1',layer:'session',session:ses,text:'세션 공유 메모 · '+LONG,author:'하은'}];CONTI.save();return ses}"""
SLOT = "(()=>'lay:'+CONTI.STG.svc.id+'~tab-l')()"
# 내 조판(서버·기기 사본)을 지운다 — 추천 조판만 있는 사람(처음 여는 멤버)과 같게
CLEAR_MINE = """async (slot)=>{await fetch('/api/me/prefs/stage/'+encodeURIComponent(slot),{method:'PUT',credentials:'include',
  headers:{'content-type':'application/json','x-conti':'1'},body:JSON.stringify({value:null})});
  Object.keys(localStorage).filter(k=>k.indexOf('conti-'+slot+'@')===0).forEach(k=>localStorage.removeItem(k))}"""

def pop_hint(pg):
    pg.click('[data-stg="cfg"]'); pg.wait_for_selector('.stgpop', timeout=5000)
    h = pg.locator('.stgpop .hint').last.inner_text()
    pg.click('[data-stg="cfg"]'); pg.wait_for_timeout(300)
    return h

def saved(pg):
    # 서버(설정)와 기기 사본에 남은 이 예배 조판
    return pg.evaluate("""async (slot)=>{const r=await fetch('/api/me/prefs',{credentials:'include'});const j=await r.json();
      const loc=Object.keys(localStorage).filter(k=>k.indexOf('conti-'+slot+'@')===0).map(k=>localStorage.getItem(k));
      return {srv:((j.prefs||{}).stage||{})[slot]||null,loc:loc.filter(v=>v&&v!=='null')}}""", pg.evaluate(SLOT))

def centered(g, what):
    if not g: fail('%s 블록이 없음' % what)
    if abs(g['l'] - g['r']) > 0.01: fail('%s 가운데가 아님 (왼쪽 %.3f · 오른쪽 %.3f)' % (what, g['l'], g['r']))

def run():
  with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    ctx = b.new_context(viewport={'width': 1366, 'height': 900})   # 노트북 — tab-l (2열 캔버스에 곡 하나)
    pg = ctx.new_page()
    pg.on('pageerror', lambda e: errs.append(repr(e)[:300])); pg.on('dialog', lambda d: d.accept())
    pg.goto(URL); pg.wait_for_selector('#lgUser', timeout=10000)
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName')
    pg.check('#lgAgree')
    pg.fill('#lgName', '하은'); pg.fill('#lgUser', 'wfs' + tag); pg.fill('#lgPass', 'secret1'); pg.click('[data-act="lg-submit"]')
    pg.wait_for_selector('#gtTeam', timeout=10000); pg.fill('#gtTeam', '무대팀'); pg.click('#gtSess .q:has-text("건반")')
    pg.click('[data-act="team-create"]'); pg.wait_for_selector('.shell[data-page]', timeout=15000)

    pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]', timeout=8000)
    pg.fill('[data-f="svc.name"]', '점검 예배'); pg.wait_for_timeout(300)
    si = pg.evaluate("CONTI.S.services.findIndex(s=>s.name==='점검 예배')")
    pg.click('[data-act="add-item"]'); pg.wait_for_timeout(400)
    pg.fill('[data-f="item.title"]', '한 곡'); pg.fill('[data-f="item.key"]', 'G'); pg.fill('[data-f="item.form"]', 'Int – AABB')
    pg.set_input_files('#pieceFile', [SHEET])
    pg.wait_for_function("(si)=>{const it=CONTI.S.services[si].items[0];const p=it&&(it.pieces||[])[0];return p&&p.w>0}", arg=si, timeout=120000)
    pg.wait_for_timeout(700)
    pg.evaluate("""(si)=>{const it=CONTI.S.services[si].items[0];const p=it.pieces[0];
      p.markers=[{id:'wfm1',label:'A',x:Math.round(p.w*0.08),y:Math.round(p.h*0.35),cut:null}];CONTI.save()}""", si)
    pg.click('[data-act="publish"]'); pg.wait_for_selector('#pubOnly', timeout=8000)
    pg.click('#pubOnly'); pg.wait_for_timeout(3000)
    sid = pg.evaluate("(si)=>CONTI.S.services[si].id", si)

    # ================= desk-1 =================
    open_stage(pg, sid)
    if pg.evaluate("CONTI.STG.layout"): fail('준비: 처음부터 고친 조판이 있음')
    if pg.evaluate("CONTI.STG.lay.cols") < 2: fail('준비: 캔버스가 한 열뿐이라 가운데 맞춤을 잴 수 없음')
    auto = pg.evaluate(GAPS); centered(auto, '자동 조판')
    if auto['l'] < 0.05: fail('준비: 자동 조판이 캔버스를 꽉 채움 %s' % auto)

    pg.click('[data-stg="edit"]'); pg.wait_for_timeout(500)
    g = pg.evaluate(GAPS)
    if abs(g['l'] - auto['l']) > 0.01: fail('desk-1 편집을 켜자 조판이 옆으로 옮겨짐 (자동 왼쪽 %.3f → 편집 %.3f)' % (auto['l'], g['l']))
    xs = pg.evaluate("CONTI.STG.layout.screens[0].blocks.map(b=>b.x)")
    if min(xs) < 0.05: fail('desk-1 고칠 수 있는 조판이 왼쪽 끝(x=%s)' % xs)
    pg.click('[data-stg="edit"]'); pg.wait_for_timeout(1500)
    centered(pg.evaluate(GAPS), 'desk-1 편집을 켰다 끈 뒤')
    if pg.evaluate("CONTI.STG.layout"): fail('desk-1 아무것도 안 고쳤는데 손으로 고친 조판이 남음')
    if '손으로 고친' in pop_hint(pg): fail('desk-1 안 고쳤는데 ⚙ 에 손으로 고친 조판이라고 나옴')
    sv = saved(pg)
    if sv['srv'] or sv['loc']: fail('desk-1 안 고쳤는데 조판이 저장됨 %s' % str(sv)[:200])
    print('desk-1 편집 켜기·끄기 — 자동 조판 그대로 가운데 · 저장 안 됨 ok', auto)

    # 진짜 옮기면 남는다 (그대로 두면 안 고친 것으로 치는 것이 옮긴 것까지 버리지 않게)
    pg.click('[data-stg="edit"]'); pg.wait_for_timeout(500)
    blk = pg.locator('.sblk').last; bb = blk.bounding_box()
    pg.mouse.move(bb['x'] + bb['width'] / 2, bb['y'] + 30); pg.mouse.down()
    pg.mouse.move(bb['x'] + bb['width'] / 2 + 120, bb['y'] + 30, steps=10); pg.mouse.up(); pg.wait_for_timeout(400)
    pg.click('[data-stg="edit"]'); pg.wait_for_timeout(1500)
    if not pg.evaluate("CONTI.STG.layout"): fail('desk-1 옮긴 조판이 사라짐')
    if '손으로 고친' not in pop_hint(pg): fail('desk-1 옮긴 뒤 ⚙ 에 손으로 고친 조판이 안 나옴')
    sv = saved(pg)
    if not sv['srv'] or not sv['loc']: fail('desk-1 옮긴 조판이 저장 안 됨 %s' % str(sv)[:200])
    moved = pg.evaluate(GAPS)
    if auto['r'] - moved['r'] < 0.03: fail('desk-1 옮긴 자리가 안 남음 %s' % moved)
    # 새로고침해도 옮긴 자리
    open_stage(pg, sid, reload=True)
    g = pg.evaluate(GAPS)
    if abs(g['l'] - moved['l']) > 0.01 or abs(g['r'] - moved['r']) > 0.01: fail('desk-1 새로고침 뒤 옮긴 자리가 아님 %s' % g)
    print('desk-1 옮긴 조판은 남음 ok', moved)

    # ↻ 자동으로 다시 → 끄면 자동 조판으로 (가운데, 저장본 없음)
    pg.click('[data-stg="edit"]'); pg.wait_for_timeout(500)
    pg.click('[data-stg="auto"]'); pg.wait_for_timeout(600)
    g = pg.evaluate(GAPS)
    if abs(g['l'] - auto['l']) > 0.01: fail('desk-1 ↻ 뒤 편집 조판이 가운데가 아님 %s' % g)
    pg.click('[data-stg="edit"]'); pg.wait_for_timeout(1500)
    centered(pg.evaluate(GAPS), 'desk-1 ↻ 뒤 끈 조판')
    if pg.evaluate("CONTI.STG.layout"): fail('desk-1 ↻ 뒤 끄자 자동 조판을 옮겨 적은 조판이 다시 저장됨')
    sv = saved(pg)
    if sv['srv'] or sv['loc']: fail('desk-1 ↻ 뒤에도 조판이 남음 %s' % str(sv)[:200])
    open_stage(pg, sid, reload=True)
    centered(pg.evaluate(GAPS), 'desk-1 ↻ 뒤 새로고침')
    if '손으로 고친' in pop_hint(pg): fail('desk-1 ↻ 뒤 새로고침했는데 손으로 고친 조판')
    # 이 조판 그대로 내보내기(자동 조판)도 화면처럼 가운데 · 메모 띠 이름표도 무대와 같다 (phone-1 — 인쇄도 같은 띠를 쓴다)
    pg.evaluate(NOTES, [sid, LONG]); pg.evaluate("window.dispatchEvent(new Event('resize'))"); pg.wait_for_timeout(600)
    centered(pg.evaluate(GAPS), 'desk-1 메모 띠가 선 자동 조판')
    pg.click('[data-stg="export"]'); pg.wait_for_selector('#pvGo', timeout=8000); pg.click('#pvGo')
    pg.wait_for_selector('#printArea .ppage', timeout=15000); pg.wait_for_timeout(800)
    pv = pg.evaluate("""()=>{const c=document.querySelector('#printArea .ppage .pclip')||document.querySelector('#printArea .ppage .pinner');
      const r=c.getBoundingClientRect();const els=[...c.querySelectorAll('.blk,.pstrip')];
      const L=Math.min(...els.map(e=>e.getBoundingClientRect().left)),R=Math.max(...els.map(e=>e.getBoundingClientRect().right));
      return {l:(L-r.left)/r.width,r:(r.right-R)/r.width}}""")
    if abs(pv['l'] - pv['r']) > 0.02: fail('desk-1 내보낸 종이가 가운데가 아님 %s' % pv)
    pw = pg.evaluate("""()=>[...document.querySelectorAll('#printArea .pstrip .m')].map(m=>m.querySelector('.who').textContent+'|'+m.textContent)""")
    if not any(w.startswith('나|') and '내 개인 메모' in w for w in pw): fail('phone-1 인쇄 띠에서 나만 메모 이름이 나가 아님 %s' % pw)
    pg.evaluate("(()=>{const a=document.querySelector('#printArea');if(a)a.remove();document.body.classList.remove('printing')})()")
    print('desk-1 ↻ 자동으로 다시 → 자동 조판 · 내보내기도 가운데 ok', pv)

    # 인도자 추천 조판이 있는 예배: ↻ 자동으로 다시 → 끄기는 다음에 열어도 자동이다.
    # 비워 두기(null)만 남기면 '내 조판 없음'으로 보고 추천 조판(옮긴 블록 · 손으로 고친 조판)으로 돌아갔다
    open_stage(pg, sid, reload=True)
    auto2 = pg.evaluate(GAPS); centered(auto2, 'desk-1 추천 전 자동 조판')
    pg.click('[data-stg="edit"]'); pg.wait_for_timeout(500)
    blk = pg.locator('.sblk').last; bb = blk.bounding_box()
    pg.mouse.move(bb['x'] + bb['width'] / 2, bb['y'] + 30); pg.mouse.down()
    pg.mouse.move(bb['x'] + bb['width'] / 2 + 120, bb['y'] + 30, steps=10); pg.mouse.up(); pg.wait_for_timeout(400)
    pg.click('[data-sc="rec"]'); pg.wait_for_timeout(1500)
    pg.click('[data-stg="edit"]'); pg.wait_for_timeout(1500)
    rec = pg.evaluate("(()=>{const L=((CONTI.STG.svc.published||{}).stageLayouts||{})['tab-l'];return !!(L&&L.screens)})()")
    if not rec: fail('준비: 인도자 추천 조판이 발행본에 안 붙음')
    moved2 = pg.evaluate(GAPS)
    if auto2['r'] - moved2['r'] < 0.015: fail('준비: 추천한 조판이 옮긴 자리가 아님 %s / 자동 %s' % (moved2, auto2))
    pg.click('[data-stg="edit"]'); pg.wait_for_timeout(500)
    pg.click('[data-stg="auto"]'); pg.wait_for_timeout(600)
    pg.click('[data-stg="edit"]'); pg.wait_for_timeout(1500)
    centered(pg.evaluate(GAPS), 'desk-1 추천이 있는 예배에서 ↻ 뒤 끈 조판')
    if pg.evaluate("CONTI.STG.layout"): fail('desk-1 추천이 있는 예배에서 ↻ 뒤 끄자 조판이 남음')
    if '손으로 고친' in pop_hint(pg): fail('desk-1 추천이 있는 예배에서 ↻ 뒤 손으로 고친 조판이라고 나옴')
    sv = saved(pg)
    if not (sv['srv'] or {}).get('auto') or (sv['srv'] or {}).get('screens'): fail('desk-1 추천이 있는데 자동으로 보기로 한 것이 서버에 안 남음 %s' % str(sv)[:200])
    if not sv['loc'] or '"auto"' not in sv['loc'][0]: fail('desk-1 추천이 있는데 자동으로 보기로 한 것이 기기에 안 남음 %s' % str(sv)[:200])
    for how in ('다시 열기', '새로고침'):
        open_stage(pg, sid, reload=(how == '새로고침')); pg.wait_for_timeout(1500)   # 열 때 추천을 다시 받는 것(stageOpen)까지 기다린다
        g = pg.evaluate(GAPS)
        centered(g, 'desk-1 ↻ 뒤 %s (추천이 있는 예배)' % how)
        if pg.evaluate("CONTI.STG.layout"): fail('desk-1 ↻ 뒤 %s하자 추천 조판으로 돌아감 %s' % (how, g))
        if '손으로 고친' in pop_hint(pg): fail('desk-1 ↻ 뒤 %s했는데 손으로 고친 조판' % how)
    # 내 것을 지우면(추천만 있는 사람 — 처음 여는 멤버와 같다) 추천 조판으로 연다 · 거기서 옮기면 내 조판으로 남는다
    pg.evaluate(CLEAR_MINE, pg.evaluate(SLOT))
    open_stage(pg, sid, reload=True); pg.wait_for_timeout(1500)
    g = pg.evaluate(GAPS)
    if not pg.evaluate("CONTI.STG.layout") or abs(g['r'] - moved2['r']) > 0.01: fail('desk-1 내 조판이 없는데 추천 조판으로 안 열림 %s' % g)
    pg.click('[data-stg="edit"]'); pg.wait_for_timeout(500)
    blk = pg.locator('.sblk').last; bb = blk.bounding_box()
    pg.mouse.move(bb['x'] + bb['width'] / 2, bb['y'] + 30); pg.mouse.down()
    pg.mouse.move(bb['x'] + bb['width'] / 2 - 60, bb['y'] + 30, steps=10); pg.mouse.up(); pg.wait_for_timeout(400)
    pg.click('[data-stg="edit"]'); pg.wait_for_timeout(1500)
    mine = pg.evaluate(GAPS); sv = saved(pg)
    if not (sv['srv'] or {}).get('screens'): fail('desk-1 추천에서 옮긴 조판이 내 조판으로 안 남음 %s' % str(sv)[:200])
    open_stage(pg, sid, reload=True); pg.wait_for_timeout(1500)
    g = pg.evaluate(GAPS)
    if abs(g['r'] - mine['r']) > 0.01: fail('desk-1 추천에서 옮긴 내 조판이 새로고침 뒤 아님 %s / %s' % (g, mine))
    print('desk-1 추천 조판이 있어도 ↻ 자동으로 다시 → 다시 열어도 자동 · 추천·내 조판은 그대로 ok')

    # ================= phone-1 · phone-2 =================
    st = ctx.storage_state()
    pc = b.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, storage_state=st)
    ph = pc.new_page()
    ph.on('pageerror', lambda e: errs.append(repr(e)[:300])); ph.on('dialog', lambda d: d.accept())
    ph.goto(URL + '#/view/' + sid); ph.wait_for_selector('[data-act="play"][data-stage="1"]', timeout=20000); ph.wait_for_timeout(1500)
    ses = ph.evaluate(NOTES, [sid, LONG])
    ph.click('[data-act="play"][data-stage="1"]'); ph.wait_for_selector('#stageWrap .pstrip', timeout=15000); ph.wait_for_timeout(800)
    if ph.evaluate("CONTI.STG.layout"): fail('준비: 폰인데 고친 조판')
    chips = ph.evaluate("""()=>[...document.querySelectorAll('#stageWrap .pstrip .m')].map(m=>({who:m.querySelector('.who').textContent,
      text:m.textContent.slice(m.querySelector('.who').textContent.length),title:m.title}))""")
    if len(chips) != 3: fail('준비: 메모 칩이 %d개 %s' % (len(chips), chips))
    if any(c['title'] != c['text'] for c in chips): fail('phone-2 칩에 전문(title)이 없음 %s' % chips)
    who = {c['text'].split(' ')[0]: c['who'] for c in chips}
    if who.get('내') != '나': fail('phone-1 나만 메모 칩 이름이 %r (연습 화면처럼 나)' % who.get('내'))
    if who.get('인도자') != '전체': fail('phone-1 인도자 전체 메모 이름이 %r' % who.get('인도자'))
    if who.get('세션') != ses: fail('phone-1 세션 메모 이름이 %r (기대 %r)' % (who.get('세션'), ses))
    print('phone-1 무대 메모 칩 이름 ok', who)

    # 띠 밖으로 잘린 칩이 없다 — 모자라면 칩이 줄고 글자 끝에 … 가 선다
    r = ph.evaluate("""()=>{const s=document.querySelector('#stageWrap .pstrip');const sr=s.getBoundingClientRect();
      return [...s.querySelectorAll('.m')].map(m=>{const q=m.getBoundingClientRect();const t=m.querySelector('.tx');
        const cs=t&&getComputedStyle(t);
        return {right:Math.round(q.right-sr.right),vis:q.width,cut:!!t&&t.scrollWidth>t.clientWidth+1,
          ell:!!cs&&cs.textOverflow==='ellipsis'&&cs.overflow==='hidden'&&cs.display!=='inline'}})}""")
    if any(c['right'] > 1 for c in r): fail('phone-2 띠 끝에서 칩이 잘림 %s' % r)
    if not any(c['cut'] for c in r): fail('준비: 줄어든 칩이 없음 (띠가 넉넉함) %s' % r)
    if any(c['cut'] and not c['ell'] for c in r): fail('phone-2 줄어든 칩에 말줄임표가 없음 %s' % r)
    if any(c['vis'] < 24 for c in r): fail('phone-2 칩이 너무 줄어 안 보임 %s' % r)
    # 긴 메모부터 준다 — 짧은 메모는 다 보이고, 준 칩은 다 보이는 칩보다 좁지 않다
    if r[1]['cut'] or not r[2]['cut']: fail('phone-2 짧은 메모가 줄거나 긴 메모가 안 줄어듦 %s' % r)
    full_w = max([c['vis'] for c in r if not c['cut']] or [0]); cut_w = min([c['vis'] for c in r if c['cut']])
    if cut_w < full_w - 1: fail('phone-2 긴 메모보다 짧은 메모가 더 줄어듦 %s' % r)
    if SHOT: ph.screenshot(path=os.path.join(SHOT, 'webfix_stage_phone.png'))
    print('phone-2 칩은 띠 안에서 줄고 … ok', r)

    # 잘린 띠를 탭하면 메모 전문이 뜬다 (화면은 안 넘어간다) · 바깥 탭으로 닫힌다
    s0 = ph.evaluate("CONTI.STG.screen")
    ph.locator('#stageWrap .pstrip').first.tap(); ph.wait_for_timeout(500)
    box = ph.locator('#stageWrap .stgmemo')
    if not box.count(): fail('phone-2 잘린 메모 띠를 탭해도 전문이 안 뜸')
    full = box.inner_text()
    if SHOT: ph.screenshot(path=os.path.join(SHOT, 'webfix_stage_memo.png'))
    for t in ['인도자 전체 메모', '내 개인 메모', LONG]:
        if t not in full: fail('phone-2 전문에 %r 이 없음: %r' % (t, full))
    ws = ph.evaluate("[...document.querySelectorAll('#stageWrap .stgmemo .who')].map(e=>e.textContent)")
    if ws != ['전체', '나', ses]: fail('phone-2 전문의 이름표가 띠와 다름: %s' % ws)
    ok = ph.evaluate("""()=>{const e=document.querySelector('#stageWrap .stgmemo');const r=e.getBoundingClientRect();
      return r.left>=0&&r.right<=innerWidth&&r.top>=0&&r.bottom<=innerHeight}""")
    if not ok: fail('phone-2 전문 창이 화면 밖으로 나감')
    if ph.evaluate("CONTI.STG.screen") != s0: fail('phone-2 띠를 탭하자 화면이 넘어감')
    ph.mouse.click(195, 700); ph.wait_for_timeout(400)
    if ph.locator('#stageWrap .stgmemo').count(): fail('phone-2 바깥을 탭해도 전문 창이 안 닫힘')
    print('phone-2 탭하면 메모 전문 ok')
    # 다 보이는 띠는 전처럼 — 탭해도 창이 안 뜬다 (화면이 여럿이면 다음 화면으로 넘긴다)
    ph.evaluate("""(sid)=>{const it=CONTI.S.services.find(x=>x.id===sid).items[0];it.notes=it.notes.slice(0,2);
      window.dispatchEvent(new Event('resize'))}""", sid); ph.wait_for_timeout(600)
    if ph.evaluate("[...document.querySelectorAll('#stageWrap .pstrip .tx')].some(t=>t.scrollWidth>t.clientWidth+1)"): fail('준비: 짧은 메모뿐인데 줄어듦')
    ph.locator('#stageWrap .pstrip').first.tap(); ph.wait_for_timeout(400)
    if ph.locator('#stageWrap .stgmemo').count(): fail('phone-2 다 보이는 띠를 탭했는데 전문 창이 뜸')
    print('phone-2 다 보이는 띠는 전처럼 ok')

    if errs: fail('페이지 오류: %s' % errs[:3])
    b.close()
  print('OK test_webfix_stage')

run()
