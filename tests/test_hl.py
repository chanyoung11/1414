# 하이라이트·마스크: 판 폭이 바뀐 뒤에도 찍은 자리에 그려지고, 탭하면 지워진다
import os, sys, time
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHEET = os.path.join(ROOT, 'docs', 'sample_sheet.jpg')
tag = str(int(time.time()))[-6:]
def fail(m): print('FAIL:', m); sys.exit(1)

def run():
  with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    c = b.new_context(viewport={'width': 1400, 'height': 950}); pg = c.new_page()
    pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('dialog', lambda d: d.accept())
    pg.goto(URL); pg.wait_for_selector('#lgUser', timeout=8000)
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName')
    pg.fill('#lgName', '하은'); pg.fill('#lgUser', 'hl' + tag); pg.fill('#lgPass', 'secret1'); pg.click('[data-act="lg-submit"]')
    pg.wait_for_selector('#gtTeam', timeout=8000); pg.fill('#gtTeam', '하이팀'); pg.click('[data-act="team-create"]')
    pg.wait_for_selector('.hd [data-act="team"]', timeout=8000)
    pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]'); pg.fill('[data-f="svc.name"]', '하이 예배')
    pg.click('[data-act="add-item"]'); pg.wait_for_selector('[data-f="item.title"]'); pg.fill('[data-f="item.title"]', '곡')
    pg.set_input_files('#pieceFile', [SHEET])
    pg.wait_for_function("(()=>{const p=(CONTI.S.services[0].items[0].pieces||[])[0];return p&&p.ocr&&p.ocr!=='pending'})()", timeout=90000)
    pg.wait_for_timeout(1200)

    def drag(x0, y0, x1, y1):
        sl = pg.locator('.slice').first.bounding_box()
        pg.mouse.move(sl['x'] + x0, sl['y'] + y0); pg.mouse.down()
        pg.mouse.move(sl['x'] + (x0 + x1) / 2, sl['y'] + (y0 + y1) / 2, steps=4)
        pg.mouse.move(sl['x'] + x1, sl['y'] + y1, steps=4); pg.mouse.up(); pg.wait_for_timeout(700)

    # ---- 배경 크기가 좌표계와 맞아야 한다 (auto 였을 때 어긋났다) ----
    bg = pg.evaluate("(()=>{const sl=document.querySelector('.slice');return {bg:sl.style.backgroundSize,s:sl.dataset.s,w:sl.clientWidth}})()")
    if 'auto' in (bg['bg'] or ''): fail('배경 높이가 auto 라 비율이 어긋날 수 있음: %s' % bg)
    if not bg['s']: fail('슬라이스에 배율(data-s)이 없음')
    print('slice ok:', bg)

    pg.click('[data-act="tool"][data-t="hl"]'); pg.wait_for_timeout(400)
    drag(60, 60, 220, 100)
    hls = pg.evaluate("CONTI.S.services[0].items[0].pieces[0].hls")
    if len(hls) != 1: fail('하이라이트가 안 만들어짐: %s' % hls)
    made = hls[0]
    print('created ok:', {k: round(v) if isinstance(v, (int, float)) else v for k, v in made.items() if k != 'id'})

    # ---- 그린 자리에 그려졌는가 (화면 좌표로 되돌려 비교) ----
    box = pg.evaluate("(()=>{const e=document.querySelector('.hl[data-hl]');const s=+e.closest('.slice').dataset.s;return {l:parseFloat(e.style.left)/s,t:parseFloat(e.style.top)/s,w:parseFloat(e.style.width)/s}})()")
    if abs(box['l'] - made['x']) > 2: fail('가로 위치가 어긋남: 화면 %s vs 저장 %s' % (box['l'], made['x']))
    if abs(box['w'] - made['w']) > 2: fail('너비가 어긋남: %s vs %s' % (box['w'], made['w']))
    print('placement ok')

    # ---- 살짝 떨린 탭은 하이라이트를 만들지 않는다 ----
    sl = pg.locator('.slice').first.bounding_box()
    pg.mouse.move(sl['x'] + 400, sl['y'] + 200); pg.mouse.down()
    pg.mouse.move(sl['x'] + 403, sl['y'] + 202, steps=2); pg.mouse.up(); pg.wait_for_timeout(600)
    if len(pg.evaluate("CONTI.S.services[0].items[0].pieces[0].hls")) != 1: fail('떨린 탭이 하이라이트를 만듦')
    print('tiny drag ignored ok')

    # ---- 탭하면 지워진다 ----
    el = pg.locator('.hl[data-hl]').first.bounding_box()
    pg.mouse.click(el['x'] + el['width'] / 2, el['y'] + el['height'] / 2); pg.wait_for_timeout(900)
    if pg.evaluate("CONTI.S.services[0].items[0].pieces[0].hls").__len__(): fail('탭해도 안 지워짐')
    print('delete ok')

    # ---- 판 폭을 바꾼 뒤에도 자리가 맞는다 ----
    drag(80, 120, 260, 170)
    before = pg.evaluate("CONTI.S.services[0].items[0].pieces[0].hls[0]")
    pg.set_viewport_size({'width': 1000, 'height': 950}); pg.wait_for_timeout(900)
    after = pg.evaluate("(()=>{const e=document.querySelector('.hl[data-hl]');const s=+e.closest('.slice').dataset.s;return {l:parseFloat(e.style.left)/s,w:parseFloat(e.style.width)/s}})()")
    if abs(after['l'] - before['x']) > 2 or abs(after['w'] - before['w']) > 2:
        fail('폭이 바뀐 뒤 자리가 어긋남: %s vs 저장 %s' % (after, before))
    print('after resize ok')

    if errs: fail('페이지 오류:\n' + '\n'.join(errs[:5]))
    print('PASS test_hl')
    b.close()

run()
