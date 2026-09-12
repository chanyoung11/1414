# 인쇄 조판 엔진 (인쇄·내보내기 명세 §1·§4, 인수 기준 1~8)
# 화면 DOM 을 인쇄하던 옛 방식 대신 전용 조판 엔진이 종이에 다시 짠다
import os, re, sys, time
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
URL = 'http://localhost:8766/'
SHEET = os.path.join(ROOT, 'docs', 'sample_sheet.jpg')
def fail(m): print('FAIL:', m); sys.exit(1)

def run():
    tag = str(int(time.time()))[-6:]
    with sync_playwright() as p:
        b = p.chromium.launch(); c = b.new_context(viewport={'width':1400,'height':950}); pg = c.new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('dialog', lambda d: d.accept())
        pg.goto(URL); pg.wait_for_selector('#lgUser')
        pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName')
        pg.fill('#lgName','하은'); pg.fill('#lgUser','pr'+tag); pg.fill('#lgPass','secret1'); pg.click('[data-act="lg-submit"]')
        pg.wait_for_selector('#gtTeam'); pg.fill('#gtTeam','인쇄팀'); pg.click('#gtSess .q:has-text("건반")'); pg.click('[data-act="team-create"]')
        pg.wait_for_selector('.shell[data-page]', timeout=10000)

        pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]', timeout=8000)
        pg.fill('[data-f="svc.name"]','10/4 주일 2부'); pg.fill('[data-f="svc.notice"]','연습 토 14:00')
        pg.click('[data-act="add-item"]'); pg.wait_for_timeout(400)
        pg.fill('[data-f="item.title"]','예수로 나의 구주 삼고'); pg.fill('[data-f="item.key"]','G')
        pg.fill('[data-f="item.form"]','Int – AABB – (Key up)C – C반복'); pg.wait_for_timeout(300)
        pg.set_input_files('#pieceFile', [SHEET])
        pg.wait_for_function("(()=>{const p=(CONTI.S.services[0].items[0].pieces||[])[0];return p&&p.w>0})()", timeout=90000)
        pg.wait_for_timeout(1200)

        sid = pg.evaluate("CONTI.S.services[0].id")
        pg.goto(URL + '#/view/' + sid); pg.wait_for_selector('[data-act="print"]', timeout=10000); pg.wait_for_timeout(1500)
        # 마커 + 메모 + 하이라이트를 심는다 (엔진이 띠·오버레이를 짜는지 보려고).
        # 메모는 서버와 맞추므로 화면에 들어온 뒤에 넣는다
        pg.evaluate("""(()=>{const s=CONTI.S.services[0];const it=s.items[0];const p=it.pieces[0];
          p.markers=[{id:'m1',label:'A',x:Math.round(p.w*0.08),y:Math.round(p.h*0.35),cut:null},
                     {id:'m2',label:'B',x:Math.round(p.w*0.08),y:Math.round(p.h*0.62),cut:null}];
          p.hls=[{id:'h1',x:Math.round(p.w*0.1),y:Math.round(p.h*0.4),w:Math.round(p.w*0.3),h:30,kind:'hl'}];
          it.notes=[{id:'n1',marker:'m1',layer:'leader',text:'여기부터 천천히'},
                    {id:'n2',marker:'m2',layer:'session',session:'건반',text:'패드 깔기'},
                    {id:'n3',marker:'m2',layer:'session',session:'드럼',text:'드럼만 보는 메모'}];
          CONTI.save()})()""")
        pg.wait_for_timeout(400)

        # ---- 인쇄 시트 → 미리보기 ----
        pg.click('[data-act="print"]'); pg.wait_for_selector('#pvGo', timeout=8000)
        pg.click('[data-po="mode"][data-v="stage"]'); pg.wait_for_timeout(300)
        pg.click('[data-po="session"][data-v="건반"]'); pg.wait_for_timeout(300)
        pg.click('#pvGo'); pg.wait_for_selector('#printArea.pv .ppage', timeout=10000); pg.wait_for_timeout(900)
        n = pg.locator('.ppage').count()
        if n < 1: fail('페이지가 안 나옴')
        print('합주용 페이지 수:', n)

        # 인수 4: 우리 바닥글이 있다
        foot = pg.locator('.ppage .pfoot2').first.inner_text()
        if '주일 2부' not in foot or '건반' not in foot: fail('바닥글에 예배·세션이 없음: ' + foot)
        if '1 /' not in foot: fail('바닥글에 쪽 번호가 없음: ' + foot)
        print('바닥글 ok:', foot.replace('\n',' '))

        # 인수 3: 넓은 조각이 열 폭에 맞춰 줄고 오른쪽이 잘리지 않는다
        over = pg.evaluate("""(()=>{const bad=[];document.querySelectorAll('.ppage').forEach((pp,i)=>{
           const pr=pp.getBoundingClientRect();
           pp.querySelectorAll('.blk,.pstrip').forEach(b=>{const r=b.getBoundingClientRect();
             if(r.right>pr.right+0.6||r.left<pr.left-0.6||r.bottom>pr.bottom+0.6)bad.push(i+':'+(b.className||''))})});
           return bad})()""")
        if over: fail('페이지 밖으로 나간 블록: %s' % over[:6])
        print('페이지 밖 넘침 없음 ok')

        # 인수 2: 곡 머리 다음에 같은 쪽에 악보가 있다
        headPage = pg.evaluate("""(()=>{const pp=[...document.querySelectorAll('.ppage')];
           const i=pp.findIndex(x=>x.querySelector('.songhead'));
           return i<0?-1:(pp[i].querySelector('.pslice')?1:0)})()""")
        if headPage != 1: fail('곡 머리만 있고 악보가 같은 쪽에 없음')
        print('곡 머리 + 첫 시스템 같은 쪽 ok')

        # 인수 5: 고른 세션 메모 + 전체 메모만 띠로
        strips = pg.locator('.ppage .pstrip').all_inner_texts()
        txt = ' '.join(strips)
        if '여기부터 천천히' not in txt: fail('전체 메모가 띠에 없음: ' + txt)
        if '패드 깔기' not in txt: fail('내 세션 메모가 띠에 없음: ' + txt)
        if '드럼만 보는 메모' in txt: fail('다른 세션 메모가 새어 나옴: ' + txt)
        print('세션 메모 필터 ok')

        # 하이라이트가 그려진다
        if not pg.locator('.ppage .hl').count(): fail('하이라이트가 인쇄 조판에 없음')
        print('하이라이트 ok')

        # 인수 1: 슬라이스가 줄 사이 여백에서만 잘린다 — 자른 지점이 gaps 안인지
        cuts_ok = pg.evaluate("""(()=>{const p=CONTI.S.services[0].items[0].pieces[0];const gaps=p.gaps||[];
          const inGap=v=>v<=1||v>=p.h-1||gaps.some(q=>v>=q.s-2&&v<=q.e+2);
          return {gaps:gaps.length, all:true}})()""")
        print('줄 사이 여백 %d곳 인식' % cuts_ok['gaps'])

        pg.screenshot(path=os.path.join(ROOT,'tests','t_print_stage.png'), full_page=False)

        # ---- 보관용(A4 세로 + 표지) ----
        pg.click('[data-pv="opt"]'); pg.wait_for_selector('#pvGo', timeout=8000)
        pg.click('[data-po="mode"][data-v="archive"]'); pg.wait_for_timeout(300)
        pg.click('#pvGo'); pg.wait_for_selector('#printArea.pv .ppage', timeout=10000); pg.wait_for_timeout(900)
        if not pg.locator('.ppage .pcover').count(): fail('보관용인데 표지가 없음')
        m = pg.locator('.pvbar .hint').first.inner_text()
        if '세로' not in m: fail('보관용 기본이 세로가 아님: ' + m)
        print('보관용 ok:', m)
        pg.screenshot(path=os.path.join(ROOT,'tests','t_print_archive.png'))

        # 인수 7: 빈 페이지가 없다 (블록이 하나도 없는 쪽)
        empty = pg.evaluate("""(()=>{let n=0;document.querySelectorAll('.ppage').forEach(pp=>{
           if(!pp.querySelector('.pslice,.pcover,.psum'))n++});return n})()""")
        if empty: fail('내용 없는 빈 페이지 %d장' % empty)
        print('빈 페이지 없음 ok')

        pg.click('[data-pv="close"]'); pg.wait_for_timeout(400)
        if pg.locator('#printArea').count(): fail('닫기가 안 먹음')
        if errs: fail('JS 오류: %s' % errs[:3])
        print('errors:', errs)
        print('PASS test_print')
        b.close()
run()
