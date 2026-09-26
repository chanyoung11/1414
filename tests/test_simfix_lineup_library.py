# iOS 시뮬레이터 수동 점검(2026-09-26) — 콘티 보기·라이브러리·편성·메모 (D1~D9 · E6)
#  D1 같은 기기에서 앞 계정(인도자)이 '인도자의 글'을 읽었으면, 로그아웃 뒤 가입한 멤버에게 글 창도 안 읽음 점도 안 뜨던 것
#     (읽음 S.readRev 가 계정·팀을 바꿔도 앞 사람 것 그대로) → 스코프마다 따로
#  E6 인도자가 새 기기에서 로그인하면 제가 쓴 글이 '읽었어요' 창·안 읽음 점으로 뜨던 것 → 발행한 사람은 읽은 것으로 (서버)
#  D2 폰 라이브러리에서 찾는 중에도 카드·'전체 N곡'·칩 줄이 그대로라 결과가 자판 밑에 있던 것 → 접고 '찾은 곡 N곡'
#  D3 폰 곡 상세 상단에서 제목이 한 글자로 잘리던 것 → 단추는 아이콘만, '다른 키로'는 ≡ 안
#  D4 끊긴 채 인도자 '이 곡에 항상' 메모가 말없이 '이번 예배만'이 되고 영어 오류(Failed to fetch · Load failed)가 뜨던 것
#  D5 끊긴 채 쓴 메모에 '메모 저장'만 뜨고, 서버가 안 닿는 동안(NET.server 는 true) 다시 올리지도 않던 것
#  D6 초성 찾기가 아티스트·가사를 안 보던 것 (찾기 칸은 '제목 · 가사 · 아티스트 · 태그 — 초성도 됩니다')
#  D7 통보하기 뒤 편성 패널이 맨 위로 튀던 것
#  D8 통보 확인 문구가 '이름 에게'(띄어 써 iOS 창이 조사만 넘김) · 인도자가 제게도 통보하던 것
#  D9 멤버 가입 알림이 메모 아이콘이던 것
#
# 사용: CONTI_URL=http://localhost:8766/ .venv/bin/python tests/test_simfix_lineup_library.py   (개발 서버가 떠 있어야 한다)
#       SOFT=1 이면 실패해도 끝까지 간다 (고치기 전 코드에서 모두 재현해 볼 때) · WK=1 이면 WebKit 으로
import os, sys, time, json, datetime, random, string
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHEET = os.path.join(ROOT, 'docs', 'sample_sheet.jpg')
URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
H = {'x-conti': '1'}
tag = str(int(time.time()))[-6:]
SOFT = os.environ.get('SOFT') == '1'
FAILS = []
N = [0]
PHONE = dict(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, service_workers='block')

def fail(m):
    print('FAIL:', m)
    if SOFT: FAILS.append(m); return
    sys.exit(1)
def ok(r, what=''):
    if not r.ok: print('FAIL: %s %s %s' % (what, r.status, r.text()[:200])); sys.exit(1)
    return r.json()
def uname(p): N[0] += 1; return '%s%s%d' % (p, tag, N[0])
rid = lambda: ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(10))

def signup(c, prefix, name):
    u = uname(prefix)
    me = ok(c.request.post(URL + 'api/auth/signup', headers=H, data={'username': u, 'password': 'secret1', 'name': name}), 'signup')
    return u, me['user']['id']

def make_team(c, name, my):
    t = ok(c.request.post(URL + 'api/teams', headers=H, data={'name': name, 'myName': my, 'session': '인도자'}), 'team')['teamId']
    return t, ok(c.request.get(URL + 'api/teams/%s' % t), 'team get')['invite']

def page(c, hash_='#/home', sel='.shell[data-page]'):
    pg = c.new_page(); pg.errs = []; pg.dialogs = []
    pg.on('pageerror', lambda e: pg.errs.append(str(e)[:200]))
    def dlg(d): pg.dialogs.append(d.message); d.accept()
    pg.on('dialog', dlg)
    pg.goto(URL + hash_)
    if sel: pg.wait_for_selector(sel, timeout=15000)
    return pg

# 토스트를 모두 적어 둔다 (곧 다른 토스트로 바뀌는 것까지)
TOASTS = """()=>{window.__toasts=[];const t=document.querySelector('#toast');
  new MutationObserver(()=>{window.__toasts.push(t.textContent)}).observe(t,{childList:true,characterData:true,subtree:true})}"""

def wait_until(pg, expr, ms=12000, arg=None):
    try: pg.wait_for_function(expr, arg=arg, timeout=ms); return True
    except Exception: return False

def poll(fn, ms=10000, step=400):
    t = time.time() + ms / 1000
    while time.time() < t:
        if fn(): return True
        time.sleep(step / 1000)
    return fn()

def msg_state(pg):
    return pg.evaluate("""()=>({popup:!!document.querySelector('#msgOk'),
      dot:[...document.querySelectorAll('[data-act="msg"]')].some(b=>b.classList.contains('dot'))})""")

# ---------------------------------------------------------------- D1 · E6
def sec_read(b):
    c = b.new_context(**PHONE)
    lu, luid = signup(c, 'rl', '리더')
    team, inv = make_team(c, '글팀', '리더')
    pg = page(c)
    pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]', timeout=8000)
    pg.fill('[data-f="svc.name"]', '글 예배'); pg.fill('[data-f="svc.message"]', '은혜를 기억하며')
    pg.click('[data-act="add-item"]'); pg.wait_for_selector('[data-f="item.title"]', timeout=8000)
    pg.fill('[data-f="item.title"]', '곡하나'); pg.wait_for_timeout(400)
    sid = pg.evaluate('CONTI.route().a')
    pg.click('[data-act="publish"]'); pg.wait_for_selector('#pubOnly', timeout=6000); pg.click('#pubOnly')
    if not wait_until(pg, "(id)=>{const s=CONTI.S.services.find(x=>x.id===id);return s&&s.published&&!s.pubPending}", arg=sid): fail('준비: 발행이 안 끝남')
    rev = pg.evaluate("(id)=>CONTI.S.services.find(x=>x.id===id).published.messageRev", sid)
    if not rev: fail('준비: 인도자의 글 판(messageRev)이 없음')
    # E6 서버: 발행한 사람은 제 글을 읽은 것으로 받는다 (다른 기기가 받아 가는 값)
    got = ok(c.request.get(URL + 'api/services/%s?team=%s' % (sid, team)), 'svc')['readRev']
    if got != rev: fail('E6 발행한 인도자의 서버 읽음이 %s (글 판 %s)' % (got, rev))

    # 같은 기기에서 인도자 로그아웃 → 초대로 멤버 가입
    pg.goto(URL + '#/settings'); pg.wait_for_selector('[data-act="set-tab"][data-t="app"]', timeout=8000)
    pg.click('[data-act="set-tab"][data-t="app"]'); pg.wait_for_selector('#sLogout', timeout=8000); pg.click('#sLogout')
    pg.wait_for_selector('#lgUser', timeout=10000)
    if pg.evaluate("Object.keys(CONTI.S.readRev||{}).length"): fail('D1 로그아웃했는데 앞 사람 읽음이 남음: %s' % pg.evaluate('CONTI.S.readRev'))
    pg.goto(URL + '#/join/' + inv); pg.wait_for_selector('#lgUser', timeout=8000)
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName')
    pg.check('#lgAgree'); pg.fill('#lgName', '드럼이'); pg.fill('#lgUser', uname('rm')); pg.fill('#lgPass', 'secret1'); pg.click('[data-act="lg-submit"]')
    pg.wait_for_selector('#jnName', timeout=8000); pg.click('#gtSess .q:has-text("드럼")'); pg.click('[data-act="team-join"]')
    pg.wait_for_selector('.shell[data-page]', timeout=8000); pg.wait_for_timeout(1500)
    got = ok(c.request.get(URL + 'api/services/%s?team=%s' % (sid, team)), 'svc m')['readRev']
    if got != 0: fail('E6 멤버의 서버 읽음이 0 이 아님: %s' % got)
    pg.goto(URL + '#/view/' + sid); pg.wait_for_selector('#app .top', timeout=10000)
    if not wait_until(pg, "!!document.querySelector('#msgOk')", 6000): fail('D1 앞 계정이 읽은 기기에서 가입한 멤버에게 인도자의 글이 안 뜸 (readRev %s)' % pg.evaluate('CONTI.S.readRev'))
    if not msg_state(pg)['dot']: fail('D1 멤버에게 안 읽음 점이 없음')
    if pg.locator('#msgOk').count(): pg.click('#msgOk'); pg.wait_for_timeout(800)
    if msg_state(pg)['dot']: fail('D1 읽었어요 뒤에도 점이 남음')
    if not poll(lambda: ok(c.request.get(URL + 'api/services/%s?team=%s' % (sid, team)), 'svc m2')['readRev'] == rev, 6000): fail('D1 멤버가 읽은 것이 서버에 안 감')
    print('D1 같은 기기에서 앞 계정이 읽은 글도 새 멤버에게 창·점으로 뜸 · 로그아웃하면 읽음이 비워짐 ok')

    # E6: 인도자가 새 기기(아이패드)에서 로그인 → 제 글이 뜨지 않는다
    c2 = b.new_context(viewport={'width': 820, 'height': 1180}, is_mobile=True, has_touch=True, service_workers='block')
    ok(c2.request.post(URL + 'api/auth/login', headers=H, data={'username': lu, 'password': 'secret1'}), 'login')
    p2 = page(c2); p2.wait_for_timeout(2000)
    p2.goto(URL + '#/view/' + sid); p2.wait_for_selector('#app .top', timeout=10000); p2.wait_for_timeout(3000)
    st = msg_state(p2)
    if st['popup'] or st['dot']: fail('E6 새 기기에서 인도자에게 제 글이 떠 있음: %s' % st)
    if not p2.locator('[data-act="msg"]').count(): fail('E6 글 아이콘이 사라짐 (다시 보기는 되어야 한다)')
    print('E6 새 기기의 인도자에게 제 글 창·점이 안 뜸 (글 아이콘은 그대로) ok')
    for x in (pg, p2):
        if x.errs: fail('페이지 오류: %s' % x.errs)
    c.close(); c2.close()

# ---------------------------------------------------------------- D2 · D3 · D6
def sec_library(b):
    c = b.new_context(**PHONE)
    signup(c, 'll', '리더')
    team, _ = make_team(c, '곡팀', '리더')
    songs = []
    for t, art, fl, tags in (('주님 찬양', 'QA 아티스트', '주님을 찬양 합니다 영원히', ['경배', '감사', '고백']),
                             ('은혜로다', '', '', ['찬양', '결단']), ('감사해요', '', '', ['축제', '빠른곡', '성탄'])):
        songs.append(ok(c.request.post(URL + 'api/songs', headers=H, data={'teamId': team, 'title': t, 'artist': art, 'firstLine': fl,
            'tags': tags, 'folder': '주일' if t != '감사해요' else '수요', 'key': 'G', 'form': 'A B'}), 'song')['song'])
    items = [{'id': rid(), 'title': s['title'], 'songId': s['id'], 'arrId': s['arrangements'][0]['id'], 'key': 'G', 'pieces': [], 'media': []} for s in songs]
    sid = rid()
    ok(c.request.put(URL + 'api/services/' + sid, headers=H, data={'teamId': team, 'doc': {'id': sid, 'name': '예배', 'date': datetime.date.today().isoformat(),
        'version': 1, 'items': items, 'message': '', 'messageRev': 0}}), 'pub')
    pg = page(c, '#/library', '#libQ')
    if not wait_until(pg, "CONTI.S.songs.length>=3&&CONTI.S.songs.every(s=>s.lastUsed)", 10000): fail('준비: 곡 목록이 안 옴')
    pg.evaluate('CONTI.render()'); pg.wait_for_selector('#libQ'); pg.wait_for_timeout(500)
    vis = lambda sel: pg.evaluate("(s)=>{const e=document.querySelector(s);return !!(e&&e.offsetParent)}", sel)
    if not pg.locator('.scards').count() or not vis('.scards'): fail('준비: 최근 부른 곡 카드가 없음')

    # D2 폰에서 찾기: 카드·'전체 N곡'·통계를 접고 찾은 수 · 켜 둔 칩만 · 결과가 자판 위에 (자판을 띄운 보이는 높이 494pt)
    pg.click('#libQ'); pg.type('#libQ', 'ㅈㄴ', delay=60); pg.wait_for_timeout(500)
    info = pg.evaluate("""()=>{const l=document.querySelector('#libList');const lbls=[...document.querySelectorAll('.libpage .lbl')].filter(x=>x.offsetParent).map(x=>x.textContent.trim());
      const row=l.querySelector('.songrow');
      return {top:row?row.getBoundingClientRect().bottom:9999,rows:l.querySelectorAll('.songrow').length,lbls,
        cards:[...document.querySelectorAll('.scards')].some(x=>x.offsetParent),ins:!!document.querySelector('.insight').offsetParent,
        chips:[...document.querySelectorAll('.filters .q')].filter(x=>x.offsetParent).length,focus:(document.activeElement||{}).id}}""")
    if info['rows'] != 1: fail('준비: ㅈㄴ 로 한 곡이 안 걸림 %s' % info)
    if info['cards'] or '전체 3곡' in info['lbls'] or info['ins']: fail('D2 찾는 중인데 카드·전체 N곡·통계가 그대로: %s' % info)
    if '찾은 곡 1곡' not in info['lbls']: fail('D2 찾은 수가 안 보임: %s' % info)
    if info['top'] > 494: fail('D2 첫 결과가 자판 밑(보이는 높이 494)에 있음: %s' % info)
    if info['chips']: fail('D2 폰에서 찾는 중인데 안 켠 칩이 남음: %s' % info)
    if info['focus'] != 'libQ': fail('D2 찾는 사이 찾기 칸 초점이 빠짐(자판이 닫힘): %s' % info)
    pg.type('#libQ', 'ㅊ', delay=60); pg.wait_for_timeout(400)   # 더 쳐도 그대로 (다시 그리지 않는다)
    if pg.evaluate("(document.activeElement||{}).id") != 'libQ': fail('D2 더 치니 초점이 빠짐')
    # 켜 둔 칩은 남는다(끌 수 있게)
    pg.fill('#libQ', ''); pg.evaluate("CONTI.LIB.q='';CONTI.LIB.key='G';CONTI.render()"); pg.wait_for_selector('#libQ')
    pg.click('#libQ'); pg.type('#libQ', 'ㅇㅎ', delay=60); pg.wait_for_timeout(500)
    on = pg.evaluate("[...document.querySelectorAll('.filters .q')].filter(x=>x.offsetParent).map(x=>x.textContent.trim())")
    if on != ['G']: fail('D2 찾는 중 켜 둔 칩(G)만 남아야 함: %s' % on)
    if '찾은 곡 1곡' not in pg.evaluate("(document.querySelector('#libHit')||{}).textContent||''"): fail('D2 켜 둔 칩으로 좁힌 찾은 수가 틀림')
    # 지우면 다시 편다
    pg.fill('#libQ', ''); pg.dispatch_event('#libQ', 'change'); pg.evaluate("CONTI.LIB.key='';CONTI.render()"); pg.wait_for_timeout(500)
    if not vis('.scards') or vis('#libHit'): fail('D2 찾기를 지웠는데 카드가 안 돌아옴')
    print('D2 폰 라이브러리 찾기: 카드·통계·안 켠 칩을 접고 찾은 수 · 첫 결과 %dpt(자판 위) · 초점 유지 ok' % info['top'])

    # D6 초성: 아티스트·가사·태그도 (가사는 세 글자부터)
    res = {}
    for q in ('ㅇㅌㅅㅌ', 'ㅇㅇㅎ', 'ㄱㅂ', 'ㅈㄴ', 'ㅇㅇ'):
        res[q] = pg.evaluate("(q)=>CONTI.S.songs.map(s=>[s.title,CONTI.matchSong(s,q)]).filter(x=>x[1].rank>0).map(x=>x[0]+'|'+x[1].where)", q)
    if res['ㅇㅌㅅㅌ'] != ['주님 찬양|아티스트: QA 아티스트']: fail('D6 아티스트 초성이 안 걸림: %s' % res)
    if res['ㅇㅇㅎ'] != ['주님 찬양|가사: 주님을 찬양 합니다 영원히']: fail('D6 가사 초성이 안 걸림: %s' % res)
    if res['ㄱㅂ'] != ['주님 찬양|태그: 경배']: fail('D6 태그 초성이 안 걸림: %s' % res)
    if res['ㅈㄴ'] != ['주님 찬양|']: fail('D6 제목 초성이 바뀜: %s' % res)
    if any('가사' in x for x in res['ㅇㅇ']): fail('D6 두 글자 초성이 가사까지 걸림(거의 다 걸린다): %s' % res)
    pg.click('#libQ'); pg.fill('#libQ', ''); pg.type('#libQ', 'ㅇㅇㅎ', delay=60); pg.wait_for_timeout(500)
    if pg.locator('#libList .songrow').count() != 1: fail('D6 화면에서 ㅇㅇㅎ 결과가 없음')
    print('D6 초성으로 아티스트·가사·태그도 찾음 (가사는 세 글자부터) ok')

    # D3 폰 곡 상세: 제목이 읽히고, '다른 키로'는 ≡ 안에
    pg.fill('#libQ', ''); pg.evaluate("CONTI.LIB.q='';CONTI.render()")
    pg.evaluate("(id)=>{CONTI.LIB.detail=null;CONTI.LIB.tab='arr';CONTI.go('library/'+id)}", songs[0]['id']); pg.wait_for_selector('.songtop h1', timeout=8000); pg.wait_for_timeout(800)
    d3 = pg.evaluate("""()=>{const h=document.querySelector('.songtop h1');const t=document.querySelector('.songtop');
      return {w:h.getBoundingClientRect().width,sw:h.scrollWidth,over:t.scrollWidth-t.clientWidth,
        clone:!!(document.querySelector('.songtop [data-act="song-clone"]')||{}).offsetParent}}""")
    if d3['w'] < d3['sw'] or d3['w'] < 60: fail('D3 폰 곡 상세 제목이 잘림: %s' % d3)
    if d3['over'] > 1: fail('D3 상단 줄이 화면 밖으로 넘침: %s' % d3)
    if d3['clone']: fail('D3 폰 상단에 다른 키로 글자 단추가 남음')
    pg.click('.songtop [data-act="song-more"]'); pg.wait_for_selector('#smInfo', timeout=5000)
    if not pg.evaluate("!!document.querySelector('#smClone').offsetParent"): fail('D3 폰 ≡ 안에 다른 키로가 없음')
    pg.click('#smClone'); pg.wait_for_timeout(1500)   # prompt 는 빈 값으로 받는다 → 서버가 거절하거나 '새 편곡'
    if not any('어느 키로' in d for d in pg.dialogs): fail('D3 ≡ 의 다른 키로가 키를 묻지 않음')
    # 데스크톱은 전과 같다 (상단 글자 단추 · ≡ 에는 없음)
    pg.set_viewport_size({'width': 1240, 'height': 900}); pg.evaluate('CONTI.render()'); pg.wait_for_selector('.songtop h1'); pg.wait_for_timeout(500)
    if not pg.evaluate("!!document.querySelector('.songtop [data-act=\"song-clone\"]').offsetParent"): fail('D3 데스크톱 상단의 다른 키로가 사라짐')
    if '연습' not in pg.locator('.songtop [data-arrplay]').inner_text(): fail('D3 데스크톱 연습 단추 글자가 사라짐')
    pg.click('.songtop [data-act="song-more"]'); pg.wait_for_selector('#smInfo', timeout=5000)
    if pg.evaluate("!!document.querySelector('#smClone').offsetParent"): fail('D3 데스크톱 ≡ 에 다른 키로가 겹쳐 보임')
    pg.click('#modal [data-close]')
    print('D3 폰 곡 상세: 제목 %dpt 다 보임 · 연습/예배에 넣기는 아이콘 · 다른 키로는 ≡ 안 (데스크톱은 그대로) ok' % d3['w'])
    if pg.errs: fail('페이지 오류: %s' % pg.errs)
    c.close()

# ---------------------------------------------------------------- D7 · D8 · D9
def sec_lineup(b):
    c = b.new_context(**PHONE)
    _, luid = signup(c, 'nl', 'Qaleader')
    team, inv = make_team(c, '편성팀', 'Qaleader')
    cm = b.new_context()
    _, muid = signup(cm, 'nm', 'QA드럼')
    ok(cm.request.post(URL + 'api/invite/%s/join' % inv, headers=H, data={'name': 'QA드럼', 'sessions': ['드럼']}), 'join')
    d = (datetime.date.today() + datetime.timedelta(days=10)).isoformat()
    did = ok(c.request.post(URL + 'api/teams/%s/dates' % team, headers=H, data={'date': d, 'label': '주일예배', 'time': '11:00'}), 'date')['date']['id']
    ok(c.request.put(URL + 'api/teams/%s/dates/%s/lineup' % (team, did), headers=H,
        data={'lineup': [{'session': '드럼', 'memberId': muid}, {'session': '인도자', 'memberId': luid}]}), 'lineup')
    pg = page(c)
    pg.evaluate("(id)=>CONTI.go('lineup/'+id)", did); pg.wait_for_selector('.lnbody', timeout=10000); pg.wait_for_timeout(1200)
    if not pg.evaluate("(()=>{const b=document.querySelector('.lnbody');return b.scrollHeight>b.clientHeight+50})()"): fail('준비: 편성 패널이 스크롤되지 않음')
    pg.evaluate("document.querySelector('.lnbody').scrollTop=9999"); pg.wait_for_timeout(200)
    top0 = pg.evaluate("document.querySelector('.lnbody').scrollTop")
    pg.click('[data-act="lnotify"]')
    if not wait_until(pg, "document.querySelector('.lnhd .hint')&&document.querySelector('.lnhd .hint').textContent.includes('통보함')", 8000): fail('준비: 통보가 안 끝남')
    pg.wait_for_timeout(1500)
    top1 = pg.evaluate("document.querySelector('.lnbody').scrollTop")
    if abs(top1 - top0) > 2: fail('D7 통보한 뒤 편성 패널이 %s → %s 로 튐' % (top0, top1))
    print('D7 통보 뒤에도 편성 패널이 보던 자리(%d) 그대로 ok' % top1)

    conf = [m for m in pg.dialogs if '편성을 알릴까요' in m]
    if conf != ['QA드럼에게 편성을 알릴까요?']: fail('D8 통보 확인 문구: %s (조사를 붙이고 나는 빼야 한다)' % pg.dialogs)
    ln = [n for n in ok(c.request.get(URL + 'api/notifications?team=' + team), 'noti L')['notifications'] if n['type'] in ('lineup.notify', 'lineup.changed')]
    if ln: fail('D8 통보한 인도자에게도 편성 알림이 감: %s' % [n['title'] for n in ln])
    mn = [n for n in ok(cm.request.get(URL + 'api/notifications?team=' + team), 'noti M')['notifications'] if n['type'] == 'lineup.notify']
    if len(mn) != 1 or '드럼으로 섭니다' not in mn[0]['title']: fail('D8 멤버 통보가 안 감: %s' % mn)
    if '통보 후 변경' in pg.locator('.lnft').inner_text(): fail('D8 나를 빼고 보냈더니 통보 후 변경으로 보임')
    # 드럼을 빼고 인도자만 남겨 변경 통보: 빠진 드럼에게 알린다고 묻고(빠졌어요 알림이 간다) · 서버는 나에게 안 보낸다
    ok(c.request.put(URL + 'api/teams/%s/dates/%s/lineup' % (team, did), headers=H, data={'lineup': [{'session': '인도자', 'memberId': luid}]}), 'lineup2')
    pg.evaluate("CONTI.pullSchedule(null,true).then(()=>CONTI.render())"); pg.wait_for_timeout(1200)
    pg.dialogs.clear(); pg.click('[data-act="lnotify"]'); pg.wait_for_timeout(1500)
    if [m for m in pg.dialogs if '알릴' in m] != ['QA드럼에게 편성을 알릴까요?']: fail('D8 빠진 사람에게 알리는 변경 통보의 확인 문구: %s' % pg.dialogs)
    ln = [n for n in ok(c.request.get(URL + 'api/notifications?team=' + team), 'noti L2')['notifications'] if n['type'] in ('lineup.notify', 'lineup.changed')]
    if ln: fail('D8 변경 통보에서도 인도자에게 감: %s' % [n['title'] for n in ln])
    mn = [n for n in ok(cm.request.get(URL + 'api/notifications?team=' + team), 'noti M2')['notifications'] if n['type'] == 'lineup.changed']
    if len(mn) != 1 or '빠졌어요' not in mn[0]['title']: fail('D8 빠진 멤버에게 변경 통보가 안 감: %s' % mn)
    # 나만 선 날: 알릴 다른 사람이 없다고 묻는다
    d2 = (datetime.date.today() + datetime.timedelta(days=17)).isoformat()
    did2 = ok(c.request.post(URL + 'api/teams/%s/dates' % team, headers=H, data={'date': d2, 'label': '수요예배', 'time': '19:30'}), 'date2')['date']['id']
    ok(c.request.put(URL + 'api/teams/%s/dates/%s/lineup' % (team, did2), headers=H, data={'lineup': [{'session': '인도자', 'memberId': luid}]}), 'lineup3')
    pg.evaluate("CONTI.pullSchedule(null,true)"); pg.wait_for_timeout(800)
    pg.evaluate("(id)=>CONTI.go('lineup/'+id)", did2); pg.wait_for_selector('.lnbody', timeout=10000); pg.wait_for_timeout(800)
    pg.dialogs.clear(); pg.click('[data-act="lnotify"]'); pg.wait_for_timeout(1500)
    if not any('알릴 다른 사람이 없어요' in m for m in pg.dialogs): fail('D8 나만 선 날의 확인 문구: %s' % pg.dialogs)
    if [n for n in ok(c.request.get(URL + 'api/notifications?team=' + team), 'noti L3')['notifications'] if n['type'] in ('lineup.notify', 'lineup.changed')]:
        fail('D8 나만 선 날 통보가 나에게 감')
    print('D8 확인 문구 "QA드럼에게 …"(빠진 사람도) · 나만 선 날은 "알릴 다른 사람이 없어요" · 누른 인도자에게는 안 보냄 ok')

    # D9 알림함: 멤버 가입은 사람 아이콘
    pg.goto(URL + '#/inbox'); pg.wait_for_selector('.nrow2', timeout=10000); pg.wait_for_timeout(500)
    icon = pg.evaluate("""()=>{const r=[...document.querySelectorAll('.nrow2')].find(x=>x.textContent.includes('들어왔어요'));return r?r.querySelector('.ni').innerHTML:''}""")
    if 'r="3.2"' not in icon: fail('D9 멤버 가입 알림 아이콘이 사람 아이콘이 아님: %s' % icon[:120])
    print('D9 멤버 가입 알림은 사람 아이콘 ok')
    if pg.errs: fail('페이지 오류: %s' % pg.errs)
    c.close(); cm.close()

# ---------------------------------------------------------------- D4 · D5
def sec_memo(b):
    c = b.new_context(**PHONE)
    signup(c, 'mo', '리더')
    team, _ = make_team(c, '메모팀', '리더')
    sid = ok(c.request.post(URL + 'api/songs', headers=H, data={'teamId': team, 'title': '주님 찬양', 'key': 'G', 'form': 'A – B'}), 'song')['song']['id']
    pg = page(c); pg.evaluate(TOASTS)
    pg.evaluate("CONTI.pullSongs(true)"); pg.wait_for_timeout(1200)
    pg.evaluate("(id)=>{CONTI.LIB.detail=null;CONTI.go('library/'+id)}", sid); pg.wait_for_selector('.acard', timeout=10000); pg.wait_for_timeout(400)
    pg.click('.acard [data-arradd]'); pg.wait_for_selector('#atsGo', timeout=6000)
    pg.click('[data-ats="new"]'); pg.wait_for_selector('#atsName', timeout=5000)
    pg.fill('#atsName', '메모 예배'); pg.click('#atsGo')
    pg.wait_for_selector('[data-f="item.title"]', timeout=10000); pg.wait_for_timeout(600)
    svc = pg.evaluate("CONTI.route().a")
    pg.set_input_files('#pieceFile', [SHEET]); pg.wait_for_timeout(2500)
    pg.evaluate("""(()=>{const s=CONTI.S.services.find(x=>x.id===CONTI.route().a);const it=s.items[0];
      it.pieces[0].markers=[{id:'mk1',label:'A',x:40,y:60,cut:120}];CONTI.save();CONTI.render()})()""")
    pg.wait_for_timeout(1500)
    if not pg.evaluate("(id)=>!!CONTI.arrOfItem(CONTI.S.services.find(x=>x.id===id).items[0])", svc): fail('준비: 곡이 편곡에 안 이어짐')
    pg.click('[data-act="publish"]'); pg.wait_for_selector('#pubOnly', timeout=6000); pg.click('#pubOnly')
    if not wait_until(pg, "(id)=>{const s=CONTI.S.services.find(x=>x.id===id);return s&&s.published&&!s.pubPending}", 20000, svc): fail('준비: 발행이 안 끝남')

    # 연습 화면 — 켜 둔 채 서버가 안 닿는다(NET.server 는 true 로 남는다 · 아이폰의 약한 와이파이·포털)
    pg.goto(URL + '#/play/%s/0' % svc); pg.wait_for_selector('[data-marker="mk1"]', timeout=15000)
    pg.wait_for_timeout(4500)   # 라이브러리 올리기(3초 뒤)까지 끝나게 — 그 뒤의 저장이 메모를 대신 밀어 주면 D5 가 시험이 안 된다
    blocked = []
    def blk(r): blocked.append(r.request.method + ' ' + r.request.url.split('/api')[1].split('?')[0]); r.abort()
    pg.route('**/api/**', blk)
    pg.evaluate("window.__toasts=[]")
    pg.locator('span.mk[data-marker="mk1"]').first.click(); pg.wait_for_selector('#cText', timeout=6000)
    if not pg.locator('[data-w2="always"].on').count(): fail('준비: 연결돼 있을 때 인도자 기본이 이 곡에 항상이 아님')
    pg.fill('#cText', '항상 메모'); pg.click('#cSave'); pg.wait_for_timeout(2500)
    ts = pg.evaluate("window.__toasts")
    if not any(b.startswith('POST /arrangements/') for b in blocked): fail('준비: 고정 메모 저장이 막히지 않음 %s' % blocked)
    if any(('fetch' in t.lower()) or ('load failed' in t.lower()) for t in ts): fail('D4 브라우저 영어 오류가 토스트에 뜸: %s' % ts)
    if not any('연결이 안 돼 이번 예배에만 남겼어요' in t and '이 곡에 항상' in t for t in ts): fail('D4 고정 메모를 이번 예배 메모로 남긴 까닭을 말하지 않음: %s' % ts)
    if '항상 메모' not in pg.evaluate("(id)=>CONTI.S.services.find(x=>x.id===id).items[0].notes.map(n=>n.text)", svc): fail('D4 못 남긴 고정 메모가 이번 예배 메모로도 안 남음')
    print('D4 끊긴 채 이 곡에 항상: 우리말로 까닭("%s") · 이번 예배 메모로 남김 ok' % ([t for t in ts if '연결' in t] or [''])[0])

    # D5 이번 예배만 메모 — 못 올렸다고 알리고, 서버가 다시 닿으면(online 이벤트 없이) 저절로 다시 올린다
    pg.evaluate("window.__toasts=[]")
    pg.locator('span.mk[data-marker="mk1"]').first.click(); pg.wait_for_selector('#cText', timeout=6000)
    pg.click('[data-w2="once"]'); pg.fill('#cText', '한 번 메모'); pg.click('#cSave'); pg.wait_for_timeout(2000)
    ts = pg.evaluate("window.__toasts")
    if not any('못 올렸어요' in t and '연결되면' in t for t in ts): fail('D5 끊긴 채 쓴 메모에 못 올렸다는 표시가 없음: %s' % ts)
    pg.unroute('**/api/**')
    t0 = time.time(); got = False
    while time.time() - t0 < 14:
        pg.wait_for_timeout(700)
        if any(n['text'] == '한 번 메모' for n in ok(c.request.get(URL + 'api/notes?team=%s&service=%s' % (team, svc)), 'notes')['notes']): got = True; break
    if not got: fail('D5 서버가 다시 닿았는데 못 올린 메모를 다시 올리지 않음 (online 이벤트·화면 복귀 전)')
    srv = [n['text'] for n in ok(c.request.get(URL + 'api/notes?team=%s&service=%s' % (team, svc)), 'notes2')['notes']]
    if '항상 메모' not in srv: fail('D4 이번 예배 메모로 남긴 고정 메모가 서버에 안 올라감: %s' % srv)
    print('D5 못 올린 메모: "못 올렸어요 · 연결되면 올려요" · 서버가 닿자 %.1f초 만에 다시 올림 ok' % (time.time() - t0))

    # D4 앱이 오프라인인 줄 알 때: 인도자도 '이번 예배만'이 기본이고 까닭을 적는다
    pg.evaluate("CONTI.NET.server=null")
    pg.locator('span.mk[data-marker="mk1"]').first.click(); pg.wait_for_selector('#cText', timeout=6000)
    if not pg.locator('[data-w2="once"].on').count(): fail('D4 오프라인인데 인도자 기본이 이 곡에 항상')
    if '연결된 뒤에' not in pg.locator('#cWhenHint').inner_text(): fail('D4 오프라인 안내가 없음: %s' % pg.locator('#cWhenHint').inner_text())
    pg.click('#modal [data-close]'); pg.evaluate("CONTI.NET.server=true")
    print('D4 오프라인이면 이번 예배만이 기본 · "이 곡에 항상은 연결된 뒤에" ok')
    if pg.errs: fail('페이지 오류: %s' % pg.errs)
    c.close()

def run():
    with sync_playwright() as p:
        b = p.webkit.launch() if os.environ.get('WK') else p.chromium.launch()
        only = sys.argv[1:]
        try:
            for name, fn in (('read', sec_read), ('library', sec_library), ('lineup', sec_lineup), ('memo', sec_memo)):
                if only and name not in only: continue
                fn(b)
        finally:
            b.close()
    if FAILS: print('FAILED %d:' % len(FAILS)); [print(' -', f) for f in FAILS]; sys.exit(1)
    print('OK test_simfix_lineup_library')

if __name__ == '__main__':
    run()
