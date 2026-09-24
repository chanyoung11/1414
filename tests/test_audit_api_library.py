# 감사 묶음 api-library 회귀 검사 (F06 F07 F44 F45 G11 F46 G04)
#  F06 기본 편곡을 한 번 고친 뒤 다른 편곡을 기본으로 바꾸면 500
#  F07 인도자 '이 곡에 항상' 메모의 대상 세션(드럼)이 버려져 모두에게 '전체'로 보임
#  F44 사용 날짜가 'Tue Sep 23'(연도 없음)으로 나가 '작년 이맘때'가 늘 비어 있음
#  F45 ♩= 에 72.5 를 넣으면 편곡 저장 전체가 500 (키·송폼까지 사라짐)
#  G11 8자보다 긴 마커 라벨의 고정 메모가 잘려 저장되어 어디에도 안 보임
#  F46 공유 코드 담기(take)에 틀린 시도 제한이 없음
#  G04 곡 목록이 since 여도 팀 전체를 읽고, 앱은 늘 통째로 받음 → 한꺼번에 열면 서버 메모리가 넘침
# 되돌려진 수정 바로잡기(r2)
#  F44·G04 배포 전에 받아 둔 기기의 옛 꼴 캐시(연도 없는 날짜)는 since 로는 안 고쳐짐 → 한 번 통째로 받는다 (SONGS_V)
#  G04 since=1·0·2026 처럼 JS 는 읽고 DB 는 못 읽는 값이 500
#  G11 8자 라벨 그대로인 마커('Bridge 1')의 새 메모가 앞이 같은 긴 마커('Bridge 12')에도 붙음
#  F46 틀린 시도를 읽고 나중에 더해, 한꺼번에 보내면 셈을 빠져나감 (300개 중 170여 개)
# 사용: CONTI_URL=http://localhost:8802/ .venv/bin/python tests/test_audit_api_library.py
import os, sys, time, datetime, random, json, urllib.request, urllib.error, concurrent.futures
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
tag = str(int(time.time() * 1000))[-8:]
H = {'x-conti': '1'}
PNG = bytes.fromhex('89504e470d0a1a0a0000000d4948445200000001000000010806000000'
                    '1f15c4890000000d49444154789c6360f8cf00000301010018dd8db40000000049454e44ae426082') + b'\0' * 400
def fail(m): print('FAIL:', m); sys.exit(1)

def call(rq, method, path, body=None, headers=None):
    r = rq.fetch(URL + 'api' + path, method=method, headers={**H, **(headers or {})},
                 data=body if body is not None else None)
    try: j = r.json()
    except Exception: j = None
    return r.status, j

def ok(rq, method, path, body=None):
    st, j = call(rq, method, path, body)
    if st != 200: fail('%s %s → %s %s' % (method, path, st, j))
    return j

def leader(b, name):
    c = b.new_context(viewport={'width': 1300, 'height': 950})
    ok(c.request, 'POST', '/auth/signup', {'username': name + tag, 'password': 'secret12', 'name': '리더'})
    t = ok(c.request, 'POST', '/teams', {'name': '감사팀' + name, 'myName': '리더'})
    return c, t['teamId']

def song_of(rq, tid, sid):
    return ok(rq, 'GET', '/songs/%s?team=%s' % (sid, tid))

def list_of(rq, tid, since=None):
    return ok(rq, 'GET', '/songs?team=%s%s' % (tid, '&since=' + since if since else ''))

def run():
  with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    c, tid = leader(b, 'lib')
    rq = c.request

    # ---------------- F06: 기본 편곡 바꾸기 ----------------
    s = ok(rq, 'POST', '/songs', {'teamId': tid, 'title': '기본 바꾸기', 'key': 'G', 'form': 'A B'})['song']
    sid, aA = s['id'], s['arrangements'][0]['id']
    aB = ok(rq, 'POST', '/songs/%s/arrangements' % sid, {'teamId': tid, 'fromId': aA, 'key': 'A', 'name': 'A키'})['arrangement']['id']
    order = [(aA, aB), (aB, aA), (aA, aB), (aB, aA)]
    for i, (cur, nxt) in enumerate(order):
        ok(rq, 'PATCH', '/arrangements/' + cur, {'teamId': tid, 'songNote': '고침 %d' % i})   # 지금 기본을 먼저 고친다
        st, j = call(rq, 'PATCH', '/arrangements/' + nxt, {'teamId': tid, 'isDefault': True, 'key': 'Bb'})
        if st != 200: fail('F06: 기본 편곡 바꾸기 %d번째가 %s %s' % (i + 1, st, j))
        arrs = song_of(rq, tid, sid)['song']['arrangements']
        defs = [a['id'] for a in arrs if a['isDefault']]
        if defs != [nxt]: fail('F06: 기본이 %s 여야 하는데 %s' % (nxt, defs))
    print('F06 ok: 기본 편곡을 고친 뒤에도 네 번 바꿔 모두 200, 기본은 늘 하나')

    # ---------------- F07: 대상 세션이 있는 인도자 고정 메모 ----------------
    n = ok(rq, 'POST', '/arrangements/%s/notes' % aA, {'teamId': tid, 'markerLabel': 'B', 'layer': 'all', 'session': '드럼', 'text': '쉬기'})['note']
    if n['session'] != '드럼': fail('F07: 대상 세션이 버려짐: %s' % n)
    n2 = ok(rq, 'POST', '/arrangements/%s/notes' % aA, {'teamId': tid, 'markerLabel': 'B', 'layer': 'all', 'text': '다 같이'})['note']
    if n2['session'] is not None: fail('F07: 대상 없는 메모에 세션이 붙음: %s' % n2)
    st, j = call(rq, 'POST', '/arrangements/%s/notes' % aA, {'teamId': tid, 'markerLabel': 'B', 'layer': 'all', 'session': '없는세션', 'text': 'x'})
    if st != 400: fail('F07: 팀에 없는 세션을 받음: %s %s' % (st, j))
    got = {x['text']: x['session'] for a in list_of(rq, tid)['songs'][0]['arrangements'] for x in a['notes']}
    if got.get('쉬기') != '드럼' or got.get('다 같이') is not None: fail('F07: 목록에서 대상이 이상함 %s' % got)
    print('F07 ok: 인도자 메모 대상 드럼이 저장되고 목록에도 드럼으로 온다')

    # ---------------- G11: 긴 마커 라벨 ----------------
    n3 = ok(rq, 'POST', '/arrangements/%s/notes' % aA, {'teamId': tid, 'markerLabel': 'Pre-Chorus', 'layer': 'all', 'text': '빌드업'})['note']
    if n3['markerLabel'] != 'Pre-Chorus': fail('G11: 라벨이 잘림: %r' % n3['markerLabel'])
    st, j = call(rq, 'POST', '/arrangements/%s/notes' % aA, {'teamId': tid, 'markerLabel': 'X' * 41, 'layer': 'all', 'text': 'x'})
    if st != 400: fail('G11: 너무 긴 라벨을 잘라서 받음: %s %s' % (st, j))
    print('G11 ok: Pre-Chorus 그대로 저장, 41자는 거절')

    # ---------------- F45: ♩= 소수·큰 수 ----------------
    st, j = call(rq, 'PATCH', '/arrangements/' + aB, {'teamId': tid, 'bpm': 72.5, 'key': 'C', 'form': 'V C B', 'songNote': '느리게'})
    if st != 200: fail('F45: bpm 72.5 저장이 %s %s' % (st, j))
    a = [x for x in song_of(rq, tid, sid)['song']['arrangements'] if x['id'] == aB][0]
    if a['bpm'] != 73 or a['key'] != 'C' or a['form'] != 'V C B': fail('F45: 저장된 값이 이상함 %s' % {k: a[k] for k in ('bpm', 'key', 'form')})
    for v, want in ((3000000000, 400), ('abc', None), (-5, None), (8, 20)):
        st, j = call(rq, 'PATCH', '/arrangements/' + aB, {'teamId': tid, 'bpm': v})
        if st != 200: fail('F45: bpm %r → %s %s' % (v, st, j))
        got_bpm = [x for x in song_of(rq, tid, sid)['song']['arrangements'] if x['id'] == aB][0]['bpm']
        if got_bpm != want: fail('F45: bpm %r → %r (기대 %r)' % (v, got_bpm, want))
    tk = ok(rq, 'POST', '/share/take', {'teamId': tid, 'payload': {'v': 1, 'songs': [{'title': '받은 곡', 'arr': {'bpm': 88.4, 'key': 'D',
          'notes': [{'label': 'B', 'text': '드럼만', 'session': '드럼'}, {'label': 'C', 'text': '베이스만', 'session': '없는세션'}]}}]}})
    ts = song_of(rq, tid, tk['songs'][0]['songId'])
    if ts['song']['arrangements'][0]['bpm'] != 88: fail('F45: 코드로 받은 bpm %s' % ts['song']['arrangements'][0]['bpm'])
    tn = {x['text']: x['session'] for x in ts['notes']}
    if tn.get('드럼만') != '드럼' or tn.get('없는세션 · 베이스만', 'x') is not None: fail('F07: 코드로 받은 메모의 대상이 이상함 %s' % tn)
    print('F45 ok: 72.5→73, 30억→400, 이상한 값→비움, 코드로 받기도 같음 (메모 대상도 따라옴)')

    # ---------------- F44: 사용 날짜 ----------------
    today = datetime.date.today()
    try: last_year = today.replace(year=today.year - 1)
    except ValueError: last_year = today.replace(year=today.year - 1, day=28)
    ly = last_year.isoformat()
    svc = 'svc' + tag
    ok(rq, 'PUT', '/services/' + svc, {'teamId': tid, 'doc': {'id': svc, 'version': 1, 'name': '작년 예배', 'date': ly,
        'items': [{'id': 'i1', 'songId': sid, 'arrId': aA, 'key': 'G', 'title': '기본 바꾸기'}]}})
    row = [x for x in list_of(rq, tid)['songs'] if x['id'] == sid][0]
    if row.get('usedDates') != [ly]: fail('F44: usedDates 가 %r (기대 [%r])' % (row.get('usedDates'), ly))
    if row.get('lastUsed') != ly or row.get('firstUsed') != ly: fail('F44: lastUsed/firstUsed %r %r' % (row.get('lastUsed'), row.get('firstUsed')))
    d = song_of(rq, tid, sid)
    if d['usages'][0]['serviceDate'] != ly: fail('F44: 사용 이력 날짜 %r' % d['usages'][0]['serviceDate'])
    print('F44 ok: usedDates/lastUsed = %s' % ly)

    # ---------------- 화면: 작년 이맘때 · 대상 표시 · 라벨 칸 · 잘린 옛 라벨 · ♩= 저장 ----------------
    pg = c.new_page()
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('dialog', lambda dl: dl.accept())
    pg.goto(URL); pg.wait_for_selector('.shell[data-page]', timeout=10000)
    pg.goto(URL + '#/library'); pg.wait_for_selector('.libpage', timeout=10000); pg.wait_for_timeout(1200)
    if '작년 이맘때' not in pg.locator('.libpage').inner_text(): fail('F44: 라이브러리에 작년 이맘때가 안 보임')
    pg.goto(URL + '#/library/' + sid); pg.wait_for_selector('[data-tab="notes"]', timeout=10000)
    pg.click('[data-tab="notes"]'); pg.wait_for_timeout(500)
    tags = pg.locator('.mrow .tag').all_inner_texts()
    if '드럼' not in tags: fail('F07: 메모 탭에서 대상이 안 보임 %s' % tags)
    vis = pg.evaluate('''(n)=>{const it={fixedNotes:[n],pieces:[{markers:[{id:'m1',label:'B'}]}]};
      const ctx=s=>({mode:'play',session:s,f:{leader:true,session:true,mine:true}});
      return [CONTI.fixedNotesOf(it,'m1',ctx('드럼')).length, CONTI.fixedNotesOf(it,'m1',ctx('싱어')).length]}''', n)
    if vis != [1, 0]: fail('F07: 드럼에게만 보여야 하는데 %s' % vis)
    lab = pg.evaluate('''()=>{const it=l=>({fixedNotes:[{id:'n',markerLabel:l,layer:'all',text:'t'}],pieces:[{markers:[{id:'m',label:'Pre-Chorus'},{id:'k',label:'A1'}]}]});
      return [CONTI.fixedNotesOf(it('Pre-Chor'),'m').length, CONTI.fixedNotesOf(it('Pre-Chorus'),'m').length,
              CONTI.fixedNotesOf(it('Pre-C'),'m').length, CONTI.fixedNotesOf(it('A'),'k').length]}''')
    if lab != [1, 1, 0, 0]: fail('G11: 라벨 맞추기 %s (기대 [1,1,0,0])' % lab)
    if 'id="customLabel" placeholder="직접 입력 (A1, B2…)" maxlength="40"' not in pg.content(): fail('G11: 라벨 입력칸에 길이 제한이 없음')
    pg.click('[data-tab="arr"]'); pg.wait_for_timeout(300)
    pg.click('[data-arredit="%s"]' % aB); pg.wait_for_selector('#aeBpm', timeout=5000)
    pg.fill('#aeBpm', '96.6'); pg.fill('#aeKey', 'E'); pg.click('#aeOk'); pg.wait_for_timeout(1500)
    a = [x for x in song_of(rq, tid, sid)['song']['arrangements'] if x['id'] == aB][0]
    if a['bpm'] != 97 or a['key'] != 'E': fail('F45: 화면에서 저장한 값이 서버에 없음 %s %s' % (a['bpm'], a['key']))
    if pg.evaluate('!!CONTI.S.songs.find(s=>s.id==="%s").dirty' % sid): fail('F45: 저장한 뒤에도 곡이 dirty')
    print('UI ok: 작년 이맘때 보임 · 메모 탭에 드럼 · 드럼만 보임 · 잘린 옛 라벨 복구 · 라벨 40자 · ♩=96.6→97')

    # ---------------- G11 (r2): 8자 라벨 그대로인 마커가 있으면 그 마커에만 ----------------
    lab2 = pg.evaluate('''()=>{const it=(l,ms)=>({fixedNotes:[{id:'n',markerLabel:l,layer:'all',text:'t'}],
        pieces:[{markers:ms.slice(0,1).map((x)=>({id:'m0',label:x}))},{markers:ms.slice(1).map((x,i)=>({id:'m'+(i+1),label:x}))}]});
      const B=['Bridge 1','Bridge 12','Bridge 1 (반복)'];
      return [CONTI.fixedNotesOf(it('Bridge 1',B),'m0').length, CONTI.fixedNotesOf(it('Bridge 1',B),'m1').length,
              CONTI.fixedNotesOf(it('Bridge 1',B),'m2').length, CONTI.fixedNotesOf(it('Pre-Chor',['Pre-Chorus']),'m0').length,
              CONTI.fixedNotesOf(it('Pre-Chor',['Pre-Chor','Pre-Chorus']),'m0').length, CONTI.fixedNotesOf(it('Pre-Chor',['Pre-Chor','Pre-Chorus']),'m1').length]}''')
    if lab2 != [1, 0, 0, 1, 1, 0]: fail('G11: 8자 라벨 마커의 메모가 긴 마커에도 붙음 %s (기대 [1,0,0,1,1,0])' % lab2)
    print('G11 ok: Bridge 1 메모는 Bridge 12 에 안 붙고, 잘린 옛 Pre-Chor 는 같은 라벨 마커가 없을 때만 Pre-Chorus 에')

    # ---------------- F44·G04 (r2): 배포 전에 받아 둔 기기 — 옛 꼴 캐시는 한 번 통째로 받는다 ----------------
    # 옛 서버가 준 꼴(연도 없는 날짜·시각이 붙은 lastUsed)로 캐시를 되돌리고, 그 뒤로 바뀐 것이 없게 songsAt 을 지금으로 둔다.
    # 옛 앱은 SONGS_V 를 몰랐다 → 지운다
    pg.goto(URL + '#/library'); pg.wait_for_selector('.libpage', timeout=10000); pg.wait_for_timeout(800)
    pg.evaluate('''async()=>{for(const s of CONTI.S.songs){if((s.usedDates||[]).length){
        s.usedDates=s.usedDates.map(d=>new Date(d+'T00:00:00').toDateString().slice(0,10));
        s.lastUsed=new Date(s.lastUsed+'T00:00:00+09:00').toISOString();s.firstUsed=s.lastUsed}}
      CONTI.S.songsAt=new Date().toISOString();delete CONTI.S.songsV;await CONTI.save()}''')
    pg.wait_for_timeout(1500)
    old = pg.evaluate('''async(id)=>{const raw=await CONTI.IDB.get('kv',await CONTI.IDB.get('kv','scope'));const s=JSON.parse(raw);
      return [s.songsV===undefined, (s.songs.find(x=>x.id===id)||{}).usedDates]}''', sid)
    if not old[0] or not old[1] or old[1][0] == ly: fail('F44: 옛 꼴 캐시를 만들지 못함 %s' % old)
    sreq = []
    pg.on('request', lambda r: sreq.append(r.url) if '/api/songs?' in r.url else None)
    pg.reload(); pg.wait_for_selector('.libpage', timeout=10000)
    pg.wait_for_function('CONTI.S.songsV===2', timeout=10000); pg.wait_for_timeout(1200)
    if not sreq or 'since=' in sreq[0]: fail('F44: 옛 꼴 캐시인데 통째로 안 받음 %s' % sreq)
    got = pg.evaluate('(id)=>{const s=CONTI.S.songs.find(x=>x.id===id);return [s.usedDates,s.lastUsed]}', sid)
    if got != [[ly], ly]: fail('F44: 다시 연 뒤에도 옛 날짜 %s' % got)
    if '작년 이맘때' not in pg.locator('.libpage').inner_text(): fail('F44: 옛 캐시 기기에서 작년 이맘때가 안 보임')
    sreq.clear(); pg.reload(); pg.wait_for_selector('.libpage', timeout=10000); pg.wait_for_timeout(2000)
    if not sreq or any('since=' not in u for u in sreq): fail('F44: 한 번 통째로 받은 뒤에도 또 통째로 받음 %s' % sreq)
    print('F44 ok: 옛 꼴 캐시는 한 번 통째로 받아 작년 이맘때가 보이고, 그 뒤로는 since')

    # ---------------- G04: since 는 바뀐 곡만, 통계·새 편곡·세션 이름도 since 로 ----------------
    c2, t2 = leader(b, 'syn')
    r2 = c2.request
    ids = []
    for i in range(3):
        bid = 'bl%s%d' % (tag, i)
        r = r2.fetch(URL + 'api/blobs/%s?team=%s' % (bid, t2), method='POST', headers={**H, 'content-type': 'image/png'}, data=PNG)
        if r.status != 200: fail('파일 올리기 %s' % r.status)
        so = ok(r2, 'POST', '/songs', {'teamId': t2, 'title': '곡%d' % i, 'key': 'G',
             'pieces': [{'id': 'p%d' % i, 'blob': bid, 'w': 10, 'h': 10, 'markers': [], 'hls': [], 'chords': []}]})['song']
        ids.append((so['id'], so['arrangements'][0]['id'], bid))
    ok(r2, 'POST', '/arrangements/%s/notes' % ids[0][1], {'teamId': t2, 'markerLabel': 'A', 'layer': 'all', 'session': '드럼', 'text': '크게'})
    time.sleep(6)   # 서버가 since 기준을 몇 초 앞당겨 주므로 그 밖으로 나간다
    full = list_of(r2, t2)
    if len(full['songs']) != 3 or len(full['blobs']) != 3: fail('G04: 통째 목록 %d곡 %d파일' % (len(full['songs']), len(full['blobs'])))
    t0 = full['now']
    if list_of(r2, t2, t0)['songs']: fail('G04: 아무것도 안 바뀌었는데 since 가 곡을 줌')
    upd0 = {x['id']: x['updatedAt'] for x in full['songs']}
    ok(r2, 'PATCH', '/arrangements/' + ids[1][1], {'teamId': t2, 'key': 'A'})
    inc = list_of(r2, t2, t0)
    if [x['id'] for x in inc['songs']] != [ids[1][0]]: fail('G04: since 가 바뀐 곡만 줘야 함 %s' % [x['title'] for x in inc['songs']])
    if list(inc['blobs'].keys()) != [ids[1][2]]: fail('G04: since 인데 다른 곡 파일 주소까지 줌 %s' % list(inc['blobs'].keys()))
    # 발행 → 통계가 바뀐 곡이 since 로 온다. '최근 고친' 순서(updatedAt)는 그대로
    sv2 = 'sv2' + tag
    ok(r2, 'PUT', '/services/' + sv2, {'teamId': t2, 'doc': {'id': sv2, 'version': 1, 'name': '주일', 'date': today.isoformat(),
        'items': [{'id': 'i1', 'songId': ids[2][0], 'arrId': ids[2][1], 'key': 'G', 'title': '곡2'}]}})
    inc = list_of(r2, t2, t0)
    row = [x for x in inc['songs'] if x['id'] == ids[2][0]]
    if not row or row[0]['useCount'] != 1: fail('G04: 발행한 곡의 통계가 since 로 안 옴 %s' % [(x['title'], x.get('useCount')) for x in inc['songs']])
    if row[0]['updatedAt'] != upd0[ids[2][0]]: fail('G04: 발행이 최근 고친 시각을 바꿈')
    # 발행을 지우면(콘티 삭제) 통계가 다시 0 으로
    t1 = inc['now']; time.sleep(6)
    ok(r2, 'DELETE', '/services/%s?team=%s' % (sv2, t2))
    row = [x for x in list_of(r2, t2, t1)['songs'] if x['id'] == ids[2][0]]
    if not row or row[0]['useCount'] != 0: fail('G04: 콘티를 지운 뒤 통계가 since 로 안 옴')
    # 다른 키로 새 편곡 → since 로 온다
    t1 = list_of(r2, t2)['now']; time.sleep(6)
    ok(r2, 'POST', '/songs/%s/arrangements' % ids[0][0], {'teamId': t2, 'fromId': ids[0][1], 'key': 'D'})
    row = [x for x in list_of(r2, t2, t1)['songs'] if x['id'] == ids[0][0]]
    if not row or len(row[0]['arrangements']) != 2: fail('G04: 새 편곡이 since 로 안 옴')
    # 세션 이름 바꾸기 → 메모 대상이 바뀐 곡이 since 로 온다
    t1 = list_of(r2, t2)['now']; time.sleep(6)
    sess = ok(r2, 'GET', '/me')['teams'][0]['sessions']
    ok(r2, 'PATCH', '/teams/' + t2, {'sessions': ['드럼1' if x == '드럼' else x for x in sess], 'rename': {'드럼': '드럼1'}})
    row = [x for x in list_of(r2, t2, t1)['songs'] if x['id'] == ids[0][0]]
    if not row or [n['session'] for a in row[0]['arrangements'] for n in a['notes']] != ['드럼1']: fail('G04: 세션 이름 바뀐 메모가 since 로 안 옴')
    print('G04 ok: since 는 바뀐 곡과 그 파일만 · 발행/삭제 통계 · 새 편곡 · 세션 이름도 since 로 온다')
    for v in ('1', '0', '2026', 'abc', '275760-09-13'):
        st, j = call(r2, 'GET', '/songs?team=%s&since=%s' % (t2, v))
        if st != 200 or len(j['songs']) != 3: fail('G04: since=%s → %s %s (통째로 줘야 함)' % (v, st, j and len(j.get('songs') or [])))
    print('G04 ok: since=1·0·2026 처럼 날짜가 아닌 값은 500 대신 통째로')

    # 한꺼번에 열어도 모두 받는다 (무거운 목록은 줄을 세워 만든다 — 자리가 안 풀리면 여기서 멈추거나 실패한다)
    pg2 = c2.new_page(); pg2.on('pageerror', lambda e: errs.append(str(e)))
    songs_reqs = []
    pg2.on('request', lambda r: songs_reqs.append(r.url) if '/api/songs?' in r.url else None)
    pg2.goto(URL); pg2.wait_for_selector('.shell[data-page]', timeout=10000)
    stat = pg2.evaluate('''async(t)=>{const rs=await Promise.all(Array.from({length:12},()=>fetch('/api/songs?team='+t).then(r=>r.status)));
      const after=await fetch('/api/songs?team='+t).then(r=>r.status);return rs.concat([after])}''', t2)
    if any(x != 200 for x in stat): fail('G04: 한꺼번에 받기 %s' % stat)
    print('G04 ok: 13번 한꺼번에 받아도 모두 200')

    # 앱: 처음엔 통째로, 다시 열면 since 로. 못 받은 파일은 다시 열 때 채운다
    pg2.wait_for_function('CONTI.S.songsAt', timeout=10000); pg2.wait_for_timeout(1500)
    if not any('since=' not in u for u in songs_reqs): fail('G04: 처음 열 때 통째로 받지 않음 %s' % songs_reqs)
    bid = ids[1][2]
    if not pg2.evaluate('async(id)=>!!(await CONTI.IDB.get("blobs",id))', bid): fail('G04: 악보 파일을 못 받음')
    pg2.evaluate('async(id)=>{await CONTI.IDB.del("blobs",id);await CONTI.save()}', bid); pg2.wait_for_timeout(800)
    songs_reqs.clear()
    pg2.reload(); pg2.wait_for_selector('.shell[data-page]', timeout=10000); pg2.wait_for_timeout(2500)
    if not songs_reqs or any('since=' not in u for u in songs_reqs): fail('G04: 다시 열 때 통째로 받음 %s' % songs_reqs)
    if not pg2.evaluate('async(id)=>!!(await CONTI.IDB.get("blobs",id))', bid): fail('G04: since 로 연 뒤 빠진 파일을 안 채움')
    print('G04 ok: 다시 열면 since 로 받고, 빠진 파일은 채운다')

    # ---------------- F46: 코드 담기에도 틀린 시도 제한 ----------------
    c3, t3 = leader(b, 'shr')
    def code(): return ''.join(random.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(6))
    sts = [call(c3.request, 'POST', '/share/%s/take' % code(), {'teamId': t3})[0] for _ in range(21)]
    if sts[:20] != [404] * 20 or sts[20] != 429: fail('F46: 담기 틀린 시도 제한이 없음 %s' % sts)
    st, _ = call(c3.request, 'GET', '/share/' + code())
    if st != 429: fail('F46: 담기로 잠긴 뒤 미리보기가 %s' % st)
    c4, t4 = leader(b, 'sh2')
    for _ in range(20): call(c4.request, 'GET', '/share/' + code())
    st, _ = call(c4.request, 'POST', '/share/%s/take' % code(), {'teamId': t4})
    if st != 429: fail('F46: 미리보기로 잠겼는데 담기가 %s' % st)
    print('F46 ok: 담기도 20번 틀리면 429, 미리보기와 같은 셈')

    # r2: 한꺼번에 보내도 20번까지만 (전에는 먼저 읽고 나중에 더해 수백 개 중 백몇십 개가 셈 밖으로 나갔다)
    def raw_take(cookie, cd, team):
        rq_ = urllib.request.Request(URL + 'api/share/%s/take' % cd, data=json.dumps({'teamId': team}).encode(), method='POST',
                                     headers={'x-conti': '1', 'content-type': 'application/json', 'cookie': cookie})
        try: return urllib.request.urlopen(rq_, timeout=60).status
        except urllib.error.HTTPError as e: return e.code
    c5, t5 = leader(b, 'sh5')
    ck = '; '.join('%s=%s' % (x['name'], x['value']) for x in c5.cookies())
    with concurrent.futures.ThreadPoolExecutor(60) as ex:
        sts = list(ex.map(lambda _: raw_take(ck, code(), t5), range(150)))
    cnt = {k: sts.count(k) for k in set(sts)}
    if cnt != {404: 20, 429: 130}: fail('F46: 한꺼번에 150번 담기 → %s (기대 404×20, 429×130)' % cnt)
    # 있는 코드는 틀린 시도가 아니다 — 먼저 센 한 번을 도로 뺀다 (미리보기 25번·담기·다 쓴 코드 담기 5번 뒤에도 틀린 20번까지는 404)
    c6, t6 = leader(b, 'sh6')
    s6 = ok(c6.request, 'POST', '/songs', {'teamId': t6, 'title': '나눌 곡'})['song']
    real = ok(c6.request, 'POST', '/share', {'teamId': t6, 'songIds': [s6['id']], 'maxUses': 1})['code']
    st, _ = call(c5.request, 'GET', '/share/' + real)
    if st != 429: fail('F46: 잠긴 계정이 진짜 코드 미리보기를 %s' % st)
    sts = [call(c6.request, 'GET', '/share/' + real.lower())[0] for _ in range(25)]
    sts += [call(c6.request, 'POST', '/share/%s/take' % real, {'teamId': t6})[0] for _ in range(6)]
    if sts != [200] * 26 + [404] * 5: fail('F46: 있는 코드가 틀린 시도로 셈됨 %s' % sts)
    sts = [call(c6.request, 'GET', '/share/' + code())[0] for _ in range(21)]
    if sts != [404] * 20 + [429]: fail('F46: 있는 코드를 쓴 뒤 틀린 시도 셈이 이상함 %s' % sts)
    print('F46 ok: 한꺼번에 150번이어도 틀린 시도는 20번까지, 있는 코드는 세지 않음')

    if errs: fail('페이지 오류: %s' % errs[:3])
    b.close()
  print('OK test_audit_api_library')

run()
