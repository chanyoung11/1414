# 자판(iOS 웹뷰) 검사 — 시뮬레이터 재점검(2026-09-26)에서 남은 것 중 '자판' 몫
#
# 사용: CONTI_URL=http://localhost:8766/ .venv/bin/python tests/test_simfix_keyboard.py   (개발 서버가 떠 있어야 한다)
#      SOFT=1 이면 실패해도 끝까지 간다 (고치기 전 코드에서 전부 재현해 볼 때)
#
# 크롬에는 화면 자판이 없어 iOS 웹뷰가 하는 일을 흉내 낸다 (시뮬레이터에서 잰 값):
#  · 자판이 올라오면 레이아웃 화면(documentElement.clientHeight 874)은 그대로, 보이는 화면(visualViewport.height)만 494 로 준다
#  · 칸을 누르면 iOS 가 창을 밀어 올린다(scrollY = visualViewport.offsetTop) — 칸이 이미 자판 위에 보여도 (아이디 160 · 곡 제목 380 ·
#    하드웨어 자판 44·14). 자판 덮개만큼 문서가 더 넘어가게 되어 문서가 넘어가지 않는 화면도 밀린다
#  · 밀린 동안 innerHeight 는 874-offsetTop 으로 알린다 (그래서 innerHeight 로 자판 높이를 재면 offsetTop 을 두 번 뺀다)
# 크롬의 fixed 는 스크롤을 따라오므로 상태바 띠는 그림이 아니라 --vvt(띠의 top)로 본다.
#
# 본다
#  A3·N3 로그인 아이디(자판 380·밀림 160) · 하드웨어 자판(밀림 14·44)처럼 칸이 이미 보이는데 민 것은 되돌린다 · 띠(body::before)는
#        보이는 화면 맨 위(--vvt = offsetTop)에 붙는다 — 되돌릴 수 없어 밀린 채 남는 화면(설정 기타 카포)에서도
#  N4    편집기 곡 제목(밀림 380): 창 대신 편집기 스크롤 칸(.ws)이 올라가 편집기 바·띠는 제자리, 칸은 자판 위
#  B3    연습 화면 메모 창(재생 시각 줄까지 있어 자판 위 빈자리보다 크다): 저장 줄이 시트 바닥에 붙어 자판 위에 보인다 · 시트 머리는
#        상태바 밑 · iOS 가 창을 민 채면(offsetTop 237) 자판 높이를 레이아웃 화면으로 재 --kb 143 (전에는 0 이라 저장이 자판 밑)
#  N1    자판이 떠 있을 때 알림(한글 자판 아이디 → 영문)은 보이는 화면 위쪽(상태바 밑)에 한 줄로 — 자판 뒤도, 치는 칸 위도 아니게
#  ·     자판이 뜬 채 손가락으로 끌어 민 화면은 되돌리지 않는다 · 컴퓨터 웹은 그대로 (띠 top 0 · kbup 없음)
#  A3    로그인 화면 상태바 띠는 로그인 바탕(#0A0A0A)과 같은 색
import os, sys, time
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
SRV = urlparse(URL)
tag = str(int(time.time()))[-7:]
SOFT = os.environ.get('SOFT') == '1'
FAILS = []
def fail(m):
  print('FAIL:', m)
  if SOFT: FAILS.append(m); return
  sys.exit(1)

W, H, SAT, SAB, KB = 402, 874, 62, 34, 380   # 아이폰 16 Pro · 화면 자판(한글) 380
VIS = H - KB                                   # 494

MOCK = r"""
(() => {
  window.Capacitor = {
    getPlatform: () => 'ios', isNativePlatform: () => true, isPluginAvailable: () => false,
    Plugins: {
      StatusBar: { setStyle: () => Promise.resolve(), setBackgroundColor: () => Promise.resolve(), hide: () => Promise.resolve(), show: () => Promise.resolve() },
      App: { addListener: () => Promise.resolve({ remove() {} }), getLaunchUrl: () => Promise.resolve(undefined), exitApp() {}, getInfo: () => Promise.resolve({}) },
      SplashScreen: { hide: () => Promise.resolve() },
      KeepAwake: { keepAwake: () => Promise.resolve(), allowSleep: () => Promise.resolve() },
    },
  };
  try { localStorage.setItem('conti-theme', 'dark'); localStorage.setItem('conti-push-asked', '1'); } catch (e) {}
  const safe = () => { const r = document.documentElement; if (r) { r.style.setProperty('--sat', '__SAT__px'); r.style.setProperty('--sab', '__SAB__px'); } };
  safe(); document.addEventListener('readystatechange', safe);
  // ---- iOS 자판 흉내 ----
  const vv = new EventTarget(), st = window.__kb = { h: null }, de = () => document.documentElement;
  Object.defineProperty(vv, 'height', { get: () => st.h != null ? st.h : de().clientHeight });
  Object.defineProperty(vv, 'width', { get: () => de().clientWidth });
  Object.defineProperty(vv, 'offsetTop', { get: () => st.h != null ? Math.max(0, window.scrollY) : 0 });
  Object.defineProperty(vv, 'offsetLeft', { get: () => 0 });
  Object.defineProperty(vv, 'pageTop', { get: () => window.scrollY });
  Object.defineProperty(vv, 'scale', { get: () => 1 });
  Object.defineProperty(window, 'visualViewport', { configurable: true, get: () => vv });
  Object.defineProperty(window, 'innerHeight', { configurable: true, get: () => de().clientHeight - vv.offsetTop });
  addEventListener('scroll', () => vv.dispatchEvent(new Event('scroll')));
  const fire = () => { vv.dispatchEvent(new Event('resize')); vv.dispatchEvent(new Event('scroll')); };
  let sp = null;
  // 자판 kb 가 올라오고 iOS 가 창을 pan 만큼 민다 — 자판 덮개만큼 문서가 더 넘어간다
  window.__kbShow = (kb, pan) => {
    st.h = de().clientHeight - kb;
    if (!sp) { sp = document.createElement('div'); sp.id = 'kbInset'; document.body.appendChild(sp); }
    sp.style.cssText = 'position:absolute;left:0;width:1px;height:1px;pointer-events:none;top:' + (de().clientHeight + kb - 1) + 'px';
    if (pan != null) window.scrollTo(0, pan);
    fire();
  };
  window.__kbHide = () => { st.h = null; if (sp) { sp.remove(); sp = null; } window.scrollTo(0, 0); fire(); };
})();
""".replace('__SAT__', str(SAT)).replace('__SAB__', str(SAB))

def state(pg):
  return pg.evaluate("""(()=>{const de=document.documentElement,cs=getComputedStyle(de),ae=document.activeElement,r=ae&&ae.getBoundingClientRect();
    return {sy:Math.round(scrollY),vvt:cs.getPropertyValue('--vvt').trim(),kb:cs.getPropertyValue('--kb').trim(),kbt:cs.getPropertyValue('--kbt').trim(),
      up:de.classList.contains('kbup'),strip:getComputedStyle(document.body,'::before').top,ae:ae&&(ae.id||ae.getAttribute('data-f')||ae.tagName),
      r:r?[Math.round(r.top),Math.round(r.bottom)]:null}})()""")

def run():
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
      return route.abort()   # 바깥(글꼴 CDN·유튜브)은 막는다

    c = b.new_context(viewport={'width': W, 'height': H}, is_mobile=True, has_touch=True, service_workers='block')
    c.route('**/*', handler); c.add_init_script(MOCK)
    pg = c.new_page(); pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('dialog', lambda d: d.accept())
    pg.goto('https://localhost/'); pg.wait_for_selector('#lgUser', timeout=15000); pg.wait_for_timeout(400)

    def show(kb, pan=None): pg.evaluate("([k,p])=>window.__kbShow(k,p)", [kb, pan]); pg.wait_for_timeout(250)
    def hide(): pg.evaluate("()=>{document.activeElement&&document.activeElement.blur();window.__kbHide()}"); pg.wait_for_timeout(250)
    def focus(sel): pg.evaluate("(s)=>document.querySelector(s).focus()", sel); pg.wait_for_timeout(30)

    # ---- A3 로그인 화면 띠 색 ----
    bg = pg.evaluate("[getComputedStyle(document.body,'::before').backgroundColor,getComputedStyle(document.querySelector('.auth')).backgroundColor]")
    if bg[0] != bg[1]: fail('A3 로그인 상태바 띠(%s)가 로그인 바탕(%s)과 다른 색 — 위에 밝은 띠' % tuple(bg))
    else: print('A3 로그인 띠 = 바탕 %s ok' % bg[0])

    # ---- A3 로그인 아이디: 칸이 보이는데 민 160 을 되돌린다 ----
    # (글꼴이 달라 칸 자리가 시뮬레이터와 조금 다르다 — 칸이 자판 위에 들어가는 자판 높이로 본다: 시뮬레이터는 아이디 410~448 · 자판 380)
    ub = pg.evaluate("Math.round(document.getElementById('lgUser').getBoundingClientRect().bottom)")
    kb1 = min(KB, H - ub - 40)
    focus('#lgUser'); show(kb1, 160)
    s = state(pg)
    if s['sy'] != 0: fail('A3 아이디 칸이 자판 위에 보이는데 창이 밀린 채(로고·제목이 시계 밑): %s' % s)
    elif s['vvt'] != '0px' or s['strip'] != '0px': fail('A3 되돌린 뒤 띠 자리가 0 이 아님: %s' % s)
    elif not (s['r'][1] <= H - kb1 - 12): fail('A3 되돌린 뒤 아이디 칸이 자판 밑: %s' % s)
    else: print('A3 로그인 아이디 밀림 160 → 0 ok', s)
    hide()
    # ---- N3 하드웨어 자판(보조 막대 44): 밀림 14 ----
    focus('#lgUser'); show(44, 14)
    s = state(pg)
    if s['sy'] != 0: fail('N3 하드웨어 자판에서 민 14 가 남음: %s' % s)
    else: print('N3 하드웨어 자판 밀림 14 → 0 ok', s)
    hide()
    # ---- 손가락으로 끌어 민 것은 그대로 ----
    focus('#lgUser')
    pg.evaluate("""()=>{const t=(y)=>new Touch({identifier:7,target:document.body,clientX:200,clientY:y});
      document.body.dispatchEvent(new TouchEvent('touchstart',{bubbles:true,touches:[t(400)],changedTouches:[t(400)]}));
      document.body.dispatchEvent(new TouchEvent('touchmove',{bubbles:true,touches:[t(340)],changedTouches:[t(340)]}))}""")
    show(KB, 160)
    s = state(pg)
    if s['sy'] != 160: fail('자판이 뜬 채 손가락으로 끈 화면을 되돌림: %s' % s)
    elif s['vvt'] != '160px' or s['strip'] != '160px': fail('A3 밀린 채 남은 화면에서 띠가 보이는 화면 위(160)로 안 따라옴: %s' % s)
    else: print('끌어 민 화면은 그대로 · 띠는 보이는 화면 위(--vvt 160) ok', s)
    hide()

    # ---- N1 자판 위 알림 ----
    show(KB)
    pg.fill('#lgUser', '뮻12'); focus('#lgPass'); pg.wait_for_timeout(500)
    t = pg.evaluate("""(()=>{const t=document.getElementById('toast'),r=t.getBoundingClientRect(),f=document.activeElement.getBoundingClientRect();
      return {show:t.classList.contains('show'),txt:t.textContent,top:Math.round(r.top),bottom:Math.round(r.bottom),h:Math.round(r.height),val:document.getElementById('lgUser').value,
        up:document.documentElement.classList.contains('kbup'),field:[Math.round(f.top),Math.round(f.bottom)]}})()""")
    if t['val'] != 'abc12' or not t['show']: fail('N1 준비: 한글 자판 아이디가 영문으로 안 바뀜/알림 없음 %s' % t)
    elif t['bottom'] > VIS - 4 or t['top'] < SAT: fail('N1 자판이 떠 있는데 알림이 보이는 화면(상태바 밑 ~ 자판 위 %d) 밖: %s' % (VIS, t))
    elif not (t['bottom'] <= t['field'][0] or t['top'] >= t['field'][1]): fail('N1 알림이 치고 있는 칸(비밀번호)을 가림: %s' % t)
    elif t['h'] > 60: fail('N1 알림이 여러 줄로 접힘: %s' % t)
    else: print('N1 알림이 보이는 화면 위쪽 한 줄 ok', t)
    hide()

    # ---- 가입 · 팀 · 예배 (연습 화면 준비) ----
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName'); pg.check('#lgAgree')
    pg.fill('#lgName', '자판'); pg.fill('#lgUser', 'kb' + tag); pg.fill('#lgPass', 'secret12'); pg.click('[data-act="lg-submit"]')
    pg.wait_for_selector('#gtTeam', timeout=15000); pg.fill('#gtTeam', '자판팀' + tag); pg.click('[data-act="team-create"]')
    pg.wait_for_selector('.shell[data-page]', timeout=15000); pg.wait_for_timeout(600)
    for _ in range(3):
      if pg.locator('#modal .ov').count(): pg.evaluate("CONTI.closeModal()"); pg.wait_for_timeout(300)
    pg.evaluate("document.querySelector('[data-act=\"new-svc\"]').click()"); pg.wait_for_selector('[data-f="svc.name"]', timeout=8000)
    pg.evaluate("document.querySelector('[data-act=\"add-item\"]').click()"); pg.wait_for_selector('[data-f="item.title"]')
    pg.fill('[data-f="item.title"]', 'Afresh'); pg.locator('[data-f="item.title"]').blur(); pg.wait_for_timeout(300)
    sid = pg.evaluate("""async()=>{const c=document.createElement('canvas');c.width=1000;c.height=1300;const x=c.getContext('2d');x.fillStyle='#fff';x.fillRect(0,0,1000,1300);
      x.strokeStyle='#000';for(let s=0;s<5;s++)for(let l=0;l<5;l++){x.beginPath();x.moveTo(40,120+s*240+l*14);x.lineTo(960,120+s*240+l*14);x.stroke()}
      const blob=await new Promise(r=>c.toBlob(r,'image/png'));const id='kbimg'+Date.now();await CONTI.IDB.put('blobs',id,blob);
      const sv=CONTI.S.services.find(s=>s.id===CONTI.route().a);const it=sv.items[0];it.form='A – B – C';
      it.media.push({id:'kbm1',type:'youtube',url:'https://youtu.be/dQw4w9WgXcQ',name:'',start:0,end:0,notes:[],sessions:[]});
      it.pieces.push({id:'kbp1',blob:id,w:1000,h:1300,gaps:[],markers:[{id:'mA',label:'A',x:50,y:100,cut:null},{id:'mB',label:'B',x:50,y:580,cut:null}],hls:[],name:'',chords:[],sheetKey:'',keyConfirmed:false,offset:null});
      sv.updatedAt=Date.now();CONTI.save();return sv.id}""")
    pg.wait_for_timeout(500)

    # ---- N4 편집기 곡 제목: 밀림 380 → 스크롤 칸이 대신 ----
    pg.evaluate("(s)=>{location.hash='#/edit/'+s}", sid); pg.wait_for_selector('[data-f="item.title"]', timeout=8000); pg.wait_for_timeout(600)
    pg.evaluate("document.querySelector('#app .ws').scrollTop=0"); pg.wait_for_timeout(100)
    y0 = pg.evaluate("Math.round(document.querySelector('[data-f=\"item.title\"]').getBoundingClientRect().top)")
    bar0 = pg.evaluate("Math.round(document.querySelector('#app .ws').getBoundingClientRect().top)")
    focus('[data-f="item.title"]'); show(KB, 380)
    s = state(pg); ws = pg.evaluate("Math.round(document.querySelector('#app .ws').scrollTop)")
    bar = pg.evaluate("Math.round(document.querySelector('#app .ws').getBoundingClientRect().top)")
    if y0 + 38 <= VIS - 12: fail('N4 준비: 곡 제목이 처음부터 자판 위(%d) — 검사가 헛돎' % y0)
    if s['sy'] != 0: fail('N4 편집기 곡 제목에서 창이 밀린 채(편집기 바·날짜가 시계 밑): %s ws=%d' % (s, ws))
    elif ws < 300: fail('N4 편집기 스크롤 칸이 대신 안 올라감: ws=%d %s' % (ws, s))
    elif not (SAT <= s['r'][0] and s['r'][1] <= VIS - 12): fail('N4 곡 제목 칸이 자판 위·상태바 아래에 없음: %s' % s)
    elif bar != bar0: fail('N4 편집기 머리(.ws 위 가장자리)가 움직임 %d→%d' % (bar0, bar))
    else: print('N4 편집기 곡 제목 밀림 380 → 스크롤 칸 %d · 창 0 ok' % ws, s)
    hide()

    # ---- N3 설정 기타 카포: 밀어야 하고 스크롤 칸이 없다 → 밀린 채 두되 띠는 따라온다 ----
    pg.evaluate("()=>{location.hash='#/settings'}"); pg.wait_for_selector('#sCapo', timeout=8000); pg.wait_for_timeout(500)
    cy = pg.evaluate("Math.round(document.querySelector('#sCapo').getBoundingClientRect().bottom)")
    focus('#sCapo'); show(KB, 374)
    s = state(pg)
    if cy <= VIS - 12: print('N3 참고: 카포 칸이 처음부터 자판 위(%d) — 되돌림 검사로 본다' % cy)
    if cy > VIS - 12 and s['sy'] != 374: fail('N3 칸을 보이려면 밀어야 하는데 되돌림: %s' % s)
    elif s['vvt'] != '%dpx' % s['sy'] or s['strip'] != '%dpx' % s['sy']: fail('N3 밀린 동안 상태바 띠가 보이는 화면 위에 없음(시계 밑으로 글이 지나감): %s' % s)
    elif not (s['r'][1] <= VIS): fail('N3 카포 칸이 자판 밑: %s' % s)
    else: print('N3 설정 카포 밀림 %d · 띠 --vvt %s ok' % (s['sy'], s['vvt']))
    hide()

    # ---- B3 연습 화면 메모 창 ----
    pg.evaluate("(s)=>{location.hash='#/play/'+s+'/0'}", sid); pg.wait_for_selector('.mkabs', timeout=10000); pg.wait_for_timeout(800)
    show(KB)
    pg.evaluate("document.querySelector('.mkabs[data-marker=\"mB\"]').scrollIntoView({block:'center'})"); pg.wait_for_timeout(200)
    pg.tap('.mkabs[data-marker="mB"]'); pg.wait_for_selector('#cText', timeout=6000); pg.wait_for_timeout(400)
    k = pg.evaluate("""(()=>{const r=s=>{const b=document.querySelector(s).getBoundingClientRect();return [Math.round(b.top),Math.round(b.bottom)]};const sm=document.querySelector('#modal .sheetm');
      return {ae:document.activeElement.id,inp:r('#cText'),save:r('#cSave'),sheet:r('#modal .sheetm'),over:sm.scrollHeight>sm.clientHeight+1,time:!!document.querySelector('#cTime'),
        up:document.documentElement.classList.contains('kbup'),pos:getComputedStyle(document.querySelector('#cSave').closest('.row')).position}})()""")
    if k['ae'] != 'cText' or not k['up'] or not k['time']: fail('B3 준비: 연습 메모 창(재생 시각 줄)에 커서·자판이 안 섬 %s' % k)
    elif not k['over']: print('B3 참고: 메모 창이 자판 위 빈자리에 다 들어감 %s' % k)
    if k['save'][1] > VIS or k['save'][0] < k['inp'][1]: fail('B3 연습 메모 창의 저장이 자판 밑(시트 안 스크롤 밑): %s' % k)
    elif k['inp'][0] < SAT or k['inp'][1] > VIS: fail('B3 메모 칸이 안 보임: %s' % k)
    elif k['sheet'][0] < SAT: fail('B3 시트 머리가 상태바(시계) 밑: %s' % k)
    else: print('B3 연습 메모 창 저장 줄이 자판 위 ok', k)
    # iOS 가 창을 237 민 채(사용자가 칸을 다시 누름) — 자판 높이는 레이아웃 화면으로 잰다
    pg.wait_for_timeout(1600)   # 포커스 직후의 되돌림이 끝난 뒤
    pg.evaluate("window.scrollTo(0,237)"); pg.wait_for_timeout(250)
    s = state(pg)
    sv = pg.evaluate("(()=>{const b=document.querySelector('#cSave').getBoundingClientRect();return [Math.round(b.top),Math.round(b.bottom)]})()")
    if s['sy'] != 237: fail('B3 준비: 창이 안 밀림 %s' % s)
    elif s['kb'] != '%dpx' % (H - VIS - 237) or s['kbt'] != '237px': fail('B3 창이 밀린 채 자판 높이를 잘못 잼(offsetTop 두 번 뺌): --kb %s --kbt %s (바라는 것 %dpx·237px)' % (s['kb'], s['kbt'], H - VIS - 237))
    elif sv[1] > 237 + VIS: fail('B3 창이 밀린 채 저장이 자판 밑: %s %s' % (sv, s))
    else: print('B3 밀린 창(237)에서 --kb %s · 저장 %s ok' % (s['kb'], sv))
    pg.evaluate("CONTI.closeModal()"); hide()
    c.close()

    # ================= 컴퓨터 웹 — 그대로 =================
    c = b.new_context(viewport={'width': 1300, 'height': 900}, service_workers='block')
    pg = c.new_page(); pg.on('pageerror', lambda e: errs.append('web: %s' % e))
    pg.goto(URL); pg.wait_for_selector('#lgUser', timeout=15000); pg.wait_for_timeout(300)
    pg.click('#lgUser'); pg.wait_for_timeout(300)
    w = pg.evaluate("[getComputedStyle(document.body,'::before').top,document.documentElement.classList.contains('kbup'),scrollY]")
    if w != ['0px', False, 0]: fail('컴퓨터 웹에서 칸을 눌러도 띠·창이 움직임: %s' % w)
    else: print('컴퓨터 웹 그대로 ok', w)
    c.close(); b.close()
    bad = [e for e in errs if 'ResizeObserver' not in e]
    if bad: fail('페이지 오류: %s' % bad[:3])
  if FAILS:
    print('\n%d개 실패' % len(FAILS)); sys.exit(1)
  print('OK test_simfix_keyboard')

run()
