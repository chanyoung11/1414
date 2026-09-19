# 무대 모드 = 자동 조판 (인쇄·내보내기 명세 §1-A, 인수 기준 9~11)
# 한 곡이 한 화면에, 스크롤 없음. ⚙ 조판은 그 곡·그 기기·그 사람에게만.
import os, sys, time
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
SHEET = os.path.join(ROOT, 'docs', 'sample_sheet.jpg')
def fail(m): print('FAIL:', m); sys.exit(1)

def open_pop(pg):
    # ⚙ 는 토글이다. 이미 열려 있으면 그대로 쓴다
    if not pg.locator('.stgpop').count():
        pg.click('[data-stg="cfg"]')
    pg.wait_for_selector('.stgpop', timeout=5000)

def run():
    tag = str(int(time.time()))[-6:]
    with sync_playwright() as p:
        b = p.chromium.launch()
        c = b.new_context(viewport={'width':1180,'height':820})   # iPad 가로
        pg = c.new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(repr(e)[:300])); pg.on('dialog', lambda d: d.accept())
        pg.goto(URL); pg.wait_for_selector('#lgUser')
        pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName')
        pg.check('#lgAgree')   # 약관·개인정보처리방침 동의 (필수)
        pg.fill('#lgName','하은'); pg.fill('#lgUser','st'+tag); pg.fill('#lgPass','secret1'); pg.click('[data-act="lg-submit"]')
        pg.wait_for_selector('#gtTeam'); pg.fill('#gtTeam','무대팀'); pg.click('#gtSess .q:has-text("건반")'); pg.click('[data-act="team-create"]')
        pg.wait_for_selector('.shell[data-page]', timeout=10000)

        pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]', timeout=8000)
        pg.fill('[data-f="svc.name"]','10/4 주일 2부')
        for title, key in [('예수로 나의 구주 삼고','G'), ('시간을 뚫고','A')]:
            pg.click('[data-act="add-item"]'); pg.wait_for_timeout(400)
            pg.fill('[data-f="item.title"]', title); pg.fill('[data-f="item.key"]', key)
            pg.fill('[data-f="item.form"]','Int – AABB – (Key up)C')
            pg.set_input_files('#pieceFile', [SHEET])
            pg.wait_for_function("(()=>{const its=CONTI.S.services[0].items;const it=its[its.length-1];const p=(it.pieces||[])[0];return p&&p.w>0})()", timeout=90000)
            pg.wait_for_timeout(800)
        sid = pg.evaluate("CONTI.S.services[0].id")
        pg.goto(URL + '#/view/' + sid); pg.wait_for_selector('[data-act="play"][data-stage="1"]', timeout=10000); pg.wait_for_timeout(1200)

        # ---- 무대 모드 열기 ----
        pg.click('[data-act="play"][data-stage="1"]'); pg.wait_for_selector('#stageWrap .stgpage', timeout=15000); pg.wait_for_timeout(900)

        # 인수 9: 한 화면 · 스크롤 없음
        def screens():
            return pg.evaluate("(()=>CONTI.STG&&CONTI.STG.nscreens||-1)()")
        if screens() != 1: fail('iPad 가로에서 한 화면에 안 들어감: %s화면' % screens())
        scrolls = pg.evaluate("""(()=>{const w=document.querySelector('#stageWrap');
           return {sx:w.scrollWidth>w.clientWidth+1, sy:w.scrollHeight>w.clientHeight+1,
                   bx:document.body.scrollWidth>window.innerWidth+1}})()""")
        if scrolls['sx'] or scrolls['sy'] or scrolls['bx']: fail('무대에 스크롤이 생김: %s' % scrolls)
        print('가로 한 화면 · 스크롤 없음 ok')

        # 페이지 밖으로 삐져나온 블록이 없다
        over = pg.evaluate("""(()=>{const pp=document.querySelector('.stgpage');const pr=pp.getBoundingClientRect();const bad=[];
           pp.querySelectorAll('.blk,.pstrip').forEach(b=>{const r=b.getBoundingClientRect();
             if(r.right>pr.right+0.6||r.left<pr.left-0.6||r.bottom>pr.bottom+0.6)bad.push(b.className)});return bad})()""")
        if over: fail('화면 밖으로 나간 블록: %s' % over[:5])
        print('화면 밖 넘침 없음 ok')

        # 인수 1: 오선 중간에서 잘린 시스템이 없다 — 모든 경계가 줄 사이 여백 안
        bad = pg.evaluate("""(()=>{const f=CONTI.STG.lay;const out=[];
           f.screens.forEach(pgx=>pgx.blocks.filter(b=>b.type==='slice').forEach(b=>{
             const gaps=b.pc.im.gaps||[],H=b.pc.im.h;
             const ok=v=>v<=2||v>=H-2||gaps.some(q=>v>=q.s-4&&v<=q.e+4);
             b.ranges.forEach(r=>{if(!ok(r[0]))out.push(['start',Math.round(r[0])]);
                                  if(!ok(r[1]))out.push(['end',Math.round(r[1])])})}));
           return out})()""")
        if bad: fail('여백 밖에서 잘린 경계: %s' % bad[:6])
        print('오선 중간 절단 없음 ok')
        pg.screenshot(path=os.path.join(ROOT,'tests','t_stage_land.png'))

        # 곡 이동 — v2 는 넘김 단위가 '화면'이다.
        # 두 곡이 한 화면에 있으면 그 곡 조각을 탭해서 바를 바꾼다 (기획 §5)
        if screens() > 1:
            pg.keyboard.press('ArrowRight'); pg.wait_for_timeout(900)
            if pg.evaluate("CONTI.STG.screen") != 1: fail('→ 로 다음 화면 이동 안 됨')
        else:
            pg.click('[data-si="1"]'); pg.wait_for_timeout(700)
        if pg.evaluate("CONTI.STG.idx") != 1: fail('둘째 곡으로 안 바뀜')
        # 기본(송폼을 곡마다 블록으로)에서는 맨 위에 곡명을 쓰지 않는다
        if pg.locator('.stgbar b').inner_text().strip(): fail('맨 위에 곡명이 남음: %r' % pg.locator('.stgbar b').inner_text())
        # 「상단 바」 모드로 돌리면 지금 보는 곡이 바에 뜬다
        pg.evaluate("()=>{CONTI.STG.pref.form='bar';window.dispatchEvent(new Event('resize'))}"); pg.wait_for_timeout(700)
        bar = pg.locator('.stgbar b').inner_text()
        if '시간을 뚫고' not in bar: fail('상단 바 모드인데 곡명이 안 뜸: %r' % bar)
        pg.evaluate("()=>{CONTI.STG.pref.form='block';window.dispatchEvent(new Event('resize'))}"); pg.wait_for_timeout(500)
        print('곡 이동 ok:', bar)

        # ---- ⚙ 내 조판: 크기 키우면 화면이 나뉜다 · 그 곡에만 저장 ----
        open_pop(pg)
        z0 = pg.evaluate("CONTI.STG.pref.zoom")
        for _ in range(4):
            pg.click('[data-stg="z"][data-d="1"]'); pg.wait_for_timeout(350)
        z1 = pg.evaluate("CONTI.STG.pref.zoom")
        if not (z1 > z0): fail('크기 키우기가 안 먹음: %s → %s' % (z0, z1))
        print('크기 조절 ok: ×%.1f → ×%.1f, %d화면' % (z0, z1, screens()))

        # 인수 10: 이 조판은 그 예배·그 기기·그 사람에게만 (v2 — 한 화면에 여러 곡)
        keys = pg.evaluate("(()=>Object.keys(localStorage).filter(k=>k.indexOf('stage:')===0))()")
        if len(keys) != 1: fail('저장 키가 예배마다 따로가 아님: %s' % keys)
        if 'tab-l' not in keys[0]: fail('기기 구간이 키에 없음: %s' % keys[0])
        if sid not in keys[0]: fail('예배 id 가 키에 없음: %s' % keys[0])
        print('조판 저장 키 ok:', keys[0])

        # 나갔다 들어와도 내 조판이 남는다
        pg.keyboard.press('Escape'); pg.wait_for_timeout(600)
        pg.click('[data-act="play"][data-stage="1"]'); pg.wait_for_selector('#stageWrap .stgpage', timeout=15000); pg.wait_for_timeout(900)
        if pg.evaluate("CONTI.STG.pref.zoom") != z1: fail('다시 열었을 때 내 조판이 안 남음')
        print('내 조판 유지 ok')

        # 되돌리기
        open_pop(pg)
        pg.click('[data-stg="reset"]'); pg.wait_for_timeout(700)
        if pg.evaluate("CONTI.STG.pref.zoom") != 1: fail('자동으로 되돌리기가 안 먹음')
        print('되돌리기 ok')

        # ---- 인수 11: ⇪ 내보내기는 내 조판 값으로 시트를 채운다 ----
        open_pop(pg)
        pg.click('[data-stgt="memos"]'); pg.wait_for_timeout(500)     # 메모 띠 끔
        open_pop(pg)
        pg.click('[data-stg="export"]'); pg.wait_for_selector('#pvGo', timeout=8000)
        prt = pg.evaluate("(()=>{const P=CONTI.PRT;return {memos:P.memos,orient:P.orient,only:!!P.only,session:P.session}})()")
        if prt['memos'] is not False: fail('내 메모 토글이 인쇄 시트에 안 옮겨짐: %s' % prt)
        if prt['orient'] != 'landscape': fail('화면 방향이 안 옮겨짐: %s' % prt)
        print('⇪ 내보내기 시트 ok:', prt)
        want = pg.evaluate("CONTI.STG&&CONTI.STG.nscreens")
        pg.click('#pvGo'); pg.wait_for_selector('#printArea.pv .ppage', timeout=10000); pg.wait_for_timeout(700)
        if pg.locator('.ppage .pstrip').count(): fail('메모 띠를 껐는데 종이에 나옴')
        got = pg.locator('#printArea .ppage').count()
        if want and got != want: fail('화면 %s개인데 종이는 %d장 (화면 = 쪽)' % (want, got))
        print('종이 결과가 화면 설정과 같음 ok — %d장' % got)
        pg.click('[data-pv="close"]'); pg.wait_for_timeout(400)

        # ---- 세로(iPad 세로)에서도 한 화면 ----
        pg.set_viewport_size({'width':820,'height':1180})
        pg.goto(URL + '#/view/' + sid); pg.wait_for_selector('[data-act="play"][data-stage="1"]', timeout=10000); pg.wait_for_timeout(1000)
        pg.click('[data-act="play"][data-stage="1"]'); pg.wait_for_selector('#stageWrap .stgpage', timeout=15000); pg.wait_for_timeout(900)
        # v2 는 세로 1열이라 곡 수만큼 화면이 늘 수 있다. 곡 수를 넘지만 않으면 된다
        if not (1 <= screens() <= 2): fail('iPad 세로 화면 수가 이상함: %s화면' % screens())
        s2 = pg.evaluate("""(()=>{const w=document.querySelector('#stageWrap');
           return w.scrollHeight>w.clientHeight+1||w.scrollWidth>w.clientWidth+1})()""")
        if s2: fail('세로에서 스크롤이 생김')
        print('세로 %d화면 · 스크롤 없음 ok' % screens())
        pg.screenshot(path=os.path.join(ROOT,'tests','t_stage_port.png'))

        # Esc 로 나가기
        pg.keyboard.press('Escape'); pg.wait_for_timeout(600)
        if pg.locator('#stageWrap').count(): fail('Esc 로 안 닫힘')
        print('Esc 종료 ok')

        if errs: fail('JS 오류: %s' % errs[:3])
        print('errors:', errs)
        print('PASS test_stage')
        b.close()
run()
