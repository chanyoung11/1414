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
      body:JSON.stringify({teamId:CONTI.S.team.id,serviceId:%s,notes:[{id:'late-note-1',itemId:CONTI.S.services[0].items[0].id,layer:'leader',text:'늦게 온 메모',at:Date.now()}]})})""" % json.dumps(svc))
    gate['open'] = True
    for rt in list(held): rt.continue_()
    pg.wait_for_function("CONTI.S.services[0].items[0].notes.some(n=>n.text==='늦게 온 메모')", timeout=10000)
    pg.wait_for_function("document.body.innerText.indexOf('늦게 온 메모')>=0", timeout=5000)
    print('F91 늦게 온 메모도 화면에 ok')
    c.close()

TESTS = [('F25', t_push_off), ('SCORE', t_score), ('CHORD', t_chords), ('F90', t_ai_switch), ('F91', t_nav)]

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
