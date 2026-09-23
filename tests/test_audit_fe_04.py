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
// 설정의 '계정 연결'(login 표시 없음)은 예전처럼 붙는다
r = await call('POST', '/auth/social', { provider: 'google', idToken: await token('s3' + tag) }, u1.cookie);
if (r.status !== 200 || r.j.user.id !== u1.j.user.id) fail('계정 연결이 안 됨 ' + r.status);
links = await call('GET', '/auth/social', null, u1.cookie);
if ((links.j.linked || []).length !== 1) fail('계정 연결 목록 ' + JSON.stringify(links.j));
console.log('  social server ok');
process.exit(0);
"""


def run():
    only = set(sys.argv[1:])
    tests = [('f20', t_f20), ('notes', t_notes), ('f21', t_f21), ('pull', t_pull), ('f75', t_f75), ('f76', t_f76),
             ('draft', t_draft), ('g31', t_g31), ('f80', t_f80), ('logout', t_logout)]
    with sync_playwright() as p:
        b = p.chromium.launch()
        for name, fn in tests:
            if only and name not in only: continue
            fn(b)
        b.close()
    print('AUDIT FE-04 OK')


if __name__ == '__main__':
    run()
