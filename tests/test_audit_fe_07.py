# 전역감사 2026-09-24 fe-07 되돌림 방지
#  F25 '이 기기에서 끄기'가 홈에 오면 풀리던 것 · 홈마다 푸시 구독을 5~6번 보내던 것
#  F89 마디를 고칠 때마다 악보가 맨 위로 튀던 것
#  G08 악보 화면이 콘티의 연주 키(it.key)를 무시하던 것 (인쇄·내보내기 포함)
#  G33 고치기 중에 옮긴 악보를 보고 원래 값을 고치던 것
#  G34 코드 칸이 대문자 고정이라 폰에서 Bm7 이 BM7 로 들어가던 것
#  G19 카포·'여기부터 전조'로 옮긴 코드를 원래 연주 키의 #·b 로 적던 것 (G→Ab 에 G#)
#  F90 AI 호출 중에 팀을 바꾸면 곡이 다른 팀 라이브러리로 복사되던 것
#  F91 연습 화면에서 다음 곡으로 넘길 때마다 서버 응답을 기다리던 것
#  G20 스스로 나간 멤버가 '인도자가 비활성으로 뒀다' 화면에 갇히던 것
import os, sys, time, json
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
H = {'x-conti': '1'}
tag = str(int(time.time()))[-6:]
def fail(m): print('FAIL:', m); sys.exit(1)

# 헤드리스 크로뮴은 푸시 서비스에 못 붙는다. 권한은 'granted' 로, 구독은 가짜로
PUSH_STUB = r"""
(()=>{
 try{Object.defineProperty(Notification,"permission",{get:()=>"granted",configurable:true})}catch(e){}
 const st={sub:null,n:0};window.__pushst=st;
 const mk=(key)=>{st.n++;const ep='https://example.invalid/push/stub'+Date.now()+'-'+st.n;
   return {endpoint:ep,options:{applicationServerKey:key},
     toJSON(){return {endpoint:ep,keys:{p256dh:'BObJ'+'A'.repeat(83),auth:'x'.repeat(22)}}},
     async unsubscribe(){st.sub=null;return true}}};
 PushManager.prototype.getSubscription=async function(){return st.sub};
 PushManager.prototype.subscribe=async function(o){let k=o.applicationServerKey;
   if(k instanceof Uint8Array)k=k.buffer.slice(k.byteOffset,k.byteOffset+k.byteLength);
   st.sub=mk(k);return st.sub};
})();
"""

def signup(pg, user, name='하은'):
    pg.goto(URL); pg.wait_for_selector('#lgUser', timeout=10000)
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName')
    pg.check('#lgAgree')
    pg.fill('#lgName', name); pg.fill('#lgUser', user); pg.fill('#lgPass', 'secret1')
    pg.click('[data-act="lg-submit"]')

def make_team(pg, name):
    pg.wait_for_selector('#gtTeam', timeout=10000); pg.fill('#gtTeam', name)
    pg.click('[data-act="team-create"]'); pg.wait_for_selector('.shell[data-page]', timeout=10000)

def new_page(b, errs, who, **kw):
    c = b.new_context(viewport=kw.pop('viewport', {'width': 1300, 'height': 950}), **kw)
    pg = c.new_page()
    pg.on('pageerror', lambda e: errs.append(who + ': ' + str(e)))
    pg.on('dialog', lambda d: d.accept())
    return c, pg

# ---------------------------------------------------------------- F25
def t_push_off(b, errs):
    c, pg = new_page(b, errs, 'push', permissions=['notifications'])
    c.add_init_script(PUSH_STUB)
    log = []
    pg.on('request', lambda r: log.append(r.url) if '/api/push/subscribe' in r.url else None)
    signup(pg, 'po' + tag); make_team(pg, '푸시팀')
    pg.wait_for_timeout(4000)   # 홈이 일정·콘티를 받고 몇 번 다시 그려질 때까지
    n1 = len(log)
    if n1 != 1: fail('F25 홈에 한 번 들어왔는데 구독을 %d번 보냄 (한 번이어야)' % n1)
    # 홈을 몇 번 오가도 더 보내지 않는다
    for _ in range(2):
        pg.goto(URL + '#/settings'); pg.wait_for_selector('.setpane', timeout=8000)
        pg.goto(URL + '#/'); pg.wait_for_timeout(1200)
    if len(log) != 1: fail('F25 홈을 다시 그릴 때마다 구독을 또 보냄: %d' % len(log))
    print('F25 홈 구독 한 번만 ok')

    pg.goto(URL + '#/settings'); pg.wait_for_selector('.setpane', timeout=8000)
    pg.click('[data-act="set-tab"][data-t="noti"]'); pg.wait_for_selector('#sPushOff', timeout=5000)
    pg.click('#sPushOff'); pg.wait_for_timeout(1200)
    if pg.evaluate('CONTI.pushState()') != 'off': fail('F25 끈 뒤 상태가 off 가 아님: %s' % pg.evaluate('CONTI.pushState()'))
    if not pg.locator('#sPushOn').count(): fail('F25 끈 뒤 설정에 "알림 켜기"가 없음')
    n2 = len(log)
    pg.goto(URL + '#/'); pg.wait_for_timeout(3500)
    if len(log) != n2: fail('F25 끈 뒤 홈에 오자 다시 구독함')
    if pg.evaluate('!!window.__pushst.sub'): fail('F25 끈 뒤 브라우저 구독이 되살아남')
    # 새로 열어도(새 세션) 꺼진 채로
    pg.reload(); pg.wait_for_selector('.shell[data-page]', timeout=10000); pg.wait_for_timeout(3500)
    if len(log) != n2: fail('F25 다시 열었더니 다시 구독함')
    if pg.evaluate('CONTI.pushState()') != 'off': fail('F25 다시 연 뒤 off 가 풀림')
    print('F25 끄기가 홈·새로 열기 뒤에도 유지 ok')

    # 다시 켜면 구독하고, 그 뒤로는 켜진 상태
    pg.goto(URL + '#/settings'); pg.wait_for_selector('.setpane', timeout=8000)
    pg.click('[data-act="set-tab"][data-t="noti"]'); pg.wait_for_selector('#sPushOn', timeout=5000)
    pg.click('#sPushOn'); pg.wait_for_timeout(1500)
    if len(log) != n2 + 1: fail('F25 다시 켰는데 구독을 안 보냄: %d' % (len(log) - n2))
    if pg.evaluate('CONTI.pushState()') != 'granted': fail('F25 다시 켠 뒤 상태가 granted 가 아님')
    print('F25 다시 켜기 ok')
    c.close()

TESTS = [('F25', t_push_off)]

def run():
    only = set(sys.argv[1:])
    with sync_playwright() as p:
        b = p.chromium.launch(); errs = []
        for name, fn in TESTS:
            if only and name not in only: continue
            fn(b, errs)
        b.close()
    errs = [e for e in errs if 'ResizeObserver' not in e]
    if errs: fail('JS 오류: %s' % errs[:3])
    print('OK')

if __name__ == '__main__':
    run()
