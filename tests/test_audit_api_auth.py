# 전역감사 2026-09-24 · 계정/권한 묶음 회귀 테스트 (api-auth)
#  F05  계정 삭제가 전 인도자·팀을 나간 사람에게 500 이던 것 + 실패해도 메모·혼자 팀이 먼저 지워지던 것
#  F36  지운 팀(30일 유예)·비활성 멤버만 남은 팀이 계정 삭제를 막던 것
#  F04  소셜 전용 계정은 비밀번호가 없어 계정을 못 지우던 것
#  F37  복구 코드를 로그인만으로 새로 받을 수 있던 것 (현재 비밀번호 확인)
#  F38  세션 이름을 바꿔도 그날 정원(service_dates.slots)·녹음 메모의 세션이 옛 이름으로 남던 것
#  F111 두 세션 이름을 맞바꾸면 메모가 한쪽으로 몰리던 것
#  G02  개인 설정(prefs)이 한없이 커지던 것 — 무대 조판은 따로 두고, 크기·개수 한도
#  F02  AI 하루 한도를 동시에 여러 번 부르면 넘던 것
#  G01  계정을 여러 개 만들어 AI 한도를 늘리던 것 — 전체 하루 한도 · 주소당 가입 제한
#  G09  로그아웃해도 토큰이 90일 동안 살아 있던 것 · 모든 기기에서 로그아웃
# 되돌려진 수정 바로잡기 (r2)
#  F37  소셜 전용 계정은 세션만으로 복구 코드·비밀번호를 만들고 구글을 떼 주인을 내쫓을 수 있던 것
#       → 연결된 구글·애플로 방금 받은 토큰으로 다시 확인 (연결·해제·계정 삭제도) · 옛 앱(비밀번호 없이 부름)은
#       세지 않고 업데이트 안내 · 동시에 틀린 비밀번호를 보내면 잠금을 건너뛰던 것
#  F38  세션 이름 바꾸기가 녹음 메모를 읽어 고쳐 다시 써서, 그사이 단 메모가 사라지던 것
#  G02  아직 옮기지 않은 옛 조판이 크면 PATCH /me/prefs 가 413 이던 것 (연산자 우선순위)
#  F02  악보 다시 묻기 · Vision 으로 다시 읽기를 부른 뒤에 세어, 동시에 보내면 한도를 넘겨 부르던 것
#  G01  주소당 가입 제한이 동시 가입·IPv6 주소 바꾸기로 뚫리던 것 · 새 계정 몇 개로 전체 AI 한도를 채워 모두 멈추던 것
# 준비: sh scripts/dev-local.sh (로컬 DB). DB 를 직접 보는 곳이 있어 psql(또는 docker exec conti-pg)이 필요하다
import os, sys, time, json, random, subprocess, threading, urllib.request, urllib.error, shutil
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/').rstrip('/') + '/'
DB = os.environ.get('CONTI_DB', 'postgres://postgres:pg@localhost:54329/postgres')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
tag = str(int(time.time()))[-6:]
FAILS = []
def fail(m):
    print('FAIL:', m); FAILS.append(m)
    raise AssertionError(m)

# ---------- DB (로컬만) ----------
def sql(s):
    if shutil.which('psql'): cmd = ['psql', DB, '-tAc', s]
    else: cmd = ['docker', 'exec', 'conti-pg', 'psql', '-U', 'postgres', '-tAc', s]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode: raise RuntimeError('psql: ' + r.stderr.strip()[:300])
    return r.stdout.strip()
def lit(v): return "'" + str(v).replace("'", "''") + "'"

# ---------- HTTP ----------
def call(method, path, body=None, token=None, cookie=None, headers=None, raw=None, ctype=None, base=None):
    h = {'x-conti': '1'}
    if token: h['authorization'] = 'Bearer ' + token
    if cookie: h['cookie'] = cookie
    data = None
    if raw is not None: data = raw; h['content-type'] = ctype or 'application/octet-stream'
    elif body is not None: data = json.dumps(body).encode(); h['content-type'] = 'application/json'
    h.update(headers or {})
    req = urllib.request.Request((base or URL) + 'api' + path, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            st, txt, hd = r.status, r.read().decode(), r.headers
    except urllib.error.HTTPError as e:
        st, txt, hd = e.code, e.read().decode(), e.headers
    try: j = json.loads(txt)
    except Exception: j = {'_raw': txt[:200]}
    return st, j, hd

N = [0]
def uname(p):
    N[0] += 1
    return (p + tag + str(N[0]))[:20]
APP = {'x-conti-app': '1'}
def signup(p, name='하은', password='secret1', headers=None, base=None):
    u = uname(p)
    st, j, _ = call('POST', '/auth/signup', {'username': u, 'password': password, 'name': name}, headers={**APP, **(headers or {})}, base=base)
    if st != 200: fail('가입 실패 %s %s' % (st, j))
    return {'u': u, 'pw': password, 't': j['token'], 'id': j['user']['id']}
def login(a, app=True):
    st, j, hd = call('POST', '/auth/login', {'username': a['u'], 'password': a['pw']}, headers=APP if app else None)
    if st != 200: fail('로그인 실패 %s %s' % (st, j))
    if app: return j['token']
    ck = [c for c in hd.get_all('Set-Cookie') or [] if c.startswith('conti_s=')]
    return ck[0].split(';')[0] if ck else None
def ok(st, j, what):
    if st != 200: fail('%s: %s %s' % (what, st, j))
    return j
def team(a, name='팀', session='인도자'):
    return ok(*call('POST', '/teams', {'name': name, 'myName': '인도', 'session': session}, token=a['t'])[:2], '팀 만들기')
def join(a, t, name='멤버', session='드럼'):
    return ok(*call('POST', '/invite/%s/join' % t['invite'], {'name': name, 'session': session}, token=a['t'])[:2], '팀 가입')
def me_status(**kw): return call('GET', '/me', **kw)[0]
KST = "(now() at time zone 'Asia/Seoul')::date"

ONLY = [x for x in os.environ.get('ONLY', '').split(',') if x]   # 개발 중에 일부만: ONLY=f05,prefs
def section(fn, name=None):
    name = name or fn.__name__
    if ONLY and not any(o in name for o in ONLY): return
    try: fn()
    except AssertionError: pass
    except Exception as e:
        print('FAIL:', name, repr(e)[:300]); FAILS.append(name)

# ---------- F05 ----------
def t_f05():
    A = signup('dla'); B = signup('dlb'); C = signup('dlc')
    T = team(A, '삭제팀')
    join(B, T, '비'); join(C, T, '씨')
    # A 가 곡·공유 코드를 만든 뒤 (songs.created_by · share_codes.created_by) 인도자를 B 에게 넘긴다 (billing_user_id 가 A 로 못박힘)
    s = ok(*call('POST', '/songs', {'teamId': T['teamId'], 'title': '주의 이름 높이며'}, token=A['t'])[:2], '곡')
    sid = (s.get('song') or s).get('id')
    st, j, _ = call('POST', '/share', {'teamId': T['teamId'], 'songIds': [sid]}, token=A['t'])
    ok(*call('POST', '/teams/%s/transfer' % T['teamId'], {'userId': B['id']}, token=A['t'])[:2], '인도자 넘기기')
    # C 는 팀을 나간다 (team_audit.actor_id)
    ok(*call('DELETE', '/teams/%s/members/%s' % (T['teamId'], C['id']), token=C['t'])[:2], '팀 나가기')
    st, j, _ = call('POST', '/auth/delete', {'username': A['u'], 'password': A['pw']}, token=A['t'])
    if st != 200: fail('F05 전 인도자 계정 삭제가 %s: %s' % (st, j))
    if me_status(token=A['t']) != 401: fail('F05 지운 계정의 세션이 살아 있음')
    st, j, _ = call('POST', '/auth/delete', {'username': C['u'], 'password': C['pw']}, token=C['t'])
    if st != 200: fail('F05 팀을 나간 사람 계정 삭제가 %s: %s' % (st, j))
    tv = ok(*call('GET', '/teams/' + T['teamId'], token=B['t'])[:2], '팀 보기')
    if tv.get('billingUserId') != B['id']: fail('F05 결제 담당이 남은 인도자로 돌아오지 않음: %s' % tv.get('billingUserId'))
    if sql("select count(*) from invites where team_id=%s" % lit(T['teamId'])) != '1': fail('F05 팀 기본 초대 링크가 사라짐')
    print('F05 전 인도자 · 나간 사람 삭제 ok')

    # 중간에 실패하면 아무것도 지워지지 않아야 한다 (메모 · 혼자 팀 · 파일)
    E = signup('dle'); TE = team(E, '혼자팀')
    st, j, _ = call('POST', '/blobs/audf05x1?team=' + TE['teamId'], raw=b'\x89PNG' + b'0' * 200, ctype='image/png', token=E['t'])
    ok(st, j, '파일 올리기')
    burl = j['url']
    note = {'id': 'audn' + tag, 'itemId': 'it1', 'layer': 'mine', 'text': '내 메모'}
    ok(*call('POST', '/notes', {'teamId': TE['teamId'], 'serviceId': 's1', 'notes': [note]}, token=E['t'])[:2], '메모')
    probe = 'audit_api_auth_probe_' + tag
    sql('create table %s (u uuid references users(id))' % probe)
    try:
        sql('insert into %s values(%s)' % (probe, lit(E['id'])))
        st, j, _ = call('POST', '/auth/delete', {'username': E['u'], 'password': E['pw']}, token=E['t'])
        if st == 200: fail('F05 탐침 행이 있는데 삭제가 성공함')
        left = sql("select (select count(*) from notes where author_id=%s)||','||(select count(*) from teams where id=%s)||','||(select count(*) from blobs where team_id=%s)"
                   % (lit(E['id']), lit(TE['teamId']), lit(TE['teamId'])))
        if left != '1,1,1': fail('F05 삭제가 실패했는데 메모/팀/파일 행이 먼저 지워짐 (notes,teams,blobs=%s)' % left)
        try: urllib.request.urlopen(burl, timeout=10)
        except urllib.error.HTTPError as e: fail('F05 삭제가 실패했는데 파일이 지워짐 (%s)' % e.code)
    finally:
        sql('drop table if exists %s' % probe)
    st, j, _ = call('POST', '/auth/delete', {'username': E['u'], 'password': E['pw']}, token=E['t'])
    if st != 200: fail('F05 탐침을 치운 뒤 삭제 실패 %s %s' % (st, j))
    if sql("select count(*) from teams where id=%s" % lit(TE['teamId'])) != '0': fail('F05 혼자 팀이 남음')
    try:
        urllib.request.urlopen(burl, timeout=10); fail('F05 혼자 팀의 파일이 남음')
    except urllib.error.HTTPError as e:
        if e.code != 404: fail('F05 파일 확인 응답이 이상함 %s' % e.code)
    print('F05 실패하면 통째로 되돌리고, 성공하면 파일까지 ok')

# ---------- F36 ----------
def t_f36():
    L = signup('dsl'); M = signup('dsm')
    S = team(L, '지운팀'); join(M, S)
    ok(*call('DELETE', '/teams/' + S['teamId'], {'name': '지운팀'}, token=L['t'])[:2], '팀 삭제')
    st, j, _ = call('POST', '/auth/delete', {'username': L['u'], 'password': L['pw']}, token=L['t'])
    if st != 200: fail('F36 지운 팀이 계정 삭제를 막음: %s %s' % (st, j))
    row = sql("select (deleted_at is not null)::text||','||created_by from teams where id=%s" % lit(S['teamId']))
    if row != 'true,' + M['id']: fail('F36 지운 팀이 유예 상태로 남은 멤버에게 넘어가지 않음: %s' % row)
    # 다른 멤버가 모두 비활성(나감)이면 넘길 사람이 없다 → 막지 않고 팀을 삭제 예약한다
    L2 = signup('dsl'); M2 = signup('dsm')
    R = team(L2, '빈팀'); join(M2, R)
    ok(*call('DELETE', '/teams/%s/members/%s' % (R['teamId'], M2['id']), token=M2['t'])[:2], '나가기')
    st, j, _ = call('POST', '/auth/delete', {'username': L2['u'], 'password': L2['pw']}, token=L2['t'])
    if st != 200: fail('F36 비활성 멤버만 남은 팀이 계정 삭제를 막음: %s %s' % (st, j))
    if sql("select (deleted_at is not null)::text from teams where id=%s" % lit(R['teamId'])) != 'true': fail('F36 주인 없는 팀이 삭제 예약되지 않음')
    # 활성 멤버가 있으면 여전히 막는다
    L3 = signup('dsl'); M3 = signup('dsm'); Q = team(L3, '산팀'); join(M3, Q)
    st, j, _ = call('POST', '/auth/delete', {'username': L3['u'], 'password': L3['pw']}, token=L3['t'])
    if st != 400 or '인도자' not in j.get('message', ''): fail('F36 활성 멤버가 있는 팀의 인도자가 그냥 지워짐 %s %s' % (st, j))
    print('F36 ok')

# ---------- F04 ----------
def t_f04():
    S1 = signup('dso'); TS = team(S1, '소셜팀')
    sql("update users set password_hash='' where id=%s" % lit(S1['id']))   # 소셜로만 가입한 계정과 같은 상태
    st, j, _ = call('POST', '/auth/delete', {'username': 'nope'}, token=S1['t'])
    if st != 400: fail('F04 아이디 확인 없이 지워짐 %s' % st)
    st, j, _ = call('POST', '/auth/delete', {'username': S1['u']}, token=S1['t'])
    if st != 200: fail('F04 소셜 전용 계정을 못 지움: %s %s' % (st, j))
    if sql("select count(*) from users where id=%s" % lit(S1['id'])) != '0': fail('F04 계정이 남음')
    print('F04 api ok')

def t_f04_ui(b):
    S2 = signup('dsu', password='secret1')
    ck = login(S2, app=False)
    c = b.new_context(viewport={'width': 1180, 'height': 820})
    c.add_cookies([{'name': 'conti_s', 'value': ck.split('=', 1)[1], 'url': URL}])
    pg = c.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:150])); pg.on('dialog', lambda d: d.accept())
    pg.goto(URL); pg.wait_for_selector('#gtTeam', timeout=15000)
    pg.fill('#gtTeam', '소셜팀'); pg.click('[data-act="team-create"]'); pg.wait_for_selector('.shell[data-page]', timeout=15000)
    sql("update users set password_hash='' where id=%s" % lit(S2['id']))
    pg.goto(URL + '#/settings'); pg.wait_for_selector('.setpane', timeout=10000)
    pg.click('[data-act="set-tab"][data-t="account"]'); pg.wait_for_selector('#sDel', timeout=5000)
    pg.wait_for_function("()=>{const b=document.querySelector('#linkList');return b&&!/불러오는 중/.test(b.textContent)}", timeout=15000)
    # 복구 코드: 소셜 전용 계정은 비밀번호 칸 없이 바로 발급
    pg.click('#sRc'); pg.wait_for_selector('#rcPw, .linkbox', timeout=5000)
    if pg.locator('#rcPw').count(): fail('F37 소셜 전용 계정에 비밀번호 칸이 뜸')
    pg.wait_for_selector('.linkbox', timeout=5000); pg.click('#rcClose'); pg.wait_for_timeout(300)
    pg.click('#sDel'); pg.wait_for_selector('#daUser', timeout=5000)
    if pg.locator('#daPw').count(): fail('F04 소셜 전용 계정인데 비밀번호 칸이 있음')
    pg.fill('#daUser', S2['u']); pg.click('#daGo')
    pg.wait_for_selector('#lgUser', timeout=20000)
    if sql("select count(*) from users where id=%s" % lit(S2['id'])) != '0': fail('F04 화면에서 지웠는데 계정이 남음')
    if errs: fail('F04 화면 오류 %s' % errs[:2])
    c.close()
    print('F04 화면 ok')

# ---------- F37 ----------
def t_f37():
    P = signup('drc')
    st, j, _ = call('POST', '/auth/recovery', {}, token=P['t'])
    if st == 200: fail('F37 비밀번호 없이 복구 코드가 나옴')
    st, j, _ = call('POST', '/auth/recovery', {'password': 'wrong-pw'}, token=P['t'])
    if st != 401: fail('F37 틀린 비밀번호로 %s' % st)
    st, j, _ = call('POST', '/auth/recovery', {'password': P['pw']}, token=P['t'])
    if st != 200 or not j.get('code'): fail('F37 맞는 비밀번호로 발급 안 됨 %s %s' % (st, j))
    code = j['code']
    # 복구는 그대로 된다
    st, j, _ = call('POST', '/auth/recover', {'username': P['u'], 'code': code, 'next': 'newpass9'})
    if st != 200: fail('F37 발급한 코드로 복구 실패 %s %s' % (st, j))
    # 틀린 비밀번호도 로그인처럼 시도 횟수를 센다 — 세션만 가진 사람이 비밀번호를 맞혀 볼 수 없게
    Q = signup('drq'); seen = set()
    for i in range(9):
        st, j, _ = call('POST', '/auth/recovery', {'password': 'bad%d' % i}, token=Q['t']); seen.add(st)
    if 429 not in seen: fail('F37 틀린 비밀번호를 계속 넣어도 막지 않음 %s' % seen)
    # 동시에 보내도 잠금을 건너뛰지 못한다 (전에는 40개가 모두 401 — 먼저 세어 보고 나중에 더했다)
    Q2 = signup('drp')
    r = parallel(40, lambda i: call('POST', '/auth/recovery', {'password': 'bad%d' % i}, token=Q2['t'])[0])
    if r.count(401) > 8 or 429 not in r: fail('F37 동시에 보낸 틀린 비밀번호가 잠금을 건너뜀 401=%d 429=%d' % (r.count(401), r.count(429)))
    # 옛 앱(비밀번호 칸이 없어 몸통 없이 부른다)은 업데이트 안내만 — 시도로 세지 않아 비밀번호 바꾸기·삭제가 잠기지 않는다
    O = signup('dro')
    r = [call('POST', '/auth/recovery', None, token=O['t']) for _ in range(9)]
    if any(x[0] != 403 or x[1].get('error') != 'reauth_required' for x in r): fail('F37 옛 앱 호출이 %s' % [(x[0], x[1].get('error')) for x in r][:3])
    if '업데이트' not in r[0][1].get('message', ''): fail('F37 옛 앱에 업데이트 안내가 없음: %s' % r[0][1])
    st, j, _ = call('POST', '/auth/password', {'current': O['pw'], 'next': 'secret2'}, token=O['t'])
    if st != 200: fail('F37 옛 앱 호출 몇 번에 비밀번호 바꾸기가 잠김 %s %s' % (st, j))
    # 연결된 구글·애플도 비밀번호도 없으면 이 세션이 유일한 길 → 그대로 발급 (들어올 길을 만들 수 있게)
    S = signup('drs'); sql("update users set password_hash='' where id=%s" % lit(S['id']))
    st, j, _ = call('POST', '/auth/recovery', {}, token=S['t'])
    if st != 200: fail('F37 로그인 수단이 없는 계정 발급 실패 %s %s' % (st, j))
    # 구글로만 들어오는 계정: 세션만으로는 복구 코드 · 비밀번호 만들기 · 계정 삭제가 안 된다 (다시 로그인한 토큰은 t_social 에서)
    G = signup('drg'); sql("update users set password_hash='' where id=%s" % lit(G['id']))
    sql("insert into identities(provider, subject, user_id, email) values('google', %s, %s, 'g@audit.example')" % (lit('drg-' + G['id']), lit(G['id'])))
    for path, body in (('/auth/recovery', {}), ('/auth/password', {'next': 'hijack1'}), ('/auth/delete', {'username': G['u']})):
        st, j, _ = call('POST', path, body, token=G['t'])
        if st != 403 or j.get('error') != 'reauth_required': fail('F37 소셜 전용 계정이 세션만으로 %s → %s %s' % (path, st, j))
    if sql("select (password_hash='' and recovery_hash is null)::text from users where id=%s" % lit(G['id'])) != 'true': fail('F37 세션만으로 비밀번호·복구 코드가 생김')
    print('F37 ok')

def t_f37_ui(b):
    P = signup('dru'); ck = login(P, app=False)
    c = b.new_context(viewport={'width': 1180, 'height': 820})
    c.add_cookies([{'name': 'conti_s', 'value': ck.split('=', 1)[1], 'url': URL}])
    pg = c.new_page(); pg.on('dialog', lambda d: d.accept())
    pg.goto(URL); pg.wait_for_selector('#gtTeam', timeout=15000)
    pg.fill('#gtTeam', '복구팀'); pg.click('[data-act="team-create"]'); pg.wait_for_selector('.shell[data-page]', timeout=15000)
    pg.goto(URL + '#/settings'); pg.wait_for_selector('.setpane', timeout=10000)
    pg.click('[data-act="set-tab"][data-t="account"]'); pg.wait_for_selector('#sRc', timeout=5000)
    pg.wait_for_function("()=>{const b=document.querySelector('#linkList');return b&&!/불러오는 중/.test(b.textContent)}", timeout=15000)
    pg.click('#sRc'); pg.wait_for_selector('#rcPw', timeout=5000)
    pg.fill('#rcPw', 'wrong-pw'); pg.click('#rcGo'); pg.wait_for_timeout(700)
    if pg.locator('.linkbox').count(): fail('F37 화면: 틀린 비밀번호로 코드가 보임')
    if '비밀번호' not in pg.locator('#rcErr').inner_text(): fail('F37 화면: 틀린 비밀번호 안내가 없음')
    pg.fill('#rcPw', P['pw']); pg.click('#rcGo'); pg.wait_for_selector('.linkbox', timeout=5000)
    if len(pg.locator('.linkbox').inner_text().strip()) < 12: fail('F37 화면: 코드가 이상함')
    c.close()
    print('F37 화면 ok')

# ---------- F38 · F111 ----------
def t_rename():
    L = signup('drn'); T = team(L, '이름팀')
    tid = T['teamId']
    M = signup('drm'); join(M, T, '싱', '싱어')
    # 그날 정원 (앞으로의 날짜)
    day = time.strftime('%Y-%m-%d', time.localtime(time.time() + 20 * 86400))
    d = ok(*call('POST', '/teams/%s/dates' % tid, {'date': day, 'label': '주일'}, token=L['t'])[:2], '날짜')['date']
    ok(*call('PUT', '/teams/%s/dates/%s/lineup' % (tid, d['id']), {'lineup': [], 'slots': {'싱어': 5, '드럼': 2}}, token=L['t'])[:2], '정원')
    # 녹음 + 싱어 세션 메모
    u = ok(*call('POST', '/rehearsals/upload-url', {'teamId': tid, 'size': 1000, 'mime': 'audio/mp4'}, token=L['t'])[:2], '업로드 주소')
    urllib.request.urlopen(urllib.request.Request(u['uploadUrl'], data=b'\0' * 1000, method='PUT', headers={'content-type': 'audio/mp4'}))
    r = ok(*call('POST', '/rehearsals', {'teamId': tid, 'serviceId': 'svc1', 'pathname': u['pathname'], 'blobId': u['blobId'], 'duration': 10}, token=L['t'])[:2], '녹음')['rehearsal']
    ok(*call('POST', '/rehearsals/%s/notes' % r['id'], {'teamId': tid, 'note': {'layer': 'session', 'session': '싱어', 'text': '싱어끼리', 't': 3}}, token=M['t'])[:2], '녹음 메모')
    # 맞바꿀 세션의 메모 (예배 메모 · 고정 메모)
    notes = [{'id': 'aud1' + tag, 'itemId': 'i1', 'layer': 'leader', 'session': '드럼', 'text': '드럼 메모'},
             {'id': 'aud2' + tag, 'itemId': 'i1', 'layer': 'leader', 'session': '베이스', 'text': '베이스 메모'}]
    ok(*call('POST', '/notes', {'teamId': tid, 'serviceId': 'svc1', 'notes': notes}, token=L['t'])[:2], '메모')
    s = ok(*call('POST', '/songs', {'teamId': tid, 'title': '맞바꿈'}, token=L['t'])[:2], '곡')
    song = s.get('song') or s
    aid = (song.get('arrangements') or [{}])[0].get('id') or sql("select id from arrangements where song_id=%s limit 1" % lit(song['id']))
    for sess in ('드럼', '베이스'):
        ok(*call('POST', '/arrangements/%s/notes' % aid, {'teamId': tid, 'layer': 'session', 'session': sess, 'text': sess + ' 고정'}, token=L['t'])[:2], '고정 메모')
    tv = ok(*call('GET', '/teams/' + tid, token=L['t'])[:2], '팀')
    sessions = tv['sessions']
    new = [{'싱어': '보컬', '드럼': '베이스', '베이스': '드럼'}.get(x, x) for x in sessions]
    ok(*call('PATCH', '/teams/' + tid, {'sessions': new, 'rename': {'싱어': '보컬', '드럼': '베이스', '베이스': '드럼'}}, token=L['t'])[:2], '이름 바꾸기')
    slots = json.loads(sql("select slots::text from service_dates where id=%s" % lit(d['id'])) or '{}')
    if slots.get('보컬') != 5 or '싱어' in slots or slots.get('베이스') != 2: fail('F38 그날 정원이 새 이름을 따라가지 않음: %s' % slots)
    rs = ok(*call('GET', '/rehearsals?team=%s&service=svc1' % tid, token=M['t'])[:2], '녹음 목록')['rehearsals']
    got = [n for n in rs[0]['notes'] if n['text'] == '싱어끼리']
    if not got or got[0].get('session') != '보컬': fail('F38 녹음 메모 세션이 옛 이름으로 남음: %s' % rs[0]['notes'])
    ns = dict(x.split('|') for x in sql("select text||'|'||session from notes where team_id=%s" % lit(tid)).splitlines())
    if ns != {'드럼 메모': '베이스', '베이스 메모': '드럼'}: fail('F111 맞바꾼 뒤 예배 메모 세션이 이상함: %s' % ns)
    an = dict(x.split('|') for x in sql("select text||'|'||session from arrangement_notes where team_id=%s" % lit(tid)).splitlines())
    if an != {'드럼 고정': '베이스', '베이스 고정': '드럼'}: fail('F111 맞바꾼 뒤 고정 메모 세션이 이상함: %s' % an)
    print('F38 · F111 ok')

# 이름 바꾸기와 동시에 단 녹음 메모가 사라지지 않는다 (배열을 읽어 고쳐 다시 쓰지 않고 한 문장으로)
def t_rename_race():
    L = signup('drr'); T = team(L, '동시팀'); tid = T['teamId']
    M = signup('drq'); join(M, T, '싱', '싱어')
    rids = []
    for i in range(30):
        u = ok(*call('POST', '/rehearsals/upload-url', {'teamId': tid, 'size': 100, 'mime': 'audio/mp4'}, token=L['t'])[:2], '업로드 주소')
        urllib.request.urlopen(urllib.request.Request(u['uploadUrl'], data=b'\0' * 100, method='PUT', headers={'content-type': 'audio/mp4'}))
        r = ok(*call('POST', '/rehearsals', {'teamId': tid, 'serviceId': 'svr%d' % i, 'pathname': u['pathname'], 'blobId': u['blobId'], 'duration': 10}, token=L['t'])[:2], '녹음')['rehearsal']
        rids.append(r['id'])
        ok(*call('POST', '/rehearsals/%s/notes' % r['id'], {'teamId': tid, 'note': {'layer': 'session', 'session': '싱어', 'text': '처음', 't': 1}}, token=M['t'])[:2], '메모')
    posted, stop = [], [False]
    def poster(k):
        i = 0
        while not stop[0]:
            nid = 'rr%s_%d_%d' % (tag, k, i)
            st, j, _ = call('POST', '/rehearsals/%s/notes' % rids[(k * 7 + i) % len(rids)], {'teamId': tid, 'note': {'id': nid, 'layer': 'mine', 'text': '동시', 't': 2}}, token=M['t'])
            if st == 200: posted.append(nid)
            i += 1
    th = [threading.Thread(target=poster, args=(k,)) for k in range(4)]
    for x in th: x.start()
    time.sleep(0.4)
    sess = ok(*call('GET', '/teams/' + tid, token=L['t'])[:2], '팀')['sessions']
    try:
        for k in range(6):
            a, b = ('싱어', '보컬') if k % 2 == 0 else ('보컬', '싱어')
            sess = [b if x == a else x for x in sess]
            ok(*call('PATCH', '/teams/' + tid, {'sessions': sess, 'rename': {a: b}}, token=L['t'])[:2], '이름 바꾸기')
    finally:
        stop[0] = True
        for x in th: x.join()
    have = set(sql("select x->>'id' from rehearsals r, jsonb_array_elements(r.notes) x where r.team_id=%s" % lit(tid)).split())
    lost = [n for n in posted if n not in have]
    if lost: fail('F38 이름을 바꾸는 동안 단 녹음 메모 %d/%d 개가 사라짐' % (len(lost), len(posted)))
    left = sql("select count(*) from rehearsals r, jsonb_array_elements(r.notes) x where r.team_id=%s and x->>'session' is not null and x->>'session'<>'싱어'" % lit(tid))
    if left != '0': fail('F38 여섯 번 바꾼 뒤(싱어로 돌아옴) 세션 메모 %s 개가 다른 이름' % left)
    print('F38 동시 메모 ok (%d 개 모두 남음)' % len(posted))

# ---------- G02 ----------
def t_prefs():
    A = signup('dpf')
    st, j, _ = call('PUT', '/me/prefs/stage/big~pc', {'value': {'x': 'a' * 100000}}, token=A['t'])
    if st != 413: fail('G02 무대 조판 하나가 100KB 인데 받아 줌 %s' % st)
    for i in range(305):
        st, j, _ = call('PUT', '/me/prefs/stage/k%03d~pc' % i, {'value': {'zoom': 1, 'i': i}}, token=A['t'])
        if st != 200: fail('G02 조판 저장 실패 %s %s' % (st, j))
    p = ok(*call('GET', '/me/prefs', token=A['t'])[:2], '설정')['prefs']
    stg = p.get('stage') or {}
    if len(stg) > 300: fail('G02 조판 개수 한도가 없음: %d' % len(stg))
    if 'k304~pc' not in stg or stg['k304~pc'].get('i') != 304: fail('G02 방금 저장한 조판이 없음')
    if 'k000~pc' in stg: fail('G02 오래된 조판부터 빠지지 않음')
    # 지우기
    ok(*call('PUT', '/me/prefs/stage/k304~pc', {'value': None}, token=A['t'])[:2], '조판 지우기')
    stg = ok(*call('GET', '/me/prefs', token=A['t'])[:2], '설정')['prefs'].get('stage') or {}
    if 'k304~pc' in stg: fail('G02 지운 조판이 남음')
    # 조판은 users.prefs 를 다시 쓰지 않는다
    if sql("select (prefs ? 'stage')::text from users where id=%s" % lit(A['id'])) != 'false': fail('G02 조판이 아직 users.prefs 안에 있음')
    # 예전 방식으로 prefs 안에 있던 조판은 읽을 때 옮긴다
    B = signup('dpg')
    sql("""update users set prefs = '{"bpm":88,"stage":{"old~pc":{"zoom":2}}}'::jsonb where id=%s""" % lit(B['id']))
    p = ok(*call('GET', '/me/prefs', token=B['t'])[:2], '설정')['prefs']
    if (p.get('stage') or {}).get('old~pc', {}).get('zoom') != 2 or p.get('bpm') != 88: fail('G02 옛 조판을 못 읽음: %s' % p)
    if sql("select (prefs ? 'stage')::text from users where id=%s" % lit(B['id'])) != 'false': fail('G02 옛 조판을 옮기지 않음')
    p = ok(*call('PATCH', '/me/prefs', {'prefs': {'bpm': 90}}, token=B['t'])[:2], 'PATCH')['prefs']
    if p.get('bpm') != 90 or (p.get('stage') or {}).get('old~pc', {}).get('zoom') != 2: fail('G02 PATCH 응답에 조판이 빠짐: %s' % p)
    # PATCH 로는 조판을 못 덮는다 · 전체 크기 한도
    ok(*call('PATCH', '/me/prefs', {'prefs': {'stage': {'x': {'zoom': 9}}}}, token=B['t'])[:2], 'PATCH stage')
    stg = ok(*call('GET', '/me/prefs', token=B['t'])[:2], '설정')['prefs'].get('stage') or {}
    if 'x' in stg or 'old~pc' not in stg: fail('G02 PATCH 가 조판을 덮음: %s' % stg)
    codes = [call('PATCH', '/me/prefs', {'prefs': {'k%d' % i: 'z' * 150000}}, token=B['t'])[0] for i in range(4)]
    if 413 not in codes: fail('G02 설정 전체 크기 한도가 없음 %s' % codes)
    size = int(sql("select pg_column_size(prefs) from users where id=%s" % lit(B['id'])))
    if size > 300000: fail('G02 prefs 가 %d 바이트까지 커짐' % size)
    # 아직 옮기지 않은 옛 조판이 커도(120KB) 다른 설정 PATCH 는 된다 — 크기는 조판을 뺀 나머지로 센다
    C = signup('dph')
    sql("""update users set prefs = jsonb_build_object('bpm', 80, 'stage', jsonb_build_object('old~pc', jsonb_build_object('x', repeat('a', 120000)))) where id=%s""" % lit(C['id']))
    st, j, _ = call('PATCH', '/me/prefs', {'prefs': {'bpm': 90}}, token=C['t'])
    if st != 200 or j['prefs'].get('bpm') != 90: fail('G02 옛 조판이 큰 계정의 PATCH 가 %s %s' % (st, str(j)[:120]))
    if sql("select prefs->>'bpm' from users where id=%s" % lit(C['id'])) != '90': fail('G02 PATCH 가 저장되지 않음')
    print('G02 ok')

# ---------- F02 ----------
def parallel(n, fn):
    out = [None] * n
    def run(i): out[i] = fn(i)
    th = [threading.Thread(target=run, args=(i,)) for i in range(n)]
    for t in th: t.start()
    for t in th: t.join()
    return out

def t_ai():
    try: sql("delete from ai_usage_all where day=%s" % KST)
    except Exception: pass
    A = signup('dai'); T1 = team(A, 'AI팀1'); T2 = team(A, 'AI팀2')
    body = lambda t: {'teamId': t['teamId'], 'b64': 'x' * 200, 'mime': 'image/png'}
    r1 = parallel(100, lambda i: call('POST', '/omr', body(T1), token=A['t'])[0])
    ok1 = r1.count(200)
    if ok1 != 60: fail('F02 팀 하루 한도(60)를 동시에 부르면 %d 번 통과' % ok1)
    if set(r1) - {200, 429}: fail('F02 이상한 응답 %s' % set(r1))
    r2 = parallel(60, lambda i: call('POST', '/omr', body(T2), token=A['t'])[0])
    if r2.count(200) != 20: fail('F02 사람 하루 한도(80)를 동시에 부르면 %d 번 더 통과' % r2.count(200))
    if sql("select calls from ai_usage where team_id=%s and day=%s and kind='omr'" % (lit(T1['teamId']), KST)) != '60': fail('F02 팀 사용량 기록이 한도와 다름')
    print('F02 동시 호출 한도 ok')

    # G01 전체 하루 한도: 다 차면 막는다 (fail closed). 가입한 지 며칠 안 된 계정은 따로 둔 작은 통('omr:new')을 써서
    # 새 계정을 찍어 내 채워도 원래 쓰던 계정(팀)은 멈추지 않는다
    B = signup('dbi'); TB = team(B, 'AI팀3')          # 새 계정
    O = signup('dbo'); TO = team(O, 'AI팀4')          # 오래 쓴 계정
    sql("update users set created_at=now()-interval '30 days' where id=%s" % lit(O['id']))
    if call('POST', '/omr', body(TB), token=B['t'])[0] != 200 or call('POST', '/omr', body(TO), token=O['t'])[0] != 200: fail('G01 첫 호출이 막힘')
    sql("insert into ai_usage_all(day, kind, calls) values(%s, 'omr:new', 1000000) on conflict (day, kind) do update set calls=1000000" % KST)
    try:
        st, j, _ = call('POST', '/omr', body(TB), token=B['t'])
        if st != 429: fail('G01 새 계정 통이 찼는데 통과 %s' % st)
        if call('POST', '/omr', body(TO), token=O['t'])[0] != 200: fail('G01 새 계정들이 채운 한도에 오래 쓴 계정까지 멈춤')
        sql("insert into ai_usage_all(day, kind, calls) values(%s, 'omr', 1000000) on conflict (day, kind) do update set calls=1000000" % KST)
        st, j, _ = call('POST', '/omr', body(TO), token=O['t'])
        if st != 429: fail('G01 전체 한도가 찼는데 통과 %s' % st)
    finally:
        sql("delete from ai_usage_all where day=%s" % KST)
    if call('POST', '/omr', body(TB), token=B['t'])[0] != 200: fail('G01 전체 한도를 비웠는데 막힘')
    print('G01 전체 하루 한도 · 새 계정 통 ok')

def t_signup_ip():
    # 문서용 주소. /64 마다 따로 세므로 돌릴 때마다 앞 64비트를 다르게
    rnd = lambda: '2001:db8:%x:%x::%x:%x' % tuple(random.randint(0, 65535) for _ in range(4))
    ip = rnd()
    xff = {'x-forwarded-for': '10.0.0.1, ' + ip}   # 앞단이 붙인 맨 뒤 값이 진짜 주소
    codes = []
    for i in range(32):
        st, j, _ = call('POST', '/auth/signup', {'username': uname('dip'), 'password': 'secret1', 'name': '가'}, headers=xff)
        codes.append(st)
        if st == 429: break
    if 429 not in codes: fail('G01 한 주소에서 가입을 %d 번 해도 막지 않음' % len(codes))
    if codes.index(429) < 20: fail('G01 가입 제한이 너무 빡빡함 (%d 번째에서 막힘)' % (codes.index(429) + 1))
    # 다른 주소는 그대로
    st, j, _ = call('POST', '/auth/signup', {'username': uname('dip'), 'password': 'secret1', 'name': '가'}, headers={'x-forwarded-for': rnd()})
    if st != 200: fail('G01 다른 주소 가입까지 막힘 %s' % st)
    print('G01 주소당 가입 제한 ok (%d 번째에서 막힘)' % (codes.index(429) + 1))
    # 한 /64 안에서 뒤 64비트를 바꿔 가며 가입해도 같이 센다 (전에는 45개가 모두 통과)
    pre = '2001:db8:%x:%x' % (random.randint(0, 65535), random.randint(0, 65535))
    codes = [call('POST', '/auth/signup', {'username': uname('div'), 'password': 'secret1', 'name': '가'},
                  headers={'x-forwarded-for': '%s:%x:%x:%x:%x' % (pre, i + 1, i * 7 + 1, i * 13 + 1, i + 5)})[0] for i in range(34)]
    if codes.count(200) != 30: fail('G01 한 /64 에서 주소를 바꿔 가며 가입이 %d 번 됨' % codes.count(200))
    # 동시에 보내도 한도를 넘지 않는다 (전에는 다 만든 뒤에 세어서 80개가 모두 통과)
    ip4 = '198.51.100.%d' % random.randint(1, 254)
    sql("delete from login_attempts where username=%s" % lit('signup:|' + ip4))
    names = [uname('dpp') for _ in range(60)]   # 아이디는 미리 (스레드끼리 겹치지 않게)
    r = parallel(60, lambda i: call('POST', '/auth/signup', {'username': names[i], 'password': 'secret1', 'name': '가'}, headers={'x-forwarded-for': ip4})[0])
    if r.count(200) != 30 or set(r) - {200, 429}: fail('G01 한 주소에서 동시에 가입 %d 번 통과 %s' % (r.count(200), set(r)))
    print('G01 /64 · 동시 가입 ok')

# ---------- G09 ----------
def t_logout():
    A = signup('dlo')
    t2 = login(A)
    ok(*call('POST', '/auth/logout', {}, token=A['t'])[:2], '로그아웃')
    if me_status(token=A['t']) != 401: fail('G09 로그아웃한 토큰이 그대로 통함')
    if me_status(token=t2) != 200: fail('G09 다른 기기 토큰까지 끊김')
    ck = login(A, app=False)
    if me_status(cookie=ck) != 200: fail('G09 쿠키 로그인 실패')
    ok(*call('POST', '/auth/logout', {}, cookie=ck)[:2], '쿠키 로그아웃')
    if me_status(cookie=ck) != 401: fail('G09 로그아웃한 쿠키를 다시 보내면 통함')
    # 모든 기기에서 로그아웃
    t3 = login(A); t4 = login(A); time.sleep(1.1)
    ok(*call('POST', '/auth/logout', {'all': True}, token=t3)[:2], '모두 로그아웃')
    if me_status(token=t4) != 401 or me_status(token=t2) != 401: fail('G09 모든 기기에서 로그아웃이 다른 기기를 못 끊음')
    t5 = login(A)
    if me_status(token=t5) != 200: fail('G09 모두 로그아웃 뒤 다시 로그인이 안 됨')
    print('G09 ok')

def t_logout_ui(b):
    A = signup('dlu'); ck = login(A, app=False); other = login(A)
    c = b.new_context(viewport={'width': 1180, 'height': 820})
    c.add_cookies([{'name': 'conti_s', 'value': ck.split('=', 1)[1], 'url': URL}])
    pg = c.new_page(); pg.on('dialog', lambda d: d.accept())
    pg.goto(URL); pg.wait_for_selector('#gtTeam', timeout=15000)
    pg.fill('#gtTeam', '로그아웃팀'); pg.click('[data-act="team-create"]'); pg.wait_for_selector('.shell[data-page]', timeout=15000)
    time.sleep(1.1)
    pg.goto(URL + '#/settings'); pg.wait_for_selector('.setpane', timeout=10000)
    pg.click('[data-act="set-tab"][data-t="account"]'); pg.wait_for_selector('#sLogoutAll', timeout=5000)
    pg.click('#sLogoutAll'); pg.wait_for_selector('#lgUser', timeout=15000)
    if me_status(token=other) != 401: fail('G09 화면의 모든 기기 로그아웃이 다른 기기를 못 끊음')
    c.close()
    print('G09 화면 ok')

# ---------- 가짜 구글 · 가짜 Gemini 를 붙인 서버 (이 테스트가 띄우고 끈다) ----------
# 개발 서버는 진짜 구글 공개키로만 토큰을 믿고 AI 는 'mock'(다시 묻기 없이 바로 답)이라, 구글로 다시 로그인하는 확인과
# 악보 다시 묻기의 한도를 볼 수 없다. api/index.js 를 한 프로세스에 띄우고 바깥 요청(fetch)만 가로챈다. DB 는 로컬 도커
HARNESS_JS = r"""
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { webcrypto as wc } from 'node:crypto';
const root = process.env.ROOT;
for (const k of ['BLOB_READ_WRITE_TOKEN', 'R2_ENDPOINT', 'R2_BUCKET', 'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY', 'GOOGLE_APPLICATION_CREDENTIALS']) delete process.env[k];
Object.assign(process.env, { DATABASE_URL: 'postgres://postgres:pg@localhost:54329/postgres', AUTH_SECRET: process.env.AUTH_SECRET || 'local-dev-secret-0123456789',
  GOOGLE_CLIENT_ID_WEB: 'audit-client', APNS_BUNDLE_ID: 'audit.bundle', GEMINI_API_KEY: 'audit-fake', GOOGLE_VISION_KEY: 'mock' });
const kp = await wc.subtle.generateKey({ name: 'RSASSA-PKCS1-v1_5', modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: 'SHA-256' }, true, ['sign', 'verify']);
const jwk = await wc.subtle.exportKey('jwk', kp.publicKey); jwk.kid = 'audit-auth'; jwk.alg = 'RS256';
const b64u = (x) => Buffer.from(x).toString('base64url');
async function token(pv, sub, age) {
  const now = Math.floor(Date.now() / 1000) - age;
  const h = b64u(JSON.stringify({ alg: 'RS256', kid: 'audit-auth', typ: 'JWT' }));
  const b = b64u(JSON.stringify({ iss: pv === 'apple' ? 'https://appleid.apple.com' : 'https://accounts.google.com', aud: pv === 'apple' ? 'audit.bundle' : 'audit-client',
    sub, email: sub + '@audit.example', exp: now + 3600, iat: now }));
  return h + '.' + b + '.' + b64u(await wc.subtle.sign('RSASSA-PKCS1-v1_5', kp.privateKey, new TextEncoder().encode(h + '.' + b)));
}
const gem = {};   // 이미지 앞 8글자 → Gemini 를 부른 횟수
const reply = (status, obj) => new Response(JSON.stringify(obj), { status, headers: { 'content-type': 'application/json' } });
const okText = (text) => reply(200, { candidates: [{ content: { parts: [{ text }] }, finishReason: 'STOP' }], usageMetadata: { promptTokenCount: 100, candidatesTokenCount: 50, thoughtsTokenCount: 10, totalTokenCount: 160 } });
const realFetch = globalThis.fetch;
globalThis.fetch = async (u, o) => {
  const url = String(u);
  if (url.startsWith('https://www.googleapis.com/oauth2/v3/certs') || url.startsWith('https://appleid.apple.com/auth/keys')) return reply(200, { keys: [jwk] });
  if (!url.includes('generativelanguage.googleapis.com')) return realFetch(u, o);
  const body = JSON.parse(o.body), parts = body.contents[0].parts;
  const tag = (((parts.find((x) => x.inline_data) || {}).inline_data || {}).data || '').slice(0, 8);
  gem[tag] = (gem[tag] || 0) + 1;
  await new Promise((r) => setTimeout(r, 150));
  if (tag.startsWith('ERR503')) return reply(503, { error: { message: 'overloaded', status: 'UNAVAILABLE' } });
  if (tag.startsWith('BADJSON')) return okText('{"songs": [ truncated');
  if (/고칠 마디/.test(parts[0].text || '')) return okText('{"fixes": []}');
  // 4곡 · 곡마다 24마디가 모두 박자가 모자란다 → 곡마다 8마디씩 세 번 다시 묻는다 (사진 한 장에 1 + 12번)
  const song = (i) => ({ title: 's' + i, key: 'A', time: '4/4', timeSignature: '4/4', sections: [{ name: 'A', bars: [{ chords: ['A'] }] }],
    measures: Array.from({ length: 24 }, () => ({ n: [{ p: 'A4', d: 4 }] })) });
  return okText(JSON.stringify({ songs: [1, 2, 3, 4].map(song) }));
};
const { default: api } = await import(root + '/api/index.js');
const appDir = path.join(root, 'app');
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.json': 'application/json', '.png': 'image/png', '.svg': 'image/svg+xml', '.css': 'text/css', '.webmanifest': 'application/manifest+json' };
const srv = http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://x');
  if (url.pathname === '/__tok') return res.end(await token(url.searchParams.get('pv') || 'google', url.searchParams.get('sub') || '', +url.searchParams.get('age') || 0));
  if (url.pathname === '/__gem') { res.setHeader('content-type', 'application/json'); return res.end(JSON.stringify(gem)); }
  if (url.pathname === '/__env') { for (const [k, v] of url.searchParams) { if (v) process.env[k] = v; else delete process.env[k]; } return res.end('ok'); }
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
        env = {'PATH': os.environ.get('PATH', ''), 'HOME': os.environ.get('HOME', ''), 'ROOT': ROOT, 'BLOB_LOCAL_DIR': os.path.join(ROOT, '.localblob')}
        self.p = subprocess.Popen(['node', '--input-type=module', '-e', HARNESS_JS], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        line = ''
        for _ in range(200):
            line = self.p.stdout.readline()
            if line.startswith('READY') or not line: break
        if not line.startswith('READY'): raise RuntimeError('가짜 서버를 못 띄움: ' + line)
        self.base = 'http://127.0.0.1:%s/' % line.split()[1]
        threading.Thread(target=lambda: [None for _ in self.p.stdout], daemon=True).start()   # 로그는 버린다 (파이프가 차지 않게)
    def get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=30) as r: return r.read().decode()
    def tok(self, sub, pv='google', age=0): return self.get('__tok?pv=%s&sub=%s&age=%d' % (pv, sub, age))
    def env(self, **kw): self.get('__env?' + '&'.join('%s=%s' % kv for kv in kw.items()))
    def gem(self, t): return json.loads(self.get('__gem')).get(t[:8], 0)
    def call(self, *a, **kw): return call(*a, base=self.base, **kw)
    def close(self): self.p.terminate(); self.p.wait(10)
HX = [None]
def hx():
    if not HX[0]: HX[0] = Harness()
    return HX[0]

def social_account(H, sub, pv='google'):
    st, j, _ = H.call('POST', '/auth/social', {'provider': pv, 'idToken': H.tok(sub, pv), 'login': True, 'agreedAt': '2026-09-24T00:00:00Z'}, headers=APP)
    if st != 200: fail('소셜 가입 실패 %s %s' % (st, j))
    return {'t': j['token'], 'id': j['user']['id'], 'u': j['user']['username'], 'sub': sub}

# ---------- F37: 소셜 전용 계정 · 로그인 방법을 바꾸는 일은 다시 로그인한 토큰(또는 비밀번호)으로 ----------
def t_social():
    H = hx()
    S = social_account(H, 'sg1-' + tag)
    ra = lambda sub, pv='google', age=0: {'reauth': {'provider': pv, 'idToken': H.tok(sub, pv, age)}}
    st, j, _ = H.call('POST', '/auth/recovery', {}, token=S['t'])
    if st != 403 or j.get('error') != 'reauth_required': fail('F37 소셜 전용 계정이 세션만으로 복구 코드 %s %s' % (st, j))
    st, j, _ = H.call('POST', '/auth/recovery', ra('someone-else-' + tag), token=S['t'])
    if st != 401: fail('F37 이 계정에 안 붙은 구글 토큰으로 복구 코드 %s' % st)
    st, j, _ = H.call('POST', '/auth/recovery', ra(S['sub'], age=20 * 60), token=S['t'])
    if st != 401: fail('F37 20분 전에 받은 토큰으로 복구 코드 %s' % st)
    st, j, _ = H.call('POST', '/auth/recovery', ra(S['sub']), token=S['t'])
    if st != 200 or not j.get('code'): fail('F37 방금 다시 로그인한 토큰으로 복구 코드 실패 %s %s' % (st, j))
    # 세션만 가진 사람이 제 구글·애플을 붙여 두는 길도 막는다 (붙이면 그걸로 '다시 확인'을 통과한다)
    st, j, _ = H.call('POST', '/auth/social', {'provider': 'apple', 'idToken': H.tok('atk-' + tag, 'apple')}, token=S['t'])
    if st != 403: fail('F37 세션만으로 다른 애플 계정이 붙음 %s %s' % (st, j))
    st, j, _ = H.call('POST', '/auth/social', {'provider': 'apple', 'idToken': H.tok('sa1-' + tag, 'apple'), **ra(S['sub'])}, token=S['t'])
    if st != 200: fail('F37 구글로 확인하고 애플 연결 실패 %s %s' % (st, j))
    # 떼기도 확인이 필요하다 · 붙어 있는 다른 쪽(애플)으로 확인해도 된다
    st, j, _ = H.call('DELETE', '/auth/social/google', {}, token=S['t'])
    if st != 403: fail('F37 세션만으로 구글 연결이 떨어짐 %s' % st)
    st, j, _ = H.call('DELETE', '/auth/social/google', ra('sa1-' + tag, 'apple'), token=S['t'])
    if st != 200: fail('F37 애플로 확인하고 구글 떼기 실패 %s %s' % (st, j))
    if sql("select string_agg(provider, ',') from identities where user_id=%s" % lit(S['id'])) != 'apple': fail('F37 연결 목록이 이상함')
    # 비밀번호 만들기 · 계정 삭제
    P = social_account(H, 'sg2-' + tag)
    st, j, _ = H.call('POST', '/auth/password', {'next': 'hijack1'}, token=P['t'])
    if st != 403: fail('F37 세션만으로 소셜 전용 계정의 비밀번호가 생김 %s' % st)
    st, j, _ = H.call('POST', '/auth/password', {'next': 'mine123', **ra(P['sub'])}, token=P['t'])
    if st != 200: fail('F37 다시 로그인하고 비밀번호 만들기 실패 %s %s' % (st, j))
    D = social_account(H, 'sg3-' + tag)
    st, j, _ = H.call('POST', '/auth/delete', {'username': D['u']}, token=D['t'])
    if st != 403: fail('F37 세션만으로 소셜 전용 계정이 지워짐 %s' % st)
    st, j, _ = H.call('POST', '/auth/delete', {'username': D['u'], **ra(D['sub'])}, token=D['t'])
    if st != 200: fail('F37 다시 로그인하고 계정 삭제 실패 %s %s' % (st, j))
    # 비밀번호가 있는 계정은 비밀번호로 확인 (연결 · 해제)
    A = signup('dsp', base=H.base)
    st, j, _ = H.call('POST', '/auth/social', {'provider': 'google', 'idToken': H.tok('atk2-' + tag)}, token=A['t'])
    if st != 403: fail('F37 세션만으로 비밀번호 계정에 구글이 붙음 %s' % st)
    st, j, _ = H.call('POST', '/auth/social', {'provider': 'google', 'idToken': H.tok('sp1-' + tag), 'password': 'nope'}, token=A['t'])
    if st != 401: fail('F37 틀린 비밀번호로 구글이 붙음 %s' % st)
    st, j, _ = H.call('POST', '/auth/social', {'provider': 'google', 'idToken': H.tok('sp1-' + tag), 'password': A['pw']}, token=A['t'])
    if st != 200: fail('F37 비밀번호로 확인하고 구글 연결 실패 %s %s' % (st, j))
    st, j, _ = H.call('DELETE', '/auth/social/google', {}, token=A['t'])
    if st != 403: fail('F37 세션만으로 비밀번호 계정의 구글이 떨어짐 %s' % st)
    st, j, _ = H.call('DELETE', '/auth/social/google', {'password': A['pw']}, token=A['t'])
    if st != 200: fail('F37 비밀번호로 확인하고 구글 떼기 실패 %s' % st)
    # 로그인 화면의 소셜 로그인(login)은 그대로 — 확인 없이 들어온다
    st, j, _ = H.call('POST', '/auth/social', {'provider': 'apple', 'idToken': H.tok('sa1-' + tag, 'apple'), 'login': True}, headers=APP)
    if st != 200 or j['user']['id'] != S['id']: fail('F37 애플 로그인이 안 됨 %s' % st)
    print('F37 소셜 전용 · 연결/해제 다시 확인 ok')

def cookie_of(hd): return [c for c in hd.get_all('Set-Cookie') or [] if c.startswith('conti_s=')][0].split(';')[0]
def t_social_ui(b):
    H = hx()
    S = social_account(H, 'su1-' + tag)
    ck = cookie_of(H.call('POST', '/auth/social', {'provider': 'google', 'idToken': H.tok(S['sub']), 'login': True})[2])
    c = b.new_context(viewport={'width': 1180, 'height': 820}, service_workers='block')
    c.add_cookies([{'name': 'conti_s', 'value': ck.split('=', 1)[1], 'url': H.base}])
    # 구글 로그인 스크립트 대신: 숨은 버튼을 누르면 window.__sub 의 토큰을 돌려준다
    GSI = """window.google={accounts:{id:{initialize(o){window.__gcb=o.callback},prompt(){},
      renderButton(el){const b=document.createElement('div');b.setAttribute('role','button');
        b.onclick=async()=>{const r=await fetch('/__tok?sub='+encodeURIComponent(window.__sub||''));window.__gcb({credential:await r.text()})};el.appendChild(b)}}}};"""
    c.route('https://accounts.google.com/gsi/client', lambda r: r.fulfill(status=200, content_type='text/javascript', body=GSI))
    pg = c.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)[:150])); pg.on('dialog', lambda d: d.accept())
    def fresh(name):
        pg.goto(H.base); pg.wait_for_selector('#gtTeam', timeout=15000)
        pg.fill('#gtTeam', name); pg.click('[data-act="team-create"]'); pg.wait_for_selector('.shell[data-page]', timeout=15000)
        pg.goto(H.base + '#/settings'); pg.wait_for_selector('.setpane', timeout=10000)
        pg.click('[data-act="set-tab"][data-t="account"]'); pg.wait_for_selector('#sRc', timeout=5000)
        pg.wait_for_function("()=>{const b=document.querySelector('#linkList');return b&&!/불러오는 중/.test(b.textContent)}", timeout=15000)
    fresh('소셜확인팀')
    # 다른 구글 계정으로 확인하면 코드가 안 나온다
    pg.evaluate("s=>window.__sub=s", 'stranger-' + tag)
    pg.click('#sRc'); pg.wait_for_timeout(1500)
    if pg.locator('.linkbox').count(): fail('F37 화면: 다른 구글 계정으로 복구 코드가 나옴')
    if sql("select (recovery_hash is null)::text from users where id=%s" % lit(S['id'])) != 'true': fail('F37 화면: 다른 구글 계정으로 복구 코드가 저장됨')
    # 이 계정의 구글로 다시 로그인하면 나온다
    pg.evaluate("s=>window.__sub=s", S['sub'])
    pg.click('#sRc'); pg.wait_for_selector('.linkbox', timeout=8000)
    pg.click('#rcClose'); pg.wait_for_timeout(300)
    # 비밀번호 만들기 (현재 비밀번호 칸 없이 구글로 확인)
    if pg.locator('#sPw0').count(): fail('F37 화면: 소셜 전용 계정에 현재 비밀번호 칸이 있음')
    pg.fill('#sPw1', 'mine1234'); pg.click('#sPwOk')
    pg.wait_for_function("()=>/정했어요/.test((document.querySelector('#toast')||{}).textContent||'')", timeout=8000)
    if sql("select (password_hash<>'')::text from users where id=%s" % lit(S['id'])) != 'true': fail('F37 화면: 비밀번호가 안 생김')
    # 계정 삭제 (소셜 전용 · 구글로 확인)
    D = social_account(H, 'su2-' + tag)
    ck = cookie_of(H.call('POST', '/auth/social', {'provider': 'google', 'idToken': H.tok(D['sub']), 'login': True})[2])
    c.clear_cookies(); c.add_cookies([{'name': 'conti_s', 'value': ck.split('=', 1)[1], 'url': H.base}])
    fresh('지울팀')
    pg.evaluate("s=>window.__sub=s", D['sub'])
    pg.click('#sDel'); pg.wait_for_selector('#daUser', timeout=5000)
    if pg.locator('#daPw').count(): fail('F37 화면: 소셜 전용 계정 삭제에 비밀번호 칸이 있음')
    pg.fill('#daUser', D['u']); pg.click('#daGo')
    pg.wait_for_selector('#lgUser', timeout=20000)
    if sql("select count(*) from users where id=%s" % lit(D['id'])) != '0': fail('F37 화면: 구글로 확인했는데 계정이 남음')
    # 비밀번호가 있는 계정: 연결·해제 전에 현재 비밀번호를 묻는다 · 계정 삭제는 비밀번호 칸으로
    P = signup('dpu', base=H.base)
    ck = cookie_of(H.call('POST', '/auth/login', {'username': P['u'], 'password': P['pw']})[2])
    c.clear_cookies(); c.add_cookies([{'name': 'conti_s', 'value': ck.split('=', 1)[1], 'url': H.base}])
    fresh('비번팀')
    pg.evaluate("s=>window.__sub=s", 'pu-' + tag)
    pg.click('[data-link="google"]'); pg.wait_for_selector('#raPw', timeout=5000)
    pg.fill('#raPw', P['pw']); pg.click('#raGo')
    pg.wait_for_selector('[data-unlink="google"]', timeout=8000)
    if sql("select count(*) from identities where user_id=%s" % lit(P['id'])) != '1': fail('F37 화면: 비밀번호로 확인했는데 구글이 안 붙음')
    pg.click('[data-unlink="google"]'); pg.wait_for_selector('#raPw', timeout=5000)
    pg.fill('#raPw', P['pw']); pg.click('#raGo')
    pg.wait_for_selector('[data-link="google"]', timeout=8000)
    if sql("select count(*) from identities where user_id=%s" % lit(P['id'])) != '0': fail('F37 화면: 비밀번호로 확인했는데 구글이 안 떨어짐')
    pg.click('#sDel'); pg.wait_for_selector('#daPw', timeout=5000)
    pg.fill('#daUser', P['u']); pg.fill('#daPw', P['pw']); pg.click('#daGo')
    pg.wait_for_selector('#lgUser', timeout=20000)
    if sql("select count(*) from users where id=%s" % lit(P['id'])) != '0': fail('F37 화면: 비밀번호 계정 삭제가 안 됨')
    if errs: fail('F37 화면 오류 %s' % errs[:2])
    c.close()
    print('F37 화면 (소셜 전용 다시 확인) ok')

# ---------- F02 · G01: 악보 다시 묻기 · Vision 으로 다시 읽기도 부르기 전에 한도에서 자리를 잡는다 ----------
def t_ai_fanout():
    H = hx()
    H.env(AI_DAILY_SCORE=5, AI_DAILY_OCR=3)
    newteam = lambda A, name: ok(*H.call('POST', '/teams', {'name': name, 'myName': '인도', 'session': '인도자'}, token=A['t'])[:2], '팀')['teamId']
    used = lambda tid, kind: int(sql("select calls from ai_usage where team_id=%s and day=%s and kind=%s" % (lit(tid), KST, lit(kind))) or 0)
    try:
        A = signup('dfa', base=H.base)
        tid = newteam(A, '다시묻기'); img = 'RP' + tag
        r = parallel(20, lambda i: H.call('POST', '/score', {'teamId': tid, 'b64': img + 'A' * 200, 'mime': 'image/png'}, token=A['t'])[0])
        n = H.gem(img)
        if n > 5: fail('F02 팀 한도 5 인데 Gemini 를 %d 번 부름 (다시 묻기를 부른 뒤에 셈)' % n)
        if used(tid, 'score') != n: fail('F02 센 횟수(%d)와 부른 횟수(%d)가 다름' % (used(tid, 'score'), n))
        if not r.count(200) or set(r) - {200, 429}: fail('F02 응답이 이상함 %s' % set(r))
        # 한도가 넉넉하면 다시 묻기를 모두 하고, 한 번씩 센다 (사진 한 장에 1 + 12번)
        H.env(AI_DAILY_SCORE=100)
        tid2 = newteam(A, '다시묻기2'); img2 = 'RQ' + tag
        st, j, _ = H.call('POST', '/score', {'teamId': tid2, 'b64': img2 + 'A' * 200, 'mime': 'image/png'}, token=A['t'])
        if st != 200 or H.gem(img2) != 13 or used(tid2, 'score') != 13: fail('F02 다시 묻기 전부: %s 부름 %d 셈 %d' % (st, H.gem(img2), used(tid2, 'score')))
        print('F02 악보 다시 묻기 한도 ok (동시 20번 → %d 번 부름)' % n)
        # Vision 으로 다시 읽기: 과금된 실패(잘린 답) 뒤에는 장수만큼 더 잡아야 하고, 자리가 없으면 부르지 않는다
        ims = lambda t: [{'b64': t + 'A' * 200, 'mime': 'image/png', 'w': 10, 'h': 10}, {'b64': t + 'B' * 200, 'mime': 'image/png', 'w': 10, 'h': 10}]
        tid3 = newteam(A, '코드')
        st, j, _ = H.call('POST', '/ocr', {'teamId': tid3, 'images': ims('BADJSON1')}, token=A['t'])
        if st != 429 or used(tid3, 'ocr') > 3: fail('F02 코드 인식 한도 3 인데 Vision 으로 다시 읽음: %s 센 것 %d' % (st, used(tid3, 'ocr')))
        # 오류 응답(503)은 과금되지 않으니 돌려주고 Vision 장수만 센다
        tid4 = newteam(A, '코드2')
        st, j, _ = H.call('POST', '/ocr', {'teamId': tid4, 'images': ims('ERR503AB')}, token=A['t'])
        if st != 200 or j.get('engine') != 'vision' or used(tid4, 'ocr') != 2: fail('F02 Gemini 503 뒤 Vision: %s %s 센 것 %d' % (st, j.get('engine'), used(tid4, 'ocr')))
        print('F02 Vision 으로 다시 읽기 한도 ok')
    finally:
        H.env(AI_DAILY_SCORE='', AI_DAILY_OCR='')

def run():
    section(t_f05); section(t_f36); section(t_f04); section(t_f37); section(t_rename)
    section(t_rename_race); section(t_prefs); section(t_ai); section(t_signup_ip); section(t_logout)
    try:
        section(t_social); section(t_ai_fanout)
        with sync_playwright() as p:
            b = p.chromium.launch()
            section(lambda: t_f04_ui(b), 't_f04_ui'); section(lambda: t_f37_ui(b), 't_f37_ui'); section(lambda: t_logout_ui(b), 't_logout_ui')
            section(lambda: t_social_ui(b), 't_social_ui')
            b.close()
    finally:
        if HX[0]: HX[0].close()
    if FAILS:
        print('\n%d 건 실패' % len(FAILS)); sys.exit(1)
    print('OK — 계정/권한 감사 묶음 (F05 F36 F04 F37 F38 F111 G02 F02 G01 G09)')

run()
