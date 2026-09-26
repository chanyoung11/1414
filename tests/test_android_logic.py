# 안드로이드 에뮬레이터 점검(2026-09-27)에서 나온 '로직' 몫 되돌림 방지
#
# 사용: CONTI_URL=http://localhost:8766/ .venv/bin/python tests/test_android_logic.py   (개발 서버가 떠 있어야 한다)
#      SOFT=1 이면 실패해도 끝까지 간다 (고치기 전 코드에서 전부 재현해 볼 때)
#      DATABASE_URL(또는 CONTI_DB) 이 있으면 psql 로 곡 코드 만든 시각을 바꿔 AND2-12 를 본다 (없으면 그 칸은 건너뛴다)
#
# 안드로이드 흉내: 픽셀 7(412x915 · 2.625배 · 터치 · 안드로이드 UA) · 태블릿(1280x800 · 터치).
# 앱은 https://localhost 를 흉내 내고(NATIVE) 가짜 Capacitor(getPlatform 'android' · 상태바 · 푸시 · 뒤로 키)를 넣는다.
# 인터넷 끊김은 웹(같은 api()·같은 화면)에서 브라우저 오프라인으로 본다 — 앱 흉내의 가로채기는 오프라인을 못 따른다.
#
# 본다
#  AND1-04 밝은 테마: 로그인 화면(.auth-main)만 상태바 DARK · 로그인 전에 연 약관과 오프라인으로 켠 홈은 LIGHT
#  AND1-10 가입 창에서 동의 체크 → 약관 → 뒤로 키 → 체크가 그대로 (아이디도)
#  AND1-11 안드로이드 앱 첫 홈: 시스템 권한 창보다 앱 안내 창('알림을 받을까요?')이 먼저 · '밤에도 울리기'를 고르고
#          '알림 받기'를 눌러야 권한을 묻는다 · 고른 대로 조용한 시간이 꺼진다 · 이미 허락한 기기는 창 없이 조용히 등록
#  AND1-12 앱이 앞에 있을 때 발행 알림이 오면 홈 예배 목록에 새 콘티가 곧 나타난다
#  AND2-09 무대 ⚙ 창·편집(블록 메뉴) 중 뒤로 키는 그것부터 닫고 무대에 남는다 · 마지막에야 무대를 나간다
#  AND1-07 켜 둔 채 끊기면 위쪽 띠(#netoff) · 달력 날짜를 눌러 실패하면 우리말 토스트 ('Failed to fetch' 없음) · 다시 붙으면 띠가 걷힌다
#  AND2-13 녹음 올리기가 끊겨 실패하면 우리말 안내 + 올리기 단추 하나(id 겹침 없음) + 기기에 저장
#  AND1-08 새 곡 키 칸의 한글 자판 글자(ㅁ→A · 므→Am) · 못 읽는 키는 막음 · 곡 편집 키 칸(ㅎ→G) ·
#          정기 예배 시간 칸은 안드로이드에서 숫자 자판(inputmode) · 1100 → 11:00 으로 저장
#  AND2-12 곡 코드 미리보기의 보낸 날짜가 한국 날짜 (KST 05:50 에 만든 코드가 전날로 안 보인다)
#  AND2-14 마커 라벨 '직접 입력' 칸에서 엔터 = 확인
#  AND2-11 영상을 틀지 않고 마커 메모를 쓰면 '재생 시각에도 붙이기'가 꺼져 있다 · 틀어 본 자리면 켜져 있다
#  AND2-07 유튜브 플레이어가 늦게 준비돼 첫 'listening' 을 흘려도 다시 불러 연결된다 (중계 yt.html · 웹 둘 다) ·
#          늦을 때 안내가 '영상 주인이 임베드를 막았을 때'가 아니다
#  AND2-03 태블릿 무대 조판 고치기: 블록을 손가락으로 탭하면 블록 메뉴가 떠 있다 (뒤따르는 click 에 닫히지 않음) · 마우스 클릭도
import os, sys, time, json, struct, subprocess, datetime
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
SRV = urlparse(URL)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHEET = os.path.join(ROOT, 'docs', 'sample_sheet.jpg')
tag = str(int(time.time()))[-6:]
SOFT = os.environ.get('SOFT') == '1'
FAILS = []
def fail(m):
  print('FAIL:', m)
  if SOFT: FAILS.append(m); return
  sys.exit(1)

AND_UA = 'Mozilla/5.0 (Linux; Android 16; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36'
TAB_UA = 'Mozilla/5.0 (Linux; Android 16; Pixel Tablet) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'
PHONE = dict(viewport={'width': 412, 'height': 915}, device_scale_factor=2.625, is_mobile=True, has_touch=True, user_agent=AND_UA)
TABLET = dict(viewport={'width': 1280, 'height': 800}, device_scale_factor=2, is_mobile=True, has_touch=True, user_agent=TAB_UA)

# 가짜 Capacitor (안드로이드). 푸시 권한은 __PERM__ 으로 시작한다 (prompt: 안 물음 · granted: 이미 허락)
MOCK = r"""
(() => {
  const cap = window.__cap = { style: [], app: {}, pl: {}, push: { perm: '__PERM__', req: 0, reg: 0 } };
  const ok = (v) => Promise.resolve(v);
  const StatusBar = { setStyle: (o) => { cap.style.push(o.style); return ok(); }, setBackgroundColor: () => ok(), hide: () => ok(), show: () => ok() };
  const PushNotifications = {
    checkPermissions: () => ok({ receive: cap.push.perm }),
    requestPermissions: () => { cap.push.req++; cap.push.perm = 'granted'; return ok({ receive: 'granted' }); },
    register: () => { cap.push.reg++; setTimeout(() => (cap.pl.registration || []).forEach((f) => f({ value: 'tok-' + Date.now() })), 30); return ok(); },
    unregister: () => ok(), createChannel: () => ok(), removeAllListeners: () => { cap.pl = {}; return ok(); },
    addListener: (n, f) => { (cap.pl[n] = cap.pl[n] || []).push(f); return ok({ remove() {} }); },
  };
  window.Capacitor = {
    getPlatform: () => 'android', isNativePlatform: () => true, isPluginAvailable: () => false,
    Plugins: {
      StatusBar, PushNotifications,
      App: { addListener: (n, f) => { (cap.app[n] = cap.app[n] || []).push(f); return ok({ remove() {} }); },
             getLaunchUrl: () => ok(undefined), exitApp() { cap.exited = (cap.exited || 0) + 1; }, getInfo: () => ok({}) },
      SplashScreen: { hide: () => ok() }, KeepAwake: { keepAwake: () => ok(), allowSleep: () => ok() },
    },
  };
  cap.back = () => (cap.app.backButton || []).forEach((f) => f({ canGoBack: false }));
  cap.pushIn = (data) => (cap.pl.pushNotificationReceived || []).forEach((f) => f({ title: 't', body: 'b', data }));
  try { localStorage.setItem('conti-theme', 'light'); } catch (e) {}
  const safe = () => { const r = document.documentElement; if (r) { r.style.setProperty('--sat', '24px'); r.style.setProperty('--sab', '0px'); } };
  safe(); document.addEventListener('readystatechange', safe);
})();
"""

# 유튜브 흉내: 뜬 뒤 1.5초 동안 온 'listening' 은 흘린다 (첫 열기의 늦은 준비). 그 뒤의 listening 에만 답한다
YT_STUB = r"""<!doctype html><body style="background:#000"><script>
const t0=Date.now();let on=false,playing=false,cur=0,src=null;
addEventListener('message',e=>{let d;try{d=typeof e.data==='string'?JSON.parse(e.data):e.data}catch(_){return}
 if(d.event==='listening'){if(Date.now()-t0<1500||on)return;on=true;src=e.source;
  src.postMessage(JSON.stringify({event:'initialDelivery',id:1,channel:'widget',info:{duration:634,currentTime:0,playerState:-1}}),'*');
  src.postMessage(JSON.stringify({event:'onReady',id:1,channel:'widget'}),'*');
  setInterval(()=>{if(playing)cur+=0.5;src.postMessage(JSON.stringify({event:'infoDelivery',id:1,channel:'widget',info:{currentTime:cur,playerState:playing?1:2}}),'*')},500);return}
 if(!on)return;
 if(d.event==='command'&&d.func==='playVideo')playing=true;
 if(d.event==='command'&&d.func==='pauseVideo')playing=false;});
</script></body>"""

def wav_bytes(sec=1, rate=8000):
  n = sec * rate
  data = b'\x00\x00' * n
  return b'RIFF' + struct.pack('<I', 36 + len(data)) + b'WAVEfmt ' + struct.pack('<IHHIIHH', 16, 1, 1, rate, rate * 2, 2, 16) + b'data' + struct.pack('<I', len(data)) + data

def kst_today(): return (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=9)).date()

def psql(sql):
  db = os.environ.get('DATABASE_URL') or os.environ.get('CONTI_DB') or ''
  if not db: return None
  for exe in ('/opt/homebrew/opt/postgresql@18/bin/psql', 'psql'):
    try: return subprocess.run([exe, db, '-v', 'ON_ERROR_STOP=1', '-Atc', sql], capture_output=True, text=True, timeout=20, check=True).stdout.strip()
    except FileNotFoundError: continue
  return None

def run():
  with sync_playwright() as p:
    b = p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
    errs = []

    def handler(route):
      u = urlparse(route.request.url)
      if u.hostname in ('www.youtube.com', 'youtube.com', 'www.youtube-nocookie.com') and '/embed/' in u.path:
        return route.fulfill(status=200, body=YT_STUB, headers={'content-type': 'text/html'})
      if u.scheme == 'https' and u.hostname in ('localhost', 'lets1414.com', 'www.lets1414.com') and u.port is None:
        if API_DOWN[0] and u.path.startswith('/api/'): return route.abort('internetdisconnected')
        try: return route.fulfill(response=route.fetch(url='%s://%s/%s' % (SRV.scheme, SRV.netloc, u.path.lstrip('/')) + ('?' + u.query if u.query else '')))
        except Exception:
          try: return route.abort()
          except Exception: return
      if u.hostname == SRV.hostname and u.port == SRV.port: return route.continue_()
      return route.abort()   # 바깥(글꼴 CDN 등)은 막는다
    API_DOWN = [False]

    def native(dev, perm='prompt'):
      c = b.new_context(service_workers='block', **dev)
      c.route('**/*', handler)
      c.add_init_script(MOCK.replace('__PERM__', perm))
      pg = c.new_page(); pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('dialog', lambda d: d.accept())
      return c, pg

    def web(dev):
      c = b.new_context(service_workers='block', **dev)
      c.route(__import__('re').compile(r'^https://www\.youtube\.com/embed/.*'), lambda r: r.fulfill(status=200, body=YT_STUB, headers={'content-type': 'text/html'}))
      c.add_init_script("try{localStorage.setItem('conti-theme','light');localStorage.setItem('conti-push-asked','1')}catch(e){}")
      pg = c.new_page(); pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('dialog', lambda d: d.accept())
      return c, pg

    def signup(pg, uname, name, team, base):
      pg.goto(base); pg.wait_for_selector('#lgUser', timeout=15000)
      pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName'); pg.check('#lgAgree')
      pg.fill('#lgName', name); pg.fill('#lgUser', uname); pg.fill('#lgPass', 'secret12'); pg.click('[data-act="lg-submit"]')
      pg.wait_for_selector('#gtTeam', timeout=15000); pg.fill('#gtTeam', team); pg.click('[data-act="team-create"]')
      pg.wait_for_selector('.shell[data-page]', timeout=15000)

    def api_ctx(uname):
      rq = p.request.new_context(base_url=URL, extra_http_headers={'x-conti': '1'})
      r = rq.post('api/auth/login', data={'username': uname, 'password': 'secret12'})
      if not r.ok: fail('API 로그인 실패 %s %s' % (r.status, r.text()[:200]))
      return rq

    def last_style(pg): st = pg.evaluate('__cap.style'); return st[-1] if st else None

    def toast_seen(pg, ms=4000):
      seen = []
      end = time.time() + ms / 1000
      while time.time() < end:
        t = pg.evaluate("(()=>{const t=document.getElementById('toast');return t&&t.classList.contains('show')?t.textContent:''})()")
        if t and t not in seen: seen.append(t)
        pg.wait_for_timeout(100)
      return seen

    # ============ 1. 안드로이드 폰 앱: 상태바 · 가입 동의 · 알림 안내 · 알림으로 목록 · 무대 뒤로 키 ============
    c, pg = native(PHONE, 'prompt')
    pg.goto('https://localhost/'); pg.wait_for_selector('#lgUser', timeout=15000); pg.wait_for_timeout(500)
    if last_style(pg) != 'DARK': fail('AND1-04 로그인 화면(어두운 바탕)의 상태바가 DARK 가 아님: %s' % pg.evaluate('__cap.style'))
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName')
    uname = 'aa' + tag
    pg.fill('#lgName', '안드'); pg.fill('#lgUser', uname); pg.fill('#lgPass', 'secret12')
    pg.tap('#lgAgree'); pg.wait_for_timeout(200)
    if not pg.is_checked('#lgAgree'): fail('AND1-10 동의 칸을 눌러도 체크가 안 됨')
    pg.tap('a[data-act="legal"][data-k="terms"]')
    pg.wait_for_function("location.hash.indexOf('legal')>=0", timeout=8000); pg.wait_for_timeout(500)
    if pg.locator('.auth-main').count(): fail('AND1-04 약관 화면에 로그인 바탕이 남음')
    if last_style(pg) != 'LIGHT': fail('AND1-04 로그인 전에 연 약관(밝은 바탕)의 상태바가 흰 글씨(DARK): %s' % pg.evaluate('__cap.style')[-3:])
    else: print('AND1-04 로그인 화면 DARK · 로그인 전 약관 LIGHT ok')
    pg.mouse.wheel(0, 20000); pg.wait_for_timeout(300)
    if last_style(pg) != 'LIGHT': fail('AND1-04 약관 끝까지 내리면 상태바가 바뀜')
    pg.evaluate('__cap.back()'); pg.wait_for_selector('#lgAgree', timeout=8000); pg.wait_for_timeout(300)
    st = pg.evaluate("({agree:document.getElementById('lgAgree').checked,u:document.getElementById('lgUser').value})")
    if not st['agree'] or st['u'] != uname: fail('AND1-10 약관을 보고 뒤로 오면 동의 체크가 풀림: %s' % st)
    else: print('AND1-10 약관 → 뒤로: 체크·아이디 그대로 ok', st)
    if last_style(pg) != 'DARK': fail('AND1-04 로그인 화면으로 돌아와도 상태바가 DARK 로 안 돌아옴')
    if not pg.is_checked('#lgAgree'): pg.check('#lgAgree')   # (SOFT) 풀렸으면 다시 체크하고 이어 간다
    pg.click('[data-act="lg-submit"]'); pg.wait_for_selector('#gtTeam', timeout=15000)
    pg.fill('#gtTeam', 'zzqa안드' + tag); pg.click('[data-act="team-create"]'); pg.wait_for_selector('.shell[data-page]', timeout=15000)
    team = pg.evaluate('CONTI.S.team.id')

    # ---- AND1-11 첫 홈: 안내 창이 먼저, 권한은 '알림 받기' 뒤에 ----
    try: pg.wait_for_selector('#pbYes', timeout=6000)
    except Exception: pass
    push = pg.evaluate('__cap.push')
    if not pg.locator('#pbYes').count(): fail('AND1-11 안드로이드 앱 첫 홈에 알림 안내 창이 안 뜸 (권한 창 %d번): %s' % (push['req'], push))
    elif push['req']: fail('AND1-11 안내 창보다 먼저 시스템 권한 창을 띄움: %s' % push)
    else:
      if pg.is_checked('#pbNight'): fail('AND1-11 밤에도 울리기가 처음부터 켜져 있음')
      pg.tap('#pbNight'); pg.tap('#pbYes'); pg.wait_for_timeout(1500)
      push = pg.evaluate('__cap.push'); q = pg.evaluate('CONTI.quietOf()')
      if push['req'] != 1 or push['reg'] < 1: fail('AND1-11 알림 받기를 눌러도 권한·등록을 안 함: %s' % push)
      if q.get('on') is not False: fail('AND1-11 밤에도 울리기를 골랐는데 조용한 시간이 켜져 있음: %s' % q)
      if pg.evaluate('CONTI.pushState()') != 'granted': fail('AND1-11 켠 뒤 알림 상태가 granted 가 아님: %s' % pg.evaluate('CONTI.pushState()'))
      print('AND1-11 안내 창 먼저 · 알림 받기 뒤 권한 %d번 · 조용한 시간 %s ok' % (push['req'], q))

    # ---- AND1-12 앱이 앞에 있을 때 발행 알림 → 홈 목록 ----
    pg.evaluate("location.hash='#/home'"); pg.wait_for_selector('.shell[data-page]', timeout=8000); pg.wait_for_timeout(1500)
    rq = api_ctx(uname)
    sid = 'and' + tag
    day = (kst_today() + datetime.timedelta(days=7)).isoformat()
    doc = {'id': sid, 'name': '알림콘티' + tag, 'date': day, 'version': 1,
           'items': [{'id': 'i1', 'title': '첫 곡', 'key': 'G', 'pieces': [], 'media': [], 'notes': []}]}
    r = rq.put('api/services/' + sid, data={'teamId': team, 'doc': doc})
    if not r.ok: fail('발행 PUT 실패 %s %s' % (r.status, r.text()[:200]))
    pg.wait_for_timeout(1200)
    if '알림콘티' + tag in pg.locator('#app').inner_text(): print('  (알림 전에 이미 목록에 있음 — 다른 까닭으로 받음)')
    pg.evaluate("(d)=>__cap.pushIn(d)", {'type': 'publish', 'teamId': team, 'link': '#/view/' + sid})
    try: pg.wait_for_function("(n)=>document.getElementById('app').innerText.indexOf(n)>=0", arg='알림콘티' + tag, timeout=6000); print('AND1-12 발행 알림 → 홈 목록에 새 콘티 ok')
    except Exception: fail('AND1-12 앱이 앞에 있을 때 발행 알림이 와도 홈 목록에 새 콘티가 안 나타남')

    # ---- AND2-09 무대 ⚙ 창에서 뒤로 키 ----
    pg.evaluate("(id)=>CONTI.S.services.some(s=>s.id===id)||CONTI.SYNC.pullServices()", sid); pg.wait_for_timeout(500)   # (SOFT) 목록이 안 왔으면 받고 이어 간다
    pg.evaluate("(id)=>CONTI.stageOpen(CONTI.S.services.find(s=>s.id===id),0)", sid); pg.wait_for_selector('#stageWrap', timeout=10000); pg.wait_for_timeout(400)
    pg.click('[data-stg="cfg"]'); pg.wait_for_timeout(300)
    if not pg.evaluate('CONTI.STG.open'): fail('무대 ⚙ 창이 안 열림')
    pg.evaluate('__cap.back()'); pg.wait_for_timeout(300)
    if not pg.locator('#stageWrap').count(): fail('AND2-09 ⚙ 창이 떠 있을 때 뒤로 키가 무대 전체를 끝냄')
    elif pg.evaluate('CONTI.STG.open'): fail('AND2-09 뒤로 키로 ⚙ 창이 안 닫힘')
    else:
      pg.evaluate('__cap.back()'); pg.wait_for_timeout(300)
      if pg.locator('#stageWrap').count(): fail('AND2-09 창이 없을 때 뒤로 키로 무대를 못 나감')
      else: print('AND2-09 ⚙ 창 → 뒤로: 창만 닫힘 · 다시 뒤로: 무대 나감 ok')

    # ---- AND1-04 오프라인으로 켠 홈 (서버에 못 닿아 사용자 없음) ----
    API_DOWN[0] = True
    pg.evaluate("location.hash='#/home'"); pg.reload(); pg.wait_for_selector('.shell[data-page]', timeout=15000); pg.wait_for_timeout(3500)
    info = pg.evaluate("({user:!!CONTI.NET.user,server:CONTI.NET.server,auth:!!document.querySelector('.auth-main')})")
    if info['auth']: fail('AND1-04 오프라인으로 켰는데 로그인 화면이 뜸: %s' % info)
    elif last_style(pg) != 'LIGHT': fail('AND1-04 오프라인으로 켠 밝은 홈의 상태바가 흰 글씨(DARK): %s %s' % (pg.evaluate('__cap.style'), info))
    else: print('AND1-04 오프라인으로 켠 홈 LIGHT ok', info)
    API_DOWN[0] = False
    c.close(); rq.dispose()

    # ---- AND1-11 이미 허락한 기기: 창 없이 조용히 등록 ----
    c, pg = native(PHONE, 'granted')
    signup(pg, 'ab' + tag, '허락', 'zzqa허락' + tag, 'https://localhost/'); pg.wait_for_timeout(2800)
    push = pg.evaluate('__cap.push')
    if pg.locator('#pbYes').count(): fail('AND1-11 이미 허락한 기기에 안내 창이 또 뜸')
    if push['reg'] < 1 or push['req']: fail('AND1-11 이미 허락한 기기가 조용히 등록하지 않음: %s' % push)
    else: print('AND1-11 이미 허락한 기기: 창 없이 등록 ok', push)
    c.close()

    # ============ 2. 웹(안드로이드 폰): 끊김 · 녹음 올리기 · 키·시간 칸 · 곡 코드 날짜 ============
    c, pg = web(PHONE)
    wname = 'ac' + tag
    signup(pg, wname, '웹폰', 'zzqa웹' + tag, URL)
    team = pg.evaluate('CONTI.S.team.id')
    rq = c.request

    # ---- AND1-08 새 곡 키 칸 ----
    pg.goto(URL + '#/library'); pg.wait_for_selector('[data-act="lib-new"]', timeout=10000)
    def new_song(title, key):
      pg.click('[data-act="lib-new"]'); pg.wait_for_selector('#nsKey')
      pg.fill('#nsTitle', title); pg.fill('#nsKey', key); pg.click('#nsOk'); pg.wait_for_timeout(1200)
      return pg.evaluate("(t)=>{const s=(CONTI.S.songs||[]).find(x=>x.title===t);return s?{origKey:s.origKey,key:((s.arrangements||[])[0]||{}).key}:null}", title)
    s1 = new_song('키한글' + tag, 'ㅁ')
    if not s1 or s1['origKey'] != 'A' or s1['key'] != 'A': fail('AND1-08 키 칸의 한글 자판 ㅁ 이 A 로 안 바뀜: %s' % s1)
    pg.goto(URL + '#/library'); pg.wait_for_selector('[data-act="lib-new"]', timeout=10000)
    s2 = new_song('키단조' + tag, '므')
    if not s2 or s2['origKey'] != 'Am': fail('AND1-08 므 가 Am 으로 안 바뀜: %s' % s2)
    pg.goto(URL + '#/library'); pg.wait_for_selector('[data-act="lib-new"]', timeout=10000)
    pg.click('[data-act="lib-new"]'); pg.wait_for_selector('#nsKey'); pg.fill('#nsTitle', '키틀림' + tag); pg.fill('#nsKey', 'x7')
    seen = []
    pg.click('#nsOk'); seen = toast_seen(pg, 1200)
    bad = pg.evaluate("(t)=>(CONTI.S.songs||[]).some(x=>x.title===t)", '키틀림' + tag)
    if bad or not any('A~G' in t for t in seen): fail('AND1-08 못 읽는 키(x7)로도 곡이 만들어짐/안내 없음: made=%s toast=%s' % (bad, seen))
    else: print('AND1-08 키 칸 ㅁ→A · 므→Am · x7 막음 ok', s1, s2)
    pg.evaluate("CONTI.closeModal()")

    # ---- AND1-08 정기 예배 시간 칸 ----
    pg.goto(URL + '#/team'); pg.wait_for_selector('[data-act="tm-dates"]', state='attached', timeout=10000)
    pg.evaluate("document.querySelector('[data-act=\"tm-dates\"]').click()"); pg.wait_for_selector('#rcTime', timeout=8000)   # 팀 → 새 예배 기본값(접힘) 안의 단추
    im = pg.get_attribute('#rcTime', 'inputmode'); im2 = pg.get_attribute('#mdTime', 'inputmode')
    if im != 'numeric' or im2 != 'numeric': fail('AND1-08 안드로이드 시간 칸이 숫자 자판이 아님: %s %s' % (im, im2))
    pg.fill('#rcLabel', '주일' + tag); pg.fill('#rcTime', '1100'); pg.click('#rcLabel'); pg.wait_for_timeout(200)
    if pg.input_value('#rcTime') != '11:00': fail('AND1-08 시간 1100 이 11:00 으로 안 바뀜: %r' % pg.input_value('#rcTime'))
    pg.click('#rcAdd'); pg.wait_for_timeout(1200)
    rec = [x for x in rq.get(URL + 'api/teams/%s/dates' % team, headers={'x-conti': '1'}).json()['recurring'] if x['label'] == '주일' + tag]
    if not rec or rec[0]['time'] != '11:00': fail('AND1-08 정기 예배 시간이 11:00 으로 저장 안 됨: %s' % rec)
    else: print('AND1-08 시간 칸 inputmode=numeric · 1100 → 11:00 저장 ok')
    pg.evaluate("CONTI.closeModal()")

    # ---- AND1-08 곡 편집 키 칸 · AND2-14 마커 라벨 엔터 (편집기) ----
    pg.goto(URL + '#/home'); pg.wait_for_selector('[data-act="new-svc"]', timeout=10000)
    pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]', timeout=8000); pg.fill('[data-f="svc.name"]', '웹 예배' + tag)
    pg.click('[data-act="add-item"]'); pg.wait_for_selector('[data-f="item.title"]'); pg.fill('[data-f="item.title"]', '편집곡')
    pg.fill('[data-f="item.key"]', 'ㅎ'); pg.click('[data-f="item.title"]'); pg.wait_for_timeout(300)
    wsvc = pg.evaluate("CONTI.route().a")
    k = pg.evaluate("(id)=>CONTI.S.services.find(s=>s.id===id).items[0].key", wsvc)
    if k != 'G' or pg.input_value('[data-f="item.key"]') != 'G': fail('AND1-08 곡 편집 키 칸 ㅎ 이 G 로 안 바뀜: %r / %r' % (k, pg.input_value('[data-f="item.key"]')))
    else: print('AND1-08 곡 편집 키 칸 ㅎ→G ok')
    pg.set_input_files('#pieceFile', [SHEET])
    pg.wait_for_function("(id)=>{const it=CONTI.S.services.find(s=>s.id===id).items[0];const p=(it.pieces||[])[0];return p&&p.w>0}", arg=wsvc, timeout=90000)
    pg.wait_for_timeout(800)
    sl = pg.locator('.slice').first; sl.scroll_into_view_if_needed(); pg.wait_for_timeout(300); bb = sl.bounding_box()
    pg.mouse.click(bb['x'] + bb['width'] * 0.3, bb['y'] + min(bb['height'] * 0.4, 200)); pg.wait_for_selector('#customLabel', timeout=5000)
    pg.fill('#customLabel', 'V1'); pg.focus('#customLabel'); pg.keyboard.press('Enter'); pg.wait_for_timeout(500)
    labels = pg.evaluate("(id)=>CONTI.S.services.find(s=>s.id===id).items[0].pieces[0].markers.map(m=>m.label)", wsvc)
    if pg.locator('#customLabel').count() or 'V1' not in labels: fail('AND2-14 직접 입력 칸에서 엔터로 마커가 안 놓임: open=%s labels=%s' % (pg.locator('#customLabel').count(), labels))
    else: print('AND2-14 마커 라벨 직접 입력 엔터 = 확인 ok', labels)
    if pg.get_attribute('#customLabel', 'enterkeyhint') if pg.locator('#customLabel').count() else False: pass
    pg.evaluate("CONTI.closeModal()")

    # ---- AND2-12 곡 코드의 보낸 날짜 ----
    sgid = pg.evaluate("(t)=>(CONTI.S.songs.find(x=>x.title===t)||{}).id", '키한글' + tag)
    r = rq.post(URL + 'api/share', headers={'x-conti': '1'}, data={'teamId': team, 'songId': sgid})
    if not r.ok: fail('곡 코드 만들기 실패 %s %s' % (r.status, r.text()[:200]))
    else:
      code = r.json()['code']
      got = rq.get(URL + 'api/share/' + code, headers={'x-conti': '1'}).json()['payload']['from']['at']
      if got != kst_today().isoformat(): fail('AND2-12 오늘 만든 곡 코드의 보낸 날짜가 한국 날짜가 아님: %s (KST %s)' % (got, kst_today()))
      ch = psql("update share_codes set created_at='2026-09-26T20:50:00Z', payload=jsonb_set(payload,'{from,at}','\"2026-09-26\"') where code='%s' returning code" % code)
      if ch is None: print('  (DATABASE_URL 이 없어 KST 05:50 코드는 건너뜀)')
      else:
        got = rq.get(URL + 'api/share/' + code, headers={'x-conti': '1'}).json()['payload']['from']['at']
        if got != '2026-09-27': fail('AND2-12 KST 05:50 에 만든 코드가 전날(%s)로 보임' % got)
        else: print('AND2-12 곡 코드 보낸 날짜 KST ok (UTC 20:50 → %s)' % got)

    # ---- AND2-13 녹음 올리기가 끊겨 실패 ----
    svc = wsvc
    pg.goto(URL + '#/edit/' + svc); pg.wait_for_selector('[data-act="publish"]', timeout=10000)
    pg.click('[data-act="publish"]'); pg.wait_for_selector('#pubOnly', timeout=8000); pg.click('#pubOnly')
    pg.wait_for_function("(id)=>{const s=CONTI.S.services.find(x=>x.id===id);return s.published&&!s.pubPending}", arg=svc, timeout=30000)
    pg.goto(URL + '#/view/' + svc); pg.wait_for_selector('[data-act="reh-add"]', timeout=15000)
    pg.click('[data-act="reh-add"]'); pg.wait_for_selector('#rhFile', state='attached', timeout=5000)
    pg.set_input_files('#rhFile', files=[{'name': 'reh.wav', 'mimeType': 'audio/wav', 'buffer': wav_bytes()}]); pg.wait_for_timeout(1200)
    c.set_offline(True); pg.wait_for_timeout(300)
    pg.click('#rhOk')
    seen = toast_seen(pg, 2500)
    txt = pg.locator('#rhProg').inner_text(); n_ok = pg.locator('#rhOk').count()
    if 'Failed' in txt or any('Failed' in t for t in seen): fail('AND2-13 녹음 올리기 실패가 영어(Failed to fetch): %r %s' % (txt, seen))
    if '인터넷' not in txt: fail('AND2-13 끊겨 못 올렸다는 우리말 안내가 없음: %r' % txt)
    if n_ok != 1: fail('AND2-13 올리기(rhOk) 단추가 %d개 (id 겹침)' % n_ok)
    if not pg.locator('#rhSave').count(): fail('AND2-13 실패 줄에 기기에 저장이 없음')
    if n_ok == 1 and pg.locator('#rhOk').is_disabled(): fail('AND2-13 다시 올리기 단추가 막혀 있음')
    if '인터넷' in txt and n_ok == 1: print('AND2-13 녹음 올리기 끊김: %r · 단추 하나 ok' % txt)
    c.set_offline(False); pg.wait_for_timeout(300)
    pg.evaluate("CONTI.closeModal()")

    # ---- AND1-07 켜 둔 채 끊김: 띠 · 달력 날짜 누르기 ----
    today = kst_today().isoformat()
    r = rq.post(URL + 'api/teams/%s/dates' % team, headers={'x-conti': '1'}, data={'date': today, 'label': '끊김' + tag})
    if not r.ok: fail('날짜 추가 실패 %s %s' % (r.status, r.text()[:200]))
    pg.goto(URL + '#/cal'); pg.wait_for_selector('[data-cal="%s"]' % today, timeout=15000); pg.wait_for_timeout(600)
    if pg.locator('#netoff').is_visible(): fail('AND1-07 연결돼 있는데 끊김 띠가 보임')
    c.set_offline(True); pg.wait_for_timeout(400)
    if not pg.locator('#netoff').is_visible(): fail('AND1-07 인터넷이 끊겨도 표시가 없음 (#netoff)')
    before = pg.evaluate("(d)=>{const a=CONTI.SCH.availability.find(x=>x.date===d&&x.userId===CONTI.S.team.me.userId);return a?a.state:'unset'}", today)
    pg.tap('[data-cal="%s"]' % today)
    seen = toast_seen(pg, 3000)
    after = pg.evaluate("(d)=>{const a=CONTI.SCH.availability.find(x=>x.date===d&&x.userId===CONTI.S.team.me.userId);return a?a.state:'unset'}", today)
    n0 = len(FAILS)
    if any('Failed' in t or 'fetch' in t for t in seen): fail('AND1-07 날짜를 누르면 영어 오류 토스트: %s' % seen)
    elif not any('인터넷' in t for t in seen): fail('AND1-07 끊겨 실패했다는 우리말 토스트가 없음: %s' % seen)
    if after != before: fail('AND1-07 실패한 가능/보류가 되돌아가지 않음: %s → %s' % (before, after))
    c.set_offline(False); pg.wait_for_timeout(500)
    if pg.locator('#netoff').is_visible(): fail('AND1-07 다시 연결돼도 끊김 띠가 남음')
    elif len(FAILS) == n0: print('AND1-07 끊김 띠 · 우리말 토스트 %s · 다시 붙으면 걷힘 ok' % seen)
    c.close()

    # ============ 3. 안드로이드 태블릿 앱: 마커 메모 기본값 · 유튜브 연결 · 무대 블록 메뉴 · 편집 중 뒤로 키 ============
    c, pg = native(TABLET, 'granted')
    tname = 'ad' + tag
    signup(pg, tname, '태블릿', 'zzqa태블릿' + tag, 'https://localhost/')
    pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]', timeout=8000); pg.fill('[data-f="svc.name"]', '태블릿 예배')
    pg.click('[data-act="add-item"]'); pg.wait_for_selector('[data-f="item.title"]'); pg.fill('[data-f="item.title"]', '영상곡')
    tsid = pg.evaluate("CONTI.route().a")
    pg.set_input_files('#pieceFile', [SHEET])
    pg.wait_for_function("(id)=>{const it=CONTI.S.services.find(s=>s.id===id).items[0];const p=(it.pieces||[])[0];return p&&p.w>0}", arg=tsid, timeout=90000)
    pg.fill('#ytUrl', 'https://youtu.be/dQw4w9WgXcQ'); pg.click('[data-act="add-yt"]'); pg.wait_for_timeout(600)
    pg.evaluate("""(id)=>{const it=CONTI.S.services.find(s=>s.id===id).items[0];const p=it.pieces[0];p.markers=p.markers||[];
      p.markers.push({id:'mkC',label:'C',x:Math.round(p.w*0.3),y:Math.round(Math.min(p.h*0.3,300)),cut:null});CONTI.save()}""", tsid)

    # ---- AND2-07 늦게 준비되는 유튜브 (중계 yt.html) ----
    pg.goto('https://localhost/#/play/' + tsid); pg.wait_for_selector('#yt', state='attached', timeout=15000)
    relay = pg.evaluate("CONTI.YT.relay")
    try: pg.wait_for_function('CONTI.P.ytReady', timeout=8000); print('AND2-07 늦게 준비된 유튜브도 연결 (중계 %s) ok' % relay)
    except Exception: fail('AND2-07 첫 listening 을 흘린 유튜브와 끝내 연결되지 않음 (중계 %s)' % relay)

    # ---- AND2-11 영상을 틀지 않고 마커 메모 ----
    pg.evaluate("CONTI.P.started=false")
    pg.click('[data-marker="mkC"]'); pg.wait_for_selector('#cText', timeout=5000)
    if not pg.locator('#cAlsoT').count(): fail('AND2-11 마커 메모 창에 재생 시각 붙이기 칸이 없음 (영상이 있는데)')
    elif pg.is_checked('#cAlsoT'): fail('AND2-11 영상을 안 틀었는데 재생 시각에도 붙이기가 켜져 있음 (0:00 메모가 생김)')
    else: print('AND2-11 안 튼 영상: 재생 시각 붙이기 꺼짐 ok')
    pg.evaluate("CONTI.closeModal()"); pg.wait_for_timeout(200)
    if pg.evaluate('CONTI.P.ytReady'):
      pg.click('[data-act="ptoggle"]'); pg.wait_for_timeout(1600)
      pg.evaluate("CONTI.P.pause&&CONTI.P.pause()"); pg.wait_for_timeout(700)
      t = pg.evaluate('CONTI.P.t')
      pg.click('[data-marker="mkC"]'); pg.wait_for_selector('#cText', timeout=5000)
      if t > 0 and not pg.is_checked('#cAlsoT'): fail('AND2-11 틀어 본 자리(%.1f초)인데 재생 시각 붙이기가 꺼져 있음' % t)
      elif t <= 0: fail('AND2-07 재생 단추로 영상 시각이 안 움직임 (P.t=%s)' % t)
      else: print('AND2-11 틀어 본 자리(%.1f초)에서는 켜짐 ok · AND2-07 재생 단추로 시각이 움직임' % t)
      pg.evaluate("CONTI.closeModal()")

    # ---- AND2-03 무대 조판 고치기: 블록 탭 → 메뉴 ----
    pg.evaluate("(id)=>CONTI.stageOpen(CONTI.S.services.find(s=>s.id===id),0)", tsid); pg.wait_for_selector('#stageWrap', timeout=10000); pg.wait_for_timeout(600)
    pg.click('[data-stg="edit"]'); pg.wait_for_timeout(400)
    if not pg.evaluate('CONTI.STG.edit'): fail('무대 편집(✎)이 안 켜짐 (태블릿)')
    blk = pg.locator('#stageWrap [data-sid]').first
    if not blk.count(): fail('무대 편집에 블록이 없음')
    else:
      bb = blk.bounding_box(); x, y = bb['x'] + bb['width'] / 2, bb['y'] + min(bb['height'] / 2, 150)
      pg.touchscreen.tap(x, y); pg.wait_for_timeout(500)
      menus = pg.locator('#stageWrap .sblkmenu').count()
      if not menus or not pg.evaluate('CONTI.STG.menu'): fail('AND2-03 블록을 손가락으로 탭해도 블록 메뉴가 안 남음 (menus=%d)' % menus)
      else: print('AND2-03 태블릿 블록 탭 → 메뉴 남음 ok')
      # ---- AND2-09 편집 중 뒤로 키: 메뉴 → 편집 → 무대 ----
      pg.evaluate('__cap.back()'); pg.wait_for_timeout(300)
      s9 = pg.evaluate("({wrap:!!document.getElementById('stageWrap'),edit:CONTI.STG.edit,menu:CONTI.STG.menu})")
      if not s9['wrap'] or not s9['edit'] or s9['menu']: fail('AND2-09 블록 메뉴가 떠 있을 때 뒤로 키: %s (메뉴만 닫혀야)' % s9)
      pg.evaluate('__cap.back()'); pg.wait_for_timeout(300)
      s9 = pg.evaluate("({wrap:!!document.getElementById('stageWrap'),edit:CONTI.STG.edit})")
      if not s9['wrap'] or s9['edit']: fail('AND2-09 편집 중 뒤로 키가 편집만 끝내지 않음: %s' % s9)
      else: print('AND2-09 편집 중 뒤로 키: 메뉴 → 편집 끝 · 무대에 남음 ok')
      # 마우스(컴퓨터 크롬) 클릭도 같은 순서다
      if not pg.locator('#stageWrap').count():   # (SOFT) 뒤로 키가 무대를 닫았으면 다시 연다
        pg.evaluate("(id)=>CONTI.stageOpen(CONTI.S.services.find(s=>s.id===id),0)", tsid); pg.wait_for_selector('#stageWrap', timeout=10000); pg.wait_for_timeout(600)
      if not pg.evaluate('CONTI.STG.edit'): pg.click('[data-stg="edit"]')
      pg.evaluate("CONTI.STG.menu=null"); pg.wait_for_timeout(300)
      blk = pg.locator('#stageWrap [data-sid]').first; bb = blk.bounding_box()
      pg.mouse.click(bb['x'] + bb['width'] / 2, bb['y'] + min(bb['height'] / 2, 150)); pg.wait_for_timeout(500)
      if not pg.locator('#stageWrap .sblkmenu').count(): fail('AND2-03 마우스로 블록을 눌러도 메뉴가 안 남음')
      else: print('AND2-03 마우스 클릭 → 메뉴 남음 ok')
      # 빈 곳(캔버스 바깥 여백)을 누르면 닫힌다
      pg.mouse.click(5, 790); pg.wait_for_timeout(400)
      if pg.evaluate('CONTI.STG.menu'): fail('AND2-03 바깥을 눌러도 블록 메뉴가 안 닫힘')
    pg.evaluate("CONTI.stageExit()")
    c.close()

    # ---- AND2-07 웹(중계 없음)도 다시 부른다 · 늦을 때 안내 ----
    c, pg = web(dict(viewport={'width': 1180, 'height': 820}))
    signup(pg, 'ae' + tag, '웹영상', 'zzqa영상' + tag, URL)
    wsid = pg.evaluate("""()=>{const s={id:'yt'+Date.now().toString(36),name:'영상 예배',date:'2026-12-01',notice:'',version:0,published:null,
      items:[{id:'i1',title:'곡',key:'',mod:'',form:'',songNote:'',pieces:[],notes:[],media:[{id:'m1',type:'youtube',url:'https://youtu.be/dQw4w9WgXcQ',notes:[]}]}]};
      CONTI.S.services.push(s);CONTI.save();return s.id}""")
    pg.goto(URL + '#/play/' + wsid); pg.wait_for_selector('#yt', state='attached', timeout=10000)
    try: pg.wait_for_function('CONTI.P.ytReady', timeout=8000); print('AND2-07 웹 직접 넣기도 늦은 플레이어와 연결 ok')
    except Exception: fail('AND2-07 웹: 첫 listening 을 흘린 유튜브와 연결되지 않음')
    # 끝내 답이 없는 플레이어: 안내가 '임베드를 막았다'가 아니다
    c.route(__import__('re').compile(r'^https://www\.youtube\.com/embed/.*'), lambda r: r.fulfill(status=200, body='<!doctype html><body></body>', headers={'content-type': 'text/html'}))
    pg.goto(URL + '#/home'); pg.wait_for_timeout(300); pg.goto(URL + '#/play/' + wsid); pg.wait_for_selector('#yt', state='attached', timeout=10000); pg.wait_for_timeout(3200)
    h = pg.locator('#ytHint').inner_text()
    if '임베드를 막았' in h: fail('AND2-07 준비가 늦을 뿐인데 "영상 주인이 임베드를 막았다"고 안내: %s' % h)
    else: print('AND2-07 늦을 때 안내: %s ok' % h[:40])
    c.close()

    if errs: fail('JS 오류: %s' % errs[:3])
    b.close()
  if FAILS:
    print('\n%d FAIL' % len(FAILS)); [print(' -', f) for f in FAILS]; sys.exit(1)
  print('\nALL OK test_android_logic')

if __name__ == '__main__':
  run()
