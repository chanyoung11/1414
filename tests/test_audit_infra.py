# 감사(infra) 회귀 검사
#  - F33  Plus 프로모션 코드를 쓰면 팀이 plus 가 된다 (전에는 teams_plan_check 가 free/pro 만 받아 500)
#  - F109 '//' · '//x:y@' 같은 주소에 바로 400 이 나가고 서버는 멀쩡하다 (server.mjs 는 5분 매달렸고, dev.mjs 는 죽었다)
#  - F110 1KB 넘는 API 응답은 Accept-Encoding: gzip 이면 gzip 으로 나간다
#  - F146 가입·로그인이 몰려도 다른 요청이 서지 않는다 (scrypt 를 이벤트 루프 밖에서, 동시에 1~2개만 —
#         스레드 풀을 해시가 다 차지하면 gzip 응답이 해시 줄 뒤에서 0.4초씩 기다렸다)
#  - F104 직접 업로드 서명 URL 은 크기를 묶고 10분만 산다. 등록 안 한 파일은 하루 뒤 치운다.
#         서명 URL 은 사람당 15분에 200개, 치우기는 남은 게 없을 때까지 나눠 돌고, 덮어쓴 파일의 크기를 blobs 에 맞춘다
#  - F105 파일 삭제를 1,000개씩 나눠 보내고, 못 지운 것은 blob_trash 에 적었다가 다시 지운다
#  - F147 migrate-library 가 제목 없는 항목마다 '(제목 없음)' 곡을 만들지 않는다. 제목 없는 칸에 남은 남의·없는 곡 id 는
#         지우고 사용 이력에 쓰지 않는다. 공백뿐인 제목이 '-' 곡에 붙지 않는다
# 사용: CONTI_URL=http://localhost:8815/ .venv/bin/python tests/test_audit_infra.py
#   BLOB_LOCAL_DIR 은 개발 서버와 같아야 한다 (기본: 저장소의 .localblob — dev-local.sh 기본값)
#   DB 는 로컬 도커(conti-pg)만 쓴다. F147 은 따로 만든 임시 DB 에서 돌리고 지운다
import os, sys, time, json, socket, subprocess, gzip, threading, tempfile, shutil, uuid, urllib.request, urllib.error, http.cookiejar

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
if not URL.endswith('/'): URL += '/'
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
DB = os.environ.get('LOCAL_DB', 'postgres://postgres:pg@localhost:54329/postgres')
BLOB_DIR = os.environ.get('BLOB_LOCAL_DIR', os.path.join(ROOT, '.localblob'))
tag = str(int(time.time() * 1000))[-8:]
FAILS = []

def fail(m):
  print('FAIL:', m); FAILS.append(m)

if '@localhost:' not in DB and '@127.0.0.1:' not in DB:
  print('FAIL: 로컬 DB 가 아니에요 — 이 테스트는 로컬 도커 DB 만 씁니다'); sys.exit(1)

# ---------- 도우미 ----------
class Client:
  def __init__(s):
    s.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
  def call(s, method, path, body=None, headers=None, raw=None):
    h = {'x-conti': '1', **(headers or {})}
    data = raw
    if body is not None: data = json.dumps(body).encode(); h['content-type'] = 'application/json'
    req = urllib.request.Request(path if path.startswith('http') else URL + path, data=data, method=method, headers=h)
    try:
      with s.op.open(req, timeout=30) as r: return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e: return e.code, e.headers, e.read()
  def json(s, method, path, body=None):
    st, h, b = s.call(method, path, body)
    try: return st, json.loads(b or b'{}')
    except Exception: return st, {'raw': b[:200]}

def signup(c, pre):
  st, j = c.json('POST', 'api/auth/signup', {'username': pre + tag, 'password': 'secret1', 'name': '감사'})
  if st != 200: raise SystemExit('가입 실패: %s %s' % (st, j))
  st, t = c.json('POST', 'api/teams', {'name': '감사팀' + pre, 'myName': '인도자'})
  if st != 200 or not t.get('teamId'): raise SystemExit('팀 만들기 실패: %s %s' % (st, t))
  return t['teamId']

NODE_SQL = r'''
import pg from 'pg';
const c = new pg.Client({ connectionString: process.env.T_DB }); await c.connect();
try { const r = await c.query(process.env.T_SQL, JSON.parse(process.env.T_ARGS || '[]')); console.log(JSON.stringify(r.rows)); }
finally { await c.end(); }
'''
def node(code, env=None, timeout=120):
  e = {k: v for k, v in os.environ.items() if not k.startswith(('R2_', 'BLOB_', 'DATABASE_URL', 'POSTGRES_URL'))}
  e.update(env or {})
  return subprocess.run(['node', '--input-type=module', '-e', code], cwd=ROOT, env=e, capture_output=True, text=True, timeout=timeout)

def sql(q, args=None, db=DB):
  r = node(NODE_SQL, {'T_DB': db, 'T_SQL': q, 'T_ARGS': json.dumps(args or [])})
  if r.returncode: raise SystemExit('SQL 실패: %s\n%s' % (q[:80], r.stderr[-500:]))
  return json.loads(r.stdout.strip().splitlines()[-1])

def raw_get(port, path, wait=3):
  s = socket.create_connection(('127.0.0.1', port), timeout=wait)
  try:
    s.sendall(('GET %s HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n' % path).encode())
    d = s.recv(64)
    return d.split(b'\r\n')[0].decode(errors='replace') if d else '(연결 끊김)'
  except socket.timeout: return '(응답 없음)'
  finally: s.close()

def free_port():
  s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p

# ---------- 임시 DB ----------
# 공용 DB 의 스키마는 각 작업본이 서버를 켤 때마다 자기 schema.sql 로 다시 깐다. 이 작업본의 스키마 그대로 보려면 따로 만든다
class TempDB:
  def __enter__(s):
    s.name = 'audit_infra_' + tag
    s.url = DB.rsplit('/', 1)[0] + '/' + s.name
    sql('create database ' + s.name)
    s.migrate()
    return s
  def migrate(s):
    r = subprocess.run(['node', 'scripts/migrate.mjs'], cwd=ROOT, env={**os.environ, 'DATABASE_URL': s.url}, capture_output=True, text=True, timeout=120)
    if r.returncode: raise SystemExit('임시 DB 스키마 실패: ' + r.stderr[-300:])
  def __exit__(s, *a):
    sql('drop database if exists ' + s.name + ' with (force)')

# ---------- F33 ----------
def t_plus_plan(tmp):
  # 1) 스키마: plus 를 받고, plus 팀이 있어도 스키마를 다시 깔 수 있다 (전에는 제약을 다시 걸다 실패했다)
  u = sql("insert into users(username, password_hash, display_name) values('plus', 'x', 'p') returning id", db=tmp.url)[0]['id']
  t = sql("insert into teams(name, invite_token, created_by, plan) values('plus팀', 'tok-plus', $1, 'plus') returning id", [u], db=tmp.url)[0]['id']
  tmp.migrate()
  r = node(NODE_SQL, {'T_DB': tmp.url, 'T_SQL': "update teams set plan='gold' where id=$1", 'T_ARGS': json.dumps([t])})
  if r.returncode == 0 or 'teams_plan_check' not in r.stderr: return fail('F33 제약이 아무 값이나 받음')
  # 2) 앱: Plus 코드를 넣으면 팀이 plus 가 된다. 공용 DB 제약을 다른 작업본이 옛 스키마로 되돌려 놓았으면 이 부분은 건너뛴다
  cdef = sql("select pg_get_constraintdef(oid) as d from pg_constraint where conname='teams_plan_check'")[0]['d']
  if 'plus' not in cdef:
    print('ok F33 — 스키마가 plus 를 받음 (공용 DB 는 다른 작업본의 옛 스키마라 API 확인은 건너뜀: %s)' % cdef); return
  c = Client(); team = signup(c, 'ip')
  code = 'PLUS' + tag
  sql('insert into promo_codes(code, plan, days, max_uses, note) values($1,$2,30,1,$3)', [code, 'plus', 'test_audit_infra'])
  st, j = c.json('POST', 'api/promo/redeem', {'teamId': team, 'code': code})
  if st != 200 or j.get('plan') != 'plus': return fail('F33 Plus 코드 적용 실패: %s %s' % (st, j))
  st, me = c.json('GET', 'api/me')
  if (me.get('team') or {}).get('plan') != 'plus': return fail('F33 팀 플랜이 plus 로 안 보임: %s' % (me.get('team') or {}).get('plan'))
  print('ok F33 — 스키마가 plus 를 받고 다시 깔아도 됨, Plus 코드 → plan=plus, 모르는 플랜은 막힘')

# ---------- F109 ----------
BAD_PATHS = ['//', '///', '//x:y@']
def t_bad_url_dev():
  port = int(URL.rstrip('/').rsplit(':', 1)[1])
  for pth in BAD_PATHS:
    line = raw_get(port, pth)
    if ' 400 ' not in line + ' ': return fail('F109 dev 서버가 %r 에 400 을 안 줌: %s' % (pth, line))
  if ' 200 ' not in raw_get(port, '/api/health') + ' ': return fail('F109 이상한 주소 뒤 dev 서버가 죽음')
  print('ok F109 — dev.mjs: 이상한 주소에 400, 서버 멀쩡')

def t_bad_url_prod_entry():
  # 운영 진입점(server.mjs)을 DB·저장소 없이 빈 포트에 띄워 본다
  port = free_port()
  env = {'PATH': os.environ.get('PATH', ''), 'HOME': os.environ.get('HOME', ''), 'PORT': str(port)}
  p = subprocess.Popen(['node', 'server.mjs'], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
  try:
    for _ in range(100):
      try: socket.create_connection(('127.0.0.1', port), timeout=0.2).close(); break
      except OSError: time.sleep(0.1)
    for pth in BAD_PATHS:
      t = time.time(); line = raw_get(port, pth)
      if ' 400 ' not in line + ' ': return fail('F109 server.mjs 가 %r 에 400 을 안 줌: %s (%.1fs)' % (pth, line, time.time() - t))
    line = raw_get(port, '/')
    if ' 200 ' not in line + ' ': return fail('F109 server.mjs 첫 화면이 안 나옴: %s' % line)
    # 정적 파일 gzip 은 그대로
    req = urllib.request.Request('http://127.0.0.1:%d/' % port, headers={'accept-encoding': 'gzip'})
    with urllib.request.urlopen(req, timeout=5) as r:
      if r.headers.get('content-encoding') != 'gzip': return fail('F109 server.mjs 정적 gzip 이 빠짐')
    print('ok F109 — server.mjs: 이상한 주소에 바로 400, 첫 화면·정적 gzip 그대로')
  finally:
    p.terminate()
    try: p.wait(5)
    except Exception: p.kill()

# ---------- F110 ----------
def t_gzip():
  c = Client(); team = signup(c, 'iz')
  for i in range(6):
    st, _ = c.json('POST', 'api/songs', {'teamId': team, 'title': '압축 곡 %d' % i, 'key': 'G', 'form': 'I V1 V2 C C B C C O ' * 5, 'songNote': '메모 ' * 30})
    if st != 200: return fail('F110 곡 만들기 실패 %s' % st)
  st, h, b = c.call('GET', 'api/songs?team=' + team, headers={'accept-encoding': 'gzip, deflate, br'})
  if st != 200: return fail('F110 곡 목록 실패 %s' % st)
  if h.get('content-encoding') != 'gzip': return fail('F110 큰 JSON 이 압축되지 않음 (%d바이트)' % len(b))
  if 'accept-encoding' not in (h.get('vary') or '').lower(): return fail('F110 Vary: Accept-Encoding 이 없음: %s' % h.get('vary'))
  plain = gzip.decompress(b)
  if len(json.loads(plain).get('songs') or []) != 6: return fail('F110 풀어 본 JSON 이 이상함')
  st, h2, b2 = c.call('GET', 'api/songs?team=' + team)
  if h2.get('content-encoding') or len(json.loads(b2)['songs']) != 6: return fail('F110 gzip 을 모르는 요청에도 압축함')
  st, h3, b3 = c.call('GET', 'api/health', headers={'accept-encoding': 'gzip'})
  if h3.get('content-encoding'): return fail('F110 작은 응답까지 압축함')
  # 앱(다른 출처) 요청의 Vary: Origin 이 지워지지 않는다
  st, h4, _ = c.call('GET', 'api/songs?team=' + team, headers={'accept-encoding': 'gzip', 'origin': 'https://localhost'})
  vary = (h4.get('vary') or '').lower()
  if 'origin' not in vary or 'accept-encoding' not in vary: return fail('F110 Vary 가 덮어써짐: %s' % vary)
  print('ok F110 — %d바이트 → gzip %d바이트, 작은 응답·gzip 모르는 요청은 그대로' % (len(plain), len(b)))

# ---------- F146 ----------
# 해시 64개를 한꺼번에 걸고 gzip 하나가 얼마나 기다리는지 (스레드 풀 기본 4개를 같이 쓴다). 묶기 전 ~425ms
POOL_JS = r"""
import zlib from 'node:zlib';
const { hashPasswordAsync } = await import('./lib/password.js');
const body = Buffer.from(JSON.stringify(Array.from({ length: 200 }, (_, i) => ({ i, t: '곡 ' + i }))));
const gz = () => new Promise((r) => { const t = performance.now(); zlib.gzip(body, () => r(performance.now() - t)); });
await gz();
const all = Array.from({ length: 64 }, () => hashPasswordAsync('secret1'));
await new Promise((r) => setTimeout(r, 5));
const w = await gz(); await Promise.all(all);
console.log(JSON.stringify({ wait: w })); process.exit(0);
"""
# 개발 서버에 가입 64개를 한꺼번에 보내는 동안 gzip 으로 나가는 곡 목록(브라우저·앱이 받는 꼴)을 계속 받아 본다.
# 파이썬 스레드로는 가입이 흩어져 줄이 안 쌓이므로 node 로 한꺼번에 보낸다. 묶기 전 417~447ms
BURST_JS = r"""
const U = process.env.T_URL, T = process.env.T_TAG;
const H = { 'x-conti': '1', 'content-type': 'application/json' };
const post = (p, b, h = {}) => fetch(U + p, { method: 'POST', headers: { ...H, ...h }, body: JSON.stringify(b) });
const r = await post('api/auth/signup', { username: 'gb' + T, password: 'secret1', name: 'x' });
const cookie = r.headers.getSetCookie().map((c) => c.split(';')[0]).join('; ');
const team = (await (await post('api/teams', { name: '압축팀', myName: '인도자' }, { cookie })).json()).teamId;
for (let i = 0; i < 6; i++) await post('api/songs', { teamId: team, title: '압축 곡 ' + i, key: 'G', form: 'I V1 V2 C C B C C O '.repeat(5), songNote: '메모 '.repeat(30) }, { cookie });
const get = async () => {
  const t = performance.now();
  const res = await fetch(U + 'api/songs?team=' + team, { headers: { cookie, 'accept-encoding': 'gzip' } });
  await res.arrayBuffer();
  if (res.headers.get('content-encoding') !== 'gzip') throw new Error('곡 목록이 gzip 으로 안 나감');
  return performance.now() - t;
};
let ok = 0;
async function probe(n, k) {
  let done = false; const lat = [];
  const poller = (async () => { while (!done) { lat.push(await get()); await new Promise((r) => setTimeout(r, 3)); } })();
  await new Promise((r) => setTimeout(r, 100));
  await Promise.all(Array.from({ length: n }, (_, i) => post('api/auth/signup', { username: `gb${T}${k}${String(i).padStart(2, '0')}`, password: 'secret1', name: 'x' })
    .then((r) => { if (r.status === 200) ok++; return r.arrayBuffer(); })));
  done = true; await poller;
  return Math.max(...lat);
}
const worst = [];
for (let k = 0; k < 3; k++) worst.push(await probe(64, k));
console.log(JSON.stringify({ worst, ok }));
"""
def t_scrypt():
  src = open(os.path.join(ROOT, 'lib', 'password.js'), encoding='utf-8').read()
  if 'scryptSync(' in src: return fail('F146 아직 scryptSync 를 씀')
  r = node(POOL_JS)
  if r.returncode: return fail('F146 스레드 풀 검사 실패: ' + r.stderr[-300:])
  pool = json.loads(r.stdout.strip().splitlines()[-1])['wait']
  if pool > 50: return fail('F146 해시 64개 뒤에서 gzip 이 %.0fms 기다림 (스레드 풀을 해시가 다 차지)' % pool)
  r = node(BURST_JS, {'T_URL': URL, 'T_TAG': tag}, timeout=300)
  if r.returncode: return fail('F146 가입 몰아 보내기 실패: ' + r.stderr[-300:])
  burst = json.loads(r.stdout.strip().splitlines()[-1])
  if burst['ok'] < 3 * 64: return fail('F146 가입이 다 되지 않음 (%d/192) — 검사가 헛돎' % burst['ok'])
  worst = sorted(burst['worst'])[1]   # 세 번 중 가운데 — 다른 일로 바쁜 기계를 생각해서
  if worst > 150: return fail('F146 가입 64개가 몰리는 동안 gzip 응답이 %.0fms 섬 %s' % (worst, burst['worst']))
  # 비밀번호 검사가 여전히 맞게 동작한다 (await 를 빠뜨리면 틀린 비밀번호도 통과한다)
  c = Client(); c.json('POST', 'api/auth/signup', {'username': 'pw' + tag, 'password': 'right-pw', 'name': 'x'})
  if Client().json('POST', 'api/auth/login', {'username': 'pw' + tag, 'password': 'wrong-pw'})[0] != 401: return fail('F146 틀린 비밀번호로 로그인됨')
  if Client().json('POST', 'api/auth/login', {'username': 'pw' + tag, 'password': 'right-pw'})[0] != 200: return fail('F146 맞는 비밀번호로 로그인 안 됨')
  st, _ = c.json('POST', 'api/auth/password', {'current': 'nope-nope', 'next': 'new-pw-1'})
  if st != 401: return fail('F146 틀린 현재 비밀번호로 바뀜: %s' % st)
  st, _ = c.json('POST', 'api/auth/password', {'current': 'right-pw', 'next': 'new-pw-1'})
  if st != 200: return fail('F146 비밀번호 변경 실패 %s' % st)
  st, j = c.json('POST', 'api/auth/recovery', {'password': 'new-pw-1'})
  code = j.get('code')
  if Client().json('POST', 'api/auth/recover', {'username': 'pw' + tag, 'code': 'aaaa-bbbb-cccc', 'next': 'x-pw-123'})[0] != 401: return fail('F146 틀린 복구 코드가 통과')
  if Client().json('POST', 'api/auth/recover', {'username': 'pw' + tag, 'code': code, 'next': 'rec-pw-1'})[0] != 200: return fail('F146 복구 코드가 안 먹음')
  if Client().json('POST', 'api/auth/login', {'username': 'pw' + tag, 'password': 'rec-pw-1'})[0] != 200: return fail('F146 복구한 비밀번호로 로그인 안 됨')
  print('ok F146 — 해시 64개 뒤 gzip %.1fms, 가입 64개 동안 gzip 응답 최대 %.0fms %s, 로그인·변경·복구 검사 그대로' % (pool, worst, [round(x) for x in burst['worst']]))

# ---------- F104 ----------
PRESIGN_JS = r'''
process.env.R2_ENDPOINT = 'http://127.0.0.1:9'; process.env.R2_BUCKET = 'b';
process.env.R2_ACCESS_KEY_ID = 'AKIAFAKE'; process.env.R2_SECRET_ACCESS_KEY = 'fake';
const { presignPut } = await import('./lib/blob.js');
const p = await presignPut('teams/audit-infra-probe/x.jpg', 'image/jpeg', 10, 12345);
const u = new URL(p.url);
console.log(JSON.stringify({ signed: u.searchParams.get('X-Amz-SignedHeaders'), expires: u.searchParams.get('X-Amz-Expires') }));
process.exit(0);
'''
def put(url, data, ctype='image/jpeg'):
  req = urllib.request.Request(url, data=data, method='PUT', headers={'content-type': ctype})
  try:
    with urllib.request.urlopen(req, timeout=30) as r: return r.status
  except urllib.error.HTTPError as e: return e.code

def t_presign():
  # 1) 운영(R2) 서명 URL: 크기가 서명에 들어가고 10분만 산다 (가짜 키로 만들기만 — 네트워크 없음)
  r = node(PRESIGN_JS, {'DATABASE_URL': DB})
  sql("delete from blob_trash where url like 'http://127.0.0.1:9/%'")
  if r.returncode: return fail('F104 서명 URL 을 못 만듦: ' + r.stderr[-300:])
  j = json.loads(r.stdout.strip().splitlines()[-1])
  if 'content-length' not in (j['signed'] or ''): return fail('F104 크기가 서명에 안 들어감: %s' % j)
  if int(j['expires']) > 600: return fail('F104 서명 URL 이 너무 오래 삶: %s초' % j['expires'])

  # 2) 개발 서버에서 흐름 전체: 크기 없이 → 400, 다른 크기로 올리면 → 거절, 같은 크기 → 등록
  c = Client(); team = signup(c, 'iu')
  st, j = c.json('POST', 'api/blobs/au%s/upload-url' % tag, {'teamId': team, 'mime': 'image/jpeg'})
  if st != 400: return fail('F104 크기 없이 서명 URL 을 줌: %s' % st)
  body = b'\xff\xd8' + os.urandom(5000)
  st, u = c.json('POST', 'api/blobs/au%s/upload-url' % tag, {'teamId': team, 'size': len(body), 'mime': 'image/jpeg'})
  if st != 200: return fail('F104 서명 URL 실패 %s %s' % (st, u))
  if put(u['uploadUrl'], body + b'more') < 400: return fail('F104 알린 크기보다 큰 파일이 올라감')
  if put(u['uploadUrl'], body) != 200: return fail('F104 알린 크기 그대로인데 못 올림')
  st, reg = c.json('POST', 'api/blobs/au%s/register' % tag, {'teamId': team, 'pathname': u['pathname']})
  if st != 200: return fail('F104 등록 실패 %s %s' % (st, reg))
  kept_url = reg['url']
  # 등록한 id 로 서명 URL 을 다시 받아 다른 크기로 덮고 등록은 안 한다 → blobs 에는 옛 크기가 남는다(치울 때 맞춘다)
  st, u3 = c.json('POST', 'api/blobs/au%s/upload-url' % tag, {'teamId': team, 'size': 2222, 'mime': 'image/jpeg'})
  if st != 200 or put(u3['uploadUrl'], os.urandom(2222)) != 200: return fail('F104 같은 id 다시 올리기 실패 %s' % st)
  if sql('select size from blobs where team_id=$1 and id=$2', [team, 'au' + tag])[0]['size'] != len(body): return fail('F104 등록 안 했는데 크기가 바뀜')

  # 3) 받아 놓고 등록 안 한 파일: blob_trash 에 하루 뒤로 예약돼 있다가, 기한이 지나면 치운다. 등록한 파일은 남는다
  st, u2 = c.json('POST', 'api/blobs/ao%s/upload-url' % tag, {'teamId': team, 'size': 3000, 'mime': 'image/jpeg'})
  if put(u2['uploadUrl'], os.urandom(3000)) != 200: return fail('F104 두 번째 업로드 실패')
  orphan_url = u2['uploadUrl'].split('?')[0]
  rows = sql("select url, extract(epoch from due_at - now())::int as left from blob_trash where url = any($1::text[])", [[orphan_url, kept_url]])
  if len(rows) != 2 or min(r['left'] for r in rows) < 3600 * 20: return fail('F104 등록 안 한 파일이 치울 목록에 하루 뒤로 안 올라감: %s' % rows)
  if Client().call('GET', orphan_url)[0] != 200: return fail('F104 두 번째 파일이 안 올라가 있음')
  sql("update blob_trash set due_at = now() - interval '1 minute' where url = any($1::text[])", [[orphan_url, kept_url]])
  r = node("const m = await import('./lib/blob.js'); console.log(JSON.stringify(await m.sweepBlobs())); process.exit(0);",
           {'DATABASE_URL': DB, 'BLOB_LOCAL_DIR': BLOB_DIR, 'BLOB_LOCAL_BASE': URL.rstrip('/')})
  if r.returncode: return fail('F104 치우기 실패: ' + r.stderr[-300:])
  if Client().call('GET', orphan_url)[0] != 404: return fail('F104 등록 안 한 파일이 남음')
  if Client().call('GET', kept_url)[0] != 200: return fail('F104 등록한 파일까지 지움')
  if sql('select url from blob_trash where url = any($1::text[])', [[orphan_url, kept_url]]): return fail('F104 치운 뒤에도 목록에 남음')
  size = sql('select size from blobs where team_id=$1 and id=$2', [team, 'au' + tag])[0]['size']
  if size != 2222: return fail('F104 덮어쓴 파일 크기가 blobs 에 안 맞춰짐: %s (저장소에는 2222)' % size)
  print('ok F104 — 서명에 크기(content-length)·10분, 다른 크기 거절, 등록 안 한 파일만 치움, 덮어쓴 크기 맞춤 %s' % r.stdout.strip().splitlines()[-1])

# 서명 URL 은 사람당 15분에 200개 (받기만 해도 blob_trash 에 줄이 쌓인다). 한 문장으로 세니 한꺼번에 보내도 못 넘긴다
def t_upload_rate():
  c = Client(); team = signup(c, 'ir')
  uid = c.json('GET', 'api/me')[1]['user']['id']
  key = 'upload|' + uid
  try:
    sql("insert into login_attempts(username, n, last) values($1, 190, now())", [key])
    res = []
    def one(i):
      res.append(c.json('POST', 'api/blobs/ar%s%02d/upload-url' % (tag, i), {'teamId': team, 'size': 1000 + i, 'mime': 'image/jpeg'})[0])
    ws = [threading.Thread(target=one, args=(i,)) for i in range(30)]
    for w in ws: w.start()
    for w in ws: w.join()
    if sorted(res).count(200) != 10 or res.count(429) != 20: return fail('F104 한도 200 에서 멈추지 않음: 200=%d 429=%d %s' % (res.count(200), res.count(429), sorted(set(res))))
    st, j = c.json('POST', 'api/rehearsals/upload-url', {'teamId': team, 'size': 5000, 'mime': 'audio/mp4'})
    if st != 429: return fail('F104 녹음 서명 URL 은 한도를 따로 셈: %s' % st)
    # 창은 처음 받은 때부터 15분 — 띄엄띄엄 받아도 끝없이 쌓이지 않는다
    sql("update login_attempts set n=5, last=now() - interval '10 minutes' where username=$1", [key])
    if c.json('POST', 'api/blobs/as%s/upload-url' % tag, {'teamId': team, 'size': 10, 'mime': 'image/jpeg'})[0] != 200: return fail('F104 한도 아래인데 막힘')
    row = sql("select n, extract(epoch from now() - last)::int as age from login_attempts where username=$1", [key])[0]
    if row['n'] != 6 or row['age'] < 500: return fail('F104 창이 받을 때마다 밀림: %s' % row)
    sql("update login_attempts set n=200, last=now() - interval '16 minutes' where username=$1", [key])
    if c.json('POST', 'api/blobs/at%s/upload-url' % tag, {'teamId': team, 'size': 10, 'mime': 'image/jpeg'})[0] != 200: return fail('F104 15분이 지나도 막힘')
    if sql("select n from login_attempts where username=$1", [key])[0]['n'] != 1: return fail('F104 15분 뒤 새로 세지 않음')
    print('ok F104 — 서명 URL 30개를 한꺼번에: 한도까지 10개만, 나머지 429 (녹음도 같은 한도), 15분 창')
  finally:
    sql('delete from login_attempts where username=$1', [key])
    sql("delete from blob_trash where url like $1", ['%/teams/' + team + '/%'])

# 치우기는 한 번에 limit 개씩 끊어 남은 게 없을 때까지 돈다 (전에는 하루 3,000개에서 멈춰 뒤의 것이 밀렸다).
# 공용 DB 의 다른 줄을 건드리지 않게 이 검사만의 주소·폴더를 쓴다
SWEEP_JS = r'''
import fs from 'node:fs/promises'; import path from 'node:path';
const { sweepBlobs } = await import('./lib/blob.js');
const { q } = await import('./lib/db.js');
const B = process.env.BLOB_LOCAL_BASE + '/localblob/', D = process.env.BLOB_LOCAL_DIR, T = process.env.T_TEAM;
const keys = Array.from({ length: 12 }, (_, i) => `teams/${T}/sw${i}.jpg`);
for (const k of keys) { const f = path.join(D, k); await fs.mkdir(path.dirname(f), { recursive: true }); await fs.writeFile(f, Buffer.alloc(100 + keys.indexOf(k))); await fs.writeFile(f + '.type', 'image/jpeg'); }
await q(`insert into blob_trash(url, due_at) select u, now() - interval '1 minute' from unnest($1::text[]) u`, [keys.map((k) => B + k)]);
// 0번은 등록된 파일인데 blobs 의 크기가 틀려 있다 (덮어쓴 뒤 등록을 안 한 것)
await q(`insert into blobs(team_id, id, url, pathname, type, size) values($1, 'sw0', $2, $3, 'image/jpeg', 1)`, [T, B + keys[0], keys[0]]);
const out = await sweepBlobs(5);
const left = [];
for (const k of keys) if (await fs.stat(path.join(D, k)).then(() => true, () => false)) left.push(k.split('/').pop());
const trash = (await q('select count(*)::int n from blob_trash where url like $1', [B + '%']))[0].n;
const size = (await q(`select size from blobs where team_id=$1 and id='sw0'`, [T]))[0].size;
await q(`delete from blobs where team_id=$1 and id='sw0'`, [T]);
await q('delete from blob_trash where url like $1', [B + '%']);
console.log(JSON.stringify({ out, left, trash, size })); process.exit(0);
'''
def t_sweep_batches():
  c = Client(); team = signup(c, 'iw')
  d = tempfile.mkdtemp(prefix='audit-sweep-')
  try:
    r = node(SWEEP_JS, {'DATABASE_URL': DB, 'BLOB_LOCAL_DIR': d, 'BLOB_LOCAL_BASE': 'http://audit-sweep-%s.invalid' % tag, 'T_TEAM': team})
    if r.returncode: return fail('F104 치우기 하네스 실패: ' + r.stderr[-400:])
    j = json.loads(r.stdout.strip().splitlines()[-1])
    if j['out'].get('deleted') != 11 or j['out'].get('kept') != 1 or j['trash'] != 0: return fail('F104 한 번에 다 치우지 않음 (5개씩 끊어 돌아야): %s' % j)
    if j['left'] != ['sw0.jpg']: return fail('F104 남은 파일이 이상함: %s' % j['left'])
    if j['size'] != 100 or j['out'].get('resized') != 1: return fail('F104 살아 있는 파일의 크기를 안 맞춤: %s' % j)
    print('ok F104 — 치우기를 5개씩 끊어 12개 한 번에 (지움 11 · 남김 1), 남긴 파일의 크기를 blobs 에 맞춤')
  finally:
    shutil.rmtree(d, ignore_errors=True)

# ---------- F105 ----------
# 가짜 S3(127.0.0.1)를 띄워 R2 삭제를 흉내 낸다. 1,000개 넘게 한 번에 보내면 진짜처럼 거절한다
DEL_JS = r'''
import http from 'node:http';
const seen = []; let failKeys = true;
const srv = http.createServer((req, res) => {
  let b = ''; req.on('data', (c) => b += c); req.on('end', () => {
    const keys = [...b.matchAll(/<Key>([^<]*)<\/Key>/g)].map((m) => m[1]);
    seen.push(keys.length);
    res.setHeader('content-type', 'application/xml');
    if (keys.length > 1000) { res.statusCode = 400; return res.end('<?xml version="1.0"?><Error><Code>MalformedXML</Code><Message>too many</Message></Error>'); }
    const errs = failKeys ? keys.filter((k) => k.includes('fail')) : [];
    res.end('<?xml version="1.0" encoding="UTF-8"?><DeleteResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">' +
      errs.map((k) => `<Error><Key>${k}</Key><Code>InternalError</Code><Message>try again</Message></Error>`).join('') + '</DeleteResult>');
  });
});
await new Promise((r) => srv.listen(0, '127.0.0.1', r));
const base = `http://127.0.0.1:${srv.address().port}`;
process.env.R2_ENDPOINT = base; process.env.R2_BUCKET = 'b';
process.env.R2_ACCESS_KEY_ID = 'AKIAFAKE'; process.env.R2_SECRET_ACCESS_KEY = 'fake';
const { delBlobs, sweepBlobs } = await import('./lib/blob.js');
const { q } = await import('./lib/db.js');
const T = process.env.T_TAG;
const urls = Array.from({ length: 2500 }, (_, i) => `${base}/b/teams/audit-${T}/${i % 700 === 0 ? 'fail' : 'ok'}-${i}.jpg`);
await delBlobs(urls);
const first = seen.slice(); seen.length = 0;
const trash = (await q('select url from blob_trash where url like $1', [base + '/%'])).map((r) => r.url).sort();
await q(`update blob_trash set due_at = now() - interval '1 minute' where url like $1`, [base + '/%']);
failKeys = false;
const swept = await sweepBlobs();
const left = (await q('select count(*)::int n from blob_trash where url like $1', [base + '/%']))[0].n;
await q('delete from blob_trash where url like $1', [base + '/%']);
console.log(JSON.stringify({ first, trash: trash.map((u) => u.split('/').pop()), second: seen, swept, left }));
srv.close(); process.exit(0);
'''
def t_delete_chunks():
  r = node(DEL_JS, {'DATABASE_URL': DB, 'T_TAG': tag})
  if r.returncode: return fail('F105 하네스 실패: ' + r.stderr[-400:])
  j = json.loads(r.stdout.strip().splitlines()[-1])
  if not j['first'] or max(j['first']) > 1000 or sum(j['first']) != 2500:
    return fail('F105 삭제 요청을 1,000개씩 나누지 않음: %s' % j['first'])
  want = sorted('fail-%d.jpg' % i for i in range(0, 2500, 700))
  if j['trash'] != want: return fail('F105 못 지운 파일이 blob_trash 에 안 적힘: %s' % j['trash'])
  if sum(j['second']) != len(want) or j['swept'].get('deleted') != len(want) or j['left'] != 0:
    return fail('F105 다시 지우기가 안 됨: %s' % j)
  print('ok F105 — 2,500개를 %s 로 나눠 보냄, 실패한 %d개는 적었다가 다시 지움' % (j['first'], len(want)))

# ---------- F147 ----------
def t_migrate_library(tmp):
  db2 = tmp.url
  u = sql("insert into users(username, password_hash, display_name) values('mig', 'x', '이행') returning id", db=db2)[0]['id']
  t = sql("insert into teams(name, invite_token, created_by) values('이행팀', 'tok-mig', $1) returning id", [u], db=db2)[0]['id']
  # 이미 옮긴 다른 팀 (곡이 있어 건너뛴다). 이 팀의 곡 id 가 가져온 콘티의 제목 없는 칸에 남아 있다
  t2 = sql("insert into teams(name, invite_token, created_by) values('다른팀', 'tok-mig2', $1) returning id", [u], db=db2)[0]['id']
  s2 = sql("insert into songs(team_id, title, title_norm) values($1, '남의 곡', '남의곡') returning id", [t2], db=db2)[0]['id']
  a2 = sql("insert into arrangements(song_id, team_id, is_default) values($1, $2, true) returning id", [s2, t2], db=db2)[0]['id']
  sql("insert into library(team_id, id, song) values($1, 'L1', $2)", [t, json.dumps({'title': '주 이름 찬양', 'key': 'G'})], db=db2)
  sql("insert into library(team_id, id, song) values($1, 'L2', $2)", [t, json.dumps({'title': '-', 'key': 'C'})], db=db2)
  items = [{'id': 'a', 'title': ''}, {'id': 'b', 'title': '  '}, {'id': 'c'},
           {'id': 'f', 'title': '', 'songId': s2, 'arrId': a2},                                  # 남의 팀 곡
           {'id': 'g', 'title': '', 'songId': str(uuid.uuid4()), 'arrId': str(uuid.uuid4())},    # 없는 곡 (전에는 FK 로 이행 전체가 실패)
           {'id': 'd', 'title': '새 노래', 'key': 'A'}, {'id': 'e', 'title': '주 이름 찬양', 'key': 'G'}, {'id': 'h', 'title': '-', 'key': 'C'}]
  for i in range(3):
    doc = {'name': '예배 %d' % i, 'date': '2026-01-0%d' % (i + 1), 'items': items}
    sql("insert into services(team_id, id, doc) values($1, $2, $3)", [t, 's%d' % i, json.dumps(doc)], db=db2)
  r = subprocess.run(['node', 'scripts/migrate-library.mjs', '--apply'], cwd=ROOT, env={**os.environ, 'DATABASE_URL': db2}, capture_output=True, text=True, timeout=120)
  if r.returncode: return fail('F147 이행 실패: ' + (r.stderr or r.stdout)[-300:])
  titles = sorted(x['title'] for x in sql('select title from songs where team_id=$1', [t], db=db2))
  if titles != ['-', '새 노래', '주 이름 찬양']: return fail('F147 제목 없는 항목으로 곡이 생김: %s' % titles)
  uses = sql('select count(*)::int n from song_usages where team_id=$1', [t], db=db2)[0]['n']
  if uses != 9: return fail('F147 사용 이력이 이상함: %s (예배 3개 × 곡 3)' % uses)
  if sql('select count(*)::int n from song_usages where song_id=$1', [s2], db=db2)[0]['n']: return fail('F147 남의 팀 곡으로 사용 이력이 생김')
  dash = sql("select s.id from songs s where s.team_id=$1 and s.title='-'", [t], db=db2)[0]['id']
  doc = sql("select doc from services where team_id=$1 and id='s0'", [t], db=db2)[0]['doc']
  its = {it['id']: it for it in doc['items']}
  if any(its[k].get('arrId') or its[k].get('songId') for k in 'abcfg') or not all(its[k].get('arrId') for k in 'deh'):
    return fail('F147 항목 연결이 이상함: %s' % doc['items'])
  if its['h'].get('songId') != dash: return fail("F147 '-' 칸이 '-' 곡에 안 붙음")
  print("ok F147 — 제목 없는 칸 15개에서 곡이 안 생김, 남은 남의·없는 곡 id 는 지움, 공백 제목은 '-' 곡에 안 붙음, 사용 이력 9")

def run(t, *a):
  try: t(*a)
  except SystemExit as e: fail('%s: %s' % (t.__name__, e))
  except Exception as e: fail('%s: %r' % (t.__name__, e))

for t in (t_bad_url_prod_entry, t_gzip, t_scrypt, t_presign, t_upload_rate, t_sweep_batches, t_delete_chunks): run(t)
try:
  with TempDB() as tmp:
    run(t_plus_plan, tmp)
    run(t_migrate_library, tmp)
except SystemExit as e: fail('임시 DB: %s' % e)
# 옛 dev.mjs 는 여기서 죽으므로 개발 서버를 쓰는 검사 중 맨 뒤에
run(t_bad_url_dev)

if FAILS:
  print('FAILED %d' % len(FAILS)); sys.exit(1)
print('INFRA AUDIT OK')
