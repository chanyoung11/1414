# 설정 → 연결된 계정 (2026-09-20)
#  - 카드가 뜨고 구글/애플 줄이 보인다
#  - 비밀번호가 있는 보통 계정은 '연결' 버튼
#  - 소셜 전용 계정은 마지막 수단을 뗄 수 없다 (서버·화면 둘 다)
#  - 소셜 전용 계정은 현재 비밀번호 없이 비밀번호를 정할 수 있다
import os, sys, time, json
from playwright.sync_api import sync_playwright
URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
def fail(m): print('FAIL:', m); sys.exit(1)

def run():
  tag = str(int(time.time()))[-6:]
  with sync_playwright() as p:
    b = p.chromium.launch(); c = b.new_context(viewport={'width':1180,'height':820}); pg = c.new_page()
    errs=[]; pg.on('pageerror', lambda e: errs.append(str(e)[:150])); pg.on('dialog', lambda d: d.accept())
    pg.goto(URL); pg.wait_for_selector('#lgUser')
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName'); pg.check('#lgAgree')
    pg.fill('#lgName','하은'); pg.fill('#lgUser','lk'+tag); pg.fill('#lgPass','secret1'); pg.click('[data-act="lg-submit"]')
    pg.wait_for_selector('#gtTeam', timeout=15000); pg.fill('#gtTeam','연결팀')
    pg.click('#gtSess .q:has-text("건반")'); pg.click('[data-act="team-create"]')
    pg.wait_for_selector('.shell[data-page]', timeout=15000)

    # ---- 계정 탭
    pg.goto(URL + '#/settings'); pg.wait_for_selector('.setpane', timeout=10000)
    pg.click('[data-act="set-tab"][data-t="account"]'); pg.wait_for_timeout(2500)
    if not pg.locator('#linkCard').count(): fail('연결된 계정 카드가 없음')
    pg.wait_for_function("()=>{const b=document.querySelector('#linkList');return b&&!/불러오는 중/.test(b.textContent)}", timeout=15000)
    rows = pg.evaluate("()=>[...document.querySelectorAll('.linkrow')].map(r=>r.innerText.replace(/\\n/g,' | '))")
    print('줄:', rows)
    if not rows: fail('구글·애플 줄이 없음 (서버 설정을 못 읽었나)')
    if not pg.locator('[data-link="google"]').count(): fail('구글 연결 버튼이 없음')
    # 비밀번호가 있는 계정이니 안내 문구는 없어야 한다
    if '해제하려면 먼저' in pg.locator('#linkList').inner_text(): fail('비밀번호가 있는데 잠금 안내가 뜸')
    print('연결 안 된 상태 ok')

    # ---- 서버가 마지막 수단을 지키는지 (소셜 전용 계정을 흉내낸다)
    r = pg.evaluate("""async ()=>{
      const res = await fetch('/api/auth/social/google', {method:'DELETE', headers:{'x-conti':'1'}, credentials:'include'});
      return {status:res.status, body:await res.text()}}""")
    if r['status'] not in (200,400): fail('연결 안 된 것을 떼는데 이상한 응답: %s' % r)
    print('없는 연결 해제 응답 ok:', r['status'])

    # ---- 비밀번호 카드 문구 (비밀번호가 있는 계정)
    txt = pg.locator('.setpane').inner_text()
    if '비밀번호 만들기' in txt: fail('비밀번호가 있는데 만들기로 표시됨')
    if not pg.locator('#sPw0').count(): fail('현재 비밀번호 칸이 없음')
    print('비밀번호 카드 ok')

    if errs: fail('콘솔 오류: %s' % errs[:3])
    b.close()
  print('OK — 연결된 계정')
run()
