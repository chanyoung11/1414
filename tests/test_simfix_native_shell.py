# 앱 껍데기 검사 — iOS 시뮬레이터 수동 점검(2026-09-26)에서 나온 것 중 '앱 껍데기·입력' 몫
#
# 사용: CONTI_URL=http://localhost:8766/ .venv/bin/python tests/test_simfix_native_shell.py   (개발 서버가 떠 있어야 한다)
#      SOFT=1 이면 실패해도 끝까지 간다 (고치기 전 코드에서 전부 재현해 볼 때)
#
# 앱은 https://localhost 를 흉내 내고(NATIVE) 가짜 Capacitor(상태바·공유)를 넣는다. 안전 영역은 --sat/--sab 로 준다
# (아이폰 16 Pro 62/34 · 아이패드 32/20 — 크롬의 env() 는 0 이다).
# 가짜 브리지는 시뮬레이터에서 잰 것을 따른다: 네이티브 호출의 답이 돌아오면 웹뷰의 '방금 누른 손길'이 지워져
# 그 뒤의 navigator.share 는 NotAllowedError 로 거절된다 (B9). 새로 누르면(진짜 클릭) 다시 생긴다.
#
# 본다
#  A3  상태바 자리(0~--sat)는 문서를 내려도 늘 바탕색 띠로 덮인다 (로그인 화면은 어두운 띠) · 창(.ov)은 띠 위를 덮는다
#  A5  앱·터치 기기는 켜자마자·가입 직후 입력칸에 커서를 두지 않는다 (자판이 저절로 올라옴) · 컴퓨터는 전처럼 아이디 칸에
#  A6  앱이 앞에 있을 때 온 푸시도 배너로 (capacitor.config.json presentationOptions)
#  A7  confirm·alert·prompt 창 단추가 한국어 (Info.plist 한국어 · SceneDelegate 의 KoreanDialogs) — 정적 검사
#  A8  버튼(하단 탭 포함)은 길게 눌러도 글자가 잡히지 않는다 · 입력칸은 그대로
#  A12 초대: 앱은 목록 줄·만든 뒤 창에 '보내기'(공유 시트) — 누르면 Share.share 로 카톡 문구 · 복사 단추는 링크 아이콘 ·
#      컴퓨터(웹)는 전처럼 복사·카톡 문구만
#  A13 한글 자판으로 친 아이디('뮻12')는 칸을 떠날 때 누른 영문 글쇠('abc12')로 · 칸을 안 떠나고 보내도 바꿔서 가입된다
#  B8  발행 창 · 목사님 말씀 링크 창에 '보내기'(공유 시트)
#  B9  ≡ → 파일 내보내기: 창을 열고 닫아도 상태바를 또 부르지 않아 첫 공유가 거절되지 않는다 ('파일이 준비됐어요' 두 번째 누르기 없음)
#  E2  밝은 테마에서 무대를 열면 상태바 글씨가 밝게(DARK), 닫으면 되돌아온다
#  E3  아이패드 사이드바가 안전 영역 안에서 끝난다 (문서가 밀리지 않고 프로필 줄이 홈 인디케이터 위)
import io, os, sys, time, json, re, plistlib
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
from PIL import Image

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

MOCK = r"""
(() => {
  const cap = window.__cap = { style: [], shares: [], webShares: [], cleared: false };
  // 진짜로 누르면 손길이 새로 생긴다 (스크립트의 el.click() 은 아니다)
  ['pointerdown', 'click', 'keydown'].forEach((t) => addEventListener(t, (e) => { if (e.isTrusted) cap.cleared = false; }, true));
  // 네이티브 호출의 답이 브리지로 돌아오면 웹뷰가 손길을 지운다 (시뮬레이터에서 잰 것)
  const bridge = (v) => Promise.resolve().then(() => { cap.cleared = true; return v; });
  const StatusBar = { setStyle: (o) => { cap.style.push(o.style); return bridge(); },
    setBackgroundColor: () => bridge(), hide: () => bridge(), show: () => bridge() };
  const Share = { share: (o) => { cap.shares.push(o); return bridge({ activityType: 'com.kakao.talk.Share' }); }, canShare: () => bridge({ value: true }) };
  Object.defineProperty(navigator, 'canShare', { configurable: true, value: () => true });
  Object.defineProperty(navigator, 'share', { configurable: true, value: (d) => {
    cap.webShares.push({ text: d.text, files: d.files ? d.files.map((f) => f.name) : null, cleared: cap.cleared });
    return cap.cleared ? Promise.reject(new DOMException('gesture expired', 'NotAllowedError')) : Promise.resolve(); } });
  window.Capacitor = {
    getPlatform: () => 'ios', isNativePlatform: () => true, isPluginAvailable: () => false,
    Plugins: {
      StatusBar, Share,
      App: { addListener: () => Promise.resolve({ remove() {} }), getLaunchUrl: () => Promise.resolve(undefined), exitApp() {}, getInfo: () => Promise.resolve({}) },
      SplashScreen: { hide: () => Promise.resolve() },
      KeepAwake: { keepAwake: () => bridge(), allowSleep: () => bridge() },
    },
  };
  try { localStorage.setItem('conti-theme', 'light'); localStorage.setItem('conti-push-asked', '1'); } catch (e) {}
  // 안전 영역 (크롬의 env() 는 0)
  const safe = () => { const r = document.documentElement; if (r) { r.style.setProperty('--sat', '__SAT__px'); r.style.setProperty('--sab', '__SAB__px'); } };
  safe(); document.addEventListener('readystatechange', safe);
})();
"""

def static_checks():
  # A6 앱이 앞에 있을 때도 배너
  cfg = json.load(open(os.path.join(ROOT, 'capacitor.config.json')))
  po = ((cfg.get('plugins') or {}).get('PushNotifications') or {}).get('presentationOptions') or []
  if not {'banner', 'list', 'sound'} <= set(po): fail('A6 PushNotifications.presentationOptions 에 banner·list·sound 가 없음: %s' % po)
  # A7 시스템 창(인쇄·공유)과 웹 confirm 창이 한국어
  pl = plistlib.load(open(os.path.join(ROOT, 'ios/App/App/Info.plist'), 'rb'))
  if pl.get('CFBundleDevelopmentRegion') != 'ko' or 'ko' not in (pl.get('CFBundleLocalizations') or []):
    fail('A7 Info.plist 가 한국어가 아님: %s %s' % (pl.get('CFBundleDevelopmentRegion'), pl.get('CFBundleLocalizations')))
  sw = open(os.path.join(ROOT, 'ios/App/App/SceneDelegate.swift'), encoding='utf-8').read()
  for need in ['class KoreanDialogs', 'wv.uiDelegate = d', 'runJavaScriptConfirmPanelWithMessage', 'runJavaScriptAlertPanelWithMessage',
               'runJavaScriptTextInputPanelWithPrompt', 'forwardingTarget', '"취소"', '"확인"', 'hasPrefix("Capacitor")']:
    if need not in sw: fail('A7 SceneDelegate.swift 에 %s 가 없음' % need)
  if re.search(r'title:\s*"(Cancel|Ok|OK)"', sw): fail('A7 SceneDelegate.swift 에 영어 단추가 남음')
  html = open(os.path.join(ROOT, 'app/index.html'), encoding='utf-8').read()
  # A8 크롬은 -webkit-touch-callout 을 모른다 → 원문으로 본다
  if not re.search(r'\nbutton\{[^}]*-webkit-user-select:none;user-select:none;-webkit-touch-callout:none', html): fail('A8 버튼 규칙에 글자 잡기 끄기가 없음')
  # A3 띠는 인쇄에 안 나온다
  if 'body.nprint::before{display:none}' not in html or '@media print{body::before{display:none}}' not in html: fail('A3 상태바 띠가 인쇄에서 안 빠짐')
  print('A6 presentationOptions · A7 Info.plist ko + KoreanDialogs · A8 touch-callout · A3 인쇄 제외 ok')

def top_strip(pg, h, w):
  im = Image.open(io.BytesIO(pg.screenshot(clip={'x': 0, 'y': 0, 'width': w, 'height': h}))).convert('RGB')
  return {c for _, c in im.getcolors(1 << 20)}

def run():
  static_checks()
  with sync_playwright() as p:
    b = p.chromium.launch(); errs = []

    def handler(route):
      u = urlparse(route.request.url)
      if u.scheme == 'https' and u.hostname in ('localhost', 'lets1414.com', 'www.lets1414.com') and u.port is None:
        try: return route.fulfill(response=route.fetch(url='%s://%s/%s' % (SRV.scheme, SRV.netloc, u.path.lstrip('/')) + ('?' + u.query if u.query else '')))
        except Exception:
          try: return route.abort()
          except Exception: return
      if u.hostname == SRV.hostname and u.port == SRV.port: return route.continue_()
      return route.abort()   # 바깥(글꼴 CDN)은 막는다

    def native(vw, vh, sat, sab, mobile=True, state=None):
      c = b.new_context(viewport={'width': vw, 'height': vh}, is_mobile=mobile, has_touch=True, service_workers='block', storage_state=state)
      c.route('**/*', handler)
      c.add_init_script(MOCK.replace('__SAT__', str(sat)).replace('__SAB__', str(sab)))
      pg = c.new_page()
      pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('dialog', lambda d: d.accept())
      return c, pg

    def active(pg): return pg.evaluate("(document.activeElement&&document.activeElement.id)||''")

    # ================= 아이폰 (390x844 · 터치 · 상태바 62 · 홈 인디케이터 34) =================
    c, pg = native(390, 844, 62, 34)
    pg.goto('https://localhost/')
    if not pg.evaluate('/^(capacitor|ionic):/.test(location.protocol)||(location.hostname==="localhost"&&!location.port&&location.protocol==="https:")'): fail('앱 흉내가 안 됨 (NATIVE 아님)')
    pg.wait_for_selector('#lgUser', timeout=15000); pg.wait_for_timeout(400)
    # ---- A5 켜자마자 커서 없음 ----
    if active(pg) == 'lgUser': fail('A5 앱을 켜자마자 아이디 칸에 커서(자판이 저절로 올라옴)')
    # ---- A3 로그인 화면의 띠는 어둡다 ----
    bg = pg.evaluate("getComputedStyle(document.body,'::before').backgroundColor")
    h = pg.evaluate("getComputedStyle(document.body,'::before').height")
    if bg != 'rgb(17, 18, 19)' or h != '62px': fail('A3 로그인 화면 상태바 띠가 어두운 62px 가 아님: %s %s' % (bg, h))
    print('A5 켤 때 커서 없음 · A3 로그인 띠 %s %s ok' % (bg, h))

    # ---- A13 한글 자판으로 친 아이디 ----
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName'); pg.check('#lgAgree')
    pg.fill('#lgName', '셸'); pg.fill('#lgUser', '뮻12'); pg.click('#lgPass')
    v = pg.input_value('#lgUser')
    if v != 'abc12': fail('A13 칸을 떠나도 한글 아이디가 영문 글쇠로 안 바뀜: %r' % v)
    uid = 'abc' + tag   # 한글 자판으로 치면 '뮻' + 숫자
    pg.evaluate("(v)=>{document.getElementById('lgUser').value=v}", '뮻' + tag)   # 칸을 안 떠나고 곧장 보냄
    pg.fill('#lgPass', 'secret12')
    pg.evaluate("document.querySelector('[data-act=\"lg-submit\"]').click()")
    try: pg.wait_for_selector('#gtTeam', timeout=15000)
    except Exception:
      fail('A13 한글 자판으로 친 아이디로 가입이 안 됨: %s' % pg.evaluate("(document.getElementById('lgErr')||{}).textContent"))
      pg.fill('#lgUser', uid); pg.fill('#lgPass', 'secret12'); pg.click('[data-act="lg-submit"]'); pg.wait_for_selector('#gtTeam', timeout=15000)
    pg.wait_for_timeout(400)
    got = pg.evaluate("CONTI.NET.user&&CONTI.NET.user.username")
    if got != uid: fail('A13 한글 자판으로 친 아이디로 가입이 %r 로 됨 (바라는 것 %r)' % (got, uid))
    print('A13 뮻12 → abc12 (칸을 떠날 때) · 보낼 때 %s → %s ok' % ('뮻' + tag, got))
    # ---- A5 가입 직후 팀 이름 칸에 커서 없음 ----
    if active(pg) == 'gtTeam': fail('A5 가입 직후 팀 이름 칸에 커서(자판이 저절로 올라옴)')
    pg.fill('#gtTeam', '셸팀%s' % tag); pg.click('[data-act="team-create"]')
    pg.wait_for_selector('.shell[data-page]', timeout=15000)
    print('A5 가입 직후 커서 없음 ok')
    pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]', timeout=8000)
    pg.fill('[data-f="svc.name"]', '셸 예배'); pg.click('[data-act="add-item"]'); pg.wait_for_selector('[data-f="item.title"]')
    pg.fill('[data-f="item.title"]', '첫 곡'); pg.wait_for_timeout(500)
    sid = pg.evaluate("CONTI.S.services[0].id")
    # ---- A8 입력칸은 그대로 고를 수 있다 ----
    us = pg.evaluate("getComputedStyle(document.querySelector('[data-f=\"svc.name\"]')).userSelect")
    if us == 'none': fail('A8 입력칸 글자까지 못 고르게 됨')

    # ---- B8 발행 창 · 말씀 링크 창의 보내기 ----
    pg.evaluate("document.querySelector('[data-act=\"publish\"]').click()"); pg.wait_for_selector('#kk', timeout=8000)
    if not pg.locator('#kkShare').count(): fail('B8 발행 창에 보내기(공유) 단추가 없음')
    else:
      n0 = len(pg.evaluate('__cap.shares')); pg.click('#kkShare'); pg.wait_for_timeout(300)
      sh = pg.evaluate('__cap.shares')
      if len(sh) != n0 + 1 or sh[-1].get('text') != pg.input_value('#kk'): fail('B8 보내기가 카톡 문구를 공유 시트로 넘기지 않음: %s' % sh[n0:])
      if not pg.locator('#kk').count(): fail('B8 보내기 뒤 발행 창이 닫힘 (발행은 따로 눌러야 한다)')
      print('B8 발행 창 보내기 → Share.share(카톡 문구) · 창 유지 ok')
    pg.evaluate("CONTI.closeModal()")
    pg.evaluate("document.querySelector('[data-act=\"word-link\"]').click()"); pg.wait_for_selector('.linkbox', timeout=10000)
    if not pg.locator('#wlShare').count(): fail('B8 말씀 링크 창에 보내기 단추가 없음')
    else:
      n0 = len(pg.evaluate('__cap.shares')); pg.click('#wlShare'); pg.wait_for_timeout(300)
      sh = pg.evaluate('__cap.shares')
      if len(sh) != n0 + 1 or '#/word-link/' not in (sh[-1].get('text') or ''): fail('B8 말씀 링크 보내기가 링크를 안 넘김: %s' % sh[n0:])
      if pg.locator('.linkbox').count(): fail('B8 말씀 링크를 보낸 뒤 창이 안 닫힘')
      print('B8 말씀 링크 창 보내기 → Share.share(링크 문구) ok')
    pg.evaluate("CONTI.closeModal()")
    pg.evaluate("()=>{location.hash='#/home'}"); pg.wait_for_selector('[data-act="home-more"]', timeout=8000); pg.wait_for_timeout(500)

    # ---- A8 하단 탭 버튼 ----
    us = pg.evaluate("getComputedStyle(document.querySelector('.bnav button')).userSelect")
    if us != 'none': fail('A8 하단 탭 버튼 글자를 길게 눌러 고를 수 있음: %s' % us)
    print('A8 하단 탭 user-select none · 입력칸은 그대로 ok')

    # ---- E2 밝은 테마의 무대 ----
    st = pg.evaluate('__cap.style')
    if not st or st[-1] != 'LIGHT': fail('E2 밝은 테마 홈의 상태바가 LIGHT 가 아님: %s' % st)
    pg.evaluate("CONTI.stageOpen(CONTI.S.services[0],0)"); pg.wait_for_selector('#stageWrap', timeout=10000); pg.wait_for_timeout(300)
    st = pg.evaluate('__cap.style')
    if st[-1] != 'DARK': fail('E2 무대(검은 바탕)를 열어도 상태바 글씨가 어두움: %s' % st)
    pg.evaluate("CONTI.stageExit()"); pg.wait_for_timeout(300)
    st = pg.evaluate('__cap.style')
    if st[-1] != 'LIGHT': fail('E2 무대를 닫아도 상태바가 되돌아오지 않음: %s' % st)
    print('E2 무대 열면 DARK · 닫으면 LIGHT ok', st)

    # ---- B9 ≡ → 파일 내보내기가 첫 번째 누르기로 공유 시트까지 ----
    pg.evaluate("""async()=>{const b=new Blob([new Uint8Array(3000)],{type:'image/png'});await CONTI.IDB.put('blobs','bx'+Date.now(),b);
      const k=(await new Promise(r=>{const t=CONTI.IDB.db.transaction('blobs','readonly').objectStore('blobs').getAllKeys();t.onsuccess=()=>r(t.result)})).filter(x=>String(x).startsWith('bx')).pop();
      const s=CONTI.S.services[0];s.items[0].pieces.push({id:'pcx',blob:k,w:100,h:100,markers:[]});CONTI.save()}""")
    n_style = len(pg.evaluate('__cap.style'))
    for i in range(3):   # 창을 열고 닫아도 상태바를 또 부르지 않는다
      pg.evaluate("CONTI.modal('<b>x</b>',{center:true})"); pg.wait_for_timeout(50); pg.evaluate("CONTI.closeModal()"); pg.wait_for_timeout(50)
    if len(pg.evaluate('__cap.style')) != n_style: fail('B9 창을 열고 닫을 때마다 상태바(네이티브)를 또 부름: %s' % pg.evaluate('__cap.style')[n_style:])
    pg.click('[data-act="home-more"]'); pg.wait_for_selector('#modal [data-m="export"]')
    pg.click('#modal [data-m="export"]'); pg.wait_for_timeout(1200)
    ws = pg.evaluate('__cap.webShares')
    if not ws or not (ws[0].get('files') or [''])[0].endswith('.conti.json'): fail('B9 내보내기가 공유를 부르지 않음: %s' % ws)
    elif ws[0]['cleared'] or pg.locator('#sfGo').count(): fail('B9 첫 공유가 거절돼 "파일이 준비됐어요 · 보내기"를 한 번 더 눌러야 함: %s' % ws)
    else: print('B9 ≡ → 파일 내보내기 → 첫 번째에 공유 시트 ok', ws)
    if pg.locator('#sfGo').count(): pg.evaluate("CONTI.closeModal()")

    # ---- A3 문서를 내려도 상태바 자리는 바탕색 ----
    pg.evaluate("""()=>{const m=document.querySelector('.main>main');const d=document.createElement('div');d.id='tallx';
      d.style.cssText='height:3000px;background:repeating-linear-gradient(#e11 0 8px,#11e 8px 16px)';m.appendChild(d);window.scrollTo(0,900)}""")
    pg.wait_for_timeout(200)
    if pg.evaluate('window.scrollY') < 500: fail('A3 검사용으로 문서가 안 내려감')
    top = top_strip(pg, 62, 390)
    under = top_strip(pg, 120, 390) - top
    if top != {(250, 250, 250)}: fail('A3 문서를 내리면 글·그림이 상태바(시계) 밑으로 지나감: %s' % list(top)[:5])
    elif not under: fail('A3 검사용 줄무늬가 안 보임 (검사가 헛돎)')
    else: print('A3 내려도 상태바 자리 62px 는 바탕색(#FAFAFA) 띠 ok')
    pg.evaluate("CONTI.modal('<b>x</b>',{center:true})"); pg.wait_for_timeout(300)
    if top_strip(pg, 62, 390) == {(250, 250, 250)}: fail('A3 창의 어두운 막이 상태바 띠를 덮지 못함')
    pg.evaluate("CONTI.closeModal()"); pg.evaluate("()=>{document.getElementById('tallx').remove();window.scrollTo(0,0)}")
    print('A3 창(.ov)은 띠 위를 덮음 ok')

    # ---- A12 초대: 만든 뒤 창 · 목록 줄 ----
    pg.evaluate("()=>{location.hash='#/team'}"); pg.wait_for_selector('[data-act="tm-invite"]', timeout=10000)
    pg.click('[data-act="tm-invite"]'); pg.wait_for_selector('#ivOk'); pg.click('#ivOk')
    pg.wait_for_selector('#ivShare, .linkbox', timeout=10000)
    if not pg.locator('#ivShare').count(): fail('A12 초대 링크를 만든 뒤 창에 보내기(공유)가 없음')
    else:
      n0 = len(pg.evaluate('__cap.shares')); pg.click('#ivShare'); pg.wait_for_timeout(300)
      sh = pg.evaluate('__cap.shares')
      if len(sh) != n0 + 1 or '#/join/' not in (sh[-1].get('text') or '') or '초대해요' not in sh[-1].get('text', ''): fail('A12 보내기가 초대 문구·링크를 공유 시트로 넘기지 않음: %s' % sh[n0:])
      if pg.locator('#ivShare').count(): fail('A12 보낸 뒤 창이 안 닫힘')
      print('A12 만든 뒤 창 보내기 → Share.share(초대 문구) ok')
    pg.evaluate("CONTI.closeModal()"); pg.wait_for_selector('[data-icopy]', timeout=8000)
    row = pg.evaluate("""(()=>{const cp=document.querySelector('[data-icopy]'),r=cp.closest('.mrow');
      return {share:!!r.querySelector('[data-ishare]'),kakao:!!r.querySelector('[data-ikakao]'),copyLink:cp.innerHTML.includes('M10 14a4'),copyExport:cp.innerHTML.includes('M12 15V4')}})()""")
    if not row['share'] or row['kakao'] or not row['copyLink'] or row['copyExport']: fail('A12 초대 줄: 앱은 보내기가 있고 카톡 문구 복사는 빠지며 복사는 링크 아이콘이어야 함: %s' % row)
    else:
      n0 = len(pg.evaluate('__cap.shares')); pg.click('[data-ishare]'); pg.wait_for_timeout(300)
      sh = pg.evaluate('__cap.shares')
      if len(sh) != n0 + 1 or '#/join/' not in (sh[-1].get('text') or ''): fail('A12 초대 줄 보내기가 공유 시트를 안 엶: %s' % sh[n0:])
      print('A12 초대 줄 보내기 · 복사는 링크 아이콘 ok', row)
    state = c.storage_state()
    c.close()

    # ================= 아이패드 (1032x1376 · 상태바 32 · 홈 인디케이터 20) =================
    c, pg = native(1032, 1376, 32, 20, mobile=False, state=state)
    pg.goto('https://localhost/#/home'); pg.wait_for_selector('aside.side, .side', timeout=15000); pg.wait_for_timeout(600)
    r = pg.evaluate("""(()=>{const s=document.querySelector('.side').getBoundingClientRect(),p=document.querySelector('.side .prof');
      return {bottom:s.bottom,top:s.top,prof:p?p.getBoundingClientRect().bottom:null,ih:innerHeight,sh:document.scrollingElement.scrollHeight}})()""")
    if r['bottom'] > r['ih'] - 20 + 0.5 or r['sh'] > r['ih']: fail('E3 아이패드 사이드바가 안전 영역 밖으로 넘침 (문서가 밀림): %s' % r)
    elif r['prof'] is not None and r['prof'] > r['ih'] - 20: fail('E3 프로필 줄이 홈 인디케이터 자리에: %s' % r)
    else: print('E3 아이패드 사이드바 %s ok' % r)
    c.close()

    # ================= 컴퓨터 웹 (마우스) — 전과 같다 =================
    c = b.new_context(viewport={'width': 1300, 'height': 900}, service_workers='block')
    pg = c.new_page(); pg.on('pageerror', lambda e: errs.append('web: %s' % e)); pg.on('dialog', lambda d: d.accept())
    pg.goto(URL); pg.wait_for_selector('#lgUser', timeout=15000); pg.wait_for_timeout(300)
    if active(pg) != 'lgUser': fail('A5 컴퓨터에서는 아이디 칸에 커서가 있어야 함: %r' % active(pg))
    h = pg.evaluate("getComputedStyle(document.body,'::before').height")
    if h not in ('0px', 'auto'): fail('A3 웹(안전 영역 0)에 상태바 띠가 생김: %s' % h)
    pg.fill('#lgUser', uid); pg.fill('#lgPass', 'secret12'); pg.click('[data-act="lg-submit"]')
    pg.wait_for_selector('.shell[data-page]', timeout=15000)
    pg.evaluate("()=>{location.hash='#/team'}"); pg.wait_for_selector('[data-act="tm-invite"]', timeout=10000)
    pg.evaluate("()=>{CONTI.TM.open.invites=true;CONTI.render()}"); pg.wait_for_selector('[data-icopy]', timeout=8000)
    if pg.locator('[data-ishare]').count() or not pg.locator('[data-ikakao]').count(): fail('A12 컴퓨터 웹 초대 줄이 바뀜 (보내기 없이 복사·카톡 문구)')
    print('A5 컴퓨터는 아이디 칸 커서 그대로 · A12 웹은 복사·카톡 문구 그대로 ok')
    c.close()
    b.close()
    bad = [e for e in errs if 'ResizeObserver' not in e]
    if bad: fail('페이지 오류: %s' % bad[:3])
  if FAILS:
    print('\n%d개 실패' % len(FAILS)); sys.exit(1)
  print('OK test_simfix_native_shell')

run()
