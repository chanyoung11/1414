# 감사 묶음 api-ai-billing 회귀 검사
#  F47 F48 녹음 메모: 남의 메모 id 로 덮어쓰기 막힘 · 동시에 달아도 다 남음 · 세션·목회자 규칙
#  F49 F50 콘티 메모: 겸임 멤버가 모든 세션의 공유 메모를 받음 · 받지 않은 메모를 알려 주고 화면에서도 뺌
#  F51 F106 코드 인식: 그림이 아닌 형식은 넘기지 않음 · Gemini 실패는 502 + 뺀 곡을 돌려줌 · 있던 코드를 지킴
#  F53 F119 프로모션: 동시에 눌러도 한 번만 · 기한 없는/더 높은 플랜을 내리지 않음
#  F52 F107 결제 웹훅: 결제 담당의 팀 · RevenueCat 사건의 뜻 · 크레딧 중복 없음
#  F118 녹음 파일: 남의 녹음 id 앞부분으로 등록 불가 · 이미 있는 별칭을 지워도 원본은 남음
#  G21 채보: 고친 마디의 가사가 제자리에
# 다시 고친 것 (검증에서 돌아온 것)
#  F48 옛 자료(객체가 아닌 것·id·지은이 없는 것)는 녹음 메모 지우기에 안 걸림
#  F50 다른 팀 메모와 id 가 겹친 메모(다른 팀 파일에서 가져온 인도자 메모)는 새 id 로 넣고 알림 → 앱도 id 를 바꿈
#  F52 구독을 처음 반영한 팀에 적어 두고 그 팀으로 갱신·만료 (결제 담당을 넘겨도 · 새 팀 · 새 인도자 · 앱이 고른 팀)
#  F52 끊겼다 다시 산 것(RENEWAL)·속성 없는 새 구독·크레딧은 끊긴 옛 기록의 팀이 아니라 지금 고른 팀으로 (떠난 팀이 다시 유료가 되던 것)
# 사용: CONTI_URL=http://localhost:8817/ .venv/bin/python tests/test_audit_api_ai_billing.py
# (AI 는 가짜. 웹훅·코드 인식 실패는 서버 코드를 이 프로세스 안에서 fetch 를 막고 직접 부른다 — 밖으로 나가는 호출 없음)
# 준비(프로모션 코드·옛 별칭 행)는 로컬 DB 에 바로 쓴다: CONTI_DB (기본 localhost:54329, 서버와 같은 DB 여야 한다)
import os, sys, time, json, subprocess, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
if not URL.endswith('/'): URL += '/'
API = URL + 'api'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.environ.get('CONTI_DB', 'postgres://postgres:pg@localhost:54329/postgres')
SHEET = os.path.join(ROOT, 'docs', 'sample_sheet.jpg')
tag = str(int(time.time() * 10))[-7:]
def fail(m): print('FAIL:', m); sys.exit(1)

# ---------- 도우미 ----------
class Sess:
  def __init__(self): self.cookie = ''; self.uid = None
  def req(self, method, path, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    h = {'content-type': 'application/json', 'x-conti': '1'}
    if self.cookie: h['cookie'] = self.cookie
    h.update(headers or {})
    r = urllib.request.Request(API + path, method=method, data=data, headers=h)
    try:
      with urllib.request.urlopen(r, timeout=60) as resp: st, raw, hd = resp.status, resp.read(), resp.headers
    except urllib.error.HTTPError as e: st, raw, hd = e.code, e.read(), e.headers
    for c in hd.get_all('Set-Cookie') or []:
      if c.startswith('conti_s='): self.cookie = c.split(';')[0]
    try: return st, json.loads(raw or b'{}')
    except Exception: return st, {'raw': raw[:200]}

def signup(user, name):
  s = Sess()
  st, j = s.req('POST', '/auth/signup', {'username': user, 'password': 'secret12', 'name': name})
  if st != 200: fail('가입 실패 %s: %s %s' % (user, st, j))
  s.uid = j['user']['id']; return s

def db(sql, params=()):
  js = """import('pg').then(async ({default:pg})=>{const c=new pg.Client({connectionString:process.env.DB});await c.connect();
    const r=await c.query(process.env.SQL, JSON.parse(process.env.PARAMS));console.log(JSON.stringify(r.rows));await c.end()})
    .catch(e=>{console.log(JSON.stringify({error:e.message}));process.exit(1)})"""
  out = subprocess.run(['node', '-e', js], cwd=ROOT, capture_output=True, text=True,
                       env={**os.environ, 'DB': DB, 'SQL': sql, 'PARAMS': json.dumps(list(params))})
  try: return json.loads(out.stdout.strip().splitlines()[-1])
  except Exception: fail('DB 질의 실패: %s %s' % (out.stdout[-300:], out.stderr[-300:]))

def node(js, env=None):
  out = subprocess.run(['node', '--input-type=module', '-e', js], cwd=ROOT, capture_output=True, text=True,
                       env={**os.environ, 'ROOT': ROOT, **(env or {})}, timeout=120)
  lines = [l for l in out.stdout.strip().splitlines() if l.startswith('{')]
  if not lines: fail('node 실행 실패: %s %s' % (out.stdout[-500:], out.stderr[-800:]))
  return json.loads(lines[-1])

def par(fns, n=20):
  with ThreadPoolExecutor(max_workers=n) as ex: return list(ex.map(lambda f: f(), fns))

def upload_rehearsal(s, team, svc):
  st, u = s.req('POST', '/rehearsals/upload-url', {'teamId': team, 'size': 1000, 'mime': 'audio/mp4'})
  if st != 200: fail('녹음 올릴 자리 실패: %s %s' % (st, u))
  put = urllib.request.Request(u['uploadUrl'], method='PUT', data=b'\0' * 1000, headers={'content-type': 'audio/mp4'})
  urllib.request.urlopen(put, timeout=30).read()
  st, r = s.req('POST', '/rehearsals', {'teamId': team, 'serviceId': svc, 'blobId': u['blobId'], 'pathname': u['pathname'], 'duration': 60})
  if st != 200: fail('녹음 등록 실패: %s %s' % (st, r))
  return u, r['rehearsal']

def reh_notes(rid):
  return db("select coalesce(notes,'[]'::jsonb) as n from rehearsals where id=$1", [rid])[0]['n']

# ---------- 팀 ----------
L = signup('al' + tag, '인도')
st, t = L.req('POST', '/teams', {'name': '감사팀' + tag, 'myName': '인도'})
if st != 200: fail('팀 만들기 실패: %s %s' % (st, t))
TEAM, INV = t['teamId'], t['invite']
def member(user, name, sessions):
  s = signup(user, name)
  st, j = s.req('POST', '/invite/%s/join' % INV, {'name': name, 'sessions': sessions})
  if st != 200: fail('합류 실패 %s: %s %s' % (user, st, j))
  return s
A = member('aa' + tag, '겸임', ['일렉', '싱어'])
B = member('ab' + tag, '싱어', ['싱어'])
C = member('ac' + tag, '드럼', ['드럼'])
P = member('ap' + tag, '목사', ['드럼'])
st, _ = L.req('PATCH', '/teams/%s/members/%s' % (TEAM, P.uid), {'role': 'pastor'})
if st != 200: fail('목회자 지정 실패')

# ---------- F47 · F48 녹음 메모 ----------
u1, R = upload_rehearsal(L, TEAM, 'svcR')
RID = R['id']
st, _ = L.req('POST', '/rehearsals/%s/notes' % RID, {'teamId': TEAM, 'note': {'id': 'lead0001', 't': 5, 'text': '인도자 메모', 'layer': 'leader'}})
if st != 200: fail('인도자 녹음 메모 실패 %s' % st)
st, j = A.req('POST', '/rehearsals/%s/notes' % RID, {'teamId': TEAM, 'note': {'id': 'lead0001', 't': 1, 'text': '바꿔치기', 'layer': 'mine'}})
if st != 409: fail('F47 남의 메모 id 로 보냈는데 %s: %s' % (st, j))
ln = [n for n in reh_notes(RID) if n['id'] == 'lead0001']
if len(ln) != 1 or ln[0]['text'] != '인도자 메모' or ln[0]['layer'] != 'leader': fail('F47 인도자 메모가 바뀜: %s' % ln)
A.req('DELETE', '/rehearsals/%s/notes/lead0001?team=%s' % (RID, TEAM))
if not [n for n in reh_notes(RID) if n['id'] == 'lead0001']: fail('F47 멤버가 인도자 메모를 지움')
# 내 메모는 같은 id 로 다시 보내면 바뀐다 (재시도·고치기)
A.req('POST', '/rehearsals/%s/notes' % RID, {'teamId': TEAM, 'note': {'id': 'amine001', 't': 2, 'text': '처음', 'layer': 'mine'}})
st, _ = A.req('POST', '/rehearsals/%s/notes' % RID, {'teamId': TEAM, 'note': {'id': 'amine001', 't': 2, 'text': '고침', 'layer': 'mine'}})
mine = [n for n in reh_notes(RID) if n['id'] == 'amine001']
if st != 200 or len(mine) != 1 or mine[0]['text'] != '고침': fail('F47 내 메모 다시 쓰기: %s %s' % (st, mine))
# 세션 메모는 내 세션으로만
C.req('POST', '/rehearsals/%s/notes' % RID, {'teamId': TEAM, 'note': {'id': 'cses0001', 't': 3, 'text': '남의 세션', 'layer': 'session', 'session': '싱어'}})
cs = [n for n in reh_notes(RID) if n['id'] == 'cses0001']
if not cs or cs[0]['session'] != '드럼': fail('F47 남의 세션으로 세션 메모를 씀: %s' % cs)
A.req('POST', '/rehearsals/%s/notes' % RID, {'teamId': TEAM, 'note': {'id': 'ases0001', 't': 3, 'text': '싱어에게', 'layer': 'session', 'session': '싱어'}})
if [n for n in reh_notes(RID) if n['id'] == 'ases0001'][0]['session'] != '싱어': fail('F47 겸임 멤버가 내 둘째 세션에 못 씀')
# 목회자: 팀 설정이 꺼져 있으면 못 쓴다
st, _ = P.req('POST', '/rehearsals/%s/notes' % RID, {'teamId': TEAM, 'note': {'id': 'past0001', 't': 3, 'text': '목회자', 'layer': 'mine'}})
if st != 403: fail('F47 목회자 메모가 꺼져 있는데 %s' % st)
print('F47 ok — 남의 메모 id 거절 · 내 메모 고치기 · 세션 규칙 · 목회자 설정')

before = len(reh_notes(RID))
posts = [(lambda s=s, i=i: s.req('POST', '/rehearsals/%s/notes' % RID, {'teamId': TEAM, 'note': {'id': 'par%05d' % i, 't': i, 'text': '동시 %d' % i, 'layer': 'mine'}}))
         for i, s in enumerate([A, B, C, L] * 5)]
res = par(posts)
if any(st != 200 for st, _ in res): fail('F48 동시 메모 중 실패: %s' % [st for st, _ in res])
after = reh_notes(RID)
if len(after) != before + 20: fail('F48 동시에 20개를 달았는데 %d개만 늘어남' % (len(after) - before))
# 지우기와 달기가 겹쳐도 서로 안 지운다
ops = [(lambda i=i: A.req('DELETE', '/rehearsals/%s/notes/par%05d?team=%s' % (RID, i, TEAM))) for i in range(0, 20, 4)] + \
      [(lambda i=i: B.req('POST', '/rehearsals/%s/notes' % RID, {'teamId': TEAM, 'note': {'id': 'mix%05d' % i, 't': i, 'text': '겹침', 'layer': 'mine'}})) for i in range(10)]
par(ops)
ids = {n['id'] for n in reh_notes(RID)}
if any(('par%05d' % i) in ids for i in range(0, 20, 4)): fail('F48 지운 메모가 되살아남')
if any(('mix%05d' % i) not in ids for i in range(10)): fail('F48 지우는 동안 단 메모가 사라짐')
if len(ids) != len(after) - 5 + 10: fail('F48 개수가 맞지 않음: %d' % len(ids))
print('F48 ok — 동시에 20개 모두 남음 · 지우기와 달기가 겹쳐도 안 잃음')

# 옛 자료(객체가 아닌 것·null·id 없는 것·지은이 칸 없는 것)는 지우기가 건드리지 않는다 (JS 로 거르던 때와 같이).
# SQL 비교가 NULL 이 되면 '지울 것'으로 읽혀, 인도자가 메모 하나를 지울 때 이런 원소가 같이 사라졌다
_, R3 = upload_rehearsal(L, TEAM, 'svcR3')
db('update rehearsals set notes = $2::jsonb where id=$1', [R3['id'], json.dumps(
  ['옛 글자', None, {'t': 1, 'text': 'id 없음'}, {'id': 'legacy01', 't': 2, 'text': '지은이 없음'},
   {'id': 'lead0003', 't': 3, 'text': '인도자', 'layer': 'leader', 'authorId': L.uid}])])
st, _ = L.req('DELETE', '/rehearsals/%s/notes/lead0003?team=%s' % (R3['id'], TEAM))
n3 = reh_notes(R3['id'])
if st != 200 or n3 != ['옛 글자', None, {'t': 1, 'text': 'id 없음'}, {'id': 'legacy01', 't': 2, 'text': '지은이 없음'}]:
  fail('F48 인도자가 메모 하나를 지우다 옛 자료까지 지움: %s %s' % (st, n3))
A.req('DELETE', '/rehearsals/%s/notes/legacy01?team=%s' % (R3['id'], TEAM))
if len(reh_notes(R3['id'])) != 4: fail('F48 멤버가 지은이 없는 옛 메모를 지움: %s' % reh_notes(R3['id']))
L.req('DELETE', '/rehearsals/%s/notes/legacy01?team=%s' % (R3['id'], TEAM))
if [n for n in reh_notes(R3['id']) if isinstance(n, dict) and n.get('id') == 'legacy01'] or len(reh_notes(R3['id'])) != 3:
  fail('F48 인도자가 지은이 없는 옛 메모를 못 지우거나 다른 것까지 지움: %s' % reh_notes(R3['id']))
print('F48 ok — 옛 자료는 지우기에 안 걸림 (인도자는 그 메모만 지움)')

# ---------- F49 · F50 콘티 메모 (API) ----------
SV = 'svcN' + tag
NID = {k: k + tag for k in ['bsing001', 'lnote001', 'pnote001', 'cfake001', 'lsvc0001', 'pold0001']}   # notes.id 는 전역 기본키
B.req('POST', '/notes', {'teamId': TEAM, 'serviceId': SV, 'notes': [{'id': NID['bsing001'], 'itemId': 'it1', 'layer': 'session', 'session': '싱어', 'text': '싱어 공유', 'at': int(time.time() * 1000)}]})
st, ga = A.req('GET', '/notes?team=%s&service=%s' % (TEAM, SV))
if NID['bsing001'] not in [n['id'] for n in ga.get('notes', [])]: fail('F49 겸임(일렉·싱어) 멤버가 싱어 공유 메모를 못 받음')
st, gc = C.req('GET', '/notes?team=%s&service=%s' % (TEAM, SV))
if NID['bsing001'] in [n['id'] for n in gc.get('notes', [])]: fail('F49 드럼에게 싱어 메모가 보임')
print('F49 ok — 겸임 멤버가 둘째 세션 공유 메모를 받음')

L.req('POST', '/notes', {'teamId': TEAM, 'serviceId': SV, 'notes': [{'id': NID['lnote001'], 'itemId': 'it1', 'layer': 'leader', 'text': '전체 메모'}]})
st, j = P.req('POST', '/notes', {'teamId': TEAM, 'serviceId': SV, 'notes': [
  {'id': NID['pnote001'], 'itemId': 'it1', 'layer': 'mine', 'text': '목회자 메모'},
  {'id': NID['lnote001'], 'itemId': 'it1', 'layer': 'leader', 'text': '전체 메모'}]})
rj = {r['id']: r['why'] for r in j.get('rejected', [])}
if st != 200 or rj.get(NID['pnote001']) != 'pastor': fail('F50 목회자 메모 거절이 안 알려짐: %s %s' % (st, j))
if NID['lnote001'] in rj: fail('F50 서버에 이미 있는 인도자 메모를 거절로 알림 (클라이언트가 지운다): %s' % j)
st, j = C.req('POST', '/notes', {'teamId': TEAM, 'serviceId': SV, 'notes': [{'id': NID['cfake001'], 'itemId': 'it1', 'layer': 'leader', 'text': '가짜 전체'}]})
if [r for r in j.get('rejected', []) if r['id'] == NID['cfake001']] != [{'id': NID['cfake001'], 'why': 'leader'}]: fail('F50 멤버의 전체 메모 거절이 안 알려짐: %s' % j)
print('F50 서버 ok — 받지 않은 메모를 id·까닭으로 돌려줌 (서버에 있는 것은 빼고)')

# notes.id 는 모든 팀을 통틀어 하나다. 다른 팀 파일에서 가져온 인도자 메모는 원래 id 를 지녀 그 팀 메모와 겹친다.
# 전에는 넣지 못하고도 saved:1 로 답해 앱이 그림자에 넣었고, 다음 받기 때 메모가 말없이 사라졌다
LX = signup('ax' + tag, '다른팀')
st, tx = LX.req('POST', '/teams', {'name': '다른팀' + tag, 'myName': '인도'})
if st != 200: fail('다른 팀 만들기 실패 %s %s' % (st, tx))
TX = tx['teamId']
XID = 'xnote001' + tag
LX.req('POST', '/notes', {'teamId': TX, 'serviceId': 'svcX' + tag, 'notes': [{'id': XID, 'itemId': 'it1', 'layer': 'leader', 'text': '다른 팀 메모'}]})
imp = {'teamId': TEAM, 'serviceId': SV, 'notes': [{'id': XID, 'itemId': 'it1', 'layer': 'leader', 'text': '가져온 메모'}]}
st, j = L.req('POST', '/notes', imp)
ren = j.get('renamed') or []
if st != 200 or j.get('rejected') or j.get('saved') != 1 or len(ren) != 1 or ren[0].get('id') != XID or not ren[0].get('to'):
  fail('F50 다른 팀 메모와 id 가 겹친 메모를 새 id 로 넣고 알리지 않음: %s %s' % (st, j))
ALT = ren[0]['to']
st, j2 = L.req('POST', '/notes', imp)   # 다시 보내도(renamed 를 모르는 옛 앱) 같은 새 id — 두 번 들어가지 않는다
if j2.get('renamed') != ren or j2.get('saved') != 1: fail('F50 같은 메모를 다시 보냈더니 다른 답: %s' % j2)
st, g = L.req('GET', '/notes?team=%s&service=%s' % (TEAM, SV))
if [n['id'] for n in g.get('notes', []) if n['text'] == '가져온 메모'] != [ALT]: fail('F50 가져온 메모가 서버에 새 id 로 하나만 있지 않음: %s' % g)
st, gx = LX.req('GET', '/notes?team=%s&service=%s' % (TX, 'svcX' + tag))
if [(n['id'], n['text']) for n in gx.get('notes', [])] != [(XID, '다른 팀 메모')]: fail('F50 원래 팀의 메모가 바뀜: %s' % gx)
# 이 콘티에 이미 있는 남의 메모를 다시 보낸 것(그림자를 잃은 기기)은 저장으로 친다 — 거절·새 id 없음
st, j = A.req('POST', '/notes', {'teamId': TEAM, 'serviceId': SV, 'notes': [{'id': NID['bsing001'], 'itemId': 'it1', 'layer': 'session', 'session': '싱어', 'text': '싱어 공유'}]})
if st != 200 or j.get('rejected') or j.get('renamed') or j.get('saved') != 1: fail('F50 이 콘티에 있는 메모를 다시 보낸 것을 달리 답함: %s' % j)
print('F50 서버 ok — 다른 팀과 id 가 겹친 메모는 새 id 로 넣고 renamed 로 알림 (다시 보내도 하나)')

# ---------- F118 녹음 파일 별칭 ----------
L.req('PATCH', '/rehearsals/%s' % RID, {'teamId': TEAM, 'keep': True})
st, j = A.req('POST', '/rehearsals', {'teamId': TEAM, 'serviceId': 'svcR', 'blobId': u1['blobId'][:5], 'pathname': u1['pathname'], 'duration': 5})
if st != 400: fail('F118 남의 녹음 id 앞부분으로 등록됨: %s %s' % (st, j))
st, j = L.req('POST', '/blobs/rehe/register', {'teamId': TEAM, 'pathname': u1['pathname']})
if st != 400: fail('F118 짧은 id 로 녹음 파일을 악보 파일로 등록함: %s %s' % (st, j))
# 예전 검사로 이미 생긴 별칭(같은 파일을 가리키는 다른 행)을 지워도 원본 파일은 남는다
row = db('select url, pathname, type, size from blobs where team_id=$1 and id=$2', [TEAM, u1['blobId']])[0]
alias = u1['blobId'][:5]
db('insert into blobs(team_id, id, url, pathname, type, size) values($1,$2,$3,$4,$5,$6)', [TEAM, alias, row['url'], row['pathname'], row['type'], row['size']])
aid = db("insert into rehearsals(team_id, service_id, date, label, blob_id, uploaded_by) values($1,'svcR',current_date,'별칭',$2,$3) returning id", [TEAM, alias, A.uid])[0]['id']
st, _ = L.req('DELETE', '/rehearsals/%s?team=%s' % (aid, TEAM))
if st != 200: fail('F118 별칭 녹음 지우기 실패 %s' % st)
try: code = urllib.request.urlopen(row['url'], timeout=10).status
except urllib.error.HTTPError as e: code = e.code
if code != 200: fail('F118 별칭을 지웠더니 보관 잠금한 원본 녹음이 %s' % code)
print('F118 ok — 앞부분 id 등록 거절 · 별칭을 지워도 원본 유지')

# ---------- F53 · F119 프로모션 ----------
# teams.plan 제약이 아직 'plus' 를 받지 않는 DB 면(다른 수정에서 넓힌다) Plus 가 끼는 검사는 건너뛴다
PLUS = "'plus'" in (db("select pg_get_constraintdef(oid) as d from pg_constraint where conname='teams_plan_check'") or [{'d': ''}])[0]['d']
C1, C2, C3 = 'AUD1' + tag, 'AUD2' + tag, 'AUD3' + tag
db("insert into promo_codes(code, plan, days, max_uses) values($1,'pro',30,1),($2,'pro',30,50),($3,'pro',30,50)", [C1, C2, C3])
def new_leader(i):
  s = signup('pl%d%s' % (i, tag), '리더%d' % i)
  st, t = s.req('POST', '/teams', {'name': '코드팀%d' % i, 'myName': '리더'})
  if st != 200: fail('코드팀 만들기 실패 %s %s' % (st, t))
  s.team = t['teamId']; return s
leaders = par([(lambda i=i: new_leader(i)) for i in range(10)], 10)
res = par([(lambda s=s: s.req('POST', '/promo/redeem', {'teamId': s.team, 'code': C1})) for s in leaders])
okn = sum(1 for st, _ in res if st == 200)
used = db('select used from promo_codes where code=$1', [C1])[0]['used']
nred = db('select count(*)::int n from promo_redemptions where code=$1', [C1])[0]['n']
if okn != 1 or used != 1 or nred != 1: fail('F53 1회용 코드를 10팀이 동시에: 성공 %d · used %d · 기록 %d' % (okn, used, nred))
T1 = leaders[1] if res[0][0] == 200 else leaders[0]   # 코드를 못 받은 팀
res = par([(lambda: T1.req('POST', '/promo/redeem', {'teamId': T1.team, 'code': C2})) for _ in range(15)], 15)
okn = sum(1 for st, _ in res if st == 200)
if okn != 1 or any(st not in (200, 400) for st, _ in res): fail('F53 같은 팀 15번 동시: %s' % [st for st, _ in res])
days = db("select extract(epoch from plan_until - now())/86400 as d from teams where id=$1", [T1.team])[0]['d']
if not (29 < float(days) < 31): fail('F53 30일 코드인데 %.1f일이 쌓임' % float(days))
if db('select used from promo_codes where code=$1', [C2])[0]['used'] != 1: fail('F53 같은 팀인데 코드 사용 수가 여러 번 늘어남')
print('F53 ok — 1회용 코드는 한 팀만 · 같은 팀 동시 요청도 기간 한 번')

T2, T3, T4 = leaders[2], leaders[3], leaders[4]
db("update teams set plan='pro', plan_until=null, plan_source='manual' where id=$1", [T2.team])
st, j = T2.req('POST', '/promo/redeem', {'teamId': T2.team, 'code': C3})
t2 = db('select plan, plan_until from teams where id=$1', [T2.team])[0]
if st != 400 or t2['plan'] != 'pro' or t2['plan_until'] is not None: fail('F119 기한 없는 Pro 가 기한 있는 것으로 바뀜: %s %s %s' % (st, j, t2))
if PLUS:
  db("update teams set plan='plus', plan_until=now()+interval '10 days', plan_source='promo' where id=$1", [T3.team])
  st, j = T3.req('POST', '/promo/redeem', {'teamId': T3.team, 'code': C3})
  p3 = db('select plan from teams where id=$1', [T3.team])[0]['plan']
  db("update teams set plan='free', plan_until=null, plan_source=null where id=$1", [T3.team])   # 공유 DB 에 plus 를 남기지 않는다
  if st != 400 or p3 != 'plus': fail('F119 Plus 가 Pro 코드로 내려감: %s %s' % (st, j))
else: print('F119 Plus 검사 건너뜀 — DB 가 아직 plus 플랜을 받지 않음')
db("update teams set plan='pro', plan_until=now()+interval '10 days', plan_source='promo' where id=$1", [T4.team])
st, j = T4.req('POST', '/promo/redeem', {'teamId': T4.team, 'code': C3})
d4 = float(db("select extract(epoch from plan_until - now())/86400 as d from teams where id=$1", [T4.team])[0]['d'])
if st != 200 or not (39 < d4 < 41): fail('F119 남은 Pro 10일에 30일이 이어 붙지 않음: %s %s %.1f' % (st, j, d4))
if db('select used from promo_codes where code=$1', [C3])[0]['used'] != 1: fail('F119 거절한 요청이 코드를 써 버림')
print('F119 ok — 기한 없는/더 높은 플랜은 그대로 · 같은 플랜은 이어 붙임')

# ---------- F52 · F107 · F106 · F51 서버 안에서 (fetch 막음) ----------
INPROC = r"""
process.env.ENFORCE_PLAN = '1'; process.env.GEMINI_API_KEY = 'fake'; process.env.RC_WEBHOOK_SECRET = 'audit-secret';
process.env.DATABASE_URL = process.env.DB; process.env.AUTH_SECRET = process.env.AUTH_SECRET || 'local-dev-secret-0123456789';
process.env.BLOB_LOCAL_DIR = process.env.BLOB_LOCAL_DIR || (process.env.ROOT + '/.localblob');
delete process.env.GOOGLE_VISION_KEY; delete process.env.GOOGLE_APPLICATION_CREDENTIALS;
const sent = [];
globalThis.fetch = async (u, o) => {
  if (String(u).includes('generativelanguage')) { sent.push(JSON.parse(o.body));
    return { ok: false, status: 503, json: async () => ({ error: { message: 'The model is overloaded. Please try again later.', status: 'UNAVAILABLE' } }) }; }
  throw new Error('blocked ' + u);
};
const { default: api } = await import(process.env.ROOT + '/api/index.js');
const { q, one } = await import(process.env.ROOT + '/lib/db.js');
const call = (method, path, body, headers = {}) => new Promise((resolve) => {
  const h = {};
  const res = { statusCode: 200, setHeader(k, v) { h[k.toLowerCase()] = v; }, getHeader(k) { return h[k.toLowerCase()]; },
    end(s) { let j = null; try { j = JSON.parse(s); } catch {} resolve({ status: this.statusCode, body: j, headers: h }); } };
  api({ method, url: '/api' + path, headers: { 'x-conti': '1', 'content-type': 'application/json', ...headers }, body, socket: { remoteAddress: '127.0.0.1' } }, res);
});
const T = process.env.TAG; const out = {};
const user = async (n) => { const r = await call('POST', '/auth/signup', { username: n + T, password: 'secret12', name: n });
  return { id: r.body.user.id, cookie: String(r.headers['set-cookie']).split(';')[0] }; };
const as = (u) => ({ cookie: u.cookie });
const plan = async (id) => one("select plan, plan_source, extract(epoch from plan_until - now())/86400 as d from teams where id=$1", [id]);
const day = 86400000;

// F52 · F107 결제 웹훅
const a = await user('wa'), b = await user('wb');
const team = (await call('POST', '/teams', { name: '결제팀', myName: '가' }, as(a))).body;
await call('POST', `/invite/${team.invite}/join`, { name: '나', sessions: ['드럼'] }, as(b));
const hook = (ev) => call('POST', '/iap/webhook', { event: { app_user_id: a.id, ...ev } }, { authorization: 'audit-secret' });
out.buy = (await hook({ type: 'INITIAL_PURCHASE', product_id: 'pro_monthly', expiration_at_ms: Date.now() + 30 * day, id: 'b1' + T })).body;
out.transfer = (await call('POST', `/teams/${team.teamId}/transfer`, { userId: b.id }, as(a))).status;
out.renew = (await hook({ type: 'RENEWAL', product_id: 'pro_monthly', expiration_at_ms: Date.now() + 60 * day, id: 'b2' + T })).body;
out.afterRenew = await plan(team.teamId);
out.paused = (await hook({ type: 'SUBSCRIPTION_PAUSED', product_id: 'pro_monthly', id: 'b3' + T })).body;
out.afterPause = await plan(team.teamId);
out.unsub = (await hook({ type: 'CANCELLATION', cancel_reason: 'UNSUBSCRIBE', product_id: 'pro_monthly', id: 'b4' + T })).body;
out.afterUnsub = await plan(team.teamId);
const top = process.env.PLUS === '1' ? 'plus_monthly' : 'pro_monthly';
if (process.env.PLUS === '1') {
  out.up = (await hook({ type: 'PRODUCT_CHANGE', product_id: 'pro_monthly', new_product_id: 'plus_monthly', expiration_at_ms: Date.now() + 60 * day, id: 'b5' + T })).body;
  out.afterUp = await plan(team.teamId);
  out.down = (await hook({ type: 'PRODUCT_CHANGE', product_id: 'plus_monthly', new_product_id: 'pro_monthly', id: 'b6' + T })).body;
  out.afterDown = await plan(team.teamId);
}
for (let i = 0; i < 3; i++) await hook({ type: 'NON_RENEWING_PURCHASE', product_id: 'credits_100', id: 'cr' + T });
out.credits = (await one('select omr from credit_balance where team_id=$1', [team.teamId]) || { omr: 0 }).omr;
out.creditRefund = (await hook({ type: 'CANCELLATION', cancel_reason: 'CUSTOMER_SUPPORT', product_id: 'credits_100', id: 'b7' + T })).body;
out.afterCreditRefund = await plan(team.teamId);
out.supportCancel = (await hook({ type: 'CANCELLATION', cancel_reason: 'CUSTOMER_SUPPORT', product_id: top, expiration_at_ms: Date.now() + 20 * day, id: 'b7s' + T })).body;
out.afterSupportCancel = await plan(team.teamId);
out.refund = (await hook({ type: 'CANCELLATION', cancel_reason: 'CUSTOMER_SUPPORT', product_id: top, expiration_at_ms: Date.now(), id: 'b8' + T })).body;
out.afterRefund = await plan(team.teamId);
await q("update teams set plan='pro', plan_until=null, plan_source='manual' where id=$1", [team.teamId]);
out.expireManual = (await hook({ type: 'EXPIRATION', product_id: 'pro_monthly', id: 'b9' + T })).body;
out.afterExpireManual = await plan(team.teamId);
// 새 인도자가 사도 손으로 준 기한 없는 플랜은 덮지 않는다 (덮으면 결제 기간이 끝날 때 무료로 떨어진다). 그 뒤 만료도 그 플랜을 안 건드린다
const hookAs = (who, ev) => call('POST', '/iap/webhook', { event: { app_user_id: who.id, ...ev } }, { authorization: 'audit-secret' }).then((r) => r.body);
const attr = (teamId) => ({ subscriber_attributes: { teamId: { value: teamId, updated_at_ms: Date.now() } } });
const row = (id) => one('select plan, plan_source, plan_until, iap_user_id, billing_user_id, extract(epoch from plan_until - now())/86400 as d from teams where id=$1', [id]);
out.bBuysOverManual = await hookAs(b, { type: 'INITIAL_PURCHASE', product_id: 'pro_monthly', expiration_at_ms: Date.now() + 30 * day, id: 'b10' + T });
out.bExpire = await hookAs(b, { type: 'EXPIRATION', product_id: 'pro_monthly', id: 'b11' + T });
out.afterB = await row(team.teamId);

// S2 결제 담당을 넘긴 뒤에도 산 사람의 갱신·만료는 그 팀으로 간다. 넘겨받은 결제 담당이 따로 사도 살아 있는 구독을 빼앗지 않는다
const c2 = await user('wc'), d2 = await user('wd');
const team2 = (await call('POST', '/teams', { name: '결제팀2', myName: '다' }, as(c2))).body;
await call('POST', `/invite/${team2.invite}/join`, { name: '라', sessions: ['드럼'] }, as(d2));
out.s2buy = await hookAs(c2, { type: 'INITIAL_PURCHASE', product_id: 'pro_monthly', expiration_at_ms: Date.now() + 30 * day, id: 's2a' + T });
out.billingMove = (await call('POST', `/teams/${team2.teamId}/billing`, { userId: d2.id }, as(c2))).status;
out.s2renew = await hookAs(c2, { type: 'RENEWAL', product_id: 'pro_monthly', expiration_at_ms: Date.now() + 60 * day, id: 's2b' + T });
out.s2 = await row(team2.teamId);
out.s2steal = await hookAs(d2, { type: 'INITIAL_PURCHASE', product_id: 'pro_monthly', expiration_at_ms: Date.now() + 30 * day, id: 's2c' + T, ...attr(team2.teamId) });
out.s2stealRenew = await hookAs(d2, { type: 'RENEWAL', product_id: 'pro_monthly', expiration_at_ms: Date.now() + 30 * day, id: 's2d' + T });
out.s2kept = await row(team2.teamId);
out.s2exp = await hookAs(c2, { type: 'EXPIRATION', product_id: 'pro_monthly', id: 's2e' + T });
out.s2after = await row(team2.teamId);

// S3 인도자를 넘기고 새 팀을 만든 뒤 산 것은 새 팀으로. S7 넘겨받은 새 인도자가 산 것은 옛 팀으로 (결제 담당도 그 사람이 된다).
// 그 뒤 옛 인도자의 만료는 제 구독이 적힌 새 팀만 끊는다
const e3 = await user('we'), f3 = await user('wf');
const x3 = (await call('POST', '/teams', { name: '옛팀', myName: '마' }, as(e3))).body;
await call('POST', `/invite/${x3.invite}/join`, { name: '바', sessions: ['드럼'] }, as(f3));
await call('POST', `/teams/${x3.teamId}/transfer`, { userId: f3.id }, as(e3));
const y3 = (await call('POST', '/teams', { name: '새팀', myName: '마' }, as(e3))).body;
out.s3buy = await hookAs(e3, { type: 'INITIAL_PURCHASE', product_id: 'pro_monthly', expiration_at_ms: Date.now() + 30 * day, id: 's3a' + T });
out.s3x = await row(x3.teamId); out.s3y = await row(y3.teamId);
out.s7buy = await hookAs(f3, { type: 'INITIAL_PURCHASE', product_id: 'pro_monthly', expiration_at_ms: Date.now() + 30 * day, id: 's7a' + T });
out.s7x = await row(x3.teamId);
out.s3exp = await hookAs(e3, { type: 'EXPIRATION', product_id: 'pro_monthly', id: 's3e' + T });
out.s3xAfter = await row(x3.teamId); out.s3yAfter = await row(y3.teamId);
out.ids = { e3: e3.id, f3: f3.id, c2: c2.id };

// 여러 팀의 인도자는 앱이 알려 준 팀(사용자 속성 teamId)으로 산다. 제 팀이 아닌 id 를 보내면 어디에도 넣지 않는다
const g = await user('wg');
const g1 = (await call('POST', '/teams', { name: '첫팀', myName: '사' }, as(g))).body;
// 무료로는 팀을 하나만 만들 수 있어(ENFORCE_PLAN) 둘째 팀은 DB 에 바로 만든다
const g2 = { teamId: (await one(`insert into teams(name, invite_token, created_by) values('둘째팀', $2, $1) returning id`, [g.id, 'g2' + T])).id };
await q(`insert into members(user_id, team_id, name, session, sessions, role) values($1, $2, '사', '인도자', $3, 'leader')`, [g.id, g2.teamId, ['인도자']]);
out.gBuy = await hookAs(g, { type: 'INITIAL_PURCHASE', product_id: 'pro_monthly', expiration_at_ms: Date.now() + 30 * day, id: 'g1' + T, ...attr(g2.teamId) });
out.g1 = await row(g1.teamId); out.g2 = await row(g2.teamId);
const h = await user('wh');
const h1 = (await call('POST', '/teams', { name: '셋째팀', myName: '아' }, as(h))).body;
out.hBuy = await hookAs(h, { type: 'INITIAL_PURCHASE', product_id: 'pro_monthly', expiration_at_ms: Date.now() + 30 * day, id: 'h1' + T, ...attr(g1.teamId) });
out.g1after = await row(g1.teamId); out.h1 = await row(h1.teamId);

// 끊겼다 다시 산 것(RevenueCat 은 RENEWAL 로 보낸다)은 끊긴 옛 기록의 팀이 아니라 지금 고른 팀으로.
// A 가 X 에서 사고 인도자·결제 담당을 B 에게 넘긴 뒤 만료 → X 를 떠나 새 팀 Y 를 만들고 다시 산다
const leave = (tm, who) => call('DELETE', `/teams/${tm.teamId}/members/${who.id}`, {}, as(who)).then((r) => r.status);
for (const [k, ev] of [['rAttr', (y) => ({ type: 'RENEWAL', ...attr(y.teamId) })], ['rNo', () => ({ type: 'RENEWAL' })], ['iNo', () => ({ type: 'INITIAL_PURCHASE' })]]) {
  const pa = await user('p' + k + 'a'), pb = await user('p' + k + 'b');
  const px = (await call('POST', '/teams', { name: '옛팀', myName: '가' }, as(pa))).body;
  await call('POST', `/invite/${px.invite}/join`, { name: '나', sessions: ['드럼'] }, as(pb));
  await hookAs(pa, { type: 'INITIAL_PURCHASE', product_id: 'pro_monthly', expiration_at_ms: Date.now() + 30 * day, id: k + '1' + T });
  const steps = [(await call('POST', `/teams/${px.teamId}/transfer`, { userId: pb.id }, as(pa))).status,
                 (await call('POST', `/teams/${px.teamId}/billing`, { userId: pb.id }, as(pa))).status];
  steps.push((await hookAs(pa, { type: 'EXPIRATION', product_id: 'pro_monthly', id: k + '2' + T })).kind);
  steps.push(await leave(px, pa));
  const py = (await call('POST', '/teams', { name: '새팀', myName: '가' }, as(pa))).body;
  out[k] = { steps, hook: await hookAs(pa, { product_id: 'pro_monthly', expiration_at_ms: Date.now() + 30 * day, id: k + '3' + T, ...ev(py) }),
             x: await row(px.teamId), y: await row(py.teamId), a: pa.id };
}
// 구독이 살아 있으면(결제 유예로 기한이 조금 지났어도 만료가 오기 전이면) 갱신은 속성이 다른 팀을 가리켜도 적힌 팀으로
{
  const la = await user('la');
  const lx = (await call('POST', '/teams', { name: '구독팀', myName: '가' }, as(la))).body;
  const ly = { teamId: (await one(`insert into teams(name, invite_token, created_by) values('다른팀', $2, $1) returning id`, [la.id, 'ly' + T])).id };
  await q(`insert into members(user_id, team_id, name, session, sessions, role) values($1, $2, '가', '인도자', $3, 'leader')`, [la.id, ly.teamId, ['인도자']]);
  await hookAs(la, { type: 'INITIAL_PURCHASE', product_id: 'pro_monthly', expiration_at_ms: Date.now() + 30 * day, id: 'la1' + T, ...attr(lx.teamId) });
  await q(`update teams set plan_until = now() - interval '2 days' where id=$1`, [lx.teamId]);
  out.grace = { hook: await hookAs(la, { type: 'RENEWAL', product_id: 'pro_monthly', expiration_at_ms: Date.now() + 30 * day, id: 'la2' + T, ...attr(ly.teamId) }),
                x: await row(lx.teamId), y: await row(ly.teamId) };
}
// 크레딧: 구독이 살아 있는 X 의 인도자를 넘기고(결제 담당은 그대로) 새 팀 Y 를 만든 사람이 속성 없이 산다 → Y
{
  const ca = await user('ca'), cb = await user('cb');
  const cx = (await call('POST', '/teams', { name: '구독팀', myName: '가' }, as(ca))).body;
  await call('POST', `/invite/${cx.invite}/join`, { name: '나', sessions: ['드럼'] }, as(cb));
  await hookAs(ca, { type: 'INITIAL_PURCHASE', product_id: 'pro_monthly', expiration_at_ms: Date.now() + 30 * day, id: 'ca1' + T });
  await call('POST', `/teams/${cx.teamId}/transfer`, { userId: cb.id }, as(ca));
  const cy = (await call('POST', '/teams', { name: '새팀', myName: '가' }, as(ca))).body;
  out.cred = { hook: await hookAs(ca, { type: 'NON_RENEWING_PURCHASE', product_id: 'credits_30', id: 'ca2' + T }),
               x: (await one('select omr from credit_balance where team_id=$1', [cx.teamId]) || { omr: 0 }).omr,
               y: (await one('select omr from credit_balance where team_id=$1', [cy.teamId]) || { omr: 0 }).omr,
               xPlan: await row(cx.teamId) };
}
// 인도자·결제 담당을 넘기고 멤버로 남은 사람의 구독이 결제 문제로 만료됐다가 되살아나면(RENEWAL) 그 팀으로.
// 속성이 제가 인도자·결제 담당이 아닌 다른 팀을 가리키면 어디에도 넣지 않는다
{
  const sa = await user('sa'), sb = await user('sb'), sz = await user('sz');
  const sx = (await call('POST', '/teams', { name: '구독팀', myName: '가' }, as(sa))).body;
  await call('POST', `/invite/${sx.invite}/join`, { name: '나', sessions: ['드럼'] }, as(sb));
  const szt = (await call('POST', '/teams', { name: '남의팀', myName: '다' }, as(sz))).body;
  await call('POST', `/invite/${szt.invite}/join`, { name: '라', sessions: ['드럼'] }, as(sa));
  await hookAs(sa, { type: 'INITIAL_PURCHASE', product_id: 'pro_monthly', expiration_at_ms: Date.now() + 30 * day, id: 'sa1' + T, ...attr(sx.teamId) });
  await call('POST', `/teams/${sx.teamId}/transfer`, { userId: sb.id }, as(sa));
  await call('POST', `/teams/${sx.teamId}/billing`, { userId: sb.id }, as(sa));
  await hookAs(sa, { type: 'EXPIRATION', product_id: 'pro_monthly', id: 'sa2' + T });
  const other = await hookAs(sa, { type: 'RENEWAL', product_id: 'pro_monthly', expiration_at_ms: Date.now() + 30 * day, id: 'sa3' + T, ...attr(szt.teamId) });
  const afterOther = { x: await row(sx.teamId), z: await row(szt.teamId) };
  const back = await hookAs(sa, { type: 'RENEWAL', product_id: 'pro_monthly', expiration_at_ms: Date.now() + 30 * day, id: 'sa4' + T, ...attr(sx.teamId) });
  out.stay = { other, afterOther, back, x: await row(sx.teamId), a: sa.id, b: sb.id };
}

// F106 · F51 코드 인식: Gemini 가 과부하면 502, 이번 달 곡 한도를 돌려주고, 하루 호출 수도 세지 않는다
const c = await user('oc');
const ct = (await call('POST', '/teams', { name: '인식팀', myName: '다' }, as(c))).body;
const r = await call('POST', '/ocr', { teamId: ct.teamId, songKey: 'song1', images: [{ b64: 'JVBERi0' + 'A'.repeat(300), mime: 'application/pdf', w: 10, h: 10 }] }, as(c));
out.ocr = { status: r.status, error: r.body && r.body.error };
out.ocrMime = sent.map((x) => x.contents[0].parts[1].inline_data.mime_type);
out.ocrSongs = (await q("select 1 from ai_songs where team_id=$1 and kind='ocr'", [ct.teamId])).length;
out.ocrCalls = (await q("select calls from ai_usage where team_id=$1 and kind='ocr'", [ct.teamId])).map((x) => x.calls);
out.ocrRefunds = (await q("select 1 from credit_refunds where team_id=$1", [ct.teamId])).length;
console.log(JSON.stringify(out));
process.exit(0);
"""
o = node(INPROC, {'DB': DB, 'TAG': tag, 'PLUS': '1' if PLUS else ''})
if o['buy'].get('kind') != 'grant': fail('F52 첫 결제가 반영 안 됨: %s' % o['buy'])
if o['transfer'] != 200: fail('인도자 넘기기 실패')
if o['renew'].get('kind') != 'grant' or not (59 < float(o['afterRenew']['d']) < 61): fail('F52 인도자를 넘긴 뒤 갱신이 팀을 못 찾음: %s %s' % (o['renew'], o['afterRenew']))
if o['afterPause']['plan'] != 'pro': fail('F107 멈춤 예약(SUBSCRIPTION_PAUSED)에 바로 끊김: %s' % o['afterPause'])
if o['afterUnsub']['plan'] != 'pro': fail('F107 그냥 해지에 바로 끊김: %s' % o['afterUnsub'])
if PLUS and o['afterUp']['plan'] != 'plus': fail('F107 Pro→Plus 변경에 옛 상품이 들어감: %s %s' % (o['up'], o['afterUp']))
if PLUS and o['afterDown']['plan'] != 'plus': fail('F107 내리는 변경이 바로 반영됨: %s' % o['afterDown'])
if o['credits'] != 100: fail('F107 같은 크레딧 사건을 세 번 받았더니 %s' % o['credits'])
if o['afterCreditRefund']['plan'] != ('plus' if PLUS else 'pro'): fail('F107 크레딧 팩 환불로 구독이 끊김: %s' % o['afterCreditRefund'])
if o['afterSupportCancel']['plan'] == 'free': fail('F107 환불 없는 고객센터 해지(만료가 남음)에 바로 끊김: %s' % o['afterSupportCancel'])
if o['afterRefund']['plan'] != 'free': fail('F107 환불(CUSTOMER_SUPPORT)인데 유료가 남음: %s %s' % (o['refund'], o['afterRefund']))
if o['afterExpireManual']['plan'] != 'pro' or o['afterExpireManual']['plan_source'] != 'manual': fail('F107 손으로 준 플랜을 결제 만료가 지움: %s' % o['afterExpireManual'])
ab = o['afterB']
if 'skipped' not in o['bBuysOverManual'] or 'skipped' not in o['bExpire'] or ab['plan'] != 'pro' or ab['plan_source'] != 'manual' or ab['plan_until'] is not None:
  fail('F52 새 인도자의 결제·만료가 손으로 준 기한 없는 플랜을 덮거나 끊음: %s %s %s' % (o['bBuysOverManual'], o['bExpire'], ab))
ids = o['ids']
if o['s2buy'].get('kind') != 'grant' or o['billingMove'] != 200: fail('S2 준비 실패: %s %s' % (o['s2buy'], o['billingMove']))
if o['s2renew'].get('kind') != 'grant' or not (59 < float(o['s2']['d']) < 61): fail('F52 결제 담당을 넘긴 뒤 산 사람의 갱신이 팀을 못 찾음: %s %s' % (o['s2renew'], o['s2']))
if 'skipped' not in o['s2steal'] or 'skipped' not in o['s2stealRenew']: fail('F52 남의 구독이 살아 있는 팀에 다른 사람의 결제가 들어감: %s %s' % (o['s2steal'], o['s2stealRenew']))
if o['s2kept']['iap_user_id'] != ids['c2'] or not (59 < float(o['s2kept']['d']) < 61): fail('F52 산 사람의 구독이 다른 사람 결제로 바뀜: %s' % o['s2kept'])
if o['s2exp'].get('kind') != 'revoke' or o['s2after']['plan'] != 'free': fail('F52 결제 담당을 넘긴 뒤 산 사람의 만료가 팀을 못 찾음: %s %s' % (o['s2exp'], o['s2after']))
if o['s3y']['plan'] != 'pro' or o['s3x']['plan'] != 'free' or o['s3y']['iap_user_id'] != ids['e3']: fail('F52 인도자를 넘기고 새 팀에서 산 것이 옛 팀에 들어감: 옛 %s 새 %s' % (o['s3x'], o['s3y']))
s7 = o['s7x']
if o['s7buy'].get('kind') != 'grant' or s7['plan'] != 'pro' or s7['iap_user_id'] != ids['f3'] or s7['billing_user_id'] != ids['f3']: fail('F52 넘겨받은 새 인도자가 산 것이 안 들어감: %s %s' % (o['s7buy'], s7))
if o['s3yAfter']['plan'] != 'free' or o['s3xAfter']['plan'] != 'pro': fail('F52 옛 인도자의 만료가 새 인도자가 산 팀을 끊음: 옛 %s 새 %s' % (o['s3xAfter'], o['s3yAfter']))
if o['gBuy'].get('kind') != 'grant' or o['g2']['plan'] != 'pro' or o['g1']['plan'] != 'free': fail('F52 앱이 알려 준 팀(teamId)이 아닌 곳에 들어감: %s %s %s' % (o['gBuy'], o['g1'], o['g2']))
if 'skipped' not in o['hBuy'] or o['g1after']['plan'] != 'free' or o['h1']['plan'] != 'free': fail('F52 제 팀이 아닌 teamId 로 산 것이 어딘가에 들어감: %s %s %s' % (o['hBuy'], o['g1after'], o['h1']))
for k in ('rAttr', 'rNo', 'iNo'):
  r = o[k]
  if r['steps'] != [200, 200, 'revoke', 200]: fail('F52 다시 산 경우 준비 실패(%s): %s' % (k, r['steps']))
  if r['hook'].get('kind') != 'grant' or r['y']['plan'] != 'pro' or r['y']['iap_user_id'] != r['a'] or r['x']['plan'] != 'free' or r['x']['iap_user_id'] is not None:
    fail('F52 구독이 끊긴 뒤 새 팀에서 다시 산 것(%s)이 떠난 옛 팀에 들어감: %s 옛 %s 새 %s' % (k, r['hook'], r['x'], r['y']))
g = o['grace']
if g['hook'].get('kind') != 'grant' or g['x']['plan'] != 'pro' or not (29 < float(g['x']['d']) < 31) or g['y']['plan'] != 'free':
  fail('F52 구독이 살아 있는(결제 유예) 팀의 갱신이 속성의 다른 팀으로 감: %s 구독팀 %s 다른팀 %s' % (g['hook'], g['x'], g['y']))
c = o['cred']
if c['hook'].get('kind') != 'credits' or c['y'] != 30 or c['x'] != 0 or c['xPlan']['plan'] != 'pro':
  fail('F52 속성 없는 크레딧이 지금 인도자인 팀이 아니라 구독이 적힌 옛 팀으로: %s 옛 %s 새 %s' % (c['hook'], c['x'], c['y']))
st = o['stay']
if 'skipped' not in st['other'] or st['afterOther']['z']['plan'] != 'free' or st['afterOther']['x']['plan'] != 'free':
  fail('F52 제가 인도자·결제 담당이 아닌 팀을 가리킨 갱신이 어딘가에 들어감: %s %s' % (st['other'], st['afterOther']))
if st['back'].get('kind') != 'grant' or st['x']['plan'] != 'pro' or st['x']['iap_user_id'] != st['a'] or st['x']['billing_user_id'] != st['b']:
  fail('F52 결제 담당을 넘기고 남은 사람의 되살아난 구독이 그 팀을 못 찾음: %s %s' % (st['back'], st['x']))
print('F52 ok — 끊겼다 다시 산 것은 지금 고른 팀으로(속성·산 사람의 팀) · 살아 있는 구독의 갱신은 적힌 팀 · 크레딧은 지금 인도자인 팀 · 멤버로 남은 사람의 되살아난 구독')
print('F52·F107 ok — 구독은 처음 반영한 팀으로 (인도자·결제 담당을 넘겨도) · 새 팀·새 인도자 · 앱이 고른 팀 · 남의 구독 안 빼앗음 · 멈춤·해지·환불 · 크레딧 중복 없음 · 수동 플랜 보호')
if o['ocr'] != {'status': 502, 'error': 'ocr_failed'}: fail('F106 Gemini 과부하인데 %s' % o['ocr'])
if o['ocrSongs'] != 0: fail('F106 실패했는데 이번 달 곡 한도가 빠짐')
if o['ocrRefunds'] != 0: fail('F106 엔진 실패를 월 3회 환불로 셈')
if any(o['ocrCalls']): fail('F106 실패한 호출을 하루 한도에 셈: %s' % o['ocrCalls'])
if not o['ocrMime'] or any(m != 'image/jpeg' for m in o['ocrMime']): fail('F51 그림이 아닌 형식이 Gemini 로 넘어감: %s' % o['ocrMime'])
print('F106·F51 ok — 엔진 실패는 502 · 한도 되돌림 · 형식은 그림만')

# ---------- G21 채보 가사 (fetch 막고 lib 만) ----------
G21 = r"""
process.env.GEMINI_API_KEY = 'fake';
const { transcribeScore } = await import(process.env.ROOT + '/lib/gemini.js');
let call = 0, fixN;
globalThis.fetch = async () => { call++;
  const payload = call === 1 ? { songs: [{ title: 't', key: 'G', time: '4/4', verses: 1, confidence: 0.9, measures: [
      { n: [{ p: 'D4', d: 4, l: ['주'] }, { p: 'G4', d: 4, l: ['님'] }, { p: 'B4', d: 2, l: ['께'] }] },
      { n: [{ p: 'D4', d: 4, l: ['주'] }, { p: 'G4', d: 4, l: ['님'] }, { p: 'B4', d: 4, l: ['께'] }] }] }] }
    : { fixes: [{ measure: 2, n: fixN }] };
  return { ok: true, status: 200, json: async () => ({ candidates: [{ content: { parts: [{ text: JSON.stringify(payload) }] } }], usageMetadata: {} }) }; };
const out = [];
for (const f of [
  [{ p: null, d: 4 }, { p: 'D4', d: 4 }, { p: 'G4', d: 4 }, { p: 'B4', d: 4 }],
  [{ p: 'D4', d: 4 }, { p: 'E4', d: 4 }, { p: 'G4', d: 4 }, { p: 'B4', d: 4 }],
  [{ p: 'D4', d: 4 }, { p: 'E4', d: 4 }, { p: 'A4', d: 4 }, { p: 'C5', d: 4 }]]) {
  call = 0; fixN = f;
  const r = await transcribeScore({ b64: 'x', mime: 'image/jpeg' });
  out.push(r.songs[0].measures[1].n.map((n) => (n.p || '-') + ':' + ((n.l || [])[0] || '')).join(' '));
}
console.log(JSON.stringify({ out }));
"""
g = node(G21)['out']
if g[0] != '-: D4:주 G4:님 B4:께': fail('G21 앞 쉼표를 넣어 고친 마디의 가사가 밀림: %s' % g[0])
if g[1] != 'D4:주 E4: G4:님 B4:께': fail('G21 음표를 하나 더한 마디의 가사가 밀림: %s' % g[1])
if g[2] != 'D4:주 G4:님 B4:께': fail('G21 가사를 제자리에 못 옮기는데 고친 것을 씀: %s' % g[2])
print('G21 ok — 쉼표·음표가 늘어도 가사가 제자리 · 못 옮기면 원래 마디')

# ---------- 화면: F50 목회자 메모 · F106 있던 코드 지키기 ----------
def ui():
  with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    c1 = b.new_context(viewport={'width': 1180, 'height': 820})
    c1.add_cookies([{'name': 'conti_s', 'value': L.cookie.split('=', 1)[1], 'url': URL}])
    pg = c1.new_page(); pg.on('pageerror', lambda e: errs.append('L:' + str(e))); pg.on('dialog', lambda d: d.accept())
    pg.goto(URL); pg.wait_for_selector('.shell[data-page]', timeout=15000)
    pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]')
    pg.fill('[data-f="svc.name"]', '감사 예배'); pg.click('[data-act="add-item"]'); pg.wait_for_selector('[data-f="item.title"]')
    pg.fill('[data-f="item.title"]', '곡하나'); pg.fill('[data-f="item.key"]', 'A'); pg.fill('[data-f="item.form"]', '1414 – AAB – Int(2)')
    pg.set_input_files('#pieceFile', [SHEET]); pg.wait_for_timeout(3000)
    pg.click('#sheet .slice', position={'x': 200, 'y': 160}); pg.wait_for_selector('#modal [data-l]', timeout=5000); pg.click('#modal [data-l]'); pg.wait_for_timeout(500)
    svc = pg.evaluate('CONTI.S.services[0].id')
    # F106: 코드를 한 번 인식해 두고, 엔진이 이 장을 못 읽었다(err)고 오면 있던 코드를 지킨다
    def run_ocr():
      pg.locator('.chordbar [data-act="ocr"]').first.click(); pg.wait_for_timeout(700)
      if pg.locator('#ocrGo').count(): pg.click('#ocrGo'); pg.wait_for_timeout(300)
      pg.wait_for_function("(()=>{const p=(CONTI.S.services[0].items[0].pieces||[])[0];return p&&p.ocr&&p.ocr!=='pending'})()", timeout=60000)
    ocr = c1.request.get(URL + 'api/ocr').json()
    if ocr.get('available'):
      run_ocr()
      n0 = pg.evaluate('(CONTI.S.services[0].items[0].pieces[0].chords||[]).length')
      if n0 < 5: fail('가짜 코드 인식 결과가 너무 적음: %d' % n0)
      pg.route('**/api/ocr', lambda r: r.fulfill(status=200, content_type='application/json',
               body=json.dumps({'results': [{'tokens': [], 'err': 'The model is overloaded'}], 'engine': 'gemini', 'quota': {'used': 1, 'cap': 10}})) if r.request.method == 'POST' else r.continue_())
      run_ocr()
      st = pg.evaluate('(()=>{const p=CONTI.S.services[0].items[0].pieces[0];return {n:(p.chords||[]).length,ocr:p.ocr}})()')
      if st['n'] != n0 or st['ocr'] != 'error': fail('F106 엔진이 못 읽었는데 있던 코드가 지워짐: %d → %s' % (n0, st))
      pg.unroute('**/api/ocr')
      print('F106 화면 ok — 엔진 오류면 있던 코드 %d개 그대로, 실패로 표시' % n0)
    pg.click('[data-act="publish"]'); pg.wait_for_selector('#pubOnly'); pg.click('#pubOnly'); pg.wait_for_timeout(5000)

    # F50: 목회자 메모가 꺼져 있으면 쓰는 창이 열리지 않는다
    c2 = b.new_context(viewport={'width': 430, 'height': 900})
    c2.add_cookies([{'name': 'conti_s', 'value': P.cookie.split('=', 1)[1], 'url': URL}])
    pm = c2.new_page(); pm.on('pageerror', lambda e: errs.append('P:' + str(e))); pm.on('dialog', lambda d: d.accept())
    pm.goto(URL + '#/play/' + svc + '/0'); pm.wait_for_selector('#sheet [data-marker]', timeout=20000); pm.wait_for_timeout(1500)
    pm.click('#sheet [data-marker]'); pm.wait_for_timeout(600)
    if pm.locator('#cText').count(): fail('F50 목회자 메모가 꺼져 있는데 쓰는 창이 열림')
    if '목회자 메모는 팀 설정에서 켜야 해요' not in pm.locator('body').inner_text(): fail('F50 목회자에게 까닭을 안 알려 줌')
    # 그래도(예: 설정이 바뀌기 전에 적어 둔) 메모가 올라가면, 서버가 거절한 것은 화면에서도 빼고 알린다
    L.req('POST', '/notes', {'teamId': TEAM, 'serviceId': svc, 'notes': [{'id': NID['lsvc0001'], 'itemId': pm.evaluate("CONTI.S.services.find(s=>s.id==='%s').items[0].id" % svc), 'layer': 'leader', 'text': '인도자 전체 메모'}]})
    pm.goto(URL + '#/home'); pm.wait_for_timeout(500); pm.goto(URL + '#/play/' + svc + '/0'); pm.wait_for_selector('#sheet [data-marker]', timeout=20000)
    pm.wait_for_function("(()=>{const s=CONTI.S.services.find(x=>x.id==='%s');return s&&s.items[0].notes.some(n=>n.id==='%s')})()" % (svc, NID['lsvc0001']), timeout=15000)
    got = pm.evaluate("""(async()=>{const s=CONTI.S.services.find(x=>x.id==='%s');const it=s.items[0];
      it.notes.push({id:'%s',marker:(it.markers||[])[0]&&it.markers[0].id,layer:'mine',text:'예전 메모',author:'목사',at:Date.now()});
      CONTI.S.noteShadow[s.id]=[];   // 그림자를 잃은 기기: 받아 둔 인도자 메모까지 다시 올린다
      const ok=await CONTI.SYNC.pushNotes(s);
      return {ok,ids:it.notes.map(n=>n.id),shadow:(CONTI.S.noteShadow[s.id]||[]).map(x=>x.id)}})()""" % (svc, NID['pold0001']))
    if not got['ok']: fail('F50 메모 올리기 실패')
    if NID['pold0001'] in got['ids'] or NID['pold0001'] in got['shadow']: fail('F50 서버가 거절한 메모가 올라간 것처럼 남음: %s' % got)
    if NID['lsvc0001'] not in got['ids']: fail('F50 서버에 있는 인도자 메모까지 화면에서 지움: %s' % got)
    pm.wait_for_timeout(300)
    if '저장하지 못했어요' not in pm.locator('body').inner_text(): fail('F50 거절을 알리지 않음')
    # 설정을 켜면 쓸 수 있다
    L.req('PATCH', '/teams/%s/settings' % TEAM, {'pastorCanMemo': True})
    pm.reload(); pm.wait_for_selector('#sheet [data-marker]', timeout=20000)
    pm.wait_for_function("!!(CONTI.S.team.settings||{}).pastorCanMemo", timeout=15000); pm.wait_for_timeout(500)
    pm.click('#sheet [data-marker]'); pm.wait_for_selector('#cText', timeout=5000)
    # 다른 팀 파일에서 가져온 인도자 메모(원래 id 가 그 팀 메모와 겹침)는 서버가 새 id 로 넣는다 → 이 기기의 id 도 바꿔
    # 그림자와 서버가 맞는다. 전에는 저장된 줄 알다가 다음 받기 때 말없이 사라졌다
    YID = 'ynote001' + tag
    LX.req('POST', '/notes', {'teamId': TX, 'serviceId': 'svcY' + tag, 'notes': [{'id': YID, 'itemId': 'it1', 'layer': 'leader', 'text': '원래 팀 메모'}]})
    got = pg.evaluate("""(async()=>{const s=CONTI.S.services.find(x=>x.id==='%s');await CONTI.SYNC.pullNotes(s);const it=s.items[0];
      it.notes.push({id:'%s',marker:(it.markers||[])[0]&&it.markers[0].id,layer:'leader',text:'가져온 인도자 메모',author:'인도자',at:Date.now()});
      const ok=await CONTI.SYNC.pushNotes(s);const mine=()=>s.items[0].notes.filter(n=>n.text==='가져온 인도자 메모').map(n=>n.id);
      const pushed=mine(),shadow=(CONTI.S.noteShadow[s.id]||[]).map(x=>x.id);
      await new Promise(r=>setTimeout(r,50));   // 올린 직후와 같은 밀리초면 받기가 '방금 올린 것'으로 보고 남겨 둔다
      await CONTI.SYNC.pullNotes(s);return {ok,pushed,shadow,after:mine()}})()""" % (svc, YID))
    st, gl = L.req('GET', '/notes?team=%s&service=%s' % (TEAM, svc))
    srv = [n['id'] for n in gl.get('notes', []) if n['text'] == '가져온 인도자 메모']
    if not got['ok'] or len(srv) != 1 or srv[0] == YID: fail('F50 다른 팀과 id 가 겹친 가져온 메모가 서버에 새 id 로 안 들어감: %s %s' % (got, srv))
    if got['pushed'] != srv or srv[0] not in got['shadow'] or YID in got['shadow']: fail('F50 서버가 바꾼 id 를 이 기기가 안 따름: %s %s' % (got, srv))
    if got['after'] != srv: fail('F50 다음 받기 때 가져온 메모가 사라지거나 늘어남: %s %s' % (got, srv))
    print('F50 화면 ok — 다른 팀과 id 가 겹친 가져온 메모는 새 id 로 바뀌어 남음')
    print('F50 화면 ok — 꺼져 있으면 창을 안 열고 알림 · 거절된 메모는 빼고 알림 · 켜면 열림')
    if errs: fail('JS 오류: %s' % errs[:3])
    b.close()
ui()

# 목회자 녹음 메모도 설정을 켜면 된다
st, _ = P.req('POST', '/rehearsals/%s/notes' % RID, {'teamId': TEAM, 'note': {'id': 'past0002', 't': 3, 'text': '목회자', 'layer': 'mine'}})
if st != 200: fail('F47 목회자 메모를 켰는데 녹음 메모가 %s' % st)
print('OK — api-ai-billing 감사 회귀 검사 통과')
