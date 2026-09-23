# 감사 묶음 api-schedule-cron 회귀 검사 (사역 날짜 · 편성 통보 · 알림 · 크론)
#  F08  콘티 날짜를 옮기면 사역 날짜 연결도 따라간다 (옛 날짜에 남거나, 새 날짜에 빈 초안이 하나 더 생기지 않는다)
#  F09  GET /services 가 동시에 와도 자동 초안은 날짜마다 하나
#  F11  RevenueCat 웹훅은 x-conti 없이도 들어온다 (다른 쓰기 경로는 그대로 막힌다)
#  F54  다른 팀 알림을 누르면 그 팀으로 바꾼 뒤 연다 (sw 메시지 · ?team= 주소)
#  F55  같은 날 2부에만 편성된 사람이 불가능으로 바꿔도 인도자에게 알림이 간다
#  F56  팀 밖 사람은 편성에 들어가지 않고 알림도 받지 않는다
#  F57  사람은 그대로이고 세션만 바뀌어도 변경 통보가 간다
#  F58  계정을 지운 사람이 편성·통보 기록에 있어도 통보가 500 이 나지 않고, 다시 눌러도 또 보내지 않는다
#  G12  발행 전 콘티의 편성 통보는 편성 화면으로 · 목회자의 '쉽니다' 알림은 홈으로
#  F120 정기 예배 날짜·자동 초안은 한국 날짜 기준
#  F121 스케줄 요청의 '미선택' 수는 1부·2부 줄이 아니라 날짜로 센다
#  F122 크론이 팀을 나눠 동시에 돌아도 결과가 같다 (CRON_SECRET 이 있을 때만)
# 실행: CONTI_URL=http://localhost:8803/ [CRON_SECRET=...] .venv/bin/python tests/test_audit_api_schedule_cron.py
import os, sys, time, json, datetime, threading, itertools
import urllib.request, urllib.error, http.cookiejar
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
CRON = os.environ.get('CRON_SECRET', '')
tag = str(int(time.time() * 1000))[-8:]
_n = itertools.count(1)

def fail(m): print('FAIL:', m); sys.exit(1)

# 한국 날짜 (서버의 '오늘'과 같은 기준)
KST_TODAY = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=9)).date()
def day(n): return (KST_TODAY + datetime.timedelta(days=n)).isoformat()

class U:
    def __init__(self, name):
        self.name = name; self.id = None
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def call(self, method, path, body=None, headers=None, xconti=True):
        h = {'content-type': 'application/json'}
        if method != 'GET' and xconti: h['x-conti'] = '1'
        h.update(headers or {})
        data = None if method == 'GET' else json.dumps(body if body is not None else {}).encode()
        req = urllib.request.Request(URL + 'api/' + path.lstrip('/'), method=method, data=data, headers=h)
        try:
            with self.op.open(req, timeout=60) as r: return r.status, json.loads(r.read() or b'{}')
        except urllib.error.HTTPError as e:
            raw = e.read()
            try: return e.code, json.loads(raw or b'{}')
            except Exception: return e.code, {'raw': raw[:200].decode('utf-8', 'replace')}
    def ok(self, method, path, body=None):
        st, j = self.call(method, path, body)
        if st != 200: fail('%s %s → %s %s' % (method, path, st, j))
        return j

def signup(name):
    u = U(name)
    j = u.ok('POST', 'auth/signup', {'username': 'aq%s%02d' % (tag, next(_n)), 'password': 'secret1', 'name': name})
    u.id = j['user']['id']
    return u

# 계정 삭제(F58)에는 아이디가 필요하다
A_username = {}
def signup_named(name):
    u = U(name); un = 'aq%s%02d' % (tag, next(_n))
    j = u.ok('POST', 'auth/signup', {'username': un, 'password': 'secret1', 'name': name})
    u.id = j['user']['id']; A_username[u.id] = un
    return u

def team(leader, name):
    return leader.ok('POST', 'teams', {'name': '%s %s' % (name, tag), 'myName': leader.name, 'session': '건반'})

def join(u, t, sessions):
    return u.ok('POST', 'invite/%s/join' % t['invite'], {'name': u.name, 'sessions': sessions})

def sched(u, tid):
    return u.ok('GET', 'teams/%s/schedule?from=%s&to=%s' % (tid, day(-3), day(120)))

def notis(u, tid):
    return u.ok('GET', 'notifications?team=' + tid)['notifications']

def draft_doc(sid, name, date):
    return {'id': sid, 'name': name, 'date': date, 'items': [], 'version': 0, 'editedAt': int(time.time() * 1000)}

def f08():
    L = signup('하은'); t = team(L, 'F08'); tid = t['teamId']
    d1, d2, d3, d4 = day(10), day(17), day(12), day(19)
    # 인도자가 직접 연 날짜 (콘티를 옮겨 갈 곳)
    L.ok('POST', 'teams/%s/dates' % tid, {'date': d2, 'label': '수요예배'})
    sid = 'f08a' + tag
    # d1 에는 날짜가 없다 → 콘티 때문에 생긴 날짜(source=service)가 생긴다
    L.ok('PUT', 'services/%s/draft' % sid, {'teamId': tid, 'doc': draft_doc(sid, '특별예배', d1)})
    s = sched(L, tid)
    if not [x for x in s['dates'] if x['serviceId'] == sid and x['date'] == d1]: fail('F08 첫 저장에서 날짜가 안 붙음: %s' % s['dates'])
    # 날짜를 d2 로 옮긴다
    L.ok('PUT', 'services/%s/draft' % sid, {'teamId': tid, 'doc': draft_doc(sid, '특별예배', d2)})
    s = sched(L, tid)
    mine = [x for x in s['dates'] if x['serviceId'] == sid]
    if [x['date'] for x in mine] != [d2]: fail('F08 날짜를 옮겼는데 연결이 그대로: %s' % mine)
    if [x for x in s['dates'] if x['date'] == d1]: fail('F08 콘티 때문에 생긴 옛 날짜가 남음: %s' % s['dates'])
    # 자동 생성이 d2 에 빈 초안을 하나 더 만들면 안 된다
    before = {d['id'] for d in L.ok('GET', 'services?team=' + tid)['drafts']}
    if before != {sid}: fail('F08 날짜를 옮긴 뒤 초안이 더 생김: %s' % before)
    s = sched(L, tid)
    if len([x for x in s['dates'] if x['date'] == d2]) != 1: fail('F08 새 날짜에 줄이 둘: %s' % [x for x in s['dates'] if x['date'] == d2])

    # 정기·직접 연 날짜에서 옮기면: 그 날짜는 남되 연결만 풀리고, 자동 초안으로 다시 채우지 않는다 (콘티 삭제와 같게)
    L.ok('POST', 'teams/%s/dates' % tid, {'date': d3, 'label': '금요기도회'})
    sid2 = 'f08b' + tag
    L.ok('PUT', 'services/%s/draft' % sid2, {'teamId': tid, 'doc': draft_doc(sid2, '금요기도회', d3)})
    L.ok('PUT', 'services/%s/draft' % sid2, {'teamId': tid, 'doc': draft_doc(sid2, '금요기도회', d4)})
    s = sched(L, tid)
    r3 = [x for x in s['dates'] if x['date'] == d3]
    if len(r3) != 1 or r3[0]['serviceId']: fail('F08 직접 연 옛 날짜가 사라졌거나 연결이 남음: %s' % r3)
    if [x['date'] for x in s['dates'] if x['serviceId'] == sid2] != [d4]: fail('F08 두 번째 콘티 연결 이상: %s' % s['dates'])
    drafts = {d['id'] for d in L.ok('GET', 'services?team=' + tid)['drafts']}
    if drafts != {sid, sid2}: fail('F08 옮기고 난 옛 날짜에 자동 초안이 다시 생김: %s' % drafts)

    # 콘티 때문에 생긴 날짜에 짠 편성은 콘티를 따라간다. 날짜가 바뀌었으니 통보는 다시 해야 한다
    M = signup('민수'); join(M, t, ['드럼'])
    sid3 = 'f08c' + tag; d5, d6 = day(20), day(24)
    L.ok('PUT', 'services/%s/draft' % sid3, {'teamId': tid, 'doc': draft_doc(sid3, '청년예배', d5)})
    row = [x for x in sched(L, tid)['dates'] if x['serviceId'] == sid3][0]
    L.ok('PUT', 'teams/%s/dates/%s/lineup' % (tid, row['id']), {'lineup': [{'session': '드럼', 'memberId': M.id}]})
    L.ok('POST', 'teams/%s/dates/%s/notify' % (tid, row['id']))
    L.ok('PUT', 'services/%s/draft' % sid3, {'teamId': tid, 'doc': draft_doc(sid3, '청년예배', d6)})
    mv = [x for x in sched(L, tid)['dates'] if x['serviceId'] == sid3]
    if len(mv) != 1 or mv[0]['date'] != d6: fail('F08 편성 있는 날짜가 따라가지 않음: %s' % mv)
    if [r['memberId'] for r in mv[0]['lineup']] != [M.id]: fail('F08 옮기면서 편성이 사라짐: %s' % mv[0]['lineup'])
    if mv[0]['notified'] or any(r.get('notifiedAt') for r in mv[0]['lineup']): fail('F08 날짜가 바뀌었는데 통보함으로 남음: %s' % mv[0])
    n = L.ok('POST', 'teams/%s/dates/%s/notify' % (tid, mv[0]['id']))
    if n['sent'] != 1: fail('F08 옮긴 날짜로 다시 통보가 안 감: %s' % n)
    print('F08 ok')

def f09():
    L = signup('하은'); t = team(L, 'F09'); tid = t['teamId']
    d = day(9)
    L.ok('POST', 'teams/%s/dates' % tid, {'date': d, 'label': '성탄예배'})
    res = []
    def hit(): res.append(L.call('GET', 'services?team=' + tid)[0])
    ths = [threading.Thread(target=hit) for _ in range(5)]
    [x.start() for x in ths]; [x.join() for x in ths]
    if res != [200] * 5: fail('F09 동시 요청 실패: %s' % res)
    drafts = L.ok('GET', 'services?team=' + tid)['drafts']
    if len(drafts) != 1: fail('F09 자동 초안이 %d개 생김' % len(drafts))
    rows = [x for x in sched(L, tid)['dates'] if x['date'] == d]
    if len(rows) != 1 or rows[0]['serviceId'] != drafts[0]['id']: fail('F09 날짜 줄이 늘었거나 연결이 어긋남: %s' % rows)
    print('F09 ok')

def f11():
    st, j = U('x').call('POST', 'iap/webhook', {'event': {'type': 'TEST'}}, xconti=False)
    if st == 403: fail('F11 웹훅이 x-conti 검사에 막힘: %s' % j)
    if st not in (401, 503): fail('F11 인증 없는 웹훅이 통과함: %s %s' % (st, j))
    st, j = U('x').call('POST', 'auth/login', {'username': 'nobody', 'password': 'x'}, xconti=False)
    if st != 403: fail('F11 다른 쓰기 경로의 x-conti 검사가 풀림: %s' % st)
    print('F11 ok (%d)' % U('x').call('POST', 'iap/webhook', {}, xconti=False)[0])

def f55():
    L = signup('하은'); t = team(L, 'F55'); tid = t['teamId']
    M = signup('민수'); join(M, t, ['드럼'])
    d = day(30)
    L.ok('POST', 'teams/%s/dates' % tid, {'date': d, 'label': '주일 1부'})
    L.ok('POST', 'teams/%s/dates' % tid, {'date': d, 'label': '주일 2부'})
    rows = sorted([x for x in sched(L, tid)['dates'] if x['date'] == d], key=lambda x: x['label'])
    second = [x for x in rows if x['label'] == '주일 2부'][0]
    L.ok('PUT', 'teams/%s/dates/%s/lineup' % (tid, second['id']), {'lineup': [{'session': '드럼', 'memberId': M.id}]})
    M.ok('PUT', 'teams/%s/availability' % tid, {'date': d, 'state': 'no', 'memo': '출장'})
    c = [n for n in notis(L, tid) if n['type'] == 'avail.conflict']
    if len(c) != 1: fail('F55 2부 편성자가 불가능으로 바꿨는데 인도자 알림 %d개' % len(c))
    if c[0]['link'] != '#/lineup/' + second['id']: fail('F55 알림이 다른 예배를 가리킴: %s' % c[0]['link'])
    print('F55 ok')

def f56():
    L = signup('하은'); t = team(L, 'F56'); tid = t['teamId']
    X = signup('외부인'); team(X, 'F56 남의팀')
    d = day(31)
    row = L.ok('POST', 'teams/%s/dates' % tid, {'date': d, 'label': '주일예배'})['date']
    j = L.ok('PUT', 'teams/%s/dates/%s/lineup' % (tid, row['id']), {'lineup': [{'session': '드럼', 'memberId': X.id}]})
    if any(r['memberId'] for r in j['lineup']): fail('F56 팀 밖 사람이 편성에 저장됨: %s' % j['lineup'])
    n = L.ok('POST', 'teams/%s/dates/%s/notify' % (tid, row['id']))
    if n['sent'] != 0: fail('F56 팀 밖 사람에게 통보됨: %s' % n)
    print('F56 ok')

def f57():
    L = signup('하은'); t = team(L, 'F57'); tid = t['teamId']
    M = signup('민수'); join(M, t, ['드럼', '베이스'])
    row = L.ok('POST', 'teams/%s/dates' % tid, {'date': day(32), 'label': '주일 2부'})['date']
    did = row['id']
    def put(lineup): return L.ok('PUT', 'teams/%s/dates/%s/lineup' % (tid, did), {'lineup': lineup})
    def ntf(): return L.ok('POST', 'teams/%s/dates/%s/notify' % (tid, did))
    def last(): return [n for n in notis(M, tid) if n['type'] in ('lineup.notify', 'lineup.changed')][0]
    put([{'session': '드럼', 'memberId': M.id}])
    if ntf()['sent'] != 1: fail('F57 첫 통보 실패')
    j = put([{'session': '베이스', 'memberId': M.id}])
    if not j['changed']: fail('F57 세션 이동이 변경으로 안 잡힘')
    n = ntf()
    if n['sent'] != 1: fail('F57 세션만 바뀐 변경 통보가 안 감: %s' % n)
    if '베이스' not in last()['title']: fail('F57 변경 통보에 새 세션이 없음: %s' % last()['title'])
    first = [n for n in notis(M, tid) if n['type'] == 'lineup.notify'][0]
    if not first['ackAt']: fail("F57 옛 '드럼으로 섭니다' 카드가 할 일로 남음: %s" % first)
    if ntf()['sent'] != 0: fail('F57 바뀐 것이 없는데 또 보냄')
    # 겸임에서 세션 하나를 빼도 변경이다
    put([{'session': '드럼', 'memberId': M.id}, {'session': '베이스', 'memberId': M.id}])
    if ntf()['sent'] != 1: fail('F57 세션 추가 통보 안 감')
    j = put([{'session': '드럼', 'memberId': M.id}])
    if any(r['notifiedAt'] for r in j['lineup']): fail('F57 세션이 줄었는데 통보함으로 남음: %s' % j['lineup'])
    if ntf()['sent'] != 1: fail('F57 세션을 뺀 변경 통보가 안 감')
    t2 = last()['title']
    if '드럼' not in t2 or '베이스' in t2: fail('F57 세션 뺀 통보 문구 이상: %s' % t2)
    print('F57 ok')
    return L, M, tid, did

def f58():
    L = signup('하은'); t = team(L, 'F58'); tid = t['teamId']
    A = signup_named('지운이'); join(A, t, ['드럼'])
    B = signup('새드러머'); join(B, t, ['드럼'])
    row = L.ok('POST', 'teams/%s/dates' % tid, {'date': day(33), 'label': '주일예배'})['date']
    did = row['id']
    L.ok('PUT', 'teams/%s/dates/%s/lineup' % (tid, did), {'lineup': [{'session': '드럼', 'memberId': A.id}]})
    L.ok('POST', 'teams/%s/dates/%s/notify' % (tid, did))
    A.ok('POST', 'auth/delete', {'username': A_username[A.id], 'password': 'secret1'})
    s = [x for x in sched(L, tid)['dates'] if x['id'] == did][0]
    if any(r['memberId'] == A.id for r in s['lineup']): fail('F58 지운 계정이 앞으로의 편성에 남음: %s' % s['lineup'])
    L.ok('PUT', 'teams/%s/dates/%s/lineup' % (tid, did), {'lineup': [{'session': '드럼', 'memberId': B.id}]})
    st, j = L.call('POST', 'teams/%s/dates/%s/notify' % (tid, did))
    if st != 200: fail('F58 지운 계정 때문에 통보 실패: %s %s' % (st, j))
    if j['sent'] != 1: fail('F58 새 사람에게만 가야 함: %s' % j)
    st, j = L.call('POST', 'teams/%s/dates/%s/notify' % (tid, did))
    if st != 200 or j['sent'] != 0: fail('F58 다시 누르면 또 보냄: %s %s' % (st, j))
    print('F58 ok')

def g12():
    L = signup('하은'); t = team(L, 'G12'); tid = t['teamId']
    M = signup('민수'); join(M, t, ['일렉'])
    P = signup('목사님')
    inv = L.ok('POST', 'teams/%s/invites' % tid, {'role': 'pastor'})['invite']
    P.ok('POST', 'invite/%s/join' % inv['code'], {'name': '목사님'})
    d = day(11)
    row = L.ok('POST', 'teams/%s/dates' % tid, {'date': d, 'label': '수요예배'})['date']
    drafts = L.ok('GET', 'services?team=' + tid)['drafts']   # 자동 초안이 붙는다 (발행 전)
    s = [x for x in sched(L, tid)['dates'] if x['id'] == row['id']][0]
    if not s['serviceId']: fail('G12 자동 초안이 안 붙음: %s %s' % (s, drafts))
    L.ok('PUT', 'teams/%s/dates/%s/lineup' % (tid, row['id']), {'lineup': [{'session': '일렉', 'memberId': M.id}]})
    L.ok('POST', 'teams/%s/dates/%s/notify' % (tid, row['id']))
    n = [x for x in notis(M, tid) if x['type'] == 'lineup.notify'][0]
    if n['link'].startswith('#/view/'): fail('G12 발행 전 초안을 가리킴: %s' % n['link'])
    if n['link'] != '#/sched/' + d[:7]: fail('G12 편성 화면(그 달)으로 가야 함: %s' % n['link'])
    st, _ = M.call('GET', 'services/%s?team=%s' % (s['serviceId'], tid))
    if st != 404: fail('G12 전제: 멤버는 발행 전 초안을 못 봄 (%s)' % st)
    # 발행하고 나면 콘티로 간다
    doc = draft_doc(s['serviceId'], '수요예배', d); doc['version'] = 1
    L.ok('PUT', 'services/%s' % s['serviceId'], {'teamId': tid, 'doc': doc})
    L.ok('PUT', 'teams/%s/dates/%s/lineup' % (tid, row['id']), {'lineup': [{'session': '건반', 'memberId': M.id}]})
    L.ok('POST', 'teams/%s/dates/%s/notify' % (tid, row['id']))
    n = [x for x in notis(M, tid) if x['type'] == 'lineup.changed'][0]
    if n['link'] != '#/view/' + s['serviceId']: fail('G12 발행 뒤에는 콘티로 가야 함: %s' % n['link'])
    # 목회자에게 가는 '쉽니다'는 홈으로 (목회자는 달력에서 아무것도 못 누른다)
    row2 = L.ok('POST', 'teams/%s/dates' % tid, {'date': day(40), 'label': '금요기도회'})['date']
    L.ok('PATCH', 'teams/%s/dates/%s' % (tid, row2['id']), {'open': False})
    pc = [x for x in notis(P, tid) if x['type'] == 'date.closed']
    mc = [x for x in notis(M, tid) if x['type'] == 'date.closed']
    if len(pc) != 1 or pc[0]['link'] != '#/home': fail('G12 목회자 쉽니다 알림 링크: %s' % pc)
    if len(mc) != 1 or mc[0]['link'] != '#/cal': fail('G12 멤버 쉽니다 알림 링크: %s' % mc)
    print('G12 ok')

def f120():
    L = signup('하은'); t = team(L, 'F120'); tid = t['teamId']
    wd = (KST_TODAY.isoweekday()) % 7           # 오늘(한국) 요일, 일=0
    L.ok('POST', 'teams/%s/recurring' % tid, {'weekday': wd, 'label': '오늘예배', 'time': '19:00'})
    yd = (wd + 6) % 7                            # 어제(한국) 요일
    L.ok('POST', 'teams/%s/recurring' % tid, {'weekday': yd, 'label': '어제예배', 'time': '19:00'})
    rows = [x for x in sched(L, tid)['dates'] if x['label'] in ('오늘예배', '어제예배')]
    for x in rows:
        dt = datetime.date.fromisoformat(x['date'])
        if x['date'] < KST_TODAY.isoformat(): fail('F120 한국 날짜로 지난 날이 들어감: %s' % x)
        want = wd if x['label'] == '오늘예배' else yd
        if dt.isoweekday() % 7 != want: fail('F120 요일이 어긋남: %s (%s)' % (x, dt.strftime('%a')))
    if KST_TODAY.isoformat() not in [x['date'] for x in rows if x['label'] == '오늘예배']: fail('F120 오늘 예배가 빠짐: %s' % rows)
    # 한국 날짜로 어제인 열린 날짜에는 자동 초안을 만들지 않는다
    L.ok('POST', 'teams/%s/dates' % tid, {'date': day(-1), 'label': '지난예배'})
    L.ok('GET', 'services?team=' + tid)
    s = [x for x in sched(L, tid)['dates'] if x['date'] == day(-1)]
    if s and s[0]['serviceId']: fail('F120 한국 날짜로 어제인 예배에 초안이 생김: %s' % s)
    print('F120 ok')

def f121():
    L = signup('하은'); t = team(L, 'F121'); tid = t['teamId']
    M = signup('민수'); join(M, t, ['드럼'])
    N = signup('지수'); join(N, t, ['베이스'])
    nm = (KST_TODAY.replace(day=1) + datetime.timedelta(days=32)).replace(day=1)
    x, y, z = [(nm + datetime.timedelta(days=k)).isoformat() for k in (4, 11, 20)]
    for d, lb in ((x, '주일 1부'), (x, '주일 2부'), (y, '주일 1부')):
        L.ok('POST', 'teams/%s/dates' % tid, {'date': d, 'label': lb})
    # 민수: 두 날짜 모두 답함 → 미선택 0 / 지수: x 하나 + 사역일이 아닌 z 에 답함 → 미선택 1
    for d in (x, y): M.ok('PUT', 'teams/%s/availability' % tid, {'date': d, 'state': 'ok'})
    for d in (x, z): N.ok('PUT', 'teams/%s/availability' % tid, {'date': d, 'state': 'ok'})
    month = x[:7]
    L.ok('POST', 'notifications/ask', {'teamId': tid, 'userId': M.id, 'month': month})
    L.ok('POST', 'notifications/ask', {'teamId': tid, 'userId': N.id, 'month': month})
    bm = [n for n in notis(M, tid) if n['type'] == 'avail.request'][0]['body']
    bn = [n for n in notis(N, tid) if n['type'] == 'avail.request'][0]['body']
    if bm != '사역일 2일 · 아직 미선택 0일': fail('F121 다시 요청 수 이상 (민수): %s' % bm)
    if bn != '사역일 2일 · 아직 미선택 1일': fail('F121 다시 요청 수 이상 (지수): %s' % bn)
    print('F121 ask ok')

def cron_checks():
    if not CRON:
        print('F121/F122 크론 SKIP — CRON_SECRET 없음'); return
    auth = {'authorization': 'Bearer ' + CRON}
    # 월간 요청은 reminderDay(20~28 로만 둘 수 있다)에만 간다. 오늘(한국)이 그 범위면 오늘로 맞춰 시험한다
    today_d = KST_TODAY.day
    if 20 <= today_d <= 28:
        L = signup('하은'); t = team(L, 'F121C'); tid = t['teamId']
        P = signup('민수'); join(P, t, ['드럼'])
        Q = signup('지수'); join(Q, t, ['베이스'])
        nm = (KST_TODAY.replace(day=1) + datetime.timedelta(days=32)).replace(day=1)
        x, y, z = [(nm + datetime.timedelta(days=k)).isoformat() for k in (4, 11, 20)]
        for d, lb in ((x, '주일 1부'), (x, '주일 2부'), (y, '주일 1부')):
            L.ok('POST', 'teams/%s/dates' % tid, {'date': d, 'label': lb})
        for d in (x, y): P.ok('PUT', 'teams/%s/availability' % tid, {'date': d, 'state': 'ok'})
        Q.ok('PUT', 'teams/%s/availability' % tid, {'date': z, 'state': 'ok'})   # 사역일이 아닌 날의 답
        L.ok('PATCH', 'teams/%s/settings' % tid, {'reminderDay': today_d, 'reminderMonthsAhead': 1})
        st, j = U('c').call('GET', 'cron/remind', headers=auth)
        if st != 200: fail('F122 remind 크론 실패: %s %s' % (st, j))
        bp = [n for n in notis(P, tid) if n['type'] == 'avail.request']
        bq = [n for n in notis(Q, tid) if n['type'] == 'avail.request']
        if bp: fail('F121 두 날짜 다 답한 사람에게 월간 요청이 감: %s' % bp[0]['body'])
        if len(bq) != 1 or bq[0]['body'] != '사역일 2일 · 아직 미선택 2일': fail('F121 월간 요청 수 이상: %s' % [n['body'] for n in bq])
        print('F121 cron ok')
    else:
        print('F121 cron SKIP — 오늘은 reminderDay 로 둘 수 없는 날')
    # F122: 크론 dates 가 팀을 동시에 돌려도 한 팀에 날짜·초안이 겹치지 않는다
    L2 = signup('하은'); t = team(L2, 'F122'); tid2 = t['teamId']
    L2.ok('POST', 'teams/%s/recurring' % tid2, {'weekday': (KST_TODAY.isoweekday() + 3) % 7, 'label': '크론예배'})
    res = []
    def hit(): res.append(U('c').call('GET', 'cron/dates', headers=auth))
    ths = [threading.Thread(target=hit) for _ in range(2)]
    [x.start() for x in ths]; [x.join() for x in ths]
    for st, j in res:
        if st != 200: fail('F122 dates 크론 실패: %s %s' % (st, j))
        for k in ('recurring', 'created', 'purged', 'warned', 'dropped', 'teamsDropped'):
            if k not in j: fail('F122 크론 결과에 %s 가 없음: %s' % (k, j))
    rows = [x for x in sched(L2, tid2)['dates'] if x['label'] == '크론예배']
    if len(rows) < 12 or len(rows) != len({x['date'] for x in rows}): fail('F122 정기 예배 날짜 이상: %d' % len(rows))
    drafts = L2.ok('GET', 'services?team=' + tid2)['drafts']
    linked = [x['serviceId'] for x in rows if x['serviceId']]
    if len(drafts) != len(linked) or len(set(linked)) != len(linked): fail('F122 초안·연결 수가 어긋남: %d vs %s' % (len(drafts), linked))
    print('F122 ok (%s)' % res[0][1])

def f54_and_ui():
    # 두 팀에 속한 사람: 지금 팀 A 를 보고 있다가 팀 B 알림을 누른다
    with sync_playwright() as p:
        b = p.chromium.launch(); errs = []
        c = b.new_context(viewport={'width': 1100, 'height': 860}); pg = c.new_page()
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('dialog', lambda d: d.accept())
        # 팀 B (다른 인도자가 만들고 발행) — API 로
        LB = signup('다른인도자'); tB = team(LB, 'F54B'); tidB = tB['teamId']
        sidB = 'f54b' + tag
        doc = draft_doc(sidB, 'B팀 주일예배', day(6)); doc['version'] = 1
        doc['items'] = [{'id': 'i1', 'title': 'B팀찬양', 'key': 'G', 'pieces': []}]
        LB.ok('PUT', 'services/%s' % sidB, {'teamId': tidB, 'doc': doc})
        # 사용자: 화면에서 가입·팀 A 만들기
        un = 'aq%s%02d' % (tag, next(_n))
        pg.goto(URL); pg.wait_for_selector('#lgUser', timeout=10000)
        pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName')
        pg.check('#lgAgree'); pg.fill('#lgName', '두팀'); pg.fill('#lgUser', un); pg.fill('#lgPass', 'secret1'); pg.click('[data-act="lg-submit"]')
        pg.wait_for_selector('#gtTeam', timeout=10000); pg.fill('#gtTeam', 'F54A ' + tag); pg.click('[data-act="team-create"]'); pg.wait_for_selector('.shell[data-page]', timeout=10000)
        tidA = pg.evaluate('CONTI.S.team.id')
        r = c.request.post(URL + 'api/invite/%s/join' % tB['invite'], headers={'x-conti': '1'}, data={'name': '두팀', 'sessions': ['드럼']})
        if r.status != 200: fail('F54 팀 B 가입 실패: %s' % r.text()[:100])
        # 다시 열어 팀 목록(팀 B 포함)을 받는다. 보고 있는 팀은 그대로 A
        pg.goto(URL + '#/home'); pg.reload(); pg.wait_for_selector('.shell[data-page]', timeout=10000)
        if pg.evaluate('CONTI.S.team.id') != tidA: fail('F54 전제: 팀 A 에 있어야 함')
        # (1) 이미 열린 창: sw 가 보내는 메시지를 흉내 낸다
        ack = pg.evaluate("""([link,team])=>new Promise(res=>{const ch=new MessageChannel();ch.port1.onmessage=()=>res(true);setTimeout(()=>res(false),4000);
          navigator.serviceWorker.dispatchEvent(new MessageEvent('message',{data:{type:'push-open',link,teamId:team},ports:[ch.port2]}))})""", ['#/view/' + sidB, tidB])
        if not ack: fail('F54 화면이 sw 메시지에 답하지 않음')
        pg.wait_for_function('window.CONTI && CONTI.S.team.id===%s' % json.dumps(tidB), timeout=10000)
        pg.wait_for_function("location.hash.replace(/^#\\/?/,'')==='view/%s'" % sidB, timeout=10000)
        pg.wait_for_function("document.querySelector('#app').innerText.includes('B팀찬양')", timeout=15000)
        print('F54 message ok')
        # (2) 새 창: 주소의 ?team= 으로 연다 (먼저 같은 방법으로 팀 A 로 되돌려 둔다)
        pg.goto(URL + '?team=' + tidA + '#/home'); pg.wait_for_selector('.shell[data-page]', timeout=10000)
        pg.wait_for_function('window.CONTI && CONTI.S.team.id===%s' % json.dumps(tidA), timeout=10000)
        if '?team=' in pg.url: fail('F54 주소에 ?team= 이 남음: ' + pg.url)
        pg.goto(URL + '?team=' + tidB + '#/view/' + sidB)
        pg.wait_for_function('window.CONTI && CONTI.S.team.id===%s' % json.dumps(tidB), timeout=15000)
        pg.wait_for_function("document.querySelector('#app').innerText.includes('B팀찬양')", timeout=15000)
        if not pg.url.endswith('#/view/' + sidB) or '?team=' in pg.url: fail('F54 새 창 주소 이상: ' + pg.url)
        print('F54 url ok')
        if errs: fail('F54 page errors: %s' % errs)
        b.close()

def f57_ui(L, M, tid, did):
    # 인도자 화면: 세션만 바꿔도 '변경 통보' 버튼이 켜진다
    with sync_playwright() as p:
        b = p.chromium.launch(); c = b.new_context(viewport={'width': 1240, 'height': 900}); pg = c.new_page()
        pg.on('dialog', lambda d: d.accept())
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        # L 의 세션 쿠키를 브라우저로 옮긴다
        jar = [h for h in L.op.handlers if isinstance(h, urllib.request.HTTPCookieProcessor)][0].cookiejar
        c.add_cookies([{'name': k.name, 'value': k.value, 'url': URL} for k in jar])
        L.ok('PUT', 'teams/%s/dates/%s/lineup' % (tid, did), {'lineup': [{'session': '드럼', 'memberId': M.id}]})
        L.ok('POST', 'teams/%s/dates/%s/notify' % (tid, did))
        L.ok('PUT', 'teams/%s/dates/%s/lineup' % (tid, did), {'lineup': [{'session': '베이스', 'memberId': M.id}]})
        # F09: 켤 때 부팅과 홈 그리기가 발행본 목록을 따로 받으면 같은 초안이 두 번 들어간다 → 한 번만 받는다
        pulls = []
        pg.on('request', lambda r: pulls.append(r.url) if '/api/services?team=' in r.url else None)
        pg.goto(URL + '#/home'); pg.wait_for_selector('.shell[data-page]', timeout=10000)
        pg.wait_for_timeout(2500)
        if len(pulls) != 1: fail('F09 켤 때 발행본 목록을 %d번 받음' % len(pulls))
        if pg.evaluate('CONTI.S.team.id') != tid: fail('F57 ui 전제: 인도자 팀이 아님')
        ids = pg.evaluate('CONTI.S.services.map(s=>s.id)')
        if len(ids) != len(set(ids)): fail('F09 같은 콘티가 두 번 들어감: %s' % ids)
        pg.goto(URL + '#/lineup/' + did); pg.wait_for_selector('[data-act="lnotify"]', timeout=15000)
        btn = pg.locator('[data-act="lnotify"]')
        if btn.is_disabled(): fail('F57 세션만 바뀌었는데 변경 통보 버튼이 꺼져 있음')
        if '통보 후 변경 있음' not in pg.locator('.lnft').inner_text(): fail('F57 변경 있음 표시가 없음')
        btn.click(); pg.wait_for_timeout(1500)
        if not pg.locator('[data-act="lnotify"]').is_disabled(): fail('F57 통보 뒤에도 버튼이 켜져 있음')
        if errs: fail('F57 page errors: %s' % errs)
        b.close()
    print('F57 ui ok')

def run():
    f11()
    f08()
    f09()
    f55()
    f56()
    L, M, tid, did = f57()
    f58()
    g12()
    f120()
    f121()
    cron_checks()
    f54_and_ui()
    f57_ui(L, M, tid, did)
    print('AUDIT api-schedule-cron OK')

if __name__ == '__main__':
    run()
