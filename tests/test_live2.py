# 실사용 제보 2차 (2026-09-16 · 김대표)
#  1 악보 축소 한계 (무대 60% / 편집 50%) 를 푼다
#  2 조각을 가로로 나란히 놓고, 끌어서 순서를 바꾼다
#  3 편집 화면에서 말씀 입력란을 빼고 '인도자의 글' 하나로 모은다
import os, sys, time
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
        pg.check('#lgAgree')
        pg.fill('#lgName','하은'); pg.fill('#lgUser','l2'+tag); pg.fill('#lgPass','secret1'); pg.click('[data-act="lg-submit"]')
        pg.wait_for_selector('#gtTeam'); pg.fill('#gtTeam','제보2팀'); pg.click('#gtSess .q:has-text("건반")')
        pg.click('[data-act="team-create"]'); pg.wait_for_selector('.shell[data-page]', timeout=10000)

        pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]', timeout=8000)
        pg.fill('[data-f="svc.name"]','제보2')
        pg.click('[data-act="add-item"]'); pg.wait_for_timeout(400)
        pg.fill('[data-f="item.title"]','시험곡'); pg.fill('[data-f="item.key"]','G')
        pg.set_input_files('#pieceFile', [SHEET, SHEET])
        pg.wait_for_function("(()=>{const ps=(CONTI.S.services[0].items[0].pieces||[]);return ps.length===2&&ps.every(p=>p.w>0)})()", timeout=120000)
        pg.wait_for_timeout(1500)

        # ---- 3) 편집 화면에 말씀 입력란이 없고, 인도자의 글이 있다 ----
        if pg.locator('[data-w="passage"]').count(): fail('편집 화면에 말씀 입력란이 남아 있음')
        if not pg.locator('[data-f="svc.message"]').count(): fail('인도자의 글이 없음')
        if not pg.locator('[data-act="word-link"]').count(): fail('목사님께 링크 보내기가 사라짐')
        print('편집 말씀란 정리 ok (인도자의 글 + 링크 보내기만)')

        # ---- 1) 축소 한계 ----
        def w(): return pg.evaluate("document.querySelector('#sheet .slice').getBoundingClientRect().width")
        w0 = w()
        for _ in range(12): pg.click('[data-act="edzoom"][data-d="-1"]')
        pg.wait_for_timeout(900)
        z = pg.evaluate("+localStorage.getItem('conti-edzoom')")
        if z > 0.55: fail('편집에서 더 못 줄임: %s' % z)
        if w() >= w0: fail('줄였는데 폭이 안 줄어듦')
        print('편집 축소 ok: ×%.2f' % z)
        for _ in range(30): pg.click('[data-act="edzoom"][data-d="1"]')
        pg.wait_for_timeout(900)
        z2 = pg.evaluate("+localStorage.getItem('conti-edzoom')")
        if z2 < 2: fail('편집에서 더 못 키움: %s' % z2)
        print('편집 확대 ok: ×%.2f' % z2)
        for _ in range(40): pg.click('[data-act="edzoom"][data-d="-1"]')
        pg.wait_for_timeout(600)

        # ---- 2) 조각을 가로로 ----
        pg.wait_for_timeout(600)
        tops = pg.evaluate("[...document.querySelectorAll('#sheet .piece')].map(e=>Math.round(e.getBoundingClientRect().top))")
        if len(tops) != 2: fail('조각이 2개가 아님: %s' % tops)
        if tops[0] == tops[1]: fail('처음부터 나란히 놓여 있음 (세로가 기본이어야 함)')
        pg.click('[data-act="span-piece"]'); pg.wait_for_timeout(700)
        pg.click('[data-act="span-piece"] >> nth=1'); pg.wait_for_timeout(900)
        spans = pg.evaluate("CONTI.S.services[0].items[0].pieces.map(p=>p.span||1)")
        if spans != [2,2]: fail('½ 로 안 바뀜: %s' % spans)
        tops2 = pg.evaluate("[...document.querySelectorAll('#sheet .piece')].map(e=>Math.round(e.getBoundingClientRect().top))")
        if tops2[0] != tops2[1]: fail('½ 인데 나란히 안 놓임: %s' % tops2)
        lefts = pg.evaluate("[...document.querySelectorAll('#sheet .piece')].map(e=>Math.round(e.getBoundingClientRect().left))")
        if not (lefts[1] > lefts[0]): fail('두 번째 조각이 오른쪽에 없음: %s' % lefts)
        print('가로 배치 ok: top=%s left=%s' % (tops2, lefts))
        pg.screenshot(path=os.path.join(ROOT,'tests','t_live2_side.png'))

        # 악보가 실제로 좁아졌는지 (반쪽이면 폭도 반)
        sw = pg.evaluate("[...document.querySelectorAll('#sheet .piece')].map(e=>Math.round(e.getBoundingClientRect().width))")
        if sw[0] > 700: fail('½ 인데 폭이 안 줄어듦: %s' % sw)
        print('반쪽 폭 ok:', sw)

        # ---- 2b) 끌어서 순서 바꾸기 ----
        ids0 = pg.evaluate("CONTI.S.services[0].items[0].pieces.map(p=>p.id)")
        h = pg.evaluate("(()=>{const e=document.querySelector('#sheet [data-pdrag]');const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()")
        t = pg.evaluate("(()=>{const e=[...document.querySelectorAll('#sheet .piece')][1];const r=e.getBoundingClientRect();return {x:r.x+r.width*0.8,y:r.y+40}})()")
        pg.mouse.move(h['x'], h['y']); pg.mouse.down()
        pg.mouse.move(t['x'], t['y'], steps=12); pg.wait_for_timeout(200); pg.mouse.up(); pg.wait_for_timeout(900)
        ids1 = pg.evaluate("CONTI.S.services[0].items[0].pieces.map(p=>p.id)")
        if ids1 == ids0: fail('끌어도 순서가 안 바뀜: %s' % ids1)
        if sorted(ids1) != sorted(ids0): fail('조각이 사라지거나 늘어남: %s → %s' % (ids0, ids1))
        print('드래그 순서 바꾸기 ok: %s → %s' % (ids0, ids1))

        # ⅓ 까지 돌고 전체로 돌아온다
        pg.click('[data-act="span-piece"]'); pg.wait_for_timeout(600)
        if pg.evaluate("CONTI.S.services[0].items[0].pieces[0].span") != 3: fail('⅓ 로 안 감')
        pg.click('[data-act="span-piece"]'); pg.wait_for_timeout(600)
        if pg.evaluate("CONTI.S.services[0].items[0].pieces[0].span"): fail('전체로 안 돌아옴')
        print('전체 → ½ → ⅓ → 전체 ok')

        if errs: fail('JS 오류: %s' % errs[:3])
        print('errors:', errs)
        print('PASS test_live2')
        b.close()
run()
