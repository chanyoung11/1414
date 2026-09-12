# 채보(OMR) 연결 검증: 편집기 '채보' 버튼 → /api/omr → 결과 모달 → 곡 정보 적용
# 준비: dev 서버에 GEMINI_API_KEY (실제 키면 악보 1장 ≈ 6원, 'mock' 이면 무료)
import os, sys, time
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHEET = os.path.join(ROOT, 'docs', 'sample_sheet.jpg')
tag = str(int(time.time()))[-6:]
L = ('om' + tag, 'secret1', '하은')

def fail(msg): print('FAIL:', msg); sys.exit(1)

def run():
    with sync_playwright() as p:
        b = p.chromium.launch(); errs = []
        ctx = b.new_context(viewport={'width': 1180, 'height': 820}); pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('dialog', lambda d: d.accept())
        pg.goto(URL); pg.wait_for_selector('#lgUser', timeout=8000)
        pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName'); pg.fill('#lgName', L[2]); pg.fill('#lgUser', L[0]); pg.fill('#lgPass', L[1]); pg.click('[data-act="lg-submit"]')
        pg.wait_for_selector('#gtTeam', timeout=8000); pg.fill('#gtTeam', '채보팀'); pg.click('[data-act="team-create"]'); pg.wait_for_selector('.shell[data-page]', timeout=8000)
        avail = ctx.request.get(URL + 'api/omr').json()
        print('omr:', avail)
        if not avail.get('available'): fail('dev 서버에 GEMINI_API_KEY 가 없어요')
        pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]'); pg.fill('[data-f="svc.name"]', '채보 예배')
        pg.click('[data-act="add-item"]'); pg.wait_for_selector('[data-f="item.title"]')
        pg.set_input_files('#pieceFile', [SHEET])
        pg.wait_for_function("(()=>{const p=CONTI.S.services[0].items[0].pieces[0];return p&&p.ocr&&p.ocr!=='pending'})()", timeout=60000)
        pg.wait_for_selector('[data-act="omr"]', timeout=10000)
        t0 = time.time(); pg.click('[data-act="omr"]')
        pg.wait_for_selector('#modal [data-apply]', timeout=90000)
        print('omr modal in %.1fs' % (time.time() - t0))
        txt = pg.locator('#modal').inner_text()
        if '채보 결과' not in txt: fail('채보 결과 모달이 아님')
        pg.click('#modal [data-apply="0"]'); pg.wait_for_timeout(600)
        it = pg.evaluate("(()=>{const it=CONTI.S.services[0].items[0];return {title:it.title,key:it.key,form:it.form,sections:it.chart?it.chart.sections.length:0,model:it.chart&&it.chart.model}})()")
        print('applied:', it)
        if not it['title'] or not it['key'] or not it['form'] or it['sections'] < 1: fail('곡 정보에 채보 결과가 안 들어감: %s' % it)
        if avail.get('mock') is False and it['title'] != '우리 주 하나님': print('WARN: 제목이 기대와 다름:', it['title'])
        print('errors:', errs)
        if errs: fail('page errors')
        b.close()
    print('OMR TEST OK')

if __name__ == '__main__':
    run()
