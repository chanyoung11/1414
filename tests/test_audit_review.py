# 전역감사 2026-09-24 — 검토에서 되돌려진(검증자가 찾은) 회귀 검사
#  pending : 발행 대기를 차례로 올리는 사이 팀을 바꾸면 옛 팀 콘티가 새 팀에 발행되던 것
#  songreq : 라이브러리 곡 만들기(POST /songs)가 계속 거절되면 저장 → 3초 뒤 다시 밀기로 끝없이 되풀이하던 것
#  newsong : 에디터의 '라이브러리 → 새 곡 → 넣고 에디터로' 뒤 화면이 그대로라 넣은 곡이 안 보이던 것
#  stglegacy: 업데이트 전 이 기기에만 있던 무대 조판(conti-lay:…)을 무대를 처음 열 때 지우던 것
#  printids: test_print 가 심는 메모 id 가 서버가 받는 꼴이 아니어서 시험이 늘 떨어지던 것
# 준비: sh scripts/dev-local.sh (AI 는 가짜) → CONTI_URL=http://localhost:8766/ python tests/test_audit_review.py [이름…]
import os, sys, time, json, re
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
H = {'x-conti': '1'}
TAG = str(int(time.time() * 1000))[-8:]
SEQ = [0]
IPAD = {'width': 1180, 'height': 820}


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


def leader(b, team='검토팀'):
    c = b.new_context(viewport=IPAD, service_workers='block')
    u = nid('rv')
    must(c, 'POST', '/auth/signup', {'username': u, 'password': 'secret1', 'name': '인도', 'agreedAt': '2026-09-24T00:00:00Z'})
    t = must(c, 'POST', '/teams', {'name': team + TAG, 'myName': '인도', 'session': '인도자'})
    c._team = t['teamId']
    return c


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


def switch_team(pg, tid):
    pg.evaluate("CONTI.go('team')")
    pg.wait_for_selector('[data-act="team-switch"]', timeout=10000)
    pg.click('[data-act="team-switch"]'); pg.click('[data-switch="%s"]' % tid)
    until(pg, "t=>CONTI.S.team.id===t", tid, what='팀 전환')


# ---------- 발행 대기를 올리는 사이 팀을 바꾸면 멈춘다 (옛 팀 콘티가 새 팀에 발행되지 않는다) ----------
def t_pending(b):
    A = leader(b, 'A팀')
    B = must(A, 'POST', '/teams', {'name': 'B팀' + TAG, 'myName': '인도', 'session': '인도자'})['teamId']
    pg = page(A)
    if pg.evaluate("CONTI.S.team.id") != A._team: switch_team(pg, A._team)
    s1, s2 = nid('sA'), nid('sA')
    pg.evaluate("""([s1,s2])=>{const mk=(id,nm)=>{const items=[{id:'i'+id,title:'곡 '+nm,key:'G',form:'',pieces:[],media:[],notes:[]}];
      return {id,name:nm,date:'2099-02-01',notice:'',version:1,items,editedAt:Date.now(),
        published:{version:1,at:Date.now(),name:nm,date:'2099-02-01',folder:'',notice:'',message:'',messageRev:0,word:null,author:'인도',items:JSON.parse(JSON.stringify(items)),changes:[]},pubPending:true}};
      CONTI.S.services.push(mk(s1,'A팀 1부'),mk(s2,'A팀 2부'));CONTI.save()}""", [s1, s2])
    # 첫 발행 PUT 을 붙잡아 두고, 그 사이 B 팀으로 바꾼 뒤 놓는다
    st = {'n': 0, 'held': None}
    def hold(route):
        if route.request.method == 'PUT' and '/draft' not in route.request.url:
            st['n'] += 1
            if st['n'] == 1:
                st['held'] = route; return
        route.continue_()
    pg.route(re.compile(r'.*/api/services/sA[^/?]*$'), hold)
    pg.evaluate("()=>{window.__pp=undefined;CONTI.SYNC.pushPending().then(n=>window.__pp=n,()=>window.__pp=-1);return 1}")
    t0 = time.time()
    while not st['held'] and time.time() - t0 < 10: pg.wait_for_timeout(100)
    if not st['held']: fail('전제 실패: 첫 발행 PUT 이 안 나감')
    switch_team(pg, B)
    st['held'].continue_()
    until(pg, "window.__pp!==undefined", timeout=20000, what='발행 대기 올리기가 끝남')
    pg.wait_for_timeout(800)
    lb = must(A, 'GET', '/services?team=' + B)['services']
    if lb: fail('옛 팀 콘티가 새 팀에 발행됨: %s' % [(x['id'], x.get('name')) for x in lb])
    la = [x['id'] for x in must(A, 'GET', '/services?team=' + A._team)['services']]
    if s1 not in la: fail('붙잡았던 첫 콘티가 원래 팀(A)에 안 올라감: %s' % la)
    # 남은 콘티는 A 팀 저장본에 대기로 남아, A 로 돌아오면 A 에 올라간다
    pg.unroute(re.compile(r'.*/api/services/sA[^/?]*$'))
    switch_team(pg, A._team)
    if not pg.evaluate("(id)=>!!(CONTI.S.services.find(x=>x.id===id)||{}).pubPending", s2): fail('남은 콘티의 발행 대기 표시가 사라짐')
    pg.evaluate("CONTI.SYNC.pushPending()")
    until(pg, "(id)=>!(CONTI.S.services.find(x=>x.id===id)||{}).pubPending", s2, what='A 로 돌아와 남은 콘티를 올림')
    la = [x['id'] for x in must(A, 'GET', '/services?team=' + A._team)['services']]
    if s2 not in la: fail('A 로 돌아와도 남은 콘티가 A 에 안 올라감: %s' % la)
    if must(A, 'GET', '/services?team=' + B)['services']: fail('B 팀에 콘티가 생김')
    if pg._errs: fail('페이지 오류 %s' % pg._errs)
    pg.close()
    print('  pending ok — 팀을 바꾸면 멈추고, 올리던 것은 원래 팀으로 · 남은 것은 돌아와서')


# ---------- 곡 만들기가 계속 거절돼도 스스로 되풀이하지 않는다 · 같은 요청 id 를 이어 쓴다 ----------
def t_songreq(b):
    L = leader(b)
    pg = page(L)
    pg.wait_for_timeout(1500)
    posts = []; mode = {'v': '402'}
    def h(route):
        if route.request.method == 'POST':
            try: posts.append(json.loads(route.request.post_data or '{}').get('id'))
            except Exception: posts.append(None)
            if mode['v'] == '402':
                route.fulfill(status=402, content_type='application/json', body=json.dumps({'error': 'plan_limit', 'message': '무료는 100곡까지예요'})); return
            if mode['v'] == '409once':
                mode['v'] = 'pass'
                route.fulfill(status=409, content_type='application/json', body=json.dumps({'error': 'song_id_taken', 'message': '곡을 다시 만들어 주세요'})); return
        route.continue_()
    pg.route(re.compile(r'.*/api/songs$'), h)
    pg.evaluate("""()=>{const f=CONTI.IDB.put;CONTI.IDB.put=function(s,k,v){if(s==='kv'&&k!=='scope')window.__saves=(window.__saves||0)+1;return f.apply(this,arguments)}}""")
    sid = nid('sv'); title = '라이브러리에 없는 곡 ' + sid
    pg.evaluate("""([sid,title])=>{CONTI.S.services.push({id:sid,name:'예배',date:'2099-03-01',notice:'',version:0,items:[{id:'it'+sid,title,key:'C',form:'',pieces:[],media:[],notes:[]}],published:null,editedAt:Date.now()});CONTI.save()}""", [sid, title])
    pg.wait_for_timeout(16000)
    saves = pg.evaluate("window.__saves||0")
    if len(posts) > 2: fail('거절되는 곡 만들기를 사용자 동작 없이 되풀이함: 16초에 POST %d번 · 저장 %d번' % (len(posts), saves))
    if saves > 4: fail('거절되는 동안 상태를 계속 다시 씀: 저장 %d번' % saves)
    if not posts: fail('전제 실패: 곡 만들기를 한 번도 안 보냄')
    if len(set(posts)) != 1: fail('거절된 뒤 요청 id 가 바뀜 (응답을 못 받은 요청이 두 곡을 만들 수 있다): %s' % posts)
    req = pg.evaluate("(sid)=>(CONTI.S.services.find(x=>x.id===sid).items[0].songReq||{}).id||null", sid)
    if req != posts[0]: fail('거절된 요청 id 가 콘티에 안 남음: %s vs %s' % (req, posts[0]))
    # 제한이 풀린 뒤 사용자가 저장하면 같은 id 로 만들어지고 이어진다
    mode['v'] = 'pass'; n0 = len(posts)
    pg.evaluate("(sid)=>{const s=CONTI.S.services.find(x=>x.id===sid);s.editedAt=Date.now();CONTI.save()}", sid)
    until(pg, "(sid)=>!!CONTI.S.services.find(x=>x.id===sid).items[0].arrId", sid, timeout=15000, what='곡이 만들어져 이어짐')
    if posts[n0:] and posts[n0] != posts[0]: fail('제한이 풀린 뒤 새 id 로 보냄: %s' % posts)
    songs = [s for s in must(L, 'GET', '/songs?team=' + L._team)['songs'] if s['title'] == title]
    if len(songs) != 1 or songs[0]['id'] != posts[0]: fail('만들어진 곡이 요청 id 와 다름: %s %s' % ([s['id'] for s in songs], posts[0]))
    # 409(그 id 를 이미 다른 곡이 씀)면 다음엔 새 id 로 보낸다 — 이때도 스스로 되풀이하지 않는다
    mode['v'] = '409once'; n1 = len(posts); t2 = '두번째 곡 ' + sid
    pg.evaluate("""([sid,t])=>{const s=CONTI.S.services.find(x=>x.id===sid);s.items.push({id:'it2'+sid,title:t,key:'D',form:'',pieces:[],media:[],notes:[]});s.editedAt=Date.now();CONTI.save()}""", [sid, t2])
    t0 = time.time()
    while len(posts) < n1 + 1 and time.time() - t0 < 10: pg.wait_for_timeout(200)
    pg.wait_for_timeout(8000)
    after409 = posts[n1:]
    if not after409: fail('전제 실패: 두 번째 곡 만들기를 안 보냄')
    if len(after409) > 2: fail('409 뒤에 스스로 되풀이함: %s' % after409)
    if len(after409) == 2 and after409[0] == after409[1]: fail('409 뒤에도 같은 id 로 보냄: %s' % after409)
    if not pg.evaluate("(sid)=>!!CONTI.S.services.find(x=>x.id===sid).items[1].arrId", sid):
        pg.evaluate("(sid)=>{const s=CONTI.S.services.find(x=>x.id===sid);s.editedAt=Date.now();CONTI.save()}", sid)
        until(pg, "(sid)=>!!CONTI.S.services.find(x=>x.id===sid).items[1].arrId", sid, timeout=15000, what='409 뒤 새 id 로 만들어짐')
    ids = posts[n1:]
    if ids[-1] == ids[0]: fail('409 뒤 새 id 로 안 보냄: %s' % ids)
    if pg._errs: fail('페이지 오류 %s' % pg._errs)
    pg.close()
    print('  songreq ok — 거절이 이어져도 POST %d번에서 멈춤 · 같은 요청 id 로 이어 만듦 · 409 면 새 id' % n0)


# ---------- 에디터에서 새 곡 → '넣고 에디터로' 뒤 넣은 곡이 바로 보인다 ----------
def t_newsong(b):
    L = leader(b)
    must(L, 'POST', '/songs', {'teamId': L._team, 'title': '기존곡' + TAG, 'key': 'G'})
    pg = page(L)
    sid = nid('sv')
    pg.evaluate("""(sid)=>{CONTI.S.services.push({id:sid,name:'편집중 예배',date:'2099-03-01',notice:'',version:0,items:[{id:'it'+sid,title:'첫곡',key:'C',form:'',pieces:[],media:[],notes:[]}],published:null,editedAt:Date.now()});CONTI.save()}""", sid)
    pg.evaluate("(sid)=>CONTI.go('edit/'+sid)", sid)
    pg.wait_for_selector('[data-act="add-lib"]', timeout=10000)
    pg.evaluate("CONTI.pullSongs(true)"); pg.wait_for_timeout(600)
    pg.click('[data-act="add-lib"]'); pg.wait_for_selector('#lpNew', timeout=5000)
    pg.click('#lpNew'); pg.wait_for_selector('#nsTitle', timeout=5000)
    title = '새로만든곡' + nid('')
    pg.fill('#nsTitle', title); pg.click('#nsOk')
    pg.wait_for_selector('#atsGo', timeout=10000)
    on = pg.evaluate("(document.querySelector('#atsSvc .q.on')||{}).textContent||''")
    if '편집중 예배' not in on: fail('전제 실패: 넣기 창이 지금 고치는 예배를 고르지 않음: %r' % on)
    pg.click('#atsGo')
    until(pg, "(t)=>document.getElementById('app').innerText.includes(t)", title, timeout=5000,
          what='넣고 에디터로 뒤 에디터에 새 곡이 보임')
    if pg.evaluate("location.hash") != '#edit/' + sid: fail('에디터 주소가 바뀜: ' + pg.evaluate("location.hash"))
    n = pg.evaluate("([sid,t])=>CONTI.S.services.find(x=>x.id===sid).items.filter(i=>i.title===t).length", [sid, title])
    if n != 1: fail('새 곡이 %d번 들어감' % n)
    if pg._errs: fail('페이지 오류 %s' % pg._errs)
    pg.close()
    print('  newsong ok')


# ---------- 업데이트 전 무대 조판(conti-lay:…)을 지우지 않고 이 사람 것으로 옮긴다 · 여럿이 쓴 기기는 전처럼 읽지 않는다 ----------
LAY = {"v": 2, "screens": [{"blocks": [{"id": "xoff1", "type": "text", "text": "오프라인에서 만든 조판", "x": 0.1, "y": 0.1, "w": 0.3, "h": 0.1}]}]}


def t_stglegacy(b):
    L = leader(b)
    pg = page(L)
    uid = pg.evaluate("CONTI.NET.user.id")
    sid = nid('st')
    pg.evaluate("""(sid)=>{CONTI.S.services.push({id:sid,name:'무대',date:'2099-03-01',notice:'',version:0,items:[{id:'i'+sid,title:'곡',key:'C',form:'',pieces:[],media:[],notes:[]}],published:null,editedAt:Date.now()});CONTI.save()}""", sid)
    others = ['phone', 'tab-s', 'tab-l', 'desktop']   # 1180×820 은 tab-l — 다른 기기 구간의 예전 사본도 같이 옮긴다
    pg.evaluate("""([sid,lay,dcs])=>{for(const d of dcs)localStorage.setItem('conti-lay:'+sid+'~'+d,JSON.stringify(lay))}""", [sid, LAY, others])
    pg.evaluate("(sid)=>CONTI.stageOpen(CONTI.S.services.find(x=>x.id===sid),0)", sid)
    pg.wait_for_selector('#stageWrap', timeout=15000)
    lay = pg.evaluate("JSON.stringify(CONTI.STG.layout)") or ''
    if '오프라인에서 만든 조판' not in lay: fail('업데이트 전 이 기기에만 있던 조판으로 안 열림: %s' % lay[:200])
    # 서버에 올린 뒤 예전 사본을 치운다 (사람별 사본은 남는다)
    until(pg, "(sid)=>!Object.keys(localStorage).some(k=>k.indexOf('conti-lay:'+sid)===0&&k.indexOf('@')<0)", sid, timeout=10000,
          what='예전 사본을 서버에 올리고 치움')
    mine = pg.evaluate("([sid,uid])=>Object.keys(localStorage).filter(k=>k.indexOf('conti-lay:'+sid)===0&&k.endsWith('@'+uid)).length", [sid, uid])
    if mine < len(others): fail('사람별 사본으로 안 옮겨짐: %d' % mine)
    stage = (must(L, 'GET', '/me/prefs').get('prefs') or {}).get('stage') or {}
    got = [k for k in stage if k.startswith('lay:' + sid)]
    if len(got) < len(others): fail('서버에 안 올라감: %s' % got)
    pg.evaluate("CONTI.stageExit()")
    # 여럿이 쓴 기기(다른 계정의 저장소가 있다): 누구 것인지 모르니 읽지 않고 치운다 (F97)
    sid2 = nid('st')
    pg.evaluate("""(sid)=>{CONTI.S.services.push({id:sid,name:'무대2',date:'2099-03-02',notice:'',version:0,items:[{id:'i'+sid,title:'곡',key:'C',form:'',pieces:[],media:[],notes:[]}],published:null,editedAt:Date.now()});CONTI.save()}""", sid2)
    pg.evaluate("()=>CONTI.IDB.put('kv','state:someone-else:team','{}')")
    pg.evaluate("""([sid,lay,dcs])=>{for(const d of dcs)localStorage.setItem('conti-lay:'+sid+'~'+d,JSON.stringify(lay))}""", [sid2, LAY, others])
    pg.evaluate("(sid)=>CONTI.stageOpen(CONTI.S.services.find(x=>x.id===sid),0)", sid2)
    pg.wait_for_selector('#stageWrap', timeout=15000)
    lay = pg.evaluate("JSON.stringify(CONTI.STG.layout)") or ''
    if '오프라인에서 만든 조판' in lay: fail('여럿이 쓴 기기에서 누구 것인지 모르는 예전 조판으로 열림')
    left = pg.evaluate("(sid)=>Object.keys(localStorage).filter(k=>k.indexOf('conti-lay:'+sid)===0)", sid2)
    if left: fail('여럿이 쓴 기기의 예전 사본이 남거나 옮겨짐: %s' % left)
    pg.evaluate("CONTI.stageExit()")
    pg.evaluate("()=>CONTI.IDB.del('kv','state:someone-else:team')")
    if pg._errs: fail('페이지 오류 %s' % pg._errs)
    pg.close()
    print('  stglegacy ok')


# ---------- test_print 의 메모 id 가 서버가 받는 꼴이다 ----------
def t_printids(b):
    src = open(os.path.join(ROOT, 'tests', 'test_print.py'), encoding='utf-8').read()
    m = re.search(r"it\.notes=\[(.*?)\];", src, re.S)
    if not m: fail('test_print 에서 메모 심기를 못 찾음')
    ids = re.findall(r"\{id:('[^']*'(?:\+tag)?)", m.group(1))
    if not ids: fail('test_print 메모 id 를 못 찾음')
    for x in ids:
        lit = x.split('+')[0].strip("'") + ('123456' if x.endswith('+tag') else '')
        if not re.match(r'^[A-Za-z0-9_-]{4,40}$', lit): fail('test_print 메모 id 를 서버가 거절함: %s' % x)
    print('  printids ok', ids)


def run():
    only = set(sys.argv[1:])
    tests = [('pending', t_pending), ('songreq', t_songreq), ('newsong', t_newsong), ('stglegacy', t_stglegacy), ('printids', t_printids)]
    with sync_playwright() as p:
        b = p.chromium.launch()
        for name, fn in tests:
            if only and name not in only: continue
            fn(b)
        b.close()
    print('AUDIT REVIEW OK')


if __name__ == '__main__':
    run()
