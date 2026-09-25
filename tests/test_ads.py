# 광고: 무료 플랜에만 나오고 유료 플랜에는 안 나온다.
# 예배 중 화면(연습·콘티 보기·무대)에는 무료라도 안 나온다.
# 웹 광고(애드센스)는 승인 전이라 스위치(WEBADS.on)로 꺼 두었다 — 꺼져 있으면 아무것도 없고, 켜면 아래처럼 돈다
# (꺼진 상태의 요청·자리 검사는 tests/test_banner.py)
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
    L.click('[data-act="lg-mode"][data-m="signup"]'); L.wait_for_selector('#lgName'); L.check('#lgAgree')
    L.fill('#lgName', '하은'); L.fill('#lgUser', 'ad' + tag); L.fill('#lgPass', 'secret1')
    L.click('[data-act="lg-submit"]')
    L.wait_for_selector('#gtTeam', timeout=8000); L.fill('#gtTeam', '광고팀'); L.click('[data-act="team-create"]')
    L.wait_for_selector('.shell[data-page]', timeout=8000)

    # 승인된 주소가 아니면(로컬·미리보기) 광고를 부르지 않는다 — 정책 위반이고 오류가 난다
    if L.evaluate("CONTI.webAdsAllowed()"): fail('로컬인데 광고를 넣으려 함')
    # 스위치는 기본으로 꺼져 있다 (애드센스 승인 전). 승인된 주소·무료 플랜이라도 광고가 없다
    if L.evaluate("CONTI.WEBADS.on") is not False: fail('웹 광고 스위치가 기본으로 꺼져 있지 않음')
    if L.evaluate("(()=>{CONTI.AD_HOSTS.add(location.hostname);CONTI.S.team.plan='free';const r=CONTI.webAdsAllowed();CONTI.AD_HOSTS.delete(location.hostname);return r})()"):
      fail('스위치가 꺼졌는데 광고를 허락함')
    L.evaluate("CONTI.WEBADS.on=true")   # 여기부터는 켰을 때 (코드는 그대로 둔다)

    # 운영 주소인 것처럼 흉내 내면 무료 플랜에서는 나온다.
    # 실제 애드센스 스크립트는 부르지 않는다 (승인 안 된 주소라 오류가 난다)
    L.evaluate("""()=>{CONTI.AD_HOSTS.add(location.hostname);
      window.__adsPushed=0;
      Object.defineProperty(window,'adsbygoogle',{value:{push(){window.__adsPushed++}},configurable:true});
      CONTI.S.team.plan='free';CONTI.render()}""")
    L.wait_for_timeout(1200)
    if not L.evaluate("CONTI.webAdsAllowed()"): fail('무료 플랜인데 광고가 안 나옴')
    # 광고는 연습 화면에만 — 홈·라이브러리·일정·알림함에는 자리가 없어야 한다
    if L.locator('.webad').count(): fail('홈에 광고 자리가 남음')
    for name, h in [('라이브러리','#/library'), ('일정','#/cal'), ('알림함','#/inbox')]:
      L.evaluate("(x)=>{location.hash=x}", h); L.wait_for_timeout(900)
      if L.locator('.webad').count(): fail('%s 에 광고 자리가 남음' % name)
    # 연습 화면에는 자리가 있다 (곡 하나 있는 예배를 만들어 들어간다)
    L.evaluate("()=>{location.hash='#/home'}"); L.wait_for_timeout(600)
    L.click('[data-act="new-svc"]'); L.wait_for_selector('[data-f="svc.name"]', timeout=8000)
    L.fill('[data-f="svc.name"]', '광고 예배'); L.click('[data-act="add-item"]'); L.wait_for_selector('[data-f="item.title"]'); L.fill('[data-f="item.title"]', '곡'); L.wait_for_timeout(500)
    sid = L.evaluate("CONTI.S.services[0].id")
    L.evaluate("(x)=>{location.hash=x}", '#/play/'+sid); L.wait_for_timeout(1500)
    if not L.locator('.webad').count(): fail('연습 화면에 광고 자리가 없음')

    # 광고가 안 들어오면 자리를 접는다 — 안 접으면 예배 목록에 400px 빈 구멍이 남는다
    collapsed = L.evaluate("""(()=>{const e=document.querySelector('.webad');
      if(!e)return 'no-slot';
      e.setAttribute('data-ad-status','unfilled');
      return getComputedStyle(e).display})()""")
    if collapsed != 'none': fail('광고가 비었는데 자리가 안 접힘: %s' % collapsed)
    L.evaluate("()=>{location.hash='#/home'}"); L.wait_for_timeout(800)

    # 유료 플랜에서는 사라져야 한다
    for plan in ['pro', 'plus']:
      L.evaluate("(p)=>{CONTI.S.team.plan=p;CONTI.render()}", plan)
      L.wait_for_timeout(1000)
      if L.evaluate("CONTI.webAdsAllowed()"): fail('%s 플랜인데 광고가 나옴' % plan)
      if L.locator('.webad').count(): fail('%s 플랜인데 광고 자리가 남음' % plan)
      for h in ['#/library', '#/cal', '#/inbox']:
        L.evaluate("(x)=>{location.hash=x}", h); L.wait_for_timeout(900)
        if L.locator('.webad').count(): fail('%s 플랜인데 %s 에 광고가 남음' % (plan, h))
      L.evaluate("()=>{location.hash='#/home'}"); L.wait_for_timeout(800)

    # 애드센스 스크립트 자체의 오류는 우리 잘못이 아니므로 뺀다
    ours = [e for e in errs if 'adsbygoogle' not in e and len(e) > 4]
    if ours: fail('콘솔 오류: ' + ours[0])
    print('OK — 네 자리 모두 · 무료만 광고 · 유료는 광고 없음 · 승인된 주소에서만')
    b.close()

run()
