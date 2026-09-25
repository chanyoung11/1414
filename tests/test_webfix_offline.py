# 운영 브라우저 점검(2026-09-25) 오프라인 되돌림 방지
#  edge-2 켜 둔 채 끊긴 사이 쓴 메모가 다시 연결돼도 안 올라가던 것 (콘티를 다시 열 때까지) —
#         online 이벤트는 발행 대기만 올렸고 NET.server 는 그대로 true 라 다시 묻기도 안 돌았다.
#         다시 연결·화면 복귀에 못 올린 메모·초안·삭제를 모든 콘티에서 민다 (지금 연 콘티가 아니어도)
#  edge-3 같은 탭에서 주소만 다른 초대로 바뀌면 앞 초대의 팀이 보인 채 가입 단추는 새 초대로 가던 것 (미리보기를 코드와 함께)
#  edge-4 로그인한 팀원이 오프라인이면 '기기 전용'·'내보내기 파일을 카톡으로' 가 뜨던 것 → 팀 이름 + 오프라인 안내
#  edge-5 로그인 안 한 사람이 오프라인으로 열면 기기 전용 첫 설정(이름·세션·인도자/멤버)이 뜨던 것 → 로그인 화면 + 오프라인 안내
#         (서버가 있다는 증거 — 앱·받아 둔 서버 답·로그인한 저장소 — 가 없는 곳은 예전처럼 기기 전용: 404 · SPA fallback 정적 호스팅)
#  되돌림 검사(재검증): 초안을 밀기 전에 목록을 받고 서버 초안과 견준다 — 다른 기기에서 지운 콘티를 되살리거나 더 새 초안을 덮지 않게
#  재검증 2: 견줘서 안 올린 초안을 다시 연결 끝의 저장 타이머(2.5초)가 에디터에 열린 콘티라며 그대로 올리던 것 → 붙잡아 두고(draftHold)
#         가져올지 물어 답할 때까지 누구도 올리지 않는다 · 에디터에 열려 있으면 바로 묻는다 · 다시 연결을 견주는 동안 저장 타이머는 기다린다
import os, re, sys, time, json
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
BASE = URL.rstrip('/')
H = {'x-conti': '1'}
tag = str(int(time.time()))[-6:]
N = [0]
def fail(m): print('FAIL:', m); sys.exit(1)
def ok(r, what=''):
    if not r.ok: fail('%s %s %s' % (what, r.status, r.text()[:200]))
    return r.json()
def uname(p): N[0] += 1; return '%s%s%d' % (p, tag, N[0])

def account(b, prefix, name, **ctx):
    c = b.new_context(viewport={'width': 1240, 'height': 900}, **ctx)
    u = uname(prefix)
    me = ok(c.request.post(URL + 'api/auth/signup', headers=H, data={'username': u, 'password': 'secret1', 'name': name}), 'signup')
    return c, u, me['user']['id']

def make_team(c, name):
    return ok(c.request.post(URL + 'api/teams', headers=H, data={'name': name, 'myName': '하은', 'session': '인도자'}), 'team')['teamId']

def invite_code(c, team):
    return ok(c.request.get(URL + 'api/teams/%s' % team), 'team get')['invite']

def page(c, hash_='#/home', sel='.shell[data-page]'):
    pg = c.new_page(); pg.errs = []; pg.dismiss = False   # dismiss: 확인 창에서 '취소'
    pg.on('pageerror', lambda e: pg.errs.append(str(e)[:200])); pg.on('dialog', lambda d: d.dismiss() if pg.dismiss else d.accept())
    pg.goto(URL + hash_)
    if sel: pg.wait_for_selector(sel, timeout=15000)
    return pg

def wait_until(pg, expr, ms=12000, arg=None):
    try: pg.wait_for_function(expr, arg=arg, timeout=ms); return True
    except Exception: return False

def new_published(pg, name, song):
    pg.goto(URL + '#/home'); pg.wait_for_selector('[data-act="new-svc"]', timeout=10000)
    pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]', timeout=8000)
    pg.fill('[data-f="svc.name"]', name)
    pg.click('[data-act="add-item"]'); pg.wait_for_selector('[data-f="item.title"]', timeout=8000)
    pg.fill('[data-f="item.title"]', song); pg.wait_for_timeout(400)
    sid = pg.evaluate('CONTI.route().a')
    pg.click('[data-act="publish"]'); pg.wait_for_selector('#pubOnly', timeout=6000); pg.click('#pubOnly')
    if not wait_until(pg, "(id)=>{const s=CONTI.S.services.find(x=>x.id===id);return s&&s.published&&!s.pubPending}", arg=sid): fail('발행이 안 끝남')
    return sid

def open_view(pg, sid):
    pg.goto(URL + '#/view/' + sid); pg.wait_for_selector('#app .top', timeout=10000)

def server_notes(c, team, sid):
    return {n['id']: n for n in ok(c.request.get(URL + 'api/notes?team=%s&service=%s' % (team, sid)), 'notes')['notes']}

def poll(fn, ms=10000, step=400):
    t = time.time() + ms / 1000
    while time.time() < t:
        if fn(): return True
        time.sleep(step / 1000)
    return fn()

# 페이지 이벤트(붙잡은 요청·확인 창)를 돌리며 기다린다 — time.sleep 동안에는 playwright 가 이벤트를 넘기지 않는다
def pump(pg, fn, ms=8000):
    t = time.time() + ms / 1000
    while time.time() < t:
        if fn(): return True
        pg.wait_for_timeout(100)
    return fn()

# 콘티 화면의 메모 쓰기·지우기와 같은 길 (it.notes 를 고치고 save() → schedulePush → pushNotes)
ADD_NOTE = """([id,nid,text])=>{const s=CONTI.S.services.find(x=>x.id===id);
  s.items[0].notes.push({id:nid,layer:'mine',session:null,text,author:'하은',at:Date.now()});CONTI.save()}"""
DEL_NOTE = """([id,nid])=>{const s=CONTI.S.services.find(x=>x.id===id);s.items[0].notes=s.items[0].notes.filter(n=>n.id!==nid);CONTI.save()}"""
# 인도자가 콘티를 고친 것과 같게 (이름 · 발행 뒤 고친 판 · editedAt) — 고친 때를 돌려준다
EDIT_NAME = """([id,name])=>{const s=CONTI.S.services.find(x=>x.id===id);s.name=name;
  if(s.published&&s.version<=s.published.version)s.version=s.published.version+1;s.editedAt=Date.now();CONTI.save();return s.editedAt}"""

# ---------------------------------------------------------------- edge-2
def sec_memo(b):
    c, u, uid = account(b, 'om', '하은', service_workers='block')
    team = make_team(c, '메모팀')
    pg = page(c)
    s1 = new_published(pg, '끊김 예배', '곡1')
    s2 = new_published(pg, '둘째 예배', '곡2')
    open_view(pg, s1)
    pg.wait_for_timeout(4500)   # 라이브러리 올리기(3초 뒤)까지 끝나게 — 그 뒤의 저장이 메모를 대신 밀어 주면 시험이 안 된다
    fails = []
    pg.on('console', lambda m: fails.append(m.text) if 'notes push' in m.text else None)

    # 1) 콘티를 연 채 끊겼다가(navigator 오프라인) 다시 연결 → 그 자리에서 올라간다
    n1 = 'na' + tag
    c.set_offline(True); pg.wait_for_timeout(300)
    pg.evaluate(ADD_NOTE, [s1, n1, '끊김메모'])
    pg.wait_for_timeout(4000)   # 메모 보내기(0.7초)와 라이브러리 올리기(3초)가 끊긴 채 끝나게
    if not fails: fail('준비: 끊긴 사이 메모 보내기가 실패하지 않음')
    if pg.evaluate('CONTI.NET.server') is not True: fail('준비: 켜 둔 채 끊긴 경우(NET.server 가 true 로 남음)가 아님')
    c.set_offline(False)
    if not poll(lambda: n1 in server_notes(c, team, s1), 8000): fail('edge-2 다시 연결됐는데 끊긴 사이 쓴 메모가 서버에 안 올라감 (콘티를 다시 열기 전)')
    if pg.evaluate("CONTI.route().name") != 'view': fail('준비: 콘티 화면을 떠남')
    print('edge-2 끊긴 사이 쓴 메모: 다시 연결되면(online) 바로 올라감 ok')

    # 2) 끊긴 사이 다른 콘티에서 쓰고 지운 메모 + 인도자 초안 수정, 홈으로 나와서 다시 연결 → 모두 올라간다
    n2 = 'nb' + tag
    open_view(pg, s2); pg.wait_for_timeout(1500)
    pg.evaluate(ADD_NOTE, [s2, n2, '끊긴 사이 지울 메모']); pg.wait_for_timeout(1500)
    if n2 not in server_notes(c, team, s2): fail('준비: 온라인 메모가 안 올라감')
    c.set_offline(True); pg.wait_for_timeout(300)
    n3 = 'nc' + tag
    pg.evaluate(ADD_NOTE, [s2, n3, '둘째 끊김메모'])
    pg.evaluate(DEL_NOTE, [s2, n2])
    pg.evaluate("""(id)=>{const s=CONTI.S.services.find(x=>x.id===id);s.name='오프라인에서 고친 이름';
      if(s.published&&s.version<=s.published.version)s.version=s.published.version+1;s.editedAt=Date.now();CONTI.save()}""", s1)
    pg.evaluate("location.hash='#/home'"); pg.wait_for_timeout(1500)
    c.set_offline(False)
    if not poll(lambda: n3 in server_notes(c, team, s2), 8000): fail('edge-2 다른 콘티에서 끊긴 사이 쓴 메모가 홈에서 다시 연결돼도 안 올라감')
    if not poll(lambda: n2 not in server_notes(c, team, s2), 5000): fail('edge-2 끊긴 사이 지운 메모가 다시 연결돼도 서버에 남음')
    def draft_name():
        d = ok(c.request.get(URL + 'api/services/%s/draft?team=%s' % (s1, team)), 'draft')
        return (d.get('doc') or {}).get('name')
    if not poll(lambda: draft_name() == '오프라인에서 고친 이름', 8000): fail('edge-2 끊긴 사이 고친 초안이 다시 연결돼도 안 올라감: %r' % draft_name())
    if pg.evaluate("CONTI.route().name") != 'home': fail('준비: 홈을 떠남')
    print('edge-2 다른 콘티의 메모 쓰기·지우기와 초안도: 홈에서 다시 연결되면 올라감 ok')

    # 3) 브라우저는 '온라인'인 채 보내기만 실패(와이파이 포털·서버 잠깐 끊김 — online 이벤트 없음) → 앱으로 돌아오면(화면 복귀) 올라간다
    open_view(pg, s1); pg.wait_for_timeout(1500)
    pg.route('**/api/notes', lambda r: r.abort('failed'))
    n4 = 'nd' + tag
    pg.evaluate(ADD_NOTE, [s1, n4, '포털메모']); pg.wait_for_timeout(1500)
    pg.unroute('**/api/notes'); pg.wait_for_timeout(300)
    if n4 in server_notes(c, team, s1): fail('준비: 막아 둔 메모가 올라감')
    pg.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
    if not poll(lambda: n4 in server_notes(c, team, s1), 6000): fail('edge-2 화면 복귀에도 못 올린 메모를 다시 보내지 않음')
    print('edge-2 보내기만 실패한 메모: 화면 복귀에 올라감 ok')

    # 보낼 것이 없으면 화면 복귀가 메모·초안 요청을 만들지 않는다
    reqs = []
    pg.on('request', lambda r: reqs.append(r.method + ' ' + r.url) if re.search(r'/api/(notes|services/[^/]+/draft)', r.url) and r.method != 'GET' else None)
    for _ in range(3): pg.evaluate("document.dispatchEvent(new Event('visibilitychange'))"); pg.wait_for_timeout(300)
    pg.wait_for_timeout(3500)
    if reqs: fail('보낼 것이 없는데 화면 복귀마다 올리기 요청: %s' % reqs[:3])
    if pg.errs: fail('JS 오류: %s' % pg.errs[:3])
    print('edge-2 보낼 것이 없으면 요청하지 않음 ok')

    # 4) 같은 인도자가 여러 기기를 쓸 때 — 다시 연결돼 미는 초안이 끊긴 사이 다른 기기에서 한 일을 되돌리지 않는다.
    #    전에는 목록도 안 받고 서버 초안과 견주지도 않고 덮어, 지운 콘티가 초안으로 되살아나고 더 새 초안이 옛 것으로 바뀌었다
    cB = b.new_context(storage_state=c.storage_state())   # 같은 인도자의 다른 기기 (서버만 부른다)
    s3 = new_published(pg, '지울 예배', '곡3')
    s4 = new_published(pg, '둘이 고칠 예배', '곡4')
    pg.evaluate("location.hash='#/home'"); pg.wait_for_timeout(3500)
    c.set_offline(True); pg.wait_for_timeout(300)
    at4 = pg.evaluate(EDIT_NAME, [s4, 'A오프라인이름'])
    pg.evaluate(EDIT_NAME, [s3, 'A오프라인수정'])
    ok(cB.request.delete(URL + 'api/services/%s?team=%s' % (s3, team), headers=H), 'B 지우기')
    doc = pg.evaluate("(id)=>CONTI.SYNC.draftDoc(CONTI.S.services.find(x=>x.id===id))", s4)
    doc['name'] = 'B새이름'; doc['editedAt'] = at4 + 60000
    ok(cB.request.put(URL + 'api/services/%s/draft' % s4, headers=H, data={'teamId': team, 'doc': doc}), 'B 초안')
    c.set_offline(False)
    if not wait_until(pg, "(id)=>!CONTI.S.services.some(x=>x.id===id)", 10000, s3): fail('edge-2 다른 기기에서 지운 콘티가 다시 연결된 기기에 남음')
    pg.wait_for_timeout(2500)
    r = ok(cB.request.get(URL + 'api/services?team=%s' % team), '목록')
    if s3 in [x['id'] for x in r['services']] + [x['id'] for x in r.get('drafts', [])]: fail('edge-2 다시 연결되며 다른 기기에서 지운 콘티를 서버에 되살림')
    def draft_of(sid):
        return (ok(cB.request.get(URL + 'api/services/%s/draft?team=%s' % (sid, team)), 'draft').get('doc') or {}).get('name')
    if draft_of(s4) != 'B새이름': fail('edge-2 다시 연결되며 다른 기기의 더 새 초안을 옛 것으로 덮음: %r' % draft_of(s4))
    pg.evaluate("document.dispatchEvent(new Event('visibilitychange'))"); pg.wait_for_timeout(2500)
    if draft_of(s4) != 'B새이름': fail('edge-2 화면 복귀에 다른 기기의 더 새 초안을 덮음: %r' % draft_of(s4))
    print('edge-2 여러 기기: 지운 콘티를 되살리지 않고 · 더 새 초안을 덮지 않음 ok')
    # 그 콘티를 에디터로 열면 전처럼 가져올지 묻는다 (수락하면 받은 초안으로).
    # 화면 복귀를 마치며 건 저장 타이머(2.5초)가 에디터가 서버 초안과 견주는 사이에 터지게, 에디터의 견주기(GET 초안)를 붙잡아 둔다 —
    # 전에는 그 타이머가 견주지 않고 이 기기 것을 올려 더 새 초안을 덮었고, 에디터는 제 것을 보고 묻지도 않았다 (복귀 2.5초쯤 뒤에 열면 그랬다)
    asked, puts, held = [], [], []
    pg.on('dialog', lambda d: asked.append(d.message))
    pg.on('request', lambda r: puts.append(r.post_data or '') if r.method == 'PUT' and '/draft' in r.url else None)
    pg.route('**/api/services/*/draft?*', lambda r: held.append(r) if r.request.method == 'GET' else r.continue_())
    pg.evaluate("(id)=>{location.hash='#/edit/'+id}", s4)
    if not pump(pg, lambda: held): fail('준비: 에디터가 서버 초안과 견주지 않음')
    pg.evaluate("CONTI.SYNC.schedulePush()")   # 저장 타이머를 여기서 다시 건다 — 견주기를 붙잡아 둔 사이에 반드시 터지게
    pg.wait_for_timeout(3500)
    mid = draft_of(s4)
    for r in held: r.continue_()
    pg.unroute('**/api/services/*/draft?*')
    if mid != 'B새이름' or any('A오프라인이름' in x for x in puts):
        fail('edge-2 에디터를 여는 사이 저장 타이머가 더 새 초안을 덮음: 서버 %r · 올림 %d' % (mid, len(puts)))
    pg.wait_for_selector('[data-f="svc.name"]', timeout=10000)
    if not wait_until(pg, "(id)=>CONTI.S.services.find(x=>x.id===id).name==='B새이름'", 15000, s4):   # 열기는 메모·말씀·악보를 먼저 받는다
        st = pg.evaluate("(id)=>{const s=CONTI.S.services.find(x=>x.id===id);return {name:s.name,at:s.editedAt,pushed:s.draftPushedAt,v:s.version,pv:s.published&&s.published.version,r:CONTI.route()}}", s4)
        fail('edge-2 에디터로 열어도 더 새 초안을 가져오지 않음 %s · 물음 %s · 서버 %r · B %s' % (st, asked, draft_of(s4), at4 + 60000))
    if not any('더 새로워요' in m for m in asked): fail('edge-2 에디터로 열 때 더 새 초안을 가져올지 묻지 않음: %s' % asked)
    if pg.input_value('[data-f="svc.name"]') != 'B새이름': fail('edge-2 가져온 초안이 에디터에 안 보임: %r' % pg.input_value('[data-f="svc.name"]'))
    print('edge-2 그 콘티를 열면 더 새 초안을 가져올지 물음 · 여는 사이 저장 타이머가 덮지 않음 ok')
    if pg.errs: fail('JS 오류: %s' % pg.errs[:3])

    # 4-2) 에디터를 연 채 끊겼다 붙을 때 — 끊긴 사이 에디터에서 치고, 다른 기기가 더 새 초안을 올렸다.
    #      전에는 다시 연결을 마치며 건 저장 타이머가 2.5초 뒤 서버와 견주지 않고 이 기기 것을 올려 더 새 초안을 덮었다(묻지도 않음).
    #      붙기 직전에 친 것의 저장 타이머가 다시 연결의 견주기(목록 받기가 느림)보다 먼저 터져도 덮지 않는다
    def in_editor(name, song):
        sid = new_published(pg, name, song)
        pg.evaluate("location.hash='#/home'"); pg.wait_for_timeout(3500)   # 발행 뒤 저장 타이머가 끝나게
        pg.evaluate("(id)=>{location.hash='#/edit/'+id}", sid); pg.wait_for_selector('[data-f="svc.name"]', timeout=10000)
        pg.wait_for_timeout(1500)
        c.set_offline(True); pg.wait_for_timeout(300)
        pg.fill('[data-f="svc.name"]', name + ' 끊김'); pg.wait_for_timeout(3500)   # 끊긴 채 올리기가 실패하게
        return sid
    def newer_on_b(sid, name):
        doc = pg.evaluate("(id)=>CONTI.SYNC.draftDoc(CONTI.S.services.find(x=>x.id===id))", sid)
        doc['name'] = name; doc['editedAt'] = int(time.time() * 1000) + 60000
        ok(cB.request.put(URL + 'api/services/%s/draft' % sid, headers=H, data={'teamId': team, 'doc': doc}), 'B 초안')
    s6 = in_editor('에디터 예배', '곡6')
    newer_on_b(s6, 'B에디터이름')
    asked.clear(); puts.clear(); held.clear()
    pg.route('**/api/services?team=*', lambda r: held.append(r))   # 다시 연결의 목록 받기를 붙잡아 둔다
    pg.fill('[data-f="svc.name"]', 'A붙기직전'); pg.wait_for_timeout(200)
    c.set_offline(False)
    if not pump(pg, lambda: held): fail('준비: 다시 연결이 목록을 받지 않음')
    pg.wait_for_timeout(3500)   # 친 것의 저장 타이머(2.5초)가 이 사이에 터진다
    mid = draft_of(s6)
    for r in held: r.continue_()
    pg.unroute('**/api/services?team=*')
    if mid != 'B에디터이름' or any('A붙기직전' in x for x in puts): fail('edge-2 다시 연결을 견주기 전에 저장 타이머가 더 새 초안을 덮음: 서버 %r' % mid)
    if not pump(pg, lambda: any('더 새로워요' in m for m in asked), 10000): fail('edge-2 에디터를 연 채 다시 연결됐는데 더 새 초안을 가져올지 묻지 않음 · 서버 %r' % draft_of(s6))
    if not pump(pg, lambda: pg.input_value('[data-f="svc.name"]') == 'B에디터이름', 6000):
        fail('edge-2 가져온 초안을 에디터에 다시 그리지 않음: %r' % pg.input_value('[data-f="svc.name"]'))
    pg.wait_for_timeout(3500)
    if draft_of(s6) != 'B에디터이름' or any('A붙기직전' in x for x in puts): fail('edge-2 가져온 뒤에도 이 기기 것을 올림: 서버 %r' % draft_of(s6))
    # 그 뒤 고친 것은 전처럼 저절로 올라간다
    pg.fill('[data-f="svc.name"]', 'A이어서 고침')
    if not poll(lambda: draft_of(s6) == 'A이어서 고침', 8000): fail('edge-2 가져온 뒤 고친 초안이 안 올라감: %r' % draft_of(s6))
    print('edge-2 에디터를 연 채 다시 연결: 바로 물어 가져오고 · 저장 타이머가 덮지 않고 · 이어 고친 것은 올라감 ok')

    # 4-3) 같은 자리에서 '취소'(이 기기 것 유지)하면 약속대로 이 기기 것을 올린다
    s7 = in_editor('지킬 예배', '곡7')
    newer_on_b(s7, 'B버릴이름')
    asked.clear(); pg.dismiss = True
    c.set_offline(False)
    if not pump(pg, lambda: any('더 새로워요' in m for m in asked), 10000): fail('edge-2 에디터를 연 채 다시 연결됐는데 묻지 않음 (취소 경우)')
    if not poll(lambda: draft_of(s7) == '지킬 예배 끊김', 8000): fail('edge-2 취소(이 기기 것 유지)했는데 서버에 안 올라감: %r' % draft_of(s7))
    pg.dismiss = False
    if pg.input_value('[data-f="svc.name"]') != '지킬 예배 끊김': fail('edge-2 취소했는데 에디터가 바뀜: %r' % pg.input_value('[data-f="svc.name"]'))
    print('edge-2 에디터를 연 채 다시 연결 · 취소: 이 기기 것을 올림 ok')
    if pg.errs: fail('JS 오류: %s' % pg.errs[:3])
    cB.close()

    # 5) 팀원: 끊긴 사이 메모를 쓴 콘티가 그 사이 지워졌으면 다시 연결돼도 그 메모는 올리지 않는다 (서버는 콘티를 안 보고 받아
    #    볼 사람 없는 줄로 남았다) — 남아 있는 콘티의 메모는 그대로 올라간다
    cM, _, _ = account(b, 'omm', '민수', service_workers='block')
    ok(cM.request.post(URL + 'api/invite/%s/join' % invite_code(c, team), headers=H, data={'name': '민수', 'sessions': ['드럼']}), '가입')
    s5 = new_published(pg, '지워질 예배', '곡5')
    pm = page(cM, '#/view/' + s5, '#app .top'); pm.wait_for_timeout(1500)
    open_view(pm, s2); pm.wait_for_timeout(1500)
    pm.evaluate("location.hash='#/home'"); pm.wait_for_timeout(4500)
    cM.set_offline(True); pm.wait_for_timeout(300)
    ne, nf = 'ne' + tag, 'nf' + tag
    pm.evaluate(ADD_NOTE, [s5, ne, '지워질 콘티 메모'])
    pm.evaluate(ADD_NOTE, [s2, nf, '남는 콘티 메모'])
    ok(c.request.delete(URL + 'api/services/%s?team=%s' % (s5, team), headers=H), '지우기')
    cM.set_offline(False)
    if not poll(lambda: nf in server_notes(cM, team, s2), 8000): fail('edge-2 팀원이 끊긴 사이 쓴 메모가 다시 연결돼도 안 올라감')
    pm.wait_for_timeout(1500)
    if ne in server_notes(cM, team, s5): fail('edge-2 끊긴 사이 지워진 콘티의 메모를 서버에 올림')
    if pm.errs: fail('JS 오류 (팀원): %s' % pm.errs[:3])
    print('edge-2 팀원: 지워진 콘티의 메모는 안 올리고 남은 콘티 것은 올림 ok')
    cM.close()
    c.close()

# ---------------------------------------------------------------- edge-3
def sec_join(b):
    cA, _, _ = account(b, 'ja', '에이'); tA = make_team(cA, '에이팀'); codeA = invite_code(cA, tA)
    cB, _, _ = account(b, 'jb', '비'); tB = make_team(cB, '비팀'); codeB = invite_code(cB, tB)
    cJ, _, _ = account(b, 'jj', '제이', service_workers='block')
    pg = page(cJ, '#/join/' + codeA, '[data-act="team-join"]')
    if '에이팀' not in pg.locator('h1').first.inner_text(): fail('준비: 첫 초대가 에이팀이 아님')
    pg.evaluate("(c)=>{location.hash='#/join/'+c}", codeB)
    if not wait_until(pg, "(c)=>{const b=document.querySelector('[data-act=\"team-join\"]');return !!b&&b.dataset.tok===c}", 8000, codeB): fail('준비: 새 초대 단추가 안 그려짐')
    pg.wait_for_timeout(300)
    h1 = pg.locator('h1').first.inner_text(); btn = pg.locator('[data-act="team-join"]').inner_text()
    if '비팀' not in h1 or '에이팀' in h1: fail('edge-3 주소가 다른 초대로 바뀌었는데 앞 초대의 팀이 보임: %r' % h1)
    if '비팀' not in btn: fail('edge-3 가입 단추의 팀 이름이 새 초대가 아님: %r' % btn)
    print('edge-3 같은 탭에서 다른 초대로 바뀌면 그 초대의 팀을 보임 ok')

    # 늦게 온 앞 초대의 답이 새 초대를 덮지 않는다
    def slow(route):
        time.sleep(1.2); route.continue_()
    pg.route('**/api/invite/%s' % codeA, slow)
    pg.evaluate("(c)=>{location.hash='#/join/'+c}", codeA); pg.wait_for_timeout(150)
    pg.evaluate("(c)=>{location.hash='#/join/'+c}", codeB)
    pg.wait_for_timeout(2500)
    h1 = pg.locator('h1').first.inner_text()
    if '비팀' not in h1 or pg.get_attribute('[data-act="team-join"]', 'data-tok') != codeB: fail('edge-3 늦게 온 앞 초대가 새 초대 화면을 덮음: %r' % h1)
    pg.unroute('**/api/invite/%s' % codeA)
    print('edge-3 늦게 온 앞 초대의 답은 버림 ok')

    # 못 연 초대(잘못된 링크) 뒤에 맞는 링크로 바꾸면 그 팀이 뜬다
    pg.evaluate("location.hash='#/join/zzbadtoken00'")
    if not wait_until(pg, "document.querySelector('#app h1')&&/열 수 없어요/.test(document.querySelector('#app h1').textContent)", 8000): fail('준비: 잘못된 초대가 오류로 안 뜸')
    pg.evaluate("(c)=>{location.hash='#/join/'+c}", codeA)
    if not wait_until(pg, "(c)=>{const b=document.querySelector('[data-act=\"team-join\"]');return !!b&&b.dataset.tok===c}", 8000, codeA): fail('edge-3 못 연 초대 뒤 맞는 링크로 바꿔도 오류가 남음')
    if '에이팀' not in pg.locator('h1').first.inner_text(): fail('edge-3 못 연 초대 뒤 바꾼 링크의 팀이 아님')
    # 가입하면 화면에 보인 팀에 들어간다
    pg.evaluate("(c)=>{location.hash='#/join/'+c}", codeB)
    if not wait_until(pg, "(c)=>{const b=document.querySelector('[data-act=\"team-join\"]');return !!b&&b.dataset.tok===c}", 8000, codeB): fail('준비: 비팀 초대가 안 뜸')
    shown = pg.locator('h1').first.inner_text()
    pg.click('[data-act="team-join"]'); pg.wait_for_selector('.shell[data-page]', timeout=10000)
    me = ok(cJ.request.get(URL + 'api/me'), 'me')
    names = [t.get('teamName') for t in me.get('teams', [])]
    if names != ['비팀'] or '비팀' not in shown: fail('edge-3 화면에 보인 팀(%r)과 들어간 팀(%r)이 다름' % (shown, names))
    if pg.errs: fail('JS 오류: %s' % pg.errs[:3])
    print('edge-3 못 연 초대 뒤 맞는 링크 · 가입은 화면에 보인 팀으로 ok')
    cA.close(); cB.close(); cJ.close()

# ---------------------------------------------------------------- edge-4
def sec_team_offline(b):
    c, u, uid = account(b, 'ot', '하은', service_workers='block')
    team = make_team(c, '오프팀')
    pg = page(c)
    pg.wait_for_timeout(800)
    off = lambda r: r.abort('internetdisconnected')
    pg.route('**/api/**', off)
    pg.reload(); pg.wait_for_selector('.shell[data-page]', timeout=15000); pg.wait_for_timeout(800)
    if pg.evaluate('CONTI.NET.server') is True: fail('준비: 서버를 막았는데 붙었다고 봄')
    pill = pg.locator('.side .pill').first.inner_text()
    body = pg.locator('#app').inner_text()
    if '기기 전용' in pill or '오프팀' not in pill or '오프라인' not in pill: fail('edge-4 오프라인 팀원의 사이드바가 팀 이름·오프라인이 아님: %r' % pill)
    if '카톡으로 보내세요' in body or '이 기기에만 저장돼요' in body: fail('edge-4 오프라인 팀원에게 내보내기 파일을 카톡으로 보내라는 안내가 뜸')
    sub = pg.locator('.sect-hd p').first.inner_text()
    if '오프팀' not in sub or '연결되지 않았' not in sub: fail('edge-4 홈 안내가 팀 이름·오프라인 안내가 아님: %r' % sub)
    print('edge-4 오프라인 팀원 홈: 팀 이름 + 오프라인 안내 ok')
    pg.evaluate("location.hash='#/settings'"); pg.wait_for_selector('.setpane', timeout=8000); pg.wait_for_timeout(300)
    txt = pg.locator('#app').inner_text()
    if '이 기기 전용' in txt or '기기 전용' in pg.locator('.side .pill').first.inner_text(): fail('edge-4 오프라인 팀원 설정이 이 기기 전용으로 보임')
    if pg.locator('#sRole').count(): fail('edge-4 오프라인 팀원 설정에 기기 전용 역할(인도자/멤버) 고르기가 보임')
    pg.fill('#sName', '바뀐이름'); pg.click('#sOk'); pg.wait_for_timeout(300)
    if '연결되지 않았' not in pg.locator('#sErr').inner_text(): fail('edge-4 오프라인 팀원이 내 정보를 저장하면 알리지 않음')
    if pg.evaluate("CONTI.S.team.me.name") == '바뀐이름': fail('edge-4 오프라인 팀원의 내 정보를 기기에만 적음 (다시 연결되면 말없이 덮임)')
    print('edge-4 오프라인 팀원 설정: 팀 표시 · 역할 고르기 없음 · 저장은 연결 뒤로 ok')
    pg.unroute('**/api/**', off)
    pg.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
    if not wait_until(pg, "CONTI.NET.server===true", 8000): fail('준비: 다시 안 붙음')
    pg.evaluate("location.hash='#/home'"); pg.wait_for_timeout(800)
    pill = pg.locator('.side .pill').first.inner_text()
    if pill.strip() != '오프팀': fail('edge-4 다시 붙었는데 사이드바가 팀 이름만이 아님: %r' % pill)
    if pg.errs: fail('JS 오류: %s' % pg.errs[:3])
    print('edge-4 다시 붙으면 오프라인 표시가 사라짐 ok')
    c.close()

# ---------------------------------------------------------------- edge-5
def sec_gate(b):
    # 1) 서비스 워커로 연 사이트를 로그아웃한 채 오프라인으로 다시 연다 (운영에서 본 그대로)
    c = b.new_context(viewport={'width': 1240, 'height': 900})
    pg = page(c, '', '#lgUser')
    if not wait_until(pg, "!!(navigator.serviceWorker&&navigator.serviceWorker.controller)", 15000): fail('준비: 서비스 워커가 페이지를 안 잡음')
    c.set_offline(True); pg.reload(); pg.wait_for_timeout(2500)
    if pg.evaluate('location.hash') == '#/settings' or pg.locator('#sRole').count(): fail('edge-5 로그아웃한 채 오프라인으로 열면 기기 전용 첫 설정이 뜸')
    if not pg.locator('#lgUser').count(): fail('edge-5 로그아웃한 채 오프라인으로 열었는데 로그인 화면이 아님')
    if not pg.locator('#offNote').count() or '연결되지 않았' not in pg.locator('#offNote').inner_text(): fail('edge-5 오프라인 로그인 화면에 안내가 없음')
    if pg.locator('.side').count(): fail('edge-5 오프라인 로그인 화면에 앱 사이드바(기기 전용)가 보임')
    pg.fill('#lgUser', 'nobody'); pg.fill('#lgPass', 'secret1'); pg.click('[data-act="lg-submit"]'); pg.wait_for_timeout(1500)
    if '연결되지 않았' not in pg.locator('#lgErr').inner_text(): fail('edge-5 오프라인에서 로그인을 누르면 알리지 않음: %r' % pg.locator('#lgErr').inner_text())
    c.set_offline(False)
    if not wait_until(pg, "CONTI.NET.server===true", 10000): fail('edge-5 다시 연결됐는데 서버에 안 붙음')
    pg.wait_for_timeout(500)
    if pg.locator('#offNote').count() or not pg.locator('#lgUser').count(): fail('edge-5 다시 연결된 로그인 화면에 오프라인 안내가 남음')
    if pg.evaluate("document.querySelector('#lgUser').value") != 'nobody': fail('edge-5 다시 연결되며 친 아이디가 사라짐')
    if pg.errs: fail('JS 오류: %s' % pg.errs[:3])
    print('edge-5 로그아웃한 채 오프라인(서비스 워커): 로그인 화면 + 안내 · 다시 연결되면 그대로 로그인 화면 ok')
    c.close()

    # 2) 서버만 안 닿는(브라우저는 온라인) 로그인 화면에서 누르면 다시 찾아 보고, 찾으면 친 값으로 그대로 로그인한다
    cL, uL, _ = account(b, 'og', '하은'); make_team(cL, '게이트팀'); cL.close()
    c = b.new_context(viewport={'width': 1240, 'height': 900}, service_workers='block')
    pg = page(c, '', '#lgUser')
    off = lambda r: r.abort('internetdisconnected')
    pg.route('**/api/**', off)
    pg.reload(); pg.wait_for_selector('#lgUser', timeout=15000); pg.wait_for_timeout(500)
    if not pg.locator('#offNote').count(): fail('edge-5 서버가 안 닿는 로그인 화면에 안내가 없음')
    pg.fill('#lgUser', uL); pg.fill('#lgPass', 'secret1')
    pg.click('[data-act="lg-submit"]'); pg.wait_for_timeout(1200)
    if '연결되지 않았' not in pg.locator('#lgErr').inner_text(): fail('edge-5 서버가 안 닿는데 로그인을 누르면 알리지 않음')
    pg.unroute('**/api/**', off)
    pg.click('[data-act="lg-submit"]')
    try: pg.wait_for_selector('.shell[data-page]', timeout=12000)
    except Exception: fail('edge-5 서버가 다시 닿은 뒤 로그인을 누르면 그대로 로그인되지 않음: %r' % pg.locator('#lgErr').inner_text())
    if pg.evaluate('CONTI.S.team.name') != '게이트팀' or pg.evaluate('CONTI.NET.server') is not True: fail('edge-5 로그인 뒤 팀·연결 상태가 이상함')
    if pg.errs: fail('JS 오류: %s' % pg.errs[:3])
    print('edge-5 서버가 다시 닿으면 누른 로그인이 그대로 이어짐 ok')
    c.close()

    # 3) 로그인했지만 팀이 없는 사람도 오프라인이면 기기 전용 대신 안내 → 다시 붙으면 팀 만들기 화면
    c, u, _ = account(b, 'on', '민수', service_workers='block')
    pg = page(c, '#/home', '#gtTeam')
    pg.route('**/api/**', off)
    pg.reload(); pg.wait_for_timeout(2500)
    if pg.evaluate('location.hash') == '#/settings' or pg.locator('#sRole').count(): fail('edge-5 팀 없는 사람이 오프라인으로 열면 기기 전용 첫 설정이 뜸')
    if not pg.locator('#offNote').count(): fail('edge-5 팀 없는 사람의 오프라인 화면에 안내가 없음')
    pg.unroute('**/api/**', off)
    pg.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
    try: pg.wait_for_selector('#gtTeam', timeout=10000)
    except Exception: fail('edge-5 팀 없는 사람이 다시 붙었는데 팀 만들기 화면으로 안 감')
    print('edge-5 팀 없는 사람: 오프라인 안내 → 다시 붙으면 팀 만들기 ok')
    c.close()

    # 4) 앱(네이티브)을 처음부터 오프라인으로 켜도 로그인 화면 + 안내 (앱은 늘 서버가 있는 앱이다)
    c = b.new_context(viewport={'width': 1180, 'height': 820}, service_workers='block')
    def app_files(route):
        path = route.request.url.split('https://localhost', 1)[1].split('?')[0].split('#')[0] or '/'
        if path == '/': path = '/index.html'
        f = os.path.join(ROOT, 'app', path.lstrip('/'))
        if not os.path.isfile(f): return route.fulfill(status=404, body='')
        route.fulfill(status=200, body=open(f, 'rb').read(), headers={'content-type': 'text/html; charset=utf-8' if f.endswith('.html') else 'application/octet-stream'})
    c.route(re.compile(r'^https://localhost(/.*)?$'), app_files)
    c.route(re.compile(r'^https://lets1414\.com(/.*)?$'), lambda r: r.abort('internetdisconnected'))   # 운영에는 절대 안 나간다
    pn = c.new_page(); errs = []; pn.on('pageerror', lambda e: errs.append(str(e)))
    pn.goto('https://localhost/'); pn.wait_for_timeout(3000)
    if pn.evaluate('location.hash') == '#/settings' or pn.locator('#sRole').count(): fail('edge-5 앱을 처음부터 오프라인으로 켜면 기기 전용 첫 설정이 뜸')
    if not pn.locator('#lgUser').count() or not pn.locator('#offNote').count(): fail('edge-5 앱을 오프라인으로 켰는데 로그인 화면 + 안내가 아님')
    if errs: fail('JS 오류 (앱): %s' % errs[:3])
    print('edge-5 앱을 처음부터 오프라인으로 켜도 로그인 화면 + 안내 ok')
    c.close()

    # 5) 서버가 없는 곳(정적 호스팅 — /api 가 404)은 예전처럼 기기 전용이고, 그 곳을 오프라인으로 열어도 기기 전용이다
    c = b.new_context(viewport={'width': 1240, 'height': 900}, service_workers='block')
    c.route('**/api/**', lambda r: r.fulfill(status=404, body='not found'))
    pg = c.new_page(); pg.errs = []; pg.on('pageerror', lambda e: pg.errs.append(str(e)[:200]))
    pg.goto(URL); pg.wait_for_timeout(2000)
    if pg.evaluate('CONTI.NET.server') is not False: fail('준비: 404 인데 서버 없음(false)으로 안 봄')
    if pg.evaluate('location.hash') != '#/settings' or not pg.locator('#sRole').count() or pg.locator('#lgUser').count(): fail('정적 호스팅(서버 없음)의 기기 전용 첫 설정이 깨짐')
    c.unroute('**/api/**'); c.route('**/api/**', lambda r: r.abort('internetdisconnected'))
    pg.goto(URL + '#/home'); pg.reload(); pg.wait_for_timeout(2000)
    if pg.locator('#lgUser').count() or not pg.locator('#sRole').count(): fail('정적 호스팅을 오프라인으로 열었는데 기기 전용 대신 로그인 화면이 뜸')
    if pg.errs: fail('JS 오류: %s' % pg.errs[:3])
    print('정적 호스팅(서버 없음)은 온·오프라인 모두 기기 전용 그대로 ok')
    c.close()

    # 6) 없는 주소에 index.html 을 200 으로 주는 정적 호스팅(SPA fallback — Cloudflare Pages 기본값, app/ 에는 404.html 이 없다):
    #    서버 확인이 늘 모름(null)이라 전에는 인터넷이 되는데도 로그인 화면 + '연결되지 않았어요'에 갇혔다 → 서버가 있다는 증거가 없으면 기기 전용
    html = open(os.path.join(ROOT, 'app', 'index.html'), 'rb').read()
    c = b.new_context(viewport={'width': 1240, 'height': 900}, service_workers='block')
    c.route('**/api/**', lambda r: r.fulfill(status=200, body=html, headers={'content-type': 'text/html; charset=utf-8'}))
    pg = c.new_page(); pg.errs = []; pg.on('pageerror', lambda e: pg.errs.append(str(e)[:200]))
    pg.goto(URL); pg.wait_for_timeout(2500)
    if pg.evaluate('CONTI.NET.server') is not None: fail('준비: SPA fallback 인데 서버 확인이 모름(null)이 아님')
    if pg.locator('#lgUser').count() or pg.locator('#offNote').count(): fail('SPA fallback 정적 호스팅이 로그인 화면 + 오프라인 안내에 갇힘')
    if pg.evaluate('location.hash') != '#/settings' or not pg.locator('#sRole').count(): fail('SPA fallback 정적 호스팅의 기기 전용 첫 설정이 안 뜸')
    pg.fill('#sName', '정적'); pg.click('#sOk'); pg.wait_for_timeout(500)
    pg.reload(); pg.wait_for_timeout(2500)
    if pg.locator('#lgUser').count() or not pg.locator('.side').count(): fail('SPA fallback 정적 호스팅을 다시 열었는데 기기 전용이 아님')
    if pg.errs: fail('JS 오류: %s' % pg.errs[:3])
    print('SPA fallback 정적 호스팅(서버 확인이 늘 모름)도 기기 전용 그대로 ok')
    c.close()

    # 7) 정적 호스팅(404)을 처음부터 오프라인으로 열면 — 받아 둔 답이 없으니 기기 전용 (전에는 로그인 화면에 갇혀 새로고침해야 했다)
    c = b.new_context(viewport={'width': 1240, 'height': 900}, service_workers='block')
    c.route('**/api/**', lambda r: r.abort('internetdisconnected'))
    pg = c.new_page(); pg.errs = []; pg.on('pageerror', lambda e: pg.errs.append(str(e)[:200]))
    pg.goto(URL); pg.wait_for_timeout(2500)
    if pg.locator('#lgUser').count() or not pg.locator('#sRole').count(): fail('받아 둔 답이 없는 곳을 오프라인으로 열었는데 기기 전용이 아님')
    c.close()
    # 서버가 있던 곳으로 기억해 오프라인 로그인 화면을 띄운 채 '서버 없음(404)'을 받으면 새로고침 없이 기기 전용으로 다시 그린다
    c = b.new_context(viewport={'width': 1240, 'height': 900}, service_workers='block')
    pg = page(c, '', '#lgUser')
    if pg.evaluate("localStorage.getItem('conti-server')") != '1': fail('준비: 서버 답을 기억하지 않음')
    c.route('**/api/**', off)
    pg.reload(); pg.wait_for_selector('#offNote', timeout=10000)
    c.unroute('**/api/**', off); c.route('**/api/**', lambda r: r.fulfill(status=404, body='not found'))
    pg.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
    try: pg.wait_for_selector('#sRole', timeout=8000)
    except Exception: fail('오프라인 로그인 화면에서 서버 없음(404)을 받았는데 기기 전용으로 안 바뀜 (새로고침해야 함)')
    if pg.locator('#lgUser').count(): fail('서버 없음을 받은 뒤에도 로그인 화면이 남음')
    if pg.errs: fail('JS 오류: %s' % pg.errs[:3])
    print('받아 둔 답이 없으면 오프라인이라도 기기 전용 · 로그인 화면에서 서버 없음을 받으면 바로 기기 전용 ok')
    c.close()

def run():
    only = set(sys.argv[1:])
    secs = [('memo', sec_memo), ('join', sec_join), ('team', sec_team_offline), ('gate', sec_gate)]
    with sync_playwright() as p:
        b = p.chromium.launch()
        for name, fn in secs:
            if only and name not in only: continue
            fn(b)
        b.close()
    print('OK test_webfix_offline')

run()
