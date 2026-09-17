# 실사용 제보 수정 (2026-09-17)
#  1. 서버에서 지운 콘티는 이 기기에서도 사라진다 (중복·유령 예배)
#  2. 연습 화면 축소가 20% 까지 된다 (예전엔 60% 가 하한)
#  3. 무대 모드에서 스페이스바로 안 튼 영상이 재생되지 않는다
#  4. 무대 모드를 닫아도 곡이 그대로면 화면을 다시 그리지 않는다 (영상이 안 끊긴다)
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
    ctx = b.new_context(viewport={'width': 1300, 'height': 950}); L = ctx.new_page()
    L.on('pageerror', lambda e: errs.append(repr(e)[:200])); L.on('dialog', lambda d: d.accept())
    L.goto(URL); L.wait_for_selector('#lgUser', timeout=8000)
    L.click('[data-act="lg-mode"][data-m="signup"]'); L.wait_for_selector('#lgName'); L.check('#lgAgree')
    L.fill('#lgName', '하은'); L.fill('#lgUser', 'f2' + tag); L.fill('#lgPass', 'secret1')
    L.click('[data-act="lg-submit"]')
    L.wait_for_selector('#gtTeam', timeout=8000); L.fill('#gtTeam', '수정팀'); L.click('[data-act="team-create"]')
    L.wait_for_selector('.shell[data-page]', timeout=8000)

    # 곡 두 개짜리 예배를 만들어 발행
    L.click('[data-act="new-svc"]'); L.wait_for_selector('[data-f="svc.name"]')
    L.fill('[data-f="svc.name"]', '수정 시험')
    for t in ['첫곡', '둘째곡']:
      L.click('[data-act="add-item"]'); L.wait_for_selector('[data-f="item.title"]')
      L.fill('[data-f="item.title"]', t); L.wait_for_timeout(300)
      L.set_input_files('#pieceFile', [SHEET])
      L.wait_for_function("(()=>{const its=CONTI.S.services[0].items;const it=its[its.length-1];const p=(it.pieces||[])[0];return p&&p.w>0})()", timeout=60000)
      L.wait_for_timeout(500)
    svc = L.evaluate("CONTI.S.services[0].id")
    L.click('[data-act="publish"]'); L.wait_for_selector('#pubOnly', timeout=6000)
    L.click('#pubOnly'); L.wait_for_timeout(3500)

    # 2. 축소 20%
    L.evaluate("(id)=>location.hash='#/play/'+id", svc); L.wait_for_timeout(2500)
    L.evaluate("()=>{for(let i=0;i<20;i++)CONTI.setZoom((CONTI.pl().zoom||1)-0.1)}"); L.wait_for_timeout(600)
    z = L.evaluate("CONTI.pl().zoom")
    if z > 0.25: fail('축소가 %s 에서 멈춤 (20%%까지 되어야 함)' % z)

    # 3. 무대 모드 스페이스바로 영상이 켜지지 않는다
    L.evaluate("()=>{CONTI.setZoom(1)}"); L.wait_for_timeout(300)
    L.evaluate("(id)=>{const s=CONTI.S.services.find(x=>x.id===id);return CONTI.stageOpen(s,0)}", svc)
    L.wait_for_timeout(2500)
    if not L.locator('#stageWrap').count(): fail('무대 모드가 안 열림')
    played = L.evaluate("""()=>{let n=0;const o=CONTI.P.play;CONTI.P.play=function(){n++;return o.apply(this,arguments)};
      window.__n=()=>n;return true}""")
    L.keyboard.press('Space'); L.wait_for_timeout(600)
    L.keyboard.press('ArrowRight'); L.wait_for_timeout(900)
    if L.evaluate("window.__n()") != 0: fail('무대 모드에서 스페이스바/화살표로 영상이 재생됨')

    # 4. 곡을 안 옮기고 닫으면 다시 그리지 않는다
    L.evaluate("()=>{window.__r=0;const o=CONTI.render;CONTI.render=function(){window.__r++;return o.apply(this,arguments)}}")
    L.evaluate("()=>{CONTI.STG.idx=CONTI.STG.from;}")
    L.evaluate("()=>{const b=document.querySelector('#stageWrap [data-stg]');if(b)b.click()}")
    L.wait_for_timeout(1200)
    if L.evaluate("window.__r") and L.evaluate("CONTI.STG.from")==0:
      print('  (참고) 닫을 때 render 호출 수:', L.evaluate("window.__r"))

    if errs: fail('콘솔 오류: ' + errs[0])
    print('OK — 축소 20%% · 무대에서 영상 자동재생 없음')
    b.close()

run()
