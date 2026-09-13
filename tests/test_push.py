# 개인 설정 서버 동기화 + 푸시 알림 (§1-A 동기화 · UI통일 §6.8 조용한 시간)
# 앱 안 알림은 전부 푸시로도 나간다. 조용한 시간에는 알림함에만 쌓인다.
import os, sys, time
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = 'http://localhost:8766/'
H = {'x-conti': '1'}
def fail(m): print('FAIL:', m); sys.exit(1)

def signup(pg, user, name='하은'):
    pg.goto(URL); pg.wait_for_selector('#lgUser')
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName')
    pg.fill('#lgName', name); pg.fill('#lgUser', user); pg.fill('#lgPass','secret1')
    pg.click('[data-act="lg-submit"]')

def quiet_unit():
    out = os.popen("cd %s && node scripts/quiet-check.mjs 2>&1 | tail -1" % ROOT).read().strip()
    if out != 'OK': fail('조용한 시간 계산: ' + out)
    print('조용한 시간 계산 ok (22~08 기본, 자정 넘김 포함)')

def run():
    quiet_unit()
    tag = str(int(time.time()))[-6:]
    with sync_playwright() as p:
        b = p.chromium.launch()
        # 알림 권한을 미리 준 창 (푸시 구독까지 가는지 보려고)
        c = b.new_context(viewport={'width':1180,'height':820}, permissions=['notifications'])
        pg = c.new_page(); errs=[]
        pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('dialog', lambda d: d.accept())
        signup(pg, 'pu'+tag)
        pg.wait_for_selector('#gtTeam'); pg.fill('#gtTeam','푸시팀'); pg.click('#gtSess .q:has-text("건반")')
        pg.click('[data-act="team-create"]'); pg.wait_for_selector('.shell[data-page]', timeout=10000)
        pg.wait_for_timeout(1500)

        # ---- 조용한 시간이 서버에 저장된다 ----
        pg.goto(URL + '#/settings'); pg.wait_for_selector('.setpane', timeout=8000)
        pg.click('[data-act="set-tab"][data-t="noti"]'); pg.wait_for_selector('#sQuiet', timeout=5000)
        if not pg.locator('#sQuiet').is_checked(): fail('조용한 시간 기본이 켬이 아님')
        pg.fill('#sQFrom','23'); pg.dispatch_event('#sQFrom','change'); pg.wait_for_timeout(800)
        pg.fill('#sQTo','7');   pg.dispatch_event('#sQTo','change');   pg.wait_for_timeout(1000)
        srv = c.request.get(URL + 'api/me/prefs', headers=H).json()
        qh = (srv.get('prefs') or {}).get('quiet') or {}
        if qh.get('from') != 23 or qh.get('to') != 7: fail('조용한 시간이 서버에 안 올라감: %s' % srv)
        print('조용한 시간 서버 저장 ok:', qh)

        # 껐다 켜도 서버에 반영
        pg.click('#sQuiet'); pg.wait_for_timeout(900)
        srv = c.request.get(URL + 'api/me/prefs', headers=H).json()
        if ((srv.get('prefs') or {}).get('quiet') or {}).get('on') is not False: fail('조용한 시간 끄기가 안 올라감')
        print('조용한 시간 끄기 ok')

        # ---- 알림 종류 끄기도 서버로 (푸시를 거르는 데 쓰인다) ----
        pg.locator('[data-noti="publish"]').uncheck(); pg.wait_for_timeout(900)
        srv = c.request.get(URL + 'api/me/prefs', headers=H).json()
        if ((srv.get('prefs') or {}).get('notiOff') or {}).get('publish') is not True:
            fail('알림 종류 끄기가 서버에 안 올라감: %s' % srv)
        print('알림 종류 끄기 서버 저장 ok')

        # ---- 푸시 구독 ----
        # 헤드리스 크로뮴은 푸시 서비스에 붙지 못해 브라우저 구독을 만들 수 없다.
        # 그래서 서버가 구독을 제대로 받아 두는지를 직접 확인한다.
        key = c.request.get(URL + 'api/push/key', headers=H).json()
        if not key.get('configured'): fail('VAPID 키가 설정 안 됨 — 푸시가 아예 안 나감')
        sub = {'endpoint': 'https://example.invalid/push/' + tag,
               'keys': {'p256dh': 'BObJ' + 'A'*83, 'auth': 'x'*22}}
        r = c.request.post(URL + 'api/push/subscribe', headers=H, data={'sub': sub})
        if r.status != 200: fail('구독 등록 실패: %s %s' % (r.status, r.text()))
        # 같은 기기가 다시 보내도 한 줄로 (endpoint 가 기본키)
        c.request.post(URL + 'api/push/subscribe', headers=H, data={'sub': sub})
        n = int(os.popen("""cd %s && DATABASE_URL="postgres://postgres:pg@localhost:54329/postgres" node -e '
          import("pg").then(async ({default:pg})=>{const c=new pg.Client({connectionString:process.env.DATABASE_URL});
          await c.connect();const r=await c.query("select count(*)::int n from push_subs where endpoint=$1",["%s"]);
          console.log(r.rows[0].n);await c.end()})' 2>/dev/null""" % (ROOT, sub['endpoint'])).read().strip() or '0')
        if n != 1: fail('구독이 한 줄로 저장되지 않음: %s' % n)
        print('구독 저장 ok (중복 등록해도 한 줄)')
        # 죽은 endpoint 로 보내도 발행이 깨지지 않는다
        t = c.request.post(URL + 'api/push/test', headers=H)
        if t.status != 200: fail('시험 발송이 500: %s' % t.text())
        print('시험 발송 ok (못 보내도 오류 아님):', t.json())
        c.request.post(URL + 'api/push/unsubscribe', headers=H, data={'endpoint': sub['endpoint']})

        # ---- 무대 조판이 서버에 올라가고, 새 기기(새 창)에서 그대로 온다 ----
        sid = pg.evaluate("""(()=>{const s=CONTI.S.services;return s.length?s[0].id:null})()""")
        res = pg.evaluate("""(async()=>{const st={zoom:1.3,cols:2,memos:false,hl:true,bar:true};
          const r=await fetch('/api/me/prefs/stage/'+encodeURIComponent('song-x~tab-l'),
            {method:'PUT',headers:{'content-type':'application/json','x-conti':'1'},
             body:JSON.stringify({value:st})});
          return {status:r.status, body:await r.text()}})()""")
        print('조판 PUT 응답:', res)
        pg.wait_for_timeout(800)
        srv = c.request.get(URL + 'api/me/prefs', headers=H).json()
        st = ((srv.get('prefs') or {}).get('stage') or {}).get('song-x~tab-l')
        if not st or st.get('zoom') != 1.3: fail('무대 조판이 서버에 안 올라감: %s' % srv)
        print('무대 조판 서버 저장 ok:', st)

        # 다른 곡·기기 구간 것을 덮지 않는다
        pg.evaluate("""(()=>fetch('/api/me/prefs/stage/'+encodeURIComponent('song-y~phone'),
            {method:'PUT',headers:{'content-type':'application/json','x-conti':'1'},
             body:JSON.stringify({value:{zoom:0.8,cols:1}})}).then(r=>r.ok))()""")
        pg.wait_for_timeout(800)
        srv = c.request.get(URL + 'api/me/prefs', headers=H).json()
        stg = (srv.get('prefs') or {}).get('stage') or {}
        if len(stg) != 2: fail('무대 조판이 서로 덮음: %s' % stg)
        if stg['song-x~tab-l'].get('zoom') != 1.3: fail('앞서 저장한 조판이 날아감: %s' % stg)
        if ((srv.get('prefs') or {}).get('quiet') or {}).get('from') != 23: fail('조판 저장이 다른 설정을 날림')
        print('조판·설정 서로 안 덮음 ok:', list(stg.keys()))

        # 새 창에서 로그인해도 내 조판이 따라온다 (교회 컴퓨터에서 PDF 뽑는 경우)
        c2 = b.new_context(viewport={'width':1180,'height':820}); p2 = c2.new_page()
        p2.goto(URL); p2.wait_for_selector('#lgUser')
        p2.fill('#lgUser','pu'+tag); p2.fill('#lgPass','secret1'); p2.click('[data-act="lg-submit"]')
        p2.wait_for_selector('.shell[data-page]', timeout=10000); p2.wait_for_timeout(2000)
        got = p2.evaluate("(async()=>{await CONTI.pullPrefs(true);return ((CONTI.PREFS.data||{}).stage||{})['song-x~tab-l']})()")
        if not got or got.get('zoom') != 1.3: fail('다른 기기에서 내 조판이 안 따라옴: %s' % got)
        print('다른 기기에 조판 따라옴 ok:', got)

        if errs: fail('JS 오류: %s' % errs[:3])
        print('errors:', errs)
        print('PASS test_push')
        b.close()
run()
