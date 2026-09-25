# 애플 토큰 되돌리기 (App Store 심사 지침 5.1.1(v)) 화면 검사 — 웹·아이폰 앱이 애플 authorization code 를 보내고,
# 계정 삭제·연결 해제가 애플에 토큰을 되돌리는지 끝까지 본다.
#
# 이 검사가 스스로 띄우는 것 (끝나면 끈다): api/index.js + app/ 을 한 프로세스에서 · 같은 프로세스의 가짜 애플
# (ID 토큰 공개키 · /auth/token · /auth/revoke — APPLE_AUTH_BASE 로 가리킨다, localhost 만 받는다).
# 애플 웹 로그인 스크립트(appleid.auth.js)와 앱의 SocialLogin 플러그인은 흉내 낸다: 로그인하면 가짜 애플에서
# 그 사람의 ID 토큰과 한 번만 쓰는 code 를 받아 준다. 플러그인은 Capgo 8.5.10 처럼 useProperTokenExchange 면
# authorizationCode, 아니면(옛 방식) accessToken.token 에 code 를 준다.
#  1) 웹: 애플로 새로 가입(동의 창을 거쳐도 code 가 같이 간다) → Services ID · redirect_uri 로 바꿔 둔다 →
#     계정 삭제(애플로 다시 확인) → 애플에 되돌린다 · 로그인 화면으로
#  2) 웹: 비밀번호 계정에 애플 연결(비밀번호 확인) → 바꿔 둔다 → 연결 해제 → 되돌린다
#  3) 웹: code 를 안 주는 옛 흐름도 그대로 가입된다 (애플에 묻지 않는다)
#  4) 아이폰 앱: 플러그인을 useProperTokenExchange 로 초기화 · 애플 가입 → 번들 id 로 바꿔 둔다 → 계정 삭제 → 되돌린다
#     (다시 확인할 때 옛 모양(accessToken.token)으로 와도 code 로 보낸다)
# 준비: 로컬 DB (CONTI_DB, 기본 postgres://postgres:pg@localhost:54329/postgres). 스키마는 이 검사가 적용한다(멱등)
import os, sys, time, json, subprocess, threading, urllib.request, urllib.error
from urllib.parse import urlparse, urlencode
from playwright.sync_api import sync_playwright

DB = os.environ.get('CONTI_DB', 'postgres://postgres:pg@localhost:54329/postgres')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAG = str(int(time.time()))[-6:]
WEB, BUNDLE = 'test.lets1414.web', 'test.lets1414.app'
FAILS = []
def fail(m):
    print('FAIL:', m); FAILS.append(m)
    raise AssertionError(m)
def check(c, m):
    if not c: fail(m)
    print('ok  ', m)

HARNESS_JS = r"""
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { generateKeyPairSync, randomBytes, webcrypto as wc } from 'node:crypto';
const root = process.env.ROOT;
for (const k of ['BLOB_READ_WRITE_TOKEN', 'R2_ENDPOINT', 'R2_BUCKET', 'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY', 'GOOGLE_APPLICATION_CREDENTIALS',
  'GOOGLE_CLIENT_ID_WEB', 'GOOGLE_CLIENT_ID_IOS', 'GOOGLE_CLIENT_ID_ANDROID', 'GOOGLE_VISION_KEY']) delete process.env[k];
const sk = generateKeyPairSync('ec', { namedCurve: 'P-256' });
Object.assign(process.env, { AUTH_SECRET: process.env.AUTH_SECRET || 'local-dev-secret-0123456789', GEMINI_API_KEY: 'mock',
  APPLE_SERVICE_ID: process.env.WEB, APNS_BUNDLE_ID: process.env.BUNDLE, APPLE_SIGNIN_TEAM_ID: 'TEAM123456', APPLE_SIGNIN_KEY_ID: 'KEY1234567',
  APPLE_SIGNIN_KEY: sk.privateKey.export({ type: 'pkcs8', format: 'pem' }) });
{ const { default: pg } = await import('pg'); const c = new pg.Client({ connectionString: process.env.DATABASE_URL });
  await c.connect(); await c.query(fs.readFileSync(path.join(root, 'db', 'schema.sql'), 'utf8')); await c.end(); }
const b64u = (x) => Buffer.from(x).toString('base64url');
const rsa = await wc.subtle.generateKey({ name: 'RSASSA-PKCS1-v1_5', modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: 'SHA-256' }, true, ['sign', 'verify']);
const jwk = await wc.subtle.exportKey('jwk', rsa.publicKey); jwk.kid = 'fake-apple'; jwk.alg = 'RS256';
async function idToken(sub, aud) {
  const now = Math.floor(Date.now() / 1000);
  const h = b64u(JSON.stringify({ alg: 'RS256', kid: 'fake-apple' }));
  const b = b64u(JSON.stringify({ iss: 'https://appleid.apple.com', aud, sub, email: sub + '@privaterelay.appleid.com', iat: now, exp: now + 600 }));
  return h + '.' + b + '.' + b64u(await wc.subtle.sign('RSASSA-PKCS1-v1_5', rsa.privateKey, new TextEncoder().encode(h + '.' + b)));
}
// ---- 가짜 애플 ----
const A = { codes: new Map(), tokenCalls: [], revokes: [], issued: [] };
const form = (req) => new Promise((ok) => { let s = ''; req.setEncoding('utf8'); req.on('data', (c) => { s += c; }); req.on('end', () => ok(new URLSearchParams(s))); });
const json = (res, st, o) => { res.statusCode = st; res.setHeader('content-type', 'application/json'); res.end(JSON.stringify(o)); };
const secretSub = (f) => { try { return JSON.parse(Buffer.from(String(f.get('client_secret')).split('.')[1], 'base64url')).sub; } catch { return null; } };
const apple = http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://x');
  if (url.pathname === '/auth/keys') return json(res, 200, { keys: [jwk] });
  const f = await form(req);
  if (url.pathname === '/auth/token') {
    A.tokenCalls.push(Object.fromEntries(f));
    const c = A.codes.get(f.get('code'));
    if (secretSub(f) !== f.get('client_id')) return json(res, 400, { error: 'invalid_client' });
    if (!c || c.used || c.clientId !== f.get('client_id') || (c.redirect || null) !== (f.get('redirect_uri') || null)) return json(res, 400, { error: 'invalid_grant' });
    c.used = true;
    const refresh = 'r' + randomBytes(12).toString('hex');
    A.issued.push({ refresh, sub: c.sub, clientId: c.clientId });
    return json(res, 200, { access_token: 'a', token_type: 'Bearer', expires_in: 3600, refresh_token: refresh, id_token: await idToken(c.sub, c.clientId) });
  }
  if (url.pathname === '/auth/revoke') {
    if (secretSub(f) !== f.get('client_id')) return json(res, 400, { error: 'invalid_client' });
    A.revokes.push(Object.fromEntries(f)); res.statusCode = 200; return res.end();
  }
  json(res, 404, {});
}).listen(0, '127.0.0.1');
await new Promise((r) => apple.once('listening', r));
process.env.APPLE_AUTH_BASE = 'http://127.0.0.1:' + apple.address().port;

const { default: api } = await import(root + '/api/index.js');
const { q } = await import(root + '/lib/db.js');
const { openAppleRefresh } = await import(root + '/lib/apple.js');
const appDir = path.join(root, 'app');
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.json': 'application/json', '.png': 'image/png', '.svg': 'image/svg+xml', '.css': 'text/css', '.webmanifest': 'application/manifest+json' };
const srv = http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://x'), sp = url.searchParams;
  // 애플 로그인 화면 흉내: 이 사람(sub)이 이 클라이언트(aud)에서 방금 로그인했다 → ID 토큰 + 한 번만 쓰는 code (웹은 redirect 와 묶인다)
  if (url.pathname === '/__apple') {
    const sub = sp.get('sub'), aud = sp.get('aud');
    const out = { idToken: await idToken(sub, aud) };
    if (sp.get('code') !== '0') { out.code = 'c' + randomBytes(12).toString('hex'); A.codes.set(out.code, { sub, clientId: aud, redirect: sp.get('redirect') || null }); }
    return json(res, 200, out);
  }
  if (url.pathname === '/__state') return json(res, 200, { tokenCalls: A.tokenCalls, revokes: A.revokes, issued: A.issued });
  if (url.pathname === '/__stored') {
    const row = (await q(`select refresh_enc from identities where provider='apple' and subject=$1`, [sp.get('sub')]))[0];
    const o = row && row.refresh_enc ? await openAppleRefresh(row.refresh_enc, sp.get('sub')) : null;
    return json(res, 200, { row: !!row, enc: !!(row && row.refresh_enc), token: o && o.token, clientId: o && o.clientId });
  }
  if (url.pathname === '/__user') return json(res, 200, { n: +(await q('select count(*)::int as n from users where id=$1', [sp.get('id')]))[0].n });
  if (url.pathname === '/__cleanup') {
    const tag = '%' + sp.get('tag');
    await q(`delete from teams where name like $1`, [tag]);
    await q(`delete from users where id in (select user_id from identities where subject like $1) or username like $1`, [tag]);
    return json(res, 200, { ok: true });
  }
  if (url.pathname.startsWith('/api/') || url.pathname === '/api') return api(req, res);
  const f = path.join(appDir, decodeURIComponent(url.pathname === '/' ? '/index.html' : url.pathname));
  if (!f.startsWith(appDir + path.sep) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.statusCode = 404; return res.end('없음'); }
  res.setHeader('content-type', MIME[path.extname(f)] || 'application/octet-stream');
  fs.createReadStream(f).pipe(res);
});
srv.listen(0, '127.0.0.1', () => console.log('READY ' + srv.address().port));
"""

class Harness:
    def __init__(self):
        env = {'PATH': os.environ.get('PATH', ''), 'HOME': os.environ.get('HOME', ''), 'ROOT': ROOT, 'DATABASE_URL': DB,
               'WEB': WEB, 'BUNDLE': BUNDLE, 'BLOB_LOCAL_DIR': os.path.join(ROOT, '.localblob')}
        self.p = subprocess.Popen(['node', '--input-type=module', '-e', HARNESS_JS], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.log = []
        line = ''
        for _ in range(400):
            line = self.p.stdout.readline()
            if line.startswith('READY') or not line: break
            self.log.append(line)
        if not line.startswith('READY'): raise RuntimeError('가짜 서버를 못 띄움: ' + ''.join(self.log[-20:]) + line)
        self.base = 'http://127.0.0.1:%s/' % line.split()[1]
        threading.Thread(target=lambda: [self.log.append(l) for l in self.p.stdout], daemon=True).start()
    def get(self, path, **kw):
        with urllib.request.urlopen(self.base + path + ('?' + urlencode(kw) if kw else ''), timeout=30) as r: return json.loads(r.read().decode())
    def call(self, method, path, body=None, cookie=None):
        h = {'x-conti': '1', 'content-type': 'application/json'}
        if cookie: h['cookie'] = cookie
        req = urllib.request.Request(self.base + 'api' + path, data=json.dumps(body).encode() if body is not None else None, method=method, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=30) as r: return r.status, json.loads(r.read().decode()), r.headers
        except urllib.error.HTTPError as e: return e.code, json.loads(e.read().decode() or '{}'), e.headers
    def state(self): return self.get('__state')
    def stored(self, sub): return self.get('__stored', sub=sub)
    def close(self): self.p.terminate(); self.p.wait(10)

APPLE_JS = r"""window.AppleID={auth:{init(o){window.__appleInit=o},async signIn(){
  const i=window.__appleInit||{};
  const q=new URLSearchParams({sub:window.__appleSub||'',aud:i.clientId||'',redirect:i.redirectURI||'',code:window.__appleNoCode?'0':'1'});
  const r=await (await fetch('/__apple?'+q)).json();
  return {authorization:{id_token:r.idToken,code:r.code},user:window.__appleFirst?{name:{firstName:'길동',lastName:'홍'}}:undefined}}}};"""

# Capgo SocialLogin 8.5.10 (iOS) 흉내 — initialize 에 받은 것을 적어 두고, 애플은 useProperTokenExchange 면 authorizationCode ·
# 아니면(또는 __forceLegacy) accessToken.token 에 code 를 준다 (AppleProvider.swift 와 같다)
SL_MOCK = r"""
(() => {
  const st = { inits: [], apple: {} };
  window.__sl = st;
  window.Capacitor = { getPlatform: () => 'ios', isNativePlatform: () => true, isPluginAvailable: () => false,
    Plugins: { SocialLogin: {
      async initialize(o) { st.inits.push(JSON.parse(JSON.stringify(o || {}))); if (o && o.apple) st.apple = o.apple; },
      async login({ provider }) {
        if (provider !== 'apple') throw new Error('이 검사는 애플만');
        const q = new URLSearchParams({ sub: window.__appleSub || '', aud: st.apple.clientId || '' });
        const r = await (await fetch('/__apple?' + q)).json();
        const proper = st.apple.useProperTokenExchange && !window.__forceLegacy;
        return { provider, result: { idToken: r.idToken, accessToken: proper ? null : { token: r.code }, profile: { user: window.__appleSub, email: '', givenName: '길동', familyName: '홍' },
          ...(proper ? { authorizationCode: r.code } : {}) } };
      },
      logout: () => Promise.resolve(),
    } } };
})();
"""
IPAD_UA = 'Mozilla/5.0 (iPad; CPU OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148'

def new_team(pg, url, name):
    pg.wait_for_selector('#gtTeam', timeout=15000)
    pg.fill('#gtTeam', name); pg.click('[data-act="team-create"]'); pg.wait_for_selector('.shell[data-page]', timeout=15000)
    pg.goto(url + '#/settings'); pg.wait_for_selector('.setpane', timeout=10000)
    pg.click('[data-act="set-tab"][data-t="account"]'); pg.wait_for_selector('#sDel', timeout=5000)
    pg.wait_for_function("()=>{const b=document.querySelector('#linkList');return b&&!/불러오는 중/.test(b.textContent)}", timeout=15000)

def delete_account(pg, username):
    pg.click('#sDel'); pg.wait_for_selector('#daUser', timeout=5000)
    pg.fill('#daUser', username); pg.click('#daGo')
    pg.wait_for_selector('#lgUser', timeout=20000)

def web_flows(b, H):
    URL = H.base
    c = b.new_context(viewport={'width': 1180, 'height': 820}, service_workers='block')
    c.route('**/appleid.auth.js', lambda r: r.fulfill(status=200, content_type='text/javascript', body=APPLE_JS))
    pg = c.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:200])); pg.on('dialog', lambda d: d.accept())
    toast = lambda: pg.evaluate("(document.querySelector('#toast')||{}).textContent||''")
    RED = URL.rstrip('/') + '/api/auth/apple/callback'

    # 1) 새로 가입 — 동의 창을 거친다 (그 전에는 code 를 쓰지 않고, 동의 뒤 같은 code 로)
    sub = 'web-' + TAG
    pg.goto(URL); pg.wait_for_selector('#aBtn', timeout=15000)
    pg.evaluate("s=>{window.__appleSub=s;window.__appleFirst=true}", sub)
    n0 = len(H.state()['tokenCalls'])
    pg.click('#aBtn'); pg.wait_for_selector('#scAgree', timeout=8000)
    check(len(H.state()['tokenCalls']) == n0, '웹: 동의 창 전에는 애플 code 를 바꾸지 않는다')
    pg.check('#scAgree'); pg.click('#scOk')
    pg.wait_for_selector('#gtTeam', timeout=15000)
    st = H.state(); tc = st['tokenCalls'][-1] if len(st['tokenCalls']) > n0 else {}
    check(tc.get('client_id') == WEB and tc.get('redirect_uri') == RED, '웹: 동의 뒤 같은 code 를 Services ID · redirect_uri 로 바꾼다 (%s)' % {k: tc.get(k) for k in ('client_id', 'redirect_uri')})
    s = H.stored(sub); iss = [x for x in st['issued'] if x['sub'] == sub]
    check(s['enc'] and iss and s['token'] == iss[-1]['refresh'] and s['clientId'] == WEB, '웹: refresh token 을 암호화해 둔다')
    username = pg.evaluate("CONTI.NET.user.username"); uid = pg.evaluate("CONTI.NET.user.id")
    new_team(pg, URL, '애플웹팀' + TAG)
    r0 = len(H.state()['revokes'])
    delete_account(pg, username)
    st = H.state(); rv = st['revokes'][r0:]; iss = [x for x in st['issued'] if x['sub'] == sub]
    check(H.get('__user', id=uid)['n'] == 0, '웹: 애플로 다시 확인하고 계정 삭제')
    check(len(rv) == 1 and rv[0]['token'] == iss[-1]['refresh'] and rv[0]['client_id'] == WEB and rv[0]['token_type_hint'] == 'refresh_token',
          '웹: 삭제하면 애플에 되돌린다 (다시 확인한 로그인의 새 토큰)')

    # 2) 비밀번호 계정에 애플 연결 → 해제
    un = 'arp' + TAG
    stc, j, hd = H.call('POST', '/auth/signup', {'username': un, 'password': 'secret12', 'name': '비번', 'agreedAt': '2026-09-26T00:00:00Z'})
    ck = hd['set-cookie'].split(';')[0]
    c.add_cookies([{'name': 'conti_s', 'value': ck.split('=', 1)[1], 'url': URL}])
    pg.goto(URL); new_team(pg, URL, '애플연결팀' + TAG)
    sub2 = 'link-' + TAG
    pg.evaluate("s=>{window.__appleSub=s;window.__appleFirst=false}", sub2)
    pg.click('[data-link="apple"]'); pg.wait_for_selector('#raPw', timeout=5000)
    pg.fill('#raPw', 'secret12'); pg.click('#raGo')
    try: pg.wait_for_selector('[data-unlink="apple"]', timeout=10000)
    except Exception: fail('웹: 애플 연결이 안 됨 — %r' % toast())
    s = H.stored(sub2)
    check(s['enc'] and s['clientId'] == WEB, '웹: 연결할 때도 code 를 보내 받아 둔다')
    r0 = len(H.state()['revokes'])
    pg.click('[data-unlink="apple"]'); pg.wait_for_selector('#raPw', timeout=5000)
    pg.fill('#raPw', 'secret12'); pg.click('#raGo')
    pg.wait_for_selector('[data-link="apple"]', timeout=10000)
    rv = H.state()['revokes'][r0:]
    check(not H.stored(sub2)['row'] and len(rv) == 1 and rv[0]['token'] == s['token'] and rv[0]['client_id'] == WEB, '웹: 연결 해제하면 애플에 되돌린다')
    if errs: fail('웹 화면 오류 %s' % errs[:3])
    c.close()

    # 3) code 를 안 주는 옛 흐름 — 그대로 가입 · 애플에 묻지 않는다
    c = b.new_context(viewport={'width': 1180, 'height': 820}, service_workers='block')
    c.route('**/appleid.auth.js', lambda r: r.fulfill(status=200, content_type='text/javascript', body=APPLE_JS))
    pg = c.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:200])); pg.on('dialog', lambda d: d.accept())
    sub3 = 'nocode-' + TAG
    pg.goto(URL); pg.wait_for_selector('#aBtn', timeout=15000)
    pg.evaluate("s=>{window.__appleSub=s;window.__appleNoCode=true}", sub3)
    n0 = len(H.state()['tokenCalls'])
    pg.click('#aBtn'); pg.wait_for_selector('#scAgree', timeout=8000)
    pg.check('#scAgree'); pg.click('#scOk'); pg.wait_for_selector('#gtTeam', timeout=15000)
    s = H.stored(sub3)
    check(s['row'] and not s['enc'] and len(H.state()['tokenCalls']) == n0, '웹: code 가 없어도 가입된다 (애플 교환 없음)')
    if errs: fail('웹 화면 오류 %s' % errs[:3])
    c.close()

def native_flow(b, H):
    hb = urlparse(H.base)
    c = b.new_context(viewport={'width': 1180, 'height': 820}, service_workers='block', user_agent=IPAD_UA)
    def handler(route):
        u = urlparse(route.request.url)
        if (u.scheme == 'https' and u.hostname == 'localhost' and u.port is None) or u.hostname in ('lets1414.com', 'www.lets1414.com'):
            try: return route.fulfill(response=route.fetch(url=H.base + u.path.lstrip('/') + ('?' + u.query if u.query else '')))
            except Exception:
                try: return route.abort()
                except Exception: return
        if u.hostname == hb.hostname and u.port == hb.port: return route.continue_()
        return route.abort()
    c.route('**/*', handler)
    c.add_init_script(SL_MOCK)
    pg = c.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:200])); pg.on('dialog', lambda d: d.accept())
    sub = 'ios-' + TAG
    pg.goto('https://localhost/'); pg.wait_for_selector('#aBtn', timeout=15000)
    if not pg.evaluate('location.hostname==="localhost"&&!location.port&&location.protocol==="https:"'): fail('앱 흉내가 안 됨 (NATIVE 아님)')
    pg.evaluate("s=>{window.__appleSub=s}", sub)
    n0 = len(H.state()['tokenCalls'])
    pg.click('#aBtn'); pg.wait_for_selector('#scAgree', timeout=8000)
    pg.check('#scAgree'); pg.click('#scOk'); pg.wait_for_selector('#gtTeam', timeout=15000)
    inits = pg.evaluate("window.__sl.inits")
    check(any((i.get('apple') or {}).get('useProperTokenExchange') is True and (i.get('apple') or {}).get('clientId') == BUNDLE for i in inits),
          '앱: 플러그인을 번들 id · useProperTokenExchange 로 초기화 (%s)' % inits)
    st = H.state(); tc = st['tokenCalls'][n0:]
    check(len(tc) == 1 and tc[0]['client_id'] == BUNDLE and 'redirect_uri' not in tc[0], '앱: authorizationCode 를 번들 id 로 · redirect_uri 없이 바꾼다')
    s = H.stored(sub)
    check(s['enc'] and s['clientId'] == BUNDLE, '앱: refresh token 을 받아 둔다')
    username = pg.evaluate("CONTI.NET.user.username"); uid = pg.evaluate("CONTI.NET.user.id")
    new_team(pg, 'https://localhost/', '애플앱팀' + TAG)
    # 다시 확인할 때는 옛 모양(accessToken.token)으로 줘 본다 — 그래도 code 로 보낸다
    pg.evaluate("()=>{window.__forceLegacy=true}")
    r0 = len(H.state()['revokes'])
    delete_account(pg, username)
    st = H.state(); rv = st['revokes'][r0:]; iss = [x for x in st['issued'] if x['sub'] == sub]
    check(H.get('__user', id=uid)['n'] == 0, '앱: 애플로 다시 확인하고 계정 삭제')
    check(len(iss) == 2 and len(rv) == 1 and rv[0]['token'] == iss[-1]['refresh'] and rv[0]['client_id'] == BUNDLE,
          '앱: 삭제하면 애플에 되돌린다 (옛 모양 accessToken.token 의 code 도 받아 새 토큰으로)')
    if errs: fail('앱 화면 오류 %s' % errs[:3])
    c.close()

def run():
    H = Harness()
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            try:
                for name, fn in (('web', web_flows), ('native', native_flow)):
                    try: fn(b, H)
                    except AssertionError: pass
                    except Exception as e: FAILS.append('%s: %r' % (name, e)); print('FAIL:', name, repr(e))
            finally: b.close()
    finally:
        try: H.get('__cleanup', tag=TAG)
        except Exception as e: print('뒷정리 실패', e)
        H.close()
    if FAILS:
        print('\n%d 건 실패' % len(FAILS)); sys.exit(1)
    print('\nOK — 애플 토큰 되돌리기 화면 (웹 가입·삭제 · 연결·해제 · 옛 흐름 · 아이폰 앱)')

run()
