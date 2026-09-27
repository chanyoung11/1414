# 안드로이드 앱 껍데기 검사 — 에뮬레이터(Pixel 7, API 37) 점검(2026-09-27)에서 나온 '네이티브' 몫
#
# 사용: CONTI_URL=http://localhost:8766/ .venv/bin/python tests/test_android_native.py   (개발 서버가 떠 있어야 한다)
#      SOFT=1 이면 실패해도 끝까지 간다
#
# 앱은 https://localhost 를 흉내 내고(NATIVE) 안드로이드 웹뷰 UA 와 가짜 Capacitor(App·StatusBar·Printer·Share)를 넣는다.
# 네이티브 쪽(자바·매니페스트)은 정적으로 본다 — 에뮬레이터에서 직접 본 것은 커밋 메시지·보고에 있다.
#
# 본다
#  AND1-01 뒤로 키 = 화면 안의 '<': 곡 상세 → 라이브러리 · 편성 패널 → 편성 탭 · 설정에서 연 약관 → 설정(앱 탭) ·
#          팀 없이 연 초대 가입 화면은 초대를 지킨 채 앱만 내림 · 비밀번호 재설정 → 로그인
#  AND1-02 첫 화면(홈·로그인·팀 만들기)에서 뒤로 = minimizeApp (exitApp 아님) · 친 팀 이름이 남는다
#  AND1-03/AND2-08 돌리기·다크 모드·글자 크기 뒤 상태바 모양을 되돌림 (MainActivity.onConfigurationChanged) — 정적
#  AND1-05 로그인 전 안드로이드는 첫 그리기 전부터 바탕이 로그인 색(html.preauth) · 켜는 동안 resize 에 떼지 않음 ·
#          상태바는 먼저 DARK · 창 바탕(windowBackground)도 스플래시 색 · iOS·웹은 그대로
#  AND1-06 confirm·alert·prompt 한국어 단추 (MainActivity.KoreanDialogs) — 정적
#  AND1-09 configChanges 에 fontScale · 웹뷰 textZoom 을 새 글자 크기로 — 정적
#  AND2-01 인쇄에 orient·paper 를 넘기고 안드로이드는 그대로 용지·방향(MediaSize)·여백 0 으로 연다 — 넘기는 값 + 정적
#  AND2-02 인쇄 창이 닫힐 때(done)까지 조판(nprint)을 남기고, 닫히면 바로 뗌 · 창이 떠 있는 동안 앱이 얼지 않게
#          짧은 포그라운드 서비스(PrintKeepAlive, shortService) — 정적
#  AND2-06 파일 내보내기는 '기기에 저장'·'보내기' 중 고름 · 녹음 '기기에 저장'은 곧바로 저장 위치 고르기(saveToDevice)
#  AND2-10 마이크를 거절(NotAllowedError)하면 설정에서 켜는 길 + '설정 열기'(Printer.openAppSettings) · iOS 는 전처럼 토스트
import os, sys, time, json, re, datetime
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
SRV = urlparse(URL)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
tag = str(int(time.time()))[-7:]
SOFT = os.environ.get('SOFT') == '1'
FAILS = []
def fail(m):
  print('FAIL:', m)
  if SOFT: FAILS.append(m); return
  sys.exit(1)

UA_ANDROID = 'Mozilla/5.0 (Linux; Android 16; Pixel 7 Build/CP31; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/151.0.0.0 Mobile Safari/537.36'
UA_IOS = 'Mozilla/5.0 (iPhone; CPU iPhone OS 26_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148'

MOCK = r"""
(() => {
  const cap = window.__cap = { style: [], min: 0, exit: 0, prints: [], saves: [], dev: [], shares: [], settings: 0, listeners: {}, boot: {} };
  const P = (v) => Promise.resolve(v);
  window.Capacitor = {
    getPlatform: () => '__PLATFORM__', isNativePlatform: () => true, isPluginAvailable: () => false,
    Plugins: {
      StatusBar: { setStyle: (o) => { cap.style.push(o.style); return P(); }, setBackgroundColor: () => P(), hide: () => P(), show: () => P() },
      Share: { share: (o) => { cap.shares.push(o); return P({}); }, canShare: () => P({ value: true }) },
      App: { addListener: (ev, cb) => { cap.listeners[ev] = cb; return P({ remove() {} }); }, getLaunchUrl: () => P(undefined),
             exitApp: () => { cap.exit++; return P(); }, minimizeApp: () => { cap.min++; return P(); }, getInfo: () => P({}) },
      SplashScreen: { hide: () => P() },
      KeepAwake: { keepAwake: () => P(), allowSleep: () => P() },
      Printer: {
        setWindowBackground: () => P(),
        // 안드로이드는 인쇄 창이 닫힐 때 답한다 (__cap.finishPrint). iOS 는 곧바로 {completed}
        print: (o) => { cap.prints.push({ o, nprint: document.body.classList.contains('nprint') });
          return '__PLATFORM__' === 'android' ? new Promise((r) => { cap.finishPrint = () => r({ done: true }); }) : P({ completed: true }); },
        saveFile: (o) => { cap.saves.push({ name: o.name, append: !!o.append }); return P({ uri: 'file:///cache/exports/' + o.name }); },
        saveBytes: (o) => { cap.saves.push({ name: o.name, append: !!o.append, bytes: true }); return P({ uri: 'file:///cache/exports/' + o.name }); },
        saveToDevice: (o) => { cap.dev.push(o.name); return P({ saved: true }); },
        openAppSettings: () => { cap.settings++; return P(); },
      },
    },
  };
  try { localStorage.setItem('conti-push-asked', '1'); } catch (e) {}
  // 켜는 동안: 첫 그리기 전 html 클래스·바탕, 그리기 전에 창 크기가 바뀌어도(resize) 남는지
  document.addEventListener('DOMContentLoaded', () => {
    const h = document.documentElement;
    cap.boot.dcl = { cls: h.className, bg: getComputedStyle(h).backgroundColor, app: !!document.getElementById('app').firstChild };
    setTimeout(() => { dispatchEvent(new Event('resize'));
      requestAnimationFrame(() => requestAnimationFrame(() => { cap.boot.afterResize = { cls: h.className, app: !!document.getElementById('app').firstChild }; })); }, 30);
  });
})();
"""

def read(p): return open(os.path.join(ROOT, p), encoding='utf-8').read()

def static_checks():
  man = read('android/app/src/main/AndroidManifest.xml')
  cc = re.search(r'android:configChanges="([^"]+)"', man).group(1).split('|')
  if 'fontScale' not in cc: fail('AND1-09 MainActivity configChanges 에 fontScale 이 없음 (글자 크기를 바꾸면 앱이 다시 불러와짐): %s' % cc)
  for need in ['orientation', 'screenSize', 'uiMode']:
    if need not in cc: fail('configChanges 에서 %s 가 빠짐' % need)
  if not re.search(r'<service[^>]*\.PrintKeepAlive[^>]*foregroundServiceType="shortService"', man, re.S) and \
     not re.search(r'<service[^>]*foregroundServiceType="shortService"[^>]*\.PrintKeepAlive', man, re.S):
    fail('AND2-02 매니페스트에 PrintKeepAlive(shortService) 서비스가 없음')
  if 'android.permission.FOREGROUND_SERVICE"' not in man: fail('AND2-02 FOREGROUND_SERVICE 권한이 없음')
  ma = read('android/app/src/main/java/com/lets1414/app/MainActivity.java')
  for need, why in [('onConfigurationChanged', 'AND1-03 설정 바뀜 처리'), ('isAppearanceLightStatusBars()', 'AND1-03 바뀌기 전 상태바 모양 기억'),
                    ('setAppearanceLightStatusBars(lightStatus)', 'AND1-03 상태바 모양 되돌림'), ('decor.setBackground(bg)', 'AND1-03 창 바탕 되돌림'),
                    ('setTextZoom', 'AND1-09 글자 크기 → 웹뷰 확대'), ('class KoreanDialogs extends BridgeWebChromeClient', 'AND1-06 한국어 확인 창'),
                    ('"확인"', 'AND1-06 확인 단추'), ('"취소"', 'AND1-06 취소 단추'), ('onJsConfirm', 'AND1-06 confirm'), ('onJsAlert', 'AND1-06 alert'),
                    ('onJsPrompt', 'AND1-06 prompt'), ('setWebChromeClient(new KoreanDialogs(bridge))', 'AND1-06 웹뷰에 붙임')]:
    if need not in ma: fail('%s 없음: %s' % (why, need))
  if re.search(r'set(Positive|Negative)Button\("(OK|Cancel)"', ma): fail('AND1-06 MainActivity 에 영어 단추가 남음')
  # super.onConfigurationChanged 앞에서 기억하고 뒤에서 되돌려야 한다
  i_save, i_super, i_restore = ma.find('isAppearanceLightStatusBars()'), ma.find('super.onConfigurationChanged'), ma.find('setAppearanceLightStatusBars(lightStatus)')
  if not (0 <= i_save < i_super < i_restore): fail('AND1-03 상태바 모양을 super.onConfigurationChanged 앞에서 기억하고 뒤에서 되돌려야 함')
  pp = read('android/app/src/main/java/com/lets1414/app/PrinterPlugin.java')
  for need, why in [('call.getString("orient")', 'AND2-01 방향 읽기'), ('call.getString("paper")', 'AND2-01 용지 읽기'),
                    ('MediaSize.ISO_A4', 'AND2-01 A4'), ('MediaSize.NA_LETTER', 'AND2-01 Letter'), ('asLandscape()', 'AND2-01 가로'),
                    ('Margins.NO_MARGINS', 'AND2-01 여백 0'), ('PrintKeepAlive.start', 'AND2-02 인쇄 창 동안 깨워 두기'),
                    ('PrintKeepAlive.stop', 'AND2-02 끝나면 멈춤'), ('r.put("done", true)', 'AND2-02 창이 닫힐 때 답함'),
                    ('ACTION_CREATE_DOCUMENT', 'AND2-06 저장 위치 고르기'), ('public void saveToDevice', 'AND2-06 기기에 저장'),
                    ('ACTION_APPLICATION_DETAILS_SETTINGS', 'AND2-10 앱 정보 화면'), ('public void openAppSettings', 'AND2-10 설정 열기')]:
    if need not in pp: fail('%s 없음: %s' % (why, need))
  if 'new PrintAttributes.Builder().build()' in pp: fail('AND2-01 인쇄를 여전히 빈 PrintAttributes(Letter 세로)로 연다')
  i_finish = pp.find('public void onFinish()')
  if i_finish < 0 or pp.find('call.resolve(r)', i_finish) < 0: fail('AND2-02 인쇄 답이 onFinish 에서 나가지 않음')
  ka = read('android/app/src/main/java/com/lets1414/app/PrintKeepAlive.java')
  for need in ['FOREGROUND_SERVICE_TYPE_SHORT_SERVICE', 'public void onTimeout(int startId)', 'stopSelf()']:
    if need not in ka: fail('AND2-02 PrintKeepAlive 에 %s 없음' % need)
  st = read('android/app/src/main/res/values/styles.xml')
  m = re.search(r'<style name="AppTheme.NoActionBar".*?</style>', st, re.S)
  if not m or '<item name="android:windowBackground">@color/splash_background</item>' not in m.group(0):
    fail('AND1-05 AppTheme.NoActionBar 의 창 바탕이 스플래시 색이 아님 (스플래시 뒤 흰 화면)')
  html = read('app/index.html')
  if "P.App.exitApp&&P.App.exitApp()})" in html: fail('AND1-02 뒤로 키가 여전히 exitApp 으로 끝남')
  if 'A.minimizeApp()' not in html: fail('AND1-02 minimizeApp 을 안 씀')
  print('정적: configChanges fontScale · 상태바 되돌림 · 한국어 창 · 인쇄 용지·done·PrintKeepAlive · 기기에 저장 · 앱 설정 · 창 바탕 ok')

def run():
  static_checks()
  with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    SLOW = {'health': 0}   # 켜는 동안(서버 확인)을 늘려 첫 그리기 전 상태를 본다
    def handler(route):
      u = urlparse(route.request.url)
      if SLOW['health'] and u.path == '/api/health': time.sleep(SLOW['health'])
      if u.scheme == 'https' and u.hostname in ('localhost', 'lets1414.com', 'www.lets1414.com') and u.port is None:
        try: return route.fulfill(response=route.fetch(url='%s://%s/%s' % (SRV.scheme, SRV.netloc, u.path.lstrip('/')) + ('?' + u.query if u.query else '')))
        except Exception:
          try: return route.abort()
          except Exception: return
      if u.hostname == SRV.hostname and u.port == SRV.port: return route.continue_()
      return route.abort()   # 바깥(글꼴 CDN)은 막는다

    def native(platform, ua, state=None):
      c = b.new_context(viewport={'width': 412, 'height': 915}, is_mobile=True, has_touch=True, service_workers='block', storage_state=state, user_agent=ua)
      c.route('**/*', handler)
      c.add_init_script(MOCK.replace('__PLATFORM__', platform))
      pg = c.new_page()
      pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('dialog', lambda d: d.accept())
      return c, pg

    def back(pg, can=True):
      pg.evaluate("(c)=>__cap.listeners.backButton({canGoBack:c})", can); pg.wait_for_timeout(700)
    def hash(pg): return pg.evaluate('location.hash')
    def cap(pg, k): return pg.evaluate('__cap.' + k)

    # ================= 안드로이드 · 로그인 전 =================
    c, pg = native('android', UA_ANDROID)
    SLOW['health'] = 0.8
    pg.goto('https://localhost/')
    pg.wait_for_selector('#lgUser', timeout=15000); pg.wait_for_timeout(500)
    SLOW['health'] = 0
    bt = pg.evaluate('__cap.boot')
    if 'preauth' not in (bt.get('dcl') or {}).get('cls', '') or (bt.get('dcl') or {}).get('bg') != 'rgb(10, 10, 10)':
      fail('AND1-05 로그인 전 안드로이드 첫 그리기 전 바탕이 로그인 색(preauth, #0A0A0A)이 아님: %s' % bt)
    elif (bt.get('afterResize') or {}).get('app') is not False or 'preauth' not in bt['afterResize']['cls']:
      fail('AND1-05 켜는 동안(첫 그리기 전) resize 에 preauth 가 떨어져 밝은 바탕이 보임 (또는 검사가 그린 뒤에 돎): %s' % bt)
    cls = pg.evaluate('document.documentElement.className')
    if 'preauth' in cls: fail('AND1-05 로그인 화면을 그린 뒤에도 preauth 가 남음: %s' % cls)
    if not pg.evaluate("document.body.classList.contains('authbg')"): fail('AND1-05 로그인 화면 바탕(authbg)이 없음')
    st = cap(pg, 'style')
    if not st or st[0] != 'DARK': fail('AND1-05 켜는 동안 상태바가 먼저 밝은 글씨(DARK)가 아님: %s' % st)
    print('AND1-05 안드로이드 로그인 전: 첫 그리기 전 %s · resize 뒤 %s · 그린 뒤 떼짐 · 상태바 %s ok' % (bt.get('dcl'), bt.get('afterResize'), st[:2]))

    # ---- AND1-02 로그인 화면에서 뒤로 = 내리기 ----
    pg.fill('#lgUser', 'abc12'); h0 = hash(pg)
    back(pg)
    if cap(pg, 'min') != 1 or cap(pg, 'exit') != 0: fail('AND1-02 로그인 화면 뒤로가 앱 내리기(minimizeApp)가 아님: min=%s exit=%s' % (cap(pg, 'min'), cap(pg, 'exit')))
    if hash(pg) != h0 or pg.input_value('#lgUser') != 'abc12': fail('AND1-02 로그인 화면 뒤로에 주소·친 아이디가 바뀜: %s %r' % (hash(pg), pg.input_value('#lgUser')))
    # ---- AND1-01 비밀번호 재설정 → 로그인 ----
    pg.click('[data-act="lg-mode"][data-m="recover"]'); pg.wait_for_selector('#rcCode')
    back(pg)
    if pg.locator('#rcCode').count() or not pg.locator('[data-act="lg-submit"]').count(): fail('AND1-01 비밀번호 재설정에서 뒤로가 로그인으로 안 돌아감')
    if cap(pg, 'min') != 1: fail('AND1-01 비밀번호 재설정에서 뒤로가 앱을 내림')
    print('AND1-02 로그인 뒤로 → minimizeApp (exitApp 0) · 친 아이디 그대로 · 재설정 → 로그인 ok')

    # ---- 가입 → 팀 없음(게이트) ----
    uid = 'andn' + tag
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName'); pg.check('#lgAgree')
    pg.fill('#lgName', '안드'); pg.fill('#lgUser', uid); pg.fill('#lgPass', 'secret12'); pg.click('[data-act="lg-submit"]')
    pg.wait_for_selector('#gtTeam', timeout=15000); pg.wait_for_timeout(300)
    pg.fill('#gtTeam', '안드팀%s' % tag)
    m0 = cap(pg, 'min'); back(pg)
    if cap(pg, 'min') != m0 + 1 or pg.input_value('#gtTeam') != '안드팀%s' % tag: fail('AND1-02 팀 만들기 화면 뒤로가 내리기가 아니거나 친 팀 이름이 사라짐')
    pg.click('[data-act="team-create"]'); pg.wait_for_selector('.shell[data-page]', timeout=15000); pg.wait_for_timeout(500)
    m0 = cap(pg, 'min'); back(pg)
    if cap(pg, 'min') != m0 + 1 or cap(pg, 'exit') != 0: fail('AND1-02 홈에서 뒤로가 내리기(minimizeApp)가 아님')
    print('AND1-02 팀 만들기 화면·홈 뒤로 → minimizeApp · 친 팀 이름 그대로 ok')
    invite = pg.evaluate('CONTI.S.team.invite')

    api = """async([path,body])=>{const r=await fetch('https://lets1414.com/api'+path,{method:'POST',credentials:'include',
      headers:{'x-conti':'1','x-conti-app':'1','content-type':'application/json',authorization:'Bearer '+localStorage.getItem('conti-app-token')},body:JSON.stringify(body)});return await r.json()}"""
    tid = pg.evaluate('CONTI.S.team.id')
    song = pg.evaluate(api, ['/songs', {'teamId': tid, 'title': '뒤로 시험곡', 'key': 'G'}])['song']['id']
    date = pg.evaluate(api, ['/teams/%s/dates' % tid, {'date': (datetime.date.today() + datetime.timedelta(days=7)).isoformat(), 'label': '주일예배', 'time': '11:00'}])['date']['id']

    # ---- AND1-01 곡 상세 → 라이브러리 → 홈 ----
    pg.evaluate("CONTI.pullSongs(true)"); pg.wait_for_timeout(500)
    pg.click('.bnav [data-act="nav-lib"]'); pg.wait_for_selector('[data-song]', timeout=10000)
    pg.click('[data-song="%s"]' % song); pg.wait_for_function("location.hash.startsWith('#library/')", timeout=10000); pg.wait_for_timeout(500)
    back(pg)
    if hash(pg) != '#library': fail('AND1-01 곡 상세에서 뒤로가 라이브러리가 아님: %s' % hash(pg))
    back(pg)
    if hash(pg) not in ('#home', '#/home'): fail('AND1-01 라이브러리(탭 첫 화면)에서 뒤로가 예배(홈)가 아님: %s' % hash(pg))
    # ---- 편성 패널 → 편성 탭 ----
    pg.click('.bnav [data-act="sched"]'); pg.wait_for_selector('#app [data-act="lineup"][data-id="%s"]' % date, state='attached', timeout=10000)
    pg.locator('#app [data-act="lineup"][data-id="%s"]:visible' % date).first.click(); pg.wait_for_function("location.hash.startsWith('#lineup/')", timeout=10000); pg.wait_for_timeout(500)
    back(pg)
    if hash(pg) != '#sched' or pg.evaluate("document.body.classList.contains('lnopen')"): fail('AND1-01 편성 패널에서 뒤로가 편성 탭이 아님: %s' % hash(pg))
    # ---- 설정 > 앱 > 약관 → 설정(앱 탭) ----
    pg.evaluate("()=>{location.hash='#settings'}"); pg.wait_for_selector('[data-act="set-tab"][data-t="app"]', timeout=10000)
    pg.click('[data-act="set-tab"][data-t="app"]'); pg.wait_for_selector('#app [data-act="legal"][data-k="terms"]')
    pg.click('#app [data-act="legal"][data-k="terms"]'); pg.wait_for_function("location.hash==='#legal/terms'", timeout=10000); pg.wait_for_timeout(300)
    back(pg)
    tab = pg.evaluate("(document.querySelector('[data-act=\"set-tab\"].on')||{dataset:{}}).dataset.t")
    if hash(pg) != '#settings' or tab != 'app': fail('AND1-01 설정에서 연 약관 뒤로가 설정 > 앱이 아님: %s %s' % (hash(pg), tab))
    print('AND1-01 곡 상세 → 라이브러리 → 홈 · 편성 패널 → 편성 탭 · 약관 → 설정(앱) ok')
    # ---- 메모 창을 뒤로 키로 닫으면 X·Esc 처럼 멈췄던 재생을 다시 튼다 (전에는 멈춘 채·pausedByComposer 가 남음) ----
    pg.evaluate("()=>{window.__rs=0;const P=CONTI.P;P.__orig=P.resumeIfPaused;P.resumeIfPaused=function(){window.__rs++;P.pausedByComposer=false};P.pausedByComposer=true;CONTI.modal('<div class=\"card\">메모</div>')}")
    pg.wait_for_selector('#modal .card', timeout=5000)
    back(pg)
    rs = pg.evaluate("()=>{const P=CONTI.P;const n=window.__rs;P.resumeIfPaused=P.__orig;return {n,open:!!(document.querySelector('#modal')&&document.querySelector('#modal').firstChild),flag:P.pausedByComposer}}")
    if rs['open'] or rs['n'] != 1 or rs['flag']: fail('뒤로 키로 메모 창을 닫을 때 다시 틀기(resumeIfPaused)를 안 부름: %s' % rs)
    print('뒤로 키로 창 닫기 → 멈췄던 재생 다시 틀기 ok')

    # ---- AND2-01 · AND2-02 인쇄: 용지·방향을 넘기고, 창이 닫힐 때까지 조판을 남긴다 ----
    pg.evaluate("()=>{window.__pr=CONTI.doPrint('시험',{orient:'landscape',paper:'A4',pageW:1123,pageH:794})}")
    pg.wait_for_timeout(2200)
    pr = cap(pg, 'prints')
    if not pr or pr[0]['o'].get('orient') != 'landscape' or pr[0]['o'].get('paper') != 'A4' or not pr[0]['nprint']:
      fail('AND2-01 인쇄에 방향·용지를 안 넘기거나 조판(nprint) 없이 부름: %s' % pr)
    if not pg.evaluate("document.body.classList.contains('nprint')"): fail('AND2-02 인쇄 창이 떠 있는 동안(2.2초) 조판(nprint)이 떨어짐 — 옵션을 바꾸면 다시 조판할 것이 없다')
    pg.evaluate('__cap.finishPrint()'); pg.wait_for_timeout(150)
    if pg.evaluate("document.body.classList.contains('nprint')"): fail('AND2-02 인쇄 창이 닫혔는데(done) 조판이 바로 안 떨어짐')
    if pg.evaluate('window.__pr') is None: pass
    print('AND2-01/02 인쇄 {orient,paper} 넘김 · 창이 떠 있는 동안 nprint 유지 · done 에 바로 뗌 ok')

    # ---- AND2-06 파일 내보내기: 기기에 저장 · 보내기 중 고른다 ----
    pg.evaluate("()=>{window.__sf=CONTI.saveFile('시험.conti.json','{\"a\":1}','application/json')}")
    pg.wait_for_selector('#sfDev', timeout=5000)
    if not pg.locator('#sfGo').count(): fail('AND2-06 내보내기 창에 보내기가 없음')
    pg.click('#sfDev'); pg.wait_for_timeout(300)
    r = pg.evaluate('window.__sf')
    if cap(pg, 'dev') != ['시험.conti.json'] or r != 'saved': fail('AND2-06 기기에 저장이 saveToDevice 로 안 감: %s %s' % (cap(pg, 'dev'), r))
    pg.evaluate("()=>{window.__sf=CONTI.saveFile('보내기.conti.json','{}','application/json')}"); pg.wait_for_selector('#sfGo')
    pg.click('#sfGo'); pg.wait_for_timeout(300)
    sh = cap(pg, 'shares')
    if not sh or '보내기.conti.json' not in json.dumps(sh[-1], ensure_ascii=False) or pg.evaluate('window.__sf') is not True: fail('AND2-06 보내기가 공유 시트로 안 감: %s' % sh)
    pg.evaluate("()=>{window.__sf=CONTI.saveFile('닫기.conti.json','{}','application/json')}"); pg.wait_for_selector('#sfDev')
    back(pg)   # 뒤로 키로 창을 닫아도 끝난다
    if pg.evaluate('window.__sf') is not False or pg.locator('#sfDev').count(): fail('AND2-06 뒤로 키로 창을 닫아도 내보내기가 끝나지 않음')
    # 녹음 '기기에 저장' = 곧바로 저장 위치 고르기 (창 없이)
    pg.evaluate("()=>{window.__sf=CONTI.saveFile('연습.m4a',new Blob([new Uint8Array(5000)],{type:'audio/mp4'}),'audio/mp4','device')}"); pg.wait_for_timeout(500)
    if pg.locator('#sfDev').count() or cap(pg, 'dev')[-1] != '연습.m4a' or pg.evaluate('window.__sf') != 'saved' or not cap(pg, 'saves')[-1].get('bytes'):
      fail('AND2-06 녹음 기기에 저장이 곧바로 saveToDevice(바이트) 로 안 감: %s %s' % (cap(pg, 'dev'), cap(pg, 'saves')[-1:]))
    print('AND2-06 내보내기 기기에 저장 / 보내기 / 뒤로 닫기 · 녹음 기기에 저장 → 저장 위치 고르기 ok')

    # ---- AND2-10 마이크 거절 → 설정에서 켜는 길 ----
    pg.evaluate("()=>{location.hash='#home'}"); pg.wait_for_timeout(600)
    pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]', timeout=8000); pg.wait_for_timeout(300)
    def mic(err):
      pg.evaluate("(n)=>{navigator.mediaDevices.getUserMedia=()=>Promise.reject(new DOMException('x',n))}", err)
      pg.evaluate("CONTI.rehAddModal(CONTI.S.services[0])"); pg.wait_for_selector('#rhRec')
      pg.click('#rhRec'); pg.wait_for_timeout(400)
    mic('NotAllowedError')
    txt = pg.evaluate("document.getElementById('rhProg').innerText")
    if not pg.locator('#rhPerm').count() or '설정' not in txt or '마이크' not in txt: fail('AND2-10 마이크 거절에 설정 안내·설정 열기가 없음: %r' % txt)
    else:
      pg.click('#rhPerm'); pg.wait_for_timeout(200)
      if cap(pg, 'settings') != 1: fail('AND2-10 설정 열기가 Printer.openAppSettings 를 안 부름')
    pg.evaluate("CONTI.closeModal()"); pg.wait_for_timeout(200)
    mic('NotReadableError')
    if pg.locator('#rhPerm').count() or pg.evaluate("document.getElementById('toast').textContent") != '마이크를 쓸 수 없어요': fail('AND2-10 권한이 아닌 마이크 오류는 전처럼 토스트여야 함')
    pg.evaluate("CONTI.closeModal()")
    print('AND2-10 마이크 거절 → 설정 안내 + 설정 열기(openAppSettings) · 다른 오류는 토스트 ok')
    c.close()

    # ================= 안드로이드 · 팀 없이 연 초대 =================
    c, pg = native('android', UA_ANDROID)
    pg.goto('https://localhost/'); pg.wait_for_selector('#lgUser', timeout=15000)
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName'); pg.check('#lgAgree')
    pg.fill('#lgName', '초대'); pg.fill('#lgUser', 'andj' + tag); pg.fill('#lgPass', 'secret12'); pg.click('[data-act="lg-submit"]')
    pg.wait_for_selector('#gtTeam', timeout=15000)
    pg.evaluate("(t)=>{location.hash='#join/'+t}", invite); pg.wait_for_selector('[data-act="team-join"]', timeout=10000); pg.wait_for_timeout(300)
    h0 = hash(pg); m0 = cap(pg, 'min'); back(pg)
    if cap(pg, 'min') != m0 + 1 or hash(pg) != h0 or not pg.locator('[data-act="team-join"]').count() or pg.locator('#gtLink').count():
      fail('AND1-01 팀 없이 연 초대 가입 화면에서 뒤로가 초대를 버림: %s min=%s' % (hash(pg), cap(pg, 'min')))
    else: print('AND1-01 팀 없이 연 초대 가입 → 뒤로 = 앱만 내림 · 초대 미리보기 그대로 ok')
    c.close()

    # ================= iOS · 로그인 전 (전과 같다) =================
    c, pg = native('ios', UA_IOS)
    pg.goto('https://localhost/'); pg.wait_for_selector('#lgUser', timeout=15000); pg.wait_for_timeout(300)
    bt = pg.evaluate('__cap.boot')
    if 'preauth' in (bt.get('dcl') or {}).get('cls', ''): fail('AND1-05 iOS 에도 preauth 가 붙음 (안드로이드만): %s' % bt)
    pg.evaluate("()=>{window.__pr=CONTI.doPrint('시험',{orient:'portrait',paper:'A4'})}"); pg.wait_for_timeout(600)
    if not pg.evaluate("document.body.classList.contains('nprint')"): fail('iOS 인쇄 뒤 조판을 1.5초 남기던 것이 바뀜')
    pg.wait_for_timeout(1500)
    if pg.evaluate("document.body.classList.contains('nprint')"): fail('iOS 인쇄 뒤 조판이 안 떨어짐')
    # 웹 공유가 없는 iOS 가 앱 저장으로 오면 전처럼 공유 시트 (저장 위치 고르기는 안드로이드만)
    pg.evaluate("()=>{Object.defineProperty(navigator,'canShare',{configurable:true,value:undefined});window.__sf=CONTI.saveFile('i.conti.json','{}','application/json')}")
    pg.wait_for_timeout(500)
    if pg.locator('#sfDev').count() or len(cap(pg, 'shares')) != 1 or cap(pg, 'dev'): fail('iOS 파일 건네기가 바뀜 (기기에 저장 창·saveToDevice): shares=%s dev=%s' % (cap(pg, 'shares'), cap(pg, 'dev')))
    print('iOS: preauth 없음 · 인쇄 조판 1.5초 뒤 뗌 · 파일은 공유 시트 (전과 같다) ok')
    c.close()

    # ================= 컴퓨터 웹 =================
    c = b.new_context(viewport={'width': 1300, 'height': 900}, service_workers='block')
    pg = c.new_page(); pg.on('pageerror', lambda e: errs.append('web: %s' % e))
    pg.goto(URL); pg.wait_for_selector('#lgUser', timeout=15000)
    if 'preauth' in pg.evaluate('document.documentElement.className'): fail('AND1-05 웹에 preauth 가 붙음')
    print('웹: preauth 없음 ok')
    c.close(); b.close()
    bad = [e for e in errs if 'ResizeObserver' not in e]
    if bad: fail('페이지 오류: %s' % bad[:3])
  if FAILS:
    print('\n%d개 실패' % len(FAILS)); sys.exit(1)
  print('OK test_android_native')

run()
