# 콘티를 지우면 그 때문에 생긴 일정도 같이 사라진다.
# 예전에는 일정이 남아 홈의 D-day 카드에 계속 뜨고, '콘티 만들기'를 누르면
# 지웠던 예배가 되살아난 것처럼 보였다.
import os, sys, time
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
tag = str(int(time.time()))[-6:]
def fail(m): print('FAIL:', m); sys.exit(1)

def run():
  with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    ctx = b.new_context(viewport={'width': 1300, 'height': 950}); L = ctx.new_page()
    L.on('pageerror', lambda e: errs.append(str(e))); L.on('dialog', lambda d: d.accept())
    L.goto(URL); L.wait_for_selector('#lgUser', timeout=8000)
    L.click('[data-act="lg-mode"][data-m="signup"]'); L.wait_for_selector('#lgName')
    L.check('#lgAgree')
    L.fill('#lgName', '하은'); L.fill('#lgUser', 'dd' + tag); L.fill('#lgPass', 'secret1')
    L.click('[data-act="lg-submit"]')
    L.wait_for_selector('#gtTeam', timeout=8000); L.fill('#gtTeam', '삭제팀'); L.click('[data-act="team-create"]')
    L.wait_for_selector('.shell[data-page]', timeout=8000)

    # 날짜가 있는 예배를 만들어 발행한다 → 서버에 일정이 함께 생긴다
    fut = time.strftime('%Y-%m-%d', time.localtime(time.time() + 14*86400))
    L.click('[data-act="new-svc"]'); L.wait_for_selector('[data-f="svc.name"]')
    L.fill('[data-f="svc.name"]', '지울 예배')
    L.fill('[data-f="svc.date"]', fut); L.wait_for_timeout(400)
    L.click('[data-act="add-item"]'); L.wait_for_selector('[data-f="item.title"]')
    L.fill('[data-f="item.title"]', '곡'); L.fill('[data-f="item.key"]', 'G'); L.wait_for_timeout(500)
    svc = L.evaluate('CONTI.S.services[0].id')
    L.click('[data-act="publish"]'); L.wait_for_selector('#pubOnly', timeout=6000)
    L.click('#pubOnly'); L.wait_for_timeout(3500)

    def dates():
      return L.evaluate("async()=>{const r=await fetch('/api/teams/'+CONTI.S.team.id+'/dates',{headers:{'x-conti':'1'}});const j=await r.json();return (j.dates||[]).map(d=>d.date+'|'+d.label+'|'+d.source)}")
    got = dates()
    if not any(fut in x for x in got): fail(f'발행했는데 일정이 안 생김: {got}')
    print('발행 후 일정:', got)

    # 예배 삭제
    L.evaluate(f"async()=>{{await fetch('/api/services/{svc}?team='+CONTI.S.team.id,{{method:'DELETE',headers:{{'x-conti':'1'}}}})}}")
    L.wait_for_timeout(1500)
    got2 = dates()
    print('삭제 후 일정:', got2)
    if any(fut in x for x in got2):
      fail(f'콘티를 지웠는데 그 때문에 생긴 일정이 남아 있음: {got2}')

    # 반대쪽: 인도자가 직접 연 날짜는 콘티를 지워도 남아야 한다
    fut2 = time.strftime('%Y-%m-%d', time.localtime(time.time() + 21*86400))
    L.evaluate("""async(d)=>{await fetch('/api/teams/'+CONTI.S.team.id+'/dates',{method:'POST',
      headers:{'x-conti':'1','content-type':'application/json'},body:JSON.stringify({date:d,label:'직접 연 날짜'})})}""", fut2)
    L.wait_for_timeout(1200)
    L.evaluate("()=>{location.hash='#/home';CONTI.render()}"); L.wait_for_timeout(1500)
    L.click('[data-act="new-svc"]'); L.wait_for_selector('[data-f="svc.name"]')
    L.fill('[data-f="svc.name"]', '직접 연 날짜'); L.fill('[data-f="svc.date"]', fut2); L.wait_for_timeout(400)
    L.click('[data-act="add-item"]'); L.wait_for_selector('[data-f="item.title"]')
    L.fill('[data-f="item.title"]', '곡'); L.fill('[data-f="item.key"]', 'C'); L.wait_for_timeout(500)
    svc2 = L.evaluate('CONTI.S.services[0].id')
    L.click('[data-act="publish"]'); L.wait_for_selector('#pubOnly', timeout=6000)
    L.click('#pubOnly'); L.wait_for_timeout(3500)
    L.evaluate(f"async()=>{{await fetch('/api/services/{svc2}?team='+CONTI.S.team.id,{{method:'DELETE',headers:{{'x-conti':'1'}}}})}}")
    L.wait_for_timeout(1500)
    got3 = dates()
    print('직접 연 날짜 — 콘티 삭제 후:', got3)
    if not any(fut2 in x for x in got3):
      fail(f'인도자가 직접 연 날짜까지 지워짐: {got3}')

    if errs: fail('콘솔 오류: ' + errs[0])
    print('OK — 딸린 일정만 사라지고, 직접 연 날짜는 남음')
    b.close()

run()
