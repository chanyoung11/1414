# 실사용 제보 9건 (2026-09-15 · 김대표·형님)
#  1 D-day 히어로가 엉뚱한 예배를 가리킴 (제목은 9/15, 날짜는 9/30)
#  2 예배를 다 지워도 히어로가 그대로 남음
#  3 지운 예배가 새로고침하면 되살아남 (자동 생성이 다시 만듦)
#  4 악보 한 장이 여러 곡으로 말없이 쪼개짐
#  5 마커·하이라이트·마스크·코드 겹쳐 놓기
#  6 편집 화면 악보 크기 조절
#  7 새로고침 아이콘
#  8 예배 목록 다중 선택
#  9 악보 사진 자르기
import os, sys, time
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = 'http://localhost:8766/'
H = {'x-conti': '1'}
SHEET = os.path.join(ROOT, 'docs', 'sample_sheet.jpg')
def fail(m): print('FAIL:', m); sys.exit(1)

def run():
    tag = str(int(time.time()))[-6:]
    with sync_playwright() as p:
        b = p.chromium.launch(); c = b.new_context(viewport={'width':1400,'height':950}); pg = c.new_page()
        errs=[]; pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('dialog', lambda d: d.accept())
        pg.goto(URL); pg.wait_for_selector('#lgUser')
        pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName')
        pg.check('#lgAgree')   # 약관·개인정보처리방침 동의 (필수)
        pg.fill('#lgName','하은'); pg.fill('#lgUser','lv'+tag); pg.fill('#lgPass','secret1'); pg.click('[data-act="lg-submit"]')
        pg.wait_for_selector('#gtTeam'); pg.fill('#gtTeam','제보팀'); pg.click('#gtSess .q:has-text("건반")')
        pg.click('[data-act="team-create"]'); pg.wait_for_selector('.shell[data-page]', timeout=10000)
        team = pg.evaluate('CONTI.S.team.id')

        # ---- 1) 히어로: 이름과 날짜가 같은 예배에서 와야 한다 ----
        # 가까운 사역 날짜(먼 것)와 더 이른 콘티를 만들어 어긋나는 상황을 만든다
        import datetime
        d1 = (datetime.date.today() + datetime.timedelta(days=3)).isoformat()
        d2 = (datetime.date.today() + datetime.timedelta(days=20)).isoformat()
        c.request.post(URL + 'api/teams/%s/dates' % team, headers=H, data={'date': d2, 'label':'먼 예배', 'time':'11:00'})
        pg.evaluate("""(([d1])=>{const s=CONTI.S.services;
          const n={id:'svc-early',name:'가까운 예배',date:d1,notice:'',message:'',messageRev:0,version:0,items:[],published:null};
          s.push(n);CONTI.save()})(%s)""" % repr([d1]).replace("'", '"'))
        pg.goto(URL + '#/home'); pg.wait_for_selector('.hero', timeout=8000); pg.wait_for_timeout(1200)
        hero = pg.locator('.hero').inner_text()
        md1 = '%d/%d' % (int(d1[5:7]), int(d1[8:10]))
        if '가까운 예배' not in hero: fail('히어로가 더 이른 예배를 안 보여줌: ' + hero.replace('\n',' '))
        if md1 not in hero: fail('히어로 이름과 날짜가 어긋남 (이름은 가까운 예배인데 날짜가 다름): ' + hero.replace('\n',' '))
        print('히어로 이름·날짜 일치 ok:', hero.replace('\n',' ')[:60])

        # ---- 8) 다중 선택으로 한꺼번에 삭제 ----
        pg.click('[data-act="pick-on"]'); pg.wait_for_selector('.svcrow.picking', timeout=5000)
        pg.click('[data-act="pick-all"]'); pg.wait_for_timeout(400)
        n_sel = pg.evaluate("CONTI.HOME.sel.length")
        if n_sel < 1: fail('전체 선택이 안 됨')
        pg.click('[data-act="pick-del"]'); pg.wait_for_timeout(2500)
        if pg.evaluate("CONTI.S.services.length") != 0: fail('다중 삭제가 안 됨')
        print('다중 선택 삭제 ok: %d개' % n_sel)

        # ---- 2) 다 지웠는데 히어로가 예전 예배를 계속 보여주면 안 된다 ----
        pg.wait_for_timeout(600)
        hero2 = pg.locator('.hero').inner_text() if pg.locator('.hero').count() else ''
        if '가까운 예배' in hero2: fail('지운 예배가 히어로에 남음: ' + hero2.replace('\n',' '))
        if hero2 and '콘티 만들기' not in hero2: fail('콘티 없는 날짜인데 만들기 버튼이 없음: ' + hero2.replace('\n',' '))
        print('지운 뒤 히어로 ok:', (hero2.replace('\n',' ')[:60] or '(히어로 없음)'))

        # ---- 3) 지운 예배가 새로고침해도 되살아나지 않는다 ----
        # 자동 생성이 도는 날짜를 만들고, 거기서 생긴 콘티를 지운 뒤 다시 받아 본다
        d3 = (datetime.date.today() + datetime.timedelta(days=5)).isoformat()
        c.request.post(URL + 'api/teams/%s/dates' % team, headers=H, data={'date': d3, 'label':'자동 예배', 'time':'11:00'})
        pg.goto(URL + '#/home'); pg.wait_for_timeout(500)
        pg.evaluate("CONTI.SYNC.pullServices()"); pg.wait_for_timeout(2500)
        auto = pg.evaluate("""(()=>{const s=CONTI.S.services.find(x=>x.date==='%s');return s?s.id:null})()""" % d3)
        if not auto: fail('자동 생성된 콘티가 안 내려옴')
        print('자동 생성 ok:', auto)
        pg.evaluate("""(async(id)=>{CONTI.S.services=CONTI.S.services.filter(s=>s.id!==id);
          CONTI.S.dropped=(CONTI.S.dropped||[]).concat(id);CONTI.save();
          await CONTI.SYNC.deleteService(id)})('%s')""" % auto)
        pg.wait_for_timeout(1500)
        # 서버에서 자동 생성을 한 번 더 돌린다 (스케줄 조회가 그 계기다)
        c.request.get(URL + 'api/teams/%s/schedule' % team, headers=H)
        pg.evaluate("CONTI.SYNC.pullServices()"); pg.wait_for_timeout(2500)
        back = pg.evaluate("""(()=>CONTI.S.services.filter(x=>x.date==='%s').length)()""" % d3)
        if back: fail('지운 예배가 새로고침 뒤 되살아남 (%d개)' % back)
        print('삭제 후 되살아나지 않음 ok')

        # ---- 4·5·6·7·9) 편집 화면 ----
        pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]', timeout=8000)
        pg.fill('[data-f="svc.name"]','편집 시험')
        pg.click('[data-act="add-item"]'); pg.wait_for_timeout(400)
        pg.fill('[data-f="item.title"]','시험곡'); pg.fill('[data-f="item.key"]','G')
        n_before = pg.evaluate("CONTI.S.services[0].items.length")
        pg.set_input_files('#pieceFile', [SHEET])
        pg.wait_for_function("(()=>{const p=(CONTI.S.services[0].items[0].pieces||[])[0];return p&&p.w>0})()", timeout=90000)
        pg.wait_for_timeout(1500)
        # 4) 말없이 곡이 늘어나면 안 된다
        n_after = pg.evaluate("CONTI.S.services[0].items.length")
        if n_after != n_before: fail('악보를 넣었더니 곡이 %d → %d 로 늘어남' % (n_before, n_after))
        if pg.evaluate("CONTI.S.services[0].items[0].pieces.length") != 1: fail('조각이 하나가 아님')
        print('악보 한 장 = 한 곡 ok')

        # 6) 편집 화면 악보 크기 조절
        w0 = pg.evaluate("document.querySelector('#sheet .slice').getBoundingClientRect().width")
        pg.click('[data-act="edzoom"][data-d="1"]'); pg.wait_for_timeout(700)
        pg.click('[data-act="edzoom"][data-d="1"]'); pg.wait_for_timeout(900)
        w1 = pg.evaluate("document.querySelector('#sheet .slice').getBoundingClientRect().width")
        if not (w1 > w0 + 5): fail('편집 화면에서 악보가 커지지 않음: %s → %s' % (w0, w1))
        lbl = pg.locator('.edzoomlbl').first.inner_text()
        print('편집 악보 크기 조절 ok: %d → %d (%s)' % (w0, w1, lbl))
        pg.click('[data-act="edzoom"][data-d="-1"]'); pg.click('[data-act="edzoom"][data-d="-1"]'); pg.wait_for_timeout(700)

        # 5) 겹쳐 놓기: 하이라이트 위에 마커
        pg.click('[data-act="tool"][data-t="hl"]'); pg.wait_for_timeout(400)
        box = pg.evaluate("(()=>{const s=document.querySelector('#sheet .slice');const r=s.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height}})()")
        pg.mouse.move(box['x']+60, box['y']+60); pg.mouse.down()
        pg.mouse.move(box['x']+220, box['y']+110, steps=8); pg.mouse.up(); pg.wait_for_timeout(700)
        if pg.evaluate("CONTI.S.services[0].items[0].pieces[0].hls.length") != 1: fail('하이라이트가 안 그려짐')
        # 그 위에 또 하나 (겹쳐 긋기)
        pg.mouse.move(box['x']+100, box['y']+70); pg.mouse.down()
        pg.mouse.move(box['x']+260, box['y']+130, steps=8); pg.mouse.up(); pg.wait_for_timeout(700)
        if pg.evaluate("CONTI.S.services[0].items[0].pieces[0].hls.length") != 2: fail('하이라이트 위에 하이라이트를 못 그림')
        print('하이라이트 겹쳐 긋기 ok')
        # 하이라이트 위에 마커
        pg.click('[data-act="tool"][data-t="marker"]'); pg.wait_for_timeout(400)
        pg.mouse.click(box['x']+150, box['y']+90); pg.wait_for_timeout(700)
        if pg.locator('#modal').inner_text().strip() == '': fail('하이라이트 위에서 마커 라벨 고르기가 안 뜸')
        pg.click('#modal .q'); pg.wait_for_timeout(900)
        if pg.evaluate("CONTI.S.services[0].items[0].pieces[0].markers.length") != 1: fail('하이라이트 위에 마커를 못 놓음')
        print('하이라이트 위에 마커 ok')
        # 마커 위에 하이라이트
        pg.click('[data-act="tool"][data-t="hl"]'); pg.wait_for_timeout(400)
        mk = pg.evaluate("(()=>{const m=document.querySelector('#sheet [data-marker]');if(!m)return null;const r=m.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()")
        if mk:
            pg.mouse.move(mk['x']-10, mk['y']-10); pg.mouse.down()
            pg.mouse.move(mk['x']+120, mk['y']+40, steps=8); pg.mouse.up(); pg.wait_for_timeout(700)
            n3 = pg.evaluate("CONTI.S.services[0].items[0].pieces[0].hls.length")
            if n3 != 3:
                info = pg.evaluate("""(()=>{const s=document.querySelector('#sheet .slice');
                  const el=document.elementFromPoint(%d,%d);
                  return {tag:el&&el.className, inSlice:!!(el&&el.closest('.slice')), tool:CONTI.S&&1}})()""" % (int(mk['x']-10), int(mk['y']-10)))
                fail('마커 위에서 하이라이트를 못 그림 (hls=%s, 시작점=%s)' % (n3, info))
            print('마커 위에 하이라이트 ok')

        # 9) 자르기 버튼이 있고 모달이 뜬다
        pg.click('[data-act="crop-piece"]'); pg.wait_for_selector('#cropBox', timeout=8000); pg.wait_for_timeout(600)
        h0 = pg.evaluate("CONTI.S.services[0].items[0].pieces[0].h")
        cw = pg.evaluate("(()=>{const r=document.querySelector('#cropImg').getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height}})()")
        pg.mouse.move(cw['x']+cw['w']*0.1, cw['y']+cw['h']*0.1); pg.mouse.down()
        pg.mouse.move(cw['x']+cw['w']*0.9, cw['y']+cw['h']*0.5, steps=10); pg.mouse.up(); pg.wait_for_timeout(400)
        pg.click('#cpOk'); pg.wait_for_timeout(4000)
        h1 = pg.evaluate("CONTI.S.services[0].items[0].pieces[0].h")
        if not (h1 < h0 * 0.8): fail('자르기가 반영되지 않음: 높이 %s → %s' % (h0, h1))
        print('악보 자르기 ok: 높이 %d → %d' % (h0, h1))

        # 7) 새로고침 아이콘이 가져오기와 달라야 한다
        pg.goto(URL + '#/home'); pg.wait_for_selector('[data-act="sync"]', timeout=8000)
        same = pg.evaluate("""(()=>{const a=document.querySelector('[data-act="sync"] svg');
          const b=document.querySelector('[data-act="import"] svg');
          return !!(a&&b&&a.innerHTML===b.innerHTML)})()""")
        if same: fail('새로고침과 가져오기 아이콘이 같음')
        print('새로고침 아이콘 ok')

        if errs: fail('JS 오류: %s' % errs[:3])
        print('errors:', errs)
        print('PASS test_live1')
        b.close()
run()
