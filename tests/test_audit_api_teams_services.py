# 전역감사 2026-09-24 — 팀·발행·말씀 API 묶음 (api-teams-services) 회귀 검사
#  G03  인도자를 넘긴 옛 인도자가 팀을 나가고, 새 인도자가 내보낼 수 있다 (결제 담당은 인도자에게 돌아온다)
#  F113 인도자 넘기기가 나가기·다른 넘기기와 겹쳐도 팀에 활성 인도자가 꼭 한 명 남는다
#  F116 나간 목회자는 두 명 자리를 차지하지 않고 말씀 수정 요청도 받지 않는다
#  F115 동시에 들어와도 목회자가 둘을 넘지 않고, 가입을 두 번 눌러도 500 이 나지 않는다
#  F42  나갔던 사람이 초대 링크를 열면 '이미 팀에 있어요'가 아니라 다시 들어오는 화면이 뜬다 · 인도자에게 알림
#  F43  같은 판을 동시에 두 번 발행하면 하나만 받고 하나는 409
#  G23  말씀을 소리 없이 자르지 않는다 (400 + 입력칸 maxlength)
#  F117 콘티를 지우면 초안에만 있던 파일과 그 콘티의 녹음도 지운다 · 다시 발행해 빠진 파일도 지운다
#  ENFORCE_PLAN=1 일 때만: F39 F112 (채보 곡 수·크레딧) · F40 (기한 지난 유료) · F41 (정원은 모든 길에서)
import os, sys, time, json, subprocess, http.cookiejar, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.environ.get('CONTI_DB', 'postgres://postgres:pg@localhost:54329/postgres')
tag = str(int(time.time() * 1000))[-8:]
_n = [0]
def fail(m): print('FAIL:', m); sys.exit(1)

def sql(text, params=()):
  js = ('import("pg").then(async({default:pg})=>{const c=new pg.Client({connectionString:process.env.DATABASE_URL});'
        'await c.connect();const r=await c.query(process.argv[1],JSON.parse(process.argv[2]));'
        'console.log(JSON.stringify(r.rows));await c.end()})')
  out = subprocess.run(['node', '-e', js, text, json.dumps(list(params))], cwd=ROOT,
                       env={**os.environ, 'DATABASE_URL': DB}, capture_output=True, text=True)
  if out.returncode: fail('sql 실패: ' + out.stderr[-300:])
  return json.loads(out.stdout.strip().splitlines()[-1])

class Who:
  def __init__(self, name):
    _n[0] += 1
    self.jar = http.cookiejar.CookieJar()
    self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
    self.uname = 'au%s%d' % (tag, _n[0]); self.name = name
    st, d = self.call('POST', '/auth/signup', {'username': self.uname, 'password': 'secret1', 'name': name})
    if st != 200: fail('가입 실패 %s %s' % (st, d))
    self.id = d['user']['id']
  def call(self, method, path, body=None, raw=None, ctype='application/json'):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(URL + 'api' + path, data=data, method=method,
                                 headers={'x-conti': '1', 'content-type': ctype})
    try:
      with self.op.open(req, timeout=60) as r: return r.status, json.loads(r.read() or b'null')
    except urllib.error.HTTPError as e:
      b = e.read()
      try: return e.code, json.loads(b or b'null')
      except Exception: return e.code, b.decode(errors='replace')
  def ok(self, method, path, body=None, what=''):
    st, d = self.call(method, path, body)
    if st != 200: fail('%s: %s %s → %s %s' % (what or path, method, path, st, d))
    return d

def team_of(leader, name='감사팀'):
  d = leader.ok('POST', '/teams', {'name': name, 'myName': leader.name}, '팀 만들기')
  return d['teamId'], d['invite']

def join(who, code, what='가입'):
  return who.ok('POST', '/invite/%s/join' % code, {'name': who.name}, what)

def invite(leader, team, role):
  return leader.ok('POST', '/teams/%s/invites' % team, {'role': role, 'days': 0}, '초대 링크')['invite']['code']

def leaders(team):
  return [r['user_id'] for r in sql("select user_id from members where team_id=$1 and role='leader' and active", [team])]

def par(*fns):
  with ThreadPoolExecutor(len(fns)) as ex: return [f.result() for f in [ex.submit(fn) for fn in fns]]

def g03():
  A, B = Who('가은'), Who('나은')
  team, code = team_of(A); join(B, code)
  A.ok('POST', '/teams/%s/transfer' % team, {'userId': B.id}, '인도자 넘기기')
  st, d = A.call('DELETE', '/teams/%s/members/%s' % (team, A.id))
  if st != 200: fail('G03 옛 인도자가 팀을 못 나감: %s %s' % (st, d))
  me = B.ok('GET', '/me')['team']
  if me['billingUserId'] != B.id: fail('G03 결제 담당이 남은 인도자에게 안 돌아옴: %s' % me['billingUserId'])
  # 새 인도자가 옛 인도자를 내보내기
  C, D = Who('다은'), Who('라은')
  team2, code2 = team_of(C); join(D, code2)
  C.ok('POST', '/teams/%s/transfer' % team2, {'userId': D.id})
  st, d = D.call('DELETE', '/teams/%s/members/%s' % (team2, C.id))
  if st != 200: fail('G03 새 인도자가 옛 인도자를 못 내보냄: %s %s' % (st, d))
  # 인도자가 옛 인도자를 비활성으로 둬도 결제 담당은 인도자에게 돌아온다 (비활성인 채로 묶이지 않게)
  E, F = Who('마은'), Who('바은')
  team3, code3 = team_of(E); join(F, code3)
  E.ok('POST', '/teams/%s/transfer' % team3, {'userId': F.id})
  F.ok('PATCH', '/teams/%s/members/%s' % (team3, E.id), {'active': False}, '옛 인도자 비활성')
  if F.ok('GET', '/me')['team']['billingUserId'] != F.id: fail('G03 비활성인 옛 인도자에게 결제 담당이 남음')
  # (옛 인도자의 계정 삭제는 FK 전체 문제라 api-auth F05 에서 다룬다)
  # 스토어 구독이 살아 있는 동안은 결제 담당이 그냥 나갈 수 없다 (돈이 그 사람에게서 나가고 있다)
  G, H = Who('사은'), Who('아은')
  team4, code4 = team_of(G); join(H, code4)
  G.ok('POST', '/teams/%s/transfer' % team4, {'userId': H.id})
  sql("update teams set plan='pro', plan_until=now()+interval '20 days', plan_source='iap' where id=$1", [team4])
  st, d = G.call('DELETE', '/teams/%s/members/%s' % (team4, G.id))
  if st != 400: fail('G03 구독 중인 결제 담당이 그냥 나감: %s %s' % (st, d))
  print('G03 ok — 옛 인도자 나가기·내보내기·비활성, 구독 중엔 막힘')

def f113():
  bad = []
  for i in range(6):
    A, B, C = Who('가'), Who('나'), Who('다')
    team, code = team_of(A); join(B, code); join(C, code)
    # 두 사람에게 동시에 넘기기
    r = par(lambda: A.call('POST', '/teams/%s/transfer' % team, {'userId': B.id}),
            lambda: A.call('POST', '/teams/%s/transfer' % team, {'userId': C.id}))
    ls = leaders(team)
    if len(ls) != 1: bad.append('동시 넘기기 뒤 활성 인도자 %d명' % len(ls))
    if any(s >= 500 for s, _ in r): bad.append('동시 넘기기 500: %s' % r)
    # 넘기는 사이에 받을 사람이 나가기
    X, Y = Who('라'), Who('마')
    team2, code2 = team_of(X); join(Y, code2)
    r = par(lambda: X.call('POST', '/teams/%s/transfer' % team2, {'userId': Y.id}),
            lambda: Y.call('DELETE', '/teams/%s/members/%s' % (team2, Y.id)))
    ls = leaders(team2)
    if len(ls) != 1: bad.append('넘기기·나가기가 겹친 뒤 활성 인도자 %d명 %s' % (len(ls), r))
  if bad: fail('F113 ' + ' / '.join(bad[:3]))
  print('F113 ok — 겹쳐도 인도자 한 명')

def f116_f115():
  L = Who('인도')
  team, code = team_of(L)
  pcode = invite(L, team, 'pastor')
  P1, P2, P3 = Who('목사1'), Who('목사2'), Who('목사3')
  join(P1, pcode); join(P2, pcode)
  P1.ok('DELETE', '/teams/%s/members/%s' % (team, P1.id), None, '목회자 나가기')
  st, d = P3.call('POST', '/invite/%s/join' % pcode, {'name': P3.name})
  if st != 200: fail('F116 나간 목회자가 자리를 차지함: %s %s' % (st, d))
  # 서비스 하나를 발행해 두고 말씀 수정 요청
  L.ok('PUT', '/services/w1', {'teamId': team, 'doc': {'id': 'w1', 'name': '주일', 'date': '2026-10-04', 'version': 1, 'items': []}})
  d = L.ok('POST', '/services/w1/word-request', {'teamId': team})
  if d.get('sent') != 2: fail('F116 말씀 요청이 활성 목회자 둘에게만 가야 함: %s' % d)
  n = sql("select count(*)::int n from notifications where team_id=$1 and user_id=$2 and type='word.request'", [team, P1.id])
  if n and n[0]['n']: fail('F116 나간 목회자에게 말씀 요청 알림이 감')
  # 다시 들어오려 해도 목회자 자리가 차 있으면 막힌다 (되살리기도 같은 검사)
  st, d = P1.call('POST', '/invite/%s/join' % code, {'name': P1.name})
  if st != 400: fail('F116 목회자 두 명이 찼는데 나갔던 목회자가 되살아남: %s %s' % (st, d))
  # 인도자가 비활성 목회자를 다시 켜는 것도 막힌다
  st, d = L.call('PATCH', '/teams/%s/members/%s' % (team, P1.id), {'active': True})
  if st != 400: fail('F116 목회자 두 명이 찼는데 비활성 목회자를 켬: %s %s' % (st, d))
  print('F116 ok — 나간 목회자는 자리·알림 없음, 되살리기도 두 명까지')

  # F115: 새 팀에서 목회자 링크로 넷이 동시에
  L2 = Who('인도2'); team2, code2 = team_of(L2); pcode2 = invite(L2, team2, 'pastor')
  ps = [Who('동시%d' % i) for i in range(4)]
  r = par(*[(lambda w: (lambda: w.call('POST', '/invite/%s/join' % pcode2, {'name': w.name})))(w) for w in ps])
  np = sql("select count(*)::int n from members where team_id=$1 and role='pastor' and active", [team2])[0]['n']
  if np != 2: fail('F115 동시에 넷이 들어와 목회자가 %d명 %s' % (np, [s for s, _ in r]))
  if sorted(s for s, _ in r) != [200, 200, 400, 400]: fail('F115 동시 가입 응답: %s' % r)
  if any(s >= 500 for s, _ in r): fail('F115 동시 가입 500: %s' % r)
  # 같은 사람이 가입을 두 번 동시에
  M = Who('두번')
  r = par(lambda: M.call('POST', '/invite/%s/join' % code2, {'name': M.name}),
          lambda: M.call('POST', '/invite/%s/join' % code2, {'name': M.name}))
  if [s for s, _ in r] != [200, 200]: fail('F115 가입 두 번 누르면 %s' % [(s, d) for s, d in r])
  n = sql('select count(*)::int n from members where team_id=$1 and user_id=$2', [team2, M.id])[0]['n']
  if n != 1: fail('F115 멤버 행이 %d개' % n)
  print('F115 ok — 동시 목회자 %d명, 두 번 가입 200·200' % np)

def f43():
  L = Who('발행')
  team, _ = team_of(L)
  both = 0
  for i in range(8):
    sid = 'race%d' % i
    L.ok('PUT', '/services/' + sid, {'teamId': team, 'doc': {'id': sid, 'name': 'v1', 'date': '2026-10-04', 'version': 1, 'items': []}})
    doc = lambda t: {'teamId': team, 'doc': {'id': sid, 'name': t, 'date': '2026-10-04', 'version': 2, 'items': [{'id': 'i', 'title': t}]}}
    r = par(lambda: L.call('PUT', '/services/' + sid, doc('A')), lambda: L.call('PUT', '/services/' + sid, doc('B')))
    codes = sorted(s for s, _ in r)
    if codes == [200, 200]: both += 1
    elif codes != [200, 409]: fail('F43 동시 발행 응답이 이상함: %s' % r)
    got = L.ok('GET', '/services/%s?team=%s' % (sid, team))
    winner = 'A' if r[0][0] == 200 else 'B'
    if codes == [200, 409] and got['doc']['name'] != winner: fail('F43 200 받은 쪽(%s)이 아니라 %s 가 남음' % (winner, got['doc']['name']))
  if both: fail('F43 같은 판 동시 발행이 %d번 둘 다 200' % both)
  print('F43 ok — 동시 발행은 하나만')

def g23(p):
  L = Who('말씀'); team, _ = team_of(L)
  L.ok('PUT', '/services/m1', {'teamId': team, 'doc': {'id': 'm1', 'name': '주일', 'date': '2026-10-04', 'version': 1, 'items': []}})
  memo = '가' * 1399
  st, d = L.call('PUT', '/services/m1/word', {'teamId': team, 'word': {'passage': '시편 1:1', 'memo': memo}})
  if st != 400 or '1000' not in str(d): fail('G23 긴 메모를 잘라 저장함: %s %s' % (st, str(d)[:120]))
  L.ok('PUT', '/services/m1/word', {'teamId': team, 'word': {'passage': '시편 1:1', 'memo': '가' * 1000}}, '1000자 메모')
  tok = L.ok('POST', '/services/m1/word-link', {'teamId': team})['token']
  anon = Who('링크')   # 링크 페이지는 로그인이 없어도 된다 (쿠키는 무시된다)
  st, d = anon.call('POST', '/word-link/' + tok, {'name': '목사', 'passage': '시편 1:1', 'memo': memo})
  if st != 400: fail('G23 링크로 보낸 긴 메모를 잘라 저장함: %s %s' % (st, d))
  used = sql('select used_at from word_links where token=$1', [tok])[0]['used_at']
  if used: fail('G23 거절했는데 링크가 닫힘')
  # 입력칸에도 한도가 보인다 (링크 페이지)
  b = p.chromium.launch(); pg = b.new_page()
  pg.goto(URL + '#/word-link/' + tok); pg.wait_for_selector('#wlMemo', timeout=10000)
  ml = pg.evaluate("['wlPassage','wlTitle','wlLine','wlMemo'].map(i=>document.getElementById(i).maxLength)")
  if ml != [60, 40, 80, 1000]: fail('G23 링크 페이지 입력칸 maxlength: %s' % ml)
  b.close()
  print('G23 ok — 넘치면 400, 링크는 열린 채, maxlength')

def f42(p):
  L, M = Who('인도'), Who('멤버')
  team, code = team_of(L); join(M, code)
  M.ok('DELETE', '/teams/%s/members/%s' % (team, M.id), None, '나가기')
  d = M.ok('GET', '/invite/' + code)
  if d.get('alreadyMember'): fail('F42 나간 사람에게 alreadyMember=true')
  sql("delete from notifications where team_id=$1", [team])
  # 화면: 링크를 열면 다시 들어오는 화면이 뜬다
  b = p.chromium.launch(); ctx = b.new_context(viewport={'width': 430, 'height': 900}); pg = ctx.new_page()
  pg.on('dialog', lambda d: d.accept())
  pg.goto(URL); pg.wait_for_selector('#lgUser', timeout=8000)
  pg.fill('#lgUser', M.uname); pg.fill('#lgPass', 'secret1'); pg.click('[data-act="lg-submit"]')
  pg.wait_for_timeout(1500)
  pg.goto(URL + '#/join/' + code); pg.wait_for_selector('#jnName', timeout=10000)
  card = pg.locator('.auth-card').first.inner_text()
  if '다시 들어가기' not in card or pg.locator('#gtSess').count(): fail('F42 다시 들어오는 화면이 아님: ' + card[:120])
  pg.click('[data-act="team-join"]'); pg.wait_for_selector('.shell[data-page]', timeout=10000)
  b.close()
  act = sql('select active from members where team_id=$1 and user_id=$2', [team, M.id])[0]['active']
  if not act: fail('F42 다시 들어오기가 안 됨')
  n = sql("select count(*)::int n from notifications where team_id=$1 and user_id=$2 and type='member.join'", [team, L.id])[0]['n']
  if not n: fail('F42 다시 들어온 것을 인도자가 모름')
  # 다시 들어오기를 두 번 눌러도 둘 다 성공하고 한 번만 되살린다 (알림·기록도 한 번)
  M.ok('DELETE', '/teams/%s/members/%s' % (team, M.id), None, '다시 나가기')
  rejoins = lambda: sql("select count(*)::int n from team_audit where team_id=$1 and action='member.rejoin'", [team])[0]['n']
  n0 = rejoins()
  r = par(lambda: M.call('POST', '/invite/%s/join' % code, {'name': M.name}),
          lambda: M.call('POST', '/invite/%s/join' % code, {'name': M.name}))
  if [s for s, _ in r] != [200, 200]: fail('F42 다시 들어오기 두 번: %s' % r)
  if rejoins() - n0 != 1: fail('F42 다시 들어오기 두 번에 되살리기 %d번' % (rejoins() - n0))
  print('F42 ok — 링크로 다시 들어오기 · 인도자 알림')

def f117():
  L = Who('파일'); team, _ = team_of(L)
  def up(bid):
    st, d = L.call('POST', '/blobs/%s?team=%s' % (bid, team), raw=b'\x89PNG' + os.urandom(64), ctype='image/png')
    if st != 200: fail('파일 올리기 실패 %s %s' % (st, d))
  def have(ids):
    return set(L.ok('GET', '/blobs?team=%s&ids=%s' % (team, ','.join(ids)))['blobs'].keys())
  item = lambda bid: {'id': 'it' + bid, 'title': '곡', 'pieces': [{'id': 'p' + bid, 'blob': bid}]}
  # 초안에만 있던 콘티를 지우면 그 파일도 지운다
  b1 = 'dr' + tag; up(b1)
  L.ok('PUT', '/services/d1/draft', {'teamId': team, 'doc': {'id': 'd1', 'name': '초안', 'date': '2026-10-04', 'items': [item(b1)]}})
  d = L.ok('DELETE', '/services/d1?team=' + team)
  if have([b1]): fail('F117 초안에만 있던 파일이 남음 %s' % d)
  # 콘티를 지우면 그 콘티의 녹음(잠근 것 포함)도 지운다
  L.ok('PUT', '/services/r1', {'teamId': team, 'doc': {'id': 'r1', 'name': '녹음', 'date': '2026-10-04', 'version': 1, 'items': []}})
  u = L.ok('POST', '/rehearsals/upload-url', {'teamId': team, 'size': 100, 'mime': 'audio/mp4'})
  req = urllib.request.Request(u['uploadUrl'], data=os.urandom(100), method='PUT', headers={'content-type': 'audio/mp4'})
  urllib.request.urlopen(req).read()
  rh = L.ok('POST', '/rehearsals', {'teamId': team, 'serviceId': 'r1', 'pathname': u['pathname'], 'blobId': u['blobId'], 'duration': 3})['rehearsal']
  L.ok('PATCH', '/rehearsals/%s' % rh['id'], {'teamId': team, 'keep': True})
  L.ok('DELETE', '/services/r1?team=' + team)
  if sql('select 1 from rehearsals where id=$1', [rh['id']]): fail('F117 지운 콘티의 녹음이 남음')
  if have([u['blobId']]): fail('F117 지운 콘티의 녹음 파일이 남음')
  # 다시 발행하면서 빠진 파일(자른 악보의 옛 판)은 지운다. 다른 콘티가 쓰는 파일은 남긴다
  b2, b3, b4 = 'o' + tag, 'n' + tag, 's' + tag
  for x in (b2, b3, b4): up(x)
  L.ok('PUT', '/services/c1', {'teamId': team, 'doc': {'id': 'c1', 'name': '자르기', 'date': '2026-10-04', 'version': 1, 'items': [item(b2), item(b4)]}})
  L.ok('PUT', '/services/c2', {'teamId': team, 'doc': {'id': 'c2', 'name': '같이 씀', 'date': '2026-10-11', 'version': 1, 'items': [item(b4)]}})
  L.ok('PUT', '/services/c1', {'teamId': team, 'doc': {'id': 'c1', 'name': '자르기', 'date': '2026-10-04', 'version': 2, 'items': [item(b3)]}})
  h = have([b2, b3, b4])
  if b2 in h: fail('F117 다시 발행해 빠진 파일이 남음')
  if b3 not in h or b4 not in h: fail('F117 쓰이는 파일을 지움: %s' % h)
  print('F117 ok — 초안 파일 · 녹음 · 빠진 판 정리, 쓰이는 파일은 남김')

# ---------------- ENFORCE_PLAN=1 일 때만 ----------------
def f39_f112():
  L = Who('채보'); team, _ = team_of(L)
  omr = lambda key=None, b64='iVBOR' + 'A' * 200: L.call('POST', '/omr', dict({'teamId': team, 'b64': b64, 'mime': 'image/png'}, **({'songKey': key} if key else {})))
  st, d = omr()
  if st != 200: fail('F39 첫 채보 %s %s' % (st, d))
  if d['quota']['cap'] != 1 or d['quota']['used'] != 1: fail('F39 곡 키 없이 불러도 한 곡으로 세야 함: %s' % d['quota'])
  st, d = omr()
  if st != 402: fail('F39 무료(1곡)인데 두 번째 채보가 됨: %s %s' % (st, d))
  # 크레딧: 같은 곡은 한 번만, 실패하면 돌려준다
  sql('insert into credit_balance(team_id, omr) values($1, 5) on conflict (team_id) do update set omr=5', [team])
  for _ in range(3):
    st, d = omr('song2')
    if st != 200: fail('F112 크레딧 채보 %s %s' % (st, d))
  bal = sql('select omr from credit_balance where team_id=$1', [team])[0]['omr']
  if bal != 4: fail('F112 같은 곡 세 번에 크레딧이 %d 남음 (4여야)' % bal)
  st, d = omr('song3', b64='TW9ja0ZhaWw' + 'A' * 200)   # 가짜 엔진이 실패하는 이미지
  if st != 502: fail('F112 실패 흉내가 안 됨: %s %s' % (st, d))
  bal = sql('select omr from credit_balance where team_id=$1', [team])[0]['omr']
  if bal != 4: fail('F112 실패했는데 크레딧이 안 돌아옴: %d' % bal)
  u = L.ok('GET', '/teams/%s/usage' % team)
  if u['omr']['used'] != 1 or u['creditOmr'] != 4: fail('F112 사용량 표시: %s' % u)
  print('F39·F112 ok — 곡 키 없이도 셈 · 크레딧은 곡당 한 번 · 실패는 환불')

def f40():
  L = Who('기한'); team, _ = team_of(L)
  sql("update teams set plan='pro', plan_until=now()-interval '1 day', plan_source='promo' where id=$1", [team])
  u = L.ok('GET', '/teams/%s/usage' % team)
  if u['plan'] != 'free' or u['omr']['cap'] != 1: fail('F40 기한 지난 Pro 가 아직 Pro 한도: %s' % u)
  st, d = L.call('PATCH', '/teams/' + team, {'sessions': ['s%d' % i for i in range(12)]})
  if st != 402: fail('F40 기한 지난 Pro 가 세션 12개를 만듦: %s %s' % (st, d))
  codes = [L.call('POST', '/teams/%s/invites' % team, {'role': 'member', 'days': 30})[0] for _ in range(4)]
  if 402 not in codes: fail('F40 기한 지난 Pro 가 초대 링크를 무료 한도 넘게 만듦: %s' % codes)
  print('F40 ok — 기한 지난 유료는 무료 한도')

def f41():
  L = Who('정원'); team, code = team_of(L)
  ms = [Who('m%d' % i) for i in range(9)]
  for m in ms: join(m, code)                      # 인도자 + 9 = 10 (무료 정원)
  L.ok('PATCH', '/teams/%s/members/%s' % (team, ms[0].id), {'active': False})
  X = Who('새사람'); join(X, code)               # 다시 10
  st, d = L.call('PATCH', '/teams/%s/members/%s' % (team, ms[0].id), {'active': True})
  if st != 402: fail('F41 정원이 찼는데 다시 활성: %s %s' % (st, d))
  st, d = ms[0].call('POST', '/invite/%s/join' % code, {'name': 'm0'})
  if st != 402: fail('F41 정원이 찼는데 링크로 되살아남: %s %s' % (st, d))
  # 목회자에서 멤버로 내리기
  pcode = invite(L, team, 'pastor'); P = Who('목사'); join(P, pcode)
  st, d = L.call('PATCH', '/teams/%s/members/%s' % (team, P.id), {'role': 'member'})
  if st != 402: fail('F41 정원이 찼는데 목회자를 멤버로 내림: %s %s' % (st, d))
  n = sql("select count(*)::int n from members where team_id=$1 and active and role<>'pastor'", [team])[0]['n']
  if n != 10: fail('F41 활성 멤버 %d명' % n)
  print('F41 ok — 다시 활성·되살리기·목회자 내리기도 정원 검사')

def run():
  health = json.loads(urllib.request.urlopen(URL + 'api/health').read())
  g03(); f113(); f116_f115(); f43(); f117()
  with sync_playwright() as p:
    g23(p); f42(p)
  if health.get('enforcePlan'):
    f39_f112(); f40(); f41()
  else:
    print('SKIP(한도) — ENFORCE_PLAN 이 꺼져 있어 F39·F112·F40·F41 은 건너뜀 (ENFORCE_PLAN=1 로 서버를 켜고 다시)')
  print('OK — api-teams-services 감사 회귀 검사 통과')

run()
