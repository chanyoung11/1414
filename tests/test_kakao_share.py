# 편성 패널 '카톡으로 보내기' — 앱(iOS)은 서버를 다녀온 뒤 클립보드 쓰기가 막혀 영어 오류만 떴다 → 공유 시트로
# 사용: CONTI_URL=http://localhost:8766/ .venv/bin/python tests/test_kakao_share.py
import os, time, datetime
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
SRV=urlparse(os.environ.get('CONTI_URL','http://localhost:8766/'))
UA='Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148'
MOCK=r"""(()=>{const ok=v=>Promise.resolve(v);window.__shared=[];
window.Capacitor={getPlatform:()=>'ios',isNativePlatform:()=>true,isPluginAvailable:()=>false,Plugins:{
 StatusBar:{setStyle:()=>ok(),setBackgroundColor:()=>ok(),hide:()=>ok(),show:()=>ok()},
 PushNotifications:{checkPermissions:()=>ok({receive:'denied'}),requestPermissions:()=>ok({receive:'denied'}),register:()=>ok(),addListener:()=>ok({remove(){}}),removeAllListeners:()=>ok()},
 App:{addListener:()=>ok({remove(){}}),getLaunchUrl:()=>ok(undefined),getInfo:()=>ok({})},
 SplashScreen:{hide:()=>ok()},KeepAwake:{keepAwake:()=>ok(),allowSleep:()=>ok()},
 Share:{share:async(o)=>{window.__shared.push(o.text);return {}}}}};
try{Object.defineProperty(navigator,'clipboard',{value:{writeText:()=>Promise.reject(new Error('The request is not allowed by the user agent'))}})}catch(e){}
})();"""
tag=str(int(time.time()))[-6:]
def fail(m): print('FAIL',m); raise SystemExit(1)
with sync_playwright() as p:
    b=p.chromium.launch(); errs=[]
    c=b.new_context(viewport={'width':402,'height':874},is_mobile=True,has_touch=True,user_agent=UA)
    def h(route):
        u=urlparse(route.request.url)
        if u.scheme=='https' and u.hostname in ('localhost','lets1414.com'):
            return route.fulfill(response=route.fetch(url='%s://%s/%s'%(SRV.scheme,SRV.netloc,u.path.lstrip('/'))+('?'+u.query if u.query else '')))
        return route.continue_() if u.hostname=='localhost' else route.abort()
    c.route('**/*',h); c.add_init_script(MOCK)
    pg=c.new_page(); pg.on('pageerror',lambda e:errs.append(str(e)))
    pg.goto('https://localhost/'); pg.wait_for_selector('#lgUser',timeout=15000)
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName'); pg.check('#lgAgree')
    pg.fill('#lgName','인도'); pg.fill('#lgUser','kn'+tag); pg.fill('#lgPass','secret12'); pg.click('[data-act="lg-submit"]')
    pg.wait_for_selector('#gtTeam',timeout=15000); pg.fill('#gtTeam','카톡팀'); pg.click('[data-act="team-create"]'); pg.wait_for_selector('.shell[data-page]',timeout=15000)
    pg.wait_for_timeout(1500)
    for sel in ['.ov [data-close]','#modal [data-close]']:
        if pg.locator(sel).count(): pg.locator(sel).first.click(); pg.wait_for_timeout(300)
    tid=pg.evaluate('CONTI.S.team.id')
    d=(datetime.date.today()+datetime.timedelta(days=5)).isoformat()
    did=pg.evaluate("async([t,d])=>{const r=await fetch('/api/teams/'+t+'/dates',{method:'POST',headers:{'x-conti':'1','content-type':'application/json'},credentials:'include',body:JSON.stringify({date:d,label:'주일예배',time:'11:00'})});return (await r.json()).date.id}",[tid,d])
    pg.evaluate("location.hash='#lineup/%s'"%did); pg.wait_for_selector('[data-act="lkakao"]',timeout=10000)
    pg.evaluate("CONTI.closeModal&&CONTI.closeModal()")
    pg.locator('[data-act="lkakao"]').first.click(); pg.wait_for_timeout(1500)
    sh=pg.evaluate('window.__shared')
    toast=pg.evaluate("(document.querySelector('.toast')||{}).textContent||''")
    if not sh or '주일예배' not in sh[0]: fail('앱에서 공유 시트로 안 감: %r toast=%r'%(sh,toast))
    if 'not allowed' in toast: fail('영어 오류 토스트: %r'%toast)
    print('native share ok:', sh[0].splitlines()[0], '| toast:', repr(toast))
    if errs: fail('errors %s'%errs)
    print('OK test_kakao_share'); b.close()
