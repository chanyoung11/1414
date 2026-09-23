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
def call(method, path, body=None, token=None, cookie=None, headers=None, raw=None, ctype=None):
    h = {'x-conti': '1'}
    if token: h['authorization'] = 'Bearer ' + token
    if cookie: h['cookie'] = cookie
    data = None
    if raw is not None: data = raw; h['content-type'] = ctype or 'application/octet-stream'
    elif body is not None: data = json.dumps(body).encode(); h['content-type'] = 'application/json'
    h.update(headers or {})
    req = urllib.request.Request(URL + 'api' + path, data=data, method=method, headers=h)
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
def signup(p, name='하은', password='secret1', headers=None):
    u = uname(p)
    st, j, _ = call('POST', '/auth/signup', {'username': u, 'password': password, 'name': name}, headers={**APP, **(headers or {})})
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
    # 소셜 전용 계정은 비밀번호가 없다 → 로그인만으로 (비밀번호 만들기와 같은 기준)
    S = signup('drs'); sql("update users set password_hash='' where id=%s" % lit(S['id']))
    st, j, _ = call('POST', '/auth/recovery', {}, token=S['t'])
    if st != 200: fail('F37 소셜 전용 계정 발급 실패 %s %s' % (st, j))
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

    # G01 전체 하루 한도: 다 차면 새 계정·새 팀도 막는다 (fail closed)
    B = signup('dbi'); TB = team(B, 'AI팀3')
    if call('POST', '/omr', body(TB), token=B['t'])[0] != 200: fail('G01 첫 호출이 막힘')
    sql("update ai_usage_all set calls=1000000 where day=%s and kind='omr'" % KST)
    try:
        st, j, _ = call('POST', '/omr', body(TB), token=B['t'])
        if st != 429: fail('G01 전체 한도가 찼는데 통과 %s' % st)
    finally:
        sql("delete from ai_usage_all where day=%s" % KST)
    if call('POST', '/omr', body(TB), token=B['t'])[0] != 200: fail('G01 전체 한도를 비웠는데 막힘')
    print('G01 전체 하루 한도 ok')

def t_signup_ip():
    rnd = lambda: '2001:db8::%x:%x' % (random.randint(0, 65535), random.randint(0, 65535))   # 문서용 주소 (돌릴 때마다 다르게)
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

def run():
    section(t_f05); section(t_f36); section(t_f04); section(t_f37); section(t_rename)
    section(t_prefs); section(t_ai); section(t_signup_ip); section(t_logout)
    with sync_playwright() as p:
        b = p.chromium.launch()
        section(lambda: t_f04_ui(b), 't_f04_ui'); section(lambda: t_f37_ui(b), 't_f37_ui'); section(lambda: t_logout_ui(b), 't_logout_ui')
        b.close()
    if FAILS:
        print('\n%d 건 실패' % len(FAILS)); sys.exit(1)
    print('OK — 계정/권한 감사 묶음 (F05 F36 F04 F37 F38 F111 G02 F02 G01 G09)')

run()
