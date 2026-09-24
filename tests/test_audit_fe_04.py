# 전역감사 2026-09-24 fe-04 회귀 검사 — 동기화(발행본·초안·메모·파일) · 무대 추천 조판 · 로그인/로그아웃
# 준비: sh scripts/dev-local.sh (AI 는 가짜) → CONTI_URL=http://localhost:8766/ python tests/test_audit_fe_04.py
# 서비스 워커는 막는다 (요청을 늦추거나 끊어 경합을 재현하려면 페이지가 직접 fetch 해야 한다)
import os, sys, time, json, re, base64, subprocess
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
H = {'x-conti': '1'}
TAG = str(int(time.time() * 1000))[-8:]
SEQ = [0]
IPAD = {'width': 1180, 'height': 820}   # deviceClass() = tab-l


def fail(msg):
    print('FAIL:', msg); sys.exit(1)


def nid(p):
    SEQ[0] += 1
    return '%s%s%d' % (p, TAG, SEQ[0])


def call(ctx, method, path, data=None):
    r = ctx.request.fetch(URL + 'api' + path, method=method, headers=H, data=data)
    try: j = r.json()
    except Exception: j = None
    return r.status, j


def must(ctx, method, path, data=None):
    st, j = call(ctx, method, path, data)
    if st != 200: fail('%s %s → %s %s' % (method, path, st, j))
    return j


def user(b, name, viewport=None):
    c = b.new_context(viewport=viewport or IPAD, service_workers='block')
    u = nid('u')
    must(c, 'POST', '/auth/signup', {'username': u, 'password': 'secret1', 'name': name, 'agreedAt': '2026-09-24T00:00:00Z'})
    c._u = u
    return c


def leader(b, team='감사팀', viewport=None):
    c = user(b, '인도', viewport)
    t = must(c, 'POST', '/teams', {'name': team + TAG, 'myName': '인도', 'session': '인도자'})
    c._team = t['teamId']; c._invite = t['invite']
    return c


def member(b, lead, viewport=None, name='멤버'):
    c = user(b, name, viewport)
    must(c, 'POST', '/invite/%s/join' % lead._invite, {'name': name, 'sessions': ['드럼'], 'session': '드럼'})
    c._team = lead._team
    return c


def item(i, title, key='G'):
    return {'id': i, 'title': title, 'key': key, 'form': 'Int – AAB', 'pieces': [], 'media': []}


def publish(c, sid, version, items, name='감사 예배', date='2099-01-04', **extra):
    doc = {'id': sid, 'name': name, 'date': date, 'notice': extra.get('notice', ''), 'version': version, 'items': items}
    return must(c, 'PUT', '/services/' + sid, {'teamId': c._team, 'doc': doc})


def page(c, hash_=''):
    pg = c.new_page()
    pg._errs = []
    pg.on('pageerror', lambda e: pg._errs.append(str(e)[:300]))
    pg.on('dialog', lambda d: d.accept())
    pg.goto(URL + hash_)
    pg.wait_for_function("window.CONTI&&CONTI.S&&CONTI.S.team&&CONTI.S.team.id", timeout=15000)
    return pg


def until(pg, js, arg=None, timeout=15000, what=''):
    try:
        pg.wait_for_function(js, arg=arg, timeout=timeout, polling=150)
    except Exception:
        fail('시간 안에 안 됨: ' + (what or js))


def svc_js(sid):
    return "CONTI.S.services.find(x=>x.id===%s)" % json.dumps(sid)


def notes_on_server(c, sid):
    return must(c, 'GET', '/notes?team=%s&service=%s' % (c._team, sid))['notes']


# 페이지 안의 fetch 를 늦춘다: 규칙 [{re, method, ms}] — 요청은 바로 가고(서버는 그 순간 처리) 응답만 늦게 온다
SLOW = """(rules)=>{window.__slow=rules;if(window.__slowOn)return;window.__slowOn=true;const f=window.fetch;
 window.fetch=function(u,o){const p=f.apply(this,arguments);const m=((o&&o.method)||'GET').toUpperCase();
  const r=(window.__slow||[]).find(x=>new RegExp(x.re).test(String(u))&&(!x.method||x.method===m));
  return r?p.then(res=>new Promise(ok=>setTimeout(()=>ok(res),r.ms))):p}}"""


# ---------- F20: 인도자 추천 조판이 멤버에게 간다 · 초안뿐이면 저장했다고 하지 않는다 ----------
def t_f20(b):
    L = leader(b); M = member(b, L)
    sid = nid('st')
    publish(L, sid, 1, [item(nid('i'), '예수로 나의 구주 삼고'), item(nid('i'), '주 사랑합니다', 'D')])
    pm = page(M)
    until(pm, svc_js(sid) + "&&" + svc_js(sid) + ".published", what='멤버가 발행본을 받음')
    # 인도자: 무대 → 편집 → 인도자 추천
    pl = page(L)
    until(pl, svc_js(sid) + "&&" + svc_js(sid) + ".published", what='인도자 기기에 발행본')
    pl.evaluate("(id)=>CONTI.stageOpen(CONTI.S.services.find(x=>x.id===id),0)", sid)
    pl.wait_for_selector('#stageWrap .stgpage', timeout=15000)
    pl.click('[data-stg="edit"]'); pl.wait_for_timeout(400)
    pl.click('[data-sc="rec"]'); pl.wait_for_timeout(1500)
    doc = must(L, 'GET', '/services/%s?team=%s' % (sid, L._team))['doc']
    if 'tab-l' not in (doc.get('stageLayouts') or {}): fail('전제 실패: 서버에 추천 조판이 없음 %s' % doc.get('stageLayouts'))
    # 이미 v1 을 받아 둔 멤버: 무대를 열면 추천 조판으로 시작한다 (버전이 그대로라 목록 동기화로는 안 온다)
    pm.evaluate("(id)=>CONTI.stageOpen(CONTI.S.services.find(x=>x.id===id),0)", sid)
    pm.wait_for_selector('#stageWrap .stgpage', timeout=15000)
    until(pm, "CONTI.STG.layout&&((%s.published.stageLayouts||{})['tab-l'])" % svc_js(sid), timeout=8000,
          what='멤버 무대가 추천 조판으로 열림')
    pm.evaluate("CONTI.stageExit()")
    # 새로 들어온 멤버: 발행본을 받을 때 추천 조판도 같이 받는다
    M2 = member(b, L, name='새멤버'); pm2 = page(M2)
    until(pm2, "%s&&%s.published&&(%s.published.stageLayouts||{})['tab-l']" % (svc_js(sid), svc_js(sid), svc_js(sid)), timeout=15000,
          what='새 멤버의 발행본에 추천 조판')
    # 인도자가 다시 발행해도 이 기기의 추천 조판이 남는다
    pl.evaluate("CONTI.stageExit()")
    pl.goto(URL + '#/edit/' + sid); pl.wait_for_selector('[data-f="item.title"]', timeout=10000)
    pl.fill('[data-f="item.key"]', 'A'); pl.wait_for_timeout(400)
    pl.click('[data-act="publish"]'); pl.wait_for_selector('#pubOnly'); pl.click('#pubOnly')
    until(pl, "%s.published.version===2" % svc_js(sid), what='인도자 v2 발행')
    if not pl.evaluate("!!(%s.published.stageLayouts||{})['tab-l']" % svc_js(sid)): fail('다시 발행했더니 인도자 기기의 추천 조판이 사라짐')
    # 초안뿐인 콘티: 서버는 404, 앱은 발행부터 하라고 알린다
    did = nid('dr')
    must(L, 'PUT', '/services/%s/draft' % did, {'teamId': L._team, 'doc': {'id': did, 'name': '초안', 'date': '2099-02-01', 'items': [item(nid('i'), '곡')], 'editedAt': 1}})
    st, j = call(L, 'PUT', '/services/%s/stage-layout' % did, {'teamId': L._team, 'device': 'tab-l', 'layout': {'v': 2, 'screens': []}})
    if st != 404: fail('초안뿐인 콘티에 추천 조판 저장이 %s (404 여야 함)' % st)
    st, j = call(M, 'GET', '/services/%s/stage-layout?team=%s' % (sid, L._team))
    if st != 200 or 'tab-l' not in (j.get('stageLayouts') or {}): fail('추천 조판 조회 %s %s' % (st, j))
    for p_ in (pm, pl, pm2):
        if p_._errs: fail('page errors: %s' % p_._errs)
    for c in (L, M, M2): c.close()
    print('F20 ok')


# ---------- F22 · F79: 메모 그림자 ----------
def t_notes(b):
    L = leader(b); M = member(b, L)
    sid = nid('nt'); A = nid('iA'); B = nid('iB')
    publish(L, sid, 1, [item(A, '곡 A')])
    pm = page(M)
    until(pm, svc_js(sid), what='멤버가 v1 을 받음')
    # 다른 기기에서 v2(곡 B 추가)를 받아 곡 B 에 메모를 썼다
    publish(L, sid, 2, [item(A, '곡 A'), item(B, '곡 B')])
    nb = nid('nB')
    must(M, 'POST', '/notes', {'teamId': L._team, 'serviceId': sid, 'notes': [{'id': nb, 'itemId': B, 'layer': 'mine', 'text': '곡 B 메모'}]})
    # 이 기기는 아직 v1 (목록 동기화를 막는다) — 콘티를 열면 메모를 받고 0.7초 뒤 올린다
    pm.route(re.compile(r'/api/services\?team='), lambda r: r.abort())
    pm.goto(URL + '#/view/' + sid); pm.wait_for_timeout(3500)
    if pm.evaluate("%s.items.length" % svc_js(sid)) != 1: fail('전제 실패: 기기가 이미 v2 를 받음')
    if nb not in [n['id'] for n in notes_on_server(M, sid)]: fail('F22: v1 기기가 v2 곡의 메모를 서버에서 지움')
    if pm.evaluate("(CONTI.S.noteShadow[%s]||[]).some(x=>x.id===%s)" % (json.dumps(sid), json.dumps(nb))):
        fail('F22: 이 기기에 없는 곡의 메모가 그림자에 들어감')
    # 옛 버전이 남긴 오염된 그림자(없는 곡의 메모)가 있어도 지우지 않는다
    pm.evaluate("async ([id,nb,B])=>{CONTI.S.noteShadow[id].push({id:nb,itemId:B});await CONTI.SYNC.pushNotes(CONTI.S.services.find(x=>x.id===id))}", [sid, nb, B])
    if nb not in [n['id'] for n in notes_on_server(M, sid)]: fail('F22: 오염된 그림자로 없는 곡의 메모를 지움')
    pm.unroute(re.compile(r'/api/services\?team='))
    pm.evaluate("async (id)=>{await CONTI.SYNC.pullServices();await CONTI.SYNC.pullNotes(CONTI.S.services.find(x=>x.id===id))}", sid)
    if not pm.evaluate("%s.items[1].notes.some(n=>n.id===%s)" % (svc_js(sid), json.dumps(nb))): fail('v2 를 받은 뒤 곡 B 메모가 안 붙음')
    print('F22 ok')

    # F79: 메모 목록을 받는 사이 새 메모를 쓰면 — 화면에서 사라지지 않고 서버에서도 지워지지 않는다
    pm.evaluate(SLOW, [{'re': '/api/notes\\?', 'method': 'GET', 'ms': 3000}, {'re': '/api/notes$', 'method': 'POST', 'ms': 3000}])
    pm.evaluate("(id)=>{window.__pn=CONTI.SYNC.pullNotes(CONTI.S.services.find(x=>x.id===id))}", sid)
    pm.wait_for_timeout(400)
    rid = nid('race')
    pm.evaluate("([id,rid])=>{const s=CONTI.S.services.find(x=>x.id===id);s.items[0].notes.push({id:rid,layer:'mine',text:'레이스 메모',at:Date.now()});CONTI.save()}", [sid, rid])
    pm.wait_for_timeout(9000)
    pm.evaluate("()=>{window.__slow=[]}")
    if rid not in [n['id'] for n in notes_on_server(M, sid)]: fail('F79: 받는 사이 쓴 메모가 서버에서 지워짐')
    if not pm.evaluate("%s.items[0].notes.some(n=>n.id===%s)" % (svc_js(sid), json.dumps(rid))): fail('F79: 받는 사이 쓴 메모가 화면에서 사라짐')
    # 받는 사이 지운 메모는 되살아나지 않고 서버에서도 지워진다
    pm.evaluate(SLOW, [{'re': '/api/notes\\?', 'method': 'GET', 'ms': 3000}])
    pm.evaluate("(id)=>{window.__pn=CONTI.SYNC.pullNotes(CONTI.S.services.find(x=>x.id===id))}", sid)
    pm.wait_for_timeout(400)
    pm.evaluate("([id,rid])=>{const s=CONTI.S.services.find(x=>x.id===id);s.items[0].notes=s.items[0].notes.filter(n=>n.id!==rid);CONTI.save()}", [sid, rid])
    pm.wait_for_timeout(6000)
    pm.evaluate("()=>{window.__slow=[]}")
    if pm.evaluate("%s.items[0].notes.some(n=>n.id===%s)" % (svc_js(sid), json.dumps(rid))): fail('F79: 받는 사이 지운 메모가 되살아남')
    if rid in [n['id'] for n in notes_on_server(M, sid)]: fail('F79: 받는 사이 지운 메모가 서버에 남음')
    if pm._errs: fail('page errors: %s' % pm._errs)
    L.close(); M.close()
    print('F79 ok')


# ---------- F21: 악보 다시 불러오기가 서버에 없는 파일을 지우지 않는다 ----------
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==') + b'\0' * 400


def t_f21(b):
    L = leader(b)
    sid = nid('rf'); up = nid('bUp'); loc = nid('bLoc')
    r = L.request.post(URL + 'api/blobs/%s?team=%s' % (up, L._team), headers={**H, 'content-type': 'image/png'}, data=PNG)
    if r.status != 200: fail('파일 올리기 실패 %s %s' % (r.status, r.text()))
    publish(L, sid, 1, [{**item(nid('i'), '곡'), 'pieces': [{'id': nid('p'), 'blob': up, 'markers': []}]}])
    pl = page(L)
    until(pl, svc_js(sid), what='발행본 받음')
    # 이 기기에만 있는 초안 악보(아직 안 올림) + 받아 둔 파일이 깨진 경우
    pl.evaluate("""async ([sid,up,loc])=>{const b=new Blob([new Uint8Array(600).fill(7)],{type:'image/png'});await CONTI.IDB.put('blobs',loc,b);
      await CONTI.IDB.put('blobs',up,new Blob([new Uint8Array(300).fill(1)],{type:'image/png'}));
      const s=CONTI.S.services.find(x=>x.id===sid);s.items[0].pieces.push({id:'p'+Date.now(),blob:loc,markers:[]});CONTI.save()}""", [sid, up, loc])
    n = pl.evaluate("CONTI.SYNC.refetchBlobs()")
    if not pl.evaluate("(async (loc)=>!!(await CONTI.IDB.get('blobs',loc)))(%s)" % json.dumps(loc)):
        fail('F21: 서버에 없는 이 기기의 악보를 지움')
    size = pl.evaluate("(async (up)=>{const b=await CONTI.IDB.get('blobs',up);return b?b.size:0})(%s)" % json.dumps(up))
    if size != len(PNG): fail('F21: 서버 파일로 갈아 끼우지 못함 (size %s, 받은 수 %s)' % (size, n))
    if pl._errs: fail('page errors: %s' % pl._errs)
    L.close()
    print('F21 ok')


# ---------- F73 · F74 · G15: 목록 동기화 ----------
def t_pull(b):
    L = leader(b, '에이팀')
    tB = must(L, 'POST', '/teams', {'name': '비팀' + TAG, 'myName': '인도', 'session': '인도자'})['teamId']
    tA = L._team
    sA = nid('sA'); sB = nid('sB')
    publish(L, sA, 1, [item(nid('i'), 'A팀 곡')])
    L._team = tB; publish(L, sB, 1, [item(nid('i'), 'B팀 곡')], name='B 예배'); L._team = tA
    pl = page(L)

    def switch(tid):
        pl.evaluate("()=>{document.querySelectorAll('#tswx').forEach(e=>e.remove());document.body.insertAdjacentHTML('beforeend','<button id=\"tswx\" data-act=\"team-switch\">x</button>')}")
        pl.click('#tswx'); pl.click('#modal [data-switch="%s"]' % tid)
        until(pl, "CONTI.S.team.id===%s" % json.dumps(tid), what='팀 전환')

    if pl.evaluate("CONTI.S.team.id") != tB: switch(tB)
    until(pl, svc_js(sB), what='B 팀 콘티 받음')
    # B 에서 발행 뒤 고쳐 둔 것(아직 발행 안 함)
    pl.evaluate("(id)=>{const s=CONTI.S.services.find(x=>x.id===id);s.items[0].title='B팀 곡 (고침)';s.version=s.published.version+1;s.editedAt=Date.now();CONTI.save()}", sB)
    switch(tA)
    until(pl, svc_js(sA), what='A 팀 콘티 받음')
    pl.wait_for_timeout(800)
    # A 의 발행본을 받는 도중(응답이 늦다)에 B 로 바꾼다
    pl.evaluate("(id)=>{CONTI.S.services=CONTI.S.services.filter(x=>x.id!==id);CONTI.save()}", sA)
    pl.evaluate(SLOW, [{'re': '/api/services/' + sA + '\\?team=', 'method': 'GET', 'ms': 2500}])
    pl.evaluate("()=>{window.__pp=CONTI.SYNC.pullServices()}")
    pl.wait_for_timeout(500)
    switch(tB)
    pl.wait_for_timeout(4000)
    pl.evaluate("()=>{window.__slow=[]}")
    if pl.evaluate("!!" + svc_js(sA)): fail('F73: A 팀 콘티가 B 팀 목록에 들어감')
    if not pl.evaluate("!!" + svc_js(sB)): fail('F73: B 팀 콘티(고친 것)가 지워짐')
    if pl.evaluate("%s.items[0].title" % svc_js(sB)) != 'B팀 곡 (고침)': fail('F73: B 팀 콘티의 고친 것이 사라짐')
    print('F73 ok')

    # F74: 겹쳐 부른 동기화가 같은 초안을 두 번 넣지 않는다
    did = nid('dd')
    must(L, 'PUT', '/services/%s/draft' % did, {'teamId': tB, 'doc': {'id': did, 'name': '다른 기기 초안', 'date': '2099-03-01', 'items': [item(nid('i'), '곡')], 'editedAt': 5}})
    pl.evaluate(SLOW, [{'re': '/api/services/' + did + '\\?team=.*draft=1', 'method': 'GET', 'ms': 1200}])
    pl.wait_for_timeout(1500)   # 켤 때 돈 동기화가 이미 받아 뒀으면 지우고 다시 — 두 호출이 같이 받게
    pl.evaluate("async (id)=>{CONTI.S.services=CONTI.S.services.filter(x=>x.id!==id);await Promise.all([CONTI.SYNC.pullServices(),CONTI.SYNC.pullServices()])}", did)
    pl.evaluate("()=>{window.__slow=[]}")
    n = pl.evaluate("CONTI.S.services.filter(x=>x.id===%s).length" % json.dumps(did))
    if n != 1: fail('F74: 같은 초안이 %d번 들어감' % n)
    # 예전 버전이 두 번 저장해 둔 것은 켤 때 하나로 정리한다
    pl.evaluate("async (id)=>{const s=CONTI.S.services.find(x=>x.id===id);CONTI.S.services.push(JSON.parse(JSON.stringify(s)));CONTI.save();await new Promise(r=>setTimeout(r,600))}", did)
    pl.reload(); pl.wait_for_function("window.CONTI&&CONTI.S.team.id", timeout=15000)
    n = pl.evaluate("CONTI.S.services.filter(x=>x.id===%s).length" % json.dumps(did))
    if n != 1: fail('F74: 켤 때 중복을 정리하지 않음 (%d)' % n)
    if pl._errs: fail('page errors: %s' % pl._errs)
    print('F74 ok')

    # G15: 받는 대로 홈에 보인다 (다 받을 때까지 비어 있지 않다)
    ids = [nid('g') for _ in range(10)]
    for k, i in enumerate(ids):
        publish(L, i, 1, [item(nid('i'), '곡 %d' % k)], name='예배 %d' % k, date='2099-04-%02d' % (k + 1))
    M = member(b, L, viewport={'width': 430, 'height': 900})
    pm = M.new_page(); pm._errs = []; pm.on('pageerror', lambda e: pm._errs.append(str(e)[:300]))
    pm.add_init_script("""(()=>{const f=window.fetch;window.fetch=function(u,o){const p=f.apply(this,arguments);
      if(/\\/api\\/services\\/[^/?]+\\?team=/.test(String(u)))return p.then(r=>new Promise(ok=>setTimeout(()=>ok(r),500)));return p}})()""")
    pm.goto(URL)
    seen = None
    t0 = time.time()
    while time.time() - t0 < 20:
        st = pm.evaluate("()=>({rows:document.querySelectorAll('.svcrow').length,n:window.CONTI?CONTI.S.services.length:0})")
        if st['rows'] > 0 and st['n'] < len(ids): seen = st; break
        if st['n'] >= len(ids): break
        pm.wait_for_timeout(150)
    if not seen: fail('G15: 다 받을 때까지 홈에 콘티가 안 보임 (%s)' % st)
    until(pm, "CONTI.S.services.length>=%d&&document.querySelectorAll('.svcrow').length>0" % len(ids), timeout=20000, what='결국 전부 받음')
    if pm._errs: fail('page errors: %s' % pm._errs)
    L.close(); M.close()
    print('G15 ok (중간에 보인 것 %s)' % seen)


# ---------- F75: 1부와 같은 곡·날짜로 만든 2부 예배가 지워지지 않는다 ----------
def t_f75(b):
    L = leader(b)
    s1 = nid('w1')
    publish(L, s1, 1, [item(nid('i'), '주 은혜임을'), item(nid('i'), '우리 주 하나님')], name='1부 예배', date='2099-05-03')
    pl = page(L)
    until(pl, svc_js(s1), what='1부 받음')
    s2 = nid('w2')
    pl.evaluate("""([s1,s2])=>{const a=CONTI.S.services.find(x=>x.id===s1);
      CONTI.S.services.unshift({id:s2,name:'2부 예배',date:a.date,notice:'',version:0,published:null,editedAt:Date.now(),
       items:a.items.map(it=>({...JSON.parse(JSON.stringify(it)),id:'n'+it.id,notes:[]}))});CONTI.save()}""", [s1, s2])
    pl.evaluate("CONTI.SYNC.pullServices()"); pl.wait_for_timeout(1500)
    if not pl.evaluate("!!" + svc_js(s2)): fail('F75: 이 기기에서 만든 2부 예배를 복사본으로 보고 지움')
    # 에디터를 안 거쳐도 서버에 초안으로 올라간다
    pl.evaluate("CONTI.save()")
    ok = False
    for _ in range(40):
        pl.wait_for_timeout(250)
        st, j = call(L, 'GET', '/services/%s/draft?team=%s' % (s2, L._team))
        if st == 200 and j and j.get('doc'): ok = True; break
    if not ok: fail('F75: 새 콘티가 서버 초안으로 안 올라감')
    if pl._errs: fail('page errors: %s' % pl._errs)
    L.close()
    print('F75 ok')


# ---------- F76: 다른 기기가 같은 번호로 발행해도 이 기기의 고친 것이 남는다 ----------
def t_f76(b):
    L = leader(b)
    sid = nid('pc'); X = nid('iX')
    publish(L, sid, 1, [item(X, '곡 X', 'G')])
    pl = page(L)
    until(pl, svc_js(sid) + "&&" + svc_js(sid) + ".published", what='v1 받음')
    # 이 기기: 키를 바꾸고 곡을 더했다 (아직 발행 안 함) — touch() 와 같은 표시
    pl.evaluate("""(id)=>{const s=CONTI.S.services.find(x=>x.id===id);s.items[0].key='A';s.items.push({id:'y'+Date.now(),title:'곡 Y',key:'D',form:'',pieces:[],media:[],notes:[]});
      s.version=s.published.version+1;s.editedAt=Date.now();CONTI.save()}""", sid)
    # 다른 기기(PC)가 v2 를 발행
    publish(L, sid, 2, [item(X, '곡 X', 'G')], notice='PC 에서 고침')
    pl.evaluate("CONTI.SYNC.pullServices()"); pl.wait_for_timeout(1500)
    st = pl.evaluate("(()=>{const s=%s;return {key:s.items[0].key,n:s.items.length,pv:s.published.version,v:s.version}})()" % svc_js(sid))
    if st['key'] != 'A' or st['n'] != 2: fail('F76: 다른 기기의 발행이 이 기기의 고친 것을 덮음 %s' % st)
    if st['pv'] != 2 or st['v'] != 3: fail('F76: 버전 정리가 이상함 %s' % st)
    # 409 뒤 다시 받을 때도: PC 가 또 v3 를 발행 → 이 기기에서 발행 → 충돌 알림 → 고친 것은 남는다
    publish(L, sid, 3, [item(X, '곡 X', 'G')], notice='PC 에서 또 고침')
    pl.goto(URL + '#/edit/' + sid); pl.wait_for_selector('[data-act="publish"]', timeout=10000)
    pl.click('[data-act="publish"]'); pl.wait_for_selector('#pubOnly'); pl.click('#pubOnly')
    pl.wait_for_timeout(3000)
    st = pl.evaluate("(()=>{const s=%s;return {key:s.items[0].key,n:s.items.length,pv:s.published.version,v:s.version}})()" % svc_js(sid))
    if st['key'] != 'A' or st['n'] != 2: fail('F76: 409 뒤 다시 받으며 고친 것을 덮음 %s' % st)
    if st['pv'] != 3 or st['v'] != 4: fail('F76: 409 뒤 버전 %s' % st)
    # 고친 게 없으면(발행 창만 열었다 닫음) 새 발행본을 그대로 받는다
    pl.goto(URL + '#/home'); pl.wait_for_timeout(500)
    sid2 = nid('pc2')
    publish(L, sid2, 1, [item(nid('i'), '곡', 'G')])
    pl.evaluate("CONTI.SYNC.pullServices()"); until(pl, svc_js(sid2), what='v1 받음')
    pl.goto(URL + '#/edit/' + sid2); pl.wait_for_selector('[data-act="publish"]', timeout=10000)
    pl.click('[data-act="publish"]'); pl.wait_for_selector('#pubOnly'); pl.keyboard.press('Escape'); pl.wait_for_timeout(300)
    pl.evaluate("()=>{const m=document.querySelector('#modal [data-close]');if(m)m.click()}")
    publish(L, sid2, 2, [item(nid('i'), '곡 (PC)', 'C')])
    pl.goto(URL + '#/home'); pl.evaluate("CONTI.SYNC.pullServices()"); pl.wait_for_timeout(1500)
    if pl.evaluate("%s.items[0].title" % svc_js(sid2)) != '곡 (PC)': fail('F76: 고친 게 없는데 새 발행본을 안 받음')
    if pl._errs: fail('page errors: %s' % pl._errs)
    L.close()
    print('F76 ok')


# ---------- F77 · F78: 초안 올리기 ----------
def t_draft(b):
    L = leader(b)
    pl = page(L)
    sid = nid('df')
    pl.evaluate("""(id)=>{CONTI.S.services.push({id,name:'레이스 예배',date:'2099-06-07',notice:'',version:0,published:null,items:[],editedAt:Date.now()});CONTI.save()}""", sid)
    pl.goto(URL + '#/edit/' + sid); pl.wait_for_selector('[data-f="svc.name"]', timeout=10000); pl.wait_for_timeout(3500)
    # PUT 이 도는 사이 고친 것(에디터의 자동 저장과 같은 길: touch → save)은, 끝난 뒤 다음 자동 저장이 올린다
    pl.evaluate(SLOW, [{'re': '/api/services/' + sid + '/draft', 'method': 'PUT', 'ms': 1500}])
    pl.evaluate("(id)=>{const s=CONTI.S.services.find(x=>x.id===id);s.name='레이스 예배 A';s.editedAt=Date.now();window.__pd=CONTI.SYNC.pushDraft(s)}", sid)
    pl.wait_for_timeout(300)
    pl.evaluate("(id)=>{const s=CONTI.S.services.find(x=>x.id===id);s.name='FINAL';s.editedAt=Date.now();CONTI.save()}", sid)
    pl.wait_for_timeout(6500)
    pl.evaluate("()=>{window.__slow=[]}")
    doc = must(L, 'GET', '/services/%s/draft?team=%s' % (sid, L._team))['doc']
    if not doc or doc.get('name') != 'FINAL': fail('F77: 올리는 사이 고친 이름이 서버 초안에 없음 %s' % (doc and doc.get('name')))
    if not pl.evaluate("(()=>{const s=%s;return s.draftPushedAt===s.editedAt})()" % svc_js(sid)): fail('F77: 올린 표시가 맞지 않음')
    print('F77 ok')
    # F78: 같은 파일을 겹쳐 올리지 않는다
    big = nid('bBig')
    cnt = pl.evaluate("""async ([id,big])=>{const s=CONTI.S.services.find(x=>x.id===id);
      await CONTI.IDB.put('blobs',big,new Blob([new Uint8Array(600000).fill(3)],{type:'audio/mp4'}));
      s.items.push({id:'m'+Date.now(),title:'녹음 곡',key:'',form:'',pieces:[],media:[{id:'md'+Date.now(),type:'audio',blob:big,name:'a',notes:[]}],notes:[]});
      s.editedAt=Date.now();window.__posts=0;const f=window.fetch;
      // 올리기 요청은 1.2초 늦게 떠난다 — 그 사이 모든 호출이 '서버에 없다'는 답을 받는다 (느린 망에서 자동 저장이 겹칠 때와 같다)
      window.fetch=function(u,o){const a=arguments;if(String(u).includes('/api/blobs/'+big)&&o&&o.method==='POST'){window.__posts++;
        return new Promise(ok=>setTimeout(ok,1200)).then(()=>f.apply(this,a))}return f.apply(this,a)};
      await Promise.all([CONTI.SYNC.pushDraft(s),CONTI.SYNC.pushLibrary(),CONTI.SYNC.ensureBlobs(s.items,true),CONTI.SYNC.ensureBlobs(s.items,true)]);
      return window.__posts}""", [sid, big])
    if cnt != 1: fail('F78: 같은 파일을 %d번 올림' % cnt)
    if pl._errs: fail('page errors: %s' % pl._errs)
    L.close()
    print('F78 ok')


# ---------- G31: 1MB 가 넘는 콘티도 올라가고, 한도를 넘으면 무엇이 문제인지 알린다 ----------
def t_g31(b):
    L = leader(b)
    sid = nid('big')
    fat = 'x' * 1_500_000
    items = [dict(item(nid('i'), '큰 곡'), songNote=fat)]
    st, j = call(L, 'PUT', '/services/%s/draft' % sid, {'teamId': L._team, 'doc': {'id': sid, 'name': '큰 예배', 'date': '2099-07-05', 'items': items, 'editedAt': 1}})
    if st != 200: fail('G31: 1.5MB 초안 저장 %s %s' % (st, j))
    publish(L, sid, 1, items)
    # 로그인 없이는 여전히 1MB 까지만
    anon = b.new_context()
    r = anon.request.fetch(URL + 'api/services/' + sid + '/draft', method='PUT', headers=H, data={'teamId': L._team, 'doc': {'items': items}})
    if r.status != 413: fail('G31: 로그인 없는 큰 요청이 %s (413 이어야)' % r.status)
    anon.close()
    # 한도를 넘는 콘티: 앱이 크기를 알리고 되돌린다 (발행 대기로 남기지 않는다)
    pl = page(L)
    until(pl, svc_js(sid), what='큰 콘티 받음')
    pl.evaluate("(id)=>{const s=CONTI.S.services.find(x=>x.id===id);s.items[0].songNote='y'.repeat(4200000);s.version=s.published.version+1;s.editedAt=Date.now();CONTI.save()}", sid)
    msgs = []
    pl.on('dialog', lambda d: msgs.append(d.message))
    pl.goto(URL + '#/edit/' + sid); pl.wait_for_selector('[data-act="publish"]', timeout=15000)
    pl.click('[data-act="publish"]'); pl.wait_for_selector('#pubOnly'); pl.click('#pubOnly')
    pl.wait_for_timeout(2500)
    st = pl.evaluate("(()=>{const s=%s;return {pv:s.published.version,pend:!!s.pubPending}})()" % svc_js(sid))
    if st['pv'] != 1 or st['pend']: fail('G31: 너무 큰 발행이 발행 대기로 남음 %s' % st)
    if not any('MB' in m for m in msgs): fail('G31: 크기를 알려 주지 않음 %s' % msgs)
    if pl._errs: fail('page errors: %s' % pl._errs)
    L.close()
    print('G31 ok')


# ---------- F80: 구글·애플로 처음 오면 동의 창을 먼저 띄운다 ----------
def t_f80(b):
    c = b.new_context(viewport={'width': 430, 'height': 900}, service_workers='block')
    pg = c.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:300]))
    sent = []

    def social(route):
        body = json.loads(route.request.post_data or '{}'); sent.append(body)
        if not body.get('agreedAt'):
            return route.fulfill(status=428, content_type='application/json', body=json.dumps({'error': 'needs_consent', 'message': '처음 오셨네요'}))
        return route.fulfill(status=503, content_type='application/json', body=json.dumps({'error': 'no_social', 'message': '시험 끝'}))
    pg.route(re.compile(r'/api/auth/social$'), social)
    pg.route(re.compile(r'/api/auth/providers$'), lambda r: r.fulfill(status=200, content_type='application/json', body=json.dumps({'google': 'audit-client'})))
    pg.route('https://accounts.google.com/gsi/client', lambda r: r.fulfill(status=200, content_type='text/javascript', body=
        "window.google={accounts:{id:{initialize(c){window.__gcb=c.callback},prompt(){},"
        "renderButton(h){const b=document.createElement('div');b.setAttribute('role','button');b.onclick=()=>window.__gcb({credential:'tok.en.x'});h.appendChild(b)}}}}"))
    pg.goto(URL); pg.wait_for_selector('#gBtn', timeout=10000)   # 로그인 탭 (가입 탭이 아니다)
    pg.click('#gBtn')
    pg.wait_for_selector('#scAgree', timeout=5000)
    if not sent or sent[0].get('agreedAt'): fail('F80: 동의를 안 봤는데 동의 시각을 보냄 %s' % sent)
    if not sent[0].get('login'): fail('F80/F82: 로그인 화면의 소셜 로그인에 login 표시가 없음')
    if '14세' not in pg.locator('#modal').inner_text(): fail('F80: 동의 창에 만 14세 안내 없음')
    pg.click('#scOk'); pg.wait_for_timeout(200)
    if len(sent) != 1: fail('F80: 체크 없이 가입을 보냄')
    pg.check('#scAgree'); pg.click('#scOk'); pg.wait_for_timeout(800)
    if len(sent) != 2 or not sent[1].get('agreedAt'): fail('F80: 동의한 뒤 동의 시각을 보내지 않음 %s' % sent)
    if errs: fail('page errors: %s' % errs)
    c.close()
    # 서버: 동의 없는 새 소셜 계정은 만들지 않는다 (가짜 구글 키로 서명한 토큰을 쓰는 node 스크립트)
    r = subprocess.run(['node', '--input-type=module', '-e', SOCIAL_JS], cwd=ROOT, capture_output=True, text=True, timeout=90,
                       env={**os.environ, 'ROOT': ROOT})
    if r.returncode != 0: fail('F80 서버 검사 실패:\n' + r.stdout + r.stderr)
    print(r.stdout.strip())
    print('F80 ok')


# ---------- F81 · F82: 로그아웃 ----------
def t_logout(b):
    L = leader(b)
    ep = 'https://push.example/' + nid('ep')
    must(L, 'POST', '/push/subscribe', {'sub': {'endpoint': ep, 'keys': {'p256dh': 'k', 'auth': 'a'}}})
    must(L, 'POST', '/push/token', {'token': nid('tok'), 'platform': 'ios'})
    pl = page(L)
    # 브라우저 구독 대신: 이 기기의 알림 주소를 이 endpoint 로 보이게 한다
    pl.evaluate("(ep)=>{Object.defineProperty(navigator,'serviceWorker',{configurable:true,value:{ready:Promise.resolve({pushManager:{getSubscription:async()=>({endpoint:ep})}})}})}", ep)
    # 로그아웃이 실패하면 로그아웃된 척하지 않는다
    pl.route(re.compile(r'/api/auth/logout$'), lambda r: r.abort())
    pl.goto(URL + '#/settings'); pl.wait_for_selector('.setpane', timeout=10000)
    pl.click('[data-act="set-tab"][data-t="app"]'); pl.wait_for_selector('#sLogout', timeout=10000)
    pl.click('#sLogout'); pl.wait_for_timeout(2500)
    if not pl.evaluate("!!CONTI.NET.user"): fail('F82: 로그아웃 요청이 실패했는데 로그아웃된 것처럼 보임')
    pl.unroute(re.compile(r'/api/auth/logout$'))
    got = []
    pl.on('request', lambda r: got.append(r.post_data) if r.url.endswith('/api/auth/logout') else None)
    pl.click('#sLogout'); pl.wait_for_selector('#lgUser', timeout=10000)
    st, _ = call(L, 'GET', '/me')
    if st != 401: fail('F82: 로그아웃 뒤에도 세션이 살아 있음 %s' % st)
    if not got or ep not in (got[-1] or ''): fail('F81: 로그아웃이 이 기기의 알림 주소를 보내지 않음 %s' % got)
    # 서버: 그 endpoint 는 지워졌다 → 다시 로그인해 구독 목록을 보면 없다 (push_subs 를 직접 볼 수 없으니 같은 endpoint 를 다른 계정으로 등록해 본다)
    r = subprocess.run(['docker', 'exec', 'conti-pg', 'psql', '-U', 'postgres', '-tAc',
                        "select count(*) from push_subs where endpoint='%s'" % ep], capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip() != '0': fail('F81: 로그아웃 뒤에도 이 기기의 웹푸시 구독이 남음')
    if r.returncode != 0: print('  (docker 로 push_subs 확인 못 함 — 건너뜀)')
    # F81: 비밀번호를 바꾸면 다른 기기의 알림은 끊고 이 기기 것은 남긴다
    c = user(b, '알림'); keep = 'https://push.example/' + nid('keep'); other = 'https://push.example/' + nid('other')
    for e in (keep, other): must(c, 'POST', '/push/subscribe', {'sub': {'endpoint': e, 'keys': {'p256dh': 'k', 'auth': 'a'}}})
    must(c, 'POST', '/auth/password', {'current': 'secret1', 'next': 'secret2', 'endpoint': keep})
    r = subprocess.run(['docker', 'exec', 'conti-pg', 'psql', '-U', 'postgres', '-tAc',
                        "select endpoint from push_subs where endpoint in ('%s','%s')" % (keep, other)], capture_output=True, text=True)
    if r.returncode == 0:
        rows = r.stdout.split()
        if other in rows or keep not in rows: fail('F81: 비밀번호 변경 뒤 알림 정리가 이상함 %s' % rows)
    # F82: 로그인 화면에서 부른 소셜 로그인은 남은 세션에 붙이지 않는다 → audit_fe_04_social.mjs 에서 확인
    if pl._errs: fail('page errors: %s' % pl._errs)
    L.close(); c.close()
    print('F81 · F82 ok')


# ======== 2차 (검증에서 되돌려진 것 바로잡기) ========
def team_switch(pl, tid):
    pl.evaluate("()=>{document.querySelectorAll('#tswx').forEach(e=>e.remove());document.body.insertAdjacentHTML('beforeend','<button id=\"tswx\" data-act=\"team-switch\">x</button>')}")
    pl.click('#tswx'); pl.click('#modal [data-switch="%s"]' % tid)
    until(pl, "CONTI.S.team.id===%s" % json.dumps(tid), what='팀 전환')


def lay(A, B, x, extra=True):
    # 송폼 블록 둘 + 메모 띠·자른 악보·글 블록 (id 에 점·# 이 든다) + 이상한 id · 큰 화면 번호
    blocks = [{'id': 'h0', 'pid': A, 'iid': A, 'type': 'head', 'x': x, 'y': 0.05, 'w': 0.4, 'h': 0.1},
              {'id': 'h1', 'pid': B, 'iid': B, 'type': 'head', 'x': 0.1, 'y': 0.4, 'w': 0.4, 'h': 0.1}]
    if extra:
        blocks += [{'id': 't0.0.0', 'pid': 'p1', 'iid': A, 'type': 'strip', 'x': 0.1, 'y': 0.6, 'w': 0.3, 'h': 0.05},
                   {'id': 's0.1.40#5', 'pid': 'p1', 'iid': A, 'type': 'slice', 'x': 0.5, 'y': 0.6, 'w': 0.3, 'h': 0.2, 'ranges': [[40, 90]]},
                   {'id': 'x1a', 'type': 'text', 'text': '<b>글</b>', 'x': 0.6, 'y': 0.1, 'w': 0.3, 'h': 0.05},
                   {'id': '"><img src=x onerror=window.__xss=1>', 'type': 'text', 'text': 'x', 'x': 0, 'y': 0, 'w': 0.1, 'h': 0.1}]
    L = {'v': 2, 'screens': [{'blocks': blocks}]}
    if extra: L['off'] = [{'s': 1000000000, 'b': {'id': 'h9', 'type': 'head', 'x': 0, 'y': 0, 'w': 0.1, 'h': 0.1}}]
    return L


HEAD_X = "(()=>{const L=CONTI.STG.layout;if(!L)return null;const b=[].concat(...L.screens.map(s=>s.blocks)).find(b=>b.type==='head'&&b.idx===0);return b?b.x:null})()"


# F20: 인도자가 추천을 다시 저장하면 멤버가 다음에 열 때 바로 새 추천으로 · 받은 추천의 블록 id(점·#)가 그대로
def t_r2_f20(b):
    L = leader(b); M = member(b, L)
    sid = nid('st'); A = nid('i'); B = nid('i')
    publish(L, sid, 1, [item(A, '예수로 나의 구주 삼고'), item(B, '주 사랑합니다', 'D')])
    must(L, 'PUT', '/services/%s/stage-layout' % sid, {'teamId': L._team, 'device': 'tab-l', 'layout': lay(A, B, 0.3)})
    pm = page(M)
    until(pm, svc_js(sid) + "&&" + svc_js(sid) + ".published", what='멤버가 발행본을 받음')
    got = pm.evaluate("(%s.published.stageLayouts||{})['tab-l']||null" % svc_js(sid))
    if not got: fail('F20: 받은 발행본에 추천 조판이 없음')
    ids = [x['id'] for x in got['screens'][0]['blocks']]
    for want in ('h0', 'h1', 't0.0.0', 's0.1.40#5', 'x1a'):
        if want not in ids: fail('F20: 받은 추천 조판의 블록 id 가 바뀜 %s (%s 없음)' % (ids, want))
    if any('<' in i or '"' in i for i in ids): fail('F20: 이상한 블록 id 가 그대로 들어옴 %s' % ids)
    if not got.get('off') or got['off'][0]['s'] > 199: fail('F20: 화면 번호를 자르지 않음 %s' % got.get('off'))
    pm.evaluate("(id)=>CONTI.stageOpen(CONTI.S.services.find(x=>x.id===id),0)", sid)
    pm.wait_for_selector('#stageWrap .stgpage', timeout=15000)
    until(pm, HEAD_X + "===0.3", timeout=8000, what='멤버 무대가 첫 추천(0.3)으로 열림')
    pm.evaluate("CONTI.stageExit()")
    # 인도자가 추천을 고쳐 다시 저장 → 멤버가 다음에 열 때 그 자리에서 새 추천으로 (한 번 늦게 보이지 않는다)
    must(L, 'PUT', '/services/%s/stage-layout' % sid, {'teamId': L._team, 'device': 'tab-l', 'layout': lay(A, B, 0.6)})
    pm.evaluate("(id)=>CONTI.stageOpen(CONTI.S.services.find(x=>x.id===id),0)", sid)
    pm.wait_for_selector('#stageWrap .stgpage', timeout=15000)
    until(pm, HEAD_X + "===0.6", timeout=6000, what='다시 연 멤버 무대가 고친 추천(0.6)으로 바뀜')
    ids = [x['id'] for x in pm.evaluate("%s.published.stageLayouts['tab-l'].screens[0].blocks" % svc_js(sid))]
    if 't0.0.0' not in ids or any('<' in i for i in ids): fail('F20: 무대를 열 때 받은 추천 조판의 id %s' % ids)
    pm.evaluate("CONTI.stageExit()")
    # 내가 고친 조판이 있으면 추천이 바뀌어도 내 것 그대로
    must(M, 'PUT', '/me/prefs/stage/' + 'lay:%s~tab-l' % sid, {'value': lay(A, B, 0.45, extra=False)})
    pm.evaluate("()=>{CONTI.PREFS.at=0}")
    must(L, 'PUT', '/services/%s/stage-layout' % sid, {'teamId': L._team, 'device': 'tab-l', 'layout': lay(A, B, 0.7)})
    pm.evaluate("(id)=>CONTI.stageOpen(CONTI.S.services.find(x=>x.id===id),0)", sid)
    pm.wait_for_selector('#stageWrap .stgpage', timeout=15000)
    until(pm, HEAD_X + "===0.45", timeout=6000, what='내 조판으로 열림')
    pm.wait_for_timeout(1500)
    if pm.evaluate(HEAD_X) != 0.45: fail('F20: 내가 고친 조판을 추천이 덮음 %s' % pm.evaluate(HEAD_X))
    if pm.evaluate("%s.published.stageLayouts['tab-l'].screens[0].blocks[0].x" % svc_js(sid)) != 0.7: fail('F20: 새 추천을 받아 두지 않음')
    pm.evaluate("CONTI.stageExit()")
    if pm.evaluate("!!window.__xss"): fail('F20: 추천 조판의 id 로 스크립트가 돎')
    if pm._errs: fail('page errors: %s' % pm._errs)
    L.close(); M.close()
    print('R2 F20 ok')


# F22: 기기에 있는 곡이라도, 더 새 버전에서 더해진 영상의 메모는 그림자에 넣지도 지우지도 않는다
def t_r2_notes(b):
    L = leader(b); M = member(b, L)
    sid = nid('nm'); A = nid('iA'); m1 = nid('m1'); m2 = nid('m2')
    v1 = dict(item(A, '곡 A'), media=[{'id': m1, 'type': 'youtube', 'url': 'https://youtu.be/aaaaaaaaaaa', 'name': '영상1'}])
    publish(L, sid, 1, [v1])
    pm = page(M)
    until(pm, svc_js(sid), what='멤버가 v1 을 받음')
    v2 = dict(item(A, '곡 A'), media=v1['media'] + [{'id': m2, 'type': 'youtube', 'url': 'https://youtu.be/bbbbbbbbbbb', 'name': '영상2'}])
    publish(L, sid, 2, [v2])
    nm = nid('nM'); nl = nid('nL')
    must(M, 'POST', '/notes', {'teamId': L._team, 'serviceId': sid, 'notes': [{'id': nm, 'itemId': A, 'mediaId': m2, 't': 5, 'layer': 'mine', 'text': '영상2 메모'}]})
    must(L, 'POST', '/notes', {'teamId': L._team, 'serviceId': sid, 'notes': [{'id': nl, 'itemId': A, 'mediaId': m2, 't': 9, 'layer': 'leader', 'text': '인도자 영상2 메모'}]})
    pm.route(re.compile(r'/api/services\?team='), lambda r: r.abort())
    pm.goto(URL + '#/view/' + sid); pm.wait_for_timeout(3500)
    if pm.evaluate("%s.items[0].media.length" % svc_js(sid)) != 1: fail('전제 실패: 기기가 이미 v2 를 받음')
    if nm not in [n['id'] for n in notes_on_server(M, sid)]: fail('F22: v1 기기가 v2 에서 더해진 영상의 메모를 서버에서 지움')
    if pm.evaluate("(CONTI.S.noteShadow[%s]||[]).some(x=>x.id===%s)" % (json.dumps(sid), json.dumps(nm))): fail('F22: 이 기기에 없는 영상의 메모가 그림자에 들어감')
    # 예전 버전이 남긴 그림자(없는 영상의 메모)가 있어도 지우지 않고 그림자에서만 뺀다
    pm.evaluate("async ([id,nm,A,m2])=>{CONTI.S.noteShadow[id].push({id:nm,itemId:A,mediaId:m2});await CONTI.SYNC.pushNotes(CONTI.S.services.find(x=>x.id===id))}", [sid, nm, A, m2])
    if nm not in [n['id'] for n in notes_on_server(M, sid)]: fail('F22: 오염된 그림자로 없는 영상의 메모를 지움')
    if pm.evaluate("(CONTI.S.noteShadow[%s]||[]).some(x=>x.id===%s)" % (json.dumps(sid), json.dumps(nm))): fail('F22: 없는 영상의 그림자를 치우지 않음')
    # 인도자 기기(v1 에 머문)도 팀 전체 메모를 지우지 않는다
    pl = page(L)
    until(pl, svc_js(sid) + "&&" + svc_js(sid) + ".published", what='인도자 기기에 콘티')
    pl.route(re.compile(r'/api/services\?team='), lambda r: r.abort())
    pl.evaluate("""(id)=>{const s=CONTI.S.services.find(x=>x.id===id);s.items[0].media=s.items[0].media.slice(0,1);
      s.published.items[0].media=s.published.items[0].media.slice(0,1);s.published.version=1;s.version=1;if(CONTI.S.noteShadow)delete CONTI.S.noteShadow[id];CONTI.save()}""", sid)
    pl.goto(URL + '#/view/' + sid); pl.wait_for_timeout(3500)
    if nl not in [n['id'] for n in notes_on_server(L, sid)]: fail('F22: v1 인도자 기기가 v2 영상의 인도자 메모를 지움')
    # 받은 뒤에는 붙고, 그 영상이 있는 기기에서 지우면 서버에서도 지워진다
    pm.unroute(re.compile(r'/api/services\?team='))
    pm.evaluate("async (id)=>{await CONTI.SYNC.pullServices();await CONTI.SYNC.pullNotes(CONTI.S.services.find(x=>x.id===id))}", sid)
    if not pm.evaluate("%s.items[0].media[1].notes.some(n=>n.id===%s)" % (svc_js(sid), json.dumps(nm))): fail('v2 를 받은 뒤 영상2 메모가 안 붙음')
    pm.evaluate("async (id)=>{const s=CONTI.S.services.find(x=>x.id===id);s.items[0].media[1].notes=[];await CONTI.SYNC.pushNotes(s)}", sid)
    if nm in [n['id'] for n in notes_on_server(M, sid)]: fail('F22: 영상이 있는 기기에서 지운 메모가 서버에 남음')
    for p_ in (pm, pl):
        if p_._errs: fail('page errors: %s' % p_._errs)
    L.close(); M.close()
    print('R2 F22 ok')


# F73 · F77: 올리는 사이 팀을 바꾸거나 콘티를 지워도 옛 팀 것이 새 팀으로 가지 않고, 지운 초안이 살아나지 않는다
def t_r2_team(b):
    L = leader(b, '에이팀')
    tA = L._team
    tB = must(L, 'POST', '/teams', {'name': '비팀' + TAG, 'myName': '인도', 'session': '인도자'})['teamId']
    pl = page(L)
    if pl.evaluate("CONTI.S.team.id") != tA: team_switch(pl, tA)
    pl.wait_for_timeout(1500)
    lib_titles = lambda tid: [x.get('title') for x in must(L, 'GET', '/library?team=' + tid)['songs']]
    song_titles = lambda tid: [x.get('title') for x in must(L, 'GET', '/songs?team=' + tid)['songs']]
    blob_on = lambda tid, bid: bid in (must(L, 'GET', '/blobs?team=%s&ids=%s' % (tid, bid))['blobs'] or {})
    # (1) POST /songs 응답을 기다리는 사이 B 로 → B 의 곡 목록(S.songs)에 넣지 않는다
    posts = []
    pl.on('request', lambda r: posts.append(1) if r.method == 'POST' and r.url.endswith('/api/songs') else None)
    t2 = 'A팀 곡 둘 ' + TAG
    pl.evaluate("""(t)=>{CONTI.S.services.push({id:'s2'+Date.now(),name:'A 예배 2',date:'2099-08-09',notice:'',version:0,published:null,editedAt:Date.now(),
       items:[{id:'j'+Date.now(),title:t,key:'A',form:'',pieces:[],media:[],notes:[]}]})}""", t2)
    pl.evaluate(SLOW, [{'re': '/api/songs$', 'method': 'POST', 'ms': 2500}])
    pl.evaluate("()=>{clearTimeout(CONTI.pushSongs.retry);window.__ps=CONTI.pushSongs()}")
    pl.wait_for_timeout(600)
    team_switch(pl, tB)
    pl.wait_for_timeout(3500)
    pl.evaluate("()=>{window.__slow=[]}")
    if pl.evaluate("CONTI.S.songs.some(x=>x.title===%s)" % json.dumps(t2)): fail('F73: A 팀 곡이 B 팀 기기 곡 목록(S.songs)에 들어감')
    if t2 in song_titles(tB): fail('F73: A 팀 곡이 B 팀 서버에')
    if not posts or t2 not in song_titles(tA): fail('전제 실패: 곡 만들기 요청이 A 팀으로 안 감 (%d)' % len(posts))
    team_switch(pl, tA); pl.wait_for_timeout(800)
    # (2) pushSongs: 새 곡의 악보를 올리는 사이 B 로 → 곡이 B 에 만들어지지 않고, 악보는 A 로 올라간다
    b1 = nid('bS'); t1 = 'A팀 새 곡 ' + TAG
    pl.evaluate("""async ([sid,bid,t])=>{await CONTI.IDB.put('blobs',bid,new Blob([new Uint8Array(3000).fill(5)],{type:'image/png'}));
      CONTI.S.services.push({id:sid,name:'A 예배',date:'2099-08-02',notice:'',version:0,published:null,editedAt:Date.now(),
       items:[{id:'i'+Date.now(),title:t,key:'G',form:'',pieces:[{id:'p'+Date.now(),blob:bid,markers:[]}],media:[],notes:[]}]})}""", [nid('sA'), b1, t1])
    pl.evaluate(SLOW, [{'re': '/api/blobs/' + b1, 'method': 'POST', 'ms': 2500}])
    pl.evaluate("()=>{clearTimeout(CONTI.pushSongs.retry);window.__ps=CONTI.pushSongs()}")
    pl.wait_for_timeout(600)
    team_switch(pl, tB)
    pl.wait_for_timeout(4000)
    if t1 in song_titles(tB): fail('F73: 올리는 사이 팀을 바꿨더니 A 팀 곡이 B 팀에 만들어짐')
    if blob_on(tB, b1) or not blob_on(tA, b1): fail('F73: A 팀 악보가 B 팀으로 올라감')
    if pl.evaluate("CONTI.S.songs.some(x=>x.title===%s)" % json.dumps(t1)): fail('F73: A 팀 곡이 B 팀 목록에')
    team_switch(pl, tA); pl.wait_for_timeout(800)
    # (3) pushLibrary: 파일을 올리는 사이 B 로 → A 라이브러리 곡이 B 에 들어가지 않는다
    b3 = nid('bL'); t3 = 'A팀 보관 곡 ' + TAG
    pl.evaluate("""async ([bid,t])=>{await CONTI.IDB.put('blobs',bid,new Blob([new Uint8Array(3000).fill(6)],{type:'image/png'}));
      CONTI.S.library.push({id:'l'+Date.now(),title:t,key:'C',pieces:[{id:'q'+Date.now(),blob:bid,markers:[]}],media:[],dirty:true})}""", [b3, t3])
    pl.evaluate(SLOW, [{'re': '/api/blobs/' + b3, 'method': 'POST', 'ms': 2500}])
    pl.evaluate("()=>{window.__pl=CONTI.SYNC.pushLibrary()}")
    pl.wait_for_timeout(600)
    team_switch(pl, tB)
    pl.wait_for_timeout(4000)
    pl.evaluate("()=>{window.__slow=[]}")
    if t3 in lib_titles(tB): fail('F73: A 팀 라이브러리 곡이 B 팀 서버 라이브러리에 들어감')
    if blob_on(tB, b3): fail('F73: A 팀 라이브러리 파일이 B 팀으로 올라감')
    if pl._errs: fail('page errors: %s' % pl._errs)
    L.close()
    print('R2 F73 ok')


def t_r2_draft(b):
    L = leader(b, '에이팀')
    tA = L._team
    tB = must(L, 'POST', '/teams', {'name': '비팀' + TAG, 'myName': '인도', 'session': '인도자'})['teamId']
    pl = page(L)
    if pl.evaluate("CONTI.S.team.id") != tA: team_switch(pl, tA)
    pl.wait_for_timeout(1500)
    # (4) F77: 초안을 올리는 사이 또 고치고(다시 밀기 예약) 팀을 바꾸면 — 다시 밀기가 B 팀에 A 초안을 쓰지 않는다
    d1 = nid('dA')
    pl.evaluate("(id)=>{CONTI.S.services.push({id,name:'팀A 비밀 예배 1',date:'2099-09-06',notice:'',version:0,published:null,items:[],editedAt:Date.now()})}", d1)
    pl.evaluate(SLOW, [{'re': '/api/services/' + d1 + '/draft', 'method': 'PUT', 'ms': 2500}])
    pl.evaluate("(id)=>{const s=CONTI.S.services.find(x=>x.id===id);window.__pd=CONTI.SYNC.pushDraft(s)}", d1)
    pl.wait_for_timeout(300)
    pl.evaluate("(id)=>{const s=CONTI.S.services.find(x=>x.id===id);s.name='팀A 비밀 예배 2';s.editedAt=Date.now();CONTI.SYNC.pushDraft(s)}", d1)
    team_switch(pl, tB)
    pl.wait_for_timeout(4500)
    pl.evaluate("()=>{window.__slow=[]}")
    st, j = call(L, 'GET', '/services/%s/draft?team=%s' % (d1, tB))
    if st == 200 and j and j.get('doc'): fail('F77: 팀을 바꾼 뒤 다시 밀기가 A 팀 초안을 B 팀에 씀')
    team_switch(pl, tA); pl.wait_for_timeout(800)
    # (5) 올리는 사이 콘티를 지우면 다시 밀기가 지운 초안을 되살리지 않는다
    d2 = nid('dD')
    pl.evaluate("(id)=>{CONTI.S.services.push({id,name:'지울 예배',date:'2099-09-13',notice:'',version:0,published:null,items:[],editedAt:Date.now()})}", d2)
    pl.evaluate(SLOW, [{'re': '/api/services/' + d2 + '/draft', 'method': 'PUT', 'ms': 2500}])
    pl.evaluate("(id)=>{const s=CONTI.S.services.find(x=>x.id===id);window.__pd=CONTI.SYNC.pushDraft(s)}", d2)
    pl.wait_for_timeout(300)
    pl.evaluate("(id)=>{const s=CONTI.S.services.find(x=>x.id===id);s.name='지울 예배 2';s.editedAt=Date.now();CONTI.SYNC.pushDraft(s)}", d2)
    pl.wait_for_timeout(300)
    pl.evaluate("async (id)=>{const S=CONTI.S;S.services=S.services.filter(s=>s.id!==id);S.dropped=(S.dropped||[]).concat(id);CONTI.save();await CONTI.SYNC.deleteService(id)}", d2)
    pl.wait_for_timeout(5000)
    pl.evaluate("()=>{window.__slow=[]}")
    drafts = [d['id'] for d in (must(L, 'GET', '/services?team=' + tA).get('drafts') or [])]
    if d2 in drafts: fail('F77: 올리는 사이 지운 초안이 서버에 되살아남')
    if pl._errs: fail('page errors: %s' % pl._errs)
    L.close()
    print('R2 F77 ok')


# F78: 다른 순서로 겹친 올리기 · 늦게 온 '서버에 없음' 답이 방금 올린 파일을 또 올리지 않는다
def t_r2_blobs(b):
    L = leader(b)
    pl = page(L)
    x = nid('bx'); y = nid('by'); z = nid('bz')
    # 올리기 요청은 1초 늦게 떠난다 (느린 망). 그 위에 SLOW 로 답을 늦춘다
    pl.evaluate("""()=>{window.__posts={};const f=window.fetch;
      window.fetch=function(u,o){const a=arguments;const m=String(u).match(/\\/api\\/blobs\\/([^?/]+)\\?/);
        if(m&&o&&o.method==='POST'){window.__posts[m[1]]=(window.__posts[m[1]]||0)+1;return new Promise(ok=>setTimeout(ok,1000)).then(()=>f.apply(this,a))}return f.apply(this,a)}}""")
    pl.evaluate(SLOW, [])
    n = pl.evaluate("""async ([x,y])=>{for(const id of [x,y])await CONTI.IDB.put('blobs',id,new Blob([new Uint8Array(400000).fill(4)],{type:'audio/mp4'}));
      window.__posts={};const A={pieces:[],media:[{id:'a',type:'audio',blob:x}]},B={pieces:[],media:[{id:'b',type:'audio',blob:y}]};
      await Promise.all([CONTI.SYNC.ensureBlobs([A,B],true),CONTI.SYNC.ensureBlobs([B,A],true)]);return window.__posts}""", [x, y])
    if n.get(x) != 1 or n.get(y) != 1: fail('F78: 순서가 다른 두 올리기가 같은 파일을 또 올림 %s' % n)
    n = pl.evaluate("""async (z)=>{await CONTI.IDB.put('blobs',z,new Blob([new Uint8Array(400000).fill(2)],{type:'audio/mp4'}));window.__posts={};
      const it=[{pieces:[],media:[{id:'c',type:'audio',blob:z}]}];const p1=CONTI.SYNC.ensureBlobs(it,true);
      // 두 번째 호출의 '서버에 있나' 답은 첫 호출이 올리기를 마친 뒤에 온다
      window.__slow=[{re:'/api/blobs\\\\?team=',method:'GET',ms:2500}];const p2=CONTI.SYNC.ensureBlobs(it,true);window.__slow=[];
      await Promise.all([p1,p2]);return window.__posts}""", z)
    if n.get(z) != 1: fail('F78: 늦게 온 답 때문에 방금 올린 파일을 또 올림 %s' % n)
    n = pl.evaluate("async (z)=>{window.__posts={};await CONTI.SYNC.ensureBlobs([{pieces:[],media:[{id:'c',type:'audio',blob:z}]}],true);return window.__posts}", z)
    if n.get(z): fail('F78: 서버에 있는 파일을 또 올림 %s' % n)
    if pl._errs: fail('page errors: %s' % pl._errs)
    L.close()
    print('R2 F78 ok')


# F76: 발행 대기(못 올린 발행)가 409 로 돌아와도 고친 것이 남는다 · 버전만 올라간 옛 콘티는 새 발행본을 받는다
def t_r2_f76(b):
    L = leader(b)
    sid = nid('pp'); X = nid('iX')
    publish(L, sid, 1, [item(X, '곡 X', 'G')])
    pl = page(L)
    until(pl, svc_js(sid) + "&&" + svc_js(sid) + ".published", what='v1 받음')
    # 이 기기: 키를 A 로, 곡 Y 를 더해 발행했는데 올리다 끊겨 발행 대기로 남았다 (발행 창이 남기는 모양)
    pl.evaluate("""(id)=>{const s=CONTI.S.services.find(x=>x.id===id);s.items[0].key='A';s.items.push({id:'y'+Date.now(),title:'곡 Y',key:'D',form:'',pieces:[],media:[],notes:[]});
      s.version=2;s.editedAt=Date.now();s.published={...s.published,version:2,at:Date.now(),items:JSON.parse(JSON.stringify(s.items)).map(it=>({...it,notes:undefined}))};s.pubPending=true;CONTI.save()}""", sid)
    publish(L, sid, 2, [item(X, '곡 X', 'G')], notice='PC 에서 고침')   # 그 사이 PC 가 v2 를 발행
    pl.evaluate("CONTI.SYNC.pushPending()"); pl.wait_for_timeout(1500)
    st = pl.evaluate("(()=>{const s=%s;return {key:s.items[0].key,n:s.items.length,pv:s.published.version,v:s.version,pend:!!s.pubPending,notice:s.published.notice}})()" % svc_js(sid))
    if st['key'] != 'A' or st['n'] != 2: fail('F76: 발행 대기가 409 로 돌아오며 고친 것이 덮임 %s' % st)
    if st['pv'] != 2 or st['v'] != 3 or st['pend'] or st['notice'] != 'PC 에서 고침': fail('F76: 409 뒤 상태 %s' % st)
    # 예전 앱이 발행 창을 열기만 해서 버전만 올라간 콘티: 고친 게 없으니 다른 기기의 새 발행본을 받는다
    sid2 = nid('pv')
    publish(L, sid2, 1, [item(nid('i'), '곡', 'G')])
    pl.evaluate("CONTI.SYNC.pullServices()"); until(pl, svc_js(sid2) + "&&" + svc_js(sid2) + ".published", what='v1 받음')
    pl.evaluate("(id)=>{const s=CONTI.S.services.find(x=>x.id===id);s.version=s.published.version+1;CONTI.save()}", sid2)
    publish(L, sid2, 2, [item(nid('i'), '곡 (PC)', 'C')])
    pl.evaluate("CONTI.SYNC.pullServices()"); pl.wait_for_timeout(1500)
    st = pl.evaluate("(()=>{const s=%s;return {t:s.items[0].title,v:s.version,pv:s.published.version}})()" % svc_js(sid2))
    if st['t'] != '곡 (PC)' or st['v'] != 2: fail('F76: 버전만 올라간 콘티가 새 발행본을 안 받음 %s' % st)
    if pl._errs: fail('page errors: %s' % pl._errs)
    L.close()
    print('R2 F76 ok')


# G31: 한도는 바이트로 잰다 — 한글이 많아 글자 수는 한도 아래여도 바이트가 넘으면 파일·요청을 보내지 않고 알린다
def t_r2_g31(b):
    L = leader(b)
    sid = nid('kb')
    publish(L, sid, 1, [item(nid('i'), '가사 많은 곡')])
    pl = page(L)
    until(pl, svc_js(sid), what='콘티 받음')
    sent = []
    pl.on('request', lambda r: sent.append(r.method + ' ' + r.url) if r.method == 'PUT' and re.search(r'/api/services/%s(/draft)?$' % sid, r.url) else None)
    # 한글 140만 자: 글자 수 1.4M(한도 4M 아래) · UTF-8 4.2MB(한도 위)
    pl.evaluate("(id)=>{const s=CONTI.S.services.find(x=>x.id===id);s.items[0].songNote='가'.repeat(1400000);s.version=s.published.version+1;s.editedAt=Date.now()}", sid)
    pl.evaluate("(id)=>CONTI.SYNC.pushDraft(CONTI.S.services.find(x=>x.id===id))", sid)
    pl.wait_for_timeout(500)
    if sent: fail('G31: 바이트로는 한도를 넘는 초안을 보냄 %s' % sent)
    msgs = []
    pl.on('dialog', lambda d: msgs.append(d.message))
    pl.goto(URL + '#/edit/' + sid); pl.wait_for_selector('[data-act="publish"]', timeout=15000)
    pl.click('[data-act="publish"]'); pl.wait_for_selector('#pubOnly'); pl.click('#pubOnly')
    pl.wait_for_timeout(2500)
    if [x for x in sent if '/draft' not in x]: fail('G31: 바이트로는 한도를 넘는 발행을 보냄 %s' % sent)
    m = [x for x in msgs if 'MB' in x]
    if not m or not re.search(r'\((4\.[1-9]|[5-9])', m[0]): fail('G31: 알린 크기가 한도 위로 나오지 않음 %s' % msgs)
    st = pl.evaluate("(()=>{const s=%s;return {pv:s.published.version,pend:!!s.pubPending}})()" % svc_js(sid))
    if st['pv'] != 1 or st['pend']: fail('G31: 너무 큰 발행이 남음 %s' % st)
    if pl._errs: fail('page errors: %s' % pl._errs)
    L.close()
    print('R2 G31 ok')


# F80: 애플 새 계정 동의 창을 취소하고 다시 들어와도 애플이 준 이름으로 가입 (예전 앱의 가입은 서버 SOCIAL_JS 에서)
def t_r2_f80(b):
    c = b.new_context(viewport={'width': 430, 'height': 900}, service_workers='block')
    pg = c.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)[:300]))
    sent = []

    def social(route):
        body = json.loads(route.request.post_data or '{}'); sent.append(body)
        if not body.get('agreedAt'):
            return route.fulfill(status=428, content_type='application/json', body=json.dumps({'error': 'needs_consent', 'message': '처음 오셨네요'}))
        return route.fulfill(status=503, content_type='application/json', body=json.dumps({'error': 'no_social', 'message': '시험 끝'}))
    pg.route(re.compile(r'/api/auth/social$'), social)
    pg.route(re.compile(r'/api/auth/providers$'), lambda r: r.fulfill(status=200, content_type='application/json', body=json.dumps({'apple': 'audit.service'})))
    b64 = lambda o: base64.urlsafe_b64encode(json.dumps(o).encode()).decode().rstrip('=')
    tok = b64({'alg': 'RS256'}) + '.' + b64({'sub': 'apple-' + TAG, 'iss': 'https://appleid.apple.com'}) + '.sig'
    other = b64({'alg': 'RS256'}) + '.' + b64({'sub': 'apple-other-' + TAG}) + '.sig'
    # 애플 웹 로그인 흉내: 이름은 그 계정의 첫 허락 때만 준다 (window.__appleTok 으로 계정을 고른다)
    pg.route(re.compile(r'appleid\.cdn-apple\.com/.*appleid\.auth\.js'), lambda r: r.fulfill(status=200, content_type='text/javascript', body=
        "window.__appleSeen={};window.AppleID={auth:{init(){},async signIn(){const t=window.__appleTok;const first=!window.__appleSeen[t];window.__appleSeen[t]=1;"
        "return {authorization:{id_token:t},user:first?{name:{firstName:'길동',lastName:'홍'}}:undefined}}}}"))
    pg.goto(URL); pg.wait_for_selector('#aBtn', timeout=15000)
    pg.evaluate("(t)=>{window.__appleTok=t}", tok)
    pg.click('#aBtn')
    pg.wait_for_selector('#scAgree', timeout=5000)
    if sent[-1].get('name') != '홍길동': fail('전제 실패: 첫 허락에 이름이 안 감 %s' % sent[-1])
    pg.click('#modal [data-close]'); pg.wait_for_timeout(200)
    # 다시 누르면 애플은 이름을 주지 않는다
    pg.click('#aBtn')
    pg.wait_for_selector('#scAgree', timeout=5000)
    pg.check('#scAgree'); pg.click('#scOk'); pg.wait_for_timeout(800)
    if not sent[-1].get('agreedAt') or sent[-1].get('name') != '홍길동': fail('F80: 취소 뒤 다시 가입할 때 애플 이름이 빠짐 %s' % sent[-1])
    # 다른 애플 계정(이미 허락해 이름을 안 주는)에는 그 이름을 쓰지 않는다
    pg.evaluate("(t)=>{window.__appleTok=t;window.__appleSeen[t]=1}", other)
    pg.click('#aBtn'); pg.wait_for_selector('#scAgree', timeout=5000)
    if sent[-1].get('name'): fail('F80: 다른 계정에 앞사람 이름을 씀 %s' % sent[-1])
    if errs: fail('page errors: %s' % errs)
    c.close()
    print('R2 F80 ok')


# F81: 로그아웃 뒤 같은 사람이 같은 창에서 다시 로그인하면 알림을 다시 등록한다
PUSH_STUB = """(()=>{const ep=%s;const sub={endpoint:ep,options:{applicationServerKey:null},toJSON(){return {endpoint:ep,keys:{p256dh:'k',auth:'a'}}},unsubscribe:async()=>true};
  const pm={getSubscription:async()=>sub,subscribe:async()=>sub};
  Object.defineProperty(navigator,'serviceWorker',{configurable:true,value:{ready:Promise.resolve({pushManager:pm}),register:async()=>({}),addEventListener(){},getRegistration:async()=>null,getRegistrations:async()=>[],controller:null}});
  try{Object.defineProperty(Notification,'permission',{configurable:true,get:()=>'granted'})}catch(e){}})()"""


def t_r2_push(b):
    c = b.new_context(viewport=IPAD)
    u = nid('pu')
    must(c, 'POST', '/auth/signup', {'username': u, 'password': 'secret1', 'name': '알림', 'agreedAt': '2026-09-24T00:00:00Z'})
    must(c, 'POST', '/teams', {'name': '알림팀' + TAG, 'myName': '알림', 'session': '인도자'})
    ep = 'https://push.example/' + nid('re')
    pg = c.new_page(); pg._errs = []; pg.on('pageerror', lambda e: pg._errs.append(str(e)[:300]))
    pg.on('dialog', lambda d: d.accept())
    pg.add_init_script(PUSH_STUB % json.dumps(ep))
    subs = []
    pg.on('request', lambda r: subs.append(1) if r.url.endswith('/api/push/subscribe') else None)
    pg.goto(URL + '#/home'); pg.wait_for_function("window.CONTI&&CONTI.S.team.id", timeout=15000)

    def wait_subs(n0):
        t0 = time.time()
        while len(subs) <= n0 and time.time() - t0 < 10: pg.wait_for_timeout(200)
        return len(subs) > n0

    def rows():
        r = subprocess.run(['docker', 'exec', 'conti-pg', 'psql', '-U', 'postgres', '-tAc', "select count(*) from push_subs where endpoint='%s'" % ep], capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else None
    if not wait_subs(0): fail('전제 실패: 홈에서 알림을 등록하지 않음')
    pg.wait_for_timeout(500)
    if rows() not in (None, '1'): fail('전제 실패: 구독 줄 %s' % rows())
    pg.goto(URL + '#/settings'); pg.wait_for_selector('.setpane', timeout=10000)
    pg.click('[data-act="set-tab"][data-t="app"]'); pg.wait_for_selector('#sLogout', timeout=10000)
    pg.click('#sLogout'); pg.wait_for_selector('#lgUser', timeout=10000)
    if rows() not in (None, '0'): fail('F81: 로그아웃 뒤 구독이 남음 %s' % rows())
    n0 = len(subs)
    pg.fill('#lgUser', u); pg.fill('#lgPass', 'secret1'); pg.click('[data-act="lg-submit"]')
    pg.wait_for_function("window.CONTI&&CONTI.NET.user", timeout=10000)
    if not wait_subs(n0): fail('F81: 같은 사람이 다시 로그인했는데 알림을 다시 등록하지 않음')
    pg.wait_for_timeout(500)
    if rows() not in (None, '1'): fail('F81: 다시 로그인한 뒤 구독 줄 %s' % rows())
    if pg._errs: fail('page errors: %s' % pg._errs)
    c.close()
    print('R2 F81 ok')


# G15: 받는 대로 다시 그릴 때 목록이 깜빡이지 않고(떠오르는 효과 없음), 누르고 있는 동안에는 다시 그리지 않는다
def t_r2_g15(b):
    L = leader(b)
    ids = [nid('g') for _ in range(14)]
    for k, i in enumerate(ids):
        publish(L, i, 1, [item(nid('i'), '곡 %d' % k)], name='예배 %d' % k, date='2099-10-%02d' % (k + 1))
    M = member(b, L, viewport={'width': 430, 'height': 900})
    pm = M.new_page(); pm._errs = []; pm.on('pageerror', lambda e: pm._errs.append(str(e)[:300]))
    pm.add_init_script("""(()=>{const f=window.fetch;window.fetch=function(u,o){const p=f.apply(this,arguments);
      if(/\\/api\\/services\\/[^/?]+\\?team=/.test(String(u)))return p.then(r=>new Promise(ok=>setTimeout(()=>ok(r),500)));return p}})()""")
    pm.goto(URL)
    t0 = time.time(); st = None
    while time.time() - t0 < 20:
        st = pm.evaluate("()=>({rows:document.querySelectorAll('.svcrow').length,n:window.CONTI?CONTI.S.services.length:0})")
        if st['rows'] > 0: break
        pm.wait_for_timeout(100)
    if not st or not st['rows'] or st['n'] >= len(ids): fail('전제 실패: 받는 중에 목록이 안 보임 %s' % st)
    if pm.evaluate("document.querySelectorAll('#app .svcrow.rise').length"): fail('G15: 받는 중 다시 그린 목록이 떠오르는 효과로 깜빡임')
    # 누르고 있는 동안에는 그 줄을 바꾸지 않는다
    pm.evaluate("()=>{const r=document.querySelector('.svcrow');r.__held=1;window.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}))}")
    n1 = pm.evaluate("CONTI.S.services.length")
    pm.wait_for_timeout(2500)
    held = pm.evaluate("!!(document.querySelector('.svcrow')||{}).__held")
    n2 = pm.evaluate("CONTI.S.services.length")
    pm.evaluate("()=>window.dispatchEvent(new PointerEvent('pointerup',{bubbles:true}))")
    if n2 == n1: fail('전제 실패: 누르는 동안 받은 것이 없음 (%d)' % n1)
    if not held: fail('G15: 누르고 있는 동안 목록을 다시 그림')
    until(pm, "CONTI.S.services.length>=%d&&document.querySelectorAll('.svcrow').length>=%d" % (len(ids), len(ids)), timeout=20000, what='결국 전부 보임')
    if pm._errs: fail('page errors: %s' % pm._errs)
    L.close(); M.close()
    print('R2 G15 ok')


# ======== 3차 ========
# F76: 버전만 올라간 콘티인데 발행 뒤 곡이 라이브러리에 이어져(pushSongs) 초안 곡에만 songId·arrId·bs 등이 붙은 경우도
# '고친 것'으로 보지 않고 다른 기기의 새 발행본을 받는다 (전에는 v3 '수정 중'으로 남아 PC 의 v2 를 영영 안 받았다)
def t_r3_f76(b):
    L = leader(b)
    sid = nid('pl'); X = nid('iX'); title = '이을 곡 ' + TAG
    publish(L, sid, 1, [item(X, title, 'G')])
    pl = page(L)
    until(pl, svc_js(sid) + "&&" + svc_js(sid) + ".published", what='v1 받음')
    pl.evaluate("()=>{clearTimeout(CONTI.pushSongs.retry);return CONTI.pushSongs()}")
    until(pl, svc_js(sid) + ".items[0].arrId", what='곡이 라이브러리에 이어짐')
    if pl.evaluate(svc_js(sid) + ".published.items[0].arrId"): fail('전제 실패: 발행본에도 arrId 가 있음')
    # 예전 앱이 발행 창을 열기만 해서 버전만 올라간 모양
    pl.evaluate("(id)=>{const s=CONTI.S.services.find(x=>x.id===id);s.version=s.published.version+1;CONTI.save()}", sid)
    publish(L, sid, 2, [item(X, title, 'C')], notice='PC 에서')
    pl.evaluate("CONTI.SYNC.pullServices()")
    until(pl, svc_js(sid) + ".published.version===2", what='v2 받음')
    pl.wait_for_timeout(500)
    st = pl.evaluate("(()=>{const s=%s;return {key:s.items[0].key,v:s.version,pv:s.published.version}})()" % svc_js(sid))
    if st['key'] != 'C' or st['v'] != 2: fail('F76: 라이브러리에 이은 것만 다른 콘티가 새 발행본을 안 받음 %s' % st)
    # 진짜로 고친 것(키)은 여전히 지킨다
    pl.evaluate("(id)=>{const s=CONTI.S.services.find(x=>x.id===id);s.items[0].key='E';s.version=s.published.version+1;s.editedAt=Date.now();CONTI.save()}", sid)
    publish(L, sid, 3, [item(X, title, 'F')], notice='PC 에서 또')
    pl.evaluate("CONTI.SYNC.pullServices()")
    until(pl, svc_js(sid) + ".published.version===3", what='v3 받음')
    pl.wait_for_timeout(500)
    st = pl.evaluate("(()=>{const s=%s;return {key:s.items[0].key,v:s.version}})()" % svc_js(sid))
    if st['key'] != 'E' or st['v'] != 4: fail('F76: 고친 키가 새 발행본에 덮임 %s' % st)
    if pl._errs: fail('page errors: %s' % pl._errs)
    L.close()
    print('R3 F76 ok')


# F73: 쌓아 둔 곡 수정(pushDirtySongs)을 보내는 사이 팀을 바꿔도 남은 편곡 수정은 그 곡의 팀으로 간다 (새 팀 id 로 보내 404 로 헛돌던 것)
def t_r3_dirty(b):
    L = leader(b, '에이팀')
    tA = L._team
    tB = must(L, 'POST', '/teams', {'name': '비팀' + TAG, 'myName': '인도', 'session': '인도자'})['teamId']
    title = '쌓인 곡 ' + TAG
    sg = must(L, 'POST', '/songs', {'teamId': tA, 'title': title, 'origKey': 'G'})['song']
    aid = sg['arrangements'][0]['id']
    pl = page(L)
    if pl.evaluate("CONTI.S.team.id") != tA: team_switch(pl, tA)
    until(pl, "CONTI.S.songs.some(x=>x.id===%s)" % json.dumps(sg['id']), what='곡 받음')
    arr_teams = []
    pl.on('request', lambda r: arr_teams.append(json.loads(r.post_data or '{}').get('teamId')) if r.method == 'PATCH' and '/api/arrangements/' in r.url else None)
    pl.evaluate("""([sid,aid])=>{const s=CONTI.S.songs.find(x=>x.id===sid);s.pend={songNote:'메모'};s.pendArr={[aid]:{key:'D'}};s.dirty=true;CONTI.save()}""", [sg['id'], aid])
    pl.evaluate(SLOW, [{'re': '/api/songs/', 'method': 'PATCH', 'ms': 2500}])
    pl.evaluate("CONTI.SYNC.schedulePush()")
    pl.wait_for_timeout(3700)   # 3초 뒤 곡 PATCH 가 나가고 답을 기다리는 중
    team_switch(pl, tB)
    pl.wait_for_timeout(3500)
    pl.evaluate("()=>{window.__slow=[]}")
    if arr_teams != [tA]: fail('F73: 팀을 바꾼 뒤 편곡 수정이 다른 팀 id 로 감 %s' % arr_teams)
    keys = [a.get('key') for s in must(L, 'GET', '/songs?team=' + tA)['songs'] if s['id'] == sg['id'] for a in (s.get('arrangements') or [])]
    if 'D' not in keys: fail('F73: A 팀 편곡에 수정이 안 들어감 %s' % keys)
    if pl._errs: fail('page errors: %s' % pl._errs)
    L.close()
    print('R3 F73 ok')


# ======== 4차 ========
# F73: 옛 팀(A)의 받기에서 초안 받기가 실패(catch)했고 A 에 발행본이 없으면, 그 사이 바꾼 새 팀(B)의 목록에서
# 'A 서버 목록에 없다'며 B 의 발행 콘티를 지우던 것 (고쳐 두고 아직 못 올린 것은 사라졌다)
def t_r4_pull(b):
    L = leader(b, '에이팀')
    tA = L._team
    tB = must(L, 'POST', '/teams', {'name': '비팀' + TAG, 'myName': '인도', 'session': '인도자'})['teamId']
    sB = nid('sB'); d = nid('dA')
    must(L, 'PUT', '/services/' + sB, {'teamId': tB, 'doc': {'id': sB, 'name': 'B 예배', 'date': '2099-02-01', 'notice': '', 'version': 1, 'items': [item(nid('i'), 'B곡')]}})
    pl = page(L)
    # A 의 초안 받기(draft=1)는 2.5초 붙잡았다가 500 으로 돌려준다 · A 에서 시작한 받기가 어떻게 끝나는지 적는다
    pl.evaluate("""(d)=>{window.__failN=0;const f=window.fetch;window.fetch=function(u,o){const s=String(u);
       if(s.includes('/api/services/'+d+'?')&&s.includes('draft=1'))return new Promise(ok=>setTimeout(()=>{window.__failN++;
        ok(new Response(JSON.stringify({error:'x',message:'boom'}),{status:500,headers:{'content-type':'application/json'}}))},2500));
       return f.apply(this,arguments)};
      window.__log=[];const o=CONTI.SYNC.pullServicesOnce;CONTI.SYNC.pullServicesOnce=async function(){const tid=CONTI.S.team.id;
       const r=await o.apply(this,arguments);window.__log.push({tid,endTid:CONTI.S.team.id,r,n:CONTI.S.services.length});return r}}""", d)
    if pl.evaluate("CONTI.S.team.id") != tB: team_switch(pl, tB)
    until(pl, svc_js(sB) + "&&" + svc_js(sB) + ".published", what='B 콘티 받음')
    pl.wait_for_timeout(1000)
    # A 에는 발행본 없이 다른 기기의 초안만 있다
    must(L, 'PUT', '/services/%s/draft' % d, {'teamId': tA, 'doc': {'id': d, 'name': 'A 초안', 'date': '2099-02-08', 'notice': '', 'version': 0, 'items': [item(nid('i'), 'A곡')], 'editedAt': int(time.time() * 1000)}})
    team_switch(pl, tA)
    pl.evaluate("()=>{window.__pa=CONTI.SYNC.pullServices()}")   # 전환이 부른 받기와 겹치면 같은 것을 돌려받는다
    pl.wait_for_timeout(700)
    team_switch(pl, tB)
    # B 에서 발행 뒤 고쳐 둔 것 (A 받기가 실패로 끝나기 전)
    pl.evaluate("(id)=>{const s=CONTI.S.services.find(x=>x.id===id);if(!s)return;s.name='B 고침';s.version=s.published.version+1;s.editedAt=Date.now();CONTI.save()}", sB)
    pl.wait_for_timeout(3500)
    log = pl.evaluate("window.__log")
    fromA = [x for x in log if x['tid'] == tA]
    if not pl.evaluate("window.__failN") or not fromA: fail('전제 실패: A 의 초안 받기가 실패하지 않음 (%s, %s)' % (pl.evaluate("window.__failN"), log))
    if pl.evaluate("CONTI.S.team.id") != tB: fail('전제 실패: B 로 안 돌아옴')
    if not pl.evaluate("!!" + svc_js(sB)): fail('F73: 초안 받기가 실패한 A 팀 받기가 B 팀 발행 콘티를 지움 %s' % fromA)
    if pl.evaluate(svc_js(sB) + ".name") != 'B 고침': fail('F73: B 팀 콘티의 고친 것이 사라짐')
    if any(x['r'] for x in fromA): fail('F73: A 에서 시작한 받기가 팀이 바뀐 뒤에도 끝까지 돌아 바뀌었다고 함 %s' % fromA)
    if pl.evaluate("CONTI.S.services.some(x=>x.id===%s)" % json.dumps(d)): fail('F73: A 팀 초안이 B 팀 목록에')
    # 같은 조건에서 팀을 바꾸지 않으면 실패한 초안은 건너뛰고 받기는 끝까지 돈다 (다음에 다시 받는다)
    team_switch(pl, tA)
    pl.evaluate("()=>{window.__log=[]}")
    r = pl.evaluate("CONTI.SYNC.pullServices()")
    if pl.evaluate("CONTI.S.team.id") != tA or pl.evaluate("CONTI.S.services.some(x=>x.id===%s)" % json.dumps(d)): fail('초안 받기 실패 뒤 A 목록 %s' % r)
    team_switch(pl, tB)
    pl.wait_for_timeout(800)
    if not pl.evaluate("!!" + svc_js(sB)) or pl.evaluate(svc_js(sB) + ".name") != 'B 고침': fail('F73: B 로 돌아온 뒤 고친 B 콘티가 없음')
    if pl._errs: fail('page errors: %s' % pl._errs)
    L.close()
    print('R4 F73 ok')


# api/index.js 를 이 프로세스 안에서 띄우고, 구글 공개키만 가짜로 바꿔 서명한 ID 토큰으로 /auth/social 을 부른다
# (개발 서버는 진짜 구글 키로만 검증하므로 가짜 토큰을 받지 않는다). DB 는 로컬 도커
SOCIAL_JS = r"""
import http from 'node:http';
import { webcrypto as wc } from 'node:crypto';
const root = process.env.ROOT;
process.env.GOOGLE_CLIENT_ID_WEB = 'audit-client';
process.env.DATABASE_URL = 'postgres://postgres:pg@localhost:54329/postgres';
process.env.AUTH_SECRET = process.env.AUTH_SECRET || 'local-dev-secret-0123456789';
const fail = (m) => { console.log('FAIL: ' + m); process.exit(1); };
const kp = await wc.subtle.generateKey({ name: 'RSASSA-PKCS1-v1_5', modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: 'SHA-256' }, true, ['sign', 'verify']);
const jwk = await wc.subtle.exportKey('jwk', kp.publicKey); jwk.kid = 'audit-fe04'; jwk.alg = 'RS256';
const realFetch = globalThis.fetch;
globalThis.fetch = async (u, o) => String(u).startsWith('https://www.googleapis.com/oauth2/v3/certs')
  ? new Response(JSON.stringify({ keys: [jwk] }), { headers: { 'content-type': 'application/json' } }) : realFetch(u, o);
const b64u = (x) => Buffer.from(x).toString('base64url');
async function token(sub) {
  const now = Math.floor(Date.now() / 1000);
  const h = b64u(JSON.stringify({ alg: 'RS256', kid: 'audit-fe04', typ: 'JWT' }));
  const b = b64u(JSON.stringify({ iss: 'https://accounts.google.com', aud: 'audit-client', sub, email: sub + '@audit.example', exp: now + 600, iat: now }));
  const sig = await wc.subtle.sign('RSASSA-PKCS1-v1_5', kp.privateKey, new TextEncoder().encode(h + '.' + b));
  return h + '.' + b + '.' + b64u(sig);
}
const { default: api } = await import(root + '/api/index.js');
const srv = http.createServer((req, res) => api(req, res));
await new Promise((ok) => srv.listen(0, '127.0.0.1', ok));
const base = 'http://127.0.0.1:' + srv.address().port + '/api';
async function call(method, path, body, cookie) {
  const r = await realFetch(base + path, { method, headers: { 'x-conti': '1', 'content-type': 'application/json', ...(cookie ? { cookie } : {}) }, body: body ? JSON.stringify(body) : undefined });
  const sc = (r.headers.getSetCookie ? r.headers.getSetCookie() : []).map((c) => c.split(';')[0]).find((c) => c.startsWith('conti_s=')) || null;
  let j = null; try { j = await r.json(); } catch {}
  return { status: r.status, j, cookie: sc };
}
const tag = Date.now().toString(36);
// F80: 동의 없는 새 구글 계정은 만들지 않는다 (428 needs_consent). 동의하면 만들고 동의 버전이 남는다
let r = await call('POST', '/auth/social', { provider: 'google', idToken: await token('s1' + tag), login: true });
if (r.status !== 428 || !r.j || r.j.error !== 'needs_consent') fail('동의 없는 소셜 가입이 ' + r.status + ' ' + JSON.stringify(r.j));
r = await call('POST', '/auth/social', { provider: 'google', idToken: await token('s1' + tag), login: true, agreedAt: new Date().toISOString() });
if (r.status !== 200 || !r.cookie) fail('동의한 소셜 가입 실패 ' + r.status + ' ' + JSON.stringify(r.j));
if (!r.j.user || r.j.user.agreedVer !== r.j.user.legalVer) fail('동의 버전이 안 남음 ' + JSON.stringify(r.j.user));
// 이미 있는 계정은 동의 없이도 로그인된다
r = await call('POST', '/auth/social', { provider: 'google', idToken: await token('s1' + tag), login: true });
if (r.status !== 200) fail('있는 계정 로그인이 ' + r.status);
// F82: 남은 세션(로그아웃 실패)이 있어도 로그인 화면에서 부른 것은 그 계정에 붙이지 않는다
const u1 = await call('POST', '/auth/signup', { username: 'fe4' + tag, password: 'secret1', name: '앞사람', agreedAt: new Date().toISOString() });
if (u1.status !== 200) fail('가입 실패 ' + u1.status);
r = await call('POST', '/auth/social', { provider: 'google', idToken: await token('s2' + tag), login: true, agreedAt: new Date().toISOString() }, u1.cookie);
if (r.status !== 200) fail('다음 사람 소셜 로그인 ' + r.status + ' ' + JSON.stringify(r.j));
if (r.j.user.id === u1.j.user.id) fail('로그인 화면의 소셜 로그인이 남은 세션의 계정으로 들어감');
let links = await call('GET', '/auth/social', null, u1.cookie);
if ((links.j.linked || []).length) fail('남은 세션 계정에 다음 사람의 구글 계정이 붙음 ' + JSON.stringify(links.j.linked));
// 설정의 '계정 연결'(login 표시 없음)은 붙는다. 들어올 길을 더하는 일이라 현재 비밀번호로 본인 확인을 한다 (F37)
r = await call('POST', '/auth/social', { provider: 'google', idToken: await token('s3' + tag), password: 'secret1' }, u1.cookie);
if (r.status !== 200 || r.j.user.id !== u1.j.user.id) fail('계정 연결이 안 됨 ' + r.status);
links = await call('GET', '/auth/social', null, u1.cookie);
if ((links.j.linked || []).length !== 1) fail('계정 연결 목록 ' + JSON.stringify(links.j));
// 이미 깔린 예전 앱: 로그아웃 상태에서 login 표시 없이 늘 지금 시각을 agreedAt 으로 보낸다(동의 창을 본 적 없음)
// → 계정은 만들되 동의는 남기지 않는다 (그 앱의 약관 동의 창이 뜬다)
r = await call('POST', '/auth/social', { provider: 'google', idToken: await token('s4' + tag), agreedAt: new Date().toISOString() });
if (r.status !== 200) fail('예전 앱 소셜 가입이 ' + r.status + ' ' + JSON.stringify(r.j));
if (r.j.user.agreedVer) fail('예전 앱 가입에 동의 버전이 남음 ' + JSON.stringify(r.j.user));
console.log('  social server ok');
process.exit(0);
"""


def run():
    only = set(sys.argv[1:])
    tests = [('f20', t_f20), ('notes', t_notes), ('f21', t_f21), ('pull', t_pull), ('f75', t_f75), ('f76', t_f76),
             ('draft', t_draft), ('g31', t_g31), ('f80', t_f80), ('logout', t_logout),
             ('r2f20', t_r2_f20), ('r2notes', t_r2_notes), ('r2team', t_r2_team), ('r2draft', t_r2_draft), ('r2blobs', t_r2_blobs), ('r2f76', t_r2_f76),
             ('r2g31', t_r2_g31), ('r2f80', t_r2_f80), ('r2push', t_r2_push), ('r2g15', t_r2_g15),
             ('r3f76', t_r3_f76), ('r3dirty', t_r3_dirty), ('r4pull', t_r4_pull)]
    with sync_playwright() as p:
        b = p.chromium.launch()
        for name, fn in tests:
            if only and name not in only: continue
            fn(b)
        b.close()
    print('AUDIT FE-04 OK')


if __name__ == '__main__':
    run()
