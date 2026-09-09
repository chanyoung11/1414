# 실제 채보: 사진 → 오선 줄 단위 /api/score → 병합 → OSMD 렌더 (실비 발생, 대략 30~80원)
import os, sys, time
from playwright.sync_api import sync_playwright
URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHEET = os.environ.get('SCORE_SHEET', os.path.join(ROOT, 'docs', 'sample_sheet.jpg'))
tag = str(int(time.time()))[-6:]
def fail(m): print('FAIL:', m); sys.exit(1)

def run():
  with sync_playwright() as p:
    b = p.chromium.launch(); errs=[]
    ctx=b.new_context(viewport={'width':1300,'height':950}); pg=ctx.new_page()
    pg.on('pageerror',lambda e:errs.append(str(e))); pg.on('dialog',lambda d:d.accept())
    pg.goto(URL); pg.wait_for_selector('#lgUser',timeout=8000)
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName')
    pg.fill('#lgName','하은'); pg.fill('#lgUser','sl'+tag); pg.fill('#lgPass','secret1'); pg.click('[data-act="lg-submit"]')
    pg.wait_for_selector('#gtTeam',timeout=8000); pg.fill('#gtTeam','악보팀'); pg.click('[data-act="team-create"]'); pg.wait_for_selector('.hd [data-act="team"]',timeout=8000)
    if not ctx.request.get(URL+'api/omr').json().get('available'): fail('GEMINI_API_KEY 없음')
    pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]'); pg.fill('[data-f="svc.name"]','악보 예배')
    pg.click('[data-act="add-item"]'); pg.wait_for_selector('[data-f="item.title"]')
    pg.set_input_files('#pieceFile',[SHEET])
    pg.wait_for_function("(()=>{const p=CONTI.S.services[0].items[0].pieces[0];return p&&p.ocr&&p.ocr!=='pending'})()",timeout=90000)
    pg.wait_for_selector('[data-act="score-make"]',timeout=10000)
    t0=time.time(); pg.click('[data-act="score-make"]')
    pg.wait_for_selector('#osmd svg',timeout=240000); pg.wait_for_timeout(2000)
    dt=time.time()-t0
    sc=pg.evaluate("(()=>{const s=CONTI.S.services[0].items[0].score;return {n:s.measures.length,key:s.key,time:s.time,title:s.title,tempo:s.tempo,lines:s.lines,failed:s.failed,cost:s.cost,bad:CONTI.badMeasuresOf(s).length}})()")
    print('score: %s  (%.1fs)' % (sc, dt))
    if sc['n'] < 4: fail('마디가 너무 적음: %s' % sc)
    if sc['failed']: print('WARN: 실패한 줄', sc['failed'])
    ratio = sc['bard'] if False else (sc['bad']/max(1,sc['n']))
    print('bad measures: %d/%d (%.0f%%)' % (sc['bad'], sc['n'], ratio*100))
    if ratio > 0.25: fail('박자 오류가 %.0f%% — 너무 높아요' % (ratio*100))
    paths=pg.evaluate("document.querySelectorAll('#osmd svg path').length")
    if paths<40: fail('악보가 제대로 안 그려짐: path %d' % paths)
    pg.screenshot(path=os.path.join(ROOT,'tests','t_score_live.png'), full_page=True)
    print('paths', paths, '· screenshot tests/t_score_live.png')
    if errs: fail('page errors:\n'+'\n'.join(errs[:5]))
    print('PASS test_score_live')
    b.close()
run()
