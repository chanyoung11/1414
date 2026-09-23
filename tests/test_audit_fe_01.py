# 전역 감사 fe-01 회귀 검사
#   F14 발행본·편곡·가져온 파일의 숫자 칸(버전·영상 시작·템포·절단선·전조·메모 층·ov 키)에 태그를 넣어도 스크립트가 돌지 않는다
#   F15 폴더로 거른 채 '전체 선택' → 삭제해도 안 보이는 폴더의 예배는 남는다
#   F16 초안에서 영상을 지운 발행 콘티를 열어도 콘티 보기가 멈추지 않는다
#   F17 발행 뒤 연습 화면에서 남긴 "이 곡에 항상" 메모 · 팀원의 '나만' 고정 메모가 바로 보인다 · 재생 시각에도 붙이기
#   F63 넓은 화면에서 저장한 나눈 폭·높이가 좁은 화면에서 악보 칸을 없애지 않는다
#   G24 멤버에게는 "이 곡에 항상 + 세션에 공유"를 못 고르게 · 목회자 메모가 꺼져 있으면 작성창을 안 연다
#   CONTI_URL=http://localhost:8766/ .venv/bin/python tests/test_audit_fe_01.py
import os, sys, time, json, base64, struct, zlib
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHEET = os.path.join(ROOT, 'docs', 'sample_sheet.jpg')
tag = str(int(time.time()))[-6:]
H = {'x-conti': '1'}
HJ = {'x-conti': '1', 'content-type': 'application/json'}

def fail(m): print('FAIL:', m); sys.exit(1)
def log(*a): print(*a, flush=True)

# 작은 흰 PNG (가져오기 파일에 넣을 악보 그림)
def tiny_png(w=300, h=400):
  raw = b''.join(b'\x00' + b'\xff\xff\xff' * w for _ in range(h))
  def chunk(t, d): return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
  return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')

# 칸마다 다른 표시를 남기는 페이로드. 속성 안(href·class·data-*)이든 글자 자리든 빠져나오게
def X(name): return '1"><img src=x onerror="window.__xss=(window.__xss||[]).concat(\'%s\')">' % name

def signup(pg, name, user):
  pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName'); pg.check('#lgAgree')
  pg.fill('#lgName', name); pg.fill('#lgUser', user); pg.fill('#lgPass', 'secret1'); pg.click('[data-act="lg-submit"]')

def xss(pg): return pg.evaluate('window.__xss||null')

def run():
  with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    cL = b.new_context(viewport={'width': 1300, 'height': 950}); L = cL.new_page()
    L.on('pageerror', lambda e: errs.append('L:' + str(e))); L.on('dialog', lambda d: d.accept())
    L.goto(URL); L.wait_for_selector('#lgUser', timeout=8000)
    signup(L, '하은', 'fa' + tag)
    L.wait_for_selector('#gtTeam', timeout=8000); L.fill('#gtTeam', '감사팀'); L.click('[data-act="team-create"]')
    L.wait_for_selector('.shell[data-page]', timeout=8000)
    team = L.evaluate('CONTI.S.team.id')
    link = L.evaluate("location.origin+location.pathname+'#/join/'+CONTI.S.team.invite")
    api = cL.request

    # ================= F14 (서버) — 저장할 때·내려줄 때 숫자 칸을 숫자로 =================
    bad_doc = {'id': 'xs' + tag, 'name': '공격', 'date': '2030-01-05', 'version': X('version'), 'items': [{
      'id': 'it1', 'title': '곡', 'key': 'G', 'ov': {'key': True, X('ov'): True},
      'pieces': [{'id': 'pc1', 'markers': [{'id': 'mk1', 'label': 'A', 'x': 1, 'y': 1, 'cut': X('cut'), 'keyShift': X('ks')}]}],
      'media': [{'id': 'md1', 'type': 'youtube', 'url': 'https://youtu.be/abcdefghijk', 'start': X('start'), 'end': X('end'), 'notes': [{'id': 'n1', 't': X('t'), 'layer': X('layer'), 'text': 'x'}]}],
      'score': {'tempo': X('tempo'), 'measures': []},
      'fixedNotes': [{'id': 'f1', 'layer': X('flayer'), 'markerLabel': 'A', 'text': 'x'}, {'id': 'f2', 'layer': 'all', 'markerLabel': 'A', 'text': 'y'}]}]}
    r = api.put(URL + 'api/services/' + bad_doc['id'], headers=HJ, data=json.dumps({'teamId': team, 'doc': bad_doc}))
    if r.status != 200: fail('발행 PUT 실패 %s %s' % (r.status, r.text()[:200]))
    got = api.get(URL + 'api/services/%s?team=%s' % (bad_doc['id'], team)).json()['doc']
    it = got['items'][0]; md = it['media'][0]; mk = it['pieces'][0]['markers'][0]
    if got['version'] != 0: fail('버전이 숫자로 안 바뀜: %r' % got['version'])
    if md['start'] != 0 or md['end'] != 0 or md['notes'][0]['t'] != 0: fail('영상 시작·끝·메모 시각이 숫자가 아님: %r' % md)
    if md['notes'][0]['layer'] != 'mine': fail('메모 층이 걸러지지 않음: %r' % md['notes'][0])
    if mk.get('cut') is not None or mk.get('keyShift') is not None: fail('절단선·전조가 걸러지지 않음: %r' % mk)
    if it['score']['tempo'] is not None: fail('템포가 걸러지지 않음: %r' % it['score'])
    if [f['layer'] for f in it['fixedNotes']] != ['mine', 'all']: fail('고정 메모 층: %r' % it['fixedNotes'])
    if list(it['ov'].keys()) != ['key']: fail('ov 키가 걸러지지 않음: %r' % it['ov'])
    # 초안도
    r = api.put(URL + 'api/services/%s/draft' % ('xd' + tag), headers=HJ, data=json.dumps({'teamId': team, 'doc': dict(bad_doc, id='xd' + tag)}))
    if r.status != 200: fail('초안 PUT 실패 %s' % r.status)
    gd = api.get(URL + 'api/services/%s/draft?team=%s' % ('xd' + tag, team)).json()['doc']
    if gd['items'][0]['media'][0]['start'] != 0: fail('초안의 영상 시작이 숫자가 아님')
    # 편곡도 (PATCH 로 저장 → 목록으로 받기)
    sg = api.post(URL + 'api/songs', headers=H, data={'teamId': team, 'title': '편곡 검사곡', 'key': 'G'}).json()['song']
    arr_id = sg['arrangements'][0]['id']
    r = api.patch(URL + 'api/arrangements/' + arr_id, headers=HJ, data=json.dumps({'teamId': team,
      'media': [{'id': 'm1', 'type': 'youtube', 'url': 'https://youtu.be/abcdefghijk', 'start': X('astart')}],
      'score': {'tempo': X('atempo'), 'measures': []}}))
    if r.status != 200: fail('편곡 PATCH 실패 %s' % r.status)
    songs = api.get(URL + 'api/songs?team=' + team).json()['songs']
    a = [x for x in songs if x['id'] == sg['id']][0]['arrangements'][0]
    if a['media'][0]['start'] != 0 or a['score']['tempo'] is not None: fail('편곡 숫자 칸이 걸러지지 않음: %r %r' % (a['media'], a['score']))
    api.delete(URL + 'api/services/%s?team=%s' % (bad_doc['id'], team), headers=H)
    api.delete(URL + 'api/services/%s?team=%s' % ('xd' + tag, team), headers=H)
    log('F14 server sanitize ok')

    # ================= F14 (앱) — 서버를 거치지 않는 값(가져온 파일·이 기기에 이미 받아 둔 것)도 화면에서 막는다 =================
    sid = 'xi' + tag
    item = {'id': 'it1', 'title': '곡', 'key': 'G', 'form': 'A', 'arrId': None,
      'pieces': [{'id': 'pc1', 'blob': 'bl' + tag, 'w': 300, 'h': 400,
                  'markers': [{'id': 'mk1', 'label': 'A', 'x': 20, 'y': 40, 'cut': X('cut'), 'keyShift': X('ks')}], 'hls': [], 'chords': []}],
      'media': [{'id': 'md1', 'type': 'youtube', 'url': 'https://youtu.be/abcdefghijk', 'name': '영상', 'start': X('start'), 'end': 0,
                 'notes': [{'id': 'tn1', 't': X('t'), 'layer': 'leader', 'session': None, 'text': '타임라인', 'author': '인도자'}]}],
      'notes': [{'id': 'nt1', 'marker': 'mk1', 'layer': X('layer'), 'session': None, 'text': '층', 'author': '하은'}],
      'score': {'key': 'G', 'tempo': X('tempo'), 'time': '4/4', 'measures': [{'c': [{'b': 0, 't': 'G'}], 'n': [{'p': 'G4', 'd': 1}]}]},
      'ov': {X('ov'): True}}
    pub = dict(version=X('version'), at=int(time.time() * 1000), name='가져온 예배', date='2030-02-02', notice='', message='인도자 글', messageRev=1,
               author='하은', items=[dict(item, notes=None)], changes=[{'kind': 'add', 'text': '곡 추가'}])
    svc = {'id': sid, 'name': '가져온 예배', 'date': '2030-02-02', 'version': X('sver'), 'items': [item], 'published': pub, 'message': '인도자 글'}
    data = {'app': 'conti', 'at': int(time.time() * 1000), 'services': [svc], 'library': [],
            'blobs': {'bl' + tag: {'type': 'image/png', 'b64': base64.b64encode(tiny_png()).decode()}}}
    # 서버 없이 쓰는 기기처럼 (카톡으로 받은 파일을 가져오는 흐름). 서버에 없는 발행본은 동기화 때 지워지므로 그동안 서버를 끈다
    L.evaluate("()=>{CONTI.NET.server=false}")
    L.evaluate("async (t)=>{await CONTI.importJSON(new Blob([t],{type:'application/json'}))}", json.dumps(data))
    ver = L.evaluate("CONTI.S.services.find(x=>x.id==='%s').published.version" % sid)
    if ver != 0: fail('가져온 파일의 버전이 숫자로 안 바뀜: %r' % ver)
    # 고치기 전에 이 기기에 이미 받아 둔 문서는 버전에 글자가 든 채로 남아 있다 → 화면에서도 막혀야 한다
    L.evaluate("(v)=>{const s=CONTI.S.services.find(x=>x.id==='%s');s.version=v;s.published.version=v;CONTI.save()}" % sid, X('version'))
    L.evaluate("()=>{location.hash='#/home';CONTI.render()}"); L.wait_for_timeout(900)
    if 'onerror' not in L.locator('#app').inner_text(): fail('홈 배지에 버전 글자가 안 보임 (검사가 헛돎)')
    if xss(L): fail('홈에서 스크립트가 돎: %s' % xss(L))
    L.evaluate("()=>location.hash='#/view/%s'" % sid); L.wait_for_selector('.card', timeout=8000); L.wait_for_timeout(700)
    if xss(L): fail('콘티 보기에서 스크립트가 돎: %s' % xss(L))
    # 인도자의 글은 처음 열 때 저절로 뜬다. 안 떴으면 연다
    if not L.locator('#modal .ov').count(): L.click('.top [data-act="msg"]'); L.wait_for_timeout(700)
    if '인도자의 글' not in L.locator('#modal').inner_text(): fail('인도자의 글 창이 안 열림')
    if xss(L): fail('인도자의 글에서 스크립트가 돎: %s' % xss(L))
    L.keyboard.press('Escape'); L.evaluate("()=>{const c=document.querySelector('#modal [data-close]');if(c)c.click()}"); L.wait_for_timeout(300)
    L.evaluate("()=>location.hash='#/play/%s/0'" % sid); L.wait_for_selector('#sheet', timeout=8000); L.wait_for_timeout(1200)
    if xss(L): fail('연습 화면에서 스크립트가 돎: %s' % xss(L))
    L.evaluate("()=>location.hash='#/score/%s/it1'" % sid); L.wait_for_timeout(1500)
    if xss(L): fail('악보 화면에서 스크립트가 돎: %s' % xss(L))
    L.evaluate("()=>location.hash='#/edit/%s'" % sid); L.wait_for_selector('#sheet .mkabs, #sheet .strip', timeout=8000); L.wait_for_timeout(900)
    if xss(L): fail('편집기에서 스크립트가 돎: %s' % xss(L))
    L.locator('#sheet [data-marker="mk1"]').first.click(); L.wait_for_timeout(700)
    if not L.locator('#modal [data-ks]').count(): fail('마커 메뉴가 안 열림')
    if xss(L): fail('마커 메뉴에서 스크립트가 돎: %s' % xss(L))
    L.evaluate("()=>{const c=document.querySelector('#modal');if(c)c.innerHTML=''}"); L.evaluate("()=>CONTI.render()")
    if L.evaluate("CONTI.ovKeys({ov:{key:true,'<b>':true,score:false}}).join()") != 'key': fail('ovKeys 가 편곡 칸 밖의 키를 돌려줌')
    L.evaluate("()=>{CONTI.S.services=CONTI.S.services.filter(x=>x.id!=='%s');CONTI.NET.server=true;CONTI.save();location.hash='#/home'}" % sid); L.wait_for_timeout(500)
    log('F14 client sinks ok')

    # ================= F15 — 폴더로 거른 채 전체 선택 · 삭제 =================
    ids = []
    for i, folder in enumerate(['25 하반기', '25 하반기', '26 상반기', '26 상반기']):
      d = {'id': 'fo%d%s' % (i, tag), 'name': '폴더 예배 %d' % i, 'date': '2031-01-0%d' % (i + 1), 'folder': folder, 'version': 1,
           'items': [{'id': 'i1', 'title': '곡', 'pieces': [], 'media': []}]}
      r = api.put(URL + 'api/services/' + d['id'], headers=HJ, data=json.dumps({'teamId': team, 'doc': d}))
      if r.status != 200: fail('폴더 예배 발행 실패')
      ids.append(d['id'])
    L.evaluate("async()=>{await CONTI.SYNC.pullServices();CONTI.render()}"); L.wait_for_timeout(800)
    L.click('[data-act="home-folder"][data-v="25 하반기"]'); L.wait_for_timeout(500)
    if L.locator('.svcrow').count() != 2: fail('폴더로 거른 목록이 2개가 아님: %d' % L.locator('.svcrow').count())
    L.click('[data-act="pick-on"]'); L.wait_for_timeout(300)
    L.click('[data-act="pick-all"]'); L.wait_for_timeout(300)
    n = L.evaluate('CONTI.HOME.sel.length')
    if n != 2: fail('전체 선택이 안 보이는 폴더까지 골랐음: %d개' % n)
    if L.locator('[data-act="pick-all"]').inner_text().strip() != '전체 해제': fail('보이는 것을 다 골랐는데 "전체 해제"가 아님')
    # 다른 폴더로 바꾸면 고른 것도 그 폴더 안으로 좁혀진다
    L.click('[data-act="home-folder"][data-v="26 상반기"]'); L.wait_for_timeout(300)
    if L.evaluate('CONTI.HOME.sel.length') != 0: fail('폴더를 바꿔도 안 보이는 예배가 골라진 채로 남음')
    L.click('[data-act="home-folder"][data-v="25 하반기"]'); L.wait_for_timeout(300)
    L.click('[data-act="pick-all"]'); L.wait_for_timeout(300)
    L.click('[data-act="pick-del"]'); L.wait_for_timeout(2500)
    left = [x['id'] for x in api.get(URL + 'api/services?team=' + team).json()['services'] if x['id'] in ids]
    if sorted(left) != sorted(ids[2:]): fail('삭제 뒤 서버에 남은 예배가 다름: %s' % left)
    for x in ids[2:]: api.delete(URL + 'api/services/%s?team=%s' % (x, team), headers=H)
    L.evaluate("async()=>{await CONTI.SYNC.pullServices();CONTI.render()}"); L.wait_for_timeout(500)
    log('F15 pick-all within folder ok')

    # ================= 곡 · 악보 · 발행 (F16 · F17 · G24 · F63 공통) =================
    bid = 'sh' + tag
    with open(SHEET, 'rb') as f: img = f.read()
    r = api.post(URL + 'api/blobs/%s?team=%s' % (bid, team), headers={'x-conti': '1', 'content-type': 'image/jpeg'}, data=img)
    if r.status != 200: fail('악보 파일 올리기 실패 %s' % r.status)
    song = api.post(URL + 'api/songs', headers=H, data={'teamId': team, 'title': '고정 메모 곡', 'key': 'G', 'form': 'A – B'}).json()['song']
    aid = song['arrangements'][0]['id']
    piece = {'id': 'pc1', 'blob': bid, 'w': 2120, 'h': 3163, 'markers': [{'id': 'mk1', 'label': 'A', 'x': 200, 'y': 400, 'cut': 360}], 'hls': [], 'chords': []}
    media = {'id': 'md1', 'type': 'youtube', 'url': 'https://youtu.be/abcdefghijk', 'name': '영상', 'start': 0, 'end': 0}
    am = dict(media, id='am1')   # 편곡에도 같은 영상 (예배 곡이 편곡을 따라가는 상태)
    api.patch(URL + 'api/arrangements/' + aid, headers=HJ, data=json.dumps({'teamId': team, 'pieces': [piece], 'media': [am]}))
    s1 = 'fx' + tag
    doc = {'id': s1, 'name': '고정 메모 예배', 'date': '2031-03-01', 'version': 1, 'items': [
      {'id': 'it1', 'title': '고정 메모 곡', 'key': 'G', 'form': 'A – B', 'songId': song['id'], 'arrId': aid, 'pieces': [piece], 'media': [media], 'fixedNotes': []}]}
    r = api.put(URL + 'api/services/' + s1, headers=HJ, data=json.dumps({'teamId': team, 'doc': doc}))
    if r.status != 200: fail('발행 실패 %s %s' % (r.status, r.text()[:200]))
    L.evaluate("async()=>{await CONTI.SYNC.pullServices();await CONTI.pullSongs(true);CONTI.render()}"); L.wait_for_timeout(1500)

    # ================= F16 — 초안에서 영상을 지운 발행 콘티 =================
    L.evaluate("()=>{const s=CONTI.S.services.find(x=>x.id==='%s');s.items[0].media=[];CONTI.save()}" % s1)
    n0 = len(errs)
    L.evaluate("()=>location.hash='#/view/%s'" % s1); L.wait_for_timeout(1500)
    if len(errs) > n0: fail('콘티 보기가 오류로 멈춤: %s' % errs[n0:])
    if L.locator('.card').count() < 1 or '고정 메모 곡' not in L.locator('#app').inner_text(): fail('콘티 보기에 곡 카드가 안 그려짐')
    # 곡을 초안에서 통째로 빼도
    L.evaluate("()=>{const s=CONTI.S.services.find(x=>x.id==='%s');s._keep=s.items;s.items=[];CONTI.render()}" % s1); L.wait_for_timeout(800)
    if len(errs) > n0: fail('곡을 뺀 초안에서 콘티 보기가 멈춤: %s' % errs[n0:])
    L.evaluate("()=>{const s=CONTI.S.services.find(x=>x.id==='%s');s.items=s._keep;delete s._keep;s.items[0].media=[JSON.parse(%s)];s.items[0].media[0].notes=[];CONTI.save()}" % (s1, json.dumps(json.dumps(media))))
    log('F16 viewer ok')

    # ================= F17 — 인도자가 발행 뒤 연습 화면에서 "이 곡에 항상" =================
    L.evaluate("()=>location.hash='#/play/%s/0'" % s1); L.wait_for_selector('#sheet [data-marker="mk1"]', timeout=15000); L.wait_for_timeout(800)
    L.locator('#sheet [data-marker="mk1"]').first.click(); L.wait_for_selector('#cText', timeout=6000)
    if not L.locator('[data-w2="always"].on').count(): fail('인도자 기본이 "이 곡에 항상"이 아님')
    if not L.locator('#cAlsoT').count(): fail('"재생 시각에도 붙이기"가 없음')
    L.fill('#cText', '연습중새메모'); L.click('#cSave')
    L.wait_for_function("document.querySelector('#sheet').innerText.includes('연습중새메모')", timeout=8000)   # 새로고침 없이 바로
    tl = L.evaluate("(CONTI.S.services.find(x=>x.id==='%s').items[0].media[0].notes||[]).map(n=>n.text+'@'+n.marker)" % s1)
    if '연습중새메모@mk1' not in tl: fail('"재생 시각에도 붙이기"를 켰는데 타임라인 메모가 안 붙음: %s' % tl)
    fx = api.get(URL + 'api/songs/%s?team=%s' % (song['id'], team)).json()['notes']
    if not any(n['text'] == '연습중새메모' and n['layer'] == 'all' for n in fx): fail('서버에 고정 메모가 없음: %s' % fx)
    log('F17 leader post-publish always note shows at once ok')

    # ---- 멤버 ----
    cM = b.new_context(viewport={'width': 1300, 'height': 950}); M = cM.new_page()
    M.on('pageerror', lambda e: errs.append('M:' + str(e))); M.on('dialog', lambda d: d.accept())
    M.goto(link); M.wait_for_selector('#lgUser', timeout=8000)
    signup(M, '민수', 'fb' + tag)
    M.wait_for_selector('#jnName', timeout=8000)
    if M.locator('#gtSess .q:has-text("드럼")').count(): M.click('#gtSess .q:has-text("드럼")')
    M.click('[data-act="team-join"]'); M.wait_for_selector('.shell[data-page]', timeout=10000)
    M.wait_for_function("CONTI.S.services.some(x=>x.id==='%s')" % s1, timeout=20000)
    M.evaluate("CONTI.pullSongs(true)"); M.wait_for_timeout(1500)
    me_m = cM.request.get(URL + 'api/me').json()
    mid = me_m['user']['id']; msess = M.evaluate('CONTI.S.team.me.session')
    # ---- F16 뿌리: 라이브러리에서 영상을 바꿔도 팀원 기기의 예배 곡(발행본 사본)은 그대로 ----
    api.patch(URL + 'api/arrangements/' + aid, headers=HJ, data=json.dumps({'teamId': team, 'media': [dict(am, url='https://youtu.be/zyxwvutsrqp')]}))
    M.evaluate("CONTI.pullSongs(true)"); M.wait_for_timeout(1500)
    mids = M.evaluate("CONTI.S.services.find(x=>x.id==='%s').items[0].media.map(m=>m.id)" % s1)
    if mids != ['md1']: fail('라이브러리 영상이 바뀌자 팀원 기기의 예배 영상이 갈아 끼워짐: %s' % mids)
    n0 = len(errs)
    M.evaluate("()=>location.hash='#/view/%s'" % s1); M.wait_for_selector('.card', timeout=8000); M.wait_for_timeout(800)
    if len(errs) > n0: fail('팀원 콘티 보기가 오류로 멈춤: %s' % errs[n0:])
    log('F16 member copy keeps published media ok')
    M.evaluate("()=>location.hash='#/play/%s/0'" % s1); M.wait_for_selector('#sheet [data-marker="mk1"]', timeout=15000); M.wait_for_timeout(800)
    if '연습중새메모' not in M.locator('#sheet').inner_text(): fail('팀원에게 발행 뒤 남긴 고정 메모가 안 보임')
    # ---- G24: 멤버는 "이 곡에 항상"이면 세션에 공유를 못 고른다 ----
    M.locator('#sheet [data-marker="mk1"]').first.click(); M.wait_for_selector('#cText', timeout=6000)
    if not M.locator('[data-w2="once"].on').count(): fail('멤버 기본이 "이번 예배만"이 아님')
    if not M.locator('[data-sc="session"]').is_visible(): fail('"이번 예배만"인데 세션에 공유가 안 보임')
    M.click('[data-sc="session"]'); M.click('[data-w2="always"]'); M.wait_for_timeout(200)
    if M.locator('[data-sc="session"]').is_visible(): fail('멤버에게 "이 곡에 항상 + 세션에 공유"가 보임 (서버가 거절함)')
    if not M.locator('#cScHint').is_visible(): fail('세션 공유를 감춘 까닭이 안 보임')
    if not M.locator('[data-sc="mine"].on').count(): fail('세션 공유를 감췄는데 범위가 "나만"으로 안 돌아옴')
    M.click('[data-w2="once"]'); M.wait_for_timeout(200)
    if not M.locator('[data-sc="session"]').is_visible(): fail('"이번 예배만"으로 돌아왔는데 세션에 공유가 안 보임')
    M.click('[data-w2="always"]'); M.wait_for_timeout(200)
    toasts = []
    M.fill('#cText', '내고정메모'); M.click('#cSave')
    M.wait_for_function("document.querySelector('#sheet').innerText.includes('내고정메모')", timeout=8000)
    fxm = cM.request.get(URL + 'api/songs/%s?team=%s' % (song['id'], team)).json()['notes']
    mine = [n for n in fxm if n['text'] == '내고정메모']
    if not mine or mine[0]['layer'] != 'mine': fail('멤버의 나만 고정 메모가 서버에 없음: %s' % fxm)
    # 다시 열어도 (발행본의 굳은 목록에 없어도) 보인다
    M.reload(); M.wait_for_selector('#sheet [data-marker="mk1"]', timeout=15000); M.wait_for_timeout(1200)
    txt = M.locator('#sheet').inner_text()
    if '내고정메모' not in txt or '연습중새메모' not in txt: fail('다시 연 연습 화면에 고정 메모가 빠짐: %s' % txt[:300])
    # 인도자에게는 멤버의 나만 메모가 안 보인다
    L.reload(); L.wait_for_selector('#sheet [data-marker="mk1"]', timeout=15000); L.wait_for_timeout(1200)
    if '내고정메모' in L.locator('#sheet').inner_text(): fail('멤버의 나만 고정 메모가 인도자에게 보임')
    log('F17 member own always note shows ok · G24 member scope ok')

    # ---- G24: 세션 리더는 "이 곡에 항상 + 세션에 공유"가 된다 ----
    r = api.patch(URL + 'api/teams/%s/members/%s' % (team, mid), headers=HJ, data=json.dumps({'role': 'session_lead'}))
    if r.status != 200: fail('세션 리더로 바꾸기 실패 %s' % r.status)
    M.reload(); M.wait_for_selector('#sheet [data-marker="mk1"]', timeout=15000); M.wait_for_timeout(1500)
    if M.evaluate('CONTI.S.team.me.role') != 'session_lead': fail('역할이 안 바뀜')
    M.locator('#sheet [data-marker="mk1"]').first.click(); M.wait_for_selector('#cText', timeout=6000)
    M.click('[data-w2="always"]'); M.wait_for_timeout(200)
    if not M.locator('[data-sc="session"]').is_visible(): fail('세션 리더에게 "이 곡에 항상 + 세션에 공유"가 안 보임')
    M.click('[data-sc="session"]'); M.fill('#cText', '세션고정'); M.click('#cSave')
    # 띠에 칩이 많으면 +N 으로 접히므로 연습 화면이 그리는 목록(발행본 + 편곡)으로 본다
    M.wait_for_function("""()=>{const s=CONTI.S.services.find(x=>x.id==='%s');const it=CONTI.pubOrDraft(s).items[0];
      return CONTI.fixedNotesOf(it,'mk1',{mode:'play',session:'%s',f:{leader:true,session:true,mine:true}}).some(n=>n.text==='세션고정')}""" % (s1, msess), timeout=8000)
    if '+' not in M.locator('#sheet .strip').first.inner_text() and '세션고정' not in M.locator('#sheet').inner_text(): fail('세션 고정 메모가 띠에 안 그려짐')
    fxs = [n for n in cM.request.get(URL + 'api/songs/%s?team=%s' % (song['id'], team)).json()['notes'] if n['text'] == '세션고정']
    if not fxs or fxs[0]['layer'] != 'session' or fxs[0]['session'] != msess: fail('세션 리더의 세션 고정 메모: %s' % fxs)
    # ---- G24: 목회자 — 목회자 메모가 꺼져 있으면 작성창을 안 연다 ----
    r = api.patch(URL + 'api/teams/%s/members/%s' % (team, mid), headers=HJ, data=json.dumps({'role': 'pastor'}))
    if r.status != 200: fail('목회자로 바꾸기 실패 %s' % r.status)
    M.reload(); M.wait_for_selector('#sheet [data-marker="mk1"]', timeout=15000); M.wait_for_timeout(1500)
    if M.evaluate('CONTI.S.team.me.role') != 'pastor': fail('목회자로 안 바뀜')
    M.locator('#sheet [data-marker="mk1"]').first.click(); M.wait_for_timeout(700)
    if M.locator('#cText').count(): fail('목회자 메모가 꺼져 있는데 작성창이 열림')
    r = api.patch(URL + 'api/teams/%s/settings' % team, headers=HJ, data=json.dumps({'pastorCanMemo': True}))
    if r.status != 200: fail('목회자 메모 켜기 실패 %s' % r.status)
    M.reload(); M.wait_for_selector('#sheet [data-marker="mk1"]', timeout=15000); M.wait_for_timeout(1500)
    M.locator('#sheet [data-marker="mk1"]').first.click(); M.wait_for_selector('#cText', timeout=6000)
    if M.locator('[data-sc="session"]').count(): fail('세션이 없는 목회자에게 "에 공유"가 보임')
    M.evaluate("()=>{const c=document.querySelector('#modal [data-close]');if(c)c.click()}")
    log('G24 session lead / pastor ok')

    # ================= F63 — 넓은 화면에서 저장한 폭·높이 =================
    cW = b.new_context(viewport={'width': 1024, 'height': 700}, storage_state=cL.storage_state()); W = cW.new_page()
    W.on('pageerror', lambda e: errs.append('W:' + str(e))); W.on('dialog', lambda d: d.accept())
    W.goto(URL); W.wait_for_selector('.shell[data-page]', timeout=10000)
    W.evaluate("()=>{localStorage.setItem('conti-lw','1002px');localStorage.setItem('conti-th-edit','2000')}")
    W.evaluate("()=>location.hash='#/edit/%s'" % s1); W.wait_for_selector('#edsheet', timeout=10000); W.wait_for_timeout(1200)
    ew = W.evaluate("document.querySelector('#edsheet').getBoundingClientRect().width")
    if ew < 250: fail('좁은 화면에서 편집기 악보 칸이 %dpx' % ew)
    lw = W.evaluate("document.querySelector('#stack').getBoundingClientRect().width")
    if lw < 290: fail('왼쪽 칸이 %dpx (300 아래로 줄면 안 됨)' % lw)
    bh = W.evaluate("document.querySelector('#stack>.panel:last-child').getBoundingClientRect().height")
    if bh < 100: fail('저장된 높이 때문에 곡 편집 칸이 %dpx' % bh)
    W.evaluate("()=>location.hash='#/play/%s/0'" % s1); W.wait_for_selector('#sheet', timeout=10000); W.wait_for_timeout(1200)
    pw = W.evaluate("(()=>{const ws=document.querySelector('#ws');const k=[...ws.children];return k[k.length-1].getBoundingClientRect().width})()")
    if pw < 250: fail('좁은 화면에서 연습 악보 칸이 %dpx' % pw)
    # 넓은 화면에서는 저장한 폭 그대로
    W.set_viewport_size({'width': 1366, 'height': 900}); W.wait_for_timeout(600)
    lw2 = W.evaluate("document.querySelector('#stack').getBoundingClientRect().width")
    if abs(lw2 - 1002) > 4: fail('넓은 화면에서 저장한 폭(1002px)이 안 지켜짐: %d' % lw2)
    log('F63 saved split clamps ok (edit %d / play %d / rows %d)' % (ew, pw, bh))
    cW.close()

    if xss(L) or xss(M): fail('스크립트가 돎: %s %s' % (xss(L), xss(M)))
    errs2 = [e for e in errs if 'youtube' not in e.lower()]
    if errs2: fail('페이지 오류: %s' % errs2[:5])
    api.delete(URL + 'api/services/%s?team=%s' % (s1, team), headers=H)
    b.close()
  print('OK test_audit_fe_01 — F14 F15 F16 F17 F63 G24')

run()
