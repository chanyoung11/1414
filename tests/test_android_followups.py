# 안드로이드 점검 뒤따름(2026-09-27 검증에서 나온 네 가지) 되돌림 방지
#
# 사용: CONTI_URL=http://localhost:8766/ .venv/bin/python tests/test_android_followups.py   (개발 서버가 떠 있어야 한다)
#      SOFT=1 이면 실패해도 끝까지 간다 (고치기 전 코드에서 전부 재현해 볼 때)
#
# 안드로이드 흉내: 픽셀 7(412x915 · 2.625배 · 터치 · 안드로이드 웹뷰 UA). 앱은 https://localhost 를 흉내 내고(NATIVE)
# 가짜 Capacitor(getPlatform 'android' · Printer.openAppSettings)를 넣는다. 마이크는 크롬의 가짜 장치로 실제 녹음한다.
#
# 본다
#  F1 (AND1-18 되돌림) 비밀번호 눈 단추: 안드로이드 웹뷰는 type 을 바꾸면 자판(IME)을 다시 붙이면서 커서를 맨 앞으로 돌린다
#     (흉내: type 이 바뀐 뒤 30·90ms 에 커서를 0 으로). 'abc123' · 눈 · '9' = 'abc1239' · 다시 눈 · '8' = 'abc12398' ·
#     포커스 그대로 — 로그인 · 가입 · 설정 계정(현재·새 비밀번호)
#  F2 (AND2-10) 마이크를 거절해 뜬 '마이크 권한이 꺼져 있어요 · 설정 열기'가 권한을 켜고 녹음하면 걷힌다 · 멈춘 뒤에도 · 창을 다시 열어도 없다
#  F3 (AND1-15 같은 종류) 라이브러리 '예배에 넣기'의 예배 칩 · 편성 창 머리 · 서버 /words 이름에 날짜가 두 번 찍히지 않는다
#     ('10/04 10/4 주일 오전예배' 아님)
#  F4 녹음 올리기는 한 번만: 느린 올리기 중에 창을 닫고 다시 열면 '올리는 중'(올리기·녹음 막힘) · 막힌 단추를 억지로 눌러도 새로 안 올림 ·
#     끝나면 다시 연 창이 닫히고 올리지 않은 녹음이 사라짐 · 서버에 하나 · 등록 응답을 잃고 '다시 올리기'를 눌러도 서버에 하나(같은 표) ·
#     서버: 같은 표(clientId)는 같은 파일 자리 · 같은 자리를 두 번 등록하면 같은 녹음(dup) · 표 없는 옛 앱은 예전처럼 새 자리
#     느린 망: 웹뷰가 커널 버퍼에 한꺼번에 넘긴(88%) 뒤 오래 소식이 없어도 멀쩡한 올리기를 60초에 끊지 않는다 (재검증 — 기기에서 2MB 가 60초에 끊김)
import os, sys, re, time, json, struct, datetime
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
SRV = urlparse(URL)
tag = str(int(time.time()))[-7:]
SOFT = os.environ.get('SOFT') == '1'
SHOTS = os.environ.get('SHOTS')
FAILS = []
def fail(m):
  print('FAIL:', m)
  if SOFT: FAILS.append(m); return
  sys.exit(1)

UA_AND = 'Mozilla/5.0 (Linux; Android 16; Pixel 7 Build/CP31; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/151.0.0.0 Mobile Safari/537.36'
PHONE = dict(viewport={'width': 412, 'height': 915}, device_scale_factor=2.625, is_mobile=True, has_touch=True, user_agent=UA_AND)

MOCK = r"""
(() => {
  const cap = window.__cap = { settings: 0, style: [] };
  const P = (v) => Promise.resolve(v);
  window.Capacitor = {
    getPlatform: () => 'android', isNativePlatform: () => true, isPluginAvailable: () => false,
    Plugins: {
      StatusBar: { setStyle: (o) => { cap.style.push(o.style); return P(); }, setBackgroundColor: () => P(), hide: () => P(), show: () => P() },
      App: { addListener: () => P({ remove() {} }), getLaunchUrl: () => P(undefined), exitApp: () => P(), minimizeApp: () => P(), getInfo: () => P({}) },
      SplashScreen: { hide: () => P() },
      KeepAwake: { keepAwake: () => P(), allowSleep: () => P() },
      Printer: { setWindowBackground: () => P(), openAppSettings: () => { cap.settings++; return P(); } },
    },
  };
  try { localStorage.setItem('conti-theme', 'light'); localStorage.setItem('conti-push-asked', '1'); } catch (e) {}
})();
"""

# 안드로이드 자판(IME) 다시 붙기 흉내: 칸의 type 이 바뀌면 조금 뒤(30·90ms) 커서를 맨 앞(0)으로 돌린다
IME = r"""
window.__ime = (sel) => { const i = document.querySelector(sel); if (!i || i.__ime) return; i.__ime = 1;
  new MutationObserver(() => [30, 90].forEach((t) => setTimeout(() => { try { if (document.activeElement === i) i.setSelectionRange(0, 0); } catch (e) {} }, t)))
    .observe(i, { attributes: true, attributeFilter: ['type'] }); };
"""

# 마이크: __micDeny 이면 거절(NotAllowedError — 두 번 거절한 안드로이드처럼 곧바로), 아니면 크롬 가짜 장치로 실제 녹음
MIC = r"""
(() => { const md = navigator.mediaDevices; if (!md || !md.getUserMedia) return; const orig = md.getUserMedia.bind(md);
  window.__micDeny = false; window.__micAsk = 0;
  md.getUserMedia = (c) => { window.__micAsk++; return window.__micDeny ? Promise.reject(new DOMException('denied', 'NotAllowedError')) : orig(c); }; })();
"""

# 느린 올리기(R2 PUT) 흉내: __slowPut ms 만큼 늦게 보낸다 · 보낸 PUT 을 센다
SLOWPUT = r"""
(() => { const o = XMLHttpRequest.prototype.open, s = XMLHttpRequest.prototype.send; window.__puts = 0; window.__slowPut = 0;
  XMLHttpRequest.prototype.open = function (m) { this.__put = String(m).toUpperCase() === 'PUT'; return o.apply(this, arguments); };
  XMLHttpRequest.prototype.send = function (b) { if (this.__put) { window.__puts++; const d = window.__slowPut; if (d) { setTimeout(() => s.call(this, b), d); return; } }
    return s.call(this, b); }; })();
"""

# 느린 망의 커널 버퍼 흉내: __stallPut 이면 PUT 을 보내지 않고, 곧 88%를 한꺼번에 넘긴 진행 소식 하나만 주고 멈춘다
# (에뮬레이터 umts 에서 2MB 녹음이 0.5초에 88% → 65초 뒤에야 100% · 451초에 끝남). 올리기의 멈춤 감시(kick 이 건 30초 이상 setTimeout)를 적는다
STALLPUT = r"""
(() => { const s = XMLHttpRequest.prototype.send, st = window.setTimeout; window.__stallPut = 0; window.__stallX = null; window.__tmo = [];
  window.setTimeout = function (f, ms) { if (+ms >= 30000 && /\bkick\b/.test(new Error().stack || '')) window.__tmo.push(+ms); return st.apply(this, arguments); };
  XMLHttpRequest.prototype.send = function (b) { if (this.__put && window.__stallPut) { const x = this; window.__stallX = x; const n = (b && b.size) || 0;
      st(() => { if (x.upload.onprogress) x.upload.onprogress({ lengthComputable: true, loaded: Math.round(n * 0.88), total: n }); }, 100); return; }
    return s.call(this, b); }; })();
"""

def wav_bytes(sec=1, rate=8000):
  n = sec * rate; data = b'\x00\x00' * n
  return b'RIFF' + struct.pack('<I', 36 + len(data)) + b'WAVEfmt ' + struct.pack('<IHHIIHH', 16, 1, 1, rate, rate * 2, 2, 16) + b'data' + struct.pack('<I', len(data)) + data

def kst_today(): return (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=9)).date()
def md(d): return '%d/%d' % (d.month, d.day)
DUP = re.compile(r'(?<![0-9])(\d{1,2})/0?(\d{1,2}) \1/\2(?![0-9])')

def run():
  with sync_playwright() as p:
    b = p.chromium.launch(args=['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'])
    errs = []

    def handler(route):
      u = urlparse(route.request.url)
      if u.scheme == 'https' and u.hostname in ('localhost', 'lets1414.com', 'www.lets1414.com') and u.port is None:
        try: return route.fulfill(response=route.fetch(url='%s://%s/%s' % (SRV.scheme, SRV.netloc, u.path.lstrip('/')) + ('?' + u.query if u.query else '')))
        except Exception:
          try: return route.abort()
          except Exception: return
      if u.hostname == SRV.hostname and u.port == SRV.port: return route.continue_()
      return route.abort()   # 바깥(글꼴 CDN)은 막는다

    def native():
      c = b.new_context(service_workers='block', **PHONE)
      c.route('**/*', handler)
      c.add_init_script(MOCK); c.add_init_script(IME); c.add_init_script(MIC)
      pg = c.new_page(); pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('dialog', lambda d: d.accept())
      return c, pg

    def api(pg, method, path, body=None):
      return pg.evaluate("""async([m,p,b])=>{const t=localStorage.getItem('conti-app-token')||'';const r=await fetch('https://lets1414.com/api'+p,{method:m,credentials:'include',
        headers:{'x-conti':'1','x-conti-app':'1','content-type':'application/json',...(t?{authorization:'Bearer '+t}:{})},body:b?JSON.stringify(b):undefined});
        let j=null;try{j=await r.json()}catch(e){}return {status:r.status,j}}""", [method, path, body])

    def shot(pg, name):
      if SHOTS: os.makedirs(SHOTS, exist_ok=True); pg.screenshot(path=os.path.join(SHOTS, name + '.png'))

    def toast_seen(pg, ms=4000):
      seen = []; end = time.time() + ms / 1000
      while time.time() < end:
        t = pg.evaluate("(()=>{const t=document.getElementById('toast');return t&&t.classList.contains('show')?t.textContent:''})()")
        if t and t not in seen: seen.append(t)
        pg.wait_for_timeout(100)
      return seen

    # ================= F1 비밀번호 눈 단추 커서 =================
    c, pg = native()
    pg.goto('https://localhost/'); pg.wait_for_selector('#lgUser', timeout=15000); pg.wait_for_timeout(300)

    def caret_check(sel, label):
      if not pg.locator('%s ~ .pweye' % sel).count(): fail('F1 %s 비밀번호 칸(%s)에 눈 단추가 없음' % (label, sel)); return
      pg.evaluate('(s)=>window.__ime(s)', sel)
      pg.tap(sel); pg.fill(sel, ''); pg.wait_for_timeout(100)
      pg.keyboard.type('abc123'); pg.wait_for_timeout(100)
      pg.tap('%s ~ .pweye' % sel); pg.wait_for_timeout(700)
      s1 = pg.evaluate("(s)=>{const i=document.querySelector(s);return {type:i.type,focus:document.activeElement===i,ss:i.selectionStart,se:i.selectionEnd}}", sel)
      pg.keyboard.type('9'); pg.wait_for_timeout(100); v1 = pg.input_value(sel)
      pg.tap('%s ~ .pweye' % sel); pg.wait_for_timeout(700)
      s2 = pg.evaluate("(s)=>{const i=document.querySelector(s);return {type:i.type,focus:document.activeElement===i,ss:i.selectionStart,se:i.selectionEnd}}", sel)
      pg.keyboard.type('8'); pg.wait_for_timeout(100); v2 = pg.input_value(sel)
      # 눈 단추 바로 뒤에 전체를 골라 새로 쳐도(칸 채우기) 커서 되돌리기가 고른 것을 풀어 뒤에 덧붙이지 않는다.
      # 자판 흉내(30·90ms 에 커서 0)가 끝난 뒤(150ms)에 채운다 — 20ms 에 채우면 흉내가 fill 의 '전체 고르기'와 '넣기' 사이에 끼어
      # 고른 것을 접어 가끔 덧붙었다(앱이 아니라 흉내의 틈 · 네 번에 한 번꼴). 되돌리기가 전체 선택을 푸는지는 selectionchange 로 그대로 걸린다
      pg.tap('%s ~ .pweye' % sel); pg.wait_for_timeout(150); pg.fill(sel, 'secret12'); pg.wait_for_timeout(700); v3 = pg.input_value(sel)
      pg.tap('%s ~ .pweye' % sel); pg.wait_for_timeout(700)
      if v1 != 'abc1239': fail('F1 %s 눈 단추(보기) 뒤 친 글자가 맨 앞에 들어감: %r (커서 %s)' % (label, v1, s1))
      elif v2 != 'abc12398': fail('F1 %s 눈 단추(가리기) 뒤 친 글자가 맨 앞에 들어감: %r (커서 %s)' % (label, v2, s2))
      elif v3 != 'secret12': fail('F1 %s 눈 단추 바로 뒤 전체 선택 + 새로 치기가 덧붙음: %r' % (label, v3))
      elif not s1['focus'] or not s2['focus']: fail('F1 %s 눈 단추를 누르니 칸의 포커스(자판)가 빠짐: %s %s' % (label, s1, s2))
      elif s1['type'] != 'text' or s2['type'] != 'password': fail('F1 %s 보기·가리기가 안 바뀜: %s %s' % (label, s1, s2))
      else: print('F1 %s 눈 단추 뒤 커서 끝 · abc123→9→8 = %s ok' % (label, v2))
    caret_check('#lgPass', '로그인')
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName'); pg.check('#lgAgree')
    caret_check('#lgPass', '가입')
    uname = 'fu' + tag
    pg.fill('#lgName', '뒤따름'); pg.fill('#lgUser', uname); pg.fill('#lgPass', 'secret12'); pg.click('[data-act="lg-submit"]')
    pg.wait_for_selector('#gtTeam', timeout=15000); pg.fill('#gtTeam', 'zzqa뒤' + tag); pg.click('[data-act="team-create"]')
    pg.wait_for_selector('.shell[data-page]', timeout=15000); pg.wait_for_timeout(600)
    for _ in range(3):
      if pg.locator('#modal .ov').count(): pg.evaluate("CONTI.closeModal()"); pg.wait_for_timeout(300)
    team = pg.evaluate('CONTI.S.team.id')
    pg.evaluate("()=>{location.hash='#/settings'}"); pg.wait_for_selector('[data-act="set-tab"][data-t="account"]', timeout=8000)
    pg.click('[data-act="set-tab"][data-t="account"]'); pg.wait_for_selector('#sPw1', timeout=8000); pg.wait_for_timeout(200)
    caret_check('#sPw0', '설정 현재 비밀번호'); caret_check('#sPw1', '설정 새 비밀번호')
    pg.fill('#sPw0', ''); pg.fill('#sPw1', ''); pg.evaluate("document.activeElement&&document.activeElement.blur()")

    # ================= F3 날짜 두 번 =================
    r = api(pg, 'POST', '/teams/%s/recurring' % team, {'weekday': 0, 'label': '주일 오전예배', 'time': '11:00'})
    if r['status'] != 200: fail('정기 예배 만들기 실패: %s' % r)
    pg.evaluate("async()=>{await CONTI.SYNC.pullServices();await CONTI.pullSchedule(null,true)}"); pg.wait_for_timeout(500)
    pg.evaluate("()=>{location.hash='#/library'}"); pg.wait_for_timeout(500)
    pg.evaluate("CONTI.addToServiceSheet(['nosong'])"); pg.wait_for_selector('#atsSvc', timeout=5000)
    chips = pg.evaluate("[...document.querySelectorAll('#atsSvc [data-ats]')].filter(b=>b.dataset.ats!=='new').map(b=>b.childNodes[0].textContent.trim())")
    shot(pg, 'f3_chips')
    names = pg.evaluate("CONTI.S.services.filter(s=>s.date).map(s=>[s.date,s.name])")
    bad = [t for t in chips if DUP.search(t)]
    if not chips: fail('F3 준비: 예배에 넣기에 예배 칩이 없음 (예배 %s)' % names[:3])
    elif bad: fail('F3 예배에 넣기 칩에 날짜가 두 번: %s' % bad[:2])
    elif not all('주일 오전예배' in t and re.match(r'^\d{1,2}/\d{1,2} ', t) for t in chips): fail('F3 예배 칩이 날짜 + 이름이 아님: %s' % chips[:2])
    else: print('F3 예배에 넣기 칩 ok', chips[:2])
    pg.evaluate("CONTI.closeModal()"); pg.wait_for_timeout(200)
    # 편성 창 머리 · 서버 /words: 이름에 이미 날짜가 든 사역 날짜
    d1 = kst_today() + datetime.timedelta(days=10)
    lab = '%s 특별예배' % md(d1)
    r = api(pg, 'POST', '/teams/%s/dates' % team, {'date': d1.isoformat(), 'label': lab})
    did = ((r.get('j') or {}).get('date') or {}).get('id')
    if r['status'] != 200 or not did: fail('F3 준비: 날짜 추가 실패 %s' % r)
    else:
      pg.evaluate("async()=>{await CONTI.pullSchedule(null,true)}")
      pg.evaluate("(id)=>{location.hash='#/lineup/'+id}", did); pg.wait_for_selector('.lnhd b', timeout=10000); pg.wait_for_timeout(300)
      hd = pg.evaluate("document.querySelector('.lnhd b').textContent")
      shot(pg, 'f3_lineup')
      if hd != lab: fail('F3 편성 창 머리에 날짜가 두 번(또는 이름이 바뀜): %r (이름 %r)' % (hd, lab))
      else: print('F3 편성 창 머리 ok', hd)
      w = api(pg, 'GET', '/words?team=%s' % team)
      row = next((x for x in ((w.get('j') or {}).get('services') or []) if x.get('dateId') == did), None)
      if not row: fail('F3 서버 /words 에 새 날짜가 없음: %s' % json.dumps(w)[:300])
      elif row.get('name') != lab: fail('F3 서버 /words 이름에 날짜가 두 번: %r' % row.get('name'))
      else: print('F3 서버 /words 이름 ok', row.get('name'))
    pg.evaluate("()=>{location.hash='#/home'}"); pg.wait_for_timeout(300)

    # ================= F2 마이크 안내 =================
    svc = pg.evaluate("CONTI.S.services.find(s=>s.date).id")
    pg.evaluate("()=>{window.__micDeny=true}")
    pg.evaluate("(id)=>CONTI.rehAddModal(CONTI.S.services.find(s=>s.id===id))", svc); pg.wait_for_selector('#rhRec')
    pg.tap('#rhRec'); pg.wait_for_timeout(400)
    t0 = pg.evaluate("document.getElementById('rhProg').innerText")
    if not pg.locator('#rhPerm').count() or '마이크' not in t0: fail('F2 준비: 마이크 거절에 설정 안내가 없음: %r' % t0)
    shot(pg, 'f2_denied')
    pg.evaluate("()=>{window.__micDeny=false}")   # 설정에서 켜고 돌아왔다
    pg.tap('#rhRec')
    try: pg.wait_for_function("document.getElementById('rhPick').textContent.indexOf('녹음 중')>=0", timeout=6000)
    except Exception: fail('F2 준비: 권한을 켠 뒤 녹음이 시작되지 않음: %r' % pg.evaluate("document.getElementById('rhPick').textContent"))
    t1 = pg.evaluate("document.getElementById('rhProg').innerText"); n1 = pg.locator('#rhPerm').count()
    shot(pg, 'f2_recording')
    pg.wait_for_timeout(1300); pg.tap('#rhRec')
    try: pg.wait_for_function("document.getElementById('rhPick').textContent.indexOf('방금 녹음')>=0", timeout=6000)
    except Exception: fail('F2 준비: 녹음을 멈춰도 방금 녹음이 안 됨')
    t2 = pg.evaluate("document.getElementById('rhProg').innerText"); n2 = pg.locator('#rhPerm').count()
    pg.evaluate("CONTI.closeModal()"); pg.wait_for_timeout(250)
    pg.evaluate("(id)=>CONTI.rehAddModal(CONTI.S.services.find(s=>s.id===id))", svc); pg.wait_for_selector('#rhRec')
    t3 = pg.evaluate("document.getElementById('rhProg').innerText"); n3 = pg.locator('#rhPerm').count(); pk3 = pg.evaluate("document.getElementById('rhPick').textContent")
    if n1 or '마이크 권한' in t1: fail('F2 권한을 켜고 녹음이 시작됐는데 마이크 권한 안내가 남음: %r' % t1)
    elif n2 or '마이크 권한' in t2: fail('F2 녹음을 멈춘 뒤에도 마이크 권한 안내가 남음: %r' % t2)
    elif n3 or '마이크 권한' in t3: fail('F2 창을 다시 열어도 마이크 권한 안내가 남음: %r' % t3)
    elif '올리지 않은 녹음' not in pk3: fail('F2 다시 연 창에 방금 녹음이 없음: %r' % pk3)
    else: print('F2 권한을 켜고 녹음하면 안내가 걷힘 · 멈춘 뒤 · 다시 열어도 없음 ok')
    pg.evaluate("CONTI.closeModal()")
    c.close()

    # ================= F4 녹음 한 번만 올리기 (웹 · 안드로이드 폰) =================
    c = b.new_context(service_workers='block', **PHONE)
    c.grant_permissions(['microphone'], origin='%s://%s' % (SRV.scheme, SRV.netloc))
    c.add_init_script("try{localStorage.setItem('conti-theme','light');localStorage.setItem('conti-push-asked','1')}catch(e){}")
    c.add_init_script(SLOWPUT); c.add_init_script(STALLPUT)
    pg = c.new_page(); pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('dialog', lambda d: d.accept())
    reqs = []
    pg.on('request', lambda rq_: reqs.append((rq_.method, urlparse(rq_.url).path)) if rq_.method in ('POST', 'PUT') else None)
    def n_req(m, path): return sum(1 for x in reqs if x[0] == m and x[1] == path)
    pg.goto(URL); pg.wait_for_selector('#lgUser', timeout=15000)
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName'); pg.check('#lgAgree')
    pg.fill('#lgName', '녹음'); pg.fill('#lgUser', 'fv' + tag); pg.fill('#lgPass', 'secret12'); pg.click('[data-act="lg-submit"]')
    pg.wait_for_selector('#gtTeam', timeout=15000); pg.fill('#gtTeam', 'zzqa녹' + tag); pg.click('[data-act="team-create"]')
    pg.wait_for_selector('.shell[data-page]', timeout=15000); pg.wait_for_timeout(500)
    for _ in range(3):
      if pg.locator('#modal .ov').count(): pg.evaluate("CONTI.closeModal()"); pg.wait_for_timeout(300)
    team = pg.evaluate('CONTI.S.team.id')
    rq = c.request; H = {'x-conti': '1'}
    sid = 'fu' + tag; day = (kst_today() + datetime.timedelta(days=3)).isoformat()
    doc = {'id': sid, 'name': '녹음예배' + tag, 'date': day, 'version': 1, 'items': [{'id': 'i1', 'title': '곡', 'key': 'G', 'pieces': [], 'media': [], 'notes': []}]}
    r = rq.put(URL + 'api/services/' + sid, headers=H, data={'teamId': team, 'doc': doc})
    if not r.ok: fail('발행 PUT 실패 %s %s' % (r.status, r.text()[:200]))
    pg.evaluate("CONTI.SYNC.pullServices()"); pg.wait_for_timeout(400)
    pg.evaluate("(id)=>{location.hash='#/view/'+id}", sid); pg.wait_for_selector('[data-act="reh-add"]', timeout=15000)
    def server_n():
      r = rq.get(URL + 'api/rehearsals?team=%s&service=%s' % (team, sid), headers=H)
      return len(r.json().get('rehearsals') or []) if r.ok else -1
    def sheet(): pg.click('[data-act="reh-add"]'); pg.wait_for_selector('#rhOk', timeout=5000); pg.wait_for_timeout(150)
    def st(): return pg.evaluate("""(()=>{const g=id=>document.getElementById(id);if(!g('rhOk'))return null;
      return {ok:g('rhOk').disabled,okt:g('rhOk').textContent,rec:g('rhRec').disabled,file:g('rhFile').disabled,prog:g('rhProg').innerText,pick:g('rhPick').textContent,label:g('rhLabel').value}})()""")

    # ---- 1. 느린 올리기 중에 창을 닫았다 다시 열기 ----
    sheet()
    pg.fill('#rhLabel', '느린연습')
    pg.tap('#rhRec')
    try: pg.wait_for_function("document.getElementById('rhPick').textContent.indexOf('녹음 중')>=0", timeout=6000)
    except Exception: fail('F4 준비: 녹음이 시작되지 않음 %s' % st())
    pg.wait_for_timeout(1500); pg.tap('#rhRec')
    pg.wait_for_function("document.getElementById('rhPick').textContent.indexOf('방금 녹음')>=0", timeout=6000)
    pg.evaluate("()=>{window.__slowPut=5000}")
    pg.tap('#rhOk'); pg.wait_for_timeout(700)
    a0 = st()
    pg.click('#modal [data-close]'); pg.wait_for_timeout(300)
    sheet(); a1 = st(); shot(pg, 'f4_reopen_busy')
    if not a1['ok'] or not a1['rec'] or not a1['file']: fail('F4 올리는 중에 다시 연 창에서 올리기·녹음·파일 고르기가 막히지 않음: %s' % a1)
    elif not any(k in a1['prog'] for k in ('올리는 중', '올릴 자리', '마무리')): fail('F4 다시 연 창에 올리는 중이라는 표시가 없음: %s' % a1)
    elif a1['label'] != '느린연습': fail('F4 다시 연 창에 올리는 중인 녹음 이름이 없음: %s' % a1)
    else: print('F4 올리는 중에 다시 연 창: 막힘 · 표시 %r ok' % a1['prog'])
    pg.evaluate("()=>{const b=document.getElementById('rhOk');b.disabled=false;b.click()}"); pg.wait_for_timeout(400)   # 억지로 한 번 더
    if n_req('POST', '/api/rehearsals/upload-url') != 1: fail('F4 올리는 중에 다시 연 창의 올리기가 새 올리기를 시작함 (upload-url %d번)' % n_req('POST', '/api/rehearsals/upload-url'))
    try: pg.wait_for_function("!document.getElementById('rhOk')", timeout=20000)
    except Exception: fail('F4 올리기가 끝나도 다시 연 창이 안 닫힘: %s' % st())
    seen = toast_seen(pg, 1500)
    n1 = server_n()
    sheet(); a2 = st(); pg.evaluate("CONTI.closeModal()"); pg.wait_for_timeout(200)
    c1 = (n_req('POST', '/api/rehearsals/upload-url'), n_req('POST', '/api/rehearsals'), pg.evaluate('window.__puts'))
    if n1 != 1: fail('F4 느린 올리기 + 다시 열기 뒤 서버의 녹음이 %d개 (하나여야)' % n1)
    elif c1 != (1, 1, 1): fail('F4 올리기가 겹침 (upload-url·등록·PUT) = %s' % (c1,))
    elif '올리지 않은 녹음' in a2['pick'] or not a2['ok']: fail('F4 올린 뒤 다시 열어도 올리지 않은 녹음이 남음(또 올릴 수 있음): %s' % a2)
    else: print('F4 느린 올리기 중 닫고 다시 열기: 서버 %d개 · 요청 %s · 다시 열면 비어 있음 · 토스트 %s ok' % (n1, c1, seen))
    pg.evaluate("()=>{window.__slowPut=0}")

    # ---- 2. 등록 응답을 잃고 '다시 올리기' ----
    LOST = []
    def lost(route):
      if route.request.method == 'POST' and not LOST:
        resp = route.fetch(); LOST.append(resp.status)   # 서버는 등록했는데 응답이 끊겼다
        return route.abort('internetdisconnected')
      return route.continue_()
    pred = lambda u: urlparse(u).path == '/api/rehearsals'
    sheet()
    pg.set_input_files('#rhFile', files=[{'name': 'reh.wav', 'mimeType': 'audio/wav', 'buffer': wav_bytes()}]); pg.wait_for_timeout(1200)
    c.route(pred, lost)
    pg.tap('#rhOk')
    try: pg.wait_for_function("(()=>{const b=document.getElementById('rhOk');return b&&!b.disabled&&b.textContent.indexOf('다시')>=0})()", timeout=15000)
    except Exception: fail('F4 등록 응답을 잃었는데 다시 올리기가 안 뜸: %s' % st())
    b1 = st(); c.unroute(pred, lost); shot(pg, 'f4_lost')
    n_lost = server_n()
    pg.tap('#rhOk')
    try: pg.wait_for_function("!document.getElementById('rhOk')", timeout=15000)
    except Exception: fail('F4 다시 올리기가 안 끝남: %s' % st())
    n2 = server_n()
    c2 = (n_req('POST', '/api/rehearsals/upload-url'), n_req('POST', '/api/rehearsals'), pg.evaluate('window.__puts'))
    if LOST != [200]: fail('F4 준비: 잃은 등록이 서버에서 안 됨 %s' % LOST)
    elif n_lost != 2: fail('F4 준비: 응답을 잃은 등록 뒤 서버 녹음 %d개' % n_lost)
    elif n2 != 2: fail('F4 등록 응답을 잃고 다시 올리니 같은 녹음이 또 생김: 서버 %d개 (둘이어야)' % n2)
    elif c2 != (3, 2, 2): fail('F4 다시 올리기가 파일을 또 올리거나 또 등록함 (upload-url·등록·PUT) = %s (3·2·2 여야)' % (c2,))
    else: print('F4 등록 응답을 잃고 다시 올리기: 서버 %d개 (같은 표 → 이미 있는 녹음) · 요청 %s · 안내 %r ok' % (n2, c2, b1['prog'][:30]))

    # ---- 3. 서버: 같은 표 · 같은 자리 · 옛 앱 ----
    def up_url(cid=None):
      body = {'teamId': team, 'size': 1000, 'mime': 'audio/mp4'}
      if cid: body['clientId'] = cid
      return rq.post(URL + 'api/rehearsals/upload-url', headers=H, data=body).json()
    o1, o2 = up_url(), up_url()
    k1, k2 = up_url('cid' + tag + 'abcdef'), up_url('cid' + tag + 'abcdef')
    if o1.get('blobId') == o2.get('blobId'): fail('F4 서버: 표 없는 옛 앱이 같은 자리를 받음 %s' % o1.get('blobId'))
    if k1.get('blobId') != k2.get('blobId') or not re.match(r'^r[0-9a-f]{16}$', k1.get('blobId') or ''): fail('F4 서버: 같은 표에 다른 자리 %s %s' % (k1.get('blobId'), k2.get('blobId')))
    pu = rq.put(k1['uploadUrl'], data=b'\x00' * 1000, headers={'content-type': 'audio/mp4'})
    if not pu.ok: fail('F4 서버: 준비 PUT 실패 %s' % pu.status)
    reg = {'teamId': team, 'serviceId': sid, 'blobId': k1['blobId'], 'pathname': k1['pathname'], 'date': day, 'label': 'API', 'duration': 1, 'clientId': 'cid' + tag + 'abcdef'}
    g1 = rq.post(URL + 'api/rehearsals', headers=H, data=reg).json(); g2 = rq.post(URL + 'api/rehearsals', headers=H, data=reg).json()
    k3 = up_url('cid' + tag + 'abcdef')
    id1 = (g1.get('rehearsal') or {}).get('id')
    if not id1 or g1.get('dup'): fail('F4 서버: 첫 등록 %s' % g1)
    elif (g2.get('rehearsal') or {}).get('id') != id1 or not g2.get('dup'): fail('F4 서버: 같은 자리를 두 번 등록하니 녹음이 또 생김 %s' % g2)
    elif (k3.get('rehearsal') or {}).get('id') != id1: fail('F4 서버: 이미 등록된 표로 upload-url 을 물었는데 그 녹음을 안 돌려줌 %s' % k3)
    elif server_n() != 3: fail('F4 서버: 녹음 수 %d (셋이어야)' % server_n())
    else: print('F4 서버: 옛 앱 새 자리 · 같은 표 같은 자리 · 두 번 등록 = 같은 녹음(dup) · 이미 등록된 표 ok')

    # ---- 4. 느린 망: 커널 버퍼에 한꺼번에 넘어간 뒤 오래 소식이 없어도 멀쩡한 올리기를 60초에 끊지 않는다 ----
    # (멈춤 감시가 88%에서 60초에 끊어 느린 망에서는 다시 올려도 늘 실패했다 — 재검증에서 기기로 확인)
    WAV2 = wav_bytes(60, 16000)   # 약 1.9MB
    sheet()
    pg.set_input_files('#rhFile', files=[{'name': 'big.wav', 'mimeType': 'audio/wav', 'buffer': WAV2}]); pg.wait_for_timeout(1200)
    pg.evaluate("()=>{window.__stallPut=1;window.__tmo=[]}")
    pg.tap('#rhOk')
    try: pg.wait_for_function("window.__stallX&&document.getElementById('rhProg').textContent.indexOf('88%')>=0", timeout=15000)
    except Exception: fail('F4 느린 망 준비: 88%% 진행이 안 보임: %s' % st())
    pg.wait_for_timeout(300)
    tmo = pg.evaluate('window.__tmo'); s4 = st()
    need = 60000 + 0.8 * len(WAV2) / 4096 * 1000   # 넘어간 1.7MB 가 4KB/s 로 빠질 시간
    if 60000 not in tmo: fail('F4 느린 망: 아무것도 안 넘어갔을 때의 멈춤 감시(60초)가 없음: %s' % tmo)
    elif not tmo or tmo[-1] < need: fail('F4 느린 망: 88%%를 넘긴 뒤 멈춤 감시가 %.0f초 — 커널 버퍼(%.1fMB)가 빠질 시간(%.0f초 이상)을 안 기다림' % ((tmo[-1] if tmo else 0) / 1000, len(WAV2) * 0.88 / 1048576, need / 1000))
    elif '88%' not in s4['prog'] or not s4['ok']: fail('F4 느린 망: 올리는 중 표시가 아님 %s' % s4)
    else: print('F4 느린 망: 88%% 뒤 멈춤 감시 %.0f초 (60초에 안 끊음) ok' % (tmo[-1] / 1000))
    pg.evaluate("()=>{window.__stallPut=0;const x=window.__stallX;if(x&&x.onerror)x.onerror()}")   # 끝내기: 끊긴 것으로
    try: pg.wait_for_function("(()=>{const b=document.getElementById('rhOk');return b&&!b.disabled&&b.textContent.indexOf('다시')>=0})()", timeout=8000)
    except Exception: fail('F4 느린 망: 끊긴 뒤 다시 올리기가 안 뜸: %s' % st())
    pg.evaluate("CONTI.closeModal()")
    c.close()

    if errs: fail('JS 오류: %s' % errs[:3])
    b.close()
  if FAILS:
    print('\n%d FAIL' % len(FAILS)); [print(' -', f) for f in FAILS]; sys.exit(1)
  print('\nOK test_android_followups')

if __name__ == '__main__':
  run()
