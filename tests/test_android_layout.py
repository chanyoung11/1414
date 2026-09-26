# 안드로이드 앱 화면 배치 검사 — 에뮬레이터 점검(2026-09-27)에서 나온 것 중 '배치' 몫
#
# 사용: CONTI_URL=http://localhost:8766/ .venv/bin/python tests/test_android_layout.py   (개발 서버가 떠 있어야 한다)
#      SOFT=1 이면 실패해도 끝까지 간다 (고치기 전 코드에서 전부 재현해 볼 때)
#
# 앱은 https://localhost 를 흉내 내고(NATIVE) 가짜 Capacitor(getPlatform 'android')를 넣는다. 크롬에는 화면 자판이 없어
# 안드로이드 웹뷰가 하는 두 가지를 흉내 낸다 (에뮬레이터 Pixel 7 · 412x915 · 2.625 에서 잰 값):
#  · 창이 준다: Capacitor SystemBars 가 자판 높이만큼 웹뷰 아래를 비워 창(innerHeight·clientHeight·visualViewport)이 같이
#    915 → 578 로 준다 (가로 411 → 150). → 뷰포트 크기를 줄여 흉내 낸다
#  · 보이는 화면만 준다: 배너 광고가 한 번 뜬 뒤(애드몹이 insets 리스너를 갈아 끼움)에는 창은 그대로이고 visualViewport 만 준다
#    (가로 411 → 150). → visualViewport 를 가짜로 바꿔 흉내 낸다 (offsetTop 0)
# 글자 크기 130%(font_scale 1.3 = 웹뷰 textZoom)는 그려진 글자 크기를 모두 1.3 배로 적어 흉내 낸다.
#
# 본다
#  AND1-13 자판이 뜬 동안(창이 줄어든 안드로이드) 아래 탭바를 숨긴다 — 설정 비밀번호·카포 · 라이브러리 찾기 · 자판을 내리면(뒤로) 다시
#          · 숨긴 동안 본문 아래 여백(--bnavh)은 그대로
#  AND1-14 폰 편성 카드에 '주일 오전예배'가 다 보인다 · 달력 칸·표 머리의 짧은 이름이 낱말 가운데에서 잘리지 않는다 ('주일 오' 아님)
#  AND1-15 홈 '지금 할 일'에 날짜가 두 번 찍히지 않는다 ('10/4 10/4 주일 오전예배' 아님)
#  AND1-16 글자 130%: 일정·편성 머리 기간 '2026.09 – 11' 한 줄 · 설정 '기타 카포' 한 줄 · 가로 넘침 없음
#  AND1-17 안드로이드 설정 > 계정 '연결된 계정' 안내는 보이는 제공자만 ('구글로도') · iOS 는 '구글·애플로도'
#  AND1-18 안드로이드 비밀번호 칸(로그인·가입·계정·계정 삭제)에 보기(눈) 단추 — 누르면 친 값이 보이고 칸의 포커스는 그대로 ·
#          다시 누르면 가린다 · autocomplete 그대로 · iOS·컴퓨터는 단추 없음(그대로)
#  AND2-04 세로 폭 768~820(800dp 태블릿 세로 · 아이패드 820 웹)에서 숨은 탭바 높이를 화면 높이로 잡지 않는다 (--bnavh 0 · 스크롤 없음)
#  AND2-05 폰 가로에서 메모 창을 열고 자판이 뜨면(보이는 150px) 입력 칸이 저장 줄에 가리지 않고 저장 단추도 보인다 (두 흉내 모두)
import os, sys, time, json, datetime
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
SRV = urlparse(URL)
tag = str(int(time.time()))[-7:]
SOFT = os.environ.get('SOFT') == '1'
SHOTS = os.environ.get('SHOTS')   # 이 폴더에 화면을 남긴다 (눈으로 볼 때)
FAILS = []
def fail(m):
  print('FAIL:', m)
  if SOFT: FAILS.append(m); return
  sys.exit(1)

UA_AND = 'Mozilla/5.0 (Linux; Android 16; Pixel 7 Build/BP4A; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/140.0.0.0 Mobile Safari/537.36'
UA_IOS = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148'

MOCK = r"""
(() => {
  const PLAT = '__PLAT__';
  window.Capacitor = {
    getPlatform: () => PLAT, isNativePlatform: () => true, isPluginAvailable: () => false,
    Plugins: {
      StatusBar: { setStyle: () => Promise.resolve(), setBackgroundColor: () => Promise.resolve(), hide: () => Promise.resolve(), show: () => Promise.resolve() },
      App: { addListener: () => Promise.resolve({ remove() {} }), getLaunchUrl: () => Promise.resolve(undefined), exitApp() {}, getInfo: () => Promise.resolve({}) },
      SplashScreen: { hide: () => Promise.resolve() },
      KeepAwake: { keepAwake: () => Promise.resolve(), allowSleep: () => Promise.resolve() },
    },
  };
  try { localStorage.setItem('conti-theme', 'light'); localStorage.setItem('conti-push-asked', '1'); } catch (e) {}
  const safe = () => { const r = document.documentElement; if (r) { r.style.setProperty('--sat', '__SAT__px'); r.style.setProperty('--sab', '__SAB__px'); } };
  safe(); document.addEventListener('readystatechange', safe);
  // ---- 보이는 화면만 주는 자판 (배너가 뜬 뒤의 안드로이드) — 창은 그대로, visualViewport 만 준다 ----
  const vv = new EventTarget(), st = window.__kb = { h: null }, de = () => document.documentElement;
  Object.defineProperty(vv, 'height', { get: () => st.h != null ? st.h : de().clientHeight });
  Object.defineProperty(vv, 'width', { get: () => de().clientWidth });
  Object.defineProperty(vv, 'offsetTop', { get: () => 0 });
  Object.defineProperty(vv, 'offsetLeft', { get: () => 0 });
  Object.defineProperty(vv, 'pageTop', { get: () => window.scrollY });
  Object.defineProperty(vv, 'scale', { get: () => 1 });
  Object.defineProperty(window, 'visualViewport', { configurable: true, get: () => vv });
  const fire = () => { vv.dispatchEvent(new Event('resize')); vv.dispatchEvent(new Event('scroll')); };
  addEventListener('resize', fire);   // 창이 줄면 보이는 화면도 준다
  window.__vvShow = (h) => { st.h = h; fire(); };
  window.__vvHide = () => { st.h = null; fire(); };
})();
"""

# 글자 크기 130% — 그려진 글자 크기를 모두 1.3 배로 (웹뷰 textZoom 흉내)
ZOOM = """(()=>{const els=[...document.querySelectorAll('#app *')];const fs=els.map(e=>parseFloat(getComputedStyle(e).fontSize));
  els.forEach((e,i)=>e.style.setProperty('font-size',(fs[i]*1.3)+'px','important'))})()"""
# 한 요소 안 글(바로 밑 글 마디)이 몇 줄로 그려졌나
LINES = """(el)=>{const tops=new Set();for(const n of el.childNodes){if(n.nodeType!==3||!n.textContent.trim())continue;const r=document.createRange();r.selectNodeContents(n);
  for(const b of r.getClientRects())if(b.width>1)tops.add(Math.round(b.top))}return tops.size}"""

# 연습 화면 준비: 콘티 초안에 유튜브 영상이 달린 곡 하나 (이 기기에만)
ADD_ITEM = """(()=>{const sv=CONTI.S.services.find(s=>!s.items.length)||CONTI.S.services[0];
  sv.items.push({id:'andi1',title:'Afresh',key:'G',mod:'',form:'A – B',songNote:'',pieces:[],media:[{id:'andm1',type:'youtube',url:'https://youtu.be/dQw4w9WgXcQ',name:'',start:0,end:0,notes:[],sessions:[]}],notes:[]});
  sv.updatedAt=Date.now();CONTI.save();return sv.id})()"""

def run():
  with sync_playwright() as p:
    b = p.chromium.launch(); errs = []

    def handler(route):
      u = urlparse(route.request.url)
      if u.scheme == 'https' and u.hostname in ('localhost', 'lets1414.com', 'www.lets1414.com') and u.port is None:
        if u.path == '/api/auth/social' and route.request.method == 'GET' and SOCIAL.get('fake'):
          # 연결된 계정: 구글·애플 모두 켜진 서버 (로컬 서버에는 키가 없다)
          return route.fulfill(status=200, content_type='application/json', body=json.dumps({'linked': [], 'hasPassword': True, 'available': {'google': True, 'apple': True}}))
        try: return route.fulfill(response=route.fetch(url='%s://%s/%s' % (SRV.scheme, SRV.netloc, u.path.lstrip('/')) + ('?' + u.query if u.query else '')))
        except Exception:
          try: return route.abort()
          except Exception: return
      if u.hostname == SRV.hostname and u.port == SRV.port: return route.continue_()
      return route.abort()   # 바깥(글꼴 CDN·유튜브)은 막는다
    SOCIAL = {'fake': True}

    def native(plat, vw, vh, sat=24, sab=24, state=None, dsf=2.625, sw=None, sh=None):
      c = b.new_context(viewport={'width': vw, 'height': vh}, screen={'width': sw or vw, 'height': sh or vh}, device_scale_factor=dsf,
                        is_mobile=True, has_touch=True, user_agent=UA_AND if plat == 'android' else UA_IOS, service_workers='block', storage_state=state)
      c.route('**/*', handler)
      c.add_init_script(MOCK.replace('__PLAT__', plat).replace('__SAT__', str(sat)).replace('__SAB__', str(sab)))
      pg = c.new_page(); pg.on('pageerror', lambda e: errs.append('%s: %s' % (plat, e))); pg.on('dialog', lambda d: d.accept())
      pg.goto('https://localhost/')
      return c, pg

    def api(pg, method, path, body=None):
      return pg.evaluate("""async([m,p,b])=>{const t=localStorage.getItem('conti-app-token')||'';const r=await fetch('https://lets1414.com/api'+p,{method:m,credentials:'include',
        headers:{'x-conti':'1','x-conti-app':'1','content-type':'application/json',...(t?{authorization:'Bearer '+t}:{})},body:b?JSON.stringify(b):undefined});
        let j=null;try{j=await r.json()}catch(e){}return {status:r.status,j}}""", [method, path, body])

    def shot(pg, name):
      if SHOTS: os.makedirs(SHOTS, exist_ok=True); pg.screenshot(path=os.path.join(SHOTS, name + '.png'))
    def nav_hidden(pg): return pg.evaluate("(()=>{const n=document.querySelector('#app .bnav');return !n||n.getClientRects().length===0})()")
    def closeall(pg):
      for _ in range(3):
        if pg.locator('#modal .ov').count(): pg.evaluate("CONTI.closeModal()"); pg.wait_for_timeout(300)

    # ================= 안드로이드 폰 (412x915) =================
    W, H = 412, 915
    c, pg = native('android', W, H)
    pg.wait_for_selector('#lgUser', timeout=15000); pg.wait_for_timeout(300)

    # ---- AND1-18 로그인 비밀번호 칸의 보기 단추 ----
    def eye_check(sel, label, focus_first=True):
      ok = pg.evaluate("(s)=>{const i=document.querySelector(s);const e=i&&i.parentElement.querySelector('.pweye');return !!e}", sel)
      if not ok: fail('AND1-18 %s 비밀번호 칸(%s)에 보기(눈) 단추가 없음' % (label, sel)); return
      if focus_first: pg.tap(sel)
      pg.fill(sel, 'Secret12')
      ac0 = pg.evaluate("(s)=>document.querySelector(s).getAttribute('autocomplete')", sel)
      pg.tap('%s ~ .pweye' % sel); pg.wait_for_timeout(150)
      shot(pg, 'eye_' + sel.strip('#'))
      s1 = pg.evaluate("(s)=>{const i=document.querySelector(s),e=i.parentElement.querySelector('.pweye');return {type:i.type,val:i.value,focus:document.activeElement===i,pressed:e.getAttribute('aria-pressed'),ac:i.getAttribute('autocomplete'),"
                       "in:(()=>{const a=i.getBoundingClientRect(),q=e.getBoundingClientRect();return q.left>=a.left&&q.right<=a.right+1&&q.top>=a.top-1&&q.bottom<=a.bottom+1})()}}", sel)
      pg.tap('%s ~ .pweye' % sel); pg.wait_for_timeout(150)
      s2 = pg.evaluate("(s)=>{const i=document.querySelector(s);return {type:i.type,focus:document.activeElement===i}}", sel)
      if s1['type'] != 'text' or s1['val'] != 'Secret12' or s1['pressed'] != 'true': fail('AND1-18 %s 눈 단추를 눌러도 친 값이 안 보임: %s' % (label, s1))
      elif focus_first and not s1['focus']: fail('AND1-18 %s 눈 단추를 누르니 칸의 포커스(자판)가 빠짐: %s' % (label, s1))
      elif s1['ac'] != ac0: fail('AND1-18 %s autocomplete 가 바뀜 %s → %s' % (label, ac0, s1['ac']))
      elif not s1['in']: fail('AND1-18 %s 눈 단추가 칸 안(오른쪽)에 있지 않음: %s' % (label, s1))
      elif s2['type'] != 'password': fail('AND1-18 %s 다시 눌러도 가려지지 않음: %s' % (label, s2))
      else: print('AND1-18 %s 눈 단추 보기·가리기 ok' % label, s1)
    eye_check('#lgPass', '로그인')

    # ---- 가입 (가입 칸에도 눈) ----
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName'); pg.check('#lgAgree')
    eye_check('#lgPass', '가입')
    pg.fill('#lgName', '안드'); pg.fill('#lgUser', 'and' + tag); pg.fill('#lgPass', 'secret12'); pg.click('[data-act="lg-submit"]')
    pg.wait_for_selector('#gtTeam', timeout=15000); pg.fill('#gtTeam', '안드팀' + tag); pg.click('[data-act="team-create"]')
    pg.wait_for_selector('.shell[data-page]', timeout=15000); pg.wait_for_timeout(600); closeall(pg)
    team = pg.evaluate('CONTI.S.team.id')

    # 정기 예배 '주일 오전예배' → 날짜와 콘티 초안이 생긴다 (이름 규칙 기본값 '{월}/{일} {이름}')
    r = api(pg, 'POST', '/teams/%s/recurring' % team, {'weekday': 0, 'label': '주일 오전예배', 'time': '11:00'})
    if r['status'] != 200: fail('정기 예배 만들기 실패: %s' % r)
    pg.evaluate("async()=>{await CONTI.SYNC.pullServices();await CONTI.pullSchedule(null,true);CONTI.render()}"); pg.wait_for_timeout(800)

    # ---- AND1-15 '지금 할 일' 날짜 두 번 ----
    titles = pg.evaluate("CONTI.todoCards().map(c=>c.title||'')")
    dup = [t for t in titles if len(t.split(' ')) > 1 and t.split(' ')[0] == t.split(' ')[1]]
    empty = [t for t in titles if '콘티가 비어 있어요' in t]
    if not empty: fail('AND1-15 준비: 빈 콘티 카드가 없음 %s' % titles)
    elif dup: fail('AND1-15 지금 할 일에 날짜가 두 번: %s' % dup[:2])
    elif not all('주일 오전예배' in t for t in empty): fail('AND1-15 카드 이름이 빠짐: %s' % empty[:2])
    else: print('AND1-15 지금 할 일 제목 ok', empty[0])
    # 홈 화면에 그려진 글에서도
    pg.evaluate("()=>{location.hash='#/home'}"); pg.wait_for_timeout(700)
    txt = pg.evaluate("document.querySelector('#app').innerText")
    import re
    m = re.search(r'(\d{1,2}/\d{1,2}) \1 ', txt)
    if m: fail('AND1-15 홈 화면에 날짜 두 번: %r' % m.group(0))

    # ---- AND1-14 폰 편성 카드 · 달력 칸 이름 ----
    pg.evaluate("()=>{location.hash='#/sched'}"); pg.wait_for_selector('.schrow', timeout=10000); pg.wait_for_timeout(400)
    s = pg.evaluate("(()=>{const b=document.querySelector('.schrow .grow b');return {t:b.textContent,sw:b.scrollWidth,cw:b.clientWidth,w:Math.round(b.getBoundingClientRect().width)}})()")
    shot(pg, 'sched_card')
    if s['t'] != '주일 오전예배': fail('AND1-14 폰 편성 카드 이름이 잘림: %s' % s)
    elif s['sw'] > s['cw'] + 1: fail('AND1-14 폰 편성 카드 이름이 칸을 넘침(말줄임 없음): %s' % s)
    else: print('AND1-14 폰 편성 카드 이름 ok', s)
    pg.evaluate("()=>{location.hash='#/cal'}"); pg.wait_for_selector('.cal-cell .lb', timeout=10000); pg.wait_for_timeout(300)
    lb = pg.evaluate("(()=>{const e=document.querySelector('.cal-cell .lb');return {t:e.textContent,sw:e.scrollWidth,cw:e.clientWidth}})()")
    if lb['t'] in ('주일 오', '주일 '): fail('AND1-14 달력 칸 이름이 낱말 가운데에서 잘림: %s' % lb)
    elif lb['sw'] > lb['cw'] + 1: fail('AND1-14 달력 칸 이름이 칸을 넘침: %s' % lb)
    else: print('AND1-14 달력 칸 이름 ok', lb)

    # ---- AND1-17 연결된 계정 안내 ----
    pg.evaluate("()=>{location.hash='#/settings'}"); pg.wait_for_selector('[data-act="set-tab"][data-t="account"]', timeout=8000)
    pg.click('[data-act="set-tab"][data-t="account"]'); pg.wait_for_selector('#linkList .linkrow', timeout=8000); pg.wait_for_timeout(200)
    k = pg.evaluate("(()=>{const c=document.getElementById('linkCard');return {hint:c.querySelector('.hint').textContent,rows:[...c.querySelectorAll('.linkrow b')].map(x=>x.textContent)}})()")
    shot(pg, 'account')
    if k['rows'] != ['구글']: fail('AND1-17 준비: 안드로이드 연결 줄이 구글만이 아님 %s' % k)
    elif '애플' in k['hint'] or 'Apple' in k['hint'] or not k['hint'].startswith('구글로도'): fail('AND1-17 안드로이드 연결 안내에 없는 제공자가 나옴: %s' % k)
    else: print('AND1-17 안드로이드 연결 안내 ok', k)

    # ---- AND1-18 계정 비밀번호 칸 ----
    eye_check('#sPw0', '계정 현재 비밀번호'); eye_check('#sPw1', '계정 새 비밀번호')
    pg.fill('#sPw0', ''); pg.fill('#sPw1', '')
    pg.evaluate("document.activeElement&&document.activeElement.blur()"); pg.wait_for_timeout(200)

    # ---- AND1-13 자판이 뜬 동안(창이 줄어듦) 탭바 숨김 ----
    KBH = 578
    def kb_case(sel, label, prep=None):
      if prep: prep()
      if nav_hidden(pg): fail('AND1-13 준비: %s 자판 전인데 탭바가 숨음' % label); return
      bh0 = pg.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--bnavh').trim()")
      pg.tap(sel); pg.wait_for_timeout(120)
      pg.set_viewport_size({'width': W, 'height': KBH}); pg.wait_for_timeout(450)
      s = pg.evaluate("(()=>{const de=document.documentElement;return {ih:innerHeight,ae:document.activeElement&&document.activeElement.id,cls:de.className,bh:getComputedStyle(de).getPropertyValue('--bnavh').trim()}})()")
      hid = nav_hidden(pg); shot(pg, 'kb_' + sel.strip('#'))
      # 뒤로(자판만 내림): 칸에 포커스는 남은 채 창이 돌아온다
      pg.set_viewport_size({'width': W, 'height': H}); pg.wait_for_timeout(450)
      back = nav_hidden(pg)
      pg.evaluate("document.activeElement&&document.activeElement.blur()"); pg.wait_for_timeout(200)
      if not hid: fail('AND1-13 %s 자판이 뜬 동안 탭바가 자판 위에 남음: %s' % (label, s))
      elif s['bh'] != bh0: fail('AND1-13 %s 탭바를 숨긴 동안 본문 아래 여백(--bnavh)이 바뀜 %s → %s' % (label, bh0, s['bh']))
      elif back: fail('AND1-13 %s 자판을 내렸는데(포커스는 남음) 탭바가 안 돌아옴' % label)
      elif nav_hidden(pg): fail('AND1-13 %s 칸을 떠났는데 탭바가 안 돌아옴' % label)
      else: print('AND1-13 %s 자판 동안 탭바 숨김 ok' % label, s)
    kb_case('#sPw0', '설정 계정 비밀번호')
    def to_profile():
      pg.click('[data-act="set-tab"][data-t="profile"]'); pg.wait_for_selector('#sCapo'); pg.wait_for_timeout(200)
    kb_case('#sCapo', '설정 기타 카포', to_profile)
    def to_lib():
      pg.evaluate("()=>{location.hash='#/library'}"); pg.wait_for_timeout(900)
    to_lib()
    if pg.locator('#libQ').count(): kb_case('#libQ', '라이브러리 찾기')
    else: fail('AND1-13 준비: 라이브러리 찾기 칸(#libQ)이 없음')

    # ---- AND1-16 글자 130% ----
    pg.evaluate("()=>{location.hash='#/cal'}"); pg.wait_for_selector('.cal-cell', timeout=10000); pg.wait_for_timeout(400)
    pg.evaluate(ZOOM); pg.wait_for_timeout(150)
    def period_lines():
      return pg.evaluate("(L)=>{const b=[...document.querySelectorAll('#app main b')].find(x=>/^\\d{4}\\.\\d{2} –/.test(x.textContent));const f=new Function('return '+L)();return b?{t:b.textContent,n:f(b),sw:document.documentElement.scrollWidth}:null}", LINES)
    s = period_lines(); shot(pg, 'zoom_cal')
    if not s: fail('AND1-16 준비: 일정 머리 기간을 못 찾음')
    elif s['n'] != 1: fail('AND1-16 일정 머리 기간이 %d줄로 꺾임: %s' % (s['n'], s))
    elif s['sw'] > W + 1: fail('AND1-16 일정 화면이 가로로 넘침: %s' % s)
    else: print('AND1-16 일정 기간 한 줄 ok', s)
    pg.evaluate("()=>{location.hash='#/sched'}"); pg.wait_for_selector('.schrow', timeout=10000); pg.wait_for_timeout(400)
    pg.evaluate(ZOOM); pg.wait_for_timeout(150)
    s = period_lines(); shot(pg, 'zoom_sched')
    if not s or s['n'] != 1: fail('AND1-16 편성 머리 기간이 한 줄이 아님: %s' % s)
    elif s['sw'] > W + 1: fail('AND1-16 편성 화면이 가로로 넘침: %s' % s)
    else: print('AND1-16 편성 기간 한 줄 ok', s)
    pg.evaluate("()=>{location.hash='#/settings'}"); pg.wait_for_timeout(300)
    pg.click('[data-act="set-tab"][data-t="profile"]'); pg.wait_for_selector('#sCapo'); pg.wait_for_timeout(200)
    pg.evaluate(ZOOM); pg.wait_for_timeout(150); shot(pg, 'zoom_profile')
    s = pg.evaluate("(L)=>{const l=[...document.querySelectorAll('#app .lbl')].find(x=>/기타 카포/.test(x.textContent));const f=new Function('return '+L)();return {n:f(l),sw:document.documentElement.scrollWidth,h:Math.round(l.querySelector('.hint').getBoundingClientRect().width)}}", LINES)
    if s['n'] != 1: fail('AND1-16 설정 "기타 카포" 라벨이 %d줄로 꺾임: %s' % (s['n'], s))
    elif s['sw'] > W + 1: fail('AND1-16 설정 화면이 가로로 넘침: %s' % s)
    else: print('AND1-16 설정 기타 카포 한 줄 ok', s)
    # 글자 100% 로 되돌린다 (다시 그리면 인라인 크기가 사라진다)
    pg.evaluate("()=>{location.hash='#/home'}"); pg.wait_for_timeout(400)

    # ---- AND2-05 폰 가로 메모 창 (자판 위 150px) ----
    state = c.storage_state()
    c.close()
    LW, LH, LVIS = 915, 411, 150
    def land_case(mode):
      c2, p2 = native('android', LW, LH, sat=32, sab=0, state=state, sw=LW, sh=LH)
      p2.wait_for_selector('.shell[data-page]', timeout=15000); p2.wait_for_timeout(500)
      for _ in range(3):
        if p2.locator('#modal .ov').count(): p2.evaluate("CONTI.closeModal()"); p2.wait_for_timeout(300)
      sid = p2.evaluate(ADD_ITEM)
      p2.evaluate("(s)=>{location.hash='#/play/'+s+'/0'}", sid); p2.wait_for_selector('[data-act="tnote"]', timeout=10000); p2.wait_for_timeout(600)
      p2.evaluate("document.querySelector('[data-act=\"tnote\"]').click()"); p2.wait_for_selector('#cText', timeout=6000); p2.wait_for_timeout(300)
      if mode == 'vv': p2.evaluate("(h)=>window.__vvShow(h)", LVIS)
      else: p2.set_viewport_size({'width': LW, 'height': LVIS})
      p2.wait_for_timeout(700)
      # 웹뷰는 자판이 뜬 뒤 커서 칸을 보이는 화면 가운데로 올린다(에뮬레이터: 칸 가운데 93 ≈ 보이는 시트 가운데) — 앱이 맞춘 뒤에 온다
      p2.evaluate("document.getElementById('cText').scrollIntoView({block:'center'})"); p2.wait_for_timeout(200)
      k = p2.evaluate("""(()=>{const vis=visualViewport.height;const r=e=>{const b=e.getBoundingClientRect();return [Math.round(b.top),Math.round(b.bottom),Math.round(b.left),Math.round(b.right)]};
        const hit=e=>{const b=e.getBoundingClientRect();if(b.bottom<=0||b.top>=vis||!b.width)return false;const y=Math.max(b.top+2,Math.min(b.bottom-2,(b.top+b.bottom)/2));const x=(b.left+b.right)/2;const h=document.elementFromPoint(x,y);return !!h&&(h===e||e.contains(h))};
        const inp=document.getElementById('cText');const saves=[...document.querySelectorAll('#modal button')].filter(x=>/저장/.test(x.textContent)&&x.offsetParent);
        const sv=saves.find(x=>{const b=x.getBoundingClientRect();return b.top>=0&&b.bottom<=vis&&hit(x)});
        return {vis,ae:document.activeElement&&document.activeElement.id,inp:r(inp),inpHit:hit(inp),inpIn:r(inp)[0]>=0&&r(inp)[1]<=vis,save:sv?r(sv):null,cls:document.documentElement.className}})()""")
      p2.keyboard.type('land test'); p2.wait_for_timeout(150); shot(p2, 'land_' + mode)
      typed = p2.evaluate("document.getElementById('cText').value")
      if k['ae'] != 'cText': fail('AND2-05 [%s] 준비: 메모 칸에 커서가 없음 %s' % (mode, k))
      elif not (k['inpIn'] and k['inpHit']): fail('AND2-05 [%s] 폰 가로 자판 위 150px 에서 메모 칸이 가려짐(저장 줄 밑·화면 밖): %s' % (mode, k))
      elif not k['save']: fail('AND2-05 [%s] 폰 가로 자판 위에 저장 단추가 안 보임: %s' % (mode, k))
      elif typed != 'land test': fail('AND2-05 [%s] 친 글이 칸에 안 들어감: %r' % (mode, typed))
      else: print('AND2-05 [%s] 폰 가로 메모 칸·저장 보임 ok' % mode, k)
      # 칸 옆 저장으로 저장된다
      if k['save']:
        p2.evaluate("""(()=>{const vis=visualViewport.height;const b=[...document.querySelectorAll('#modal button')].find(x=>{if(!/저장/.test(x.textContent)||!x.offsetParent)return false;const q=x.getBoundingClientRect();return q.top>=0&&q.bottom<=vis});b.click()})()""")
        p2.wait_for_timeout(400)
        if p2.locator('#modal .ov').count(): fail('AND2-05 [%s] 보이는 저장을 눌러도 메모 창이 안 닫힘' % mode)
      c2.close()
    land_case('vv'); land_case('win')

    # ---- AND2-04 800dp 태블릿 세로 (1280) · 아이패드 820 웹 ----
    def tall_case(label, plat, vw, vh):
      if plat:
        c3, p3 = native(plat, vw, vh, sat=24, sab=24, state=state, dsf=2)
        p3.wait_for_selector('.shell[data-page]', timeout=15000)
      else:
        c3 = b.new_context(viewport={'width': vw, 'height': vh}, is_mobile=True, has_touch=True, device_scale_factor=2, service_workers='block')
        p3 = c3.new_page(); p3.on('pageerror', lambda e: errs.append('web: %s' % e)); p3.on('dialog', lambda d: d.accept())
        p3.goto(URL); p3.wait_for_selector('#lgUser', timeout=15000)
        p3.fill('#lgUser', 'and' + tag); p3.fill('#lgPass', 'secret12'); p3.click('[data-act="lg-submit"]'); p3.wait_for_selector('.shell[data-page]', timeout=15000)
      p3.wait_for_timeout(600)
      for _ in range(3):
        if p3.locator('#modal .ov').count(): p3.evaluate("CONTI.closeModal()"); p3.wait_for_timeout(300)
      for page in ('home', 'settings'):
        p3.evaluate("(r)=>{location.hash='#/'+r}", page); p3.wait_for_timeout(700)
        s = p3.evaluate("(()=>{const m=document.querySelector('#app main');return {bh:getComputedStyle(document.documentElement).getPropertyValue('--bnavh').trim(),pb:getComputedStyle(m).paddingBottom,sh:document.scrollingElement.scrollHeight,ih:innerHeight,nav:(document.querySelector('#app .bnav')||{getClientRects:()=>[]}).getClientRects().length}})()")
        if s['nav'] == 0 and s['bh'] not in ('0px', ''): fail('AND2-04 %s %s: 숨은 탭바 높이를 %s 로 잡음 (본문 아래 여백 %s)' % (label, page, s['bh'], s['pb']))
        elif s['nav'] == 0 and float(s['pb'].replace('px', '')) > 200: fail('AND2-04 %s %s: 본문 아래 여백이 큼 %s' % (label, page, s))
        else: print('AND2-04 %s %s ok' % (label, page), s)
      c3.close()
    tall_case('안드로이드 800dp 태블릿 세로', 'android', 800, 1280)
    tall_case('아이패드 820 웹 세로', None, 820, 1180)

    # ---- 폰 탭바 여백은 그대로 ----
    c4, p4 = native('android', W, H, state=state)
    p4.wait_for_selector('.shell[data-page]', timeout=15000); p4.wait_for_timeout(600)
    bh = p4.evaluate("parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--bnavh'))")
    if not (40 <= bh <= 120): fail('폰 탭바 높이(--bnavh)가 이상함: %s' % bh)
    else: print('폰 --bnavh %s ok' % bh)
    c4.close()

    # ================= iOS·컴퓨터 — 그대로 =================
    SOCIAL['fake'] = True
    c5, p5 = native('ios', 402, 874, sat=62, sab=34, state=state, dsf=3)
    p5.wait_for_selector('.shell[data-page]', timeout=15000); p5.wait_for_timeout(500)
    for _ in range(3):
      if p5.locator('#modal .ov').count(): p5.evaluate("CONTI.closeModal()"); p5.wait_for_timeout(300)
    p5.evaluate("()=>{location.hash='#/settings'}"); p5.wait_for_selector('[data-act="set-tab"][data-t="account"]', timeout=8000)
    p5.click('[data-act="set-tab"][data-t="account"]'); p5.wait_for_selector('#linkList .linkrow', timeout=8000); p5.wait_for_timeout(200)
    k = p5.evaluate("(()=>{const c=document.getElementById('linkCard');return {hint:c.querySelector('.hint').textContent,rows:[...c.querySelectorAll('.linkrow b')].map(x=>x.textContent),eye:document.querySelectorAll('.pweye').length}})()")
    if not k['hint'].startswith('구글·애플로도'): fail('AND1-17 iOS 연결 안내가 바뀜: %s' % k)
    elif k['eye']: fail('AND1-18 iOS 비밀번호 칸에 눈 단추가 생김(그대로여야): %s' % k)
    else: print('iOS 연결 안내·비밀번호 칸 그대로 ok', k)
    # iOS 자판 흉내(보이는 화면만 줄어듦)로 kbup·탭바 숨김은 전처럼
    p5.evaluate("()=>{location.hash='#/settings'}"); p5.wait_for_timeout(200)
    p5.click('[data-act="set-tab"][data-t="profile"]'); p5.wait_for_selector('#sCapo')
    p5.tap('#sCapo'); p5.evaluate("(h)=>window.__vvShow(h)", 874 - 380); p5.wait_for_timeout(400)
    s = p5.evaluate("(()=>{const de=document.documentElement;return {up:de.classList.contains('kbup'),tight:de.classList.contains('kbtight'),nav:(document.querySelector('#app .bnav')||{getClientRects:()=>[]}).getClientRects().length}})()")
    if not s['up'] or s['nav'] or s['tight']: fail('iOS 자판 동안 kbup·탭바 숨김이 전과 다름: %s' % s)
    else: print('iOS 자판 kbup 그대로 ok', s)
    c5.close()

    c6 = b.new_context(viewport={'width': 1300, 'height': 900}, service_workers='block')
    p6 = c6.new_page(); p6.on('pageerror', lambda e: errs.append('web: %s' % e))
    p6.goto(URL); p6.wait_for_selector('#lgUser', timeout=15000); p6.wait_for_timeout(300)
    n = p6.evaluate("document.querySelectorAll('.pweye').length")
    if n: fail('AND1-18 컴퓨터 로그인 비밀번호 칸에 눈 단추가 생김(그대로여야)')
    p6.click('#lgPass'); p6.set_viewport_size({'width': 1300, 'height': 500}); p6.wait_for_timeout(300)
    cls = p6.evaluate("document.documentElement.className")
    if 'kbnav' in cls or 'kbup' in cls or 'kbtight' in cls: fail('컴퓨터 웹에서 창을 줄이니 자판 처리가 켜짐: %s' % cls)
    else: print('컴퓨터 웹 그대로 ok', cls)
    c6.close()
    b.close()
    bad = [e for e in errs if 'ResizeObserver' not in e]
    if bad: fail('페이지 오류: %s' % bad[:3])
  if FAILS:
    print('\n%d개 실패' % len(FAILS)); sys.exit(1)
  print('OK test_android_layout')

if __name__ == '__main__':
  run()
