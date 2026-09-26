# 아이폰 시뮬레이터 점검에서 나온 것 — 로그인·팀 (A1 A2 A4 A9 A10 A11)
#   CONTI_URL=http://localhost:8766/ CONTI_DB=postgres://postgres:pg@localhost:54329/postgres .venv/bin/python tests/test_simfix_auth_team.py
# - A1: 팀 만들기에서 고른 세션(건반)이 무시되고 늘 인도자로 만들어지던 것 · 둘을 누르면 둘 다 켜져 보이던 것 (하나만 고른다)
# - A2: 회원가입으로 들어온 사람이 로그아웃하면 '회원가입' 화면에 동의 체크가 켜지고 아이디가 채워진 채로 열리던 것
# - A4: 조용한 시간(기본 22~08시)에 「시험 알림 보내기」가 알림이 켜져 있어도 '보낼 기기가 없어요'였던 것
#   서버를 이 프로세스 안에서 띄워(web-push 는 가짜로) 조용한 시간 한가운데서 시험 발송이 나가고, 보통 알림은 여전히 걸러지는지 본다
# - A9: 「더보기」 아래 시트를 끌어내려도 닫히지 않던 것 — 멀리 끌거나 휙 내리면 닫히고, 조금 끌면 제자리, 누르기는 그대로 먹는다.
#   입력칸 위에서 시작했거나 안쪽이 스크롤된 채 끈 것은 닫지 않는다 (크로뮴 CDP 로 진짜 터치를 보낸다)
# - A10: 설정·팀·말씀(더보기로 가는 페이지)에서 하단 탭이 하나도 안 켜지던 것 → 「더보기」가 켜진다
# - A11: 종 드롭다운의 '새 알림이 없어요' 종 아이콘이 왼쪽 끝에 붙던 것 → 가운데
import os, sys, time, json, re, subprocess
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
URL = URL if URL.endswith('/') else URL + '/'
DB = os.environ.get('CONTI_DB', 'postgres://postgres:pg@localhost:54329/postgres')
tag = str(int(time.time()))[-6:]

def fail(m): print('FAIL:', m); sys.exit(1)

# ---------------------------------------------------------------- A4 (서버 안에서)
INPROC = r"""
process.env.DATABASE_URL = process.env.DB; process.env.AUTH_SECRET = process.env.AUTH_SECRET || 'local-dev-secret-0123456789';
process.env.VAPID_PUBLIC_KEY = 'BBq9nqw8YvL_wusVh4V6jQIXo-nph79oqnhr8VhzTfO67ssHN4FwThabeFwyq7YKeYl3lIOHJRklS6kfO8sbEVo';
process.env.VAPID_PRIVATE_KEY = 'Qy2iS5vLHI40osMnj_7AQwXeTtFRf0aP24RkV21cMY8';
process.env.GEMINI_API_KEY = 'mock';
for (const k of ['FCM_PROJECT_ID', 'FCM_USE_METADATA', 'APNS_KEY_ID']) delete process.env[k];
// 바깥으로는 아무것도 보내지 않는다: 웹 푸시 발송을 가짜로 바꿔 몇 번 불렸는지만 센다
const { createRequire } = await import('node:module');
const webpush = createRequire(process.env.ROOT + '/lib/push.js')('web-push');
const pushed = [];
webpush.sendNotification = async (sub, body) => { pushed.push({ endpoint: sub.endpoint, body: JSON.parse(body) }); return { statusCode: 201 }; };
const { default: api } = await import(process.env.ROOT + '/api/index.js');
const { sendPush } = await import(process.env.ROOT + '/lib/push.js');
const { q } = await import(process.env.ROOT + '/lib/db.js');
const call = (method, path, body, headers = {}) => new Promise((resolve) => {
  const h = {};
  const res = { statusCode: 200, setHeader(k, v) { h[k.toLowerCase()] = v; }, getHeader(k) { return h[k.toLowerCase()]; },
    end(s) { let j = null; try { j = JSON.parse(s); } catch {} resolve({ status: this.statusCode, body: j, headers: h }); } };
  api({ method, url: '/api' + path, headers: { 'x-conti': '1', 'content-type': 'application/json', ...headers }, body, socket: { remoteAddress: '127.0.0.1' } }, res);
});
const out = {};
const r = await call('POST', '/auth/signup', { username: 'sfq' + process.env.TAG, password: 'secret12', name: '밤' });
const uid = r.body.user.id, H = { cookie: String(r.headers['set-cookie']).split(';')[0] };
try {
  // 지금이 조용한 시간 한가운데가 되게 (KST 지금 시각 ~ 두 시간 뒤)
  const h = (new Date().getUTCHours() + 9) % 24;
  out.prefs = (await call('PATCH', '/me/prefs', { prefs: { quiet: { on: true, from: h, to: (h + 2) % 24 } } }, H)).status;
  out.sub = (await call('POST', '/push/subscribe', { sub: { endpoint: 'https://push.example.com/simfix/' + process.env.TAG,
    keys: { p256dh: 'BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM', auth: 'tBHItJI5svbpez7KI4CCXg' } } }, H)).status;
  // 보통 알림(발행)은 조용한 시간이라 폰을 울리지 않는다 — 그대로여야 한다
  out.normal = await sendPush([uid], { title: '발행', body: 'x', link: '#/home', type: 'publish' }, { type: 'publish' });
  out.normalPushed = pushed.length;
  const t = await call('POST', '/push/test', {}, H);
  out.test = { status: t.status, body: t.body };
  out.testPushed = pushed.map((p) => p.body.title);
} finally {
  await q('delete from push_subs where user_id=$1', [uid]);
  await q('delete from users where id=$1', [uid]);
}
console.log(JSON.stringify(out));
process.exit(0);
"""

def quiet_test_push():
    r = subprocess.run(['node', '--input-type=module', '-e', INPROC], cwd=ROOT, capture_output=True, text=True, timeout=90,
                       env={**os.environ, 'DB': DB, 'ROOT': ROOT, 'TAG': tag})
    line = (r.stdout.strip().splitlines() or [''])[-1]
    if r.returncode or not line.startswith('{'): fail('A4 서버 확인 실패: %s %s' % (r.stdout[-400:], r.stderr[-600:]))
    o = json.loads(line)
    print('A4', o)
    if o['prefs'] != 200 or o['sub'] != 200: fail('A4 준비 실패 (조용한 시간·구독): %s' % o)
    if o['normal'] != 0 or o['normalPushed'] != 0: fail('A4 보통 알림이 조용한 시간에 폰을 울림: %s' % o)
    if o['test']['status'] != 200 or not (o['test']['body'] or {}).get('sent'):
        fail('A4 조용한 시간에 시험 발송이 0 — 알림이 켜져 있어도 \'보낼 기기가 없어요\'가 뜬다: %s' % o['test'])
    if o['testPushed'] != ['알림 시험']: fail('A4 시험 알림이 이 기기로 나가지 않음: %s' % o['testPushed'])
    print('A4 조용한 시간에도 시험 발송은 나가고 보통 알림은 그대로 걸러짐 ok')

# ---------------------------------------------------------------- 화면
def on_chips(pg):
    return pg.evaluate("[...document.querySelectorAll('#gtSess .q.on')].map(b=>b.dataset.s)")

def on_tabs(pg):
    return pg.evaluate("[...document.querySelectorAll('#app>.bnav button.on')].map(b=>b.dataset.act)")

def run():
    quiet_test_push()
    with sync_playwright() as p:
        b = p.chromium.launch()
        c = b.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
        pg = c.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('dialog', lambda d: d.accept())
        cdp = c.new_cdp_session(pg)
        def touch(kind, pts):
            cdp.send('Input.dispatchTouchEvent', {'type': kind, 'touchPoints': [{'x': x, 'y': y} for x, y in pts]})
        def drag(x, y0, x1, y1, steps=14, dt=0.016):
            touch('touchStart', [(x, y0)])
            for i in range(1, steps + 1):
                touch('touchMove', [(x + (x1 - x) * i / steps, y0 + (y1 - y0) * i / steps)]); time.sleep(dt)
            touch('touchEnd', [])
        def tap_at(x, y):
            touch('touchStart', [(x, y)]); time.sleep(0.05); touch('touchEnd', [])
        def center(sel):
            r = pg.locator(sel).first.bounding_box()
            if not r: fail('안 보임: ' + sel)
            return r['x'] + r['width'] / 2, r['y'] + r['height'] / 2
        def sheet_open(): return pg.evaluate("!!document.querySelector('#modal>.ov')")
        def leftover(): return pg.evaluate("document.querySelectorAll('body>.ov').length")

        # ---- 가입 (가입 탭에서 동의 체크 — 시뮬레이터에서 한 그대로) ----
        user = 'sf' + tag
        pg.goto(URL); pg.wait_for_selector('#lgUser')
        pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName')
        pg.check('#lgAgree'); pg.fill('#lgName', '하은'); pg.fill('#lgUser', user); pg.fill('#lgPass', 'secret1')
        pg.click('[data-act="lg-submit"]'); pg.wait_for_selector('#gtTeam', timeout=10000)

        # ---- A1 팀 만들기 세션 ----
        if on_chips(pg) != ['인도자']: fail('A1 처음 고른 세션이 인도자가 아님: %s' % on_chips(pg))
        pg.tap('#gtSess .q[data-s="건반"]')
        if on_chips(pg) != ['건반']: fail('A1 건반을 눌렀는데 켜진 것: %s' % on_chips(pg))
        pg.tap('#gtSess .q[data-s="드럼"]')
        if on_chips(pg) != ['드럼']: fail('A1 세션은 하나만 — 드럼을 누르면 건반은 꺼져야 함: %s' % on_chips(pg))
        pg.tap('#gtSess .q[data-s="건반"]')
        if on_chips(pg) != ['건반']: fail('A1 다시 건반: %s' % on_chips(pg))
        pg.fill('#gtTeam', '시뮬팀' + tag)
        with pg.expect_request(lambda r: r.url.endswith('/api/teams') and r.method == 'POST') as rq:
            pg.click('[data-act="team-create"]')
        sent = json.loads(rq.value.post_data or '{}')
        if sent.get('session') != '건반': fail('A1 팀 만들기가 고른 세션을 안 보냄: %s' % sent)
        pg.wait_for_selector('.shell[data-page="home"]', timeout=10000)
        mine = pg.evaluate("(CONTI.NET.teams[0]||{}).me||null")
        if not mine or mine.get('session') != '건반' or mine.get('role') != 'leader': fail('A1 만든 팀의 내 세션·역할: %s' % mine)
        print('A1 팀 만들기 세션 건반(하나만 고름) ok:', sent)
        pg.wait_for_timeout(800)

        # ---- A10 하단 탭 ----
        if on_tabs(pg) != ['home']: fail('A10 예배 화면 탭: %s' % on_tabs(pg))
        for page, sel in (('settings', '.setpane'), ('team', '.shell[data-page="team"]'), ('word', '.shell[data-page="word"]')):
            pg.goto(URL + '#/' + page); pg.wait_for_selector(sel, timeout=8000); pg.wait_for_timeout(200)
            if on_tabs(pg) != ['more-menu']: fail('A10 %s 에서 켜진 탭: %s (더보기가 켜져야 함)' % (page, on_tabs(pg)))
            col = pg.evaluate("[getComputedStyle(document.querySelector('#app>.bnav [data-act=more-menu]')).color,getComputedStyle(document.querySelector('#app>.bnav [data-act=home]')).color]")
            if col[0] == col[1]: fail('A10 %s 에서 더보기 색이 다른 탭과 같음: %s' % (page, col))
        pg.goto(URL + '#/home'); pg.wait_for_selector('.shell[data-page="home"]'); pg.wait_for_timeout(200)
        if on_tabs(pg) != ['home']: fail('A10 예배로 돌아온 뒤 탭: %s' % on_tabs(pg))
        print('A10 설정·팀·말씀에서 더보기 켜짐 ok')

        # ---- A11 종 드롭다운 빈 화면 ----
        pg.click('#app .hd .bell'); pg.wait_for_selector('.ddempty', timeout=8000)
        g = pg.evaluate("""(()=>{const box=document.querySelector('.ddempty').getBoundingClientRect(),i=document.querySelector('.ddempty svg.ic').getBoundingClientRect(),
          t=document.querySelector('.ddempty b');const r=document.createRange();r.selectNodeContents(t);const tr=r.getBoundingClientRect();
          return {box:(box.left+box.right)/2,icon:(i.left+i.right)/2,text:(tr.left+tr.right)/2}})()""")
        if abs(g['icon'] - g['box']) > 1.5 or abs(g['icon'] - g['text']) > 1.5: fail('A11 빈 알림 종이 가운데가 아님: %s' % g)
        pg.click('#app .hd .bell'); pg.wait_for_timeout(200)
        print('A11 빈 알림 종 가운데 ok:', g)

        # ---- A9 더보기 시트 끌어내리기 ----
        def open_more():
            pg.tap('#app>.bnav [data-act="more-menu"]'); pg.wait_for_selector('#modal .ov.up .morelist'); pg.wait_for_timeout(450)
        open_more()
        hx, hy = center('#modal .sheetm .handle')
        drag(hx, hy, hx, hy + 40, steps=10, dt=0.03)   # 조금, 천천히 → 제자리
        pg.wait_for_timeout(400)
        if not sheet_open(): fail('A9 조금 끌었는데 닫힘')
        tf = pg.evaluate("getComputedStyle(document.querySelector('#modal .sheetm')).transform")
        if tf not in ('none', 'matrix(1, 0, 0, 1, 0, 0)'): fail('A9 조금 끈 뒤 제자리로 안 돌아옴: %s' % tf)
        drag(hx, hy + 30, hx + 120, hy + 40)             # 옆으로 → 그대로
        drag(hx, hy + 60, hx, hy - 60)                   # 위로 → 그대로
        pg.wait_for_timeout(300)
        if not sheet_open(): fail('A9 옆·위로 끌었는데 닫힘')
        # 누르기는 그대로 먹는다 — 시트 안 「설정」을 손가락으로 톡
        sx, sy = center('#modal .morelist [data-act="settings"]')
        tap_at(sx, sy); pg.wait_for_selector('.setpane', timeout=5000)
        if sheet_open(): fail('A9 설정을 눌렀는데 시트가 남음')
        print('A9 조금 끌면 제자리 · 옆·위로는 그대로 · 누르기 ok')
        pg.goto(URL + '#/home'); pg.wait_for_selector('.shell[data-page="home"]'); pg.wait_for_timeout(300)

        open_more()
        hx, hy = center('#modal .sheetm .handle')
        drag(hx, hy, hx, hy + 250)                       # 손잡이를 250 끌어내림 (시뮬레이터에서 한 그대로)
        pg.wait_for_timeout(80)
        if sheet_open(): fail('A9 손잡이를 250 끌어내려도 시트가 안 닫힘')
        if pg.evaluate("CONTI.route().name") != 'home': fail('A9 끌어 닫았는데 다른 곳으로 감: %s' % pg.evaluate("location.hash"))
        pg.wait_for_timeout(500)
        if leftover(): fail('A9 닫힌 시트 껍데기가 남음')
        # 닫힌 뒤 하단 탭을 누르면 그대로 먹는다 (끌기가 다음 누르기를 삼키지 않는다)
        cx, cy = center('#app>.bnav [data-act="nav-lib"]'); tap_at(cx, cy)
        pg.wait_for_function("CONTI.route().name==='library'", timeout=5000)
        pg.goto(URL + '#/home'); pg.wait_for_selector('.shell[data-page="home"]'); pg.wait_for_timeout(300)

        open_more()                                      # 짧아도 휙 내리면 닫힌다 (제목 줄에서 시작)
        tx, ty = center('#modal .sheetm>b')
        drag(tx, ty, tx, ty + 70, steps=3, dt=0.012)
        pg.wait_for_timeout(80)
        if sheet_open(): fail('A9 휙 내렸는데 안 닫힘')
        pg.wait_for_timeout(500)
        print('A9 끌어내리기·휙 내리기로 닫힘 ok')

        # 입력칸 위에서 시작한 끌기 · 안쪽이 스크롤된 채 끈 것은 닫지 않는다 (손잡이 있는 보통 시트)
        pg.evaluate("""CONTI.modal('<b>시험</b><input class="field" id="tIn" style="margin-top:12px"><div id="tSc" style="height:120px;overflow:auto;margin-top:12px"><div style="height:600px">목록</div></div>')""")
        pg.wait_for_selector('#tIn'); pg.wait_for_timeout(400)
        ix, iy = center('#tIn'); drag(ix, iy, ix, iy + 250); pg.wait_for_timeout(300)
        if not sheet_open(): fail('A9 입력칸에서 시작한 끌기로 시트가 닫힘')
        pg.evaluate("document.getElementById('tSc').scrollTop=200")
        lx, ly = center('#tSc'); drag(lx, ly - 40, lx, ly + 200); pg.wait_for_timeout(300)
        if not sheet_open(): fail('A9 안쪽 목록을 위로 되감는 끌기로 시트가 닫힘')
        pg.evaluate("document.getElementById('tSc').scrollTop=0")
        drag(lx, ly - 40, lx, ly + 220); pg.wait_for_timeout(80)
        if sheet_open(): fail('A9 안쪽이 맨 위일 때 끌어내려도 보통 시트가 안 닫힘')
        pg.wait_for_timeout(500)
        if leftover(): fail('A9 보통 시트 껍데기가 남음')
        print('A9 입력칸·스크롤된 안쪽은 그대로, 보통 시트도 끌어 닫힘 ok')

        # ---- A2 로그아웃 뒤 로그인 화면 ----
        pg.goto(URL + '#/settings'); pg.wait_for_selector('.setpane')
        pg.click('[data-act="set-tab"][data-t="app"]'); pg.wait_for_selector('#sLogout')
        pg.click('#sLogout'); pg.wait_for_selector('#lgUser', timeout=10000); pg.wait_for_timeout(300)
        st = pg.evaluate("({h1:document.querySelector('.auth-card h1').textContent,agree:!!document.querySelector('#lgAgree'),user:document.querySelector('#lgUser').value,name:!!document.querySelector('#lgName')})")
        if st['h1'] != '로그인' or st['agree'] or st['name']: fail('A2 로그아웃 뒤 로그인이 아닌 가입 화면: %s' % st)
        if st['user']: fail('A2 로그아웃 뒤 앞 사람 아이디가 채워져 있음: %s' % st)
        pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgAgree')
        if pg.locator('#lgAgree').is_checked(): fail('A2 로그아웃 뒤 가입 탭의 약관 동의가 미리 켜져 있음')
        print('A2 로그아웃 뒤 로그인 탭 · 빈 아이디 · 동의 꺼짐 ok:', st)
        # 로그인 탭에서 다시 들어오면 그대로 되고, 다음 로그아웃도 로그인 탭
        pg.click('[data-act="lg-mode"][data-m="login"]'); pg.wait_for_selector('#lgUser')
        pg.fill('#lgUser', user); pg.fill('#lgPass', 'secret1'); pg.click('[data-act="lg-submit"]')
        pg.wait_for_selector('.shell[data-page="home"]', timeout=10000)

        if errs: fail('JS 오류: %s' % errs[:3])
        b.close()
    print('OK')

run()
