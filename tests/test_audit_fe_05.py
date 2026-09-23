# 감사 fe-05: 라이브러리 ↔ 콘티 동기화
#  F23  라이브러리 곡의 영상을 바꿔도 발행된 콘티의 타임라인 메모가 안 지워진다 (멤버·인도자)
#  F24  '폴더로 옮기기'를 여러 번 해도 전에 옮긴 곡이 다시 옮겨지지 않는다
#  F85  켜 둔 폴더·태그 칩이 목록에서 빠져도 그려져서 풀 수 있다
#  F86  에디터의 '라이브러리에서 추가 → 새 곡'은 지금 고치는 예배를 고른다 (8주 밖이어도)
#  F84  제목을 쓰다 멈춰도 쓰다 만 제목으로 라이브러리 곡이 생기지 않는다
#  G16  서버 한도보다 긴 곡 메모·송폼이 콘티에서 말없이 잘리지 않는다
#  G17  편곡 채우기가 한 번 실패해도 다음에 다시 민다
#  F132 곡 만들기 응답을 못 받고 다시 보내도 곡이 두 벌 생기지 않는다
#  F133 '만들기'를 두 번 눌러도 곡은 하나
#  F83  같은 파일을 동시에 두 번 받지 않는다
#  G32  인도자에서 내려오면 못 올린 라이브러리 수정을 버리고 서버 것을 받는다
import os, sys, time, json, random, datetime
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
tag = str(int(time.time()))[-6:] + str(random.randint(10, 99))
H = {'x-conti': '1'}
errs = []
def fail(m): print('FAIL:', m); sys.exit(1)

def mk(b, k, name):
  c = b.new_context(viewport={'width': 1300, 'height': 950}, service_workers='block')
  r = c.request.post(URL + 'api/auth/signup', headers=H, data={'name': name, 'username': k + tag, 'password': 'secret1'})
  if not r.ok: fail('가입 실패 %s %s' % (k, r.text()[:200]))
  return c, r.json()['user']['id']

def page(c, who):
  pg = c.new_page()
  pg.on('pageerror', lambda e: errs.append(who + ': ' + (getattr(e, 'stack', None) or str(e))[:400]))
  pg.on('dialog', lambda d: d.accept())
  return pg

def boot(pg, h='#/home'):
  pg.goto(URL + h); pg.wait_for_function('window.CONTI && CONTI.S.team.id', timeout=15000); pg.wait_for_timeout(1500)

def songs(c, team):
  return c.request.get(URL + 'api/songs?team=' + team).json()['songs']

def add_to_new_service(pg, sid, name):
  pg.goto(URL + '#/library/' + sid); pg.wait_for_selector('.acard', timeout=10000); pg.wait_for_timeout(400)
  pg.click('[data-arradd]'); pg.wait_for_selector('#atsGo', timeout=6000)
  pg.click('[data-ats="new"]'); pg.wait_for_selector('#atsName', timeout=5000)
  pg.fill('#atsName', name); pg.click('#atsGo'); pg.wait_for_selector('[data-f="item.title"]', timeout=10000); pg.wait_for_timeout(600)
  return pg.evaluate("CONTI.route().a")

def publish(pg, svc):
  pg.goto(URL + '#/edit/' + svc); pg.wait_for_selector('[data-act="publish"]', timeout=10000); pg.wait_for_timeout(300)
  pg.click('[data-act="publish"]'); pg.wait_for_selector('#pubOnly', timeout=6000); pg.click('#pubOnly'); pg.wait_for_timeout(3500)

def pull_songs(pg):
  pg.evaluate("async()=>{CONTI.S.songsAt='';await CONTI.pullSongs(true)}"); pg.wait_for_timeout(500)

def run():
  with sync_playwright() as p:
    b = p.chromium.launch()
    A, aid = mk(b, 'fa', '인도')
    team = A.request.post(URL + 'api/teams', headers=H, data={'name': '감사팀' + tag, 'myName': '인도', 'session': '인도자'}).json()['teamId']
    L = page(A, 'L')

    # ================= F23 =================
    oldMedia = [{'id': 'mOld' + tag, 'type': 'youtube', 'url': 'https://www.youtube.com/watch?v=aaaaaaaaaaa', 'name': '', 'start': 0, 'end': 0, 'notes': []}]
    s = A.request.post(URL + 'api/songs', headers=H, data={'teamId': team, 'title': '주 은혜임을', 'key': 'G', 'media': oldMedia}).json()['song']
    sid, arr = s['id'], s['arrangements'][0]['id']
    boot(L); pull_songs(L)
    svc = add_to_new_service(L, sid, '메모 예배')
    publish(L, svc)
    item = L.evaluate("(()=>{const s=CONTI.S.services.find(x=>x.id===%r);const it=s.published.items[0];return {id:it.id,media:it.media.map(m=>m.id)}})()" % svc)
    if len(item['media']) != 1: fail('발행본에 영상이 없음: %s' % item)
    mid = item['media'][0]
    code = A.request.post(URL + 'api/teams/%s/invites' % team, headers=H, data={'role': 'member'}).json()['invite']['code']
    B, bid = mk(b, 'fb', '멤버')
    j = B.request.post(URL + 'api/invite/%s/join' % code, headers=H, data={'name': '멤버', 'sessions': ['드럼']})
    if not j.ok: fail('멤버 합류 실패 %s' % j.text()[:200])
    r = B.request.post(URL + 'api/notes', headers=H, data={'teamId': team, 'serviceId': svc, 'notes': [
      {'id': 'nMem' + tag, 'itemId': item['id'], 'mediaId': mid, 't': 42, 'layer': 'mine', 'text': '여기서 필인'}]})
    r2 = A.request.post(URL + 'api/notes', headers=H, data={'teamId': team, 'serviceId': svc, 'notes': [
      {'id': 'nLed' + tag, 'itemId': item['id'], 'mediaId': mid, 't': 60, 'layer': 'leader', 'text': '여기서 전조'}]})
    if not (r.ok and r2.ok): fail('메모 만들기 실패')
    M = page(B, 'M'); boot(M, '#/play/%s/0' % svc); M.wait_for_timeout(2000)
    L.goto(URL + '#/view/' + svc); L.wait_for_timeout(2500)
    def srv_notes(c): return sorted(n['text'] for n in c.request.get(URL + 'api/notes?team=%s&service=%s' % (team, svc)).json()['notes'])
    if srv_notes(B) != ['여기서 전조', '여기서 필인']: fail('처음 메모가 이상함: %s' % srv_notes(B))
    # 인도자가 라이브러리 곡의 영상 주소를 바꾼다
    newMedia = [{'id': 'mNew' + tag, 'type': 'youtube', 'url': 'https://www.youtube.com/watch?v=bbbbbbbbbbb', 'name': '', 'start': 0, 'end': 0, 'notes': []}]
    A.request.patch(URL + 'api/arrangements/' + arr, headers=H, data={'teamId': team, 'media': newMedia})
    # 멤버: 앱을 다시 열고 곡 목록을 받은 뒤 그 콘티를 연다
    M.goto(URL + '#/home'); M.reload(); M.wait_for_function('window.CONTI && CONTI.S.team.id', timeout=15000); M.wait_for_timeout(1500)
    pull_songs(M)
    M.goto(URL + '#/play/%s/0' % svc); M.wait_for_timeout(3000)
    mm = M.evaluate("CONTI.S.services.find(x=>x.id===%r).items[0].media.map(m=>m.id)" % svc)
    if mm != [mid]: fail('멤버의 발행본 영상이 라이브러리를 따라 바뀜: %s' % mm)
    if srv_notes(B) != ['여기서 전조', '여기서 필인']: fail('F23 멤버 기기에서 메모가 지워짐: %s' % srv_notes(B))
    print('F23 member keeps published media + notes ok')
    # 인도자: 초안은 따라오지만(명세) 발행본의 영상에 달린 메모는 지우지 않는다
    pull_songs(L)
    d = L.evaluate("(()=>{const s=CONTI.S.services.find(x=>x.id===%r);return {draft:s.items[0].media.map(m=>m.url),pub:s.published.items[0].media.map(m=>m.id)}})()" % svc)
    if d['draft'] != [newMedia[0]['url']]: fail('초안은 라이브러리를 따라와야 함: %s' % d)
    if d['pub'] != [mid]: fail('발행본이 흔들림: %s' % d)
    L.goto(URL + '#/edit/' + svc); L.wait_for_timeout(1500)
    L.goto(URL + '#/view/' + svc); L.wait_for_timeout(2500)
    L.evaluate("async()=>{await CONTI.SYNC.pushNotes(CONTI.S.services.find(x=>x.id===%r))}" % svc); L.wait_for_timeout(500)
    if srv_notes(B) != ['여기서 전조', '여기서 필인']: fail('F23 인도자 기기에서 메모가 지워짐: %s' % srv_notes(B))
    print('F23 leader draft follows, published notes kept ok')
    # 화면에 있는 영상의 메모를 멤버가 지우면 그건 진짜로 지운다
    M.evaluate("""async()=>{const s=CONTI.S.services.find(x=>x.id===%r);const m=s.items[0].media[0];
      m.notes=(m.notes||[]).filter(n=>n.id!=='nMem%s');await CONTI.SYNC.pushNotes(s)}""" % (svc, tag)); M.wait_for_timeout(500)
    if srv_notes(B) != ['여기서 전조']: fail('멤버가 지운 메모가 서버에 남음: %s' % srv_notes(B))
    print('F23 genuine delete still works ok')
    M.close()

    # ================= F24 · F85 =================
    for t in ['가곡', '나곡', '다곡']:
      A.request.post(URL + 'api/songs', headers=H, data={'teamId': team, 'title': t + tag})
    L.goto(URL + '#/library'); pull_songs(L); L.wait_for_timeout(500)
    def sel(title):
      L.evaluate("t=>{CONTI.LIB.pick='multi';CONTI.LIB.sel=(CONTI.S.songs||[]).filter(s=>s.title===t).map(s=>s.id);CONTI.render()}", title + tag)
      L.wait_for_timeout(500)
    def folders():
      return {s['title'][:2]: s['folder'] for s in songs(A, team) if s['title'].endswith(tag) and s['title'][:2] in ('가곡', '나곡', '다곡')}
    sel('가곡'); L.click('[data-act="lib-move"]'); L.wait_for_selector('#mvNew', timeout=5000)
    L.fill('#mvNew', 'X'); L.click('#mvGo'); L.wait_for_timeout(2000)
    sel('나곡'); L.click('[data-act="lib-move"]'); L.wait_for_selector('#modal [data-mv="X"]', timeout=5000)
    L.click('#modal [data-mv="X"]'); L.wait_for_timeout(2000)
    sel('다곡'); L.click('[data-act="lib-move"]'); L.wait_for_selector('#modal [data-mv=""]', timeout=5000)
    L.click('#modal [data-mv=""]'); L.wait_for_timeout(2500)
    f = folders()
    if f != {'가곡': 'X', '나곡': 'X', '다곡': ''}: fail('F24 옛 곡까지 다시 옮겨짐: %s' % f)
    print('F24 move modal listeners do not pile up ok')

    # F85: X 폴더로 거른 채 두 곡을 모두 빼면 X 칩이 남아 있어 풀 수 있다
    L.evaluate("()=>{CONTI.LIB.pick=null;CONTI.LIB.sel=[];CONTI.render()}"); L.wait_for_timeout(300)
    L.click('[data-lf="folder"][data-v="X"]'); L.wait_for_timeout(500)
    if L.locator('#libList .songrow').count() != 2: fail('X 폴더에 두 곡이 안 보임')
    L.evaluate("()=>{CONTI.LIB.pick='multi';CONTI.LIB.sel=(CONTI.S.songs||[]).filter(s=>(s.folder||'')==='X').map(s=>s.id);CONTI.render()}"); L.wait_for_timeout(500)
    L.click('[data-act="lib-move"]'); L.wait_for_selector('#modal [data-mv=""]', timeout=5000)
    L.click('#modal [data-mv=""]'); L.wait_for_timeout(2500)
    chip = L.locator('[data-lf="folder"][data-v="X"]')
    if not chip.count(): fail('F85 켜 둔 폴더 칩이 사라짐 (끌 방법이 없음)')
    if 'on' not in (chip.get_attribute('class') or ''): fail('켜 둔 폴더 칩이 켜진 모양이 아님')
    txt = L.locator('#libList').inner_text()
    if '아직 곡이 없어요' in txt: fail('걸러서 빈 목록을 "아직 곡이 없어요"라고 함: %s' % txt)
    chip.click(); L.wait_for_timeout(500)
    if L.evaluate("CONTI.LIB.folder") != '': fail('칩을 눌러도 폴더 거르기가 안 풀림')
    if L.locator('#libList .songrow').count() < 3: fail('풀고 나서도 곡이 안 보임')
    # 태그가 20개 넘어 칩 목록 밖에 있는 태그로 걸러도 그 칩은 그린다
    tags = ['t%02d' % i for i in range(25)]
    tsid = [s['id'] for s in songs(A, team) if s['title'] == '다곡' + tag][0]
    A.request.patch(URL + 'api/songs/' + tsid, headers=H, data={'teamId': team, 'tags': tags})
    pull_songs(L)
    L.evaluate("()=>{CONTI.LIB.tag='t24';CONTI.render()}"); L.wait_for_timeout(400)
    tc = L.locator('[data-lf="tag"][data-v="t24"]')
    if not tc.count() or 'on' not in (tc.get_attribute('class') or ''): fail('F85 20개 밖 태그 칩이 안 그려짐')
    tc.click(); L.wait_for_timeout(300)
    if L.evaluate("CONTI.LIB.tag") != '': fail('태그 칩으로 안 풀림')
    print('F85 stale folder/tag chip can be cleared ok')

    # ================= F86 =================
    def new_svc(name, days):
      L.goto(URL + '#/home'); L.wait_for_selector('[data-act="new-svc"]', timeout=8000)
      L.click('[data-act="new-svc"]'); L.wait_for_selector('[data-f="svc.name"]', timeout=8000)
      L.fill('[data-f="svc.name"]', name)
      L.fill('[data-f="svc.date"]', (datetime.date.today() + datetime.timedelta(days=days)).isoformat()); L.wait_for_timeout(500)
      return L.evaluate("CONTI.route().a")
    near = new_svc('이번주 예배', 3)
    far = new_svc('수련회', 70)
    L.goto(URL + '#/edit/' + far); L.wait_for_selector('[data-act="add-lib"]', timeout=8000)
    L.click('[data-act="add-lib"]'); L.wait_for_selector('#lpNew', timeout=5000)
    L.click('#lpNew'); L.wait_for_selector('#nsTitle', timeout=5000)
    L.fill('#nsTitle', '수련회 새 곡' + tag); L.click('#nsOk'); L.wait_for_selector('#atsGo', timeout=8000)
    on = L.locator('#atsSvc .q.on').get_attribute('data-ats')
    if on != far: fail('F86 지금 고치는 예배가 아닌 %s 가 골라짐 (수련회 %s, 이번주 %s)' % (on, far, near))
    L.click('#atsGo'); L.wait_for_timeout(1500)
    if L.evaluate("CONTI.route().a") != far: fail('F86 다른 예배 에디터로 옮겨짐')
    got = L.evaluate("[CONTI.S.services.find(x=>x.id===%r).items.map(i=>i.title),CONTI.S.services.find(x=>x.id===%r).items.length]" % (far, near))
    if ('수련회 새 곡' + tag) not in got[0] or got[1] != 0: fail('F86 곡이 엉뚱한 예배에 들어감: %s' % got)
    print('F86 new song goes into the service being edited ok')

    # ================= F84 =================
    L.goto(URL + '#/edit/' + near); L.wait_for_selector('[data-act="add-item"]', timeout=8000)
    L.click('[data-act="add-item"]'); L.wait_for_selector('[data-f="item.title"]', timeout=5000); L.wait_for_timeout(300)
    ti = L.locator('[data-f="item.title"]')
    ti.click(); ti.press_sequentially('주님' + tag); L.wait_for_timeout(5500)   # 3초 디바운스가 지나도 아직 쓰는 중
    part = [s for s in songs(A, team) if s['title'] == '주님' + tag]
    if part: fail('F84 쓰다 만 제목으로 곡이 만들어짐')
    ti.press_sequentially('의 은혜'); L.click('[data-f="item.key"]'); L.wait_for_timeout(3000)
    names = [s['title'] for s in songs(A, team)]
    if ('주님' + tag + '의 은혜') not in names: fail('F84 칸을 떠난 뒤에도 곡이 안 만들어짐: %s' % names)
    if ('주님' + tag) in names: fail('F84 쓰다 만 제목 곡이 있음')
    linked = L.evaluate("(()=>{const s=CONTI.S.services.find(x=>x.id===%r);const it=s.items[s.items.length-1];const sg=CONTI.S.songs.find(x=>x.id===it.songId);return sg&&sg.title})()" % near)
    if linked != '주님' + tag + '의 은혜': fail('F84 콘티가 다른 곡에 이어짐: %r' % linked)
    print('F84 no song from a half-typed title ok')

    # ================= G16 =================
    s = A.request.post(URL + 'api/songs', headers=H, data={'teamId': team, 'title': '긴메모' + tag, 'key': 'G'}).json()['song']
    pull_songs(L)
    gsvc = add_to_new_service(L, s['id'], '긴 메모 예배')
    for sel_, n in [('item.key', '12'), ('item.mod', '12'), ('item.form', '500'), ('item.songNote', '300')]:
      if L.locator('[data-f="%s"]' % sel_).get_attribute('maxlength') != n: fail('G16 %s 칸에 한도(%s)가 없음' % (sel_, n))
    note = ('1절은 피아노만, 2절부터 드럼 들어오고 후렴에서 크게. 간주 끝나면 반 키 올려서 후렴 두 번. ' * 6).strip()
    form = ' – '.join(['A1', 'B', 'Int(4)', '(Down)A3B', 'C', 'C', '멘트', 'Outro(4)'] * 12)
    # 한도가 생기기 전에 적어 둔 긴 값(또는 가져온 콘티)
    L.evaluate("""([id,n,f])=>{const s=CONTI.S.services.find(x=>x.id===id);const it=s.items[0];it.songNote=n;it.form=f;s.editedAt=Date.now();CONTI.save()}""", [gsvc, note, form])
    L.evaluate("CONTI.pushSongs()"); L.wait_for_timeout(2500)
    sa = [x for x in songs(A, team) if x['id'] == s['id']][0]['arrangements'][0]
    if len(sa['songNote']) != 300 or len(sa['form']) != 500: fail('편곡이 안 채워짐: %d %d' % (len(sa['songNote']), len(sa['form'])))
    pull_songs(L); L.wait_for_timeout(500)
    it = L.evaluate("(()=>{const it=CONTI.S.services.find(x=>x.id===%r).items[0];return {n:it.songNote.length,f:it.form.length,ov:it.ov||{}}})()" % gsvc)
    if it['n'] != len(note) or it['f'] != len(form): fail('G16 콘티의 긴 값이 잘림: %s (원래 %d/%d)' % (it, len(note), len(form)))
    if not (it['ov'].get('songNote') and it['ov'].get('form')): fail('G16 라이브러리와 다르다는 표시가 없음: %s' % it)
    print('G16 long conti text not silently cut ok')

    # ================= G17 =================
    s = A.request.post(URL + 'api/songs', headers=H, data={'teamId': team, 'title': '재시도' + tag, 'key': 'G'}).json()['song']
    pull_songs(L)
    rsvc = add_to_new_service(L, s['id'], '재시도 예배')
    L.wait_for_timeout(4000)   # 곡을 넣은 저장의 밀기가 끝나게
    st = {'n': 0}
    def h503(route):
      if route.request.method == 'PATCH' and st['n'] == 0:
        st['n'] += 1; route.fulfill(status=503, body='{"error":"x","message":"잠시 끊김"}', headers={'content-type': 'application/json'})
      else: route.continue_()
    L.route('**/api/arrangements/**', h503)
    L.fill('[data-f="item.songNote"]', '후렴은 크게'); L.click('[data-f="item.key"]')
    for i in range(30):
      L.wait_for_timeout(500)
      if st['n']: break
    L.wait_for_timeout(1500); L.unroute('**/api/arrangements/**')
    if not st['n']: fail('편곡 채우기 요청이 안 나감')
    stamped = L.evaluate("(()=>{const s=CONTI.S.services.find(x=>x.id===%r);return s.songsPushedAt===s.editedAt})()" % rsvc)
    if stamped: fail('G17 실패했는데 다 민 것으로 표시함')
    L.evaluate("CONTI.pushSongs()"); L.wait_for_timeout(2000)
    sa = [x for x in songs(A, team) if x['id'] == s['id']][0]['arrangements'][0]
    if sa['songNote'] != '후렴은 크게': fail('G17 다시 밀지 않음: %r' % sa['songNote'])
    print('G17 failed fill retried ok')

    # ================= F132 =================
    import uuid
    u = str(uuid.uuid4())
    r1 = A.request.post(URL + 'api/songs', headers=H, data={'teamId': team, 'id': u, 'title': '같은요청' + tag, 'key': 'A'}).json()
    r2 = A.request.post(URL + 'api/songs', headers=H, data={'teamId': team, 'id': u, 'title': '같은요청' + tag, 'key': 'A'}).json()
    if r1['song']['id'] != u or r2['song']['id'] != u: fail('F132 id 를 안 따름: %s %s' % (r1['song']['id'], r2['song']['id']))
    if len(r2['song']['arrangements']) != 1 or r2['song']['arrangements'][0]['id'] != r1['song']['arrangements'][0]['id']: fail('F132 편곡이 두 벌')
    if [x['title'] for x in songs(A, team)].count('같은요청' + tag) != 1: fail('F132 같은 요청으로 곡이 두 벌')
    C, cid_ = mk(b, 'fc', '딴팀')
    t2 = C.request.post(URL + 'api/teams', headers=H, data={'name': '딴팀' + tag, 'myName': '딴팀', 'session': '인도자'}).json()['teamId']
    r3 = C.request.post(URL + 'api/songs', headers=H, data={'teamId': t2, 'id': u, 'title': '가로채기'})
    if r3.status != 409: fail('F132 다른 팀의 곡 id 로 만들기가 막히지 않음: %d' % r3.status)
    # 앱: 첫 요청은 서버에서 만들어졌는데 응답을 못 받음 → 다시 밀어도 한 벌
    L.goto(URL + '#/edit/' + near); L.wait_for_selector('[data-act="add-item"]', timeout=8000)
    L.click('[data-act="add-item"]'); L.wait_for_selector('[data-f="item.title"]', timeout=5000); L.wait_for_timeout(300)
    lost = {'n': 0}
    def hlost(route):
      if route.request.method == 'POST' and lost['n'] == 0:
        lost['n'] += 1; route.fetch(); route.abort()
      else: route.continue_()
    L.route('**/api/songs', hlost)
    L.fill('[data-f="item.title"]', '은혜 아니면' + tag); L.click('[data-f="item.key"]')
    for i in range(20):
      L.wait_for_timeout(500)
      if lost['n']: break
    L.wait_for_timeout(1000); L.unroute('**/api/songs')
    if not lost['n']: fail('곡 만들기 요청이 안 나감')
    L.evaluate("CONTI.pushSongs()"); L.wait_for_timeout(2500)
    n = [x['title'] for x in songs(A, team)].count('은혜 아니면' + tag)
    if n != 1: fail('F132 응답을 못 받은 뒤 다시 밀어 곡이 %d벌' % n)
    ok = L.evaluate("(()=>{const s=CONTI.S.services.find(x=>x.id===%r);const it=s.items[s.items.length-1];return !!it.songId&&!it.songReq})()" % near)
    if not ok: fail('F132 콘티가 곡에 안 이어짐')
    print('F132 idempotent song create ok')

    # ================= F133 =================
    posts = []
    L.on('request', lambda rq: posts.append(1) if rq.method == 'POST' and rq.url.endswith('/api/songs') else None)
    L.goto(URL + '#/library'); L.wait_for_selector('[data-act="lib-new"]', timeout=8000)
    L.click('[data-act="lib-new"]'); L.wait_for_selector('#nsTitle', timeout=5000)
    L.fill('#nsTitle', '두번누름' + tag)
    L.evaluate("()=>{const b=document.querySelector('#nsOk');b.click();b.click();b.click()}"); L.wait_for_timeout(2500)
    n = [x['title'] for x in songs(A, team)].count('두번누름' + tag)
    if n != 1 or len(posts) != 1: fail('F133 두 번 눌러 곡 %d벌 · 요청 %d번' % (n, len(posts)))
    print('F133 double tap creates one song ok')

    # ================= F83 =================
    bid_ = 'blb' + tag
    png = bytes.fromhex('89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478da63f8ffff3f0005fe02fea7d6a4a60000000049454e44ae426082') * 20
    up = A.request.post(URL + 'api/blobs/%s?team=%s' % (bid_, team), headers={'x-conti': '1', 'content-type': 'image/png'}, data=png)
    if not up.ok: fail('파일 올리기 실패 %s' % up.text()[:200])
    A.request.post(URL + 'api/songs', headers=H, data={'teamId': team, 'title': '파일곡' + tag,
      'pieces': [{'id': 'pc' + tag, 'blob': bid_, 'w': 1, 'h': 1, 'markers': [], 'hls': []}]})
    D = B.new_page(); D.on('pageerror', lambda e: errs.append('D: ' + str(e)))
    got = []
    D.on('request', lambda rq: got.append(rq.url) if '/localblob/' in rq.url and bid_ in rq.url else None)
    boot(D); D.wait_for_timeout(3000)
    if len(got) != 1: fail('F83 부팅 때 같은 파일을 %d번 받음' % len(got))
    D.evaluate("async()=>{await CONTI.IDB.del('blobs',%r);await Promise.all([CONTI.pullSongs(true),CONTI.pullSongs(true)])}" % bid_); D.wait_for_timeout(1000)
    if len(got) != 2: fail('F83 겹친 받기에서 같은 파일을 %d번 받음' % (len(got) - 1))
    print('F83 concurrent pulls download a file once ok')
    D.close()

    # ================= G32 =================
    E, eid = mk(b, 'fe', '가인도')
    t3 = E.request.post(URL + 'api/teams', headers=H, data={'name': '더티팀' + tag, 'myName': '가인도'}).json()['teamId']
    code = E.request.post(URL + 'api/teams/%s/invites' % t3, headers=H, data={'role': 'member'}).json()['invite']['code']
    F, fid = mk(b, 'ff', '나멤버')
    F.request.post(URL + 'api/invite/%s/join' % code, headers=H, data={'name': '나멤버', 'sessions': ['드럼']})
    gsid = E.request.post(URL + 'api/songs', headers=H, data={'teamId': t3, 'title': '처음 제목', 'key': 'G'}).json()['song']['id']
    PE = page(E, 'E'); boot(PE, '#/library'); pull_songs(PE)
    # 다른 기기에서 인도자를 넘겼는데 이 기기는 아직 모른다 — 그 사이 곡에 못 올린 수정이 쌓인다
    if E.request.post(URL + 'api/teams/%s/transfer' % t3, headers=H, data={'userId': fid}).status != 200: fail('인도자 넘기기 실패')
    PE.evaluate("(()=>{const s=CONTI.S.songs.find(x=>x.id===%r);s.pend={tempo:'빠름'};s.dirty=true;CONTI.save()})()" % gsid); PE.wait_for_timeout(600)
    F.request.patch(URL + 'api/songs/' + gsid, headers=H, data={'teamId': t3, 'title': '새 제목'})
    PE.reload(); PE.wait_for_function('window.CONTI && CONTI.S.team.id', timeout=15000); PE.wait_for_timeout(4000)
    g = PE.evaluate("(()=>{const s=CONTI.S.songs.find(x=>x.id===%r);return {role:CONTI.S.team.me.role,title:s.title,dirty:!!s.dirty,pend:s.pend||null}})()" % gsid)
    if g['role'] == 'leader': fail('역할이 안 바뀜')
    if g['dirty'] or g['pend']: fail('G32 인도자가 아닌데 못 올린 수정이 남음: %s' % g)
    if g['title'] != '새 제목': fail('G32 서버의 새 곡 정보를 안 받음: %s' % g)
    print('G32 unsent edits dropped after losing leader ok')

    if errs: fail('페이지 오류:\n' + '\n'.join(errs[:6]))
    b.close()
  print('OK test_audit_fe_05')

run()
