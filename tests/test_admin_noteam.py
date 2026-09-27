# 운영자는 팀이 없어도 운영자 화면에 들어간다 — 운영용 계정(lets1414admin)은 팀을 만들지 않아 전에는 팀 만들기 화면에 막혔다
# 팀 만들기 화면에 '운영자 화면' 단추 · #admin 새로고침 유지 · 다른 화면은 여전히 팀 만들기 · 운영자가 아니면 단추도 화면도 없음
# 사용: 서버를 ADMIN_USERS=<아이디> 로 띄우고 CONTI_URL=… ADMIN_USER=<아이디> .venv/bin/python tests/test_admin_noteam.py
#       (그 아이디로 팀이 없는 계정이 있으면 로그인, 없으면 만든다 — 비밀번호 secret12)
import os, tempfile
from playwright.sync_api import sync_playwright
URL=os.environ.get('CONTI_URL','http://localhost:8766/')
ADMIN=os.environ.get('ADMIN_USER','qaadm').lower()
S=tempfile.gettempdir()+'/'
def fail(m): print('FAIL',m); raise SystemExit(1)
with sync_playwright() as p:
    b=p.chromium.launch(); errs=[]
    for who,vp in ((ADMIN,{'width':1280,'height':900}),(ADMIN,{'width':390,'height':844})):
        c=b.new_context(viewport=vp); pg=c.new_page(); pg.on('pageerror',lambda e:errs.append(str(e)))
        pg.goto(URL); pg.wait_for_selector('#lgUser',timeout=10000)
        r=c.request.post(URL+'api/auth/login',headers={'x-conti':'1'},data={'username':who,'password':'secret12'})
        if r.status!=200:
            pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName'); pg.check('#lgAgree')
            pg.fill('#lgName','운영'); pg.fill('#lgUser',who); pg.fill('#lgPass','secret12'); pg.click('[data-act="lg-submit"]')
        else: pg.reload()
        pg.wait_for_selector('#gtTeam',timeout=10000)
        if pg.locator('[data-act="admin"]').count()!=1: fail('게이트에 운영자 단추 없음')
        pg.click('[data-act="admin"]'); pg.wait_for_selector('#admNew',timeout=10000)
        if pg.evaluate('location.hash')!='#admin': fail('hash %s'%pg.evaluate('location.hash'))
        pg.screenshot(path=S+'admin_noteam_%d.png'%vp['width'])
        # 다시 켜도 운영자 화면
        pg.reload(); pg.wait_for_selector('#admNew',timeout=10000)
        # 다른 곳(홈)으로 가면 팀 만들기 게이트
        pg.evaluate("location.hash='#home'"); pg.wait_for_selector('#gtTeam',timeout=10000)
        c.close()
    # 운영자가 아닌 사람은 게이트에 단추 없음, #admin 은 게이트
    c=b.new_context(); pg=c.new_page(); pg.on('pageerror',lambda e:errs.append(str(e)))
    pg.goto(URL); pg.wait_for_selector('#lgUser'); pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName'); pg.check('#lgAgree')
    import time; u='qanorm'+str(int(time.time()))[-5:]
    pg.fill('#lgName','보통'); pg.fill('#lgUser',u); pg.fill('#lgPass','secret12'); pg.click('[data-act="lg-submit"]'); pg.wait_for_selector('#gtTeam',timeout=10000)
    if pg.locator('[data-act="admin"]').count(): fail('보통 사람 게이트에 운영자 단추')
    pg.evaluate("location.hash='#admin'"); pg.wait_for_timeout(1500)
    if pg.locator('#admNew').count(): fail('보통 사람이 운영자 화면')
    if errs: fail('errors %s'%errs)
    print('OK admin_noteam'); b.close()
