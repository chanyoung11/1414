# 보상형 광고(코드 인식 1곡) 화면 검사 — 가짜 AdMob 플러그인으로 앱(https://localhost)을 흉내 낸다.
#
# 사용: .venv/bin/python tests/test_reward_ui.py
#   이 검사는 자기 서버를 따로 켠다 (보상은 ENFORCE_PLAN=1 · ADMOB_REWARD_UNITS 가 있어야 켜져서, 다른 검사가 쓰는 개발
#   서버를 건드리지 않게). 로컬 도커 포스트그레스(54329)만 있으면 된다. 끝나면 서버·브라우저를 끄고 만든 것을 지운다.
#   서버 프로세스 안에 '구글 흉내'가 같이 뜬다: 우리 ECDSA 키로 된 키 파일(verifier-keys.json 모양)과,
#   구글처럼 서명한 SSV 콜백을 개발 서버의 /api/ads/ssv 로 보내는 곳(/fire). 밖으로 나가는 요청은 없다 (AI 는 가짜).
#
# 본다
#  · 설정 전에는 아무것도 없다: 웹 · 앱이라도 보상형 광고 단위(ADS.android.reward)가 비어 있으면 버튼·안내가 없다
#  · 광고 불러오기 실패(FailedToLoad) · 보여 주기 실패(FailedToShow) · 끝까지 안 보고 닫기 · 보여 주기가 시작되지 않음 →
#    '광고 불러오는 중…'에 멈추지 않고 끝나며, 까닭을 시트 안(role=status)에 적고, 다시 누를 수 있고, 리스너가 남지 않는다
#  · 광고에 넘기는 값: 서버가 준 보상 표(custom_data) · user_id 없음 · 설정한 단위 · 시험 모드(ADS.test)면 isTesting
#  · 끝까지 보면 '보상 확인 중…'(aria-busy) → 서버 확인이 오면 시트를 닫고 바로 인식 · 사용량은 10/10 그대로
#  · 확인을 기다리는 사이 시트를 닫고 다른 창을 열면 그 창을 닫지 않고, 받은 보상은 '받아 둔 1곡으로 인식'으로 남는다 →
#    누르면 광고 없이 인식
#  · 확인이 늦으면 '늦어지고 있어요' + [다시 확인] · 오늘 한도 / 이번 달 한도를 나눠 말한다
#  · 인식이 402 로 막혀(다른 기기가 한도를 다 씀) 시트를 열려는 사이 다른 창을 열었거나 편집기를 떠났으면 그 창·화면을
#    덮지 않는다 (길게 알리고 상단 바에 [광고 보고 인식]) · 아무것도 안 열었으면 시트가 뜬다
import os, sys, time, json, socket, subprocess, tempfile, threading, shutil, urllib.request
from urllib.parse import urlparse, quote
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.environ.get('CONTI_DB', 'postgres://postgres:pg@localhost:54329/postgres')
SHEET = os.path.join(ROOT, 'docs', 'sample_sheet.jpg')
UNIT = '5550001111'
tag = str(int(time.time()))[-6:]
def fail(m): print('FAIL:', m); raise SystemExit(1)

def free_port():
  s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p

def sql(query, *params):
  js = ('import("pg").then(async ({default:pg})=>{const c=new pg.Client({connectionString:%s});await c.connect();'
        'const r=await c.query(%s,%s);console.log(JSON.stringify(r.rows));await c.end()})') % (json.dumps(DB), json.dumps(query), json.dumps(list(params)))
  r = subprocess.run(['node', '--input-type=module', '-e', js], cwd=ROOT, capture_output=True, text=True, timeout=30)
  if r.returncode: fail('sql: ' + r.stderr[-300:])
  return json.loads(r.stdout.strip() or '[]')

# 서버 + 구글 흉내 (한 프로세스)
HELPER = r"""
import http from 'node:http';
import { generateKeyPairSync, sign, randomBytes } from 'node:crypto';
const kp = generateKeyPairSync('ec', { namedCurve: 'P-256' });
const spki = kp.publicKey.export({ type: 'spki', format: 'der' }).toString('base64');
const KEY_ID = '424242';
http.createServer(async (req, res) => {
  const u = new URL(req.url, 'http://x');
  if (u.pathname === '/keys.json') { res.setHeader('content-type', 'application/json'); return res.end(JSON.stringify({ keys: [{ keyId: +KEY_ID, base64: spki }] })); }
  if (u.pathname === '/fire') {
    // 구글처럼: 값은 퍼센트 인코딩해 보내고 서명은 디코딩한 쿼리에 (signature · key_id 는 맨 뒤)
    const f = { ad_network: '5450213213286189855', ad_unit: u.searchParams.get('unit'), custom_data: u.searchParams.get('cd'),
      reward_amount: '1', reward_item: 'song', timestamp: String(Date.now()), transaction_id: randomBytes(16).toString('hex') };
    const names = Object.keys(f).sort();
    const dec = names.map((k) => k + '=' + f[k]).join('&'), raw = names.map((k) => k + '=' + encodeURIComponent(f[k])).join('&');
    const sig = sign('sha256', Buffer.from(dec), { key: kp.privateKey, dsaEncoding: 'der' }).toString('base64url');
    const r = await fetch(`http://127.0.0.1:${process.env.PORT}/api/ads/ssv?${raw}&signature=${sig}&key_id=${KEY_ID}`);
    return res.end(await r.text());
  }
  res.statusCode = 404; res.end();
}).listen(+process.env.KEYPORT, '127.0.0.1');
await import(process.env.ROOT + '/scripts/dev.mjs');
"""

def start_server():
  port, kport = free_port(), free_port()
  blob = tempfile.mkdtemp(prefix='rwui-blob-')
  env = {k: v for k, v in os.environ.items() if not k.startswith(('BLOB_READ_WRITE', 'R2_', 'GOOGLE_VISION', 'GOOGLE_APPLICATION'))}
  env.update({'ROOT': ROOT, 'DATABASE_URL': DB, 'AUTH_SECRET': 'local-dev-secret-0123456789', 'PORT': str(port), 'KEYPORT': str(kport),
              'ENFORCE_PLAN': '1', 'GEMINI_API_KEY': 'mock', 'BLOB_LOCAL_DIR': blob, 'BLOB_LOCAL_BASE': 'http://localhost:%d' % port,
              'ADMOB_REWARD_UNITS': 'ca-app-pub-5011605715320185/' + UNIT, 'ADMOB_KEYS_URL': 'http://127.0.0.1:%d/keys.json' % kport})
  subprocess.run(['node', 'scripts/migrate.mjs'], cwd=ROOT, env=env, capture_output=True, timeout=60, check=True)
  log = open(os.path.join(blob, 'server.log'), 'w')
  pr = subprocess.Popen(['node', '--input-type=module', '-e', HELPER], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
  for _ in range(100):
    try: urllib.request.urlopen('http://127.0.0.1:%d/api/ocr' % port, timeout=1)
    except urllib.error.HTTPError: break
    except Exception: time.sleep(0.2)
  else: pr.kill(); fail('서버가 안 켜짐')
  return pr, port, kport, blob

# 가짜 네이티브 셸 + 가짜 AdMob. mode: reward | late | dismiss | failload | failshow | hang
MOCK = r"""
(() => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const L = {};
  const emit = (n, d) => (L[n] || []).slice().forEach((f) => f(d));
  window.__ad = { mode: 'reward', calls: [], shows: 0, init: null, ssvDelay: 1500,
    active: () => Object.keys(L).filter((k) => k.startsWith('onRewardedVideoAd')).reduce((n, k) => n + L[k].length, 0) };
  const AdMob = {
    trackingAuthorizationStatus: async () => ({ status: 'authorized' }), requestTrackingAuthorization: async () => ({}),
    initialize: async (o) => { __ad.init = o; }, requestConsentInfo: async () => ({ status: 'NOT_REQUIRED' }), showConsentForm: async () => {},
    showBanner: async () => {}, hideBanner: async () => {}, removeBanner: async () => {},
    addListener: async (name, fn) => { (L[name] = L[name] || []).push(fn); return { remove: async () => { L[name] = (L[name] || []).filter((f) => f !== fn); } }; },
    prepareRewardVideoAd: async (o) => {
      __ad.calls.push(JSON.parse(JSON.stringify(o))); await sleep(150);
      if (__ad.mode === 'failload') { emit('onRewardedVideoAdFailedToLoad', { code: 3, message: 'No fill' }); throw new Error('No fill'); }
      emit('onRewardedVideoAdLoaded', { adUnitId: o.adId }); return { adUnitId: o.adId };
    },
    // 안드로이드 플러그인처럼: 보상을 받으면 끝나고, 닫기·보여 주기 실패는 이벤트로만 온다 (promise 는 안 끝남)
    showRewardVideoAd: () => new Promise((resolve) => {
      const m = __ad.mode, cd = (__ad.calls[__ad.calls.length - 1] || {}).ssv || {}; __ad.shows++;
      setTimeout(() => {
        if (m === 'failshow') { emit('onRewardedVideoAdFailedToShow', { code: 1, message: 'The ad has already been shown' }); return; }
        if (m === 'hang') return;
        emit('onRewardedVideoAdShowed', {});
        setTimeout(() => {
          if (m === 'reward' || m === 'late') {
            emit('onRewardedVideoAdReward', { type: 'song', amount: 1 }); resolve({ type: 'song', amount: 1 });
            if (m === 'reward') window.__ssvFire(cd.customData || '', __ad.ssvDelay);   // 구글이 서버를 부른다 (조금 뒤)
          }
          setTimeout(() => emit('onRewardedVideoAdDismissed', {}), 150);
        }, 300);
      }, 100);
    }),
  };
  // 보상 상태(/api/ads/reward?…)를 __hold ms 붙잡는다 — 시트가 상태를 기다리는 사이에 다른 일을 하는 검사용
  const realFetch = window.fetch.bind(window);
  window.__hold = 0; window.__held = 0;
  window.fetch = async (u, o) => {
    if (window.__hold && /\/api\/ads\/reward\?/.test(String(u && u.url || u))) { window.__held++; await sleep(window.__hold); }
    return realFetch(u, o);
  };
  window.Capacitor = {
    getPlatform: () => 'android', isNativePlatform: () => true, isPluginAvailable: () => false,
    Plugins: {
      AdMob,
      App: { addListener: () => Promise.resolve({ remove() {} }), getLaunchUrl: () => Promise.resolve(undefined), exitApp() {}, getInfo: () => Promise.resolve({}) },
      SplashScreen: { hide: () => Promise.resolve() },
    },
  };
})();
"""

def run():
  pr, port, kport, blob = start_server()
  BASE = 'http://127.0.0.1:%d/' % port
  made = {'team': None, 'user': None}
  try:
    with sync_playwright() as p:
      b = p.chromium.launch(); errs = []
      c = b.new_context(viewport={'width': 1100, 'height': 900}, service_workers='block')
      leaks = []
      NET = {'stale': False}   # 다른 기기가 한도를 다 쓴 것처럼: 이 기기는 /usage 에서 5/10 을 받는다 (서버는 10/10)
      def handler(route):
        u = urlparse(route.request.url)
        if (u.scheme == 'https' and u.hostname == 'localhost' and u.port is None) or u.hostname in ('lets1414.com', 'www.lets1414.com'):
          if NET['stale'] and u.path.startswith('/api/teams/') and u.path.endswith('/usage'):
            try:
              rr = route.fetch(url=BASE + u.path.lstrip('/') + ('?' + u.query if u.query else '')); j = rr.json(); j['ocr']['used'] = 5
              return route.fulfill(response=rr, body=json.dumps(j))
            except Exception:
              try: return route.abort()
              except Exception: return
          try: return route.fulfill(response=route.fetch(url=BASE + u.path.lstrip('/') + ('?' + u.query if u.query else '')))
          except Exception:
            try: return route.abort()
            except Exception: return
        if u.hostname in ('127.0.0.1', 'localhost') and u.port == port: return route.continue_()
        leaks.append(route.request.url); return route.abort()   # 바깥(글꼴 CDN 등)은 막는다 — 운영(lets1414.com)은 위에서 로컬로
      c.route('**/*', handler)
      c.add_init_script(MOCK)
      fired = []
      def ssv_fire(cd, delay):
        # 구글 → 우리 서버. 광고가 끝나고 조금 뒤에 온다
        def go():
          time.sleep((delay or 0) / 1000)
          try: fired.append(json.loads(urllib.request.urlopen('http://127.0.0.1:%d/fire?unit=%s&cd=%s' % (kport, UNIT, quote(cd, safe='')), timeout=10).read()))
          except Exception as e: fired.append({'err': str(e)})
        threading.Thread(target=go, daemon=True).start()
      c.expose_function('__ssvFire', ssv_fire)
      pg = c.new_page()
      pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('dialog', lambda d: d.accept())
      pg.goto('https://localhost/')
      if not pg.evaluate('/^(capacitor|ionic):/.test(location.protocol)||(location.hostname==="localhost"&&!location.port&&location.protocol==="https:")'): fail('앱 흉내가 안 됨 (NATIVE 아님)')
      pg.wait_for_selector('#lgUser', timeout=15000)
      pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName'); pg.check('#lgAgree')
      pg.fill('#lgName', '인도자'); pg.fill('#lgUser', 'rwui' + tag); pg.fill('#lgPass', 'secret12'); pg.click('[data-act="lg-submit"]')
      pg.wait_for_selector('#gtTeam', timeout=15000); pg.fill('#gtTeam', '광고보상팀' + tag); pg.click('[data-act="team-create"]')
      pg.wait_for_selector('.shell[data-page]', timeout=15000)
      team = pg.evaluate('CONTI.S.team.id'); made['team'] = team; made['user'] = pg.evaluate('CONTI.NET.user.id')
      month = time.strftime('%Y-%m', time.gmtime(time.time() + 9 * 3600))
      sql("insert into ai_songs(team_id, month, kind, song_key) select $1, $2, 'ocr', 'used'||g from generate_series(1,10) g on conflict do nothing", team, month)

      def new_song(title, first=False):
        if first:
          pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]'); pg.fill('[data-f="svc.name"]', '보상 예배')
        pg.click('[data-act="add-item"]'); pg.wait_for_selector('[data-f="item.title"]'); pg.fill('[data-f="item.title"]', title)
        pg.set_input_files('#pieceFile', [SHEET]); pg.wait_for_selector('.chordbar', timeout=15000); pg.wait_for_timeout(800)
      new_song('첫 곡', first=True)
      def bar(): return pg.inner_text('.chordbar')
      def refresh():
        pg.evaluate('(async()=>{await CONTI.pullUsage();CONTI.render()})()'); pg.wait_for_timeout(900)

      # ---- 설정 전: 아무것도 없다 ----
      refresh()
      if pg.evaluate('CONTI.PLANQ.ocr.used') != 10: fail('준비: 사용량 10 이 아님 %s' % pg.evaluate('CONTI.PLANQ.ocr'))
      if not pg.evaluate('CONTI.PLANQ.reward && CONTI.PLANQ.reward.on'): fail('서버가 보상 상태를 안 줌 %s' % pg.evaluate('CONTI.PLANQ.reward'))
      if pg.locator('.chordbar [data-act="ocr-reward"]').count() or '광고' in bar():
        fail('보상형 광고 단위가 비어 있는데 광고 버튼·안내가 보임: %s' % bar())
      if pg.evaluate('CONTI.rewardAvailable()'): fail('단위가 비어 있는데 rewardAvailable')
      print('설정 전(단위 없음) — 버튼·안내 없음 ok')

      # ---- 단위를 채우면 보인다 ----
      pg.evaluate("CONTI.ADS.android.reward='ca-app-pub-5011605715320185/%s'" % UNIT); refresh()
      btn = pg.locator('.chordbar [data-act="ocr-reward"]')
      if not btn.count() or '광고 보고 인식' not in btn.inner_text(): fail('단위를 채웠는데 광고 보고 인식 버튼이 없음: %s' % bar())
      if '광고를 보면 오늘 3곡 더' not in bar(): fail('안내 숫자가 서버 상태와 다름: %s' % bar())
      print('단위 설정 → 광고 보고 인식 버튼 · 오늘 3곡 안내 ok')

      pg.evaluate("CONTI.REWARD.poll={ms:400,n:20};CONTI.REWARD.lim.showMs=1500")
      def open_sheet():
        pg.locator('.chordbar [data-act="ocr-reward"]').last.click(); pg.wait_for_selector('#rwd #rwGo', timeout=8000); pg.wait_for_timeout(300)
      def go_and_wait(msg, timeout=15000):
        pg.click('#rwGo')
        pg.wait_for_function("m=>{const e=document.querySelector('#rwMsg');return e&&e.textContent.includes(m)}", arg=msg, timeout=timeout)
        pg.wait_for_function("!CONTI.REWARD.busy", timeout=5000)
      def after_fail(label, want_btn):
        st = pg.evaluate("({dis:document.querySelector('#rwGo').disabled,txt:document.querySelector('#rwGo').textContent,busy:CONTI.REWARD.busy,act:__ad.active(),role:document.querySelector('#rwMsg').getAttribute('role'),pro:document.querySelector('#rwPro').disabled})")
        if st['dis'] or want_btn not in st['txt']: fail('%s 뒤 버튼이 다시 안 살아남: %s' % (label, st))
        if st['busy'] or st['act']: fail('%s 뒤 busy·리스너가 남음: %s' % (label, st))
        if st['role'] != 'status' or st['pro']: fail('%s: 안내 자리가 role=status 가 아니거나 Pro 가 잠긴 채: %s' % (label, st))

      # ---- 불러오기 실패 ----
      pg.evaluate("__ad.mode='failload'")
      open_sheet()
      if pg.evaluate("document.activeElement&&document.activeElement.id") != 'rwGo': fail('시트를 열었는데 첫 버튼에 포커스가 없음')
      if '오늘 0/3' not in pg.inner_text('#rwN') or '이번 달 0/20' not in pg.inner_text('#rwN'): fail('시트 숫자: %s' % pg.inner_text('#rwN'))
      go_and_wait('광고를 불러올 수 없어요')
      after_fail('FailedToLoad', '다시 시도')
      print('FailedToLoad → 멈추지 않고 끝 · 시트 안 안내 · 다시 누를 수 있음 · 리스너 정리 ok')
      # ---- 보여 주기 실패 (안드로이드: promise 가 안 끝나고 이벤트만) ----
      pg.evaluate("__ad.mode='failshow'"); go_and_wait('광고를 보여 주지 못했어요'); after_fail('FailedToShow', '다시 시도')
      print('FailedToShow → 끝 ok')
      # ---- 보여 주기가 시작조차 안 됨 → 시간 제한 ----
      pg.evaluate("__ad.mode='hang'"); go_and_wait('광고를 보여 주지 못했어요'); after_fail('시작 안 됨', '다시 시도')
      print('보여 주기가 안 시작 → 시간 제한으로 끝 ok')
      # ---- 끝까지 안 보고 닫음 ----
      pg.evaluate("__ad.mode='dismiss'"); go_and_wait('끝까지 봐야'); after_fail('중간에 닫음', '다시 광고 보기')
      print('보상 없이 닫음 → 끝 · 다시 광고 보기 ok')
      if fired: fail('보상을 안 받았는데 서버 확인을 부름')
      st = pg.evaluate("fetch('https://lets1414.com/api/ads/reward?teamId='+CONTI.S.team.id,{headers:{'x-conti':'1','x-conti-app':'1',authorization:'Bearer '+localStorage.getItem('conti-app-token')}}).then(r=>r.json())")
      if st.get('today') != 0 or st.get('ready') != 0: fail('실패한 광고로 보상이 적힘: %s' % st)

      # ---- 광고에 넘기는 값 ----
      call = pg.evaluate("__ad.calls[__ad.calls.length-1]")
      if call.get('adId') != 'ca-app-pub-5011605715320185/' + UNIT or call.get('isTesting') is not False: fail('광고 단위·시험 모드 값: %s' % call)
      ssv = call.get('ssv') or {}
      if not str(ssv.get('customData', '')).startswith('r1.ocr.') or 'userId' in ssv: fail('custom_data 가 서버 보상 표가 아니거나 user_id 를 보냄: %s' % ssv)
      if len({json.dumps(x['ssv']) for x in pg.evaluate('__ad.calls')}) != len(pg.evaluate('__ad.calls')): fail('보상 표를 다시 씀')
      print('광고에 넘기는 값: 설정한 단위 · isTesting false · custom_data=서버 보상 표 · user_id 없음 ok')

      # ---- 끝까지 봄 → 확인 중 → 서버 확인 → 바로 인식 ----
      pg.evaluate("__ad.mode='reward';__ad.ssvDelay=2500")
      pg.click('#rwGo')
      pg.wait_for_function("(document.querySelector('#rwGo')||{}).textContent==='보상 확인 중…'", timeout=8000)
      st = pg.evaluate("({busy:document.querySelector('#rwd').getAttribute('aria-busy'),msg:document.querySelector('#rwMsg').textContent,pro:document.querySelector('#rwPro').disabled})")
      if st['busy'] != 'true' or '보상을 확인하고 있어요' not in st['msg'] or not st['pro']: fail('확인 중 상태가 안 보임: %s' % st)
      pg.wait_for_selector('#rwd', state='detached', timeout=15000)
      pg.wait_for_function("(()=>{const p=CONTI.S.services[0].items[0].pieces[0];return p.ocr==='done'&&(p.chords||[]).length>=5})()", timeout=30000)
      q = pg.evaluate('({ocr:CONTI.PLANQ.ocr,rw:CONTI.PLANQ.reward})')
      if q['ocr']['used'] != 10 or q['rw']['ready'] != 0: fail('보상으로 인식한 뒤 사용량·받아 둔 수: %s' % q)
      if not fired or not fired[-1].get('ok'): fail('서버 확인이 거절됨: %s' % fired)
      print('끝까지 봄 → 보상 확인 중(aria-busy) → 확인되면 닫고 바로 인식 · 사용량 10/10 그대로 ok')

      # ---- 확인을 기다리는 사이 닫고 다른 창을 열면: 그 창은 그대로, 보상은 받아 둔 것으로 ----
      new_song('둘째 곡')
      pg.evaluate("__ad.mode='reward';__ad.ssvDelay=3000")
      open_sheet(); pg.click('#rwGo')
      pg.wait_for_function("(document.querySelector('#rwGo')||{}).textContent==='보상 확인 중…'", timeout=8000)
      pg.click('#rwClose'); pg.wait_for_timeout(300)
      pg.evaluate("CONTI.modal('<div id=\"otherModal\"><b>결제 시트</b></div>')")
      pg.wait_for_function("CONTI.PLANQ.reward&&CONTI.PLANQ.reward.ready===1&&!CONTI.REWARD.busy", timeout=15000)
      pg.wait_for_timeout(300)
      if not pg.locator('#otherModal').count(): fail('확인이 끝나며 그 사이 연 다른 창을 닫음')
      if '받아 둔 1곡으로 인식' not in pg.inner_text('#toast'): fail('닫힌 뒤 결과를 알리지 않음: %s' % pg.inner_text('#toast'))
      pg.evaluate('CONTI.closeModal()'); pg.wait_for_timeout(500)
      b2 = pg.locator('.chordbar [data-act="ocr-reward"]').last
      if '받아 둔 1곡으로 인식' not in b2.inner_text(): fail('받아 둔 보상이 버튼에 안 보임: %s' % bar())
      if '광고로 받은 1곡이 남아 있어요' not in pg.locator('.chordbar:not(.slim)').last.inner_text(): fail('받아 둔 보상 안내 없음')
      shows = pg.evaluate('__ad.shows')
      open_sheet()
      if '받아 둔 1곡으로 인식' not in pg.inner_text('#rwGo'): fail('시트가 받아 둔 보상을 안 보임')
      pg.click('#rwGo'); pg.wait_for_selector('#rwd', state='detached', timeout=8000)
      pg.wait_for_function("(()=>{const p=CONTI.S.services[0].items[1].pieces[0];return p.ocr==='done'&&(p.chords||[]).length>=5})()", timeout=30000)
      if pg.evaluate('__ad.shows') != shows: fail('받아 둔 보상인데 광고를 또 보여 줌')
      if pg.evaluate('CONTI.PLANQ.reward.ready') != 0: fail('받아 둔 보상을 쓴 뒤 수가 안 줄어듦')
      print('기다리는 사이 연 다른 창은 그대로 · 보상은 받아 둔 것으로 · 누르면 광고 없이 인식 ok')

      # ---- 확인이 늦음 → 늦어지고 있어요 + 다시 확인 ----
      pg.evaluate("__ad.mode='late';CONTI.REWARD.poll={ms:200,n:5}")
      pg.evaluate("(()=>{const s=CONTI.S.services[0],it=s.items[1];CONTI.rewardSheet(s,it,it.pieces[0])})()"); pg.wait_for_selector('#rwd #rwGo')
      pg.wait_for_timeout(300)
      go_and_wait('보상 확인이 늦어지고 있어요')
      if '다시 확인' not in pg.inner_text('#rwGo'): fail('늦을 때 다시 확인 버튼이 없음')
      cd = pg.evaluate("__ad.calls[__ad.calls.length-1].ssv.customData")
      r = json.loads(urllib.request.urlopen('http://127.0.0.1:%d/fire?unit=%s&cd=%s' % (kport, UNIT, quote(cd, safe='')), timeout=10).read())
      if not r.get('ok'): fail('늦게 온 확인이 거절됨: %s' % r)
      pg.click('#rwGo'); pg.wait_for_function("(document.querySelector('#rwGo')||{}).textContent.includes('받아 둔 1곡으로 인식')", timeout=8000)
      print('확인이 늦으면 안내 + 다시 확인 → 받아 둔 1곡 ok')
      pg.click('#rwClose'); pg.wait_for_timeout(400)

      # ---- 오늘 한도 / 이번 달 한도를 나눠 말한다 ----
      sql("update ad_reward_grants set used_at=now(), used_key='x' where team_id=$1 and used_at is null", team)
      refresh()
      if pg.evaluate('CONTI.PLANQ.reward.today') != 3: fail('오늘 3개가 아님 %s' % pg.evaluate('CONTI.PLANQ.reward'))
      last = pg.locator('.chordbar:not(.slim)').last.inner_text()
      if '오늘 광고 인식 3곡도 다 썼어요' not in last or pg.locator('.chordbar [data-act="ocr-reward"]').count(): fail('오늘 한도 안내: %s' % last)
      pg.evaluate("(()=>{const s=CONTI.S.services[0],it=s.items[1];CONTI.rewardSheet(s,it,it.pieces[0])})()"); pg.wait_for_selector('#rwd #rwGo'); pg.wait_for_timeout(300)
      st = pg.evaluate("({dis:document.querySelector('#rwGo').disabled,txt:document.querySelector('#rwGo').textContent,p:document.querySelector('#rwP').textContent})")
      if not st['dis'] or '오늘 광고 인식을 다 썼어요' not in st['txt'] or '내일 다시' not in st['p']: fail('오늘 한도 시트: %s' % st)
      pg.click('#rwClose'); pg.wait_for_timeout(400)
      sql("update ad_reward_counts set n_month=20, day=day-1 where team_id=$1", team)
      refresh()
      last = pg.locator('.chordbar:not(.slim)').last.inner_text()
      if '이번 달 광고 인식 20곡도 다 썼어요' not in last: fail('이번 달 한도 안내: %s' % last)
      pg.evaluate("(()=>{const s=CONTI.S.services[0],it=s.items[1];CONTI.rewardSheet(s,it,it.pieces[0])})()"); pg.wait_for_selector('#rwd #rwGo'); pg.wait_for_timeout(300)
      st = pg.evaluate("({dis:document.querySelector('#rwGo').disabled,txt:document.querySelector('#rwGo').textContent,p:document.querySelector('#rwP').textContent})")
      if not st['dis'] or '이번 달 광고 인식을 다 썼어요' not in st['txt'] or '이번 달 광고 인식 20곡을 다 썼어요' not in st['p'] or '오늘' in st['txt']: fail('이번 달 한도 시트: %s' % st)
      pg.click('#rwClose'); pg.wait_for_timeout(400)
      print('오늘 한도 / 이번 달 한도를 나눠 안내 ok')

      # ---- 시험 모드: 설정 하나로 시험 광고 ----
      sql("delete from ad_reward_counts where team_id=$1", team); refresh()
      pg.evaluate("CONTI.ADS.test=true;__ad.mode='failload'")
      pg.evaluate("(()=>{const s=CONTI.S.services[0],it=s.items[1];CONTI.rewardSheet(s,it,it.pieces[0])})()"); pg.wait_for_selector('#rwd #rwGo'); pg.wait_for_timeout(300)
      go_and_wait('광고를 불러올 수 없어요')
      if pg.evaluate("__ad.calls[__ad.calls.length-1].isTesting") is not True: fail('ADS.test 인데 isTesting 이 아님')
      pg.evaluate("CONTI.ADS.test=false"); pg.click('#rwClose')
      print('시험 모드(ADS.test) → isTesting ok')
      if pg.evaluate('__ad.init') != {'initializeForTesting': False, 'testingDevices': []}: fail('초기화 값: %s' % pg.evaluate('__ad.init'))

      # ---- 인식이 402 로 막혀 시트를 열려는 사이: 다른 창을 열었거나 편집기를 떠났으면 덮지 않는다 ----
      # 다른 기기가 한도를 다 써 이 기기는 5/10 으로 안다 → [코드 인식] → [인식] → 서버 402 → 보상 상태를 받고 시트
      new_song('셋째 곡')
      pg.evaluate("__ad.mode='reward';window.__hold=0")
      def stale_ocr():
        # 앞에서 늦게 도착한 /usage 응답(10)이 낡은 값을 덮을 수 있어 몇 번 다시 받는다
        for _ in range(4):
          NET['stale'] = True; refresh(); NET['stale'] = False
          if pg.evaluate('CONTI.PLANQ.ocr.used') == 5: break
        else: fail('준비: 낡은 사용량(5)이 아님 %s' % pg.evaluate('CONTI.PLANQ.ocr'))
        b3 = pg.locator('.chordbar [data-act="ocr"]').last
        if not b3.count(): fail('준비: 낡은 사용량인데 [코드 인식] 버튼이 없음: %s' % bar())
        b3.click(); pg.wait_for_selector('#ocrGo', timeout=5000)
        pg.evaluate("document.querySelector('#toast').textContent=''")
      OTHER = "CONTI.modal('<div id=\"otherModal\"><b>메모</b><textarea id=\"memoTx\">쓰던 글</textarea></div>')"
      def settled():
        # 시트가 떴거나(고치기 전) 안내가 나왔다(고친 뒤) — 어느 쪽이든 끝난 것
        pg.wait_for_function("!!document.querySelector('#rwd')||document.querySelector('#toast').textContent.includes('이번 달 코드 인식')", timeout=20000)
        pg.wait_for_timeout(300)
      def kept(label):
        st = pg.evaluate("({other:!!document.querySelector('#otherModal'),memo:(document.querySelector('#memoTx')||{}).value,rwd:!!document.querySelector('#rwd'),toast:document.querySelector('#toast').textContent})")
        if not st['other'] or st['memo'] != '쓰던 글' or st['rwd']: fail('%s: 그 사이 연 창을 광고 시트가 덮음 %s' % (label, st))
        if '[광고 보고 인식]' not in st['toast']: fail('%s: 시트 대신 길게 알리지 않음 %s' % (label, st))
        pg.evaluate('CONTI.closeModal()'); pg.wait_for_timeout(400)
        b4 = pg.locator('.chordbar [data-act="ocr-reward"]').last
        if not b4.count() or '광고 보고 인식' not in b4.inner_text(): fail('%s: 상단 바에 [광고 보고 인식]이 없음 %s' % (label, bar()))

      # (0) 아무것도 안 열었으면 시트가 뜬다 (고친 뒤에도)
      stale_ocr(); pg.click('#ocrGo')
      pg.wait_for_selector('#rwd #rwGo', timeout=20000)
      if '광고 보고 1곡 인식' not in pg.inner_text('#rwGo'): fail('402 뒤 시트 버튼: %s' % pg.inner_text('#rwGo'))
      pg.click('#rwClose'); pg.wait_for_timeout(400)
      print('402 → 다른 창이 없으면 광고 시트 ok')
      # (1) [인식]을 누르자마자 메모 창을 연다 (402 가 오기 전)
      stale_ocr()
      pg.evaluate("document.querySelector('#ocrGo').click();" + OTHER)
      settled(); kept('402 전에 연 창')
      print('402 전에 연 메모 창(쓰던 글)은 그대로 · 안내 + 상단 바 [광고 보고 인식] ok')
      # (2) 402 뒤 보상 상태를 기다리는 사이에 연다
      stale_ocr()
      pg.evaluate("window.__hold=2000;window.__held=0;document.querySelector('#ocrGo').click()")
      pg.wait_for_function("window.__held>0", timeout=20000); pg.evaluate(OTHER)
      settled(); pg.evaluate("window.__hold=0"); kept('상태를 기다리는 사이 연 창')
      print('보상 상태를 기다리는 사이 연 창은 그대로 ok')
      # (3) 상단 바 [광고 보고 인식] → 상태를 기다리는 사이 편집기를 떠난다 → 다른 화면에 시트가 뜨지 않는다
      pg.evaluate("window.__hold=2000;window.__held=0;document.querySelector('#toast').textContent=''")
      pg.locator('.chordbar [data-act="ocr-reward"]').last.click()
      pg.wait_for_function("window.__held>0", timeout=10000); pg.evaluate("CONTI.go('')")
      settled(); pg.evaluate("window.__hold=0")
      st = pg.evaluate("({r:CONTI.route().name,rwd:!!document.querySelector('#rwd'),modal:!!document.querySelector('#modal').firstChild,toast:document.querySelector('#toast').textContent})")
      if st['r'] == 'edit' or st['rwd'] or st['modal'] or '[광고 보고 인식]' not in st['toast']: fail('편집기를 떠난 뒤 시트가 뜨거나 안내가 없음 %s' % st)
      if pg.evaluate('CONTI.REWARD.busy') or pg.evaluate('__ad.active()'): fail('떠난 뒤 busy·리스너가 남음')
      print('상태를 기다리는 사이 편집기를 떠나면 다른 화면에 시트가 안 뜸 · 안내 ok')

      if errs: fail('JS 오류: %s' % errs[:3])
      c.close()

      # ---- 웹은 그대로 (같은 팀 · 같은 한도 · 단위를 넣어도) ----
      w = b.new_context(viewport={'width': 1100, 'height': 900}, service_workers='block')
      w.route('**/*', lambda r: r.continue_() if urlparse(r.request.url).port == port else (leaks.append(r.request.url), r.abort()))
      wp = w.new_page(); wp.on('pageerror', lambda e: errs.append('web:' + str(e))); wp.on('dialog', lambda d: d.accept())
      wp.goto(BASE); wp.wait_for_selector('#lgUser', timeout=15000)
      wp.click('[data-act="lg-mode"][data-m="login"]'); wp.fill('#lgUser', 'rwui' + tag); wp.fill('#lgPass', 'secret12'); wp.click('[data-act="lg-submit"]')
      wp.wait_for_selector('.shell[data-page]', timeout=15000)
      wp.evaluate("CONTI.ADS.android.reward='ca-app-pub-5011605715320185/%s'" % UNIT)
      wp.click('[data-act="new-svc"]'); wp.wait_for_selector('[data-f="svc.name"]'); wp.fill('[data-f="svc.name"]', '웹 예배')
      wp.click('[data-act="add-item"]'); wp.wait_for_selector('[data-f="item.title"]'); wp.fill('[data-f="item.title"]', '웹 곡')
      wp.set_input_files('#pieceFile', [SHEET]); wp.wait_for_selector('.chordbar', timeout=15000); wp.wait_for_timeout(1200)
      wb = wp.inner_text('.chordbar')
      if wp.evaluate('CONTI.rewardAvailable()') or wp.locator('[data-act="ocr-reward"]').count() or '광고' in wb: fail('웹에 광고 보상 UI 가 보임: %s' % wb)
      if '이번 달 코드 인식 10곡을 다 썼어요' not in wb: fail('웹 한도 안내가 바뀜: %s' % wb)
      if errs: fail('JS 오류: %s' % errs[:3])
      print('웹은 그대로 — 광고 보상 UI 없음 ok')
      w.close(); b.close()
    print('OK — 보상형 광고 화면 검사 통과')
  finally:
    try:
      if made['team']: sql('delete from ad_ssv_seen where team_id=$1', made['team']); sql('delete from teams where id=$1', made['team'])
      if made['user']: sql('delete from users where id=$1', made['user'])
    except SystemExit: pass
    pr.terminate()
    try: pr.wait(timeout=10)
    except Exception: pr.kill()
    shutil.rmtree(blob, ignore_errors=True)

if __name__ == '__main__': run()
