# 무대 조판 블록화 (기획 §3 편집 · §6 저장) — 인수 기준 3, 6
# 블록을 끌어 옮기면 그 자리가 남고, 새로고침해도 같은 자리에 있다.
import os, sys, time
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
SHEET = os.path.join(ROOT, 'docs', 'sample_sheet.jpg')
def fail(m): print('FAIL:', m); sys.exit(1)

def open_stage(pg, sid):
    pg.goto(URL + '#/view/' + sid)
    pg.wait_for_selector('[data-act="play"][data-stage="1"]', timeout=10000); pg.wait_for_timeout(900)
    pg.click('[data-act="play"][data-stage="1"]')
    pg.wait_for_selector('#stageWrap .stgpage', timeout=15000); pg.wait_for_timeout(700)

def run():
    tag = str(int(time.time()))[-6:]
    with sync_playwright() as p:
        b = p.chromium.launch()
        c = b.new_context(viewport={'width':1180,'height':820})   # iPad 가로
        pg = c.new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(repr(e)[:300])); pg.on('dialog', lambda d: d.accept())
        pg.goto(URL); pg.wait_for_selector('#lgUser')
        pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName')
        pg.check('#lgAgree')
        pg.fill('#lgName','하은'); pg.fill('#lgUser','sl'+tag); pg.fill('#lgPass','secret1'); pg.click('[data-act="lg-submit"]')
        pg.wait_for_selector('#gtTeam'); pg.fill('#gtTeam','조판팀'); pg.click('#gtSess .q:has-text("건반")'); pg.click('[data-act="team-create"]')
        pg.wait_for_selector('.shell[data-page]', timeout=10000)

        pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]', timeout=8000)
        pg.fill('[data-f="svc.name"]','10/11 주일 2부')
        for title, key in [('예수로 나의 구주 삼고','G'), ('주 사랑합니다','D')]:
            pg.click('[data-act="add-item"]'); pg.wait_for_timeout(400)
            pg.fill('[data-f="item.title"]', title); pg.fill('[data-f="item.key"]', key)
            pg.fill('[data-f="item.form"]','Int – AABB')
            pg.set_input_files('#pieceFile', [SHEET])
            pg.wait_for_function("(()=>{const its=CONTI.S.services[0].items;const it=its[its.length-1];const p=(it.pieces||[])[0];return p&&p.w>0})()", timeout=90000)
            pg.wait_for_timeout(700)
        pg.click('[data-act="publish"]'); pg.wait_for_selector('#pubOnly', timeout=8000)
        pg.click('#pubOnly'); pg.wait_for_timeout(3500)
        sid = pg.evaluate("CONTI.S.services[0].id")

        open_stage(pg, sid)

        # ---- 편집 들어가기 ----
        if not pg.locator('[data-stg="edit"]').count(): fail('✎ 버튼이 없음')
        pg.click('[data-stg="edit"]'); pg.wait_for_timeout(400)
        if not pg.locator('.stgpage.edit').count(): fail('편집 모드로 안 들어감')
        n = pg.locator('.sblk').count()
        if n < 2: fail('편집 블록이 %d개뿐' % n)
        print('편집 모드 · 블록 %d개 ok' % n)

        # ---- 블록 하나를 끌어 옮긴다 ----
        target = pg.locator('.sblk').nth(1)
        bid = target.get_attribute('data-sid')
        before = target.bounding_box()
        pg.mouse.move(before['x']+40, before['y']+12)
        pg.mouse.down()
        pg.mouse.move(before['x']+40+170, before['y']+12+90, steps=12)
        pg.mouse.up()
        pg.wait_for_timeout(500)
        moved = pg.locator('.sblk[data-sid="%s"]' % bid)
        if not moved.count(): fail('끌고 나서 블록이 사라짐')
        after = moved.bounding_box()
        dx, dy = after['x']-before['x'], after['y']-before['y']
        if abs(dx) < 60 or abs(dy) < 40: fail('블록이 안 움직임: dx=%.0f dy=%.0f' % (dx, dy))
        print('블록 끌어 옮기기 ok (dx=%.0f dy=%.0f)' % (dx, dy))

        saved = pg.evaluate("""(sid)=>{const s=CONTI.prefs&&CONTI.prefs();return null}""", sid) if False else None
        # 저장됐나 (localStorage)
        keys = pg.evaluate("Object.keys(localStorage).filter(k=>k.indexOf('conti-lay:')===0)")
        if not keys: fail('조판이 저장되지 않음 (localStorage 비어 있음)')
        pos = pg.evaluate("""(k)=>{const v=JSON.parse(localStorage.getItem(k));
            for(const sc of v.screens)for(const b of sc.blocks)if(b.id==='%s')return {x:b.x,y:b.y};
            return null}""".replace('%s', bid), keys[0])
        if not pos: fail('저장본에 그 블록이 없음')
        print('저장 ok', keys[0], pos)

        # ---- 편집 끝내고 새로고침 → 같은 자리 ----
        pg.click('[data-stg="edit"]'); pg.wait_for_timeout(300)
        if pg.locator('.stgpage.edit').count(): fail('편집이 안 꺼짐')
        pg.goto(URL); pg.wait_for_selector('.shell[data-page]', timeout=15000); pg.wait_for_timeout(1500)
        open_stage(pg, sid)
        pg.click('[data-stg="edit"]'); pg.wait_for_timeout(500)
        again = pg.locator('.sblk[data-sid="%s"]' % bid)
        if not again.count(): fail('새로고침 뒤 그 블록이 없음')
        a2 = again.bounding_box()
        if abs(a2['x']-after['x']) > 6 or abs(a2['y']-after['y']) > 6:
            fail('새로고침 뒤 자리가 달라짐: %s → %s' % (after, a2))
        print('새로고침 뒤에도 같은 자리 ok')

        # ---- 화면 띠: 화면 추가 · 순서 · 빈 화면 지우기 (§3) ----
        n0 = pg.evaluate("CONTI.STG.nscreens")
        pg.click('[data-sc="add"]'); pg.wait_for_timeout(350)
        if pg.evaluate("CONTI.STG.nscreens") != n0+1: fail('화면 추가가 안 됨')
        pg.click('[data-sc="del"]'); pg.wait_for_timeout(350)
        if pg.evaluate("CONTI.STG.nscreens") != n0: fail('빈 화면 지우기가 안 됨')
        print('화면 띠 추가·삭제 ok')

        # ---- 텍스트 블록 (§3) ----
        pg.evaluate("window.prompt=()=>'여기서 기도'")
        pg.click('[data-sc="text"]'); pg.wait_for_timeout(450)
        if not pg.locator('.sblk .ptext').count(): fail('텍스트 블록이 안 생김')
        print('텍스트 블록 ok')

        # ---- 송폼 모드 넷 (§4) ----
        modes = []
        for _ in range(4):
            modes.append(pg.evaluate("CONTI.STG.pref.form"))
            pg.click('[data-sc="form"]'); pg.wait_for_timeout(400)
        if sorted(modes) != sorted(['auto','bar','block','hide']): fail('송폼 모드 순환이 이상함: %s' % modes)
        print('송폼 모드 4가지 ok', modes)

        # ---- 자르기 (§3) ----
        pg.wait_for_timeout(300)
        sid_cut = pg.evaluate("(()=>{const S=CONTI.STG;const L=S.layout.screens[S.screen];"
                              "const b=L.blocks.find(x=>x.type==='slice');return b?b.id:null})()")
        if sid_cut:
            n1 = pg.evaluate("CONTI.STG.layout.screens[CONTI.STG.screen].blocks.length")
            pg.click('.sblk[data-sid="%s"]' % sid_cut); pg.wait_for_timeout(400)
            if pg.locator('[data-sm="cut"]').count():
                pg.click('[data-sm="cut"]'); pg.wait_for_timeout(600)
                n2 = pg.evaluate("CONTI.STG.layout.screens[CONTI.STG.screen].blocks.length")
                if n2 != n1+1:
                    info = pg.evaluate("(()=>{const S=CONTI.STG;const L=S.layout.screens[S.screen];"
                                       "const b=L.blocks.find(x=>x.type==='slice');"
                                       "return b?{u:(b.pc.units||[]).map(u=>[u.a,u.b,!!u.strip]),r:b.ranges}:null})()")
                    fail('자르기로 블록이 안 늘어남: %d -> %d · %s' % (n1, n2, info))
                print('여백에서 자르기 ok')

                # 나뉜 두 블록을 겹쳐 놓으면 도로 하나 (§3 붙이기)
                two = pg.evaluate("(()=>{const S=CONTI.STG;const L=S.layout.screens[S.screen];"
                                  "return L.blocks.filter(b=>String(b.id).indexOf('#')>0).map(b=>b.id)})()")
                if len(two) == 2:
                    a_box = pg.locator('.sblk[data-sid="%s"]' % two[0]).bounding_box()
                    b_box = pg.locator('.sblk[data-sid="%s"]' % two[1]).bounding_box()
                    pg.mouse.move(b_box['x']+30, b_box['y']+10)
                    pg.mouse.down()
                    pg.mouse.move(a_box['x']+30, a_box['y']+14, steps=14)
                    pg.mouse.up(); pg.wait_for_timeout(600)
                    n3 = pg.evaluate("CONTI.STG.layout.screens[CONTI.STG.screen].blocks.length")
                    if n3 != n1: fail('겹쳐 놓았는데 안 합쳐짐: %d (기대 %d)' % (n3, n1))
                    print('겹쳐서 붙이기 ok')
                else:
                    fail('자른 블록이 2개가 아님: %s' % two)
            else:
                fail('악보 블록인데 ✂ 가 없음')

        # ---- 인도자 추천 조판 (§6) ----
        if not pg.locator('[data-sc="rec"]').count(): fail('인도자인데 추천 버튼이 없음')
        pg.click('[data-sc="rec"]'); pg.wait_for_timeout(2000)
        rec = pg.evaluate("(()=>{const d=CONTI.S.services[0].published;"
                          "return d&&d.stageLayouts?Object.keys(d.stageLayouts):null})()")
        if not rec or 'tab-l' not in rec: fail('추천 조판이 발행본에 안 실림: %s' % rec)
        srv = pg.evaluate("(async()=>{const r=await fetch('/api/services/'+ID+'?team='+CONTI.S.team.id,{credentials:'include'});const j=await r.json();return j.doc&&j.doc.stageLayouts?Object.keys(j.doc.stageLayouts):null})()".replace('ID', repr(sid)))
        if not srv or 'tab-l' not in srv: fail('서버 발행본에 추천 조판이 없음: %s' % srv)
        print('인도자 추천 조판 ok', srv)

        # ---- 자동으로 되돌리기 ----
        pg.click('[data-stg="auto"]'); pg.wait_for_timeout(600)
        keys2 = pg.evaluate("Object.keys(localStorage).filter(k=>k.indexOf('conti-lay:')===0).map(k=>localStorage.getItem(k))")
        # 조판은 남지 않는다. 바로 위에서 추천 조판을 올렸으니 '자동으로 보기' 표시({auto})가 남는다 — 비우면 다음에 열 때 추천으로 돌아갔다
        if keys2 and keys2[0] not in ('null', None) and ('screens' in keys2[0] or '"auto"' not in keys2[0]): fail('자동으로 되돌렸는데 저장본이 남음: %s' % keys2[0][:80])
        print('자동으로 되돌리기 ok')

        # ---- 인쇄: 화면 = 쪽 (§6) ----
        pg.click('[data-stg="edit"]'); pg.wait_for_timeout(300)
        want = pg.evaluate("CONTI.STG.nscreens")
        pg.click('[data-stg="export"]'); pg.wait_for_selector('#pvGo', timeout=8000)
        pg.click('#pvGo'); pg.wait_for_selector('#printArea.pv .ppage', timeout=15000); pg.wait_for_timeout(600)
        got = pg.locator('#printArea .ppage').count()
        if got != want: fail('화면 %d개인데 종이는 %d장' % (want, got))
        if not pg.locator('#printArea .ppage.pstage').count(): fail('무대 조판 그대로가 아님')
        over = pg.evaluate("""(()=>{const p=document.querySelector('#printArea .ppage');const r=p.getBoundingClientRect();const bad=[];
           p.querySelectorAll('.blk,.pstrip').forEach(b=>{const q=b.getBoundingClientRect();
             if(q.right>r.right+1||q.bottom>r.bottom+1)bad.push(b.className)});return bad})()""")
        if over: fail('종이 밖으로 나간 블록: %s' % over[:4])
        print('인쇄 화면=쪽 ok (%d장)' % got)
        pg.click('#printArea [data-pv="close"]'); pg.wait_for_timeout(300)

        if errs: fail('콘솔 오류: %s' % errs[:3])
        b.close()
    print('OK — 무대 조판 블록 편집 · 저장 · 복원')

run()
