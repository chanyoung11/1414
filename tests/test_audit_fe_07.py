# 전역감사 2026-09-24 fe-07 되돌림 방지
#  F25 '이 기기에서 끄기'가 홈에 오면 풀리던 것 · 홈마다 푸시 구독을 5~6번 보내던 것
#  F89 마디를 고칠 때마다 악보가 맨 위로 튀던 것
#  G08 악보 화면이 콘티의 연주 키(it.key)를 무시하던 것 (인쇄·내보내기 포함)
#  G33 고치기 중에 옮긴 악보를 보고 원래 값을 고치던 것
#  G34 코드 칸이 대문자 고정이라 폰에서 Bm7 이 BM7 로 들어가던 것
#  G19 카포·'여기부터 전조'로 옮긴 코드를 원래 연주 키의 #·b 로 적던 것 (G→Ab 에 G#)
#  F90 AI 호출 중에 팀을 바꾸면 곡이 다른 팀 라이브러리로 복사되던 것
#  F91 연습 화면에서 다음 곡으로 넘길 때마다 서버 응답을 기다리던 것
#  G20 스스로 나간 멤버가 '인도자가 비활성으로 뒀다' 화면에 갇히던 것
# 되돌림 바로잡기:
#  F25 로그아웃·401 뒤 같은 계정으로 다시 들어오면 구독을 다시 안 보내던 것 (F25R)
#  G08 Em 악보를 E·Emin·E minor·E단조 콘티에서 C#m 으로 그리던 것 (SCMODE)
#  G19 B♭ 같은 느슨한 키·키 모를 때 카포·반감화음·베이스 글자 (CHORD2)
#  F91 들어올 때 받기가 늦게 실패하면 다시 그리기를 되풀이·곡마다 2.5초 기다림·옮겨도 메모·말씀을 안 받음 (F91B)
import os, sys, time, json
from playwright.sync_api import sync_playwright

URL = os.environ.get('CONTI_URL', 'http://localhost:8766/')
H = {'x-conti': '1'}
tag = str(int(time.time()))[-6:]
def fail(m): print('FAIL:', m); sys.exit(1)

# 헤드리스 크로뮴은 푸시 서비스에 못 붙는다. 권한은 'granted' 로, 구독은 가짜로
PUSH_STUB = r"""
(()=>{
 try{Object.defineProperty(Notification,"permission",{get:()=>"granted",configurable:true})}catch(e){}
 const st={sub:null,n:0};window.__pushst=st;
 const mk=(key)=>{st.n++;const ep='https://example.invalid/push/stub'+Date.now()+'-'+st.n;
   return {endpoint:ep,options:{applicationServerKey:key},
     toJSON(){return {endpoint:ep,keys:{p256dh:'BObJ'+'A'.repeat(83),auth:'x'.repeat(22)}}},
     async unsubscribe(){st.sub=null;return true}}};
 PushManager.prototype.getSubscription=async function(){return st.sub};
 PushManager.prototype.subscribe=async function(o){let k=o.applicationServerKey;
   if(k instanceof Uint8Array)k=k.buffer.slice(k.byteOffset,k.byteOffset+k.byteLength);
   st.sub=mk(k);return st.sub};
})();
"""

def signup(pg, user, name='하은'):
    pg.goto(URL); pg.wait_for_selector('#lgUser', timeout=10000)
    pg.click('[data-act="lg-mode"][data-m="signup"]'); pg.wait_for_selector('#lgName')
    pg.check('#lgAgree')
    pg.fill('#lgName', name); pg.fill('#lgUser', user); pg.fill('#lgPass', 'secret1')
    pg.click('[data-act="lg-submit"]')

def make_team(pg, name):
    pg.wait_for_selector('#gtTeam', timeout=10000); pg.fill('#gtTeam', name)
    pg.click('[data-act="team-create"]'); pg.wait_for_selector('.shell[data-page]', timeout=10000)

def new_page(b, errs, who, **kw):
    c = b.new_context(viewport=kw.pop('viewport', {'width': 1300, 'height': 950}), **kw)
    pg = c.new_page()
    pg.on('pageerror', lambda e: errs.append(who + ': ' + str(e)))
    pg.on('dialog', lambda d: d.accept())
    return c, pg

# ---------------------------------------------------------------- F25
def t_push_off(b, errs):
    c, pg = new_page(b, errs, 'push', permissions=['notifications'])
    c.add_init_script(PUSH_STUB)
    log = []
    pg.on('request', lambda r: log.append(r.url) if '/api/push/subscribe' in r.url else None)
    signup(pg, 'po' + tag); make_team(pg, '푸시팀')
    pg.wait_for_timeout(4000)   # 홈이 일정·콘티를 받고 몇 번 다시 그려질 때까지
    n1 = len(log)
    if n1 != 1: fail('F25 홈에 한 번 들어왔는데 구독을 %d번 보냄 (한 번이어야)' % n1)
    # 홈을 몇 번 오가도 더 보내지 않는다
    for _ in range(2):
        pg.goto(URL + '#/settings'); pg.wait_for_selector('.setpane', timeout=8000)
        pg.goto(URL + '#/'); pg.wait_for_timeout(1200)
    if len(log) != 1: fail('F25 홈을 다시 그릴 때마다 구독을 또 보냄: %d' % len(log))
    print('F25 홈 구독 한 번만 ok')

    pg.goto(URL + '#/settings'); pg.wait_for_selector('.setpane', timeout=8000)
    pg.click('[data-act="set-tab"][data-t="noti"]'); pg.wait_for_selector('#sPushOff', timeout=5000)
    pg.click('#sPushOff'); pg.wait_for_timeout(1200)
    if pg.evaluate('CONTI.pushState()') != 'off': fail('F25 끈 뒤 상태가 off 가 아님: %s' % pg.evaluate('CONTI.pushState()'))
    if not pg.locator('#sPushOn').count(): fail('F25 끈 뒤 설정에 "알림 켜기"가 없음')
    n2 = len(log)
    pg.goto(URL + '#/'); pg.wait_for_timeout(3500)
    if len(log) != n2: fail('F25 끈 뒤 홈에 오자 다시 구독함')
    if pg.evaluate('!!window.__pushst.sub'): fail('F25 끈 뒤 브라우저 구독이 되살아남')
    # 새로 열어도(새 세션) 꺼진 채로
    pg.reload(); pg.wait_for_selector('.shell[data-page]', timeout=10000); pg.wait_for_timeout(3500)
    if len(log) != n2: fail('F25 다시 열었더니 다시 구독함')
    if pg.evaluate('CONTI.pushState()') != 'off': fail('F25 다시 연 뒤 off 가 풀림')
    print('F25 끄기가 홈·새로 열기 뒤에도 유지 ok')

    # 다시 켜면 구독하고, 그 뒤로는 켜진 상태
    pg.goto(URL + '#/settings'); pg.wait_for_selector('.setpane', timeout=8000)
    pg.click('[data-act="set-tab"][data-t="noti"]'); pg.wait_for_selector('#sPushOn', timeout=5000)
    pg.click('#sPushOn'); pg.wait_for_timeout(1500)
    if len(log) != n2 + 1: fail('F25 다시 켰는데 구독을 안 보냄: %d' % (len(log) - n2))
    if pg.evaluate('CONTI.pushState()') != 'granted': fail('F25 다시 켠 뒤 상태가 granted 가 아님')
    print('F25 다시 켜기 ok')
    pg.goto(URL + '#/'); pg.wait_for_timeout(2500)
    if len(log) != n2 + 1: fail('F25 설정에서 켠 뒤 홈에 오자 구독을 또 보냄: %d' % (len(log) - n2))
    c.close()

def db_count(sql):
    import subprocess
    try:
        r = subprocess.run(['docker', 'exec', 'conti-pg', 'psql', '-U', 'postgres', '-tAc', sql], capture_output=True, text=True, timeout=20)
    except Exception:
        return None
    return int(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip().isdigit() else None

def login(pg, user):
    pg.wait_for_selector('#lgUser', timeout=10000)
    if pg.locator('#lgName').count(): pg.click('[data-act="lg-mode"][data-m="login"]'); pg.wait_for_timeout(200)   # 가입하던 창이면 로그인으로
    pg.fill('#lgUser', user); pg.fill('#lgPass', 'secret1'); pg.click('[data-act="lg-submit"]')
    pg.wait_for_selector('.shell[data-page]', timeout=10000)

# 로그아웃하면 서버가 이 기기 구독을 지운다. 새로 열지 않고 같은 계정으로 다시 들어오면 다시 구독해야 한다
# (한 세션 한 번 가드가 계정 id 로만 걸려 있어 다시 안 보냈다 — 설정은 '켜져 있어요' 인데 알림은 안 옴)
def t_push_relogin(b, errs):
    c, pg = new_page(b, errs, 'push2', permissions=['notifications'])
    c.add_init_script(PUSH_STUB)
    log = []
    pg.on('request', lambda r: log.append(r.url) if '/api/push/subscribe' in r.url else None)
    user = 'pl' + tag
    signup(pg, user); make_team(pg, '다시팀')
    pg.wait_for_timeout(4000)
    if len(log) != 1: fail('F25 준비: 처음 홈에서 구독 %d번' % len(log))
    uid = pg.evaluate('CONTI.NET.user.id')
    rows = lambda: db_count("select count(*) from push_subs where user_id='%s'" % uid)
    if rows() not in (None, 1): fail('F25 준비: 서버 구독이 1개가 아님 %s' % rows())

    # 1) 로그아웃 → 같은 계정으로 다시 로그인 (새로 열지 않음)
    pg.goto(URL + '#/settings'); pg.wait_for_selector('.setpane', timeout=8000)
    pg.click('[data-act="set-tab"][data-t="app"]'); pg.wait_for_selector('#sLogout', timeout=8000)
    pg.click('#sLogout'); pg.wait_for_selector('#lgUser', timeout=10000)
    if rows() not in (None, 0): fail('F25 로그아웃했는데 서버 구독이 남음 %s' % rows())
    login(pg, user); pg.wait_for_timeout(4000)
    if len(log) != 2: fail('F25 로그아웃 뒤 다시 로그인했는데 구독을 %d번 보냄 (1번이어야)' % (len(log) - 1))
    if rows() not in (None, 1): fail('F25 다시 로그인 뒤 서버 구독이 %s개' % rows())
    print('F25 로그아웃 → 다시 로그인하면 다시 구독 ok')

    # 2) 다른 기기에서 '모든 기기에서 로그아웃' → 이 화면은 401 로 로그인 창 → 다시 로그인
    c2 = b.new_context(); r = c2.request.post(URL + 'api/auth/login', headers=H, data={'username': user, 'password': 'secret1'})
    if r.status != 200: fail('F25 준비: 다른 기기 로그인 실패 %s' % r.status)
    r = c2.request.post(URL + 'api/auth/logout', headers=H, data={'all': True}); c2.close()
    if r.status != 200: fail('F25 준비: 모든 기기 로그아웃 실패 %s' % r.status)
    if rows() not in (None, 0): fail('F25 준비: 모든 기기 로그아웃인데 서버 구독이 남음')
    pg.evaluate("CONTI.NET.server=null;dispatchEvent(new Event('online'))")   # 다시 붙으며 /me 가 401
    pg.wait_for_selector('#lgUser', timeout=10000)
    n = len(log); login(pg, user); pg.wait_for_timeout(4000)
    if len(log) != n + 1: fail('F25 401 뒤 다시 로그인했는데 구독을 %d번 보냄 (1번이어야)' % (len(log) - n))
    if rows() not in (None, 1): fail('F25 401 뒤 다시 로그인한 뒤 서버 구독이 %s개' % rows())
    # 로그인한 채로 /me 를 다시 받는 것(팀 전환 등)으로는 또 보내지 않는다
    pg.goto(URL + '#/settings'); pg.wait_for_selector('.setpane', timeout=8000); pg.goto(URL + '#/'); pg.wait_for_timeout(1500)
    if len(log) != n + 1: fail('F25 다시 로그인한 뒤 홈을 오가자 구독을 또 보냄')
    print('F25 다른 기기에서 모두 로그아웃 → 다시 로그인하면 다시 구독 ok' + ('' if rows() is not None else ' (DB 확인은 건너뜀)'))
    c.close()

# ---------------------------------------------------------------- 악보 화면 (G08 · G33 · F89)
CH = ['G', 'Bm7', 'C', 'D']
def long_score(n=80):
    return {'at': 1, 'model': 'test', 'lines': 10, 'title': '긴 악보', 'key': 'G', 'time': '4/4', 'verses': 1, 'pickup': False,
            'measures': [{'c': [{'b': 0, 't': CH[i % 4]}], 'n': [{'p': 'G4', 'd': 4}, {'p': 'B4', 'd': 4}, {'p': 'D5', 'd': 4}, {'p': 'B4', 'd': 4}]} for i in range(n)]}

def svg_text(pg):
    return pg.evaluate("(()=>{const s=document.querySelector('#osmd svg');return s?s.outerHTML:''})()")

def wait_draw(pg, before_seq=None):
    if before_seq is not None:
        pg.wait_for_function('CONTI.SC.seq>%d' % before_seq, timeout=15000)
    pg.wait_for_selector('#osmd svg', timeout=25000); pg.wait_for_timeout(900)

# 악보를 스크롤하는 칸 — 넓은 화면은 #scorewrap, 폰은 .ws
SCROLLER = """()=>{for(let e=document.querySelector('#osmd').parentElement;e;e=e.parentElement){const o=getComputedStyle(e).overflowY;
  if((o==='auto'||o==='scroll')&&e.scrollHeight>e.clientHeight+10)return e}return document.scrollingElement}"""
def scroll_top(pg):
    return pg.evaluate('(' + SCROLLER + ')().scrollTop')

def measure_click(pg, mi):
    # 마디 mi 가 화면에 오게 스크롤한 뒤 그 마디를 누른다
    box = pg.evaluate("""(mi)=>{const o=CONTI.SC.osmd,k=CONTI.SC.k;const m=o.GraphicSheet.MeasureList[mi][0].PositionAndShape;
      const sv=document.querySelector('#osmd svg');let r=sv.getBoundingClientRect();
      const y=r.top+m.AbsolutePosition.y*k;
      if(y<80||y>innerHeight-120){(""" + SCROLLER + """)().scrollTop+=y-innerHeight/2}
      r=sv.getBoundingClientRect();
      return {x:r.left+(m.AbsolutePosition.x+m.Size.width/2)*k,y:r.top+(m.AbsolutePosition.y+m.Size.height/2)*k}}""", mi)
    pg.mouse.click(box['x'], box['y'])

def t_score(b, errs):
    c, pg = new_page(b, errs, 'score')
    signup(pg, 'sk' + tag); make_team(pg, '악보키팀')
    pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]'); pg.fill('[data-f="svc.name"]', '키 예배')
    pg.click('[data-act="add-item"]'); pg.wait_for_selector('[data-f="item.title"]')
    pg.fill('[data-f="item.title"]', '긴 악보'); pg.fill('[data-f="item.key"]', 'A'); pg.wait_for_timeout(400)
    svc = pg.evaluate('CONTI.S.services[0].id'); item = pg.evaluate('CONTI.S.services[0].items[0].id')
    pg.evaluate("(sc)=>{const it=CONTI.S.services[0].items[0];it.score=sc;it.key='A';CONTI.save()}", long_score())
    pg.goto(URL + '#/score/%s/%s' % (svc, item)); wait_draw(pg)

    # ---- G08: 콘티 키 A 로 그린다 (악보는 G) ----
    pill = pg.locator('.top .pill.key').first.inner_text()
    if pill != 'A': fail('G08 머리말 키가 연주 키 A 가 아님: %r' % pill)
    s = svg_text(pg)
    if 'C#m7' not in s or 'Bm7' in s: fail('G08 악보가 연주 키로 안 옮겨짐 (C#m7 있어야, Bm7 없어야)')
    if '악보 G → 연주 A' not in pg.locator('.top h1').inner_text(): fail('G08 악보 키 → 연주 키 안내가 없음')
    # 반음 올리면 A 에서 +1 = Bb
    seq = pg.evaluate('CONTI.SC.seq'); pg.click('[data-act="score-tr"][data-d="1"]'); wait_draw(pg, seq)
    if pg.locator('.top .pill.key').first.inner_text() != 'Bb': fail('G08 A 에서 반음 올린 키가 Bb 가 아님')
    seq = pg.evaluate('CONTI.SC.seq'); pg.click('[data-act="score-tr"][data-d="0"]'); wait_draw(pg, seq)
    if 'C#m7' not in svg_text(pg): fail('G08 원본(연주 키)으로 안 돌아옴')
    # 내보내기·인쇄도 같은 키
    xml = pg.evaluate("""(()=>{let got='';const A=HTMLAnchorElement.prototype.click;
      HTMLAnchorElement.prototype.click=function(){if(this.download)got=this.href;else A.call(this)};
      return new Promise(res=>{document.querySelector('[data-act="score-menu"]').click();
        setTimeout(()=>{document.querySelector('#smXml').click();HTMLAnchorElement.prototype.click=A;
          fetch(got).then(r=>r.text()).then(res)},300)})})()""")
    if '<fifths>3</fifths>' not in xml: fail('G08 MusicXML 이 A 조표(#3)가 아님')
    pg.evaluate("window.__pc=0;window.print=()=>{window.__pc++}")
    pg.click('[data-act="score-print"]'); pg.wait_for_function('window.__pc>0', timeout=20000)
    ps = pg.evaluate("(()=>{const a=document.querySelector('#printArea');return a?a.innerHTML:''})()")
    pg.evaluate("const a=document.querySelector('#printArea');if(a)a.remove();document.body.classList.remove('printing')")
    if 'C#m7' not in ps: fail('G08 인쇄본이 연주 키가 아님')
    # 카포 2: 연주 키 A 에서 2프렛 내린 G 모양 → 적힌 그대로 (예전에는 G−2 = F 모양)
    pg.evaluate("CONTI.S.team.me.capo=2"); seq = pg.evaluate('CONTI.SC.seq'); pg.evaluate('CONTI.render()'); wait_draw(pg, seq)
    s = svg_text(pg)
    if 'Bm7' not in s or 'Am7' in s: fail('G08 카포 모양이 연주 키 기준이 아님 (Bm7 이어야)')
    if pg.locator('.top .pill.key').first.inner_text() != 'A': fail('G08 카포일 때 머리말 키')
    print('G08 악보 화면·인쇄·내보내기가 연주 키 ok')

    # ---- G33: 고치기 중에는 적힌 그대로 보이고, 마디 창도 같은 값 ----
    seq = pg.evaluate('CONTI.SC.seq'); pg.click('[data-act="score-edit"]'); wait_draw(pg, seq)
    s = svg_text(pg)
    if 'Bm7' not in s or 'C#m7' in s: fail('G33 고치기 중인데 옮긴 악보를 그림')
    if pg.locator('.top .pill.key').first.inner_text() != 'G': fail('G33 고치기 중 머리말 키가 적힌 키가 아님')
    if not pg.locator('[data-act="score-tr"][data-d="1"]').is_disabled(): fail('G33 고치기 중에 조옮김 버튼이 살아 있음')
    print('G33 고치기 중 적힌 키로 ok')

    # ---- F89: 68마디를 고쳐도 스크롤이 그대로 ----
    measure_click(pg, 67); pg.wait_for_selector('[data-ct="0"]', timeout=6000)
    if pg.locator('[data-ct="0"]').input_value() != 'D': fail('G33 68마디 창의 코드가 화면과 다름: %r' % pg.locator('[data-ct="0"]').input_value())
    top0 = scroll_top(pg)
    if top0 < 300: fail('F89 준비: 68마디로 스크롤이 안 됨 (%s)' % top0)
    seq = pg.evaluate('CONTI.SC.seq')
    pg.fill('[data-ct="0"]', 'Cmaj7'); wait_draw(pg, seq)   # 600ms 뒤 다시 그림
    top1 = scroll_top(pg)
    if abs(top1 - top0) > 5: fail('F89 코드를 고치자 스크롤이 %s → %s 로 튐' % (top0, top1))
    seq = pg.evaluate('CONTI.SC.seq'); pg.click('#mRs'); wait_draw(pg, seq)   # 바로 다시 그리는 쪽(commit)
    top2 = scroll_top(pg)
    if abs(top2 - top0) > 5: fail('F89 도돌이표를 켜자 스크롤이 %s → %s 로 튐' % (top0, top2))
    if pg.evaluate("document.querySelectorAll('#osmd svg').length") != 1: fail('F89 악보가 두 벌 그려짐')
    pg.click('[data-close="1"]'); pg.wait_for_timeout(1500)
    got = pg.evaluate("CONTI.S.services[0].items[0].score.measures[67].c[0].t")
    if got != 'Cmaj7': fail('G33 고친 코드가 적힌 값으로 저장 안 됨: %r' % got)
    print('F89 마디 고쳐도 스크롤 유지 ok (%d)' % top0)

    # 폰 폭에서는 문서 전체가 스크롤된다 (.pbody 가 overflow:visible)
    pg.set_viewport_size({'width': 400, 'height': 800})
    pg.goto(URL + '#/'); pg.wait_for_timeout(800)
    pg.goto(URL + '#/score/%s/%s' % (svc, item)); wait_draw(pg)
    if not pg.evaluate('CONTI.SC.edit'):   # 같은 악보로 돌아오면 고치기가 켜진 채다
        seq = pg.evaluate('CONTI.SC.seq'); pg.click('[data-act="score-edit"]'); wait_draw(pg, seq)
    measure_click(pg, 40); pg.wait_for_selector('[data-ct="0"]', timeout=6000)
    d0 = scroll_top(pg)
    if d0 < 300: fail('F89 준비(폰): 문서 스크롤이 안 됨 (%s)' % d0)
    seq = pg.evaluate('CONTI.SC.seq'); pg.click('#mRe'); wait_draw(pg, seq)
    d1 = scroll_top(pg)
    if abs(d1 - d0) > 5: fail('F89 폰에서 마디를 고치자 스크롤이 %s → %s 로 튐' % (d0, d1))
    print('F89 폰 폭 문서 스크롤 유지 ok (%d)' % d0)
    c.close()

# G08 장·단조가 다른 콘티 키: 으뜸음이 같으면(E ↔ Em) 그대로, 나란한조(G ↔ Em)도 그대로, 나머지는 코드 띠처럼 으뜸음 차이.
# 예전 규칙은 끝 글자 'm' 만 단조로 봐 Em 악보를 E·Emin·E minor·E단조 콘티에서 C#m 으로 그렸다
def t_score_mode(b, errs):
    c, pg = new_page(b, errs, 'scmode')
    signup(pg, 'sm' + tag); make_team(pg, '단조팀')
    pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]'); pg.fill('[data-f="svc.name"]', '단조 예배')
    pg.click('[data-act="add-item"]'); pg.wait_for_selector('[data-f="item.title"]')
    pg.fill('[data-f="item.title"]', '단조곡'); pg.fill('[data-f="item.key"]', 'E'); pg.wait_for_timeout(400)
    svc = pg.evaluate('CONTI.S.services[0].id'); item = pg.evaluate('CONTI.S.services[0].items[0].id')
    sc = {'at': 1, 'model': 'test', 'lines': 2, 'title': '단조곡', 'key': 'Em', 'time': '4/4', 'verses': 1, 'pickup': False,
          'measures': [{'c': [{'b': 0, 't': t}], 'n': [{'p': 'E4', 'd': 1}]} for t in ['Em', 'Am', 'B7', 'C']]}
    pg.evaluate("(sc)=>{const it=CONTI.S.services[0].items[0];it.score=sc;it.key='E';CONTI.save()}", sc)
    pg.goto(URL + '#/score/%s/%s' % (svc, item)); wait_draw(pg)
    def show(key):
        seq = pg.evaluate('CONTI.SC.seq')
        pg.evaluate("(k)=>{CONTI.S.services[0].items[0].key=k;CONTI.render()}", key); wait_draw(pg, seq)
        return pg.locator('.top .pill.key').first.inner_text(), svg_text(pg), pg.locator('.top h1').inner_text()
    for key in ['E', 'Emin', 'E minor', 'E단조', 'Em', 'G']:
        pill, s, h1 = show(key)
        if pill != 'Em': fail('G08 Em 악보를 %r 콘티에서 %r 로 옮김 (그대로 Em 이어야)' % (key, pill))
        if 'B7' not in s or 'G#7' in s or 'C#m' in s: fail('G08 Em 악보를 %r 콘티에서 옮겨 그림' % key)
        if '연주 ' + key in h1: fail('G08 %r 콘티인데 옮김 안내가 뜸' % key)
    # 으뜸음이 다르면 코드 띠·차트처럼 으뜸음 차이만큼 (A 콘티 → Am, 조표 차이 +2 인 F#m 이 아니라)
    pill, s, h1 = show('A')
    if pill != 'Am' or 'E7' not in s: fail('G08 A 콘티의 Em 악보가 Am 으로 안 옮겨짐: %r' % pill)
    if '악보 Em' not in h1 or '연주 A' not in h1: fail('G08 A 콘티에서 옮김 안내가 없음')
    # 장조 악보를 나란한 단조 콘티 키로 적어도 그대로 (G ↔ Em)
    pg.evaluate("()=>{const it=CONTI.S.services[0].items[0];it.score.key='G';CONTI.save()}")
    pill, s, h1 = show('Em')
    if pill != 'G' or 'B7' not in s: fail('G08 G 악보를 Em 콘티에서 옮김: %r' % pill)
    pill, s, h1 = show('E minor')
    if pill != 'G': fail('G08 G 악보를 "E minor" 콘티에서 옮김: %r' % pill)
    print('G08 장·단조가 다른 콘티 키 ok')
    c.close()

# ---------------------------------------------------------------- G19 · G34 코드 적기
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHEET = os.path.join(ROOT, 'docs', 'sample_sheet.jpg')

def red_chords(pg):
    return pg.evaluate("[...document.querySelectorAll('#sheet .chd')].map(e=>e.textContent)")

def t_chords(b, errs):
    c, pg = new_page(b, errs, 'chord')
    signup(pg, 'ck' + tag); make_team(pg, '코드팀')
    pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]'); pg.fill('[data-f="svc.name"]', '코드 예배')
    pg.click('[data-act="add-item"]'); pg.wait_for_selector('[data-f="item.title"]')
    pg.fill('[data-f="item.title"]', '전조곡'); pg.fill('[data-f="item.key"]', 'G'); pg.wait_for_timeout(300)
    pg.set_input_files('#pieceFile', [SHEET])
    pg.wait_for_function("(()=>{const it=CONTI.S.services[0].items[0];return it&&(it.pieces||[]).length>0})()", timeout=30000)
    svc = pg.evaluate('CONTI.S.services[0].id')
    # 악보 G · 연주 G. 코드를 직접 넣고, 맨 위에 '+1 전조' 표시
    pg.evaluate("""(()=>{const it=CONTI.S.services[0].items[0];const p=it.pieces[0];
      p.sheetKey='G';p.keyConfirmed=true;p.ocr='done';
      p.chords=['G','C','D/F#','Am7'].map((t,i)=>({id:'c'+i,text:t,x:100+i*120,y:300,w:40,h:30,conf:100,fixed:true}));
      p.markers=(p.markers||[]).concat([{id:'mk1',label:'후렴',x:20,y:10,keyShift:1}]);
      CONTI.save();CONTI.render()})()""")
    pg.wait_for_timeout(800)
    got = red_chords(pg)
    if got != ['Ab', 'Db', 'Eb/G', 'Bbm7']: fail('G19 +1 전조(G→Ab) 코드 이름이 틀림: %s' % got)
    print('G19 여기부터 전조 G→Ab ok:', got)

    # 카포: 연주 키 F, 카포 3 → D 모양 (예전: Gbm · D/Gb · A/Db)
    pg.evaluate("""(()=>{const it=CONTI.S.services[0].items[0];const p=it.pieces[0];it.key='F';p.sheetKey='F';
      p.markers=p.markers.filter(m=>m.id!=='mk1');p.chords=['Am','F/A','C/E','Gm'].map((t,i)=>({id:'d'+i,text:t,x:100+i*120,y:300,w:40,h:30,conf:100,fixed:true}));
      it.chart={key:'F',sections:[{name:'V',bars:[{chords:['Am','F/A']},{chords:['C/E','Gm']}]}]};
      CONTI.S.team.me.capo=3;CONTI.save()})()""")
    pg.goto(URL + '#/play/%s/0' % svc); pg.wait_for_selector('#sheet .chd', timeout=10000); pg.wait_for_timeout(500)
    got = red_chords(pg)
    if got != ['F#m', 'D/F#', 'A/C#', 'Em']: fail('G19 카포 3(F→D 모양) 코드 이름이 틀림: %s' % got)
    pg.goto(URL + '#/view/%s' % svc); pg.wait_for_selector('.chart .cc', state='attached', timeout=10000)
    ch = pg.evaluate("[...document.querySelectorAll('.chart .cc')].map(e=>e.textContent)")
    if ch != ['F#m', 'D/F#', 'A/C#', 'Em']: fail('G19 차트 카포 모양 코드 이름이 틀림: %s' % ch)
    print('G19 카포 모양 ok:', got)
    # D 악보를 C 로: bVII 은 Bb (예전: A#)
    pg.evaluate("""(()=>{const it=CONTI.S.services[0].items[0];const p=it.pieces[0];it.key='C';p.sheetKey='D';
      p.chords=['D','C','G/B','D/C'].map((t,i)=>({id:'e'+i,text:t,x:100+i*120,y:300,w:40,h:30,conf:100,fixed:true}));
      CONTI.S.team.me.capo=0;CONTI.save()})()""")
    pg.goto(URL + '#/edit/%s' % svc); pg.wait_for_selector('#sheet .chd', timeout=10000); pg.wait_for_timeout(500)
    got = red_chords(pg)
    if got != ['C', 'Bb', 'F/A', 'C/Bb']: fail('G19 D→C 에서 bVII 이름이 틀림: %s' % got)
    print('G19 빌려 온 코드 b ok:', got)

    # ---- G34: 코드 칸이 대문자 고정이 아니고, 친 대소문자를 바로잡는다 ----
    pg.click('[data-act="tool"][data-t="chord"]'); pg.wait_for_selector('#sheet .chdbox')
    pg.locator('#sheet .chdbox').first.click(); pg.wait_for_selector('#chText')
    ac = pg.get_attribute('#chText', 'autocapitalize')
    if ac == 'characters': fail('G34 코드 칸이 아직 대문자 고정')
    pg.fill('#chText', 'ASUS4'); pg.click('#chOk'); pg.wait_for_timeout(400)
    t0 = pg.evaluate("CONTI.S.services[0].items[0].pieces[0].chords.find(c=>c.id==='e0').text")
    if t0 != 'Asus4': fail('G34 ASUS4 가 Asus4 로 안 바뀜: %r' % t0)
    pg.locator('#sheet .chdbox').first.click(); pg.wait_for_selector('#chText')
    pg.fill('#chText', 'f#m7/c#'); pg.click('#chOk'); pg.wait_for_timeout(400)
    t0 = pg.evaluate("CONTI.S.services[0].items[0].pieces[0].chords.find(c=>c.id==='e0').text")
    if t0 != 'F#m7/C#': fail('G34 소문자로 친 코드가 안 바로잡힘: %r' % t0)
    pg.click('[data-act="tool"][data-t="marker"]')
    # 악보 마디 창
    pg.evaluate("(sc)=>{const it=CONTI.S.services[0].items[0];it.score=sc;it.key='G';CONTI.save()}", long_score(4))
    item = pg.evaluate('CONTI.S.services[0].items[0].id')
    pg.goto(URL + '#/score/%s/%s' % (svc, item)); wait_draw(pg)
    seq = pg.evaluate('CONTI.SC.seq'); pg.click('[data-act="score-edit"]'); wait_draw(pg, seq)
    measure_click(pg, 1); pg.wait_for_selector('[data-ct="0"]', timeout=6000)
    if pg.get_attribute('[data-ct="0"]', 'autocapitalize') == 'characters': fail('G34 마디 창 코드 칸이 대문자 고정')
    pg.fill('[data-ct="0"]', 'bm7'); pg.wait_for_timeout(200)
    pg.click('[data-close="1"]'); pg.wait_for_timeout(800)
    got = pg.evaluate("CONTI.S.services[0].items[0].score.measures[1].c[0].t")
    if got != 'Bm7': fail('G34 마디 창에 친 bm7 이 Bm7 로 안 들어감: %r' % got)
    print('G34 코드 칸 대소문자 ok')
    c.close()

# G19 되돌림: 느슨하게 적힌 악보 키(B♭), 키를 모를 때의 카포, 반감화음, 베이스 글자
def t_chords_more(b, errs):
    c, pg = new_page(b, errs, 'chord2')
    signup(pg, 'cm' + tag); make_team(pg, '코드둘팀')
    pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]'); pg.fill('[data-f="svc.name"]', '코드 예배2')
    pg.click('[data-act="add-item"]'); pg.wait_for_selector('[data-f="item.title"]')
    pg.fill('[data-f="item.title"]', '베이스곡'); pg.fill('[data-f="item.key"]', 'C'); pg.wait_for_timeout(300)
    pg.set_input_files('#pieceFile', [SHEET])
    pg.wait_for_function("(()=>{const it=CONTI.S.services[0].items[0];return it&&(it.pieces||[]).length>0})()", timeout=30000)
    svc = pg.evaluate('CONTI.S.services[0].id')
    def put(key, sheet_key, chords, capo=0):
        pg.evaluate("""([k,sk,ch,capo])=>{const it=CONTI.S.services[0].items[0];const p=it.pieces[0];it.key=k;p.sheetKey=sk;p.keyConfirmed=true;p.ocr='done';
          p.offset=null;p.markers=[];p.chords=ch.map((t,i)=>({id:'x'+i,text:t,x:100+i*120,y:300,w:40,h:30,conf:100,fixed:true}));
          CONTI.S.team.me.capo=capo;CONTI.save()}""", [key, sheet_key, chords, capo])
    def play():
        pg.goto(URL + '#/'); pg.wait_for_timeout(300)
        pg.goto(URL + '#/play/%s/0' % svc); pg.wait_for_selector('#sheet .chd', timeout=10000); pg.wait_for_timeout(500)
        return red_chords(pg)
    # D 악보를 C 로: 반감화음(이끔음)은 올림, 빌려 온 Bb 의 베이스는 Eb (예전: Abm7b5 · Abø · Ab/D#)
    put('C', 'D', ['A#m7b5', 'A#ø', 'Bb/F', 'E/G#'])
    got = play()
    if got != ['G#m7b5', 'G#ø', 'Ab/Eb', 'D/F#']: fail('G19 반감화음·베이스 이름이 틀림: %s' % got)
    # B♭ 처럼 느슨하게 적힌 악보 키를 A 로 (예전: Gbm · Dbm · E/Ab)
    put('A', 'B♭', ['Gm', 'Dm', 'F/A'])
    got = play()
    if got != ['F#m', 'C#m', 'E/G#']: fail('G19 B♭ 악보를 A 로 옮긴 코드가 b 로 적힘: %s' % got)
    # G 를 카포 2 로 치면 F 모양. 부속화음의 3음 베이스는 올림 (예전: D/Gb)
    put('G', 'G', ['E/G#', 'C', 'D', 'B7/D#'], capo=2)
    got = play()
    if got != ['D/F#', 'Bb', 'C', 'A7/C#']: fail('G19 카포로 F 모양일 때 베이스가 b 로 적힘: %s' % got)
    # 악보 키도 연주 키도 모르면 예전처럼 # (C 로 쳐서 카포 2 에 Gbm 이 나왔다)
    put('', '', ['G#m', 'E', 'C#m'], capo=2)
    got = play()
    if got != ['F#m', 'D', 'Bm']: fail('G19 키를 모를 때 카포 코드가 b 로 적힘: %s' % got)
    # 차트: B♭ 로 적힌 차트를 A 로
    pg.evaluate("""(()=>{const it=CONTI.S.services[0].items[0];it.key='A';it.chart={key:'B♭',sections:[{name:'V',bars:[{chords:['Bb','Gm']},{chords:['Eb','F/A']}]}]};
      CONTI.S.team.me.capo=0;CONTI.save()})()""")
    pg.goto(URL + '#/view/%s' % svc); pg.wait_for_selector('.chart .cc', state='attached', timeout=10000)
    ch = pg.evaluate("[...document.querySelectorAll('.chart .cc')].map(e=>e.textContent)")
    if ch != ['A', 'F#m', 'D', 'E/G#']: fail('G19 B♭ 차트를 A 로 옮긴 코드가 틀림: %s' % ch)
    print('G19 느슨한 키·키 모를 때·반감화음·베이스 글자 ok')
    c.close()

# ---------------------------------------------------------------- F90 AI 중 팀 전환
def t_ai_switch(b, errs):
    c, pg = new_page(b, errs, 'ai')
    signup(pg, 'ai' + tag); make_team(pg, 'X팀')
    X = pg.evaluate('CONTI.S.team.id'); uid = pg.evaluate('CONTI.NET.user.id')
    r = c.request.post(URL + 'api/teams', headers=H, data={'name': 'Y팀', 'myName': '하은', 'session': '인도자'})
    if r.status != 200: fail('F90 준비: 두 번째 팀을 못 만듦 %s' % r.text())
    Y = r.json()['teamId']
    pg.reload(); pg.wait_for_selector('.shell[data-page]', timeout=10000)
    if pg.evaluate('CONTI.S.team.id') != X: fail('F90 준비: 다시 열었더니 X팀이 아님')
    pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]'); pg.fill('[data-f="svc.name"]', 'X 예배')
    pg.click('[data-act="add-item"]'); pg.wait_for_selector('[data-f="item.title"]')
    pg.fill('[data-f="item.title"]', 'X팀전용곡'); pg.wait_for_timeout(400); pg.fill('[data-f="item.key"]', 'A'); pg.wait_for_timeout(400)
    pg.evaluate("(()=>{const it=CONTI.S.services[0].items[0];it.title='X팀전용곡';it.key='A';CONTI.save()})()")
    pg.set_input_files('#pieceFile', [SHEET])
    pg.wait_for_function("(()=>{const it=CONTI.S.services[0].items[0];return it&&(it.pieces||[]).length>0})()", timeout=30000)
    svc = pg.evaluate('CONTI.S.services[0].id')

    # 코드 인식 응답을 붙잡아 두고, 그 사이 Y팀으로 바꾼다
    held = []; bodies = []; gate = {'open': False}
    def hold(route):
        bodies.append(route.request.post_data_json)
        if gate['open']: route.continue_()
        else: held.append(route)
    pg.route('**/api/ocr', hold)
    pg.wait_for_selector('.chordbar [data-act="ocr"]', timeout=20000)
    pg.locator('.chordbar [data-act="ocr"]').first.click(); pg.wait_for_timeout(500)
    if pg.locator('#ocrGo').count(): pg.click('#ocrGo')
    for _ in range(60):
        if held: break
        pg.wait_for_timeout(250)
    if not held: fail('F90 준비: 코드 인식 요청이 안 나감')
    pg.goto(URL + '#/team'); pg.wait_for_selector('[data-act="team-switch"]', timeout=10000)
    pg.click('[data-act="team-switch"]'); pg.wait_for_selector('[data-switch="%s"]' % Y)
    pg.click('[data-switch="%s"]' % Y); pg.wait_for_function('CONTI.S.team.id===%s' % json.dumps(Y), timeout=10000)
    pg.wait_for_timeout(800)
    held[0].continue_(); pg.unroute('**/api/ocr')
    pg.wait_for_timeout(2500)
    if (bodies[0] or {}).get('teamId') != X: fail('F90 코드 인식이 X팀 몫으로 안 나감: %s' % (bodies[0] or {}).get('teamId'))

    # Y 에는 X 곡이 없어야 한다 (이 기기·서버 모두)
    ylib = pg.evaluate("CONTI.S.library.map(s=>s.title)")
    if 'X팀전용곡' in ylib: fail('F90 X팀 곡이 Y팀 라이브러리로 복사됨 (이 기기): %s' % ylib)
    if pg.evaluate("CONTI.S.services.some(s=>s.id===%s)" % json.dumps(svc)): fail('F90 X팀 콘티가 Y팀에 보임')
    pg.wait_for_timeout(3500)   # 라이브러리 올리기(3초 뒤)까지 기다린다
    srv = c.request.get(URL + 'api/library?team=' + Y, headers=H).json()
    if any(s.get('title') == 'X팀전용곡' for s in srv.get('songs', [])): fail('F90 X팀 곡이 Y팀 서버 라이브러리에 올라감')
    # X 저장본에는 결과가 들어가 있다 (인식 중으로 굳지 않는다)
    st = pg.evaluate("""(async()=>{const raw=await CONTI.IDB.get('kv','state:%s:%s');const s=JSON.parse(raw);
      const p=s.services.find(x=>x.id===%s).items[0].pieces[0];return {ocr:p.ocr,n:(p.chords||[]).length,lib:(s.library||[]).map(x=>x.title)}})()""" % (uid, X, json.dumps(svc)))
    if st['ocr'] != 'done' or st['n'] < 1: fail('F90 X팀 저장본에 인식 결과가 없음: %s' % st)
    if 'X팀전용곡' not in st['lib']: fail('F90 X팀 라이브러리에 곡이 안 들어감: %s' % st)
    print('F90 인식 중 팀을 바꿔도 결과는 X팀에, Y팀은 깨끗 ok:', st)

    # X 로 돌아오면 그대로 보인다
    pg.goto(URL + '#/team'); pg.wait_for_selector('[data-act="team-switch"]', timeout=10000)
    pg.click('[data-act="team-switch"]'); pg.wait_for_selector('[data-switch="%s"]' % X)
    pg.click('[data-switch="%s"]' % X); pg.wait_for_function('CONTI.S.team.id===%s' % json.dumps(X), timeout=10000)
    pg.wait_for_timeout(800)
    back = pg.evaluate("(()=>{const s=CONTI.S.services.find(x=>x.id===%s);const p=s&&s.items[0].pieces[0];return p&&{ocr:p.ocr,n:(p.chords||[]).length}})()" % json.dumps(svc))
    if not back or back['ocr'] != 'done' or back['n'] < 1: fail('F90 X팀으로 돌아왔는데 인식 결과가 없음: %s' % back)
    print('F90 X팀으로 돌아오면 결과가 그대로 ok')

    # 악보 만들기: 오선 줄마다 /score 를 부른다. 중간에 팀을 바꿔도 남은 줄은 X팀 몫, 결과도 X팀에
    if not pg.evaluate('!!CONTI.NET.omr'):
        print('F90 악보 만들기: 이 서버는 채보가 꺼져 있어 건너뜀'); c.close(); return
    pg.goto(URL + '#/edit/' + svc); pg.wait_for_selector('[data-act="score-make"]', timeout=15000)
    held.clear(); bodies.clear(); gate['open'] = False
    pg.route('**/api/score', hold)
    pg.click('[data-act="score-make"]')
    for _ in range(60):
        if held: break
        pg.wait_for_timeout(250)
    if not held: fail('F90 준비: 악보 만들기 요청이 안 나감')
    pg.goto(URL + '#/team'); pg.wait_for_selector('[data-act="team-switch"]', timeout=10000)
    pg.click('[data-act="team-switch"]'); pg.wait_for_selector('[data-switch="%s"]' % Y)
    pg.click('[data-switch="%s"]' % Y); pg.wait_for_function('CONTI.S.team.id===%s' % json.dumps(Y), timeout=10000)
    pg.wait_for_timeout(500)
    gate['open'] = True   # 붙잡은 줄을 풀고, 이어서 나가는 줄은 그대로 보낸다 (팀 id 만 적어 둔다)
    for rt in list(held): rt.continue_()
    for _ in range(120):   # IDB 는 비동기라 wait_for_function 으로는 못 기다린다
        if pg.evaluate("(async()=>{const s=JSON.parse(await CONTI.IDB.get('kv','state:%s:%s'));const it=s.services.find(x=>x.id===%s).items[0];return !!(it.score&&it.score.measures&&it.score.measures.length)})()" % (uid, X, json.dumps(svc))): break
        pg.wait_for_timeout(500)
    else: fail('F90 악보 만들기 결과가 X팀 저장본에 안 들어감')
    info = pg.evaluate("(async()=>{const s=JSON.parse(await CONTI.IDB.get('kv','state:%s:%s'));const sc=s.services.find(x=>x.id===%s).items[0].score;return {lines:sc.lines,failed:sc.failed,n:sc.measures.length}})()" % (uid, X, json.dumps(svc)))
    print('  악보:', info, '요청', len(bodies))
    teams = set((x or {}).get('teamId') for x in bodies)
    if teams != {X}: fail('F90 악보 만들기 호출이 다른 팀 몫으로 나감: %s' % teams)
    if pg.evaluate('CONTI.S.team.id') != Y or pg.evaluate("CONTI.S.services.some(s=>s.id===%s)" % json.dumps(svc)): fail('F90 악보 만들기 뒤 Y팀 화면이 X 콘티로 넘어감')
    if 'X팀전용곡' in pg.evaluate("CONTI.S.library.map(s=>s.title)"): fail('F90 악보 만들기 뒤 X 곡이 Y 라이브러리로 복사됨')
    print('F90 악보 만들기 중 팀을 바꿔도 X팀 몫·X팀 저장 ok (%d줄 붙잡음)' % len(bodies))

    # 채보: 결과 창이 Y팀 화면에서 떠도 '곡 정보에 적용'은 X팀 곡에
    pg.goto(URL + '#/team'); pg.wait_for_selector('[data-act="team-switch"]', timeout=10000)
    pg.click('[data-act="team-switch"]'); pg.wait_for_selector('[data-switch="%s"]' % X)
    pg.click('[data-switch="%s"]' % X); pg.wait_for_function('CONTI.S.team.id===%s' % json.dumps(X), timeout=10000)
    pg.goto(URL + '#/edit/' + svc); pg.wait_for_selector('[data-act="omr"]', timeout=15000)
    held.clear(); bodies.clear(); gate['open'] = False
    pg.route('**/api/omr', hold)
    pg.click('[data-act="omr"]')
    for _ in range(60):
        if held: break
        pg.wait_for_timeout(250)
    if not held: fail('F90 준비: 채보 요청이 안 나감')
    pg.goto(URL + '#/team'); pg.wait_for_selector('[data-act="team-switch"]', timeout=10000)
    pg.click('[data-act="team-switch"]'); pg.wait_for_selector('[data-switch="%s"]' % Y)
    pg.click('[data-switch="%s"]' % Y); pg.wait_for_function('CONTI.S.team.id===%s' % json.dumps(Y), timeout=10000)
    pg.wait_for_timeout(500)
    gate['open'] = True; held[0].continue_()
    pg.wait_for_selector('[data-apply="0"]', timeout=30000); pg.click('[data-apply="0"]'); pg.wait_for_timeout(1500)
    if (bodies[0] or {}).get('teamId') != X: fail('F90 채보가 X팀 몫으로 안 나감')
    if 'X팀전용곡' in pg.evaluate("CONTI.S.library.map(s=>s.title)"): fail('F90 채보 적용 뒤 X 곡이 Y 라이브러리로 복사됨')
    ch = pg.evaluate("(async()=>{const s=JSON.parse(await CONTI.IDB.get('kv','state:%s:%s'));const it=s.services.find(x=>x.id===%s).items[0];return !!(it.chart&&it.chart.sections&&it.chart.sections.length)})()" % (uid, X, json.dumps(svc)))
    if not ch: fail('F90 채보 적용이 X팀 곡에 안 들어감')
    print('F90 채보 적용도 X팀 곡에 ok')

    # 팀을 안 바꾸면 예전처럼: 악보를 만들고 악보 화면으로 간다
    pg.goto(URL + '#/team'); pg.wait_for_selector('[data-act="team-switch"]', timeout=10000)
    pg.click('[data-act="team-switch"]'); pg.wait_for_selector('[data-switch="%s"]' % X)
    pg.click('[data-switch="%s"]' % X); pg.wait_for_function('CONTI.S.team.id===%s' % json.dumps(X), timeout=10000)
    pg.evaluate("(()=>{const s=CONTI.S.services.find(x=>x.id===%s);delete s.items[0].score;CONTI.save()})()" % json.dumps(svc))
    pg.goto(URL + '#/edit/' + svc); pg.wait_for_selector('[data-act="score-make"]', timeout=15000)
    pg.click('[data-act="score-make"]')
    pg.wait_for_function("location.hash.startsWith('#score/')||location.hash.startsWith('#/score/')", timeout=60000)
    if not pg.evaluate("(()=>{const s=CONTI.S.services.find(x=>x.id===%s);return !!(s.items[0].score&&s.items[0].score.measures.length)})()" % json.dumps(svc)):
        fail('F90 같은 팀에서 악보 만들기가 안 들어감')
    if 'X팀전용곡' not in pg.evaluate("CONTI.S.library.map(s=>s.title)"): fail('F90 같은 팀 라이브러리에 곡이 없음')
    print('F90 팀을 안 바꾸면 예전처럼 ok')
    c.close()

# ---------------------------------------------------------------- F91 곡 넘기기가 서버를 기다리던 것
def t_nav(b, errs):
    c, pg = new_page(b, errs, 'nav')
    signup(pg, 'nv' + tag); make_team(pg, '넘김팀')
    pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]'); pg.fill('[data-f="svc.name"]', '넘김 예배')
    for t in ['첫곡', '둘째곡', '셋째곡']:
        pg.click('[data-act="add-item"]'); pg.wait_for_selector('[data-f="item.title"]'); pg.fill('[data-f="item.title"]', t); pg.wait_for_timeout(300)
    svc = pg.evaluate('CONTI.S.services[0].id')
    pg.goto(URL + '#/play/%s/0' % svc); pg.wait_for_function('CONTI.pl().idx===0&&!!document.querySelector(".songnav")', timeout=10000)
    pg.wait_for_timeout(800)
    # 이제부터 메모·말씀 응답을 붙잡는다 (느린 망)
    held = []; gate = {'open': False}
    def hold(route):
        if gate['open']: route.continue_()
        else: held.append(route)
    pg.route('**/api/notes?**', hold); pg.route('**/api/services/*/word?**', hold)
    t0 = time.time(); pg.click('.songnav [data-act="pn"][data-d="1"]')
    pg.wait_for_function('CONTI.pl().idx===1', timeout=12000); dt = time.time() - t0
    if dt > 1.5: fail('F91 다음 곡으로 넘기는 데 %.1f초 (서버를 기다림)' % dt)
    t0 = time.time(); pg.click('.songnav [data-act="pn"][data-d="1"]')
    pg.wait_for_function('CONTI.pl().idx===2', timeout=12000); dt2 = time.time() - t0
    if dt2 > 1.5: fail('F91 셋째 곡으로 넘기는 데 %.1f초' % dt2)
    print('F91 곡 넘기기 즉시 ok (%.2fs, %.2fs)' % (dt, dt2))
    # 콘티에 새로 들어올 때도 응답이 안 오면 오래 멈추지 않는다 (가진 것으로 먼저 그림)
    pg.goto(URL + '#/'); pg.wait_for_timeout(800)
    t0 = time.time(); pg.goto(URL + '#/view/%s' % svc)
    pg.wait_for_function("location.hash.indexOf('view/')>=0&&!!document.querySelector('#app .top')&&document.body.innerText.indexOf('첫곡')>=0", timeout=15000)
    dt3 = time.time() - t0
    if dt3 > 4: fail('F91 콘티를 여는 데 %.1f초 (응답 없는 서버를 끝까지 기다림)' % dt3)
    print('F91 느린 서버여도 콘티를 먼저 엶 ok (%.1fs)' % dt3)
    # 늦게 온 메모는 보기 화면에 다시 그려진다
    pg.evaluate("""fetch('/api/notes',{method:'POST',headers:{'content-type':'application/json','x-conti':'1'},
      body:JSON.stringify({teamId:CONTI.S.team.id,serviceId:%s,notes:[{id:'late-'+Date.now().toString(36)+Math.random().toString(36).slice(2,8),itemId:CONTI.S.services[0].items[0].id,layer:'leader',text:'늦게 온 메모',at:Date.now()}]})})""" % json.dumps(svc))
    gate['open'] = True
    for rt in list(held): rt.continue_()
    pg.wait_for_function("CONTI.S.services[0].items[0].notes.some(n=>n.text==='늦게 온 메모')", timeout=10000)
    pg.wait_for_function("document.body.innerText.indexOf('늦게 온 메모')>=0", timeout=5000)
    print('F91 늦게 온 메모도 화면에 ok')
    c.close()

# F91 되돌림: 들어올 때 받기가 늦게 실패하면 (1) 보기 화면이 다시 그리기 → 또 받기를 되풀이했고 (2) 곡을 넘길 때마다 또 2.5초씩 기다렸다.
# (3) 콘티 안에서 옮기면 메모·말씀을 다시 안 받아, 보기에 있다 편집으로 가면 목회자가 쓴 말씀이 비어 보였다(쓰면 덮어씀)
NOTES_FAIL = r"""
(()=>{window.__nf=0;const F=window.fetch;
 window.fetch=function(u,o){const s=String((u&&u.url)||u);
  if(sessionStorage.getItem('failNotes')==='1'&&/\/api\/notes\?/.test(s)&&!(o&&o.method&&o.method!=='GET')){window.__nf++;
   return new Promise((_,rej)=>setTimeout(()=>rej(new TypeError('Failed to fetch')),3500))}
  return F.apply(this,arguments)}})();
"""
def t_nav_more(b, errs):
    c, pg = new_page(b, errs, 'nav2')
    c.add_init_script(NOTES_FAIL)
    signup(pg, 'nw' + tag); make_team(pg, '넘김둘팀')
    pg.click('[data-act="new-svc"]'); pg.wait_for_selector('[data-f="svc.name"]'); pg.fill('[data-f="svc.name"]', '넘김 예배2')
    for t in ['첫곡', '둘째곡', '셋째곡']:
        pg.click('[data-act="add-item"]'); pg.wait_for_selector('[data-f="item.title"]'); pg.fill('[data-f="item.title"]', t); pg.wait_for_timeout(300)
    svc = pg.evaluate('CONTI.S.services[0].id')
    pg.goto(URL + '#/view/%s' % svc); pg.wait_for_function("document.body.innerText.indexOf('둘째곡')>=0", timeout=10000); pg.wait_for_timeout(800)
    put_word = """(p)=>fetch('/api/services/'+CONTI.S.services[0].id+'/word',{method:'PUT',headers:{'content-type':'application/json','x-conti':'1'},
      body:JSON.stringify({teamId:CONTI.S.team.id,word:{passage:p,title:'',line:'',memo:''}})}).then(r=>r.status)"""
    post_note = """(t)=>fetch('/api/notes',{method:'POST',headers:{'content-type':'application/json','x-conti':'1'},
      body:JSON.stringify({teamId:CONTI.S.team.id,serviceId:CONTI.S.services[0].id,notes:[{id:'nt'+Date.now().toString(36)+Math.random().toString(36).slice(2,8),itemId:CONTI.S.services[0].items[0].id,layer:'leader',text:t,at:Date.now()}]})}).then(r=>r.status)"""
    # (3) 다른 기기에서 쓴 메모 · 말씀이 콘티 안에서 옮길 때 들어온다
    if pg.evaluate(post_note, '다른 기기 메모') != 200: fail('F91 준비: 메모 올리기 실패')
    pg.goto(URL + '#/play/%s/0' % svc); pg.wait_for_function('CONTI.pl().idx===0&&!!document.querySelector(".songnav")', timeout=10000)
    try: pg.wait_for_function("CONTI.S.services[0].items[0].notes.some(n=>n.text==='다른 기기 메모')", timeout=6000)
    except Exception: fail('F91 보기에서 연습으로 옮겼는데 다른 기기의 메모를 안 받음')
    if pg.evaluate(put_word, '로마서 8:28') != 200: fail('F91 준비: 말씀 올리기 실패')
    pg.goto(URL + '#/edit/%s' % svc); pg.wait_for_selector('[data-f="svc.name"]', timeout=10000)
    w = pg.evaluate("(CONTI.S.services[0].word||{}).passage||''")
    if w != '로마서 8:28': fail('F91 보기·연습에서 편집으로 옮겼는데 서버의 말씀을 안 받음: %r' % w)
    print('F91 콘티 안에서 옮길 때 메모·말씀 새로 받음 ok')

    # (1) 들어올 때 받기가 늦게 실패해도 보기 화면을 되풀이해 다시 그리지 않는다
    pg.goto(URL + '#/'); pg.wait_for_timeout(500)
    pg.evaluate("sessionStorage.setItem('failNotes','1')"); pg.reload(); pg.wait_for_selector('.shell[data-page]', timeout=10000); pg.wait_for_timeout(800)
    pg.goto(URL + '#/view/%s' % svc)
    pg.wait_for_function("location.hash.indexOf('view/')>=0&&document.body.innerText.indexOf('둘째곡')>=0", timeout=10000)
    pg.wait_for_timeout(300)
    pg.evaluate("document.querySelector('#app').firstElementChild.__mark=1")
    pg.wait_for_timeout(9000)
    n = pg.evaluate('window.__nf'); kept = pg.evaluate("!!(document.querySelector('#app').firstElementChild||{}).__mark")
    if n != 1: fail('F91 받기가 실패하자 메모를 %d번 다시 받음 (1번이어야)' % n)
    if not kept: fail('F91 받기가 늦게 실패했는데 보기 화면을 다시 그림')
    print('F91 늦게 실패해도 다시 그리기·다시 받기를 되풀이 안 함 ok')

    # (2) 받기가 실패한 채로 연습으로 옮겨 곡을 넘겨도 기다리지 않는다
    t0 = time.time(); pg.goto(URL + '#/play/%s/0' % svc)
    pg.wait_for_function('CONTI.pl().idx===0&&!!document.querySelector(".songnav")', timeout=10000); dt0 = time.time() - t0
    t0 = time.time(); pg.click('.songnav [data-act="pn"][data-d="1"]')
    pg.wait_for_function('CONTI.pl().idx===1', timeout=12000); dt1 = time.time() - t0
    t0 = time.time(); pg.click('.songnav [data-act="pn"][data-d="1"]')
    pg.wait_for_function('CONTI.pl().idx===2', timeout=12000); dt2 = time.time() - t0
    if max(dt0, dt1, dt2) > 1.5: fail('F91 받기가 실패한 뒤 옮길 때마다 기다림: %.2f %.2f %.2f' % (dt0, dt1, dt2))
    print('F91 받기가 실패한 채로도 곡 넘기기 즉시 ok (%.2f, %.2f, %.2f)' % (dt0, dt1, dt2))
    pg.evaluate("sessionStorage.removeItem('failNotes')")
    c.close()

# ---------------------------------------------------------------- G20 스스로 나간 사람
def t_leave(b, errs):
    cl, L = new_page(b, errs, 'leader')
    signup(L, 'lv' + tag, '인도'); make_team(L, '떠날팀')
    team = L.evaluate('CONTI.S.team.id'); code = L.evaluate('CONTI.S.team.invite')
    cm, M = new_page(b, errs, 'member', viewport={'width': 430, 'height': 900})
    signup(M, 'lm' + tag, '지우'); M.wait_for_selector('#gtTeam', timeout=10000)
    M.goto(URL + '#/join/' + code); M.wait_for_selector('#jnName', timeout=10000)
    M.click('[data-act="team-join"]'); M.wait_for_selector('.shell[data-page]', timeout=10000)
    muid = M.evaluate('CONTI.NET.user.id')

    # 스스로 나간다 → 팀 없는 화면 (팀 만들기가 있다), '인도자에게 문의' 가 아니다
    M.goto(URL + '#/team'); M.wait_for_selector('[data-sopen="team"]', timeout=10000)
    if not M.locator('.tsec[data-sect="team"].on').count(): M.click('[data-sopen="team"]'); M.wait_for_timeout(250)
    M.click('[data-act="tm-leave"]')
    M.wait_for_selector('#gtTeam', timeout=10000)
    body = M.locator('#app').inner_text()
    if '인도자에게 문의' in body: fail('G20 스스로 나갔는데 인도자가 막은 화면이 나옴')
    if not M.locator('[data-act="team-create"]').count(): fail('G20 나간 뒤 팀 만들기가 없음')
    M.reload(); M.wait_for_selector('#gtTeam', timeout=10000)
    if '인도자에게 문의' in M.locator('#app').inner_text(): fail('G20 다시 열었더니 막힌 화면')
    me = cm.request.get(URL + 'api/me', headers=H).json()
    if me.get('blocked'): fail('G20 서버가 스스로 나간 사람을 blocked 로 줌: %s' % me.get('blocked'))
    print('G20 스스로 나가면 팀 없는 화면 ok')

    # 같은 팀 초대 링크로 다시 들어올 수 있다 ('이미 ○○ 팀에 있어요'로 돌려보내지 않는다)
    M.goto(URL + '#/join/' + code); M.wait_for_selector('#jnName', timeout=10000)
    M.click('[data-act="team-join"]'); M.wait_for_selector('.shell[data-page]', timeout=10000)
    if M.evaluate('CONTI.S.team.id') != team: fail('G20 초대 링크로 다시 들어오지 못함')
    print('G20 초대 링크로 다시 들어오기 ok')

    # 인도자가 비활성으로 두면 예전처럼 막힌 화면 — 다만 내 팀은 만들 수 있다
    r = cl.request.patch(URL + 'api/teams/%s/members/%s' % (team, muid), headers=H, data={'active': False})
    if r.status != 200: fail('G20 준비: 비활성으로 못 둠 %s %s' % (r.status, r.text()))
    M.reload(); M.wait_for_selector('.auth-card', timeout=10000); M.wait_for_timeout(500)
    body = M.locator('#app').inner_text()
    if '인도자에게 문의' not in body: fail('G20 인도자가 비활성으로 뒀는데 막힌 화면이 아님:\n' + body[:200])
    if not M.locator('[data-act="team-create"]').count(): fail('G20 막힌 화면에 팀 만들기가 없음')
    M.fill('#gtTeam', '내새팀'); M.click('[data-act="team-create"]'); M.wait_for_selector('.shell[data-page]', timeout=10000)
    print('G20 비활성 화면에서도 팀 만들기 ok')
    cl.close(); cm.close()

TESTS = [('F25', t_push_off), ('F25R', t_push_relogin), ('SCORE', t_score), ('SCMODE', t_score_mode), ('CHORD', t_chords), ('CHORD2', t_chords_more), ('F90', t_ai_switch), ('F91', t_nav), ('F91B', t_nav_more), ('G20', t_leave)]

def run():
    only = set(sys.argv[1:])
    with sync_playwright() as p:
        b = p.chromium.launch(); errs = []
        for name, fn in TESTS:
            if only and name not in only: continue
            fn(b, errs)
        b.close()
    errs = [e for e in errs if 'ResizeObserver' not in e]
    if errs: fail('JS 오류: %s' % errs[:3])
    print('OK')

if __name__ == '__main__':
    run()
